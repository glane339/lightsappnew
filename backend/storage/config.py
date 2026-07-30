from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from storage.json_store import read_json, write_json
from storage.migrations import SCHEMA_VERSION
from storage.paths import config_path, ensure_layout


class DMXConfig(BaseModel):
    universe: int = 0
    interface: Optional[str] = None
    refresh_hz: int = 120


class WLEDConfig(BaseModel):
    devices: List[str] = []
    discovery_enabled: bool = True


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
    wled: WLEDConfig = Field(default_factory=WLEDConfig)
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
