"""Performance benchmarks for Open Interface core operations.

Run with:
    pytest tests/test_benchmark.py -v

These benchmarks measure the latency of critical hot-path operations
using mock/stub backends so they can run in any CI environment
(no display, no GPU, no API keys required).

When a real Ollama instance is available (set ``OLLAMA_ENDPOINT`` env
var), the integration benchmarks will exercise the real LLM round-trip.
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


# ── Benchmark helpers ────────────────────────────────────────────────

class Timer:
    """Lightweight context-manager timer for manual benchmarks."""

    def __init__(self):
        self.elapsed: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self._start


# ── Settings benchmarks ─────────────────────────────────────────────

class TestSettingsBenchmark:
    """Measure settings load / save round-trip performance."""

    def test_settings_load_latency(self, tmp_settings_dir):
        """Loading settings from disk should complete in < 50 ms."""
        with Timer() as t:
            for _ in range(100):
                Settings()
        avg_ms = (t.elapsed / 100) * 1000
        print(f'\n  Settings load avg: {avg_ms:.2f} ms')
        assert avg_ms < 50, f'Settings load too slow: {avg_ms:.2f} ms'

    def test_settings_save_latency(self, tmp_settings_dir):
        """Saving settings to disk should complete in < 50 ms."""
        s = Settings()
        data = {'provider': 'Ollama', 'model': 'llama3.2', 'api_key': 'test-key-123'}
        with Timer() as t:
            for _ in range(100):
                s.save_settings_to_file(data)
        avg_ms = (t.elapsed / 100) * 1000
        print(f'\n  Settings save avg: {avg_ms:.2f} ms')
        assert avg_ms < 50, f'Settings save too slow: {avg_ms:.2f} ms'

    def test_settings_round_trip(self, tmp_settings_dir):
        """Save then load should preserve values (correctness + speed)."""
        s = Settings()
        data = {
            'provider': 'Ollama',
            'model': 'mistral',
            'ollama_endpoint': 'http://localhost:11434',
            'api_key': 'secret-key-42',
        }
        with Timer() as t:
            s.save_settings_to_file(data)
            loaded = Settings().get_dict()
        elapsed_ms = t.elapsed * 1000
        print(f'\n  Settings round-trip: {elapsed_ms:.2f} ms')
        assert loaded['provider'] == 'Ollama'
        assert loaded['model'] == 'mistral'
        assert loaded['api_key'] == 'secret-key-42'
        assert elapsed_ms < 100


# ── Model factory benchmarks ────────────────────────────────────────

class TestModelFactoryBenchmark:
    """Measure model creation latency for each provider path."""

    @pytest.mark.parametrize('provider,model_name', [
        ('Ollama', 'llama3.2'),
        ('Ollama', 'mistral'),
        ('OpenRouter', 'meta-llama/llama-3-70b'),
        ('Ollama', 'qwen3-vl:30b'),
        ('Ollama', 'deepseek-coder-v2:16b'),
        ('Ollama', 'llama3.1:8b-instruct-q4_K_M'),
    ])
    def test_chat_completions_model_creation(self, provider, model_name, mock_screen):
        """ChatCompletionsModel creation should be fast (< 200 ms)."""
        with Timer() as t:
            model = ModelFactory.create_model(
                model_name,
                'http://localhost:11434/v1/',
                'ollama',
                'You are a helpful assistant.',
                mock_screen,
                provider=provider,
            )
        elapsed_ms = t.elapsed * 1000
        print(f'\n  {provider}/{model_name} creation: {elapsed_ms:.2f} ms')
        assert isinstance(model, ChatCompletionsModel)
        assert elapsed_ms < 200

    def test_factory_unknown_model_fallback(self, mock_screen):
        """Unknown models should fall back gracefully."""
        model = ModelFactory.create_model(
            'some-unknown-model',
            'http://localhost:11434/v1/',
            'test-key',
            'context',
            mock_screen,
        )
        # Should fall back to GPT4v
        assert model is not None


# ── LLM response parsing benchmarks ─────────────────────────────────

class TestResponseParsingBenchmark:
    """Measure JSON parsing performance of LLM responses."""

    @pytest.fixture
    def chat_model(self, mock_screen, mock_openai_client):
        """Create a ChatCompletionsModel with a mocked client."""
        model = ChatCompletionsModel(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'You are a helpful assistant.',
            mock_screen,
        )
        model.client = mock_openai_client
        return model

    def test_parse_valid_json_response(self, chat_model):
        """Parsing a valid JSON response should be fast and correct."""
        response_text = json.dumps({
            'steps': [
                {
                    'function': 'click_cell',
                    'parameters': {'cell': 'A1'},
                    'human_readable_justification': 'test click',
                }
            ],
            'done': None,
        })
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response(response_text)

        with Timer() as t:
            for _ in range(1000):
                result = chat_model.convert_llm_response_to_json_instructions(resp)
        avg_us = (t.elapsed / 1000) * 1_000_000
        print(f'\n  JSON parse avg: {avg_us:.1f} µs')
        assert result['steps'][0]['function'] == 'click_cell'
        assert avg_us < 500  # Should be well under 500 µs

    def test_parse_response_with_markdown_wrapper(self, chat_model):
        """Responses wrapped in markdown code blocks should still parse."""
        inner = json.dumps({
            'steps': [],
            'done': 'Task completed.',
        })
        wrapped = f'```json\n{inner}\n```'
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response(wrapped)

        result = chat_model.convert_llm_response_to_json_instructions(resp)
        assert result['done'] == 'Task completed.'

    def test_parse_malformed_json_response(self, chat_model):
        """Malformed JSON should return empty dict without crashing."""
        from tests.conftest import make_chat_completion_response
        resp = make_chat_completion_response('This is not JSON at all')

        result = chat_model.convert_llm_response_to_json_instructions(resp)
        assert result == {}


# ── LLM call benchmarks (mocked) ────────────────────────────────────

class TestLLMCallBenchmark:
    """Measure the overhead of the LLM call pipeline (mocked backend)."""

    @pytest.fixture
    def chat_model(self, mock_screen, mock_openai_client):
        model = ChatCompletionsModel(
            'llama3.2',
            'http://localhost:11434/v1/',
            'ollama',
            'You are a helpful assistant.',
            mock_screen,
        )
        model.client = mock_openai_client
        return model

    def test_get_instructions_overhead(self, chat_model):
        """Full get_instructions_for_objective overhead should be < 50 ms."""
        with Timer() as t:
            for _ in range(100):
                result = chat_model.get_instructions_for_objective('Open Chrome', 0)
        avg_ms = (t.elapsed / 100) * 1000
        print(f'\n  get_instructions overhead avg: {avg_ms:.2f} ms')
        assert avg_ms < 50

    def test_format_user_request(self, chat_model):
        """Message formatting should be fast (< 5 ms)."""
        with Timer() as t:
            for _ in range(1000):
                messages = chat_model.format_user_request_for_llm('Open Chrome', 0)
        avg_ms = (t.elapsed / 1000) * 1000
        print(f'\n  format_user_request avg: {avg_ms:.3f} ms')
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert avg_ms < 5


# ── Integration benchmark (real Ollama, opt-in) ─────────────────────

@pytest.mark.skipif(
    not os.environ.get('OLLAMA_ENDPOINT'),
    reason='Set OLLAMA_ENDPOINT to run real Ollama benchmarks',
)
class TestOllamaIntegrationBenchmark:
    """End-to-end benchmarks against a real Ollama instance.

    Set OLLAMA_ENDPOINT=http://localhost:11434 to enable.
    Set OLLAMA_MODEL to override the default model (llama3.2).
    """

    MAX_RESPONSE_TIME_SECONDS = 120

    @pytest.fixture
    def ollama_model(self, mock_screen):
        endpoint = os.environ['OLLAMA_ENDPOINT']
        model_name = os.environ.get('OLLAMA_MODEL', 'llama3.2')
        base_url = f'{endpoint.rstrip("/")}/v1/'
        return ChatCompletionsModel(
            model_name, base_url, 'ollama',
            'You are a helpful assistant. Reply with valid JSON.',
            mock_screen,
        )

    def test_real_ollama_response_time(self, ollama_model):
        """Measure real Ollama response time (informational)."""
        with Timer() as t:
            result = ollama_model.get_instructions_for_objective(
                'What do you see on screen?', 0,
            )
        print(f'\n  Real Ollama response: {t.elapsed:.2f} s')
        # Just informational — no strict assertion on real LLM latency
        assert t.elapsed < self.MAX_RESPONSE_TIME_SECONDS, \
            f'Ollama response took over {self.MAX_RESPONSE_TIME_SECONDS}s'
