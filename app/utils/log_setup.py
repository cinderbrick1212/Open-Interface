"""Logging configuration for Noclip Desktop.

Sets up a rotating log file placed next to the executable when running
as a PyInstaller bundle, or in the project root when running from source.
All ``print()`` calls and ``logging.*`` calls are captured in the log file
via a stdout/stderr tee so that no existing code needs to be changed.
"""

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
    """Write to both *original* stream and the ``RotatingFileHandler``'s stream.

    Holds a reference to the :class:`~logging.handlers.RotatingFileHandler`
    rather than a separate ``open()`` file handle.  This means:

    * There is only **one** file handle for the log file (the handler's own),
      so writes from ``logging.*`` calls and from ``print()`` never interleave
      through competing handles.
    * After a log rotation the handler updates ``handler.stream`` to the new
      file; because the tee always uses ``self._handler.stream``, it follows
      the rotation automatically.
    * The handler's threading lock is acquired for every write, keeping
      ``handler.emit()`` and direct stream writes mutually exclusive.
    """

    def __init__(self, original, handler: RotatingFileHandler):
        self._original = original
        self._handler = handler

    def write(self, data: str) -> int:
        n = 0
        if self._original is not None:
            try:
                n = self._original.write(data)
            except Exception:  # pylint: disable=broad-except
                pass
        # Acquire the handler's lock so that this write and any concurrent
        # handler.emit() call are serialised; handler.stream follows rotations.
        try:
            self._handler.acquire()
            try:
                if self._handler.stream:
                    self._handler.stream.write(data)
                    self._handler.stream.flush()
            finally:
                self._handler.release()
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
            self._handler.acquire()
            try:
                if self._handler.stream:
                    self._handler.stream.flush()
            finally:
                self._handler.release()
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
    * The tee writes directly to ``file_handler.stream`` (under the handler's
      lock) so there is only one file handle and log rotation is handled
      transparently.

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

    # Rotating file handler — the single, shared file handle for the log file
    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding='utf-8',
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Tee stdout/stderr through the handler's stream so print() output also
    # lands in the log file.  No second open() handle is needed.
    sys.stdout = _Tee(sys.__stdout__, file_handler)
    sys.stderr = _Tee(sys.__stderr__, file_handler)

    logging.info("Logging started — log file: %s", log_path)
    return log_path
