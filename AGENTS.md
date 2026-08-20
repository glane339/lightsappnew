# Agent instructions

Guidance for AI coding agents working in this repository.

## Project layout

- Put Python/server code in `backend/`
- Put client/UI code in `frontend/`
- WS-11.2 layout and modes: [docs/frontend_architecture.md](docs/frontend_architecture.md)
- Keep root-level files limited to project config and docs (`README.md`, `AGENTS.md`, `requirements.txt`, `.gitignore`)

## Python environment

- Use the project venv at `venv/` (Python 3.12). `.venv/` is also gitignored if
  you created the env under that name.
- Install packages with `.\venv\Scripts\python.exe -m pip install <package>`
  (or `.\.venv\Scripts\python.exe` if that is your env path)
- When adding a dependency, update `requirements.txt` with the pinned version
- Do not commit `venv/` or `.venv/`

## Coding conventions

- Prefer small, focused changes that match existing structure
- Do not add docs or config files unless asked
- Keep backend and frontend concerns separated
- A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` in new writing
  ([D-023](docs/decisions.md#d-023-a-look-is-a-dmx_preset))
