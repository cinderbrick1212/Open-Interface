import base64
import json
import os
from pathlib import Path

# Keys that are obfuscated (base64-encoded) in the settings file.
_SENSITIVE_KEYS = frozenset({
    'api_key',
    'openai_api_key',
    'gemini_api_key',
    'claude_api_key',
    'openrouter_api_key',
    'moondream_api_key',
})


class Settings:
    def __init__(self):
        self.settings_file_path = self.get_settings_directory_path() + 'settings.json'
        os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
        self.settings = self.load_settings_from_file()

    def get_settings_directory_path(self):
        return str(Path.home()) + '/.open-interface/'

    def get_dict(self) -> dict[str, str]:
        return self.settings

    def _read_settings_file(self) -> dict[str, str]:
        if os.path.exists(self.settings_file_path):
            with open(self.settings_file_path, 'r') as file:
                try:
                    return json.load(file)
                except Exception:
                    return {}
        return {}

    def save_settings_to_file(self, settings_dict) -> None:
        settings: dict[str, str] = self._read_settings_file()

        for setting_name, setting_val in settings_dict.items():
            if setting_val is not None:
                if setting_name in _SENSITIVE_KEYS and setting_val:
                    if setting_name in ('api_key', 'openai_api_key'):
                        os.environ["OPENAI_API_KEY"] = str(setting_val)
                    settings[setting_name] = base64.b64encode(
                        str(setting_val).encode()
                    ).decode()
                else:
                    settings[setting_name] = setting_val

        with open(self.settings_file_path, 'w+') as file:
            json.dump(settings, file, indent=4)

    def load_settings_from_file(self) -> dict[str, str]:
        settings: dict[str, str] = self._read_settings_file()
        # Decode all API keys
        for key in _SENSITIVE_KEYS:
            if key in settings and settings[key]:
                try:
                    settings[key] = base64.b64decode(settings[key]).decode()
                except (ValueError, base64.binascii.Error):
                    pass  # Value may already be plain text (e.g. first run)
        return settings
