"""Ring buffer of gridded screenshots that can be compiled into an MP4 video.

The :class:`FrameBuffer` stores the most recent *N* gridded PIL images
(screenshots with the cell-grid overlay already drawn).  When the API LLM
needs context, :meth:`to_video_bytes` stitches them into a short MP4 clip
so the model receives temporal context (what happened on screen over the
last 10-30 seconds) rather than a single static frame.

Continuity guarantee
--------------------
The buffer is a **rolling window** backed by a ``deque(maxlen=…)``.
Frames accumulate continuously across local Moondream steps *and* API
review cycles — ``to_video_bytes()`` reads the buffer **without clearing
it**, so consecutive API calls produce overlapping, continuous videos.
Only :meth:`clear` (called once at the start of a new user request)
resets the buffer.

Thread-safety: all public methods acquire an internal lock.
"""

import base64
import tempfile
import threading
from collections import deque
from typing import Optional

import numpy as np
from PIL import Image

# moviepy is already in requirements.txt (moviepy==1.0.3)
# Import is compatible with both moviepy 1.x and 2.x
try:
    from moviepy import ImageSequenceClip
except ImportError:
    from moviepy.editor import ImageSequenceClip


# Default maximum number of frames to keep in the ring buffer.
DEFAULT_MAX_FRAMES = 30

# Frames-per-second when rendering the video.
#
# FPS tradeoffs (configurable via ``video_fps`` in settings.json):
#
#   * **1 FPS** – Gemini samples video at ~1 FPS internally, so every
#     captured frame is guaranteed to be seen.  30 frames → 30-second
#     video.  Best for accuracy when every state change matters.
#   * **2 FPS** (default) – good balance.  30 frames → 15-second video.
#     Gemini sees roughly every other frame, which is fine for typical
#     desktop-automation tasks where consecutive frames are similar.
#   * **4+ FPS** – shorter video / faster upload, but Gemini may skip
#     more frames.  Useful if bandwidth is limited.
DEFAULT_VIDEO_FPS = 2


class FrameBuffer:
    """Fixed-size ring buffer of gridded PIL screenshots.

    The buffer is **never cleared between API review cycles** — each
    ``to_video_bytes()`` call produces a video from the current rolling
    window, ensuring recordings are continuous with each other.

    Parameters
    ----------
    max_frames : int
        Maximum frames to store.  Older frames are dropped automatically
        by the underlying ``deque``, keeping memory bounded.
    fps : int
        Frame rate used when compiling the buffer into a video.
    """

    def __init__(
        self,
        max_frames: int = DEFAULT_MAX_FRAMES,
        fps: int = DEFAULT_VIDEO_FPS,
    ) -> None:
        self._lock = threading.Lock()
        self._frames: deque[Image.Image] = deque(maxlen=max_frames)
        self._fps = fps

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def add_frame(self, gridded_img: Image.Image) -> None:
        """Append a gridded screenshot to the buffer.

        The image should already have the grid overlay drawn (i.e. the
        output of :func:`utils.grid.create_gridded_screenshot`).
        Oldest frames are dropped automatically when *max_frames* is
        reached, keeping the buffer a continuous rolling window.
        """
        with self._lock:
            self._frames.append(gridded_img.copy())

    def frame_count(self) -> int:
        """Return the number of frames currently stored."""
        with self._lock:
            return len(self._frames)

    def clear(self) -> None:
        """Drop all stored frames.

        Only called at the start of a **new user request** — never
        between API review cycles within the same request.
        """
        with self._lock:
            self._frames.clear()

    def to_video_bytes(self) -> Optional[bytes]:
        """Compile stored frames into an MP4 video and return the bytes.

        Returns ``None`` if the buffer is empty.  The video uses a low FPS
        (default 2) since it is meant for a supervisory LLM that only needs
        to understand *what happened*, not watch smooth motion.

        **Important**: this method does NOT clear the buffer.  Frames
        continue to accumulate so the next call produces a continuous,
        overlapping video.
        """
        with self._lock:
            if not self._frames:
                return None
            # Snapshot current frames while holding the lock — do NOT clear
            frames = list(self._frames)

        # Convert PIL images → numpy arrays for moviepy
        np_frames = []
        for img in frames:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            np_frames.append(np.array(img))

        clip = ImageSequenceClip(np_frames, fps=self._fps)

        # Write to a temporary file (moviepy needs a real file for MP4)
        with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
            clip.write_videofile(
                tmp.name,
                codec='libx264',
                audio=False,
                logger=None,          # suppress moviepy's verbose output
                preset='ultrafast',   # speed over compression
            )
            tmp.seek(0)
            video_data = tmp.read()

        clip.close()
        return video_data

    def to_video_base64(self) -> Optional[str]:
        """Compile frames to MP4 and return as a base64-encoded string.

        Returns ``None`` if the buffer is empty.  Convenience wrapper
        around :meth:`to_video_bytes` for Gemini's ``inline_data`` format.
        """
        video_bytes = self.to_video_bytes()
        if video_bytes is None:
            return None
        return base64.b64encode(video_bytes).decode('utf-8')
