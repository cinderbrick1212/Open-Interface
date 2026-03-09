"""Shared pytest fixtures for Open Interface tests.

Provides mock/stub versions of Screen, Interpreter, LLM, and Core
so that tests can run in headless CI environments without a display
server, Ollama, or any API keys.
"""

import json
import os
import sys
import tempfile
from multiprocessing import Queue
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure the app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


# ── Helpers ──────────────────────────────────────────────────────────

_VALID_LLM_RESPONSE = {
    'steps': [
        {
            'function': 'click_cell',
            'parameters': {'cell': 'F12'},
            'human_readable_justification': 'Clicking the submit button',
        }
    ],
    'done': None,
}

_DONE_LLM_RESPONSE = {
    'steps': [],
    'done': 'Task completed successfully.',
}


def make_chat_completion_response(content: str) -> MagicMock:
    """Build a mock ``openai.ChatCompletion`` response object."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_settings_dir(tmp_path):
    """Return a temporary settings directory and patch Settings to use it."""
    settings_dir = str(tmp_path) + '/.noclip-desktop/'
    os.makedirs(settings_dir, exist_ok=True)
    with patch('utils.settings.Settings.get_settings_directory_path', return_value=settings_dir):
        yield settings_dir


@pytest.fixture
def mock_screen():
    """A mock Screen that returns a fake 1920x1080 screenshot."""
    screen = MagicMock()
    screen.get_size.return_value = (1920, 1080)
    screen.get_capture_region.return_value = (0, 0, 1920, 1080)
    screen.get_gridded_screenshot_in_base64.return_value = 'fake_base64_screenshot_data'
    screen.get_screenshot_in_base64.return_value = 'fake_base64_screenshot_data'
    screen.cell_map = {f'{chr(65 + c)}{r}': (c * 50, r * 50)
                       for c in range(26) for r in range(1, 21)}
    return screen


@pytest.fixture
def mock_interpreter():
    """A mock Interpreter that always succeeds."""
    interp = MagicMock()
    interp.process_command.return_value = True
    interp.process_commands.return_value = True
    interp.cell_map = {}
    return interp


@pytest.fixture
def mock_openai_client():
    """A mock OpenAI client returning a valid JSON response."""
    client = MagicMock()
    resp = make_chat_completion_response(json.dumps(_DONE_LLM_RESPONSE))
    client.chat.completions.create.return_value = resp
    return client


@pytest.fixture
def valid_llm_response():
    """Return a valid LLM response dict with steps."""
    return _VALID_LLM_RESPONSE.copy()


@pytest.fixture
def done_llm_response():
    """Return a valid LLM response dict with done=True."""
    return _DONE_LLM_RESPONSE.copy()


@pytest.fixture
def sample_settings() -> dict:
    """Return a sample settings dictionary."""
    return {
        'provider': 'Ollama',
        'model': 'llama3.2',
        'ollama_endpoint': 'http://localhost:11434',
        'default_browser': 'Chrome',
        'play_ding_on_completion': False,
    }


@pytest.fixture
def ollama_settings_factory():
    """Factory fixture that returns settings for a given Ollama model."""
    def _make(model_name: str, endpoint: str = 'http://localhost:11434') -> dict:
        return {
            'provider': 'Ollama',
            'model': model_name,
            'ollama_endpoint': endpoint,
            'default_browser': '',
        }
    return _make


@pytest.fixture
def browser_settings_factory():
    """Factory fixture that returns settings for a given browser."""
    def _make(browser: str) -> dict:
        return {
            'provider': 'Ollama',
            'model': 'llama3.2',
            'ollama_endpoint': 'http://localhost:11434',
            'default_browser': browser,
        }
    return _make
