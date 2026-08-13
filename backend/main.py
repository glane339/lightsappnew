"""
Entry point. ``python backend/main.py``, or ``.\\venv\\Scripts\\python.exe backend/main.py``.

Binds the LAN so the operator can drive the rig from a phone; there is no auth, so this
assumes a trusted network. On Windows the port needs an inbound firewall rule before
anything but localhost can connect.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Absolute imports from backend/, matching the rest of the project (no packages).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from logging_setup import configure_logging, shutdown_logging
from server import tuning
from server.app import create_app
from storage.config import ensure_config

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging(queued=True)
    config = ensure_config()
    tuning.apply()
    try:
        app = create_app(config)
        logger.info(
            "serving on http://%s:%d (ws at /ws/show)", config.server.host, config.server.port
        )
        # TCP_NODELAY needs no setting here: asyncio disables Nagle on accepted stream
        # transports itself (see asyncio.base_events._set_nodelay), on both the selector
        # and proactor loops. Nagle would otherwise batch control frames and cost more
        # than the entire budget.
        uvicorn.run(
            app,
            host=config.server.host,
            port=config.server.port,
            workers=1,
            log_level="info",
            timeout_graceful_shutdown=5,
        )
    finally:
        tuning.release()
        shutdown_logging()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
