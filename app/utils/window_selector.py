"""
Window and screen enumeration for capture region selection.

Supports:
- **Windows**: Win32 APIs via ctypes for window enumeration.
- **All platforms**: ``screeninfo`` for multi-monitor detection (with
  ``pyautogui`` fallback for single-monitor systems).
"""
import platform
from typing import Optional


def _is_windows() -> bool:
    return platform.system() == "Windows"


# ── Window enumeration (Windows-only) ────────────────────────────────

def list_windows() -> list[dict]:
    """
    Enumerate visible, non-minimized top-level windows on Windows.
    Returns a list of dicts: [{"title": str, "hwnd": int, "rect": (x, y, w, h)}, ...]
    On non-Windows platforms, returns an empty list.
    """
    if not _is_windows():
        return []

    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32

    results = []

    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Skip empty or system windows
        if not title.strip():
            return True

        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        x = rect.left
        y = rect.top
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Skip windows with no size (minimized or hidden)
        if w <= 0 or h <= 0:
            return True

        results.append({
            "title": title,
            "hwnd": hwnd,
            "rect": (x, y, w, h),
        })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    return results


def get_window_rect(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """Get the current rect (x, y, w, h) of a window by its handle."""
    if not _is_windows():
        return None

    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x = rect.left
    y = rect.top
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    return (x, y, w, h)


def get_full_screen_rect() -> tuple[int, int, int, int]:
    """Return (0, 0, screen_width, screen_height) for full-screen capture."""
    import pyautogui
    sw, sh = pyautogui.size()
    return (0, 0, sw, sh)


# ── Screen / monitor enumeration (cross-platform) ───────────────────

# Maximum display length for window titles in the capture picker.
_MAX_TITLE_DISPLAY = 45
_ELLIPSIS = "…"
_NO_WINDOWS_LABEL = "No windows detected"


def list_screens() -> list[dict]:
    """Enumerate available monitors / screens.

    Returns a list of dicts::

        [{"name": "Screen 1", "rect": (x, y, w, h), "is_primary": True}, ...]

    Uses the ``screeninfo`` library when available, falling back to
    ``pyautogui.size()`` for a single-screen result.
    """
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        results = []
        for idx, m in enumerate(monitors):
            results.append({
                "name": m.name or f"Screen {idx + 1}",
                "rect": (m.x, m.y, m.width, m.height),
                "is_primary": bool(m.is_primary),
            })
        if results:
            return results
    except Exception:
        pass

    # Fallback: single screen via pyautogui
    try:
        import pyautogui
        sw, sh = pyautogui.size()
        return [{"name": "Screen 1", "rect": (0, 0, sw, sh), "is_primary": True}]
    except Exception:
        return [{"name": "Screen 1", "rect": (0, 0, 1920, 1080), "is_primary": True}]


def get_capture_choices() -> tuple[list[str], dict[str, Optional[tuple[int, int, int, int]]]]:
    """Build user-facing capture choices for the UI.

    Returns ``(labels, label_to_rect)`` where:

    - *labels* is a list of human-readable strings suitable for a radio
      button / dropdown.
    - *label_to_rect* maps each label to its capture rect ``(x, y, w, h)``
      or ``None`` for full-screen capture.

    The first entry is always "Full Screen".  On Windows, enumerated
    application windows are appended after the screen entries.
    """
    labels: list[str] = []
    label_to_rect: dict[str, Optional[tuple[int, int, int, int]]] = {}

    # -- Full screen (primary) --
    labels.append("🖥️ Full Screen")
    label_to_rect["🖥️ Full Screen"] = None

    # -- Individual screens --
    screens = list_screens()
    if len(screens) > 1:
        for s in screens:
            w, h = s["rect"][2], s["rect"][3]
            label = f"🖥️ {s['name']}  ({w}×{h})"
            labels.append(label)
            label_to_rect[label] = s["rect"]

    # -- Application windows (Windows only) --
    windows = list_windows()
    for win in windows:
        title = win["title"]
        if len(title) > _MAX_TITLE_DISPLAY:
            title = title[:_MAX_TITLE_DISPLAY - len(_ELLIPSIS)] + _ELLIPSIS
        label = f"🪟 {title}"
        # Deduplicate labels
        if label in label_to_rect:
            label = f"{label} ({win['hwnd']})"
        labels.append(label)
        label_to_rect[label] = win["rect"]

    return labels, label_to_rect
