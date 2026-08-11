from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    E1.31 (sACN) output settings, carried over from the previous app's config.

    No transport reads these yet. The universe numbering starts at 1 to match
    ``DMX_Device.universe`` and E1.31 itself, where 0 is not a valid universe. Slot
    count is not configurable — it is ``UNIVERSE_SIZE``, fixed by the protocol.
    """

    universe: int = Field(default=1, ge=1, le=63999)
    host: str = "127.0.0.1"
    port: int = Field(default=5568, ge=1, le=65535)
    priority: int = Field(default=100, ge=0, le=200)
    interface: Optional[str] = None
    refresh_hz: int = Field(default=120, ge=1)


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
    default_sensitivity: float = 0.5


class UIConfig(BaseModel):
    theme: str = "dark"
    last_scene_id: Optional[str] = None


class AppConfig(BaseModel):
    """Every field carries a default, so a config file missing keys still loads."""

    schema_version: int = SCHEMA_VERSION
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
