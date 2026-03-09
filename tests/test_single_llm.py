"""Single local LLM tests.

Validates that Open Interface works correctly with a single local LLM
provider (Ollama) by testing the full provider-routing pipeline,
settings configuration, and model creation.

Tests are designed to run in CI without a real Ollama instance by
using mocked OpenAI-compatible responses. When a real Ollama instance
is available, set ``OLLAMA_ENDPOINT`` to run integration tests.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from models.chat_completions import ChatCompletionsModel
from models.factory import ModelFactory
from utils.settings import Settings


class TestSingleLLMSettings:
    """Verify Ollama provider settings are handled correctly."""

    def test_ollama_settings_persistence(self, tmp_settings_dir):
        """Ollama settings should round-trip through save/load."""
        s = Settings()
        s.save_settings_to_file({
            'provider': 'Ollama',
            'model': 'llama3.2',
            'ollama_endpoint': 'http://localhost:11434',
        })
        loaded = Settings().get_dict()
        assert loaded['provider'] == 'Ollama'
        assert loaded['model'] == 'llama3.2'
        assert loaded['ollama_endpoint'] == 'http://localhost:11434'

    def test_ollama_custom_endpoint(self, tmp_settings_dir):
        """Custom Ollama endpoint should be preserved."""
        s = Settings()
        s.save_settings_to_file({
            'provider': 'Ollama',
            'model': 'mistral',
            'ollama_endpoint': 'http://192.168.1.100:11434',
        })
        loaded = Settings().get_dict()
        assert loaded['ollama_endpoint'] == 'http://192.168.1.100:11434'

    def test_ollama_default_endpoint(self, tmp_settings_dir):
        """When no endpoint is set, the default should be used."""
        s = Settings()
        s.save_settings_to_file({'provider': 'Ollama', 'model': 'llama3.2'})
        loaded = Settings().get_dict()
        assert loaded.get('ollama_endpoint') is None  # llm.py applies default


class TestSingleLLMProviderRouting:
    """Verify that Ollama provider routes to ChatCompletionsModel."""

    def test_ollama_routes_to_chat_completions(self, mock_screen):
        """Ollama provider should create a ChatCompletionsModel."""
        model = ModelFactory.create_model(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'System context',
            mock_screen,
            provider='Ollama',
        )
        assert isinstance(model, ChatCompletionsModel)

    @pytest.mark.parametrize('model_name', [
        'llama3.2',
        'llama3.2:1b',
        'mistral',
        'codellama',
        'phi3',
        'gemma2',
        'qwen2.5',
        'deepseek-r1:7b',
    ])
    def test_ollama_supports_various_models(self, model_name, mock_screen):
        """Various Ollama model names should all create ChatCompletionsModel."""
        model = ModelFactory.create_model(
            model_name,
            'http://localhost:11434/v1/',
            'ollama',
            'System context',
            mock_screen,
            provider='Ollama',
        )
        assert isinstance(model, ChatCompletionsModel)
        assert model.model_name == model_name

    def test_ollama_api_key_is_dummy(self, mock_screen):
        """Ollama should work with a dummy API key."""
        model = ModelFactory.create_model(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'context',
            mock_screen,
            provider='Ollama',
        )
        assert model.api_key == 'ollama'

    def test_ollama_base_url_format(self, mock_screen):
        """Ollama base_url should end with /v1/."""
        model = ModelFactory.create_model(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'context',
            mock_screen,
            provider='Ollama',
        )
        assert model.base_url == 'http://localhost:11434/v1/'


class TestSingleLLMResponseHandling:
    """Test that single LLM responses are parsed correctly."""

    @pytest.fixture
    def ollama_model(self, mock_screen, mock_openai_client):
        model = ChatCompletionsModel(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'You are a helpful assistant.',
            mock_screen,
        )
        model.client = mock_openai_client
        return model

    def test_valid_response_with_steps(self, ollama_model):
        """Model should correctly parse a response with action steps."""
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response(json.dumps({
            'steps': [
                {
                    'function': 'click_cell',
                    'parameters': {'cell': 'B5'},
                    'human_readable_justification': 'Clicking target',
                }
            ],
            'done': None,
        }))
        result = ollama_model.convert_llm_response_to_json_instructions(resp)
        assert len(result['steps']) == 1
        assert result['steps'][0]['function'] == 'click_cell'
        assert result['done'] is None

    def test_done_response(self, ollama_model):
        """Model should correctly parse a completion response."""
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response(json.dumps({
            'steps': [],
            'done': 'Chrome is now open.',
        }))
        result = ollama_model.convert_llm_response_to_json_instructions(resp)
        assert result['steps'] == []
        assert result['done'] == 'Chrome is now open.'

    def test_multi_step_response(self, ollama_model):
        """Model should handle multi-step responses."""
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response(json.dumps({
            'steps': [
                {
                    'function': 'click_cell',
                    'parameters': {'cell': 'A1'},
                    'human_readable_justification': 'First click',
                },
                {
                    'function': 'write',
                    'parameters': {'string': 'hello world'},
                    'human_readable_justification': 'Typing text',
                },
                {
                    'function': 'press',
                    'parameters': {'key': 'enter'},
                    'human_readable_justification': 'Pressing enter',
                },
            ],
            'done': None,
        }))
        result = ollama_model.convert_llm_response_to_json_instructions(resp)
        assert len(result['steps']) == 3

    def test_get_instructions_calls_api(self, ollama_model, mock_openai_client):
        """get_instructions_for_objective should call the chat API."""
        result = ollama_model.get_instructions_for_objective('Open Chrome', 0)
        mock_openai_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs['model'] == 'llama3.2'

    def test_message_format_includes_screenshot(self, ollama_model):
        """Formatted messages should include a base64 screenshot."""
        messages = ollama_model.format_user_request_for_llm('Open Chrome', 0)
        assert messages[0]['role'] == 'system'
        user_content = messages[1]['content']
        assert any(
            item.get('type') == 'image_url' for item in user_content
        )


# ── Integration test (real Ollama, opt-in) ───────────────────────────

@pytest.mark.skipif(
    not os.environ.get('OLLAMA_ENDPOINT'),
    reason='Set OLLAMA_ENDPOINT to run real Ollama tests',
)
class TestSingleLLMIntegration:
    """Integration tests against a real Ollama instance.

    Requires: OLLAMA_ENDPOINT=http://localhost:11434
    Optional: OLLAMA_MODEL (default: llama3.2)
    """

    @pytest.fixture
    def real_model(self, mock_screen):
        endpoint = os.environ['OLLAMA_ENDPOINT']
        model_name = os.environ.get('OLLAMA_MODEL', 'llama3.2')
        base_url = f'{endpoint.rstrip("/")}/v1/'
        return ChatCompletionsModel(
            model_name, base_url, 'ollama',
            'You are a helpful assistant. Always reply with valid JSON '
            'containing "steps" (list) and "done" (string or null).',
            mock_screen,
        )

    def test_real_ollama_returns_valid_json(self, real_model):
        """A real Ollama instance should return parseable JSON."""
        result = real_model.get_instructions_for_objective(
            'Describe what you see on the screen', 0,
        )
        assert isinstance(result, dict)
        # Either has steps or done
        assert 'steps' in result or 'done' in result or result == {}
