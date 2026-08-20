from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from config.config import (
    LEDFX_BASE_URL,
    LEDFX_ENABLED,
    LEDFX_REQUEST_TIMEOUT_S,
    LEDFX_SCENE_REFRESH_S,
)
from storage.json_store import read_json, write_json
from storage.migrations import SCHEMA_VERSION
from storage.paths import config_path, ensure_layout


class DMXConfig(BaseModel):
    """
    E1.31 (sACN) output settings.

    ``transport`` gates the wire: the default emits nothing, and ``"e131"`` is set by
    hand in the user's local ``config.json`` once the rig is wired (D-013). This rig runs
    a **single universe, universe 1**, and sends **unicast** to the switch IP (D-017;
    ``mode`` defaults to ``"unicast"``). Slot count is not configurable — it is
    ``UNIVERSE_SIZE``, fixed by the protocol. The universe box blacks out when packets
    stop, so ``refresh_hz`` is what holds a look, not just packet-loss insurance
    (docs/fixture_and_transport_strategy.md §6).

    No IP belongs in this file's defaults: ``host`` and ``bind_address`` are filled in
    locally, outside the repository.
    """

    transport: Literal["null", "e131"] = "null"
    mode: Literal["unicast", "multicast"] = "unicast"
    universe: int = Field(default=1, ge=1, le=63999)
    host: str = "127.0.0.1"
    port: int = Field(default=5568, ge=1, le=65535)
    priority: int = Field(default=100, ge=0, le=200)
    source_name: str = Field(default="Lights App", min_length=1, max_length=63)

    # The local NIC to send from, as an address rather than an adapter name. Explicit
    # because a machine with both Wi-Fi and Ethernet will otherwise pick by route metric,
    # and multicast in particular has to be pinned to the interface the rig is on.
    bind_address: Optional[str] = None

    # A full 512-slot DMX frame tops out near 44 Hz on the physical bus, so a faster
    # keepalive only adds traffic the gateway has to coalesce (AF-L01, F-15).
    refresh_hz: int = Field(default=44, ge=1)


class LedfxConfig(BaseModel):
    """LEDfx HTTP integration. Nothing calls out unless ``enabled`` is true."""

    enabled: bool = LEDFX_ENABLED
    base_url: str = LEDFX_BASE_URL
    scene_refresh_s: float = LEDFX_SCENE_REFRESH_S
    request_timeout_s: float = LEDFX_REQUEST_TIMEOUT_S


class ILDAConfig(BaseModel):
    device: Optional[str] = None
    points_per_second: int = 30000


class AudioConfig(BaseModel):
    input_device: Optional[str] = None


class UIConfig(BaseModel):
    theme: str = "dark"
    last_scene_id: Optional[str] = None


class ServerConfig(BaseModel):
    """
    Bind address for the operator server.

    ``0.0.0.0`` exposes the app to the LAN, which is the point — the operator drives it
    from a phone or tablet. There is no auth, so the port stands on the LAN being
    trusted. 8800 avoids LEDfx on 8888 and the commonly-taken 8000/8080.
    """

    host: str = "0.0.0.0"
    port: int = Field(default=8800, ge=1, le=65535)


class AppConfig(BaseModel):
    """Every field carries a default, so a config file missing keys still loads."""

    schema_version: int = SCHEMA_VERSION
    server: ServerConfig = Field(default_factory=ServerConfig)
    dmx: DMXConfig = Field(default_factory=DMXConfig)
    ledfx: LedfxConfig = Field(default_factory=LedfxConfig)
    ilda: ILDAConfig = Field(default_factory=ILDAConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


def load_config(root: Optional[Path] = None) -> AppConfig:
    payload = read_json(config_path(root), root)
    if payload is None:
        return AppConfig()
    return AppConfig.model_validate(payload)


def save_config(config: AppConfig, root: Optional[Path] = None) -> None:
    write_json(config_path(root), config.model_dump())


def ensure_config(root: Optional[Path] = None) -> AppConfig:
    """Load the config, writing the normalized file back when it is missing or incomplete."""
    resolved = ensure_layout(root)
    payload = read_json(config_path(resolved), resolved)
    config = AppConfig() if payload is None else AppConfig.model_validate(payload)
    if payload != config.model_dump():
        save_config(config, resolved)
    return config
