"""Configure application logging to the data-folder ``logs/`` directory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from storage.paths import ensure_layout, logs_dir

DEFAULT_LOG_NAME = "lightsapp.log"
_CONFIGURED = False


def configure_logging(
    root: Optional[Path] = None,
    *,
    level: int = logging.INFO,
    log_name: str = DEFAULT_LOG_NAME,
) -> Path:
    """
    Attach a file handler under ``logs/`` and a stderr stream handler.

    Safe to call more than once; subsequent calls are no-ops unless the process
    is restarted. Returns the log file path.
    """
    global _CONFIGURED
    resolved = ensure_layout(root)
    log_path = logs_dir(resolved) / log_name

    if _CONFIGURED:
        return log_path

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    _CONFIGURED = True
    return log_path


def reset_logging_for_tests() -> None:
    """Drop handlers so tests can reconfigure against a temp data root."""
    global _CONFIGURED
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    _CONFIGURED = False
