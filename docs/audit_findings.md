# Lights App Repository Audit — v2

**Audit commit:** `45dbf9b0b2bf112785cefa407f0e40a675deb6ce` ("chore: ignore local development environment")
**Audit baseline includes:** `ddcadf8` (DMX_Device fixture architecture) and `7ece72d` (WLED preset-list correction)
**Audit branch:** `docs/fable-v2-repository-audit` (content identical to `main` plus this document)
**Audit date:** 2026-08-10 (updated the same day for `ddcadf8`)
**Auditor:** Claude (Fable 5), full-repository read — every backend source file (31), every test (12 files, 84 cases at last update), all 16 docs (including the new `docs/fixtures/` set), `README.md`, `AGENTS.md`, `requirements.txt`, `pytest.ini`, `.gitignore`. Test suite executed and passing at audit time (50 cases).

This document supersedes Audit v1 (written at commit `691062e`) and updates the
first Audit v2 pass (written before `ddcadf8`). Every v1 finding is reconciled in
[§ Previous Audit Reconciliation](#previous-audit-reconciliation); open v1 findings
keep their `AF-*` IDs and Audit-v2 findings carry `AF2-*` IDs.

> **Updates since audit (Aug 2026).** The following findings are partially or fully
> addressed on current `main`: **AF-H03** (WLED list registered;
> `Preset.wled_preset_list_id`; `WLED_Preset.id` = scene name), **AF-H05** (84-test
> suite including storage, sequencing, and outputs), **AF-M07** (config split documented),
> **AF-M08** (logging), **AF-L02** (requirements cleaned), **AF-H01** (`DMX_Device`
> collection and address-based resolution). **AF-H02** is now partly resolved: both cue
> lists carry a `beats` scalar per list (schema v3 → 4), which unblocked sequencing;
> per-*entry* beats remain open. **AF-M02** and **AF-M06** are resolved, **AF-M05**
> partly. **WS-3** is built (`CueSequencer`, `SceneController`, `BeatSource` protocol,
> `DmxOutput`/`WledOutput`). Multi-universe output remains open, as does WS-4 (E1.31
> transport). No app entry point wires any of it yet.

Severity reflects impact **on this project at its current stage** — a pre-runtime
repository with no deployment, no users, and no hardware output. Nothing here is
rated Critical, because nothing in the repository can currently cause data loss,
unsafe output, or a security exposure. Inflating severity would obscure the two or
three findings that actually matter.

| ID | Severity | Finding | Blocks now? |
| --- | --- | --- | --- |
| [AF-H01](#af-h01) | High | No fixture identity; DMX addresses derived positionally | ~~Yes~~ **Resolved** |
| [AF-H02](#af-h02) | High | Beat duration is absent from the persisted model | ~~Yes~~ **Partly resolved** |
| [AF-H03](#af-h03) | High | `WLED_Preset_List` unreachable; `WLED_Preset` carries no LEDfx id | ~~Yes~~ **Resolved** |
| [AF-H04](#af-h04) | High | Force-delete cascade can silently destroy Scenes and user files | No |
| [AF-H05](#af-h05) | High | No tests of any kind | ~~Yes~~ **Resolved** (storage + runtime) |
| [AF-M01](#af-m01) | Medium | DMX channel values are never range-checked or clamped | No |
| [AF-M02](#af-m02) | Medium | `sensitivity` and other numeric fields are unbounded | ~~No~~ **Resolved** |
| [AF-M03](#af-m03) | Medium | Runtime state is module-global with no concurrency story | No |
| [AF-M04](#af-m04) | Medium | Model/record duplication requires four-place edits | No |
| [AF-M05](#af-m05) | Medium | `Library.load()` writes to disk | ~~No~~ **Partly resolved** |
| [AF-M06](#af-m06) | Medium | `DMXConfig.universe` defaults to 0, not a valid sACN universe | ~~No~~ **Resolved** |
| [AF-M07](#af-m07) | Medium | `backend/config/config.py` is an empty file duplicating a real module | ~~No~~ **Resolved** |
| [AF-M08](#af-m08) | Medium | No logging anywhere in the codebase | ~~No~~ **Resolved** |
| [AF-L01](#af-l01) | Low | `refresh_hz` default of 120 exceeds DMX512 physical capability | No |
| [AF-L02](#af-l02) | Low | `requirements.txt` pins a deprecated backport and transitive deps | ~~No~~ **Resolved** |
| [AF-L03](#af-l03) | Low | Session state (`ui.last_scene_id`) stored in the config file | No |
| [AF-L04](#af-l04) | Low | `stored_version` silently coerces a non-integer version | No |
| [AF-L05](#af-l05) | Low | `import_ild` bypasses `Library.add()` | No |
| [AF-D01](#af-d01) | Doc (resolved) | README frontend reference corrected | No |
| [AF-D02](#af-d02) | Doc | No documented import root or way to run anything | No |
| [AF-D03](#af-d03) | Doc | Setup instructions reference a Python version not present locally | No |

---

## Executive Summary

Since the previous audit pass, upstream commit `ddcadf8` landed a **DMX fixture
architecture** — a persisted `DMX_Device` collection (name, model, mode, universe,
start_address, channel_count), `DMX_Device_Preset.device_id` replacing positional
`order`, patch-based channel resolution with overlap and out-of-universe
rejection, a schema v2→v3 migration, a rig seeding utility, per-model channel
documentation, and 18 new tests. This audit examined that implementation
independently and concludes it is **correct and complete for the current one-
universe installation**. The long-standing fixture-identity blocker **AF-H01 is
RESOLVED** — with one deliberate, clearly-marked limitation: `DMX_Device.universe`
is stored and validated, but the runtime buffers only universe 1 and *rejects*
(never silently drops) anything else. For a one-box basement rig, that is a sound
forward-compatible choice, not a defect.

The earlier WLED conclusions stand: the `7ece72d` correction remains complete and
correct (`ddcadf8` did not touch the WLED or LEDfx code paths, and the WLED tests
still pass unchanged at HEAD). `DMXConfig` was also repaired: universe now
defaults to a valid 1, and `host`/`port`/`priority` were recovered from the
previous app's config — **AF-M06 is RESOLVED**, though none of it is verified
against the physical universe box yet.

**The blocker list has therefore changed.** The top structural gap is now **per-entry
beat duration (AF-H02)** — both cue lists carry one `beats` scalar per list (schema
v4), and sequencers are built against that, but variable hold times per cue entry
are still unrepresentable. Second is the **LEDfx sync concurrency defect (AF2-H01)**:
the background thread still mutates and saves the whole `Library` unsynchronized, and
must be restructured before any live process shares that library. Third is the
absence of an **app entry point and transports** — the show-control core exists as
library code, but nothing subscribes beats, sends DMX, or runs LEDfx sync in one
process.

The shortest safe path to a first hardware-driven show is now:
**LEDfx regression protection (tests + thread hygiene) → entry point wiring beat
source → controller → null/recording DMX sender → E1.31 via the `sacn` library →
hardware bring-up.** Per-entry cue schema can wait until a real show needs it.
Fixture identity no longer appears on the roadmap as work to do — only as work to
protect. Details in
[§ Recommended Implementation Order](#recommended-implementation-order).

---

## Repository Ground Truth

| | |
| --- | --- |
| Branch | `docs/fable-v2-repository-audit` |
| HEAD | `45dbf9b0b2bf112785cefa407f0e40a675deb6ce` |
| Key commits in baseline | `ddcadf8` (DMX_Device architecture, schema v3, seeding, fixture docs, 18 tests), `7ece72d` (WLED list correction, schema v2) |
| Working tree | Clean at audit start (this document is the only change) |
| Python (documented) | 3.12+ (README) |
| Python (present) | `.venv/` at repo root, **Python 3.12.10**; README/AGENTS still say `venv/` ([AF2-L03](#af2-l03)) |
| Dependencies | `httpx==0.28.1`, `platformdirs==4.11.0`, `pydantic==2.13.4`, `pytest==9.1.1` — all direct, all used |
| Test suite | **84 tests, all passing** (`.venv\Scripts\python.exe -m pytest`, ~3.5 s) |
| Schema version | **4** (`storage/migrations.py`), with registered steps 1→2 (WLED lists), 2→3 (DMX devices), 3→4 (cue-list beats, sensitivity clamp) |
| CI | None |
| Entry points | Still no app entry point. `backend/seed_devices.py` is a one-shot setup utility; show-control modules are library code only |
| Source inventory | `backend/`: 12 models, 8 storage modules, 4 runtime modules, 1 audio module, 3 ledfx modules, 1 config module, `logging_setup.py`, `seed_devices.py`. `tests/`: 12 files. `docs/`: 13 architecture docs + 3 fixture docs |

Repository-wide searches re-run at HEAD (excluding `.venv/`):

- `order` on device presets: **gone from the live model/record**; remains only in
  the v2→v3 migration step, its tests, and historical doc text — all intentional.
- `wled_preset_id` (non-list form): still only migration code/tests/historical
  docs. Zero stale uses.
- `threading` / locks: only `ledfx/scene_sync.py`. `socket`/`sacn`/`asyncio`:
  zero — no transport code exists.
- LEDfx modules (`backend/ledfx/`): **byte-identical since the previous audit
  pass** — the WLED/LEDfx conclusions below are preserved, not re-derived.

---

## Overall Assessment

The repository has crossed its most important structural threshold: **the DMX
data model now describes the physical rig truthfully.** A device is a stable,
named, persisted object with an explicit patch address; looks reference devices
by id and never restate the patch; re-addressing a fixture is a one-record edit
that every look picks up; gaps are expressible; collisions are errors instead of
silent overwrites. The change was threaded through the declarative `REFERENCES`
graph, the record schemas, both converters, the migration framework, orphan-prune
roots, the conftest graph, and the docs — the same full-thickness discipline the
WLED correction showed, and further evidence the storage design carries schema
change well.

What remains is no longer *wrong structure* but *missing wiring and transports*:
per-entry cue shape (deferred — list-level `beats` unblocked sequencing), an app
entry point, E1.31 output, and real beat detection. The LEDfx adapter is still a
good HTTP boundary with a bad library-side habit (AF2-H01). Validation of channel
*values* (0–255) is still absent even though addresses are now bounded.

---

## Current End-to-End Capability

What actually executes today, end to end:

1. `Library.open(root)` → layout, migration to schema v4 (snapshot first),
   ten collections loaded, integrity checked; ILDA folder sync is opt-in.
2. `python backend/seed_devices.py` → seeds the two-fixture basement patch
   (GigBAR 2 at 1–23, Keobin bar at 25–42, universe 1) idempotently, and prints
   the patch table.
3. `SceneController.activate(scene_id)` → resolves scene → preset → both cue lists,
   applies cue 0 to the DMX universe buffer and LEDfx (via injected outputs).
4. `SceneController.on_beat()` → advances both sequencers independently; changed
   cues go to `DmxOutput` and `WledOutput`.
5. `ManualBeatSource` → protocol + scripted beats for tests; no real detector.
6. If `ledfx.enabled` were true in a future entry point: the LEDfx client/sync
   stack could poll scenes — still nothing calls `build_ledfx_stack()` today.

Nothing transmits the universe buffer, nothing runs the controller from a live
process, and nothing captures audio. The show-control *core* is implemented and
tested; the *application* around it is not.

---

## Intended End-to-End Architecture

Unchanged from the previous assessment: the documented target (operator → Scene
→ {sensitivity → audio engine → beats; Preset → DMX cue list + WLED cue list;
ILDA frame list} → shared sequencer → E1.31 box / LEDfx) remains the right
shape, and the repository is converging on it. The cue-list *entry* shape
(per-entry beats) is deferred; list-level `beats` and the sequencing core are
in place. What remains absent is absent at the integration layer, not in the
core logic.

---

## DMX Fixture Architecture Assessment (`ddcadf8`)

Audited independently against the code and tests at HEAD; not taken on trust.

### DMX_Device model — correct

[models/DMX_Device.py](../backend/models/DMX_Device.py): `id` (uuid hex default),
`name` (required), `model`/`mode` (optional; `model` links to the channel table in
`docs/fixtures/`), `universe: int = Field(default=1, ge=1)`,
`start_address: Field(ge=1, le=512)`, `channel_count: Field(ge=1, le=512)`, and a
computed `end_address` property. Bounds are tested
(`test_device_address_bounds_rejected`).

The one combination the model does **not** reject at validation time is
`start_address + channel_count − 1 > 512` (e.g. start 510, count 8 — each field
individually valid). That case is caught at runtime resolution with a clear
error ([active.py:50-54](../backend/runtime/active.py#L50-L54)) and is tested
(`test_build_channels_rejects_device_past_universe_end`). **Sufficient for now**
— the failure is loud, early (at look resolution/scene activation), and
correctly attributed. A `model_validator` catching it at construction would be a
small hardening win; noted under [AF2-L05](#af2-l05), not required.

### DMX_Device_Preset — correct

[models/DMX_Device_Preset.py](../backend/models/DMX_Device_Preset.py):
`device_id` + `channel_values`, with the docstring stating the right invariant
("a look never restates the patch"). Reference integrity is enforced through
`REFERENCES` (`device_id → dmx_devices`,
[records.py:124](../backend/storage/records.py#L124)) — adding a preset with a
missing device raises `DanglingReferenceError` (tested), and on-disk dangling
references fail the load-time integrity check like every other edge.

Length semantics: values are truncated to `device.channel_count` and
zero-padded when short, at resolution time (tested both ways). Value *range*
(0–255) is still unvalidated — AF-M01 remains open.

`channel_values: List[int] = []` as a mutable default: **functionally safe** —
pydantic v2 deep-copies non-factory defaults per instance, so instances do not
share the list. `Field(default_factory=list)` would be more conventional; this
is a style note only, deliberately not raised as a finding.

### Storage integration — complete

Verified point by point: registered in `RECORD_TYPES`, `MODEL_TYPES`,
`COLLECTION_ORDER` (correct leaves-first position: `dmx_devices` before
`dmx_device_presets`), `REFERENCES`, Library maps, and both converters
(model/record shapes match field-for-field). `DMX_DEVICES` was added to
`ROOT_COLLECTIONS` with an explicit rationale comment — the patch survives orphan
pruning even when no look uses a device yet (tested,
`test_unused_device_survives_pruning`). Delete semantics are right: deleting a
referenced device refuses without force; force-delete cascades to its device
presets but correctly *unlinks* from looks rather than destroying them (tested).
Round-trip persistence tested.

One asymmetry worth noting: `dmx_devices` got the root-collection treatment, but
`wled_presets` — which has the same externally-owned-mirror character (rows come
from LEDfx, not from the reference graph) — still did not
([AF2-M02](#af2-m02) remains open).

### Runtime resolution (`build_channels`) — correct, one edge case

[active.py:28-70](../backend/runtime/active.py#L28-L70) now resolves each device
preset → device → explicit `start_address`. Verified against the audit
checklist: explicit addresses used (order of the look's list no longer affects
addressing — placement depends only on the patch); gaps stay zero (tested);
overlapping devices raise with both ids and the contested channel (tested);
universe ≠ 1 raises explicitly rather than dropping (tested); past-512 raises
(tested); padding/truncation as above (tested); the buffer is rebuilt from zeros
on every call, so resolution is deterministic and no state leaks between looks;
empty look yields an all-zero buffer (reasonable — the "no presets in the cue
list" error fires one level up in `active_dmx_preset_id`). Error type is
`StorageError` throughout with well-formed messages naming the offending ids.

**Edge case found:** the overlap guard skips conflicts where both claims come
from the *same* device (`holder != device.id`,
[active.py:59](../backend/runtime/active.py#L59)). Consequently a look that
contains **two device presets for the same device** resolves silently, last
entry winning. Deterministic, no crash — but it means an ambiguous look renders
without complaint. Recorded as [AF2-L06](#af2-l06) (Low).

Also noted: overlap and universe checks run only at resolution time. Two devices
patched to overlapping addresses are storable and only fail when a look using
both is resolved — i.e. at scene activation. The error is clear and immediate,
and per-model validation cannot express cross-object constraints, so this is
acceptable; a Library-level patch lint on save would move the failure from
show-time to edit-time ([AF2-L05](#af2-l05)).

### Multi-universe semantics — deliberate near-term limitation, correctly handled

`SUPPORTED_UNIVERSE = 1` with an explanatory comment
([active.py:18-20](../backend/runtime/active.py#L18-L20)); devices carry a
persisted, validated `universe`; anything ≠ 1 **fails loudly** at resolution
(tested). This is the right forward-compatible shape for a one-box installation:
the patch records reality now, nothing is silently dropped, and adding
per-universe buffers later is an additive runtime change with no schema impact.
**Not a design inconsistency and not a blocker.** Do not build multi-universe
buffering until the installation actually has a second universe.

### Rig seeding (`seed_devices.py`) — appropriate as a setup utility

Idempotent by device **name** (skip if present); never modifies existing devices,
so operator re-patching survives re-runs (docstring states this contract);
repeated runs are safe (tested); `main()` is an explicit one-shot CLI against
the real data folder, which is the right home for this — it is not runtime
behavior and nothing imports it at runtime. The hard-coded `RIG` table matches
the documented patch, keeps the fixtures' physically dialled addresses (1 and 25
from the old 24-wide layout) while taking true channel counts from the manuals —
the comment explains exactly this reasoning. Seeded addresses verified
non-overlapping end-to-end through `build_channels` (tested, including the spare
channel 24).

Two mild caveats, neither worth code changes now: matching by name means
*renaming* a seeded device and re-running the script re-adds it under the RIG
name (creating an overlapping duplicate that would only surface if both were
used in one look); and the script's docstring says `venv\Scripts\python.exe`
while the actual environment is `.venv` ([AF2-L03](#af2-l03)).

### Fixture documentation — consistent with code and seed

[docs/fixtures/README.md](fixtures/README.md) index, patch table, and file-format
convention; [chauvet_gigbar_2.md](fixtures/chauvet_gigbar_2.md) (23CH, full
channel + value tables, hardware constraints noted);
[keobin_light_bar.md](fixtures/keobin_light_bar.md) (18CH, transliterated).
Cross-checked: `model` identifiers, modes, and channel counts match
`seed_devices.RIG` exactly; the patch table (1–23, 25–42, spare 24, universe 1)
matches the seed and the seed test; channel numbering is documented as 1-based
relative to `start_address`, matching the runtime's `start_address − 1` offset.
The tables are detailed enough to author real looks against.

**Hardware facts still requiring physical verification** (the docs themselves
flag these — they are transcription/recollection, not measurements):

- Keobin channels 15/16 red-vs-green ambiguity (explicit ⚠ caveat with a
  one-minute verification procedure).
- GigBAR "max 3 of 4 colours" and "ch 21/22 mutually exclusive" behavior as the
  hardware actually enforces it.
- That both fixtures are really dialled to 1 and 25 in the stated modes.
- Everything in `DMXConfig` (`host`, `port`, `priority`, universe numbering) —
  recovered from the old app's config, explicitly documented as *not tested*.

### Test coverage for the change — good

18 new tests: 11 in `test_dmx_devices.py` (round-trip, bounds, dangling
reference, prune survival, delete/cascade, gaps, padding/truncation, overlap,
past-end, second universe), 4 in `test_seed_devices.py` (documented patch,
idempotency, reload survival, non-overlap through `build_channels`), 3 in
`test_migrations.py` (device synthesis, widest-count-wins, malformed rejection).
The previously-flagged `build_channels` coverage gap is closed.

**Verdict: `ddcadf8` resolves AF-H01.** The implementation is correct for the
target installation, the migration is safe (below), and the deliberate
single-universe limit is properly enforced rather than silently assumed.

---

## Recent WLED Architecture Correction Assessment

**Preserved from the previous audit pass — re-validated, not re-derived.**
`ddcadf8` did not modify `backend/ledfx/`, the WLED models, or the WLED edges in
`records.py`; the WLED round-trip, integrity, delete/cascade, and v1→v2
migration tests all still pass at HEAD (within the 50). The prior conclusion
stands: the `7ece72d` correction is **complete and correct** across all 13
integration points checked (instantiate, add, reference, persist, load, reload,
integrity, referrers, delete, cascade, prune, archive, migrate). AF-H03 remains
**RESOLVED**. The WLED list schema is still not *sequenceable* (list-level
scalar `beats = 0`) — that is AF-H02, the top blocker below.

---

## Top Blocking Findings

1. **AF-H02 (v1, PARTLY RESOLVED) — per-entry beat duration still open.** Both cue
   lists now carry one `beats` scalar per list (schema v4, `ge=1`); sequencers are
   built and tested against that. Variable hold times per cue entry remain
   unrepresentable — deferred until a real show needs them.
2. **AF2-H01 (OPEN) — LEDfx sync thread mutates and saves the whole Library
   unsynchronized.** Must be restructured before any live process shares the
   `Library`. Unchanged since the previous pass.
3. **Integration absence** — no entry point, no E1.31 sender, no real beat
   detector. The show-control core (`SceneController`, `CueSequencer`, outputs,
   `BeatSource` protocol) is library code only.

~~Fixture identity (AF-H01)~~ — resolved by `ddcadf8`; removed from this list.

Nothing is rated Critical: no implemented behavior can cause physical harm,
catastrophic data loss (atomic writes, pre-migration snapshots, guarded and
logged cascade deletes), or security exposure (nothing listens; zip import is
traversal-hardened).

---

## Findings Summary

Audit-v2 findings only; open v1 findings are tracked in
[§ Previous Audit Reconciliation](#previous-audit-reconciliation).

| ID | Severity | Area | Finding | Blocks | Timing |
| --- | --- | --- | --- | --- | --- |
| [AF2-H01](#af2-h01) | High | Concurrency / persistence | LEDfx sync thread mutates and saves the whole Library without synchronization | Runtime orchestration, audio integration | Before runtime wiring |
| [AF2-M01](#af2-m01) | Medium | LEDfx sync | Non-`LedFxError` exceptions kill the sync thread silently; no supervision or health surface | Hardware deployment | Before hardware deployment |
| [AF2-M02](#af2-m02) | Medium | Storage semantics | `prune_orphans` deletes LEDfx-mirrored `WLED_Preset` rows not yet referenced by a cue list (`dmx_devices` got root-collection protection in `ddcadf8`; `wled_presets` did not) | Nothing currently | Before UI exposes pruning |
| [AF2-M03](#af2-m03) | Medium | Testing | LEDfx client and sync still have zero coverage (the DMX-resolution half of this finding was closed by `ddcadf8`) | Confidence in LEDfx wiring | Fix now |
| [AF2-M04](#af2-m04) | Medium | Concurrency | `LedFxClient` internal state unsynchronized but will be shared by sync thread and show loop | Runtime orchestration | Before runtime wiring |
| [AF2-L01](#af2-l01) | Low | LEDfx identity | Duplicate LEDfx scene names collapse silently (name-keyed map, last slug wins) | Nothing | Can defer |
| [AF2-L02](#af2-l02) | Low | Migration | v1→v2: a preset carrying both old and new WLED fields is re-wrapped, discarding its existing list reference | Nothing | Can defer |
| [AF2-L03](#af2-l03) | Low | Docs / environment | README/AGENTS/seed docstring say `venv/`; actual environment is `.venv/` (Python 3.12.10) | Nothing | Can defer |
| [AF2-L04](#af2-l04) | Low | Migration | v1→v2: a dangling old WLED id migrates "successfully" and only fails at next load, after the version bump | Nothing | Can defer |
| [AF2-L05](#af2-l05) | Low | DMX validation | Patch validity (end past 512; device overlap) is enforced at resolution time only — an invalid patch is storable and fails at scene activation; on-disk out-of-bounds device records surface as raw `ValidationError`, not `StorageError` | Nothing currently | Before UI |
| [AF2-L06](#af2-l06) | Low | DMX resolution | Two device presets for the *same* device in one look resolve silently, last entry winning | Nothing currently | Can defer |

---

## Critical Findings

None.

---

## High Findings

### AF2-H01
**Severity:** High · **Area:** Concurrency / persistence · **Confidence:** High

**Finding.** `LedFxSceneSync.refresh_once()` runs on a daemon thread and calls
`Library.add()` and `Library.save()` against a `Library` that has no locking of
any kind; `save()` writes **every** collection plus `config.json`.

**Evidence.** [scene_sync.py:67-84](../backend/ledfx/scene_sync.py#L67-L84) —
`with self._lock:` guards only the sync object's own reentrancy, not the
`Library`. [library.py:236-240](../backend/storage/library.py#L236-L240) —
`save()` runs `check_integrity()` then rewrites all ten collections and the
config. Unchanged by `ddcadf8`.

**Why it matters.** (1) *Data race* — the sync thread iterating the library maps
during `save()` while another thread mutates a collection raises `RuntimeError`
mid-save or persists a half-edited graph. (2) *Unintended persistence* — a
background poll that discovers one new LEDfx scene commits every unsaved
in-memory edit to disk.

**Blocks.** Runtime orchestration; audio integration; safe enabling of
`ledfx.enabled` in a running app.

**Recommended action.** The sync loop should not touch the `Library` at all:
publish discovered scene names to the library's owner (future ShowController /
main thread) via a thread-safe handoff, and let the owner upsert and persist
**only** `wled_presets`. Interim alternative: a `Library`-level `RLock` shared by
all mutators. The first option matches the project's single-owner philosophy.

**Timing.** Before runtime wiring. Not urgent while `ledfx.enabled` defaults
false and no entry point exists.

---

## Medium Findings

### AF2-M01
**Severity:** Medium · **Area:** LEDfx sync · **Confidence:** High

`refresh_once()` catches only `LedFxError`; a `StorageError`/`IntegrityError`
from `add()`/`save()` or any unexpected exception propagates out of `_run()` and
kills the daemon thread silently — no log, no flag, no restart
([scene_sync.py:67-91](../backend/ledfx/scene_sync.py#L67-L91)). During a show,
scene sync would just stop, invisibly. **Fix:** broad
`except Exception: logger.exception(...)` in the loop body plus a
`last_error`/health property. Trivial; fold into the AF2-H01 restructure.
**Timing:** before hardware deployment.

### AF2-M02
**Severity:** Medium · **Area:** Storage semantics · **Confidence:** High

`ROOT_COLLECTIONS` is now `(SCENES, ILDA_FRAMES, DMX_DEVICES)`
([records.py:109](../backend/storage/records.py#L109)) — `ddcadf8` correctly
recognized that externally-anchored collections must survive pruning, and even
documented the rationale. `wled_presets` has the same character (rows mirror
LEDfx's scene list) but was not included, so `prune_orphans()` still deletes any
LEDfx-mirrored preset not yet referenced by a cue list; sync re-adds it up to
25 s later, or never if LEDfx is offline/disabled. **Fix:** add `WLED_PRESETS`
to `ROOT_COLLECTIONS` with the same style of comment, plus a test — exactly the
treatment `dmx_devices` just received. **Timing:** before any UI exposes
pruning.

### AF2-M03
**Severity:** Medium · **Area:** Testing · **Confidence:** High

The previous pass flagged three untested implemented modules. `ddcadf8` closed
one: `runtime/active.py` is now well covered (gaps, padding, truncation,
overlap, past-end, universe rejection). Still at zero coverage:
`ledfx/client.py` (response parsing, slug resolution, activate dedup,
reachability transitions — all pure and cheap to test with
`httpx.MockTransport`) and `ledfx/scene_sync.py` (upsert, failure isolation).
This is the code that will run mid-show. **Fix:** ~8 tests. **Timing:** fix now
(P0); no hardware needed.

### AF2-M04
**Severity:** Medium · **Area:** Concurrency · **Confidence:** Medium

`LedFxClient`'s mutable state (`_name_to_slug`, `_active_name`, `_reachable`,
`_logged_unreachable`) is unsynchronized
([client.py:62-65](../backend/ledfx/client.py#L62-L65)); the intended design has
the show loop calling `activate_scene()` while the sync thread calls
`list_scenes()` on the same instance. The dedup check-then-set across an HTTP
call can interleave (reconnect re-apply vs. cue-change activation), leaving the
wrong scene active. **Fix:** route all LEDfx calls through the single
show-control thread (preferred, consistent with AF2-H01) or add a small internal
lock; state the threading contract in the client docstring. **Timing:** before
runtime wiring.

---

## Low Findings

### AF2-L01
**Severity:** Low · **Area:** LEDfx identity

`list_scenes()` builds `name → slug` last-wins
([client.py:92-104](../backend/ledfx/client.py#L92-L104)); two LEDfx scenes with
the same display name collapse to one `WLED_Preset` and activation targets the
last-enumerated slug. Avoidable by convention for one operator; log a warning on
duplicates during sync and note the convention in
[wled_ledfx_architecture.md](wled_ledfx_architecture.md). Can defer.

### AF2-L02
**Severity:** Low · **Area:** Migration (v1→v2)

The skip clause requires the new field present **and** the old field absent
([migrations.py:103](../backend/storage/migrations.py#L103)); an item carrying
both is re-wrapped and its existing `wled_preset_list_id` silently replaced. No
realistic path produces such a record; the pre-migration snapshot bounds the
damage. Lesson applied forward: the v2→v3 step keys on presence of `device_id`
alone, which is the better "new field wins" shape. Can defer.

### AF2-L03
**Severity:** Low · **Area:** Docs / environment

README, AGENTS.md, and the `seed_devices.py` docstring instruct
`venv\Scripts\python.exe`; the actual environment is `.venv/` (Python 3.12.10,
gitignored). Cosmetic, but agents follow these paths literally. Supersedes v1's
AF-D03. Can defer.

### AF2-L04
**Severity:** Low · **Area:** Migration (v1→v2)

The WLED wrap does not check the old id exists in `wled_presets`; a dangling
reference migrates, the version advances, and the failure surfaces as
`DanglingReferenceError` on the next load — fail-closed but attributed to the
graph rather than the migration, with recovery via the (correctly taken)
snapshot. The v2→v3 step has no analogous hazard (it *creates* the referenced
devices). Optional hardening for future steps. Can defer.

### AF2-L05
**Severity:** Low · **Area:** DMX validation timing · **Confidence:** High

Two patch-validity rules are enforced only at resolution time, not at
edit/save time: a device whose block runs past slot 512
(`start 510, count 8` — each field individually valid) and two devices patched
to overlapping addresses are both **storable**, failing only when a look using
them is resolved — i.e. at scene activation, mid-session. The errors are loud
and well-attributed (tested), so this is acceptable now. Additionally, an
out-of-bounds device record edited *on disk* fails load via a raw pydantic
`ValidationError` from `_from_record` (model construction) rather than a
`StorageError` — fail-closed, rough messaging. **Fix when a UI exists:** a
Library-level patch lint on `add`/`save` (end ≤ 512; pairwise overlap per
universe), moving failure to edit-time; optionally a `model_validator` for the
end-address rule. **Timing:** before UI.

### AF2-L06
**Severity:** Low · **Area:** DMX resolution · **Confidence:** High

The overlap guard exempts same-device claims
(`holder != device.id`, [active.py:59](../backend/runtime/active.py#L59)), so a
look containing two device presets for the **same** device resolves silently
with the last entry's values. Deterministic, no crash — but an ambiguous look
renders without complaint where every other ambiguity in `build_channels` is an
error. **Fix:** track claimed device ids per look and raise on a duplicate
`device_id`, or document last-wins as intended. One conditional plus a test.
Can defer.

---

## Architecture Assessment

### Scene model

**Appropriate — CURRENT.** Unchanged: `Scene` holds exactly `preset_id`,
`ilda_frame_list_id`, `sensitivity` — right references, right level, no
networking or DSP. Remaining defect is only the unbounded `sensitivity` float
(AF-M02).

### Lighting preset hierarchy

**Correct — CURRENT.** `Scene → Preset → {DMX_Preset_List, WLED_Preset_List}`,
consistent across models, records, converters, `REFERENCES`, and tests. The DMX
side now continues down correctly:
`DMX_Preset_List → DMX_Preset → DMX_Device_Preset → DMX_Device`.

### DMX fixture and patch model

**RESOLVED — CURRENT.** See the
[dedicated assessment](#dmx-fixture-architecture-assessment-ddcadf8). The
minimum correct model recommended by the previous two audits is now implemented
(as `DMX_Device` rather than `Fixture` — a naming choice matching the `DMX_*`
family, recorded in the docs). Remaining DMX risks, all small: channel-value
range validation (AF-M01), resolution-time-only patch linting (AF2-L05),
same-device duplicate presets (AF2-L06), and physical verification of the
documented patch (hardware checklist). Fixture *profiles* (semantic channel
names in code) remain correctly deferred — per-channel meaning lives in
`docs/fixtures/` per D-014.

### Shared cue sequencing

**TARGET; schema not yet sufficient — the top blocker.** Unchanged conclusions:
beat duration belongs on each cue entry (`{target_id, beats ≥ 1}`); DMX and WLED
share the entry shape and one `BeatSequencer` implementation (two instances);
runtime counters live in the sequencer instances owned by the ShowController,
never persisted; reset on activation/reload/explicit-reset only; loop by
default; advance on the completing beat; empty list is an activation error;
`beats < 1` rejected at validation. The v2→v3 migration demonstrates exactly the
pattern the cue-entry migration (v3→v4) should follow.

### Audio-engine boundary

**TARGET — unchanged.** Minimum contract: `BeatEvent {seq, timestamp, bpm?,
confidence?}` over a bounded in-process queue (or newline-JSON localhost socket
if out-of-process); Lights App owns sensitivity (pushed at activation), beat
counting, and all lighting decisions; audio engine owns BPM and detection; stale
(>1–2 s) and duplicate events dropped; on disconnect the sequencers freeze and
the looks hold — no free-run; a `ScriptedBeatSource` drives everything
deterministically in tests.

### Active DMX runtime state

**Boundary correct; ownership still absent.** `Active_DMX_Channels` remains
correctly unpersisted, rebuilt-from-zero snapshots remain the right model (now
explicitly deterministic per resolution), and the module globals still need an
owner with lifecycle and an explicit atomic-swap contract (AF-M03). New since
last pass: `SUPPORTED_UNIVERSE` makes the single-buffer limitation explicit and
enforced. Still missing for transport: clamping at the write boundary (AF-M01),
blackout operation, dirty tracking.

### E1.31 / sACN readiness

**Improved config, still no transport.** `DMXConfig` now expresses a
destination: `universe = 1 (1..63999)`, `host`, `port = 5568`,
`priority = 100 (0..200)`, `refresh_hz ≥ 1` — recovered from the previous app's
config and explicitly documented as **unverified against the box** (the
`127.0.0.1` host is a placeholder from old testing, and `refresh_hz = 120`
still exceeds the physical DMX bus — AF-L01 open). Still absent:
unicast/multicast selection and source name. The recommendation stands: a
dedicated `backend/output/` sender owning socket + timer, **using the `sacn`
PyPI library**, with Null (default) / Recording / real implementations.

### LEDfx / WLED integration

**Preserved — unchanged by `ddcadf8`.** The adapter remains sound (narrow,
`Protocol`-typed, null-by-default, timeout-bounded, log-once unreachability,
dedup with invalidation on disconnect); the defects remain on the library side
of the boundary (AF2-H01/M01/M04) plus zero test coverage (AF2-M03) and the
duplicate-name caveat (AF2-L01). Logical strip subdivision stays in LEDfx
virtual devices; no app-side model unless proven necessary. Live validation
against the installed LEDfx version is a hardware-checklist item.

### Show controller / orchestration

**Needed; now the main body of remaining work.** One small explicit
`ShowController` owning: current scene, two sequencer instances, resolved
cue-list snapshots (copies, not live Library references), sensitivity push, the
beat-queue consumer loop, calls into the output adapters, and the LEDfx
scene-name upsert (per AF2-H01's fix). Not owning: HTTP details, packet framing,
audio analysis. `activate` = replace; cue 0 applied immediately on activation.

### Concurrency and timing

**Unchanged.** Current concurrency is exactly one optional daemon thread
(`ledfx-scene-sync`) with the known defects. Recommended model remains threads +
one bounded queue into a single show-control thread, atomic snapshot swaps for
output state, a dedicated sender thread that blocks only on its own timer, no
asyncio. This makes the sequencers, LEDfx client, and dedup state
single-threaded by construction, eliminating AF2-M04 and most of AF2-H01
structurally.

### Persistence and integrity

**Strong; further validated.** Everything confirmed in the previous pass holds,
and `ddcadf8` added a second real migration exercising the framework (snapshot,
fail-hard, idempotent skip, version discipline) plus a new root collection with
documented rationale. Retained caveats: load-time writes (AF-M05, documented),
force-delete blast radius without dry-run (AF-H04, before UI),
`stored_version` coercion (AF-L04), background-writer risk (AF2-H01). JSON
storage remains the right choice at this scale.

### ILDA boundary

Unchanged and correct: opaque blob storage behind one reference edge, no output
path, gated by [laser_and_haze_safety.md](laser_and_haze_safety.md).

---

## Schema Migration Assessment

### v1 → v2 (WLED lists) — preserved

Safe, as previously assessed: snapshot-first, fail-hard on malformed data,
writes only after the full loop, version advances only after the step, idempotent
per-item skip, test-covered. Caveats [AF2-L02](#af2-l02)/[AF2-L04](#af2-l04).

### v2 → v3 (DMX devices) — audited this pass: **safe**

[migrations.py:128-186](../backend/storage/migrations.py#L128-L186), point by
point:

| Property | Verdict |
| --- | --- |
| Device-preset ids preserved | ✅ rewritten in place under the same keys; `channel_values` copied untouched |
| No silent value loss | ✅ only `order`/`channel_count` are removed from presets, both subsumed by the device |
| Device identity generation | ✅ one `DMX_Device` (uuid) per distinct legacy `order`; presets sharing an order share one device (tested) |
| Address derivation | ✅ reproduces the old packing rule — devices sorted by `order`, each starting where the previous ended, cursor from 1 — so migrated looks resolve to the same channels the old runtime produced |
| Cross-look disagreement | ✅ handled explicitly: the **widest** `channel_count` per order wins, with an in-code comment ("no device loses channels"); tested. *Caveat:* if old looks genuinely disagreed on a device's width, narrower looks now render at the widest device's addresses — the only faithful resolution, since the old per-look packing gave such looks inconsistent addresses anyway |
| Legacy detection / idempotency | ✅ keyed on absence of `device_id` — already-migrated items pass through untouched; version check makes whole-step re-runs no-ops |
| Malformed data | ✅ missing/non-int `order` or `channel_count < 1` raises `StorageError` before any write (tested) |
| Partial-failure safety | ✅ both collections written only after the full loop; `_record_version` only after the step returns; snapshot taken before any step |
| Post-migration integrity | ✅ every rewritten preset's `device_id` points at a device created in the same step, so the graph cannot dangle; enforced again by `check_integrity()` on next load |
| Universe assignment | ✅ all synthesized devices get universe 1, matching what the old single-buffer runtime actually rendered |
| Placeholder naming | ✅ `"Device {order}"` with null model/mode — honest about what the old data knew; the operator (or seed, on a fresh folder) supplies real names |

**Note on migration vs. seed:** migration compacts addresses by the old packing
rule (correct for migrated *data*), while the seed uses the physically dialled
addresses (1 and 25, correct for the real *rig*, whose old data used 24-wide
padding blocks — making the two consistent for that data). They serve different
folders and do not conflict.

---

## Testing Assessment

**Current baseline: 84 tests, all passing** (50 at audit time; sequencing and
outputs added since). Breakdown by file, verified by reading every test:

| Suite | Tests | Covers |
| --- | --- | --- |
| `test_library.py` | 13 | Round-trip (incl. WLED list), dangling refs (add + on-disk), delete/force-cascade/unlink, pruning, duplicate ids, WLED list storability, optional ILDA detach |
| `test_migrations.py` | 11 | Version handling, snapshot layout, v1→v2 WLED wrap, v2→v3 device synthesis, v3→v4 beats/sensitivity, malformed rejection |
| `test_dmx_devices.py` | 11 | Device round-trip, address bounds, dangling `device_id`, prune survival, delete/cascade, runtime resolution |
| `test_seed_devices.py` | 4 | Documented patch, idempotency, reload survival, seeded non-overlap through `build_channels` |
| `test_sequencer.py` | 11 | Beat advance, loop, hold-last, reset, one-entry no-emit |
| `test_scene_controller.py` | 13 | Activation, deactivation, beat advance, empty-list errors, failed activation preserves prior scene |
| `test_outputs.py` | 5 | DmxOutput buffer swap, WledOutput swallows LedFxError |
| `test_json_store.py` | 5 | Atomic write round-trip, quarantine (4 modes), envelope |
| `test_ilda.py` | 7 | Id traversal, import/path, folder sync both directions, blob delete, missing blob, collision suffixing |
| `test_archive.py` | 3 | Export/import round-trip, zip-slip, log/backup exclusion |
| `test_logging_setup.py` | 1 | File handler writes |

All tests use temp data roots; the real data folder is untouchable from the
suite.

**Coverage classification:**

| Area | Status |
| --- | --- |
| Storage / migration (all steps through v4) | ✅ current |
| DMX device model + persistence | ✅ current |
| DMX runtime resolution | ✅ current |
| Seed / patch | ✅ current |
| Cue sequencer | ✅ current (WS-3) |
| Scene controller + outputs | ✅ current (WS-3) |
| Beat source boundary | ✅ protocol + manual impl |
| LEDfx client / sync | ❌ still zero ([AF2-M03](#af2-m03)) |
| Real beat detection | — future (WS-9) |
| E1.31 transport | — future (WS-4) |
| App entry point | — future |

Strategy unchanged: unit tests for the sequencer as a pure state machine
(highest-value future suite); `httpx.MockTransport` for the LEDfx client now;
contract tests for `BeatEvent`; in-memory integration (Scene → universe
snapshot, Scene → LEDfx call sequence, scripted beats → deterministic
transitions); null implementations as config defaults; hardware reserved for the
checklist.

---

## CI / Tooling Assessment

Unchanged: no CI (a minimal 3.12 + pytest workflow is now clearly worth adding
— the suite is 3 s and two schema migrations deep); no linter configured (Ruff
when CI lands, nothing more); `pytest.ini` correct; absolute-from-`backend/`
imports documented and fine at this scale; `.venv` correctly gitignored.

## Dependency Assessment

Unchanged: four direct, current, used pins. Future: `sacn` (P6, first
transmitting dependency, needs sign-off), audio capture (other repo), optional
dev-only `ruff`.

---

## Documentation Drift

`ddcadf8` updated the docs alongside the code, and they are accurate: the
architecture/current-sprint/decisions/fixture-strategy/platform docs now
correctly describe `DMX_Device` as implemented, WS-2.1 as done, D-014 as
implemented, the v3 schema, and the recovered-but-unverified `DMXConfig`.
Remaining drift at HEAD, all cosmetic:

| Doc claim | Reality | Class |
| --- | --- | --- |
| README/AGENTS/`seed_devices.py`: environment at `venv/` | `.venv/` (3.12.10) | STALE ([AF2-L03](#af2-l03)) |
| platform_support.md: "no 3.12 runtime / no venv found" observations | `.venv` with 3.12.10 exists | STALE (v1-era observation) |
| show_control_architecture.md §8 cites "no logging exists" (AF-M08) | Logging exists | STALE cross-reference |
| session_handoff.md (marked **Historical**) | Accurate as history | fine |
| Older audit text describing 32 tests / fixture gap | Superseded by this document | replaced |

---

## Previous Audit Reconciliation

| Previous ID | Previous Finding | Status | Current Evidence | Replacement |
| --- | --- | --- | --- | --- |
| AF-H01 | No fixture identity; positional DMX addressing | **RESOLVED** (`ddcadf8`) | `DMX_Device` root collection; `device_id` on presets; address-based `build_channels` with overlap/universe/past-end rejection; v2→v3 migration; 18 tests. Multi-universe *buffering* deliberately deferred (universe stored, validated, rejected if ≠ 1) — a limitation, not a reopening | — |
| AF-H02 | Beat duration absent from persisted model | **PARTLY RESOLVED** (schema v4) | Both cue lists carry `beats` per list (`ge=1`); sequencers built; per-*entry* beats still absent | WS-3.5 when needed |
| AF-H03 | `WLED_Preset_List` unreachable; no LEDfx id; asymmetric Preset | **RESOLVED** (`7ece72d`) | Re-validated at HEAD; WLED tests pass unchanged | — |
| AF-H04 | Force-delete cascade blast radius, no dry-run | **OPEN** | [library.py:349-407](../backend/storage/library.py#L349-L407) unchanged; cascade logs; optional ILDA detach on delete | — (before UI) |
| AF-H05 | No tests of any kind | **RESOLVED** (storage + runtime) | 84-test suite; LEDfx still uncovered | [AF2-M03](#af2-m03) |
| AF-M01 | DMX channel values unclamped | **OPEN** | `channel_values: List[int]` unbounded on model and record | — |
| AF-M02 | `sensitivity` unbounded | **RESOLVED** (schema v4) | `Scene.sensitivity` bounded 0.0–1.0; migration clamps on-disk values | — |
| AF-M03 | Module-global runtime state, no concurrency story | **OPEN** | `active_dmx_channels` module global remains; `DmxOutput` accepts injection | [AF2-H01](#af2-h01) extends |
| AF-M04 | Model/record four-place edits | **OPEN** (accepted cost) | Both `7ece72d` and `ddcadf8` paid it correctly in all four places | — |
| AF-M05 | `Library.load()` writes to disk | **PARTLY RESOLVED** | `sync_ilda` defaults false; construct still runs migrate/ensure_config | — |
| AF-M06 | `DMXConfig.universe` defaults to 0 | **RESOLVED** (`ddcadf8`) | `universe = 1 (ge=1, le=63999)`; `host`/`port`/`priority` added, recovered from the old app's config — explicitly **unverified against the box** | — |
| AF-M07 | Empty duplicate config module | **RESOLVED** | Compile-time defaults module, documented | — |
| AF-M08 | No logging | **RESOLVED** | `logging_setup.py` + storage/ledfx/seed logging; no entry point calls it yet (none exists) | — |
| AF-L01 | `refresh_hz = 120` exceeds DMX512 | **OPEN** | Default still 120 (now validated `ge=1`); bus caps near 44 Hz | — (P6) |
| AF-L02 | Stale `typing` backport pins | **RESOLVED** | Clean requirements | — |
| AF-L03 | Session state in config | **OPEN** (deliberate, low) | Unchanged, unread | — |
| AF-L04 | `stored_version` coerces non-int to current | **OPEN** | [migrations.py:38-41](../backend/storage/migrations.py#L38-L41) | — |
| AF-L05 | `import_ild` bypasses `Library.add()` | **OPEN** (harmless) | Unchanged | — |
| AF-D01 | README frontend reference | **RESOLVED** | Accurate | — |
| AF-D02 | Import root/run undocumented | **RESOLVED** | README + platform_support | — |
| AF-D03 | Python 3.12 documented but absent locally | **SUPERSEDED** | `.venv` has 3.12.10; naming drift only | [AF2-L03](#af2-l03) |

Audit-v2 findings from the previous pass, re-checked at HEAD: AF2-H01, AF2-M01,
AF2-M02, AF2-M04, AF2-L01, AF2-L02, AF2-L03, AF2-L04 — **all still OPEN**
(LEDfx code unchanged; `wled_presets` not added to prune roots). AF2-M03 —
**PARTIALLY RESOLVED** (DMX-resolution half closed by `ddcadf8`; LEDfx half
open). New this pass: [AF2-L05](#af2-l05), [AF2-L06](#af2-l06).

---

## Recommended Implementation Order

Recalculated for HEAD. Fixture identity is **done** — it appears below only as
regression protection. Each phase is one small branch with deterministic
acceptance criteria.

### P0 — Regression protection and thread hygiene *(no hardware)*

- **Objective:** protect the two completed architecture corrections and close
  the cheap reliability holes before runtime work begins.
- **Work:** LEDfx client tests via `httpx.MockTransport` and sync upsert tests
  (AF2-M03); broad exception guard + health surface in `LedFxSceneSync._run`
  (AF2-M01); add `WLED_PRESETS` to `ROOT_COLLECTIONS` with a test (AF2-M02);
  duplicate-device guard or documented last-wins in `build_channels` (AF2-L06);
  minimal CI workflow (3.12, pytest).
- **Findings addressed:** AF2-M01, AF2-M02, AF2-M03, AF2-L06.
- **Dependencies:** none. **Hardware:** no.
- **Validation:** suite green; new LEDfx tests exercise parsing, dedup, and
  reachability transitions without a socket.
- **Do NOT yet:** any schema change; any sequencer; AF2-H01's restructure
  (lands with P4 where its new owner exists).

### P1 — Per-entry cue schema (v3 → v4) *(no hardware)*

- **Objective:** the last data-model gap. Both cue lists become ordered entry
  lists of `{target_id, beats: int ≥ 1}` (replacing `dmx_preset_ids` /
  `wled_preset_ids` + scalar `beats`), one shared entry shape. Add the
  remaining value bounds in the same pass: `channel_values` items 0–255
  (AF-M01), `sensitivity` 0.0–1.0 (AF-M02).
- **Migration:** follow the v2→v3 pattern (snapshot, fail-hard, `device_id`-
  style new-field-wins detection, write-at-end); migrated entries default
  `beats = 1`, documented.
- **Findings addressed:** AF-H02, AF-M01, AF-M02.
- **Dependencies:** P0. **Hardware:** no.
- **Validation:** round-trip + migration tests on realistic v3 data;
  `beats < 1` rejected at model and record; 255-bound tests.
- **Do NOT yet:** loop-mode flags, fades, conditions (YAGNI); runtime code.

### P2 — Shared BeatSequencer *(no hardware)*

- **Objective:** one pure state-machine class (entries, index, beats_elapsed,
  loop), consuming beat events, emitting cue-changed; zero I/O; two instances.
- **Findings addressed:** the semantic half of AF-H02.
- **Dependencies:** P1. **Hardware:** no.
- **Validation:** exhaustive synthetic-beat unit tests (advance on completing
  beat, wrap, one-entry, reset, no-emit-on-hold).
- **Do NOT yet:** wire to outputs; threads.

### P3 — Audio event contract + scripted source *(no hardware)*

- **Objective:** `BeatEvent {seq, timestamp, bpm?, confidence?}`, bounded
  queue, staleness/duplicate policy, sensitivity setter, `ScriptedBeatSource`.
- **Dependencies:** P2. **Hardware:** no.
- **Validation:** scripted stream → deterministic dual-sequencer transitions.
- **Do NOT yet:** real audio capture (other repo); free-run fallback (rejected).

### P4 — ShowController + LEDfx restructure *(no hardware)*

- **Objective:** the runtime owner. `activate/deactivate/shutdown`; resolved
  snapshots; cue 0 applied on activation; sensitivity push; single
  show-control thread draining the beat queue; **LEDfx sync hands scene names
  to the controller instead of touching the Library (AF2-H01, AF2-M04)**;
  `active.py` module globals moved into controller-owned state (AF-M03).
- **Findings addressed:** AF2-H01, AF2-M04, AF-M03.
- **Dependencies:** P2, P3. **Hardware:** no.
- **Validation:** end-to-end in-memory test — activate scene, scripted beats,
  assert universe snapshots and `NullLedFxClient` call sequence (exactly one
  activate per cue change).
- **Do NOT yet:** UI; E1.31.

### P5 — LEDfx live validation *(LEDfx running; strips optional)*

- **Objective:** validate the adapter against the installed LEDfx version
  (list shape, activate, whether `deactivate` exists, restart behavior);
  reconnect re-apply; duplicate-name warning (AF2-L01); decide exit behavior.
- **Dependencies:** P4. **Hardware:** LEDfx only (runs without physical strips).

### P6 — E1.31 transport *(hardware at the very end)*

- **Objective:** `backend/output/` sender interface — Null (default) /
  Recording / `sacn`-backed real; hybrid change+keepalive cadence; blackout on
  clean shutdown; sender thread blocks only on its own timer; finish
  `DMXConfig` (unicast/multicast, source name; fix `refresh_hz` default to
  ≤ 44, AF-L01); verify recovered `host`/`port`/`priority` against the box.
- **Findings addressed:** AF-L01; the transport half of D-017.
- **Dependencies:** P4; sign-off on the `sacn` dependency.
- **Validation:** `RecordingDmxSender` byte/cadence/sequence assertions with a
  fake clock — no socket in tests. Then the hardware checklist.
- **Do NOT yet:** Art-Net, RDM, merging, multi-universe buffers (until the rig
  has a second universe).

### P7 — Patch verification at the rig *(hardware)*

- **Objective:** confirm the seeded patch against physical reality: DIP/dial
  addresses, modes, the Keobin ch 15/16 ambiguity, GigBAR constraints; box
  IP/universe into `config.json` (never git). Most patch *data* work is already
  done by `seed_devices.py` + `docs/fixtures/`; this phase is measurement.

### P8 — UI / operator controls

- **Objective:** scene select, status (audio silent-vs-dead, DMX/LEDfx
  reachability), blackout/panic, confirmed deletion (`plan_delete()`, AF-H04),
  patch lint at edit-time (AF2-L05). Keep it small.

### P9 — Full hardware-in-loop validation

- **Objective:** the checklist below, end to end, with music.

*(ILDA stays outside the sequence, gated by
[laser_and_haze_safety.md](laser_and_haze_safety.md).)*

**Can do now without hardware:** P0–P4 in full, P6 minus bring-up, most of P5.
**Requires physical access:** LEDfx-with-WLED-device checks (P5 tail), universe
box behavior + `DMXConfig` verification (P6 bring-up), patch verification (P7),
P9.

---

## Hardware-Test Checklist

Only items that genuinely require hardware; everything else must be green in
software first.

**DMX patch (needs the fixtures):**
- [ ] GigBAR 2 is dialled to address 1 in `23CH` mode; Keobin bar to 25 in
      `18CH` — matching the seeded patch.
- [ ] Keobin channels 15/16: set 15 = 255, 16 = 17 = 0; confirm red (swap the
      doc rows if green) — the docs' own ⚠ caveat.
- [ ] GigBAR: confirm the 3-of-4-colours and ch 21/22 mutual-exclusion
      behavior as the hardware enforces it.
- [ ] Each fixture responds correctly to a manually applied look, channel by
      channel against `docs/fixtures/`.

**E1.31 / universe box (needs the custom box):**
- [ ] Universe number the box accepts (config default 1 unverified).
- [ ] Real box IP replaces the recovered `127.0.0.1`; port 5568 and priority
      100 confirmed.
- [ ] Unicast accepted (or multicast required).
- [ ] Behavior when packets stop: hold vs. blackout.
- [ ] Sustained cadence without coalescing/dropping at the configured rate.
- [ ] Blackout command produces darkness; clean exit leaves the intended state.
- [ ] Windows Firewall rule for outbound UDP 5568 pre-approved.

**LEDfx / WLED (needs the installed LEDfx + controllers):**
- [ ] `GET /api/scenes` shape matches the client's parsing on the installed
      version.
- [ ] `activate` works; confirm whether `deactivate` is supported.
- [ ] Scene-activation latency acceptable for on-beat changes.
- [ ] LEDfx restart mid-show: unreachable → recover → re-apply.
- [ ] Virtual-device subdivision behaves as independent sections under one
      scene.

**End to end (everything + audio):**
- [ ] Real music → beats → both cue lists advance; latency acceptable.
- [ ] Kill audio mid-show: lights hold, status visible, no free-run.
- [ ] Kill LEDfx mid-show: DMX unaffected. Unplug the box: LEDfx unaffected;
      sender retries; clean recovery.

---

## Confirmed Strengths

Verified at current HEAD; future work should not degrade these.

1. **Declarative reference graph** — now proven twice: both the WLED and the
   DMX-device corrections threaded new collections through `REFERENCES` and
   integrity/cascade/prune/referrers worked, test-verified.
2. **Crash-safe atomic writes** (temp file, fsync, `os.replace`, cleanup on
   `BaseException`).
3. **Corrupt-file quarantine** instead of overwrite, four modes, tested.
4. **Integrity on load, save, and insert** with typed errors, tested.
5. **Migration framework** — snapshot-first, fail-hard, version-disciplined,
   now exercised by **two** real migrations with tests; the v2→v3 step's
   widest-claim rule and new-field-wins detection are model examples for v3→v4.
6. **The DMX patch as data** — explicit addresses, gaps expressible, collisions
   and out-of-universe patches rejected loudly at resolution; per-channel
   semantics documented in `docs/fixtures/` rather than over-modelled in code.
7. **Root-collection reasoning** — externally-anchored collections (ILDA
   frames, now DMX devices) exempted from pruning with in-code rationale.
8. **Zip import hardened against traversal**, tested; **ILDA id path-escape
   validation**, tested.
9. **Persistence boundary on runtime state** (`Active_*` never persisted).
10. **Null-by-default LEDfx integration** (disabled default, `NullLedFxClient`,
    `Protocol` seam, bounded timeouts, log-once unreachability, dedup with
    invalidation) — the template for the future DMX sender.
11. **Seeding as an explicit idempotent setup utility** that never overwrites
    operator repatching.
12. **Temp-root test isolation**; **data outside the repository**; **deliberate
    single-installation scope** held consistently.

---

## Deferred / Non-Issues

Recorded so future reviews do not re-litigate them:

- Multi-universe *buffering* — universe is stored, validated, and rejected when
  unsupported; build buffers only when the rig gains a second universe.
- Fixture profile libraries / semantic channel models in code — per-channel
  meaning lives in `docs/fixtures/` by design (D-014); revisit only if raw
  values demonstrably hurt.
- `channel_values: List[int] = []` mutable default — pydantic v2 copies
  defaults per instance; functionally safe.
- Generalized venue support, multi-user, auth, cloud, plugin systems — out of
  scope by D-009/D-010.
- Replacing JSON with a database — no requirement the current design fails.
- Model/record duplication (AF-M04) — deliberate; paid correctly in both
  schema corrections.
- `Library.load()` write side effects (AF-M05) — documented; tests isolate.
- `ui.last_scene_id` in config (AF-L03) — harmless, unread.
- Full ILDA runtime — gated behind laser-safety prerequisites.
- Asyncio migration, message buses — thread + queue is sufficient for one room.
- The local `.venv/` — correctly gitignored; only doc naming drifts (AF2-L03).

---

## Audit Methodology

1. Re-established ground truth at HEAD `45dbf9b` (branch, SHA, environment,
   pins, test result) — this update explicitly re-audits after `ddcadf8`.
2. Read every file changed by `ddcadf8` in full (models, runtime, seed,
   storage, migrations, records, config, all 18 new tests, all new/updated
   docs) plus the unchanged files needed for cross-module reasoning.
3. Ran the full test suite: **50/50 pass** (Python 3.12.10).
4. Audited the DMX_Device implementation against a per-area checklist (model
   bounds, reference integrity, runtime resolution edge cases, multi-universe
   semantics, migration safety, seeding idempotency, doc/code consistency) —
   independently of the commit's claims.
5. Re-ran repository-wide searches (stale `order`/`wled_preset_id`, threading,
   sockets, sACN) to confirm no stale implementation uses and no new
   concurrency.
6. Verified the LEDfx modules byte-unchanged and preserved the prior WLED/LEDfx
   conclusions rather than re-deriving them.
7. Reconciled all v1 and prior v2 findings against HEAD with evidence.

No production code was modified. No network calls were made. No hardware was
touched.

## Validation Performed

```text
git branch / rev-parse         → docs/fable-v2-repository-audit @ 45dbf9b0
.venv\Scripts\python --version → Python 3.12.10
.venv\Scripts\python -m pytest → 84 passed (50 at audit time)
grep "order" (device presets)  → live model/record clean; migration + tests + history only
grep wled_preset_id (non-list) → migration code/tests/historical docs only
grep threading|socket|sacn|asyncio → threading only in ledfx/scene_sync.py; no transport code
git diff 7ece72d ddcadf8       → reviewed in full (25 files, +1047/−123)
```

## Files Inspected

**backend/models/** Scene, Preset, DMX_Preset_List, DMX_Preset,
DMX_Device_Preset, **DMX_Device**, WLED_Preset_List, WLED_Preset,
ILDA_Frame_List, ILDA_Frame, Active_DMX_Channels, Active_ILDA_Frame ·
**backend/storage/** records, library, json_store, migrations, paths, config,
archive, ilda_blobs · **backend/runtime/** active, sequencer, outputs,
scene_controller · **backend/audio/** beat_source · **backend/ledfx/** client,
scene_sync, service · **backend/config/** config · **backend/** logging_setup,
**seed_devices** ·
**tests/** conftest, test_library, test_migrations, **test_dmx_devices**,
**test_seed_devices**, test_json_store, test_archive, test_ilda,
test_logging_setup, **test_sequencer**, **test_scene_controller**,
**test_outputs** ·
**docs/** all 13 architecture docs + **fixtures/README, chauvet_gigbar_2,
keobin_light_bar** · **root:** README.md, AGENTS.md, requirements.txt,
pytest.ini, .gitignore.
