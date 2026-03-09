"""Multiple local LLM tests.

Validates that Open Interface correctly handles switching between
multiple LLM providers and models. Tests cover:

- Switching between Ollama models (e.g., llama3.2, mistral, codellama)
- Switching between providers (Ollama, OpenAI, Claude, Gemini, OpenRouter)
- Concurrent model creation for different providers
- Settings reconfiguration for provider switching
"""

import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from models.chat_completions import ChatCompletionsModel
from models.factory import ModelFactory
from utils.settings import Settings


# ── Multiple Ollama models ───────────────────────────────────────────

class TestMultipleOllamaModels:
    """Test switching between multiple Ollama models."""

    OLLAMA_MODELS = [
        'llama3.2',
        'llama3.2:1b',
        'mistral',
        'codellama',
        'phi3',
        'gemma2',
        'qwen2.5',
        'deepseek-r1:7b',
        'llava',
        'neural-chat',
    ]

    @pytest.mark.parametrize('model_name', OLLAMA_MODELS)
    def test_create_model_for_each(self, model_name, mock_screen):
        """Each Ollama model name should produce a valid ChatCompletionsModel."""
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

    def test_switch_between_models(self, mock_screen, mock_openai_client):
        """Switching between models should work without errors."""
        models = []
        for model_name in ['llama3.2', 'mistral', 'codellama']:
            model = ModelFactory.create_model(
                model_name,
                'http://localhost:11434/v1/',
                'ollama',
                'System context',
                mock_screen,
                provider='Ollama',
            )
            model.client = mock_openai_client
            result = model.get_instructions_for_objective('Test request', 0)
            models.append((model_name, result))

        # All should return valid results
        for name, result in models:
            assert isinstance(result, dict), f'{name} returned non-dict'

    def test_model_independence(self, mock_screen):
        """Different models should be independent instances."""
        model_a = ModelFactory.create_model(
            'llama3.2', 'http://localhost:11434/v1/', 'ollama',
            'Context A', mock_screen, provider='Ollama',
        )
        model_b = ModelFactory.create_model(
            'mistral', 'http://localhost:11434/v1/', 'ollama',
            'Context B', mock_screen, provider='Ollama',
        )
        assert model_a is not model_b
        assert model_a.model_name != model_b.model_name
        assert model_a.context != model_b.context


# ── Multiple providers ───────────────────────────────────────────────

class TestMultipleProviders:
    """Test switching between different LLM providers."""

    def test_ollama_provider(self, mock_screen):
        """Ollama provider should create ChatCompletionsModel."""
        model = ModelFactory.create_model(
            'llama3.2', 'http://localhost:11434/v1/', 'ollama',
            'context', mock_screen, provider='Ollama',
        )
        assert isinstance(model, ChatCompletionsModel)

    def test_openrouter_provider(self, mock_screen):
        """OpenRouter provider should create ChatCompletionsModel."""
        model = ModelFactory.create_model(
            'meta-llama/llama-3-70b',
            'https://openrouter.ai/api/v1/',
            'sk-or-test-key',
            'context',
            mock_screen,
            provider='OpenRouter',
        )
        assert isinstance(model, ChatCompletionsModel)

    def test_claude_provider(self, mock_screen):
        """Claude provider should create a Claude model."""
        from models.claude import Claude
        model = ModelFactory.create_model(
            'claude-3-5-sonnet-20241022',
            'unused-base-url',
            'sk-ant-test-key',
            'context',
            mock_screen,
            provider='Claude',
        )
        assert isinstance(model, Claude)

    def test_gemini_provider(self, mock_screen):
        """Gemini provider should create a Gemini model."""
        from models.gemini import Gemini
        model = ModelFactory.create_model(
            'gemini-2.0-flash',
            'unused-base-url',
            'test-gemini-key',
            'context',
            mock_screen,
            provider='Gemini',
        )
        assert isinstance(model, Gemini)

    def test_openai_provider_gpt4o(self, mock_screen):
        """OpenAI GPT-4o should create a GPT4o model."""
        from models.gpt4o import GPT4o
        with patch('models.model.OpenAI') as MockOpenAI:
            # GPT4o constructor calls client.beta.assistants.create
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            model = ModelFactory.create_model(
                'gpt-4o',
                'https://api.openai.com/v1/',
                'sk-test-key',
                'context',
                mock_screen,
            )
            assert isinstance(model, GPT4o)

    def test_openai_provider_gpt5(self, mock_screen):
        """GPT-5 model name should create a GPT5 model."""
        from models.gpt5 import GPT5
        model = ModelFactory.create_model(
            'gpt-5.2',
            'http://localhost:11434/v1/',
            'sk-test-key',
            'context',
            mock_screen,
        )
        assert isinstance(model, GPT5)


class TestProviderSwitchingWithSettings:
    """Test that provider switching via settings works correctly."""

    def test_switch_provider_settings(self, tmp_settings_dir):
        """Changing provider in settings should persist."""
        s = Settings()

        # Set to Ollama
        s.save_settings_to_file({'provider': 'Ollama', 'model': 'llama3.2'})
        loaded = Settings().get_dict()
        assert loaded['provider'] == 'Ollama'

        # Switch to OpenRouter
        s.save_settings_to_file({'provider': 'OpenRouter', 'model': 'meta-llama/llama-3-70b'})
        loaded = Settings().get_dict()
        assert loaded['provider'] == 'OpenRouter'
        assert loaded['model'] == 'meta-llama/llama-3-70b'

    def test_provider_specific_keys(self, tmp_settings_dir):
        """Different providers should store their own API keys."""
        s = Settings()
        s.save_settings_to_file({
            'openai_api_key': 'sk-openai-123',
            'claude_api_key': 'sk-ant-456',
            'gemini_api_key': 'gemini-789',
            'openrouter_api_key': 'sk-or-012',
        })
        loaded = Settings().get_dict()
        assert loaded['openai_api_key'] == 'sk-openai-123'
        assert loaded['claude_api_key'] == 'sk-ant-456'
        assert loaded['gemini_api_key'] == 'gemini-789'
        assert loaded['openrouter_api_key'] == 'sk-or-012'


class TestMultiModelResponseParsing:
    """Test that responses from different model types parse correctly."""

    @pytest.fixture
    def make_model(self, mock_screen, mock_openai_client):
        """Factory to create a ChatCompletionsModel with mocked client."""
        def _make(model_name):
            model = ChatCompletionsModel(
                model_name, 'http://localhost:11434/v1/', 'ollama',
                'System context', mock_screen,
            )
            model.client = mock_openai_client
            return model
        return _make

    def test_consistent_response_format_across_models(self, make_model):
        """All models should produce consistent response format."""
        for model_name in ['llama3.2', 'mistral', 'codellama']:
            model = make_model(model_name)
            result = model.get_instructions_for_objective('Open Chrome', 0)
            assert isinstance(result, dict)
            assert 'steps' in result or 'done' in result or result == {}

    def test_error_handling_across_models(self, make_model):
        """All models should handle errors gracefully."""
        from tests.conftest import make_chat_completion_response

        for model_name in ['llama3.2', 'mistral']:
            model = make_model(model_name)
            # Set up a bad response
            bad_resp = make_chat_completion_response('Not valid JSON')
            model.client.chat.completions.create.return_value = bad_resp
            result = model.convert_llm_response_to_json_instructions(bad_resp)
            assert result == {}


# ── Multi-model performance comparison ──────────────────────────────

class TestMultiModelPerformanceComparison:
    """Compare model creation and call overhead across providers."""

    @pytest.mark.parametrize('provider,model_name,base_url', [
        ('Ollama', 'llama3.2', 'http://localhost:11434/v1/'),
        ('Ollama', 'mistral', 'http://localhost:11434/v1/'),
        ('OpenRouter', 'meta-llama/llama-3-70b', 'https://openrouter.ai/api/v1/'),
    ])
    def test_model_creation_time(self, provider, model_name, base_url, mock_screen):
        """Model creation overhead should be small."""
        start = time.perf_counter()
        model = ModelFactory.create_model(
            model_name, base_url, 'test-key', 'context',
            mock_screen, provider=provider,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f'\n  {provider}/{model_name} creation: {elapsed_ms:.2f} ms')
        assert model is not None
        assert elapsed_ms < 500


# ── Multi-model integration tests (opt-in) ──────────────────────────

@pytest.mark.skipif(
    not os.environ.get('OLLAMA_ENDPOINT'),
    reason='Set OLLAMA_ENDPOINT to run real multi-model Ollama tests',
)
class TestMultiModelIntegration:
    """Integration tests with multiple real Ollama models.

    Set OLLAMA_ENDPOINT and OLLAMA_MODELS (comma-separated) to enable.
    Example: OLLAMA_MODELS=llama3.2,mistral,phi3
    """

    @pytest.fixture
    def model_names(self):
        models_str = os.environ.get('OLLAMA_MODELS', 'llama3.2')
        return [m.strip() for m in models_str.split(',')]

    def test_all_models_respond(self, model_names, mock_screen):
        """All configured Ollama models should return a response."""
        endpoint = os.environ['OLLAMA_ENDPOINT']
        base_url = f'{endpoint.rstrip("/")}/v1/'
        results = {}

        for model_name in model_names:
            model = ChatCompletionsModel(
                model_name, base_url, 'ollama',
                'Reply with valid JSON: {"steps": [], "done": "ok"}',
                mock_screen,
            )
            start = time.perf_counter()
            try:
                result = model.get_instructions_for_objective('Say hello', 0)
                elapsed = time.perf_counter() - start
                results[model_name] = {
                    'success': True,
                    'time_s': elapsed,
                    'response': result,
                }
            except Exception as e:
                elapsed = time.perf_counter() - start
                results[model_name] = {
                    'success': False,
                    'time_s': elapsed,
                    'error': str(e),
                }

        # Print comparison table
        print('\n  Multi-model comparison:')
        print(f'  {"Model":<25} {"Status":<10} {"Time (s)":<10}')
        print(f'  {"-" * 45}')
        for name, info in results.items():
            status = 'OK' if info['success'] else 'FAIL'
            print(f'  {name:<25} {status:<10} {info["time_s"]:<10.2f}')

        # At least one should succeed
        assert any(r['success'] for r in results.values()), \
            'No Ollama models responded successfully'
