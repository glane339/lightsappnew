# Lights App

Show-control application for a lighting rig: DMX over E1.31, WLED via LEDfx, and
(deferred) ILDA laser output, driven by manually selected, audio-reactive scenes.

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](docs/decisions.md#d-023-a-look-is-a-dmx_preset).

**Current state:** persistence layer, beat-driven show-control core, operator HTTP
server, and an E1.31 sender that frames and transmits real sACN — but stays off until
`dmx.transport` is set to `"e131"` in the local config, so a fresh install emits
nothing. Real audio capture is still not implemented; beats are manual. The
server/runtime layer was independently audited at `acc52a7`
([Audit v3](docs/audit_findings.md#audit-v3--operator-server--runtime)):
**READY WITH MINOR FIXES**. Universe **1** and the switch destination are documented
and the box **blacks out when packets stop**; transport mode is **unicast**
([D-017](docs/decisions.md#d-017-sacn-unicast-versus-multicast)). No frame has
reached the rig yet. See
[docs/project_overview.md](docs/project_overview.md).

## Structure

- `backend/` — Python backend
  - `models/` — pydantic runtime models
  - `storage/` — JSON persistence, integrity, migrations, archive
  - `runtime/` — scene controller, cue sequencer, DMX/WLED outputs, universe buffer, E1.31 framing and sender
  - `server/` — FastAPI app, show engine, control routes
  - `audio/` — beat source protocol (manual implementation only; no detector)
  - `ledfx/` — LEDfx HTTP client and scene sync (null by default)
  - `config/` — compile-time defaults that seed persisted `AppConfig`
  - `logging_setup.py` — file + stderr logging into the data-folder `logs/`
- `frontend/` — static operator UI (M1 scene picker today; WS-11.2 plan in
  [docs/frontend_architecture.md](docs/frontend_architecture.md))
- `tests/` — pytest suite (storage, sequencing, outputs, server; temp data root)
- `docs/` — architecture documentation ([start here](docs/project_overview.md))
  - `fixtures/` — per-model DMX channel tables ([index](docs/fixtures/README.md))
- `requirements.txt` — Python dependencies
- `AGENTS.md` — Instructions for AI coding agents

A `frontend/` directory holds the M1 operator page. The full UI (Performance +
Builder modes) is specified in
[docs/frontend_architecture.md](docs/frontend_architecture.md) (WS-11.2).

## Setup

Requires Python 3.12+.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(The working environment in this repository lives at `.venv/`; both `venv/` and
`.venv/` are gitignored.)

Imports are absolute from `backend/` (no package `__init__.py`). pytest sets
`pythonpath = backend` via `pytest.ini`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests inject a temporary data root and never touch `%LOCALAPPDATA%\LightsApp`.
Override the live data folder with `LIGHTSAPP_DATA_DIR` when running the app.

## Dependencies

- [pydantic](https://docs.pydantic.dev/) — data validation
- [platformdirs](https://platformdirs.readthedocs.io/) — per-user data folder
- [httpx](https://www.python-httpx.org/) — LEDfx HTTP client
- [fastapi](https://fastapi.tiangolo.com/) / [uvicorn](https://www.uvicorn.org/) — operator server
- [pytest](https://docs.pytest.org/) — test runner
