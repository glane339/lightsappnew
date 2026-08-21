"""
The app factory.

One process, one event loop, one show — ``workers`` is deliberately 1, since a second
worker would mean a second engine fighting for the same universe. The factory takes an
explicit data root so tests can build a real app against a temp folder.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from authoring.service import AuthoringService
from audio.audio_engine_source import AudioEngineBeatSource
from server.commands import CommandKind, ShowCommand
from server.commands import ShowEvent
from server.beat_timing import DetectedBeatTiming
from server.engine import ShowBusyError, ShowEngine
from server.errors import register_exception_handlers
from server.routes.authoring import router as authoring_router
from server.routes.diag import router as diag_router
from server.routes.ledfx import router as ledfx_router
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


def _submit_detected_beat(
    engine: ShowEngine, timing: DetectedBeatTiming | None = None
) -> None:
    """Bridge one detected beat to the show thread without blocking audio capture."""

    submitted_ns = time.perf_counter_ns()
    if timing is not None:
        timing = replace(timing, command_submitted_ns=submitted_ns)
    try:
        engine.submit(
            ShowCommand(
                kind=CommandKind.BEAT,
                received_ns=submitted_ns,
                detected_beat_timing=timing,
            )
        )
    except ShowBusyError:
        if timing is not None:
            engine.detected_beat_timing.record_drop(timing)
        logger.warning("dropped detected beat because the show command queue is full")


def _default_input_device_selector() -> int | str | None:
    """PortAudio's default input, used when ``AudioConfig.input_device`` is unset."""

    try:
        import sounddevice as sd
    except ImportError:
        logger.warning("live audio default device unavailable: sounddevice is not installed")
        return None
    try:
        default_in = sd.default.device[0]
    except Exception:
        logger.exception("could not read PortAudio default input device")
        return None
    if isinstance(default_in, bool) or not isinstance(default_in, int) or default_in < 0:
        logger.warning("PortAudio reports no default input device")
        return None
    try:
        info = sd.query_devices(default_in)
        name = info["name"] if isinstance(info, dict) else getattr(info, "name", default_in)
        logger.info("using PortAudio default input [%s] %s", default_in, name)
    except Exception:
        logger.info("using PortAudio default input [%s]", default_in)
    return default_in


def _resolve_input_device(configured: Optional[str]) -> int | str | None:
    """Prefer an explicit config selector; otherwise take the host default input."""

    if configured is not None:
        if not configured.strip():
            return None
        return configured
    return _default_input_device_selector()


def _build_audio_source(input_device: int | str) -> AudioEngineBeatSource | None:
    """Create the optional live source without importing hardware support at app startup."""

    try:
        from lights_audio_engine import AudioEngine
        from lights_audio_engine.capture import SoundDeviceAudioSource, run_engine
    except ImportError:
        logger.exception("live audio is configured but lights-audio-engine is unavailable")
        return None
    try:
        source = SoundDeviceAudioSource(input_device)
    except ValueError as exc:
        logger.error("live detected audio disabled: invalid input device selector: %s", exc)
        return None
    return AudioEngineBeatSource(
        source,
        AudioEngine(),
        runner=run_engine,
    )


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
    audio_selector = _resolve_input_device(app_config.audio.input_device)
    audio_source = _build_audio_source(audio_selector) if audio_selector is not None else None
    if audio_source is not None:
        audio_source.subscribe(lambda timing: _submit_detected_beat(engine, timing))
    events: "asyncio.Queue[ShowEvent]" = asyncio.Queue(maxsize=EVENT_QUEUE_MAX)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Bound to the loop only once it is actually running, since the engine posts
        # events into it from three other threads.
        engine.bind_loop(asyncio.get_running_loop(), events)
        engine.start()
        if audio_source is not None:
            audio_source.start()
            logger.info("audio engine started")
        else:
            logger.info("audio engine not started: no usable input device")
        logger.info("show engine started")
        try:
            yield
        finally:
            if audio_source is not None:
                audio_source.stop()
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
    app.state.audio_source = audio_source
    app.state.show_events = events
    app.state.request_shutdown = None

    register_exception_handlers(app)
    app.include_router(show_router)
    app.include_router(scenes_router)
    app.include_router(authoring_router)
    app.include_router(status_router)
    app.include_router(diag_router)
    app.include_router(ledfx_router)

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
