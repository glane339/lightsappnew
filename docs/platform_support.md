# Platform Support

What the repository assumes about its environment, what it actually requires, and
what is currently implicit rather than documented.

> Several assumptions below are **implicit in the code** rather than stated
> anywhere. They are marked as such. Where an assumption was checked against the
> machine used for the architecture review, the observation is given with the
> command that produced it.

---

## Operating system

**Windows is the target.** Evidence, all indirect but consistent:

- [`storage/paths.py:12`](../backend/storage/paths.py#L12) sets `APP_AUTHOR = False`
  with the comment *"keeps Windows at `%LOCALAPPDATA%\LightsApp` instead of nesting
  under a vendor folder"* — the only OS named in the codebase.
- [`README.md`](../README.md) gives setup instructions in PowerShell
  (`.\venv\Scripts\Activate.ps1`).
- [`AGENTS.md`](../AGENTS.md) uses `.\venv\Scripts\python.exe`.

**Nothing in the code is Windows-only.** The storage layer uses `pathlib`,
`platformdirs`, `os.replace`, and `tempfile` throughout, all cross-platform. It
would run on Linux or macOS today; the data folder would simply land in the
platform's standard location. Windows is a deployment choice, not a technical
constraint — likely driven by LEDfx and audio-device support.

One Windows-relevant detail that is already handled correctly: `os.replace` is
atomic on Windows as well as POSIX, and the temp file is created in the *same
directory* as the target ([`json_store.py:35`](../backend/storage/json_store.py#L35)),
which is required for the replace to work across all platforms.

---

## Python runtime

| | |
| --- | --- |
| **Documented requirement** | Python 3.12+ ([`README.md`](../README.md)) |
| **Actual minimum from the code** | 3.9 or later — `from __future__ import annotations` plus `typing.Dict`/`List` (not PEP 585 builtins) throughout, and `Path.unlink(missing_ok=True)` at [`json_store.py:45`](../backend/storage/json_store.py#L45) requires 3.8+ |
| **Observed locally** | `python --version` → `Python 3.11.9`; `py -3.12 --version` → *"No suitable Python runtime found"* |

Nothing requires 3.12 specifically. The version in the README is a preference, not a
constraint, and the documented runtime is not present on the machine inspected.
Tracked as [AF-D03](audit_findings.md#af-d03).

### Virtual environment

[`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md) both assume a venv at the
repository root:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`venv/` is gitignored ([`.gitignore`](../.gitignore)) and **does not currently
exist** in the working tree.

### Dependencies

```
platformdirs==4.11.0
pydantic==2.13.4
typing==3.7.4.3          <- remove: Python 3.4-3.6 backport, no purpose here
typing_extensions==4.16.0 <- transitive (pydantic), not imported directly
```

Only `platformdirs` and `pydantic` are actually imported by the code. See
[AF-L02](audit_findings.md#af-l02).

Dependencies that will be needed and are **not yet present**: an sACN library, an
HTTP client for LEDfx, an audio capture library, and pytest. None should be added
until the corresponding workstream begins.

---

## Import root

**Implicit and undocumented** — [AF-D02](audit_findings.md#af-d02).

There is no `__init__.py` anywhere and no `pyproject.toml`. Imports are absolute
from the `backend/` directory:

```python
# backend/storage/library.py:8
from models.DMX_Device_Preset import DMX_Device_Preset
from storage.config import AppConfig, ensure_config, save_config
```

This works only via implicit namespace packages (PEP 420) with `backend/` on
`sys.path`. In practice that means running with `backend/` as the working directory,
or setting `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "$PWD\backend"
```

Nothing in the repository states this. It is the first thing a new contributor will
trip over, and it also means there is currently no way to `pip install` the project
or to run tests from the repository root without configuration.

There is also a stray empty `backend/config/config.py`
([AF-M07](audit_findings.md#af-m07)) which shadows nothing today but creates a second
plausible import path for "config" — the real one is
[`backend/storage/config.py`](../backend/storage/config.py).

---

## Data folder

The application stores nothing inside the repository. Layout, from
[`storage/paths.py`](../backend/storage/paths.py):

```text
%LOCALAPPDATA%\LightsApp\          (Windows; platformdirs picks the equivalent elsewhere)
├── config.json                    AppConfig — dmx / wled / ilda / audio / ui
├── data/                          one JSON file per collection
│   ├── scenes.json
│   ├── presets.json
│   ├── dmx_preset_lists.json
│   ├── dmx_presets.json
│   ├── dmx_device_presets.json
│   ├── wled_presets.json
│   ├── ilda_frame_lists.json
│   └── ilda_frames.json
├── ilda/                          .ild blobs; filename is the frame id
├── backups/                       timestamped snapshots and quarantined files
└── logs/                          created, but nothing writes to it yet (AF-M08)
```

**Override:** set `LIGHTSAPP_DATA_DIR`
([`paths.py:15`](../backend/storage/paths.py#L15)) to point the whole layer
elsewhere — intended for tests and portable installs. Every storage function also
takes an explicit `root` parameter.

Two consequences worth knowing:

- **No user data or local paths can leak into git.** This is a genuine strength.
- **Constructing a `Library` creates directories and can write `config.json`**
  ([`library.py:91-93`](../backend/storage/library.py#L91-L93)). Always pass a temp
  `root` in tests, or the real data folder is modified —
  [AF-M05](audit_findings.md#af-m05).

---

## Network

**Nothing in the repository opens a socket.** No firewall rule is needed today.

When transport work begins ([roadmap phase 4](roadmap.md#phase-4--reliable-dmx-universe-state-and-e131-transport)):

| Path | Requirement | Notes |
| --- | --- | --- |
| E1.31 / sACN out | Outbound UDP, port 5568 | Windows Firewall prompts on first bind — worth pre-approving rather than discovering mid-show |
| Multicast (if chosen) | IGMP on the LAN | Unicast is recommended for a single receiver; see [D-017](decisions.md#d-017-sacn-unicast-versus-multicast) |
| LEDfx | HTTP to the LEDfx host | Typically `127.0.0.1:8888` when LEDfx runs on the same machine |

The application and the lighting hardware must be on the same LAN. The DMX universe
box's addressing is **unverified** —
[fixture_and_transport_strategy.md](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).

No IPs, hostnames, MAC addresses, or credentials belong in the repository. They go in
the user's `config.json`, which lives outside the working tree.

---

## Audio devices

**No audio code exists**, so there is no requirement today.
`AudioConfig.input_device: Optional[str]` ([`storage/config.py:30`](../backend/storage/config.py#L30))
is the only placeholder and is unread.

The decision that matters for this deployment, when the work starts: if the music
plays on the same PC, capturing it requires **WASAPI loopback**, not a line-in
device. That constrains the library choice, and the choice should be made with that
requirement in mind rather than discovered afterwards. Tracked as open question 2 in
[audio_reactivity_architecture.md](audio_reactivity_architecture.md#10-open-questions).

---

## LEDfx

An **external process**, not a library — see
[D-004](decisions.md#d-004-ledfx-owns-wled-output). It is not in
`requirements.txt` and is not managed by this application.

Requirements when phase 5 begins: LEDfx installed and running, reachable over HTTP,
with its own WLED device configuration already done. Useful for development: **LEDfx
runs without any physical WLED devices attached**, which makes it a safe manual
integration target.

---

## Hardware

None of the following is documented anywhere in the repository, and none of it is
required to develop against the current codebase:

| Hardware | Status |
| --- | --- |
| Custom DMX universe box | Opaque endpoint; IP, universe numbering, and transport mode all unverified |
| DMX fixtures | No patch recorded; no fixture model exists ([AF-H01](audit_findings.md#af-h01)) |
| WLED controllers and strips | Managed entirely by LEDfx |
| Audio interface | Undetermined; see above |
| Laser projector and DAC | **Not identified. Output must not be enabled** — [laser_and_haze_safety.md](laser_and_haze_safety.md) |

---

## Development versus production

There is currently no meaningful difference, because there is no runtime. The
distinction that should be established as output components are built:

| | Development | Production (basement) |
| --- | --- | --- |
| DMX sender | `NullDmxSender` (default) | Real sACN sender, opt-in via config |
| LEDfx client | Null or stub (default) | Real client against the LEDfx instance |
| Audio | Scripted beat source | Live device |
| Laser | Disabled, unimplemented | Disabled until [the prerequisites](laser_and_haze_safety.md#4-what-must-exist-before-output-is-enabled) are met |
| Data folder | Temp `root` per test | `%LOCALAPPDATA%\LightsApp` |

Real output is always the opt-in — see
[D-013](decisions.md#d-013-hardware-output-defaults-to-a-null-implementation).

---

## Known unsupported

- **Any laser output.** Not unsupported by omission — deliberately excluded.
- **Multi-user or concurrent operators.** Single-operator by design.
- **Remote or internet access.** LAN only; nothing listens on a socket.
- **Non-Windows deployment.** Not blocked by the code, but untested and not a target.
- **Multi-universe DMX.** Structurally impossible today — `Active_DMX_Channels` is a
  single 512-value list ([AF-H01](audit_findings.md#af-h01)).
- **Any scale beyond one room.** See [D-009](decisions.md#d-009-basement-deployment-is-the-immediate-target).

---

## Implicit assumptions, collected

Things a new contributor cannot learn from the repository without reading the source:

1. `backend/` must be on `sys.path`; there is no `__init__.py` and no packaging.
2. There is no entry point. Nothing is runnable. The code is a library.
3. Application data lives outside the repository, in a platform-specific folder.
4. `LIGHTSAPP_DATA_DIR` overrides that folder — the only test-isolation mechanism.
5. Constructing a `Library` has filesystem side effects, including writes.
6. `venv/` is expected at the repository root but is not present.
7. Python 3.12 is documented; 3.9+ is what the code actually needs.
8. There is no test command, because there are no tests.
