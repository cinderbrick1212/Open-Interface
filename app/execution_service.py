"""Sandboxed execution service for Noclip Desktop.

Runs as a subprocess. Reads JSON action requests from stdin (one per line),
validates them against the allowlist, executes via Interpreter, and writes
JSON responses to stdout.

Protocol:
  Request:  {"action": "execute", "command": {...}}
  Response: {"status": "ok"} or {"status": "error", "message": "..."}

  Request:  {"action": "set_cell_map", "cell_map": {...}}
  Response: {"status": "ok"}

  Request:  {"action": "shutdown"}
  (process exits)
"""

import json
import os
import sys

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multiprocessing import Queue
from interpreter import Interpreter


def main():
    status_queue = Queue()
    interpreter = Interpreter(status_queue)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _respond({"status": "error", "message": f"Invalid JSON: {e}"})
            continue

        action = request.get("action")

        if action == "shutdown":
            break

        elif action == "set_cell_map":
            interpreter.cell_map = request.get("cell_map", {})
            _respond({"status": "ok"})

        elif action == "set_controls_enabled":
            interpreter.controls_enabled = request.get("enabled", True)
            _respond({"status": "ok"})

        elif action == "execute":
            command = request.get("command", {})
            try:
                success = interpreter.process_command(command)
                _respond({"status": "ok" if success else "error",
                           "message": "" if success else "Command execution failed"})
            except Exception as e:
                _respond({"status": "error", "message": str(e)})

            # Drain status queue and include updates
            statuses = []
            while not status_queue.empty():
                try:
                    statuses.append(str(status_queue.get_nowait()))
                except Exception:
                    break
            if statuses:
                _respond({"status": "status_update", "messages": statuses})

        else:
            _respond({"status": "error", "message": f"Unknown action: {action}"})


def _respond(data: dict):
    """Write a JSON response to stdout."""
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
