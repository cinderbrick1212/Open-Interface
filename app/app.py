import sys
from multiprocessing import freeze_support

from web_ui import WebUI


class App:
    """
    +----------------------------------------------------+
    | App                                                |
    |                                                    |
    |    +----------+                                    |
    |    | Gradio   |                                    |
    |    | Web UI   |                                    |
    |    +----------+                                    |
    |        ^                                           |
    |        | (direct calls + status_queue)             |
    |        v                                           |
    |  +-----------+  (Screenshot + Goal)  +-----------+ |
    |  |           | --------------------> |           | |
    |  |    Core   |                       |    LLM    | |
    |  |           | <-------------------- |           | |
    |  +-----------+    (Instructions)     +-----------+ |
    |        |                                           |
    |        v                                           |
    |  +-------------+                                   |
    |  | Interpreter |                                   |
    |  +-------------+                                   |
    +----------------------------------------------------+

    The Gradio web UI replaces the previous Tkinter GUI.  It calls
    Core.execute_user_request directly in a background thread and
    streams status updates from Core.status_queue back to the
    browser via Gradio's generator protocol — no bridging threads
    needed.
    """

    def __init__(self):
        # Core is created lazily by WebUI on first request so that
        # settings changes can recreate it without restarting the app.
        self.web_ui = WebUI()

    def run(self) -> None:
        self.web_ui.run()

    def cleanup(self):
        self.web_ui.cleanup()


if __name__ == '__main__':
    freeze_support()  # As required by pyinstaller https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    app = App()
    app.run()
    app.cleanup()
    sys.exit(0)
