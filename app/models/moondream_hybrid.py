import base64
import json
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional

import moondream as md
from google import genai
from google.genai import types
from PIL import Image

from models.model import Model
from utils.grid import create_gridded_screenshot, gridded_screenshot_to_base64
from utils.screen import Screen
from utils.screen_recorder import FrameBuffer
from utils.settings import Settings

# Default Gemini Flash model used for API planning / supervision.
DEFAULT_PLANNING_MODEL = 'gemini-2.0-flash'

# How many local-only steps Moondream handles between API LLM reviews.
DEFAULT_API_REVIEW_INTERVAL = 3

# Max characters of API guidance fed into Moondream's real-time prompt.
MAX_GUIDANCE_LENGTH = 200

# Moondream answers containing any of these words trigger an API escalation.
_ESCALATION_SIGNALS = [
    'uncertain', 'unsure', 'unclear', "can't determine",
    "cannot determine", 'not sure', "don't know", 'need help',
    'unexpected', 'unable',
]


class MoondreamHybrid(Model):
    """Dual-LLM model: Moondream (local, real-time) + Gemini Flash (API, video).

    Both models receive screenshots **with the grid overlay**, but at
    different frequencies and in different formats:

    * **Moondream2** (local) runs *every* step with a **single fast query**
      on a gridded screenshot.  Images are pre-encoded once via
      ``encode_image()`` to avoid redundant JPEG conversion.
    * **Gemini Flash** (API) runs *less frequently* — on the first step,
      every ``api_review_interval`` local steps, or when Moondream
      escalates.  It receives a **short MP4 video** compiled from the
      recent gridded screenshots (with the grid overlay), giving it
      temporal context about what happened on screen.

    The API guidance is fed back into Moondream's prompt so subsequent
    local iterations stay on track.  Moondream can also **decide to stop
    and let the API analyse** by responding with ``UNCERTAIN``.

    Data pipeline
    -------------
    ::

        Screenshot → Grid overlay → Gridded frame
                                       │
                       ┌───────────────┤
                       ▼               ▼
                  FrameBuffer      Moondream (local)
                  (ring buffer)    query() per step
                       │           real-time, gridded
                       ▼
                  Compile MP4
                  (on API steps)
                       │
                       ▼
                  Gemini Flash
                  (video input)

    Settings (in ~/.open-interface/settings.json):
        moondream_api_key      – API key for Moondream Cloud (optional).
        moondream_endpoint     – Local Moondream Station URL
                                 (default: http://localhost:2020/v1).
        gemini_api_key         – API key for Gemini Flash (falls back to
                                 the main api_key if not set).
        planning_model         – Gemini model for API planning
                                 (default: gemini-2.0-flash).
        api_review_interval    – Local steps between API reviews (default: 3).
    """

    def __init__(self, model_name, base_url, api_key, context, screen=None):
        super().__init__(model_name, base_url, api_key, context, screen)

        settings = Settings().get_dict()

        # --- Moondream2 (local vision, tuned for real-time) ---
        moondream_api_key = settings.get('moondream_api_key')
        moondream_endpoint = settings.get(
            'moondream_endpoint', 'http://localhost:2020/v1'
        )

        if moondream_api_key:
            self.vision = md.vl(api_key=moondream_api_key)
        else:
            self.vision = md.vl(endpoint=moondream_endpoint)

        # --- Gemini Flash (API planning, called less frequently) ---
        gemini_api_key = settings.get('gemini_api_key') or api_key
        self._gemini_client = genai.Client(api_key=gemini_api_key)
        self.planning_model = settings.get(
            'planning_model', DEFAULT_PLANNING_MODEL
        )
        self._safety_settings = [
            types.SafetySetting(
                category=category.value, threshold="BLOCK_NONE"
            )
            for category in types.HarmCategory
            if category.value != 'HARM_CATEGORY_UNSPECIFIED'
        ]

        # --- Frame buffer for video-based API context ---
        self._frame_buffer = FrameBuffer()

        # --- Pipeline state ---
        self._api_review_interval = int(settings.get(
            'api_review_interval', DEFAULT_API_REVIEW_INTERVAL
        ))
        self._local_step_count = 0
        self._api_guidance = ''  # High-level guidance from last API review

        # --- Thread pool for parallel vision calls + prefetching ---
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
        """Unified pipeline: Moondream gets gridded screenshots every step;
        Gemini gets a video of recent gridded frames on API steps."""

        if step_num == 0:
            self._local_step_count = 0
            self._api_guidance = ''
            self._frame_buffer.clear()

        screen = self.screen or Screen()

        # ── Stage 1: Shared pipeline — screenshot → grid overlay ──
        gridded_img, cell_map = self._get_or_create_screenshot(screen)
        screen.cell_map = cell_map

        # ── Stage 2: Store gridded frame for video compilation ──
        self._frame_buffer.add_frame(gridded_img)

        # ── Stage 3: Pre-encode gridded image for Moondream ──
        try:
            encoded_img = self.vision.encode_image(gridded_img)
        except Exception as exc:
            print(f'encode_image failed ({exc}), using raw PIL image')
            encoded_img = gridded_img  # Fallback to raw PIL image

        # ── Stage 4: Route — local (fast) or API (thorough) ──
        if not self._should_use_api(step_num):
            # Real-time path: single fast Moondream query on gridded screenshot
            result = self._local_plan(original_user_request, encoded_img)
            if result is not None:
                self._local_step_count += 1
                return result
            # Moondream escalated → fall through to API

        # ── Stage 5: API path — compile video + Moondream analysis + Gemini ──
        description = self._analyze_screen_for_api(encoded_img)
        instructions = self._api_plan(
            original_user_request, step_num, description, gridded_img
        )
        self._local_step_count = 0
        return instructions

    # ------------------------------------------------------------------
    # Pipeline routing
    # ------------------------------------------------------------------

    def _should_use_api(self, step_num: int) -> bool:
        """Determine whether this step should invoke the API LLM."""
        if step_num == 0:
            return True  # Always use API for initial planning
        if self._local_step_count >= self._api_review_interval:
            return True  # Periodic review
        return False

    # ------------------------------------------------------------------
    # Real-time local planning (single fast Moondream query per step)
    # ------------------------------------------------------------------

    def _local_plan(
        self,
        user_request: str,
        encoded_img: Any,
    ) -> Optional[dict[str, Any]]:
        """Single fast Moondream query for real-time action planning.

        Unlike the API path, this does **not** run ``caption()`` or a
        layout query — just one concise action-focused query per step.
        """
        guidance_ctx = ''
        if self._api_guidance:
            # Keep guidance brief for real-time
            guidance_ctx = f"Plan: {self._api_guidance[:MAX_GUIDANCE_LENGTH]}. "

        answer = self.vision.query(
            encoded_img,
            f"{guidance_ctx}"
            f"Goal: {user_request}. "
            f"Next action? "
            f"CLICK <cell>, TYPE '<text>', PRESS <key>, DONE, or UNCERTAIN.",
        )["answer"]

        return _parse_local_answer(answer)

    # ------------------------------------------------------------------
    # API analysis (thorough but infrequent)
    # ------------------------------------------------------------------

    def _analyze_screen_for_api(self, encoded_img: Any) -> str:
        """Short Moondream analysis for API context.

        Uses ``length="short"`` captions and runs caption + query in
        parallel.  Only called during API review steps (infrequent).
        """
        caption_future = self._executor.submit(
            self.vision.caption, encoded_img, length="short"
        )
        layout_future = self._executor.submit(
            self.vision.query,
            encoded_img,
            "List visible UI elements with their grid cells.",
        )

        caption = caption_future.result()["caption"]
        layout = layout_future.result()["answer"]

        return (
            f"Screen: {caption}\n"
            f"Elements: {layout}"
        )

    def _api_plan(
        self,
        user_request: str,
        step_num: int,
        description: str,
        gridded_img: Image.Image,
    ) -> dict[str, Any]:
        """Full API LLM planning call.

        Compiles the frame buffer into a video and sends it to Gemini so
        it has temporal context (what happened on screen recently).  Falls
        back to a single gridded screenshot if video compilation fails.
        The frame buffer is NOT cleared — recordings stay continuous.
        """
        # Compile continuous video from the rolling frame buffer
        video_b64 = self._frame_buffer.to_video_base64()

        messages = self._build_planning_request(
            user_request, step_num, description, gridded_img, video_b64
        )
        llm_response = self._call_planning_llm(messages)
        instructions = self._parse_api_response(llm_response)

        # Extract guidance for future local Moondream iterations
        self._update_api_guidance(instructions)

        return instructions

    def _update_api_guidance(self, instructions: dict[str, Any]) -> None:
        """Extract high-level guidance from the API response so Moondream
        stays on track during subsequent local iterations."""
        if not instructions or not instructions.get('steps'):
            self._api_guidance = ''
            return
        justifications = [
            s.get('human_readable_justification', '')
            for s in instructions['steps']
            if s.get('human_readable_justification')
        ]
        self._api_guidance = '; '.join(justifications)

    # ------------------------------------------------------------------
    # Prefetch — pre-capture next screenshot during command execution
    # ------------------------------------------------------------------

    def prefetch_analysis(self) -> None:
        """Start the next screenshot capture in a background thread.
        Called by :class:`Core` right after commands finish executing."""
        if self._prefetch_future is None or self._prefetch_future.done():
            self._prefetch_future = self._executor.submit(
                self._capture_screenshot
            )

    def cancel_prefetch(self) -> None:
        """Cancel any pending prefetch (e.g. on user interrupt)."""
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
            self._prefetch_future = None

    # ------------------------------------------------------------------
    # Screenshot pipeline (shared by local + API paths)
    # ------------------------------------------------------------------

    def _get_or_create_screenshot(
        self, screen: Screen
    ) -> tuple[Image.Image, dict[str, tuple[int, int]]]:
        """Return ``(gridded_img, cell_map)``.

        Consumes a prefetch if available, otherwise captures synchronously.
        """
        if self._prefetch_future is not None:
            future = self._prefetch_future
            self._prefetch_future = None
            if not future.cancelled():
                try:
                    return future.result()
                except Exception as exc:
                    print(f'Prefetch failed ({exc}), falling back to sync')

        return self._capture_screenshot()

    def _capture_screenshot(
        self,
    ) -> tuple[Image.Image, dict[str, tuple[int, int]]]:
        """Shared pipeline stage: screenshot → grid overlay.

        This method is safe to call from any thread.
        """
        screen = self.screen or Screen()
        screenshot = screen.get_screenshot()
        region = screen.get_capture_region()
        return create_gridded_screenshot(screenshot, region)

    # ------------------------------------------------------------------
    # Gemini Flash API communication
    # ------------------------------------------------------------------

    def _build_planning_request(
        self,
        user_request: str,
        step_num: int,
        screen_description: str,
        gridded_img: Image.Image,
        video_b64: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        request_data: str = json.dumps({
            'original_user_request': user_request,
            'step_num': step_num,
        })

        if video_b64:
            text = (
                f"{self.context}\n\n"
                f"CURRENT SCREEN STATE (analyzed by local vision model):\n"
                f"{screen_description}\n\n"
                f"{request_data}"
                f"\n\nAttached is a video of recent screen activity "
                f"(gridded screenshots with cell overlay). "
                f"Use it to understand what happened and plan next steps:"
            )

            # Gemini inline_data: send MP4 video for temporal context
            return [
                {"text": text},
                {"inline_data": {
                    "mime_type": "video/mp4",
                    "data": video_b64,
                }},
            ]

        # Fallback: single gridded screenshot if video unavailable
        text = (
            f"{self.context}\n\n"
            f"CURRENT SCREEN STATE (analyzed by local vision model):\n"
            f"{screen_description}\n\n"
            f"{request_data}"
            f"\n\nHere is a screenshot of the user's screen:"
        )

        base64_img = gridded_screenshot_to_base64(gridded_img)
        return [
            {"text": text},
            {"inline_data": {
                "mime_type": "image/jpeg",
                "data": base64_img,
            }},
        ]

    def _call_planning_llm(
        self, message_content: list[dict[str, Any]]
    ) -> Any:
        return self._gemini_client.models.generate_content(
            model=self.planning_model,
            contents=message_content,
            config=types.GenerateContentConfig(
                safety_settings=self._safety_settings
            ),
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_api_response(self, llm_response: Any) -> dict[str, Any]:
        response_text = llm_response.text.strip()

        start_index = response_text.find('{')
        end_index = response_text.rfind('}')

        try:
            return json.loads(
                response_text[start_index:end_index + 1].strip()
            )
        except Exception as e:
            print(f'Error parsing Gemini Flash response: {e}')
            return {}

    def cleanup(self):
        self.cancel_prefetch()
        self._frame_buffer.clear()
        self._executor.shutdown(wait=False)


# ======================================================================
# Module-level helpers (no instance state — safe to call from tests)
# ======================================================================

def _parse_local_answer(answer: str) -> Optional[dict[str, Any]]:
    """Convert Moondream's natural-language answer into an action dict.

    Returns ``None`` if the answer cannot be parsed or signals
    uncertainty (triggers API escalation).
    """
    upper = answer.upper().strip()

    # ── Task completion ──
    if upper.startswith('DONE'):
        done_msg = answer[4:].strip() or 'Task completed.'
        return {'steps': [], 'done': done_msg}

    # ── Explicit escalation ──
    if upper.startswith('UNCERTAIN') or upper.startswith('UNSURE'):
        return None

    # ── CLICK <cell> ──
    if upper.startswith('CLICK'):
        cell = _extract_cell(answer)
        if cell:
            return _make_step('click_cell', {'cell': cell}, answer)

    # ── TYPE '<text>' ──
    if upper.startswith('TYPE'):
        type_match = re.search(r"""['"](.+?)['"]""", answer)
        if type_match:
            return _make_step(
                'write',
                {'string': type_match.group(1), 'interval': 0.05},
                answer,
            )

    # ── PRESS <key> ──
    if upper.startswith('PRESS'):
        parts = answer.split()
        if len(parts) >= 2:
            key = parts[1].lower().strip("'\"")
            return _make_step('press', {'key': key}, answer)

    # ── Fallback: try to find a cell reference anywhere ──
    cell = _extract_cell(answer)
    if cell:
        return _make_step('click_cell', {'cell': cell}, answer)

    # ── Check for escalation keywords in free-form text ──
    if any(s in answer.lower() for s in _ESCALATION_SIGNALS):
        return None

    # ── Unrecognised → escalate to API ──
    return None


def _extract_cell(text: str) -> Optional[str]:
    """Extract a grid cell reference (e.g. ``F12``, ``AA3``) from text."""
    match = re.search(r'\b([A-Z]{1,2}\d{1,3})\b', text.upper())
    return match.group(1) if match else None


def _make_step(
    function: str,
    parameters: dict[str, Any],
    justification: str,
) -> dict[str, Any]:
    """Build a single-step instruction dict."""
    return {
        'steps': [{
            'function': function,
            'parameters': parameters,
            'human_readable_justification': justification,
        }],
        'done': None,
    }
