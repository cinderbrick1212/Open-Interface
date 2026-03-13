"""Logging configuration for Noclip Desktop.

Sets up a rotating log file placed next to the executable when running
as a PyInstaller bundle, or in the project root when running from source.
All ``print()`` calls and ``logging.*`` calls are captured in the log file
via a stdout/stderr tee so that no existing code needs to be changed.
"""

import atexit
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_FILENAME = 'noclip-desktop.log'


def _get_log_dir() -> str:
    """Return the directory where the log file should be written.

    When running as a PyInstaller bundle (``sys.frozen`` is ``True``),
    logs are placed next to the executable so users can find them easily.
    When running from source, logs are written to the project root (the
    parent of the ``app/`` directory).
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller sets sys.executable to the path of the .exe/.app
        return os.path.dirname(sys.executable)
    # Running from source: go two levels up from this file (app/utils/ → app/ → project root)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Tee:
    """Write to both *original* stream and an open *log_file* handle.

    Replacing ``sys.stdout`` / ``sys.stderr`` with this class ensures that
    every ``print()`` statement as well as any ``logging.StreamHandler``
    output ends up in both the console and the log file without requiring
    changes throughout the codebase.
    """

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data: str) -> int:
        n = 0
        if self._original is not None:
            try:
                n = self._original.write(data)
            except Exception:  # pylint: disable=broad-except
                pass
        try:
            self._log_file.write(data)
            self._log_file.flush()
        except Exception:  # pylint: disable=broad-except
            pass
        return n

    def flush(self) -> None:
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:  # pylint: disable=broad-except
                pass
        try:
            self._log_file.flush()
        except Exception:  # pylint: disable=broad-except
            pass

    def isatty(self) -> bool:
        return False

    # Allow attribute look-ups (e.g. .encoding) to fall through to the
    # underlying stream so third-party code that inspects sys.stdout works.
    def __getattr__(self, name):
        if self._original is None:
            raise AttributeError(f"'_Tee' has no original stream and no attribute '{name}'")
        return getattr(self._original, name)


def setup_logging() -> str:
    """Configure the root logger and redirect stdout/stderr to the log file.

    * A :class:`~logging.handlers.RotatingFileHandler` (max 1 MB, 3 backups)
      is added to the root logger so all ``logging.*`` calls land in the file.
    * ``sys.stdout`` and ``sys.stderr`` are replaced with :class:`_Tee`
      instances that mirror output to both the terminal and the log file,
      capturing every ``print()`` statement without touching existing code.

    Returns the absolute path of the log file.
    """
    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, LOG_FILENAME)

    root = logging.getLogger()
    # Avoid adding duplicate handlers if setup_logging() is called more than once.
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return log_path

    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Rotating file handler — the primary sink for logging.* calls
    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding='utf-8',
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Tee stdout and stderr so that print() statements also land in the log
    _log_file = open(log_path, 'a', encoding='utf-8', buffering=1)  # pylint: disable=consider-using-with
    atexit.register(_log_file.close)
    sys.stdout = _Tee(sys.__stdout__, _log_file)
    sys.stderr = _Tee(sys.__stderr__, _log_file)

    logging.info("Logging started — log file: %s", log_path)
    return log_path
