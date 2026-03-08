import json
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional

import moondream as md
from PIL import Image

from models.model import Model
from utils.grid import create_gridded_screenshot
from utils.screen import Screen
from utils.settings import Settings

# The remote text-only model used for action planning when no override is set.
DEFAULT_PLANNING_MODEL = 'gpt-4o-mini'


class MoondreamHybrid(Model):
    """Two-LLM pipeline: Moondream2 for local vision + remote LLM for planning.

    Moondream2 (a small, efficient vision model under 2B parameters) analyses
    screenshots locally or via its cloud API and produces rich text
    descriptions of the screen.  The remote planning LLM then receives a
    *text-only* request — no large image payload is uploaded — which
    dramatically reduces latency, bandwidth, and API cost.

    Parallel execution strategy
    ---------------------------
    1. **Within each step** — Moondream ``caption()`` and ``query()`` run in
       parallel threads, cutting local vision time roughly in half.
    2. **Between steps** — After commands for step *N* finish, the next
       screenshot capture + Moondream analysis starts immediately in a
       background thread (``prefetch_analysis``).  When step *N+1* begins,
       the pre-computed description is picked up and only the planning LLM
       call is needed, eliminating the full Moondream wait.

    Settings (in ~/.open-interface/settings.json):
        moondream_api_key   – API key for Moondream Cloud (optional).
        moondream_endpoint  – URL for a local Moondream Station instance.
                              Defaults to http://localhost:2020/v1 when no
                              API key is provided.
        planning_model      – Remote model name for action planning.
                              Defaults to gpt-4o-mini.
    """

    def __init__(self, model_name, base_url, api_key, context, screen=None):
        super().__init__(model_name, base_url, api_key, context, screen)

        settings = Settings().get_dict()

        # --- Moondream2 vision model ---
        moondream_api_key = settings.get('moondream_api_key')
        moondream_endpoint = settings.get(
            'moondream_endpoint', 'http://localhost:2020/v1'
        )

        if moondream_api_key:
            self.vision = md.vl(api_key=moondream_api_key)
        else:
            self.vision = md.vl(endpoint=moondream_endpoint)

        # --- Remote planning LLM (text-only) ---
        self.planning_model = settings.get(
            'planning_model', DEFAULT_PLANNING_MODEL
        )

        # --- Thread pool for parallel vision calls + prefetching ---
        # 2 workers: one for caption, one for query (or one for prefetch)
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix='moondream'
        )
        self._prefetch_future: Optional[Future] = None

    # ------------------------------------------------------------------
    # Public interface (called by Core)
    # ------------------------------------------------------------------

    def get_instructions_for_objective(
        self, original_user_request: str, step_num: int = 0
    ) -> dict[str, Any]:
        screen = self.screen or Screen()

        # Use a prefetched vision analysis if one completed successfully;
        # otherwise capture + analyse synchronously.
        description, cell_map = self._get_or_create_analysis(screen)
        screen.cell_map = cell_map

        # Build a text-only request for the planning LLM
        messages = self._build_planning_request(
            original_user_request, step_num, description
        )

        # Call the planning LLM and parse the JSON response
        llm_response = self._call_planning_llm(messages)
        return self._parse_response(llm_response)

    # ------------------------------------------------------------------
    # Prefetch — overlap vision analysis with command execution
    # ------------------------------------------------------------------

    def prefetch_analysis(self) -> None:
        """Start the next screenshot + Moondream analysis in a background
        thread.  Called by :class:`Core` right after commands for the
        current step finish executing, so the analysis runs while the
        recursive ``execute()`` call is set up."""
        if self._prefetch_future is None or self._prefetch_future.done():
            self._prefetch_future = self._executor.submit(
                self._capture_and_analyze
            )

    def cancel_prefetch(self) -> None:
        """Cancel any pending prefetch (e.g. on user interrupt)."""
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
            self._prefetch_future = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_analysis(
        self, screen: Screen
    ) -> tuple[str, dict[str, tuple[int, int]]]:
        """Return a (description, cell_map) pair.

        If a prefetch is available and completed successfully, consume it.
        Otherwise fall back to a synchronous capture + analysis.
        """
        if self._prefetch_future is not None:
            future = self._prefetch_future
            self._prefetch_future = None
            if not future.cancelled():
                try:
                    return future.result()
                except Exception as exc:
                    print(f'Prefetch failed ({exc}), falling back to sync')

        return self._capture_and_analyze()

    def _capture_and_analyze(self) -> tuple[str, dict[str, tuple[int, int]]]:
        """Capture a screenshot, overlay the grid, and run Moondream2.

        This method is safe to call from any thread.
        """
        screen = self.screen or Screen()
        screenshot = screen.get_screenshot()
        region = screen.get_capture_region()
        gridded_img, cell_map = create_gridded_screenshot(screenshot, region)
        description = self._analyze_screen(gridded_img)
        return description, cell_map

    # ------------------------------------------------------------------
    # Moondream2 vision analysis (parallel caption + query)
    # ------------------------------------------------------------------

    def _analyze_screen(self, gridded_img: Image.Image) -> str:
        """Use Moondream2 to produce a detailed text description of the
        current screen state.

        The ``caption()`` and ``query()`` calls are submitted to the thread
        pool so they execute in parallel, roughly halving the local vision
        latency.
        """
        caption_future = self._executor.submit(
            self.vision.caption, gridded_img, length="long"
        )
        layout_future = self._executor.submit(
            self.vision.query,
            gridded_img,
            "List every visible UI element — buttons, text fields, menus, "
            "links, icons, labels, and tabs — together with the grid cell "
            "(column letter and row number) each element occupies.",
        )

        caption = caption_future.result()["caption"]
        layout = layout_future.result()["answer"]

        return (
            f"Screen overview: {caption}\n\n"
            f"UI element positions: {layout}"
        )

    # ------------------------------------------------------------------
    # Planning LLM (text-only)
    # ------------------------------------------------------------------

    def _build_planning_request(
        self,
        user_request: str,
        step_num: int,
        screen_description: str,
    ) -> list[dict[str, Any]]:
        request_data: str = json.dumps({
            'original_user_request': user_request,
            'step_num': step_num,
        })

        text = (
            f"{self.context}\n\n"
            f"CURRENT SCREEN STATE (analyzed by local vision model):\n"
            f"{screen_description}\n\n"
            f"{request_data}"
        )

        return [{'role': 'user', 'content': text}]

    def _call_planning_llm(
        self, messages: list[dict[str, Any]]
    ) -> Any:
        return self.client.chat.completions.create(
            model=self.planning_model,
            messages=messages,
            max_tokens=800,
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, llm_response: Any) -> dict[str, Any]:
        response_text = llm_response.choices[0].message.content.strip()

        start_index = response_text.find('{')
        end_index = response_text.rfind('}')

        try:
            return json.loads(
                response_text[start_index:end_index + 1].strip()
            )
        except Exception as e:
            print(f'Error parsing planning LLM response: {e}')
            return {}

    def cleanup(self):
        self.cancel_prefetch()
        self._executor.shutdown(wait=False)
