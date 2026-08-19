"""
The app factory.

One process, one event loop, one show — ``workers`` is deliberately 1, since a second
worker would mean a second engine fighting for the same universe. The factory takes an
explicit data root so tests can build a real app against a temp folder.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from authoring.service import AuthoringService
from server.commands import ShowEvent
from server.engine import ShowEngine
from server.errors import register_exception_handlers
from server.routes.authoring import router as authoring_router
from server.routes.diag import router as diag_router
from server.routes.scenes import router as scenes_router
from server.routes.show import router as show_router
from server.routes.status import router as status_router
from server.ws import handle_show_socket
from storage.config import AppConfig, ensure_config
from storage.library import Library
from storage.paths import ensure_layout

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Bounded, so a client that stops reading cannot grow the queue without limit. State is
# absolute rather than incremental, so a dropped event costs nothing but a stale readout.
EVENT_QUEUE_MAX = 256


def create_app(
    config: Optional[AppConfig] = None,
    *,
    data_root: Optional[Path] = None,
    frontend_dir: Optional[Path] = None,
) -> FastAPI:
    resolved_root = ensure_layout(data_root)
    app_config = config if config is not None else ensure_config(resolved_root)
    library = Library.open(resolved_root, sync_ilda=False)
    authoring = AuthoringService(library)
    engine = ShowEngine(library, app_config, authoring=authoring)
    events: "asyncio.Queue[ShowEvent]" = asyncio.Queue(maxsize=EVENT_QUEUE_MAX)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Bound to the loop only once it is actually running, since the engine posts
        # events into it from three other threads.
        engine.bind_loop(asyncio.get_running_loop(), events)
        engine.start()
        logger.info("show engine started")
        try:
            yield
        finally:
            engine.stop()
            logger.info("show engine stopped")

    app = FastAPI(
        title="Lights App",
        summary="Operator control plane for the lighting rig",
        lifespan=lifespan,
    )
    app.state.config = app_config
    app.state.library = library
    app.state.authoring = authoring
    app.state.engine = engine
    app.state.show_events = events
    app.state.request_shutdown = None

    register_exception_handlers(app)
    app.include_router(show_router)
    app.include_router(scenes_router)
    app.include_router(authoring_router)
    app.include_router(status_router)
    app.include_router(diag_router)

    @app.websocket("/ws/show")
    async def show_socket(websocket: WebSocket) -> None:
        # Resolved off app state rather than through Depends: WebSocket routes have no
        # Request for a dependency to read.
        await handle_show_socket(websocket, engine, events)

    # Mounted last, because "/" would otherwise shadow every route above it.
    static_dir = frontend_dir if frontend_dir is not None else FRONTEND_DIR
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
    else:
        logger.warning("no frontend directory at %s; serving api only", static_dir)

    return app
