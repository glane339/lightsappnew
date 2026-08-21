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
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

from audio.audio_engine_source import AudioEngineBeatSource
from authoring.service import AuthoringService
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from server.beat_timing import DetectedBeatTiming
from server.commands import CommandKind, ShowCommand, ShowEvent
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
from storage.paths import config_path, ensure_layout

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


def _default_input_device_selector() -> int | None:
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
    return default_in


def _resolve_input_device(configured: str | None) -> int | None:
    """Resolve one input before capture starts; explicit failures never fall back."""

    if configured is not None:
        selector = configured.strip()
        if not selector:
            logger.error("live detected audio disabled: explicit audio input selector is blank")
            return None
        requested = repr(configured)
    else:
        selector = _default_input_device_selector()
        if selector is None:
            return None
        requested = "PortAudio default"

    try:
        import sounddevice as sd
    except ImportError:
        logger.exception("live audio input cannot be resolved: sounddevice is not installed")
        return None

    try:
        info = sd.query_devices(selector, "input")
        if not isinstance(info, Mapping):
            raise TypeError("PortAudio returned malformed device information")
        index = info["index"]
        host_api_index = info["hostapi"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise TypeError("PortAudio returned an invalid device index")
        if isinstance(host_api_index, bool) or not isinstance(host_api_index, int):
            raise TypeError("PortAudio returned an invalid host API index")
        name = str(info["name"])
        host_api = sd.query_hostapis(host_api_index)
        if not isinstance(host_api, Mapping):
            raise TypeError("PortAudio returned malformed host API information")
        host_api_name = str(host_api["name"])
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        if configured is not None:
            logger.error(
                "live detected audio disabled: explicit audio input selector %s could not be "
                "resolved uniquely: %s",
                requested,
                exc,
            )
        else:
            logger.error(
                "live detected audio disabled: default input could not be resolved: %s", exc
            )
        return None

    logger.info(
        "selected audio input: requested=%s, resolved=[%d] %s, host API=%s",
        requested,
        index,
        name,
        host_api_name,
    )
    return index


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
    config: AppConfig | None = None,
    *,
    data_root: Path | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI:
    resolved_root = ensure_layout(data_root)
    logger.info(
        "application data root: %s; config path: %s",
        resolved_root,
        config_path(resolved_root),
    )
    app_config = config if config is not None else ensure_config(resolved_root)
    library = Library.open(resolved_root, sync_ilda=False)
    authoring = AuthoringService(library)
    engine = ShowEngine(library, app_config, authoring=authoring)
    audio_selector = _resolve_input_device(app_config.audio.input_device)
    audio_source = _build_audio_source(audio_selector) if audio_selector is not None else None
    if audio_source is not None:
        audio_source.subscribe(lambda timing: _submit_detected_beat(engine, timing))
    events: asyncio.Queue[ShowEvent] = asyncio.Queue(maxsize=EVENT_QUEUE_MAX)

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
