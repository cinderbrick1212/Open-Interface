"""Tests for Phase 2 process isolation.

Validates:
- ExecutionClient subprocess lifecycle
- Core sandbox opt-in/opt-out behavior
- IPC protocol format
- Cell map serialization round-trip
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


class TestIPCProtocol:
    """Test the JSON IPC protocol format."""

    def test_execute_request_format(self):
        request = {
            "action": "execute",
            "command": {
                "function": "click_cell",
                "parameters": {"cell": "A1"},
                "human_readable_justification": "test"
            }
        }
        serialized = json.dumps(request)
        parsed = json.loads(serialized)
        assert parsed["action"] == "execute"
        assert parsed["command"]["function"] == "click_cell"

    def test_set_cell_map_request_format(self):
        request = {
            "action": "set_cell_map",
            "cell_map": {"A1": [100, 200], "B2": [150, 250]}
        }
        serialized = json.dumps(request)
        parsed = json.loads(serialized)
        assert parsed["cell_map"]["A1"] == [100, 200]

    def test_shutdown_request_format(self):
        request = {"action": "shutdown"}
        assert json.dumps(request) == '{"action": "shutdown"}'

    def test_cell_map_tuple_to_list_roundtrip(self):
        """Tuples must become lists for JSON, then work as coordinates."""
        original = {"A1": (100, 200), "B2": (150, 250)}
        serializable = {k: list(v) for k, v in original.items()}
        json_str = json.dumps({"action": "set_cell_map", "cell_map": serializable})
        parsed = json.loads(json_str)
        # Verify coordinates survived the round trip
        assert parsed["cell_map"]["A1"] == [100, 200]
        assert parsed["cell_map"]["B2"] == [150, 250]


class TestExecutionClientUnit:
    """Unit tests for ExecutionClient (mocked subprocess)."""

    def test_client_can_be_imported(self):
        from execution_client import ExecutionClient
        assert ExecutionClient is not None

    @patch('execution_client.subprocess.Popen')
    def test_client_starts_subprocess(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        from execution_client import ExecutionClient
        client = ExecutionClient()
        mock_popen.assert_called_once()
        # Verify subprocess was started with correct script
        call_args = mock_popen.call_args
        assert 'execution_service.py' in call_args[0][0][1]

    @patch('execution_client.subprocess.Popen')
    def test_client_shutdown(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.return_value = '{"status": "ok"}\n'
        mock_popen.return_value = mock_proc
        from execution_client import ExecutionClient
        client = ExecutionClient()
        client.shutdown()
        assert client._process is None


class TestCoreSandboxToggle:
    """Test that Core respects the sandbox setting."""

    def test_default_no_sandbox(self):
        """By default, Core should NOT create an ExecutionClient."""
        from core import Core
        with patch('core.LLM'), \
             patch('core.Screen'), \
             patch('core.Settings') as MockSettings:
            MockSettings.return_value.get_dict.return_value = {}
            c = Core()
            assert c._exec_client is None
            assert c._use_sandbox is False

    def test_sandbox_enabled_creates_client(self):
        """When use_sandboxed_execution=True, Core should create an ExecutionClient."""
        from core import Core
        with patch('core.LLM'), \
             patch('core.Screen'), \
             patch('core.Settings') as MockSettings, \
             patch('core.ExecutionClient') as MockClient:
            MockSettings.return_value.get_dict.return_value = {
                'use_sandboxed_execution': True
            }
            c = Core()
            assert c._use_sandbox is True
            MockClient.assert_called_once()
