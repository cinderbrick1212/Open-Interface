"""Client for the sandboxed execution service.

Manages the execution subprocess lifecycle and provides a clean API
for sending commands.
"""

import json
import os
import subprocess
import sys
from typing import Any, Optional


class ExecutionClient:
    """Manages a subprocess running execution_service.py."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._start()

    def _start(self):
        """Start the execution service subprocess."""
        service_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'execution_service.py'
        )
        self._process = subprocess.Popen(
            [sys.executable, service_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
        )

    def _send(self, request: dict) -> dict:
        """Send a request and read the response."""
        if self._process is None or self._process.poll() is not None:
            self._start()

        line = json.dumps(request) + "\n"
        self._process.stdin.write(line)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline().strip()
        if not response_line:
            return {"status": "error", "message": "No response from execution service"}

        try:
            return json.loads(response_line)
        except json.JSONDecodeError:
            return {"status": "error", "message": f"Invalid response: {response_line}"}

    def execute_command(self, command: dict[str, Any]) -> bool:
        """Execute a single command via the service. Returns True on success."""
        resp = self._send({"action": "execute", "command": command})
        return resp.get("status") == "ok"

    def set_cell_map(self, cell_map: dict[str, tuple[int, int]]) -> None:
        """Update the cell map in the execution service."""
        # Convert tuple values to lists for JSON serialization
        serializable = {k: list(v) for k, v in cell_map.items()}
        self._send({"action": "set_cell_map", "cell_map": serializable})

    def set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable keyboard/mouse control."""
        self._send({"action": "set_controls_enabled", "enabled": enabled})

    def shutdown(self) -> None:
        """Gracefully shut down the execution service."""
        if self._process and self._process.poll() is None:
            try:
                self._send({"action": "shutdown"})
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
