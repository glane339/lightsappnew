# Agent instructions

Guidance for AI coding agents working in this repository.

## Project layout

- Put Python/server code in `backend/`
- Put client/UI code in `frontend/`
- Keep root-level files limited to project config and docs (`README.md`, `AGENTS.md`, `requirements.txt`, `.gitignore`)

## Python environment

- Use the project venv at `venv/` (Python 3.12)
- Install packages with `.\venv\Scripts\python.exe -m pip install <package>`
- When adding a dependency, update `requirements.txt` with the pinned version
- Do not commit `venv/`

## Coding conventions

- Prefer small, focused changes that match existing structure
- Do not add docs or config files unless asked
- Keep backend and frontend concerns separated
