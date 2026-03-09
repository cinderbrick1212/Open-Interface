"""Multiple browser configuration tests.

Validates that Open Interface correctly handles different browser
settings and that the browser preference is properly integrated into
the LLM context and settings pipeline.

Tests cover:
- Setting different default browsers (Chrome, Firefox, Safari, Edge)
- Browser setting persistence through save/load cycle
- Browser info inclusion in LLM context
- Clearing browser preference
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from utils.settings import Settings


# ── Browser settings tests ───────────────────────────────────────────

class TestBrowserSettings:
    """Test browser configuration in settings."""

    @pytest.mark.parametrize('browser', ['Chrome', 'Firefox', 'Safari', 'Edge'])
    def test_set_default_browser(self, browser, tmp_settings_dir):
        """Each supported browser should be saved correctly."""
        s = Settings()
        s.save_settings_to_file({'default_browser': browser})
        loaded = Settings().get_dict()
        assert loaded['default_browser'] == browser

    def test_empty_browser_setting(self, tmp_settings_dir):
        """Empty string browser should be preserved (no default)."""
        s = Settings()
        s.save_settings_to_file({'default_browser': ''})
        loaded = Settings().get_dict()
        assert loaded['default_browser'] == ''

    def test_switch_browsers(self, tmp_settings_dir):
        """Switching between browsers should work correctly."""
        s = Settings()

        for browser in ['Chrome', 'Firefox', 'Safari', 'Edge', '']:
            s.save_settings_to_file({'default_browser': browser})
            loaded = Settings().get_dict()
            assert loaded['default_browser'] == browser

    def test_browser_with_other_settings(self, tmp_settings_dir):
        """Browser setting should coexist with other settings."""
        s = Settings()
        s.save_settings_to_file({
            'provider': 'Ollama',
            'model': 'llama3.2',
            'default_browser': 'Firefox',
            'play_ding_on_completion': True,
        })
        loaded = Settings().get_dict()
        assert loaded['default_browser'] == 'Firefox'
        assert loaded['provider'] == 'Ollama'
        assert loaded['model'] == 'llama3.2'


# ── Browser context integration ─────────────────────────────────────

class TestBrowserContextIntegration:
    """Test that browser settings are passed into LLM context."""

    @pytest.fixture
    def mock_llm_deps(self, mock_screen, tmp_settings_dir):
        """Patch dependencies so LLM can be imported in headless env."""
        with patch('utils.local_info.locally_installed_apps', ['Chrome', 'Firefox']), \
             patch('utils.local_info.operating_system', 'Linux'):
            yield

    @pytest.mark.parametrize('browser', ['Chrome', 'Firefox', 'Safari', 'Edge'])
    def test_browser_in_llm_context(self, browser, tmp_settings_dir, mock_screen, mock_llm_deps):
        """Default browser should appear in the LLM context string."""
        s = Settings()
        s.save_settings_to_file({
            'provider': 'Ollama',
            'model': 'llama3.2',
            'ollama_endpoint': 'http://localhost:11434',
            'default_browser': browser,
        })

        from llm import LLM
        llm = LLM(mock_screen)
        context = llm.read_context_txt_file()

        assert f'Default browser is {browser}' in context

    def test_no_browser_in_context_when_empty(self, tmp_settings_dir, mock_screen, mock_llm_deps):
        """When no browser is set, it should NOT appear in context."""
        s = Settings()
        s.save_settings_to_file({
            'provider': 'Ollama',
            'model': 'llama3.2',
            'ollama_endpoint': 'http://localhost:11434',
            'default_browser': '',
        })

        from llm import LLM
        llm = LLM(mock_screen)
        context = llm.read_context_txt_file()

        assert 'Default browser is' not in context


# ── Browser + provider combo tests ──────────────────────────────────

class TestBrowserProviderCombinations:
    """Test combinations of browser settings with different providers."""

    BROWSERS = ['Chrome', 'Firefox', 'Safari', 'Edge']
    PROVIDERS = [
        ('Ollama', 'llama3.2'),
        ('OpenRouter', 'meta-llama/llama-3-70b'),
    ]

    @pytest.mark.parametrize('browser', BROWSERS)
    @pytest.mark.parametrize('provider,model', PROVIDERS)
    def test_browser_provider_combo_settings(
        self, browser, provider, model, tmp_settings_dir,
    ):
        """All browser + provider combinations should persist correctly."""
        s = Settings()
        s.save_settings_to_file({
            'provider': provider,
            'model': model,
            'default_browser': browser,
        })
        loaded = Settings().get_dict()
        assert loaded['default_browser'] == browser
        assert loaded['provider'] == provider
        assert loaded['model'] == model


# ── Browser-specific model behavior ─────────────────────────────────

class TestBrowserSpecificBehavior:
    """Test that browser choice affects LLM instructions correctly."""

    def test_custom_instructions_with_browser(self, tmp_settings_dir):
        """Custom LLM instructions should work alongside browser setting."""
        s = Settings()
        s.save_settings_to_file({
            'default_browser': 'Chrome',
            'custom_llm_instructions': 'Always use incognito mode',
        })
        loaded = Settings().get_dict()
        assert loaded['default_browser'] == 'Chrome'
        assert loaded['custom_llm_instructions'] == 'Always use incognito mode'

    @pytest.mark.parametrize('browser', ['Chrome', 'Firefox', 'Safari', 'Edge'])
    def test_browser_persistence_across_restarts(self, browser, tmp_settings_dir):
        """Browser setting should survive multiple Settings instantiations."""
        # Simulate app restart by creating new Settings instances
        s1 = Settings()
        s1.save_settings_to_file({'default_browser': browser})

        s2 = Settings()
        assert s2.get_dict()['default_browser'] == browser

        s3 = Settings()
        assert s3.get_dict()['default_browser'] == browser
