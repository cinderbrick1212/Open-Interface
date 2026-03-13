"""Tests for Phase 3 LangGraph migration.

Validates:
- Agent state model
- Graph creation and compilation
- Plan → Act → Done flow
- Plan → Act → Loop → Done flow
- MAX_STEPS termination
- Error propagation
- Interrupt handling
"""

import os
import sys
from multiprocessing import Queue
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


class TestAgentState:
    """Test the state model can be imported and used."""

    def test_state_import(self):
        from agent_state import AgentState
        state: AgentState = {
            'user_request': 'test',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        }
        assert state['user_request'] == 'test'
        assert state['step_num'] == 0


class TestAgentGraph:
    """Test the LangGraph agent with mocked LLM."""

    def _make_agent(self, llm_responses, max_steps=30):
        """Helper: build an agent with a mock LLM returning predefined responses."""
        from agent import create_agent

        mock_llm = MagicMock()
        mock_llm.get_instructions_for_objective = MagicMock(
            side_effect=llm_responses
        )
        mock_interpreter = MagicMock()
        mock_interpreter.process_command = MagicMock(return_value=True)
        mock_screen = MagicMock()
        mock_screen.cell_map = {}
        status_queue = Queue()

        agent = create_agent(
            llm=mock_llm,
            interpreter=mock_interpreter,
            screen=mock_screen,
            status_queue=status_queue,
            max_steps=max_steps,
        )
        return agent, mock_llm, mock_interpreter, status_queue

    def test_single_step_done(self):
        """LLM returns done on first call — graph should terminate."""
        responses = [
            {'steps': [{'function': 'click_cell', 'parameters': {'cell': 'A1'},
                        'human_readable_justification': 'test'}],
             'done': 'Task completed'}
        ]
        agent, mock_llm, mock_interp, _ = self._make_agent(responses)
        result = agent.invoke({
            'user_request': 'click A1',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        })
        assert result['done'] == 'Task completed'
        mock_llm.get_instructions_for_objective.assert_called_once()
        mock_interp.process_command.assert_called_once()

    def test_two_step_loop(self):
        """LLM returns done=None first, then done='ok' — graph loops once."""
        responses = [
            {'steps': [{'function': 'press', 'parameters': {'key': 'enter'},
                        'human_readable_justification': 'step 1'}],
             'done': None},
            {'steps': [], 'done': 'Finished'},
        ]
        agent, mock_llm, _, _ = self._make_agent(responses)
        result = agent.invoke({
            'user_request': 'do something',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        })
        assert result['done'] == 'Finished'
        assert mock_llm.get_instructions_for_objective.call_count == 2

    def test_max_steps_termination(self):
        """Graph should stop after max_steps even if LLM never says done."""
        # Return no-done responses forever
        infinite_responses = [
            {'steps': [], 'done': None}
        ] * 10
        agent, mock_llm, _, _ = self._make_agent(infinite_responses, max_steps=3)
        result = agent.invoke({
            'user_request': 'loop forever',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        })
        assert result.get('done') is not None
        assert 'maximum step limit' in result['done'].lower() or 'max' in result['done'].lower()
        assert mock_llm.get_instructions_for_objective.call_count <= 3

    def test_execution_failure(self):
        """If interpreter returns False, graph should stop with error."""
        from agent import create_agent

        mock_llm = MagicMock()
        mock_llm.get_instructions_for_objective.return_value = {
            'steps': [{'function': 'click', 'parameters': {'x': 0, 'y': 0},
                       'human_readable_justification': 'bad click'}],
            'done': None,
        }
        mock_interpreter = MagicMock()
        mock_interpreter.process_command.return_value = False  # Failure
        mock_screen = MagicMock()
        mock_screen.cell_map = {}

        agent = create_agent(
            llm=mock_llm,
            interpreter=mock_interpreter,
            screen=mock_screen,
            status_queue=Queue(),
            max_steps=30,
        )
        result = agent.invoke({
            'user_request': 'bad command',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        })
        assert result.get('error') == 'Unable to execute the request'

    def test_interrupt_handling(self):
        """Graph should stop if interrupt_check returns True."""
        from agent import create_agent

        mock_llm = MagicMock()
        mock_llm.get_instructions_for_objective.return_value = {
            'steps': [{'function': 'press', 'parameters': {'key': 'a'},
                       'human_readable_justification': 'typing'}],
            'done': None,
        }
        mock_interpreter = MagicMock()
        mock_interpreter.process_command.return_value = True
        mock_screen = MagicMock()
        mock_screen.cell_map = {}

        agent = create_agent(
            llm=mock_llm,
            interpreter=mock_interpreter,
            screen=mock_screen,
            status_queue=Queue(),
            max_steps=30,
            interrupt_check=lambda: True,  # Always interrupted
        )
        result = agent.invoke({
            'user_request': 'interrupted',
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        })
        assert result.get('done') == 'Interrupted'


class TestCoreLangGraphToggle:
    """Test that Core respects the use_langgraph setting."""

    def test_default_no_langgraph(self):
        """By default, Core should use the recursive execute() path."""
        from core import Core
        with patch('core.LLM'), \
             patch('core.Screen'), \
             patch('core.Settings') as MockSettings:
            MockSettings.return_value.get_dict.return_value = {}
            c = Core()
            # execute_user_request should call self.execute, not _execute_langgraph
            c.execute = MagicMock()
            c.execute_user_request('test')
            c.execute.assert_called_once_with('test')
