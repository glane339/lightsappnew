from __future__ import annotations

import logging
from pathlib import Path

from logging_setup import configure_logging, reset_logging_for_tests, shutdown_logging


def test_configure_logging_writes_to_logs_dir(data_root: Path) -> None:
    reset_logging_for_tests()
    log_path = configure_logging(data_root, level=logging.INFO)
    assert log_path.is_file() or log_path.parent.is_dir()

    logging.getLogger("tests.logging").info("hello from test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "hello from test" in text


def test_queued_logging_reaches_the_file_after_shutdown(data_root: Path) -> None:
    reset_logging_for_tests()
    log_path = configure_logging(data_root, queued=True)
    logging.getLogger("tests.logging").info("queued hello")
    shutdown_logging()

    assert "queued hello" in log_path.read_text(encoding="utf-8")
