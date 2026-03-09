import base64
import io
import os
import tempfile
import threading
from typing import Optional

import pyautogui
from PIL import Image
from utils.settings import Settings
from utils.grid import create_gridded_screenshot, gridded_screenshot_to_base64

# Maximum width (in pixels) for screenshots sent to LLMs. Larger images are
# downscaled proportionally before encoding, which significantly reduces
# payload size and speeds up API calls without meaningful quality loss for
# vision models.
MAX_SCREENSHOT_WIDTH = 1920


def _downscale(img: Image.Image, max_width: int = MAX_SCREENSHOT_WIDTH) -> Image.Image:
    """Return a proportionally downscaled copy if the image exceeds *max_width*."""
    w, h = img.size
    if w <= max_width:
        return img
    ratio = max_width / w
    new_size = (max_width, int(h * ratio))
    return img.resize(new_size, Image.LANCZOS)


class Screen:
    def __init__(self):
        self._lock = threading.Lock()
        # Currently selected capture region: (x, y, w, h) or None for full screen
        self.capture_region: Optional[tuple[int, int, int, int]] = None
        # After taking a gridded screenshot, this holds the cell->coordinate map
        self.cell_map: dict[str, tuple[int, int]] = {}

    def set_capture_region(self, region: Optional[tuple[int, int, int, int]]) -> None:
        """Set the capture region. None means full screen."""
        with self._lock:
            self.capture_region = region

    def get_size(self) -> tuple[int, int]:
        screen_width, screen_height = pyautogui.size()  # Get the size of the primary monitor.
        return screen_width, screen_height

    def get_screenshot(self) -> Image.Image:
        # Enable screen recording from settings
        with self._lock:
            region = self.capture_region
        if region:
            x, y, w, h = region
            img = pyautogui.screenshot(region=(x, y, w, h))
        else:
            img = pyautogui.screenshot()  # Takes roughly 100ms
        return img

    def get_capture_region(self) -> tuple[int, int, int, int]:
        """Return the current capture region as (x, y, w, h)."""
        with self._lock:
            region = self.capture_region
        if region:
            return region
        sw, sh = self.get_size()
        return (0, 0, sw, sh)

    def get_gridded_screenshot_in_base64(self) -> str:
        """Take a screenshot, overlay grid, and return base64 of the gridded image.
        Also updates self.cell_map with the cell-to-coordinate mapping."""
        img = self.get_screenshot()
        region = self.get_capture_region()
        gridded_img, self.cell_map = create_gridded_screenshot(img, region)
        return gridded_screenshot_to_base64(gridded_img)

    def get_screenshot_in_base64(self) -> str:
        # Base64 images work with ChatCompletions API but not Assistants API
        img = self.get_screenshot()
        img = _downscale(img)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=72)
        buf.seek(0)
        encoded_image = base64.b64encode(buf.read()).decode('utf-8')
        return encoded_image

    def get_screenshot_as_file_object(self):
        # In memory files don't work with OpenAI Assistants API because of missing filename attribute
        img_bytes = io.BytesIO()
        img = self.get_screenshot()
        img = _downscale(img)
        img.save(img_bytes, format='JPEG', quality=72)
        img_bytes.seek(0)
        return img_bytes

    def get_temp_filename_for_current_screenshot(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmpfile:
            screenshot = self.get_screenshot()
            screenshot = _downscale(screenshot)
            screenshot.save(tmpfile.name, format='JPEG', quality=72)
            return tmpfile.name

    def get_screenshot_file(self):
        # Gonna always keep a screenshot.jpg in ~/.open-interface/ because file objects, temp files, every other way has an error
        filename = 'screenshot.jpg'
        filepath = os.path.join(Settings().get_settings_directory_path(), filename)
        img = self.get_screenshot()
        img = _downscale(img)
        img.save(filepath, format='JPEG', quality=72)
        return filepath

    def get_gridded_screenshot_file(self) -> str:
        """Save a gridded screenshot to disk and return the filepath.
        Also updates self.cell_map."""
        img = self.get_screenshot()
        region = self.get_capture_region()
        gridded_img, self.cell_map = create_gridded_screenshot(img, region)
        filename = 'screenshot_gridded.jpg'
        filepath = os.path.join(Settings().get_settings_directory_path(), filename)
        # Convert RGBA to RGB if necessary (JPEG doesn't support alpha channel)
        if gridded_img.mode == "RGBA":
            gridded_img = gridded_img.convert("RGB")
        gridded_img.save(filepath, format='JPEG', quality=72)
        return filepath
