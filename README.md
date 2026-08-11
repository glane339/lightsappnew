# Lights App

Show-control application for a lighting rig: DMX over E1.31, WLED via LEDfx, and
(deferred) ILDA laser output, driven by manually selected, audio-reactive scenes.

**Current state:** persistence layer, in-memory DMX flatten, and an unwired LEDfx
HTTP client/scene sync. There is no app entry point, UI, audio processing, or DMX
network output yet. See [docs/project_overview.md](docs/project_overview.md).

## Structure

- `backend/` — Python backend
  - `models/` — pydantic runtime models
  - `storage/` — JSON persistence, integrity, migrations, archive
  - `runtime/` — in-memory active state
  - `ledfx/` — LEDfx HTTP client and scene sync (null by default)
  - `config/` — compile-time defaults that seed persisted `AppConfig`
  - `logging_setup.py` — file + stderr logging into the data-folder `logs/`
- `tests/` — pytest suite (storage layer; uses a temp data root)
- `docs/` — architecture documentation ([start here](docs/project_overview.md))
  - `fixtures/` — per-model DMX channel tables ([index](docs/fixtures/README.md))
- `requirements.txt` — Python dependencies
- `AGENTS.md` — Instructions for AI coding agents

A `frontend/` directory is planned but does not exist yet.

## Setup

Requires Python 3.12+.

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Imports are absolute from `backend/` (no package `__init__.py`). pytest sets
`pythonpath = backend` via `pytest.ini`.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest
```

Tests inject a temporary data root and never touch `%LOCALAPPDATA%\LightsApp`.
Override the live data folder with `LIGHTSAPP_DATA_DIR` when running the app.

## Dependencies

- [pydantic](https://docs.pydantic.dev/) — data validation
- [platformdirs](https://platformdirs.readthedocs.io/) — per-user data folder
- [httpx](https://www.python-httpx.org/) — LEDfx HTTP client
- [pytest](https://docs.pytest.org/) — test runner
