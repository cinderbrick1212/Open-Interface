"""Tests for app/utils/log_setup.py.

Validates that ``setup_logging()`` creates a log file in the expected
directory and that both ``logging.*`` calls and ``print()`` statements
are captured in that file.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from utils.log_setup import _get_log_dir, _Tee, LOG_FILENAME, setup_logging


# ── _get_log_dir ─────────────────────────────────────────────────────

class TestGetLogDir:
    """Unit tests for the log-directory resolution helper."""

    def test_source_run_returns_project_root(self):
        """When not frozen, the log dir should be two levels above app/utils/log_setup.py (i.e. project root)."""
        with patch.object(sys, 'frozen', False, create=True):
            log_dir = _get_log_dir()
        # The project root contains requirements.txt
        assert os.path.isfile(os.path.join(log_dir, 'requirements.txt'))

    def test_frozen_run_returns_exe_dir(self, tmp_path):
        """When frozen, the log dir should equal the directory of sys.executable."""
        fake_exe = str(tmp_path / 'Noclip Desktop.exe')
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', fake_exe):
            log_dir = _get_log_dir()
        assert log_dir == str(tmp_path)


# ── _Tee ─────────────────────────────────────────────────────────────

class TestTee:
    """Unit tests for the stdout/stderr tee helper."""

    def _make_handler(self, tmp_path, filename='tee_handler.log'):
        """Return a RotatingFileHandler writing to *tmp_path/filename*."""
        h = RotatingFileHandler(
            str(tmp_path / filename), maxBytes=1_000_000, backupCount=1,
            encoding='utf-8',
        )
        return h

    def test_write_goes_to_both_streams(self, tmp_path):
        import io
        original = io.StringIO()
        handler = self._make_handler(tmp_path)
        tee = _Tee(original, handler)

        tee.write('hello')

        assert original.getvalue() == 'hello'
        handler.stream.flush()
        handler.close()
        assert (tmp_path / 'tee_handler.log').read_text(encoding='utf-8') == 'hello'

    def test_isatty_returns_false(self, tmp_path):
        import io
        handler = self._make_handler(tmp_path, 'isatty.log')
        tee = _Tee(io.StringIO(), handler)
        assert tee.isatty() is False
        handler.close()

    def test_none_original_does_not_raise(self, tmp_path):
        handler = self._make_handler(tmp_path, 'none_original.log')
        tee = _Tee(None, handler)
        tee.write('data')  # Should not raise
        handler.close()

    def test_write_uses_handler_stream_not_separate_handle(self, tmp_path):
        """_Tee must not hold a separate open() handle — it writes via handler.stream."""
        import io
        handler = self._make_handler(tmp_path, 'shared.log')
        tee = _Tee(io.StringIO(), handler)
        tee.write('via_tee')
        handler.stream.flush()
        handler.close()
        contents = (tmp_path / 'shared.log').read_text(encoding='utf-8')
        assert 'via_tee' in contents
        # _Tee must not have its own _log_file attribute
        assert not hasattr(tee, '_log_file')


# ── setup_logging ─────────────────────────────────────────────────────

class TestSetupLogging:
    """Integration tests for ``setup_logging()``."""

    @pytest.fixture(autouse=True)
    def _restore_streams_and_logger(self):
        """Restore sys.stdout/stderr and root logger handlers after each test."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        yield
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        root.handlers = original_handlers
        root.level = original_level

    def test_log_file_created_in_specified_dir(self, tmp_path):
        """setup_logging() must create the log file in the requested directory."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            log_path = setup_logging()
        assert os.path.isfile(log_path)
        assert os.path.basename(log_path) == LOG_FILENAME
        assert os.path.dirname(log_path) == str(tmp_path)

    def test_logging_calls_appear_in_log_file(self, tmp_path):
        """logging.info() messages should be written to the log file."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            log_path = setup_logging()
        logging.getLogger('test_logger').info('sentinel_message_123')
        # Flush all handlers
        for h in logging.getLogger().handlers:
            h.flush()
        contents = (tmp_path / LOG_FILENAME).read_text(encoding='utf-8')
        assert 'sentinel_message_123' in contents

    def test_print_appears_in_log_file(self, tmp_path):
        """print() output should be captured in the log file via stdout Tee."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            setup_logging()
        print('unique_print_output_xyz')
        sys.stdout.flush()
        contents = (tmp_path / LOG_FILENAME).read_text(encoding='utf-8')
        assert 'unique_print_output_xyz' in contents

    def test_no_second_file_handle(self, tmp_path):
        """After setup_logging(), sys.stdout must not hold a private _log_file."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            setup_logging()
        assert not hasattr(sys.stdout, '_log_file')
        assert not hasattr(sys.stderr, '_log_file')

    def test_idempotent_when_called_twice(self, tmp_path):
        """Calling setup_logging() twice must not duplicate file handlers."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            setup_logging()
            setup_logging()
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_returns_absolute_path(self, tmp_path):
        """The returned path should be absolute."""
        with patch('utils.log_setup._get_log_dir', return_value=str(tmp_path)):
            log_path = setup_logging()
        assert os.path.isabs(log_path)
