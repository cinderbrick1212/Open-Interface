"""LangGraph-based execution agent for Noclip Desktop.

Replaces the recursive core.execute() loop with a structured state graph:
  plan → act → (loop or done)

Reuses the existing LLM class and Interpreter — no model classes are modified.
"""

from typing import Any, Callable, Optional

from langgraph.graph import StateGraph, END
from agent_state import AgentState


def create_agent(
    llm,
    interpreter,
    screen,
    status_queue,
    max_steps: int,
    max_steps: int,
    exec_client=None,
    browser_client=None,
    interrupt_check: Optional[Callable[[], bool]] = None,
):
    """Build and compile the execution graph.

    Args:
        llm: The existing LLM instance (has get_instructions_for_objective).
        interpreter: The Interpreter instance for direct command dispatch.
        screen: The Screen instance (provides cell_map after screenshots).
        status_queue: multiprocessing.Queue for UI status updates.
        max_steps: Maximum number of plan iterations before forced stop.
        exec_client: Optional ExecutionClient for sandboxed execution.
        interrupt_check: Callable returning True if the user requested a stop.

    Returns:
        A compiled LangGraph runnable.
    """

    def plan(state: AgentState) -> dict:
        """Call the LLM to get the next set of instructions."""
        step_num = state.get('step_num', 0)

        # Check max steps
        if step_num >= max_steps:
            msg = f'Reached maximum step limit ({max_steps}). Stopping to prevent infinite loop.'
            status_queue.put(msg)
            return {'done': msg, 'error': None}

        try:
            # Inject DOM context if available
            dom_context = None
            if browser_client and browser_client.is_available():
                dom_context = browser_client.get_dom_context()
            
            prompt = state['user_request']
            if dom_context and dom_context.get('nodes'):
                import json
                nodes_str = json.dumps(dom_context['nodes'])
                prompt += f"\n\n[Active Browser DOM Context for {dom_context.get('url')}]:\n{nodes_str}"
            
            instructions = llm.get_instructions_for_objective(
                prompt, step_num
            )

            # Sync cell map
            interpreter.cell_map = screen.cell_map
            if exec_client:
                exec_client.set_cell_map(screen.cell_map)

            # Handle empty/malformed response — retry once
            if instructions == {}:
                instructions = llm.get_instructions_for_objective(
                    state['user_request'] + ' Please reply in valid JSON',
                    step_num,
                )
                interpreter.cell_map = screen.cell_map
                if exec_client:
                    exec_client.set_cell_map(screen.cell_map)

            return {
                'instructions': instructions,
                'step_num': step_num + 1,
                'error': None,
            }
        except Exception as e:
            msg = f'Exception Unable to execute the request - {e}'
            status_queue.put(msg)
            return {'error': msg}

    def act(state: AgentState) -> dict:
        """Execute each step from the latest instructions."""
        instructions = state.get('instructions', {})

        for step in instructions.get('steps', []):
            if interrupt_check and interrupt_check():
                status_queue.put('Interrupted')
                return {'done': 'Interrupted'}

            func = step.get('function')
            params = step.get('parameters', {})

            if func == 'click_dom_id' and browser_client:
                success = browser_client.click_dom_id(params.get('node_id'))
            elif func == 'type_dom_id' and browser_client:
                success = browser_client.type_dom_id(params.get('node_id'), params.get('text'))
            elif exec_client:
                success = exec_client.execute_command(step)
            else:
                success = interpreter.process_command(step)

            if not success:
                return {'error': 'Unable to execute the request'}

        # Check the done field from the LLM
        done = instructions.get('done')
        if done:
            status_queue.put(done)
            return {'done': done}

        status_queue.put('Fetching further instructions based on current state')
        return {'done': None}

    def should_continue_from_plan(state: AgentState) -> str:
        """Route from plan: END if done/error during planning, else continue to act."""
        if state.get('error'):
            return 'end'
        if state.get('done'):
            return 'end'
        return 'act'

    def should_continue_from_act(state: AgentState) -> str:
        """Route from act: END if done/error, else loop back to plan."""
        if state.get('error'):
            return 'end'
        if state.get('done'):
            return 'end'
        return 'plan'

    # Build the graph
    graph = StateGraph(AgentState)
    graph.add_node('plan', plan)
    graph.add_node('act', act)
    graph.set_entry_point('plan')
    
    # Conditional route out of plan (handles max_steps shortcircuit)
    graph.add_conditional_edges('plan', should_continue_from_plan, {
        'act': 'act',
        'end': END,
    })
    
    # Conditional route out of act
    graph.add_conditional_edges('act', should_continue_from_act, {
        'plan': 'plan',
        'end': END,
    })

    return graph.compile()
