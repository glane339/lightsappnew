# Audit Findings

Repository-grounded findings from a full read of all 21 Python source files, the
README, AGENTS.md, and `requirements.txt` at commit `691062e`.

Severity reflects impact **on this project at its current stage** — a pre-runtime
repository with no deployment, no users, and no hardware output. Nothing here is
rated Critical, because nothing in the repository can currently cause data loss,
unsafe output, or a security exposure. Inflating severity would obscure the two or
three findings that actually matter.

| ID | Severity | Finding | Blocks now? |
| --- | --- | --- | --- |
| [AF-H01](#af-h01) | High | No fixture identity; DMX addresses derived positionally | **Yes** |
| [AF-H02](#af-h02) | High | Beat duration is absent from the persisted model | **Yes** |
| [AF-H03](#af-h03) | High | `WLED_Preset_List` unreachable; `WLED_Preset` carries no LEDfx id | **Yes** |
| [AF-H04](#af-h04) | High | Force-delete cascade can silently destroy Scenes and user files | No |
| [AF-H05](#af-h05) | High | No tests of any kind | **Yes** |
| [AF-M01](#af-m01) | Medium | DMX channel values are never range-checked or clamped | No |
| [AF-M02](#af-m02) | Medium | `sensitivity` and other numeric fields are unbounded | No |
| [AF-M03](#af-m03) | Medium | Runtime state is module-global with no concurrency story | No |
| [AF-M04](#af-m04) | Medium | Model/record duplication requires four-place edits | No |
| [AF-M05](#af-m05) | Medium | `Library.load()` writes to disk | No |
| [AF-M06](#af-m06) | Medium | `DMXConfig.universe` defaults to 0, not a valid sACN universe | No |
| [AF-M07](#af-m07) | Medium | `backend/config/config.py` is an empty file duplicating a real module | No |
| [AF-M08](#af-m08) | Medium | No logging anywhere in the codebase | No |
| [AF-L01](#af-l01) | Low | `refresh_hz` default of 120 exceeds DMX512 physical capability | No |
| [AF-L02](#af-l02) | Low | `requirements.txt` pins a deprecated backport and transitive deps | No |
| [AF-L03](#af-l03) | Low | Session state (`ui.last_scene_id`) stored in the config file | No |
| [AF-L04](#af-l04) | Low | `stored_version` silently coerces a non-integer version | No |
| [AF-L05](#af-l05) | Low | `import_ild` bypasses `Library.add()` | No |
| [AF-D01](#af-d01) | Doc (resolved) | README frontend reference corrected | No |
| [AF-D02](#af-d02) | Doc | No documented import root or way to run anything | No |
| [AF-D03](#af-d03) | Doc | Setup instructions reference a Python version not present locally | No |

---

## High

### AF-H01
**No fixture identity; DMX start addresses are derived positionally.**

*Evidence.* [`runtime/active.py:23-50`](../backend/runtime/active.py#L23-L50) sorts
device states by `order` and packs them contiguously from channel 0, so a device's
start address is the running sum of every prior device's `channel_count`. No
`Fixture`/device definition exists anywhere: no `device_id`, `universe`,
`start_address`, or channel profile appears in
[`models/`](../backend/models/) or [`records.py`](../backend/storage/records.py).
`DMX_Device_Preset` carries only `order`, `channel_count`, `channel_values`.

*Why it matters.* The same physical fixture is an unrelated row in every look, with
nothing linking them. The rig's patch is implicitly restated in every `DMX_Preset`,
so looks can silently disagree about the rig; changing one device's `channel_count`
re-addresses everything after it in that look only; address gaps cannot be
expressed; and multi-universe is impossible. Every other DMX feature is built on
top of this.

*Recommended action.* Introduce a persisted `fixtures` collection (id, name,
universe, start_address, channel_count) and replace `order` with `fixture_id` on
`DMX_Device_Preset`. Additive migration; see
[fixture_and_transport_strategy.md](fixture_and_transport_strategy.md#3-target-fixture-model).

*Blocks:* **yes** — this should be the next implementation branch.

---

### AF-H02
**Beat duration is absent from the persisted model.**

*Evidence.* `DMX_Preset_List` is `dmx_preset_ids: List[str]`
([`models/DMX_Preset_List.py:7`](../backend/models/DMX_Preset_List.py#L7)) — no beat
field at all. `WLED_Preset_List` has `beats: int = 0`
([`models/WLED_Preset_List.py:8`](../backend/models/WLED_Preset_List.py#L8)), a
single scalar on the whole list rather than per entry, defaulting to a value that is
not a valid duration.

*Why it matters.* Beat-driven sequencing is the core feature of the application, and
neither cue list can express how long an entry holds. No sequencer can be built
against the current schema.

*Recommended action.* Introduce a cue-list *entry* shape carrying
`(target_id, beats)` for both DMX and WLED in one change, so the two do not
diverge. Validate `beats >= 1` at load.

*Blocks:* **yes.**

---

### AF-H03
**`WLED_Preset_List` is unreachable and `WLED_Preset` carries no LEDfx identifier.**

*Evidence.* Verified by search — `WLED_Preset_List` appears only in its own file:

```
$ grep -rn "WLED_Preset_List\|wled_preset_list" --include=*.py .
./backend/models/WLED_Preset_List.py:5:class WLED_Preset_List(BaseModel):
```

It is absent from `RECORD_TYPES`, `COLLECTION_ORDER`, and `REFERENCES` in
[`records.py`](../backend/storage/records.py) and from `MODEL_TYPES` in
[`library.py:59-68`](../backend/storage/library.py#L59-L68), so `Library.add()`
raises `StorageError` for it ([`library.py:263-265`](../backend/storage/library.py#L263-L265)).
Separately, `WLED_Preset` has exactly one field — a generated UUID
([`models/WLED_Preset.py`](../backend/models/WLED_Preset.py)) — and no field naming
anything in LEDfx. And `Preset.wled_preset_id`
([`models/Preset.py:8`](../backend/models/Preset.py#L8)) points at the single preset,
not at a list.

*Why it matters.* Three compounding gaps mean the WLED path cannot be built at all
on the current model: nothing can identify an LEDfx preset, nothing can hold a
sequence, and the `Preset` shape is asymmetric with the DMX side (list vs. single).

*Recommended action.* Register `WLED_Preset_List`, add `ledfx_preset_id` to
`WLED_Preset`, and change `Preset.wled_preset_id` to `wled_preset_list_id`. Do this
together with AF-H02. See
[wled_ledfx_architecture.md](wled_ledfx_architecture.md#3-target-model).

*Blocks:* **yes**, for the WLED workstream.

---

### AF-H04
**Force-delete cascade can silently destroy Scenes and user files.**

*Evidence.* [`library.py:335-363`](../backend/storage/library.py#L335-L363). When a
parent references a child through a *single* (non-list) field,
`_delete_cascade` deletes the parent too. Following `REFERENCES`
([`records.py:91-103`](../backend/storage/records.py#L91-L103)): deleting one
`WLED_Preset` deletes every `Preset` that names it, which deletes every `Scene` that
names those presets. Deleting an `ILDA_Frame` also unlinks the underlying `.ild`
file from disk ([`library.py:362-363`](../backend/storage/library.py#L362-L363)).

*Why it matters.* A single `delete(..., force=True)` on a leaf object can remove the
operator's scenes and delete their imported files. The return value lists what was
removed, and `delete()` refuses by default when referrers exist
([`library.py:324-329`](../backend/storage/library.py#L324-L329)) — the guard is
real. But the blast radius of overriding it is much larger than the API suggests,
and there is no dry-run.

*Recommended action.* Add a `plan_delete()` that returns the cascade set without
performing it, so a UI can confirm before destroying anything. Document the
single-reference cascade rule prominently on `delete()`.

*Blocks:* no — but fix before any UI exposes deletion.

---

### AF-H05
**No tests of any kind.**

*Evidence.* No test files, no `tests/` directory, no pytest configuration, no test
runner in [`requirements.txt`](../requirements.txt), no CI workflow.

*Why it matters.* The storage layer contains genuinely subtle logic — recursive
cascade delete with cycle guarding, reachability-based orphan pruning, atomic
writes, corrupt-file quarantine, folder/database reconciliation — and none of it is
verified. Every change recommended in this document touches that logic. Without
tests, the fixture-model migration (AF-H01) cannot be made safely.

*Recommended action.* Add pytest and write the storage suite first, using the
`LIGHTSAPP_DATA_DIR` environment override ([`paths.py:15`](../backend/storage/paths.py#L15))
or the `root` parameter to point at a temp directory. Both already exist and make
this straightforward.

*Blocks:* **yes** — this should land alongside or before AF-H01.

---

## Medium

### AF-M01
**DMX channel values are never range-checked or clamped.**

*Evidence.* `DMX_Device_Preset.channel_values: List[int]` has no constraint
([`models/DMX_Device_Preset.py:9`](../backend/models/DMX_Device_Preset.py#L9)), nor
does `DMXDevicePresetRecord` ([`records.py:44`](../backend/storage/records.py#L44)).
`build_channels` truncates and pads for *length*
([`active.py:46-47`](../backend/runtime/active.py#L46-L47)) but never inspects
values. A stored `300` or `-1` is copied straight into the universe buffer.

*Why it matters.* DMX slots are single bytes. Out-of-range values will either raise
during packet framing or, worse, be silently masked into a different value on the
wire.

*Recommended action.* Constrain the field (`conint(ge=0, le=255)` or equivalent)
**and** clamp at the buffer write boundary, so no path can produce an invalid frame.
Same for `channel_count` (`ge=1, le=512`) and `order` (`ge=0`).

---

### AF-M02
**`sensitivity` and other numeric fields are unbounded.**

*Evidence.* `Scene.sensitivity: float` ([`models/Scene.py:9`](../backend/models/Scene.py#L9))
and `SceneRecord.sensitivity` ([`records.py:21`](../backend/storage/records.py#L21))
have no `ge`/`le`. Any float validates, including negatives, infinity, and NaN.
`AudioConfig.default_sensitivity = 0.5` ([`storage/config.py:31`](../backend/storage/config.py#L31))
implies a 0–1 range but nothing enforces it, and the relationship between the two
fields is undefined.

*Why it matters.* An out-of-range sensitivity will produce either no beats or a
flood of them, and NaN comparisons fail silently in a way that is very hard to
diagnose mid-show.

*Recommended action.* Add `Field(ge=0.0, le=1.0)` to both, and record the semantics
per [audio_reactivity_architecture.md](audio_reactivity_architecture.md#51-sensitivity).

---

### AF-M03
**Runtime state is module-global with no concurrency story.**

*Evidence.* [`runtime/active.py:19-20`](../backend/runtime/active.py#L19-L20)
declares two mutable singletons at import time. No lock, no owner, no lifecycle.

*Why it matters.* Harmless today because nothing runs, but the design requires at
least three concurrent activities (audio callback, send loop, UI). The sender
reading a buffer mid-rewrite would transmit a half-updated frame. That
`update_active_dmx_channels` assigns a freshly-built list
([`active.py:73-75`](../backend/runtime/active.py#L73-L75)) makes the swap atomic
under CPython's GIL — an accident of the implementation, not a guarantee.

*Recommended action.* Move this state into an owned object with explicit lifecycle
and locking before any thread exists. See
[show_control_architecture.md](show_control_architecture.md#6-concurrency-and-race-conditions).

---

### AF-M04
**Model/record duplication requires four-place edits.**

*Evidence.* Every field is declared twice — in `models/*.py` and again in
[`records.py`](../backend/storage/records.py) — and converted by two hand-written
if-chains, `_from_record` ([`library.py:138-171`](../backend/storage/library.py#L138-L171))
and `_to_record` ([`library.py:219-252`](../backend/storage/library.py#L219-L252)).
Adding one field means four edits.

*Why it matters.* Every schema change proposed in this document (fixtures, beats,
LEDfx ids) pays this cost, and a missed edit produces silent data loss on save
rather than an error.

*Nuance.* Separating the on-disk schema from the runtime model is a **legitimate and
deliberate** choice — it lets the persisted format evolve independently under
`migrations.py`. The design is sound; only the manual converters are the debt.

*Recommended action.* Keep the separation. Consider generating the converters from
the field lists, or collapsing them to `Model(**record.model_dump())` where the
shapes match exactly (they currently do for all eight collections). Not urgent.

---

### AF-M05
**`Library.load()` writes to disk.**

*Evidence.* `load()` calls `sync_ilda_folder()` with the default `persist=True`
([`library.py:134-135`](../backend/storage/library.py#L134-L135)), which writes
`ilda_frames.json` and `ilda_frame_lists.json` when the folder and database differ
([`library.py:449-451`](../backend/storage/library.py#L449-L451)). Additionally,
`Library.__init__` runs `ensure_layout`, `migrate`, and `ensure_config`
([`library.py:91-93`](../backend/storage/library.py#L91-L93)), so merely
*constructing* a `Library` creates directories and can write `config.json`.

*Why it matters.* A read operation with write side effects is surprising, makes
read-only inspection impossible, and means an exception during load can leave the
folder partially rewritten. The `sync_ilda: bool` and `persist: bool` parameters
already exist to opt out — they are simply not the default.

*Recommended action.* Low-risk to leave as-is given the reconciliation is genuinely
useful, but document it clearly and consider a `read_only` mode. At minimum, tests
must pass an explicit `root`.

---

### AF-M06
**`DMXConfig.universe` defaults to 0.**

*Evidence.* [`storage/config.py:14`](../backend/storage/config.py#L14). sACN
universes are numbered from 1; 0 is not a valid E1.31 universe.

*Why it matters.* The default will not work against a conforming receiver, and it
will be a confusing first failure during transport bring-up.

*Recommended action.* Default to 1 — but **verify against the actual DMX universe
box first**, since nothing in the repository documents what it expects. See
[fixture_and_transport_strategy.md](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).

---

### AF-M07
**`backend/config/config.py` is an empty file duplicating a real module.**

*Evidence.* The file is tracked, is 0 bytes, and the actual configuration module is
[`backend/storage/config.py`](../backend/storage/config.py). There is no
`backend/config/__init__.py`, so `backend/config/` is a stray directory.

*Why it matters.* Two plausible import paths for "config", one of which is empty,
is a trap for the next contributor.

*Recommended action.* Delete `backend/config/`. Not done in this documentation task
— it is a source change, however trivial.

---

### AF-M08
**No logging anywhere in the codebase.**

*Evidence.* Zero matches for `logging`, `logger`, or `print` across all source
files. Note that [`paths.py:21`](../backend/storage/paths.py#L21) already creates a
`logs/` directory that nothing ever writes to.

*Why it matters.* Several documented behaviours are effectively invisible without
it: corrupt files are quarantined and moved aside, ILDA frames vanish and are
detached from lists, cascade deletes remove records. During a show, the difference
between "silence" and "the audio device died" has to be visible somewhere.

*Recommended action.* Add `logging` with a file handler pointed at the existing
`logs/` directory before any runtime component is built.

---

## Low

### AF-L01
**`refresh_hz` default of 120 exceeds DMX512 physical capability.**

[`storage/config.py:16`](../backend/storage/config.py#L16). A full 512-slot DMX512
frame takes roughly 23 ms at the standard bit rate, capping the bus near 44 Hz.
Emitting E1.31 at 120 Hz produces traffic the gateway must coalesce or drop.
Recommend 30–44 Hz, verified against the box. Harmless until a sender exists.

### AF-L02
**`requirements.txt` pins a deprecated backport and transitive dependencies.**

[`requirements.txt`](../requirements.txt) lists `typing==3.7.4.3` — the PyPI backport
of the standard library `typing` module, intended for Python 3.4–3.6 and with no
purpose on 3.12. The code imports stdlib `typing` throughout; the package is
unnecessary and installing it into site-packages is a known source of confusion.
`typing_extensions` is also pinned but never imported directly — it is a pydantic
transitive dependency. Recommend removing both direct pins, leaving
`platformdirs` and `pydantic`.

### AF-L03
**Session state stored in the config file.**

`UIConfig.last_scene_id` ([`storage/config.py:36`](../backend/storage/config.py#L36))
is session state living in persisted configuration. Defensible for a
single-operator app and currently unread; noted only so the persistence boundary
stays deliberate.

### AF-L04
**`stored_version` silently coerces a non-integer version.**

[`migrations.py:32-36`](../backend/storage/migrations.py#L32-L36) returns
`SCHEMA_VERSION` when `schema_version` is not an `int`, so a corrupted or
hand-edited value is treated as current and migration is skipped. Raising would be
safer; the surrounding module is otherwise carefully defensive.

### AF-L05
**`import_ild` bypasses `Library.add()`.**

[`library.py:409-412`](../backend/storage/library.py#L409-L412) writes directly into
`self.ilda_frames` instead of going through `add()`. Harmless — `ILDA_Frame` has no
outbound references to validate — but inconsistent with every other insertion path.

---

## Documentation-only

### AF-D01 (resolved)
**The README frontend reference was corrected.**

[`README.md`](../README.md) lists `frontend/ — Client application` in its structure
section, and [`AGENTS.md`](../AGENTS.md) instructs agents to "Put client/UI code in
`frontend/`". No such directory exists. *Corrected in this task* — the README now
states that the frontend is not yet present.

### AF-D02
**No documented import root or way to run anything.**

There is no `__init__.py`, no `pyproject.toml`, and no entry point. Imports are
absolute from `backend/` (`from models.Scene import Scene`), which works only via
implicit namespace packages with `backend/` on `sys.path`. This is undocumented.
See [platform_support.md](platform_support.md#import-root).

### AF-D03
**Setup instructions reference an environment not present locally.**

[`README.md`](../README.md) and [`AGENTS.md`](../AGENTS.md) both assume Python 3.12
and a `venv/` at the repository root. On the machine inspected during this audit,
`python --version` reports 3.11.9, `py -3.12` reports no such runtime, and no
`venv/` directory exists. Nothing in the code requires 3.12 specifically. Recorded
in [platform_support.md](platform_support.md).

---

## Confirmed strengths

These are worth protecting; several are better than the project's stage would
suggest.

1. **The reference graph is declared as data, not code.** `REFERENCES` in
   [`records.py:91-103`](../backend/storage/records.py#L91-L103) drives integrity
   checking, cascade delete, orphan pruning, and referrer lookup from a single
   table. Adding a relationship in one place makes all four work. This is the best
   decision in the repository and every schema change should go through it.

2. **Crash-safe writes.** [`json_store.py:33-46`](../backend/storage/json_store.py#L33-L46)
   writes to a temp file in the same directory, `flush`, `fsync`, then `os.replace`,
   and unlinks the temp file on any exception including `BaseException`. Correct.

3. **Corrupt files are quarantined, not overwritten.** `read_json` moves an
   unparseable file into a timestamped `backups/` folder and raises with the
   destination in the message ([`json_store.py:49-70`](../backend/storage/json_store.py#L49-L70)),
   rather than silently starting from empty. Detects empty files, invalid JSON,
   non-object payloads, and non-object items.

4. **Integrity is checked on load *and* on save.**
   [`library.py:132`](../backend/storage/library.py#L132) and
   [`library.py:207`](../backend/storage/library.py#L207) — with a distinct
   `DanglingReferenceError`, and `add()` refuses forward references
   ([`library.py:274-280`](../backend/storage/library.py#L274-L280)).

5. **Zip import is hardened against traversal.** `_safe_members`
   ([`archive.py:46-56`](../backend/storage/archive.py#L46-L56)) rejects absolute
   paths, `..` components, and both separator styles before extracting anything.

6. **ILDA frame ids cannot escape the folder.** `validate_frame_id`
   ([`ilda_blobs.py:17-23`](../backend/storage/ilda_blobs.py#L17-L23)) rejects
   separators, `.`, `..`, and anything that is not a bare filename — important
   because ids come from user-supplied filenames.

7. **Migration framework with a pre-migration snapshot.**
   [`migrations.py:66`](../backend/storage/migrations.py#L66) snapshots before any
   step runs, refuses to open a folder from a newer build
   ([`migrations.py:60-64`](../backend/storage/migrations.py#L60-L64)), and
   registers steps by source version. No steps exist yet, but the mechanism is
   ready for the schema changes this audit recommends.

8. **The persistence boundary is explicit and correct.**
   `Active_DMX_Channels` and `Active_ILDA_Frame` are deliberately excluded from
   `RECORD_TYPES`, and the docstring says "never persisted". The hardest thing to
   retrofit was gotten right from the start.

9. **Cycle-free module graph with a documented deferred import.**
   [`archive.py:71`](../backend/storage/archive.py#L71) breaks the one latent cycle
   with a function-local import and explains why, in place.

10. **Data lives outside the repository.** `platformdirs`-based layout with a
    `LIGHTSAPP_DATA_DIR` override ([`paths.py:15`](../backend/storage/paths.py#L15))
    means no user data or local paths can leak into git, and tests have a clean
    injection point.
