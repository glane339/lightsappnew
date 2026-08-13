"""Configure application logging to the data-folder ``logs/`` directory."""

from __future__ import annotations

import logging
import logging.handlers
import queue
from pathlib import Path
from typing import List, Optional

from storage.paths import ensure_layout, logs_dir

DEFAULT_LOG_NAME = "lightsapp.log"
_CONFIGURED = False
_LISTENER: Optional[logging.handlers.QueueListener] = None


def configure_logging(
    root: Optional[Path] = None,
    *,
    level: int = logging.INFO,
    log_name: str = DEFAULT_LOG_NAME,
    queued: bool = False,
) -> Path:
    """
    Attach a file handler under ``logs/`` and a stderr stream handler.

    With ``queued``, records go onto a queue and a listener thread does the writing, so a
    log call on the show or sender thread never waits on the disk. The server turns this
    on; everything else logs inline, where a synchronous write is easier to reason about.

    Safe to call more than once; subsequent calls are no-ops unless the process
    is restarted. Returns the log file path.
    """
    global _CONFIGURED, _LISTENER
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

    handlers: List[logging.Handler] = [file_handler, stream_handler]

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if queued:
        record_queue: "queue.SimpleQueue[logging.LogRecord]" = queue.SimpleQueue()
        queue_handler = logging.handlers.QueueHandler(record_queue)
        queue_handler.setLevel(level)
        root_logger.addHandler(queue_handler)
        _LISTENER = logging.handlers.QueueListener(
            record_queue, *handlers, respect_handler_level=True
        )
        _LISTENER.start()
    else:
        for handler in handlers:
            root_logger.addHandler(handler)

    _CONFIGURED = True
    return log_path


def shutdown_logging() -> None:
    """Stop the listener thread, flushing whatever is still queued."""
    global _LISTENER
    if _LISTENER is not None:
        _LISTENER.stop()
        _LISTENER = None


def reset_logging_for_tests() -> None:
    """Drop handlers so tests can reconfigure against a temp data root."""
    global _CONFIGURED
    shutdown_logging()
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    _CONFIGURED = False
