import time
from multiprocessing import Queue
from typing import Optional, Any

from openai import OpenAIError

from interpreter import Interpreter
from execution_client import ExecutionClient
from llm import LLM
from utils.screen import Screen
from utils.settings import Settings
MAX_STEPS = 30


class Core:
    def __init__(self):
        self.status_queue = Queue()
        self.interrupt_execution = False
        self.settings_dict = Settings().get_dict()

        self.screen = Screen()
        self.interpreter = Interpreter(self.status_queue)

        # Opt-in: use sandboxed execution service instead of direct interpreter
        self._use_sandbox = self.settings_dict.get('use_sandboxed_execution', False)
        self._exec_client = None
        if self._use_sandbox:
            self._exec_client = ExecutionClient()

        # Opt-in: use browser extension via websocket
        self._browser_service = None
        self._browser_client = None
        if self.settings_dict.get('use_browser_extension', True):
            try:
                from browser_service import BrowserService
                from browser_client import BrowserClient
                self._browser_service = BrowserService()
                self._browser_service.start()
                self._browser_client = BrowserClient(self._browser_service)
            except Exception as e:
                self.status_queue.put(f"Failed to start BrowserService: {e}")

        self.llm = None
        try:
            self.llm = LLM(self.screen)
        except OpenAIError as e:
            self.status_queue.put(f'Set your OpenAPI API Key in Settings and Restart the App. Error: {e}')
        except Exception as e:
            self.status_queue.put(f'An error occurred during startup. Please fix and restart the app.\n'
                                  f'Error likely in file {Settings().settings_file_path}.\n'
                                  f'Error: {e}')

    def set_capture_region(self, region: Optional[tuple[int, int, int, int]]) -> None:
        """Set the screen capture region. None means full screen."""
        self.screen.set_capture_region(region)

    def set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable keyboard/mouse command execution."""
        self.interpreter.controls_enabled = enabled
        if self._exec_client:
            self._exec_client.set_controls_enabled(enabled)

    def execute_user_request(self, user_request: str) -> None:
        self.stop_previous_request()
        time.sleep(0.1)
        if self.settings_dict.get('use_langgraph', False) and self.llm:
            self._execute_langgraph(user_request)
        else:
            self.execute(user_request)

    def stop_previous_request(self) -> None:
        self.interrupt_execution = True
        # Cancel any in-progress prefetch so the background thread stops early
        self._cancel_model_prefetch()

    def execute(self, user_request: str, step_num: int = 0) -> Optional[str]:
        """
            This function might recurse.

            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already
                in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        self.interrupt_execution = False

        if step_num >= MAX_STEPS:
            status = f'Reached maximum step limit ({MAX_STEPS}). Stopping to prevent infinite loop.'
            self.status_queue.put(status)
            return status

        if not self.llm:
            status = 'Set your OpenAPI API Key in Settings and Restart the App'
            self.status_queue.put(status)
            return status

        try:
            instructions: dict[str, Any] = self.llm.get_instructions_for_objective(user_request, step_num)

            # Sync the cell map from the latest gridded screenshot to the interpreter
            self.interpreter.cell_map = self.screen.cell_map
            if self._exec_client:
                self._exec_client.set_cell_map(self.screen.cell_map)

            if instructions == {}:
                # Sometimes LLM sends malformed JSON response, in that case retry once more.
                instructions = self.llm.get_instructions_for_objective(user_request + ' Please reply in valid JSON',
                                                                       step_num)
                # Sync the cell map after retry
                self.interpreter.cell_map = self.screen.cell_map
            if self._exec_client:
                self._exec_client.set_cell_map(self.screen.cell_map)

            for step in instructions['steps']:
                if self.interrupt_execution:
                    self._cancel_model_prefetch()
                    self.status_queue.put('Interrupted')
                    self.interrupt_execution = False
                    return 'Interrupted'

                if self._exec_client:
                    success = self._exec_client.execute_command(step)
                else:
                    success = self.interpreter.process_command(step)

                if not success:
                    return 'Unable to execute the request'

        except Exception as e:
            status = f'Exception Unable to execute the request - {e}'
            self.status_queue.put(status)
            return status

        if instructions['done']:
            # Communicate Results
            self.status_queue.put(instructions['done'])
            self.play_ding_on_completion()
            return instructions['done']
        else:
            # Not done — kick off a prefetch so the next iteration's vision
            # analysis runs in parallel with the recursive-call setup.
            self._start_model_prefetch()
            self.status_queue.put('Fetching further instructions based on current state')
            return self.execute(user_request, step_num + 1)

    def _execute_langgraph(self, user_request: str) -> Optional[str]:
        """Execute via the LangGraph agent (opt-in alternative to recursive execute)."""
        from agent import create_agent

        agent = create_agent(
            llm=self.llm,
            interpreter=self.interpreter,
            screen=self.screen,
            status_queue=self.status_queue,
            max_steps=MAX_STEPS,
            exec_client=self._exec_client,
            browser_client=self._browser_client,
            interrupt_check=lambda: self.interrupt_execution,
        )

        initial_state: dict = {
            'user_request': user_request,
            'step_num': 0,
            'instructions': {},
            'done': None,
            'error': None,
        }

        result = agent.invoke(initial_state)

        if result.get('error'):
            return result['error']
        if result.get('done'):
            self.play_ding_on_completion()
            return result['done']
        return None

    # ------------------------------------------------------------------
    # Prefetch helpers — delegate to model if it supports pipelining
    # ------------------------------------------------------------------

    def _start_model_prefetch(self) -> None:
        """Ask the active model to start its next vision analysis in the
        background.  Models that do not support prefetching simply ignore
        this call."""
        model = getattr(self.llm, 'model', None)
        if model is not None and hasattr(model, 'prefetch_analysis'):
            model.prefetch_analysis()

    def _cancel_model_prefetch(self) -> None:
        """Cancel any in-progress prefetch (e.g. on user interrupt)."""
        model = getattr(self.llm, 'model', None) if self.llm else None
        if model is not None and hasattr(model, 'cancel_prefetch'):
            model.cancel_prefetch()

    def play_ding_on_completion(self):
        # Play ding sound to signal completion
        if self.settings_dict.get('play_ding_on_completion'):
            print('\a')

    def cleanup(self):
        self.llm.cleanup()
        if self._exec_client:
            self._exec_client.shutdown()
        if self._browser_service:
            self._browser_service.stop()
