"""
Window enumeration for Windows OS.
Uses ctypes to call Win32 APIs to list visible windows with their titles and positions.
"""
import platform
from typing import Optional


def _is_windows() -> bool:
    return platform.system() == "Windows"


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
