from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

APP_NAME = "LightsApp"
# False keeps Windows at %LOCALAPPDATA%\LightsApp instead of nesting under a vendor folder.
APP_AUTHOR = False

# Points the whole layer at a different folder, for tests and portable installs.
DATA_ROOT_ENV_VAR = "LIGHTSAPP_DATA_DIR"

CONFIG_FILE_NAME = "config.json"
DATA_DIR_NAME = "data"
ILDA_DIR_NAME = "ilda"
BACKUPS_DIR_NAME = "backups"
LOGS_DIR_NAME = "logs"

ILDA_BLOB_SUFFIX = ".ild"


def data_root(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root).expanduser()
    override = os.environ.get(DATA_ROOT_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path(user_data_dir(APP_NAME, APP_AUTHOR, roaming=False))


def config_path(root: Optional[Path] = None) -> Path:
    return data_root(root) / CONFIG_FILE_NAME


def data_dir(root: Optional[Path] = None) -> Path:
    return data_root(root) / DATA_DIR_NAME


def ilda_dir(root: Optional[Path] = None) -> Path:
    return data_root(root) / ILDA_DIR_NAME


def backups_dir(root: Optional[Path] = None) -> Path:
    return data_root(root) / BACKUPS_DIR_NAME


def logs_dir(root: Optional[Path] = None) -> Path:
    return data_root(root) / LOGS_DIR_NAME


def collection_path(collection: str, root: Optional[Path] = None) -> Path:
    return data_dir(root) / f"{collection}.json"


def ilda_blob_name(frame_id: str) -> str:
    return f"{frame_id}{ILDA_BLOB_SUFFIX}"


def ilda_blob_path(frame_id: str, root: Optional[Path] = None) -> Path:
    return ilda_dir(root) / ilda_blob_name(frame_id)


def ensure_layout(root: Optional[Path] = None) -> Path:
    resolved = data_root(root)
    for directory in (resolved, data_dir(resolved), ilda_dir(resolved), backups_dir(resolved), logs_dir(resolved)):
        directory.mkdir(parents=True, exist_ok=True)
    return resolved


def new_backup_dir(label: str, root: Optional[Path] = None) -> Path:
    parent = backups_dir(root)
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = parent / f"{stamp}-{label}"
    counter = 1
    while candidate.exists():
        candidate = parent / f"{stamp}-{label}-{counter}"
        counter += 1
    candidate.mkdir(parents=True)
    return candidate
