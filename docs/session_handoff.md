# Session Handoff

> **Historical (2026-03).** The sections below document the architecture-review
> session that created the initial `docs/` set at commit `691062e`.
>
> **Latest session (2026-08-13)** — operator server M1, symbolic DMX sender, and doc
> refresh for current status. Source added under `backend/server/`, `backend/main.py`,
> `frontend/index.html`, `backend/runtime/sender.py` (symbolic). **Next hardware work:**
> universe-box verification, then WS-4.4 `E131Transport`. Pick up from
> [Next steps](project_overview.md#next-steps-priority-order) in
> [project_overview.md](project_overview.md).
>
> **Prior session (2026-08-10)** — docs only; schema v4 / WS-3 refresh.
>
> For day-to-day status see [project_overview.md](project_overview.md) and
> [current_sprint.md](current_sprint.md).

Contributor handoff from the architecture-review session that created this
documentation set.

---

## Repository status

| | |
| --- | --- |
| **Branch** | `docs/show-control-architecture-baseline` |
| **Base** | `main` at `691062e` ("Add Wled iteration") |
| **Working tree at session start** | Clean |
| **Changes made** | `docs/` (13 new files) + one correction to `README.md` |
| **Source code changed** | None, other than the README correction |
| **Tracked files before** | 25 |

The branch contains documentation only. No behaviour changed, no dependency was
added, no packet was sent, and no hardware was touched.

---

## What was inspected

All 21 Python source files were read in full — the repository is small enough that
nothing was sampled. Also read: `README.md`, `AGENTS.md`, `requirements.txt`,
`.gitignore`, and the git history (5 commits).

Verified by search rather than assumed:

- Zero occurrences of `bpm`, `e131`, `sacn`, `ledfx`, `socket`, `udp`, `requests`,
  `httpx`, `thread`, `asyncio`, or `logging` anywhere in the source.
- `beat` appears only as `WLED_Preset_List.beats`; `sensitivity` only as a stored
  field.
- `WLED_Preset_List` appears **only in its own file** — it is unreachable code.
- No `__init__.py`, no `pyproject.toml`, no test files, no CI configuration, no
  `frontend/` directory.

---

## Documentation added

| File | Purpose |
| --- | --- |
| [project_overview.md](project_overview.md) | Entry point: purpose, maturity, terminology, current vs. target |
| [architecture.md](architecture.md) | Primary architecture doc: current graph, target components, 7 diagrams, debt, migration principles |
| [show_control_architecture.md](show_control_architecture.md) | Scene lifecycle, the four kinds of state, sequencing rules, concurrency hazards |
| [audio_reactivity_architecture.md](audio_reactivity_architecture.md) | Audio responsibilities and non-responsibilities; entirely Target |
| [fixture_and_transport_strategy.md](fixture_and_transport_strategy.md) | Device model, addressing, universe state, E1.31 transport, simulation |
| [wled_ledfx_architecture.md](wled_ledfx_architecture.md) | LEDfx ownership boundary, dedup, error handling, testing |
| [laser_and_haze_safety.md](laser_and_haze_safety.md) | ILDA status, safety boundary, prerequisites before any output |
| [audit_findings.md](audit_findings.md) | 21 findings with file/line evidence, plus 10 confirmed strengths |
| [decisions.md](decisions.md) | 20 ADRs; D-013/D-019 accepted for symbolic sender; D-020 proposed for E1.31 framing |
| [current_sprint.md](current_sprint.md) | 8 workstreams with goals, dependencies, acceptance criteria, status |
| [roadmap.md](roadmap.md) | 10 phases with scope, exit criteria, explicit non-goals, risks |
| [platform_support.md](platform_support.md) | OS, Python, import root, data folder, network, implicit assumptions |
| session_handoff.md | This file |

`README.md` was corrected: it listed a `frontend/` directory that does not exist,
and it now links to `docs/`. That is the only source-adjacent change.

---

## Most important findings

Full detail in [audit_findings.md](audit_findings.md).

1. **[AF-H01] No fixture identity — DMX addresses are derived positionally.**
   [`runtime/active.py:37-49`](../backend/runtime/active.py#L37-L49) packs device
   states contiguously by `order`, so a device's start address is the running sum of
   the ones before it. No fixture, universe, or start-address model exists anywhere.
   Consequences: no cross-look device identity, the patch is restated per look,
   address gaps are inexpressible, one universe only. **This is the root blocker.**

2. **[AF-H02] Beat duration is absent from the model.** `DMX_Preset_List` has no beat
   field at all; `WLED_Preset_List.beats` is a single scalar on the list rather than
   per entry. The core feature cannot be built on the current schema.

3. **[AF-H03] The WLED path is unbuildable.** `WLED_Preset_List` is registered
   nowhere and cannot be loaded, saved, or referenced. `WLED_Preset` has only a UUID
   and no LEDfx identifier. `Preset.wled_preset_id` points at a single preset while
   the DMX side points at a list — so WLED cannot be sequenced at all.

4. **[AF-H05] No tests.** The storage layer contains the subtlest code in the
   repository — recursive cascade delete with cycle guarding, reachability-based
   orphan pruning, atomic writes, corrupt-file quarantine — and none of it is
   verified. Every change above touches it.

5. **[AF-H04] Force-delete has a large blast radius.** Following the `REFERENCES`
   table, `delete(WLED_PRESETS, id, force=True)` cascades through `Preset` to
   `Scene`, and deleting an `ILDA_Frame` unlinks the user's `.ild` file. Guarded by
   default, but there is no dry-run.

**Counterweight:** the storage layer is genuinely well built. The declarative
`REFERENCES` table driving four behaviours from one declaration, crash-safe atomic
writes, corrupt-file quarantine instead of overwrite, zip-slip protection, ILDA
id-traversal validation, and the explicit never-persisted marking on runtime state
are all better than the project's stage would suggest. See
[Confirmed strengths](audit_findings.md#confirmed-strengths). Protect these when
changing the schema.

---

## Immediate next implementation task

**Add pytest and a storage test suite** ([WS-6.1](current_sprint.md#ws-6--hardware-independent-testing)),
then **introduce the `Fixture` collection**
([WS-2.1](current_sprint.md#ws-2--scene-and-preset-model)).

In that order, deliberately: the fixture change requires the first schema migration
ever written, against an untested migration framework, touching the least-verified
code in the repository. Tests first is not ceremony here.

Both are scoped in [current_sprint.md](current_sprint.md) with acceptance criteria.

---

## Validation commands

Run from the repository root. These were the checks performed this session:

```bash
# Syntax-check every source file (needs no dependencies)
cd backend && python -m compileall -q .
# → exit 0, no output

# Confirm WLED_Preset_List is unreachable
grep -rn "WLED_Preset_List\|wled_preset_list" --include=*.py .
# → one match, its own definition

# Confirm no runtime/transport/audio code exists
grep -rni "bpm\|e131\|sacn\|ledfx\|socket\|udp\|requests\|httpx\|thread\|asyncio\|logging" --include=*.py .
# → no matches

# Review the diff
git diff main --stat
```

**Not run, and why:** the test suite (none exists), a full import check
(`pydantic` and `platformdirs` are not installed in the ambient environment —
`python -c "import pydantic"` fails with `ModuleNotFoundError`), and any
network or hardware operation (out of scope and explicitly prohibited for this
task). No test-pass claim is made anywhere in this documentation set.

To set up an environment for real work:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\backend"
```

Note that `requirements.txt` currently pins `typing==3.7.4.3`, a Python 3.4–3.6
backport with no purpose here — see [AF-L02](audit_findings.md#af-l02).

---

## Known blockers

| Blocker | Blocks | Notes |
| --- | --- | --- |
| DMX universe box behaviour unverified | E1.31 transport (WS-4.3, WS-4.4) | Universe numbering, unicast vs. multicast, and what it does when packets stop are all unknown. No documentation exists in the repository. **Must be measured, not assumed.** |
| LEDfx preset identifier form unknown | The WLED schema change (WS-2.3) | Which LEDfx entity, what identifier form, and whether it is stable across restarts. [D-018](decisions.md#d-018-ledfx-preset-identifier-form) |
| Sensitivity semantics undefined | Any audio work | Range, direction, and the relationship to `AudioConfig.default_sensitivity`. [AF-M02](audit_findings.md#af-m02) |
| Audio event delivery undecided | Threading design | Callback vs. queue. [D-016](decisions.md#d-016-audio-event-delivery-mechanism) |
| No Python 3.12 or venv locally | Running anything | `python --version` → 3.11.9; `py -3.12` not found; no `venv/`. The code needs only 3.9+. [AF-D03](audit_findings.md#af-d03) |
| New dependencies needed | WS-4.4, WS-5.2, WS-6.1 | sACN library, HTTP client, pytest. None added this session. |

---

## Read these first

For a contributor picking this up cold, in order:

1. [project_overview.md](project_overview.md) — what this is and what state it is in.
2. [architecture.md](architecture.md) — §2 (current) before §3 (target).
3. [audit_findings.md](audit_findings.md) — the High section and the strengths.
4. [current_sprint.md](current_sprint.md) — WS-6.1 and WS-2.1.

Then the source, in this order — it follows the dependency direction:

1. [`backend/storage/records.py`](../backend/storage/records.py) — the schema and the
   `REFERENCES` table. Everything else follows from this file.
2. [`backend/storage/library.py`](../backend/storage/library.py) — the object graph
   and all CRUD/integrity behaviour.
3. [`backend/runtime/active.py`](../backend/runtime/active.py) — 82 lines, and the
   only runtime code that exists.
4. [`backend/storage/json_store.py`](../backend/storage/json_store.py) — atomic
   writes and quarantine.

Everything else is small and follows readily from those four.
