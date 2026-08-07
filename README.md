# Lights App

Show-control application for a lighting rig: DMX over E1.31, WLED via LEDfx, and
(deferred) ILDA laser output, driven by manually selected, audio-reactive scenes.

**Current state: data model and persistence layer only.** There is no entry point,
UI, audio processing, or network output yet. See
[docs/project_overview.md](docs/project_overview.md).

## Structure

- `backend/` — Python backend
  - `models/` — pydantic runtime models
  - `storage/` — JSON persistence, integrity, migrations, archive
  - `runtime/` — in-memory active state
- `docs/` — architecture documentation ([start here](docs/project_overview.md))
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

## Dependencies

- [pydantic](https://docs.pydantic.dev/) — data validation
