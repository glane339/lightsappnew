# Current Sprint

Near-term implementation plan, grounded in [audit_findings.md](audit_findings.md).
No dates — the repository contains no schedule, and inventing one would be noise.
Longer horizon in [roadmap.md](roadmap.md).

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](decisions.md#d-023-a-look-is-a-dmx_preset).

**Status key:** `Not started` · `In progress` · `Done` · `Blocked`

## Future plans

> **Updated 2026-08-19.** WS-11.2 Performance + Builder pages are in `frontend/`.
> Docs aligned with that; remaining UI work is WS-9 health, not a second frontend.
> Suite is **211** tests. Current maturity in
> [project_overview.md](project_overview.md#current-maturity).

> **Session closed 2026-08-10.** Nothing below is in progress — it is the queue for
> when work resumes. Current maturity in
> [project_overview.md](project_overview.md#current-maturity).

> **Updated 2026-08-17.** Universe **1**, single-universe rig, network-switch
> destination IP (local `config.json` only), **unicast** transport
> ([D-017](decisions.md#d-017-sacn-unicast-versus-multicast)), and **blackout on packet stop**
> are recorded in
> [fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).
> Packet-stop behaviour verified: **blackout**.
>
> **Server/runtime audit completed 2026-08-13** at `acc52a7`
> ([Audit v3](audit_findings.md#audit-v3--operator-server--runtime)). Verdict:
> **READY WITH MINOR FIXES** — no blocker to *beginning* E1.31, with four
> recommended fixes folded into the WS-4.4 window
> ([F-01](audit_findings.md#f-01) ack-ledger pairing,
> [F-02](audit_findings.md#f-02) sender exception guard,
> [F-04](audit_findings.md#f-04) stop-script hardening,
> [F-05](audit_findings.md#f-05) blackout-on-shutdown). None are implemented yet.
> The milestone order below is unchanged — the audit confirmed it.

### Landed (no action needed)

| Area | Status |
| --- | --- |
| Storage, schema v4, migrations | Done |
| DMX fixture model (`DMX_Device`, patch-based resolution) | Done |
| WLED list registration, `Preset.wled_preset_list_id` | Done |
| List-level `beats`, bounded `sensitivity` | Done (schema v4) |
| `CueSequencer`, `SceneController`, outputs, `BeatSource` protocol | Done (WS-3) |
| Symbolic DMX sender (`DmxTransport`, `NullTransport`, `SenderThread`) | Done (WS-4.2) |
| E1.31 framing + `E131Transport` (`runtime/e131.py`, opt-in via `dmx.transport`) | Done in code (WS-4.4), **unverified on hardware** |
| Send-on-change seam (`publish()` / `dmx_dirty`) | Done |
| Operator server M1 (`backend/main.py`, `/ws/show`, REST control, latency) | Done (WS-11.1) |
| WS-11.2 Performance + Builder UI | Done (remaining: WS-9 health on Performance; optional LEDfx refresh / scene helper) |
| WLED off show thread (`AsyncCueOutput` + worker) | Done (WS-5 wiring in engine) |
| Show authoring (`AuthoringService`, typed HTTP, [D-022](decisions.md#d-022-empty-cue-lists-cannot-be-authored)) | Done (WS-10) |
| 211-test suite | Done |
| Audit v2 merge + post-audit doc refresh | Done |
| Server/runtime audit v3 at `acc52a7` — READY WITH MINOR FIXES ([findings F-01…F-15](audit_findings.md#findings-summary)) | Done (fixes **not** implemented) |

### Build next (dependency order)

1. **Universe box verification** — universe **1**, one universe, switch IP,
   **unicast** ([D-017](decisions.md#d-017-sacn-unicast-versus-multicast)), and
   **blackout on packet stop** are recorded in
   [fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).
   WS-4.3 config is complete. Remaining: one activation against the physical box (WS-4.4).
2. **WS-4.4 · Actual E1.31 sender** — `E131Transport` behind `DmxTransport`; hand-rolled
   framing + byte tests; socket injected in tests; opt-in via config after box sign-off.
   See [WS-4.4](#44-real-sacn-sender) below.
3. **WS-9 · Real beat detection** — live audio is wired into look cycling;
   remaining: capture health, WASAPI loopback as a named device, BPM in the UI.
   `ManualBeatSource` stays for tests.
4. **WS-11.2 remainder** — pages exist; Performance still needs audio health, and
   optional `POST /api/ledfx/refresh` / scene-save helper are not in the API. See
   [frontend_architecture.md](frontend_architecture.md).

Longer arc: [roadmap.md](roadmap.md) phases 4 → 5 → 7 → **7a** → 8.

### Deferred (revisit when a real show needs them)

| Item | Workstream | Why wait |
| --- | --- | --- |
| Per-entry beat durations | WS-2.2 / WS-3.5 | List-level `beats` unblocked sequencing |
| `channel_values` 0–255 clamp | WS-2.4 | Sensitivity/beats done; values still open |
| Module-global buffer → owned state | WS-3.4 | Matters once a real beat thread exists |
| Multi-universe buffers | WS-4.1 | One universe matches current rig |
| ILDA output | WS-7 / phase 9 | Laser path severed; safety gates first |
| CI workflow | WS-6 / audit P0 | No blocker for local dev |

### When changing the frontend

Read [frontend_architecture.md](frontend_architecture.md) (routes, modes, builder
pages) and [authoring.md](authoring.md) (HTTP contract). The UI must not call
`Library.add()` directly — go through the authoring service and HTTP surface. Scene →
lighting preset → DMX cue list + WLED cue list is the creation hierarchy; the Scenes
builder page hides the intermediate `Preset` layer.

---

```mermaid
flowchart LR
    WS1["WS-1<br/>Architecture<br/>baseline"] --> WS6["WS-6<br/>Test harness"]
    WS6 --> WS2["WS-2<br/>Scene & preset<br/>model"]
    WS2 --> WS3["WS-3<br/>Beat<br/>sequencing"]
    WS2 --> WS4["WS-4<br/>DMX state<br/>& E1.31"]
    WS3 --> WS4
    WS3 --> WS5["WS-5<br/>LEDfx"]
    WS1 --> WS7["WS-7<br/>ILDA severed<br/>from show path"]
    WS1 --> WS8["WS-8<br/>Docs &<br/>onboarding"]
    WS3 --> WS9["WS-9<br/>Real beat<br/>detection"]
    WS2 --> WS10["WS-10<br/>Show authoring<br/>frameworks"]
    WS3 --> WS10
    WS10 --> WS11["WS-11<br/>Frontend &<br/>HTTP server"]
```

WS-6 comes before schema changes deliberately: the storage layer's cascade and
pruning logic is the code most likely to break under model changes. WS-6.1 is
**done** ([AF-H05](audit_findings.md#af-h05) partially addressed). WS-10 is **done**
— [authoring.md](authoring.md) is the HTTP contract WS-11.2 consumes.

---

## WS-1 · Architecture stabilization

### 1.1 Establish the documentation baseline
- **Goal.** A contributor can understand the system without re-reading every file.
- **Why.** The repository had no `docs/`, and the gap between the intended system
  and the implementation was undocumented and substantial.
- **Dependencies.** None.
- **Acceptance.** `docs/` contains the 13 documents indexed in
  [project_overview.md](project_overview.md#where-to-go-next); every file path
  referenced resolves; current versus target is labelled throughout.
- **Status.** **Done** — this task.
- **Files.** `docs/*`, [`README.md`](../README.md).

### 1.2 Reconcile the two config modules
- **Goal.** Make the split intentional and documented (do **not** delete
  `backend/config/`).
- **Why.** [AF-M07](audit_findings.md#af-m07) assumed `backend/config/config.py`
  was empty/dead. It now holds compile-time LEDfx defaults that seed
  [`storage/config.py`](../backend/storage/config.py) `LedfxConfig`. Two modules
  remain, with distinct roles.
- **Dependencies.** None.
- **Acceptance.** Module docstrings state the split; docs no longer call
  `backend/config/` dead.
- **Status.** **Done.**
- **Files.** [`backend/config/config.py`](../backend/config/config.py),
  [`storage/config.py`](../backend/storage/config.py).

### 1.3 Clean up `requirements.txt`
- **Goal.** Drop `typing==3.7.4.3` and the direct `typing_extensions` pin; keep
  real direct deps (`httpx`, `platformdirs`, `pydantic`, `pytest`).
- **Why.** `typing` is a Python 3.4–3.6 backport with no purpose on 3.12;
  `typing_extensions` is a pydantic transitive dependency
  ([AF-L02](audit_findings.md#af-l02)).
- **Dependencies.** None.
- **Acceptance.** A fresh venv installs from `requirements.txt` and all modules
  import successfully.
- **Status.** **Done.**
- **Files.** [`requirements.txt`](../requirements.txt).

### 1.4 Add logging
- **Goal.** A `logging` setup writing to the already-created `logs/` directory.
- **Why.** Quarantined files, vanished ILDA frames, and cascade deletes are all
  currently silent, and the runtime will need this from its first line
  ([AF-M08](audit_findings.md#af-m08)).
- **Dependencies.** None.
- **Acceptance.** Storage-layer events appear in `logs/`; no `print` anywhere.
- **Status.** **Done.**
- **Files.** [`backend/logging_setup.py`](../backend/logging_setup.py);
  [`storage/`](../backend/storage/);
  `logs/` path already exists at [`paths.py:21`](../backend/storage/paths.py#L21).

---

## WS-2 · Scene and preset model

> **2.1 (devices), 2.3 (WLED lists), and list-level `beats` (schema v4) are done.**
> Per-entry beat durations (2.2) remain deferred. Field validation (2.4) is partly
> done — `sensitivity` and `beats` are bounded; `channel_values` 0–255 is not.

The schema changes below are historical sprint text. All would be additive and
migratable through `REFERENCES` in [`records.py`](../backend/storage/records.py)
([D-015](decisions.md#d-015-the-reference-graph-stays-declarative)) if revived.

### 2.1 Introduce the `DMX_Device` collection
- **Goal.** A persisted device (id, name, model, mode, universe, start_address,
  channel_count); `DMX_Device_Preset.order` → `device_id`.
- **Why.** [AF-H01](audit_findings.md#af-h01) — positional address derivation was the
  root blocker for correct multi-look rigs, address gaps, and multi-universe.
- **Dependencies.** WS-6.1 (storage tests) — landed first, as planned.
- **Acceptance.** Fixtures round-trip; `build_channels` resolves addresses from
  fixtures rather than a cursor; a look with non-contiguous addresses produces the
  correct buffer; a look referencing a missing fixture fails the integrity check at
  load; a migration converts existing `order`-based data and is covered by a test.
- **Status.** **Done** — `dmx_devices` is a registered root collection; `build_channels`
  resolves addresses from the patch and rejects overlaps and out-of-universe devices;
  schema v3 migration synthesises devices from `order`. Named `DMX_Device` rather than
  `Fixture` to match the existing `DMX_*` naming. Multi-universe buffers deferred; the
  runtime raises for any universe but 1.
- **Files.** new [`backend/models/DMX_Device.py`](../backend/models/DMX_Device.py);
  [`models/DMX_Device_Preset.py`](../backend/models/DMX_Device_Preset.py);
  [`storage/records.py`](../backend/storage/records.py);
  [`storage/library.py`](../backend/storage/library.py);
  [`storage/migrations.py`](../backend/storage/migrations.py);
  [`runtime/active.py`](../backend/runtime/active.py).

### 2.2 Add per-entry beat durations to both cue lists
- **Goal.** Cue-list entries carrying `(target_id, beats)` for DMX and WLED alike.
- **Why.** [AF-H02](audit_findings.md#af-h02) — variable hold times per cue entry
  are still unrepresentable.
- **Dependencies.** WS-6.1.
- **Acceptance.** Both lists hold ordered entries with a per-entry beat count;
  `beats < 1` is rejected at load; migration preserves existing ordering with a
  documented default; both lists share one entry shape.
- **Status.** **Deferred.** Schema v4 added one `beats` scalar per list, which
  unblocked WS-3; revisit when a real show needs different hold times per cue.
- **Files.** [`models/DMX_Preset_List.py`](../backend/models/DMX_Preset_List.py);
  [`models/WLED_Preset_List.py`](../backend/models/WLED_Preset_List.py);
  `storage/records.py`; `storage/migrations.py`.

### 2.3 Make the WLED path modellable
- **Goal.** Register `WLED_Preset_List` with the storage layer; change
  `Preset.wled_preset_id` → `wled_preset_list_id`.
- **Why.** [AF-H03](audit_findings.md#af-h03) — the list was unreachable and the
  `Preset` shape was asymmetric with the DMX side.
- **Dependencies.** None (landed independently of parked WS-2.1/2.2).
- **Acceptance.** `WLED_Preset_List` appears in `RECORD_TYPES`, `COLLECTION_ORDER`,
  `MODEL_TYPES`, and `REFERENCES`; it round-trips; `Library.add()` accepts it;
  a `Preset` resolves to a WLED cue list; schema v2 migration wraps legacy data.
- **Status.** **Done.**
- **Files.** `models/Preset.py`; `models/WLED_Preset_List.py`;
  `storage/records.py`; `storage/library.py`; `storage/migrations.py`;
  `tests/test_library.py`; `tests/test_migrations.py`.

### 2.4 Add field validation
- **Goal.** Bound `channel_values` to 0–255, `sensitivity` to 0.0–1.0, `beats` to ≥ 1.
  `DMX_Device.start_address`/`channel_count`/`universe` are already bounded.
- **Why.** [AF-M01](audit_findings.md#af-m01), [AF-M02](audit_findings.md#af-m02) —
  invalid values currently validate and would reach the wire.
- **Dependencies.** [D-016](decisions.md#d-016-audio-event-delivery-mechanism) is
  not required, but sensitivity semantics should be recorded when this lands.
- **Acceptance.** Out-of-range values raise at model construction and at load;
  constraints applied to both the model and the record; tests cover each boundary.
- **Status.** **Partly done** — `sensitivity` and cue-list `beats` bounded in schema
  v4; `channel_values` 0–255 still open ([AF-M01](audit_findings.md#af-m01)).
- **Files.** [`models/`](../backend/models/), `storage/records.py`.

---

## WS-3 · Shared beat sequencing

> **Unparked and largely built.** The control model settled as: beats per cue *list*
> (not per entry), two independent sequencers off one beat stream, and the beat source
> behind a protocol so no audio library choice was needed to build any of it.

### 3.1 `CueSequencer`
- **Goal.** One class: entries, index, beats elapsed, loop mode; consumes beat
  events, emits cue-changed. No I/O, no knowledge of DMX or WLED.
- **Why.** [D-003](decisions.md#d-003-dmx-and-wled-share-one-beat-sequencing-implementation) —
  duplicated sequencing drifts. This is also the highest-value test target in the
  project and needs no audio or hardware.
- **Acceptance.** Advances exactly on the beat completing an entry's count; loop and
  hold-last both correct; reset returns to index 0 with a cleared counter; a beat
  that does not advance emits nothing; the full suite runs with a synthetic beat
  list and zero I/O.
- **Status.** **Done.** One addition beyond the acceptance criteria: a one-entry list
  reports no change ever, so LEDfx is not re-told to run the scene it already runs.
- **Files.** [`runtime/sequencer.py`](../backend/runtime/sequencer.py),
  [`tests/test_sequencer.py`](../tests/test_sequencer.py).

### 3.2 Scene Controller
- **Goal.** Activate/deactivate a scene: resolve definitions once, reset both
  sequencers, apply cue 0 immediately, propagate sensitivity.
- **Why.** No component owned the current scene; `ui.last_scene_id` was the only
  acknowledgement the concept existed.
- **Acceptance.** Activation applies cue 0 without waiting for a beat; switching
  scenes discards outgoing sequence state entirely; an empty cue list is a clean
  activation error, not a crash; the controller holds resolved snapshots rather than
  live `Library` references.
- **Status.** **Done.** Schema 5 dropped per-scene sensitivity; there is no
  processor input left to push. A failed activation leaves the previous scene
  running.
- **Files.** [`runtime/scene_controller.py`](../backend/runtime/scene_controller.py),
  [`runtime/outputs.py`](../backend/runtime/outputs.py),
  [`tests/test_scene_controller.py`](../tests/test_scene_controller.py),
  [`tests/test_outputs.py`](../tests/test_outputs.py).

### 3.3 Beat source boundary
- **Goal.** A `BeatSource` protocol emitting discrete beats, with a manual
  implementation, so the sequencing core is built and tested without an audio library.
- **Why.** The library choice is the least certain part of the audio work — aubio is
  GPL and unmaintained, the newer options are unproven — and it should not be able to
  block show logic.
- **Acceptance.** The controller runs off subscribed beats; a stopped source emits
  nothing; BPM is carried for display and never drives sequencing.
- **Status.** **Done** for the boundary. Production also runs
  [`AudioEngineBeatSource`](../backend/audio/audio_engine_source.py); see WS-9.
- **Files.** [`audio/beat_source.py`](../backend/audio/beat_source.py).

### 3.4 Runtime state ownership
- **Goal.** Move the universe buffer global in
  [`runtime/active.py`](../backend/runtime/active.py) into an owned object with
  explicit lifecycle and locking.
- **Why.** [AF-M03](audit_findings.md#af-m03) — concurrent activities are coming and
  there is no synchronisation. `DmxOutput` already accepts an injected buffer, which is
  half the work; the remaining half is removing the module-level default and adding a
  lock shared with beat handling.
- **Dependencies.** Matters once a real beat source brings its own thread.
- **Acceptance.** No mutable module-level state; buffer updates and sender reads are
  race-free by construction, not by GIL accident.
- **Status.** Not started.
- **Files.** `backend/runtime/`.

### 3.5 Per-entry beat counts
- **Goal.** Let one cue hold 16 beats and the next 4, by making cue lists hold
  `{preset_id, beats}` entries instead of a flat list of ids.
- **Why.** [AF-H02](audit_findings.md#af-h02). Deliberately deferred: `beats` per list
  unblocked everything else, and the library holds almost no authored content, so
  changing shape later stays cheap.
- **Dependencies.** The integrity checker, orphan pruner, and cascade delete all have
  to understand nested references first.
- **Status.** Not started — revisit after a real show.

---

## WS-4 · DMX state and E1.31 output

> **Partially landed.** The symbolic sender and send-on-change path are live in the
> operator server. **Packet framing and UDP (WS-4.4) remain blocked** on universe-box
> verification and WS-4.3 config completion.

### 4.1 Multi-universe active state with dirty tracking
- **Goal.** Per-universe 512-value buffers, dirty flags, clamped writes, blackout.
- **Why.** Single-universe and no change detection today; clamping closes
  [AF-M01](audit_findings.md#af-m01) at the boundary as well as the model.
- **Dependencies.** WS-2.1.
- **Acceptance.** Writes clamp to 0–255; dirty set on write, cleared on send;
  blackout zeroes and marks dirty; buffers are never persisted.
- **Status.** **Partly done** — single-universe dirty tracking via `publish()` /
  `dmx_dirty` in [`runtime/active.py`](../backend/runtime/active.py); multi-universe
  and clamp-at-write still open.
- **Files.** [`models/Active_DMX_Channels.py`](../backend/models/Active_DMX_Channels.py),
  `backend/runtime/`.

### 4.2 Sender interface with a null default
- **Goal.** `send(channels)` / `start()` / `stop()`, with a null implementation.
  **No real sender.**
- **Why.** [D-013](decisions.md#d-013-hardware-output-defaults-to-a-null-implementation) —
  null-by-default is what makes everything downstream safe to develop and test.
- **Dependencies.** 4.1.
- **Acceptance.** Default (and only) transport is `NullTransport`; tests never open
  a socket.
- **Status.** **Done** — [`runtime/sender.py`](../backend/runtime/sender.py)
  (`DmxTransport`, `NullTransport`, `SenderThread` send-on-change + keepalive).
- **Files.** [`backend/runtime/sender.py`](../backend/runtime/sender.py),
  [`backend/runtime/active.py`](../backend/runtime/active.py) (`publish()` / `dmx_dirty`).

### 4.3 Network configuration
- **Goal.** Reshape `DMXConfig`: unicast/multicast, source name, per-universe
  destinations; fix the `refresh_hz: 120` default.
- **Partly done.** `universe` (now 1), `host`, `port`, `priority`, `mode`, `source_name`,
  `bind_address`, and `transport` exist — universe **1**, switch destination, and
  **unicast** recorded ([§6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary),
  [D-017](decisions.md#d-017-sacn-unicast-versus-multicast)).
- **Why.** [AF-M06](audit_findings.md#af-m06), [AF-L01](audit_findings.md#af-l01);
  the current three fields cannot describe a working sACN setup.
- **Dependencies.** [D-017](decisions.md#d-017-sacn-unicast-versus-multicast) (accepted:
  unicast); verification against the actual universe box for end-to-end output.
- **Acceptance.** Config expresses a complete destination; defaults are valid;
  no IPs or hostnames appear in the repository.
- **Status.** **Done** — universe **1**, single universe, network switch destination
  (IP in local `config.json` only), **unicast** ([D-017](decisions.md#d-017-sacn-unicast-versus-multicast)),
  **blackout on packet stop**, and full transport config (`mode`, `source_name`,
  `bind_address`, `transport`, `refresh_hz` default 44) are in
  [`storage/config.py`](../backend/storage/config.py) and recorded in
  [fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).
- **Files.** [`storage/config.py`](../backend/storage/config.py).

### 4.4 Real sACN sender — **NEXT HARDWARE MILESTONE**

- **Goal.** Put the existing wake loop on the wire: an `E131Transport` class
  implementing `DmxTransport`, without changing `SenderThread`.
- **Why.** The latency budget is already measured server-receive → `NullTransport.send`
  (software path only); this adds the UDP `sendto` while keeping the same thread model
  ([D-019](decisions.md#d-019-send-on-change--keepalive-cadence)).
- **Dependencies.** 4.2 (done), 4.3 (done — universe 1, switch destination,
  unicast, packet-stop blackout recorded).
- **Audit v3 items to fold in (none implemented yet):**
  [F-01](audit_findings.md#f-01) — fix the ack/latency-ledger pairing *before* the
  ledger is used as acceptance evidence; [F-02](audit_findings.md#f-02) — exception
  guard in `SenderThread._run`; [F-05](audit_findings.md#f-05) — the close-time
  blackout below plus an explicit engine-level blackout in `stop()`, with a
  zeros-then-close test; [F-04](audit_findings.md#f-04) — harden `stop-server.ps1`
  before hardware output is enabled; [F-10](audit_findings.md#f-10) — gate
  `/api/diag/selftest` behind transport==null; [F-15](audit_findings.md#f-15) —
  settle the 120 Hz keepalive against the box (with 4.3).
- **Implementation plan:**
  1. Add [`runtime/e131.py`](../backend/runtime/e131.py) — hand-rolled 638-byte DATA
     packet builder, per-universe sequence counter, slot clamp 0–255
     ([D-020](decisions.md#d-020-hand-rolled-e131-framing)).
  2. Add `E131Transport` in [`runtime/sender.py`](../backend/runtime/sender.py) —
     reads `DMXConfig` (host, port, universe, priority, source name); lazy UDP socket;
     `send()` frames and `sendto`s; `close()` sends Stream_Terminated blackout then
     closes; send failures log and never raise.
  3. Wire transport selection in [`server/engine.py`](../backend/server/engine.py) —
     default stays `NullTransport`; opt-in field on `DMXConfig` (e.g. `transport:
     "e131"`) only after box sign-off.
  4. Tests in `tests/test_e131.py` — assert packet bytes and sequence wrap; use an
     injected fake socket; **no real UDP in CI**.
  5. Manual integration — one activation against the physical box; record verified
     settings back into [fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).
- **Acceptance.** Generated bytes asserted in tests without opening a socket;
  sequence numbers increment per universe and wrap; clean shutdown sends blackout
  then closes; a send failure logs and does not take the show down; p99 latency
  budget (13 ms scene selection → sender) still met with real transport enabled.
- **Status.** **Code landed 2026-08-16, unverified on hardware.**
  [`runtime/e131.py`](../backend/runtime/e131.py) frames 638-byte DATA packets;
  `E131Transport` in [`runtime/sender.py`](../backend/runtime/sender.py) sends them
  unicast or multicast with an injectable socket; `build_transport()` keeps
  `NullTransport` as the default. Folded in: [F-02](audit_findings.md#f-02) (sender
  exception guard), [F-05](audit_findings.md#f-05) (blackout before close, both in
  `E131Transport.close()` and `engine.stop()`), [F-10](audit_findings.md#f-10)
  (self-test refuses a live transport), [F-15](audit_findings.md#f-15) (`refresh_hz`
  default 120 → 44). **Remaining:** [F-01](audit_findings.md#f-01) ack-ledger pairing
  and one activation against the physical box.
- **Files.** [`backend/runtime/e131.py`](../backend/runtime/e131.py) (new),
  [`backend/runtime/sender.py`](../backend/runtime/sender.py),
  [`backend/storage/config.py`](../backend/storage/config.py),
  [`backend/server/engine.py`](../backend/server/engine.py),
  `tests/test_e131.py` (new).

---

## WS-5 · LEDfx integration

### 5.1 Resolve the identifier question
- **Goal.** Answer [D-018](decisions.md#d-018-ledfx-preset-identifier-form) against a
  running LEDfx instance — which entity, what identifier form, is it stable across
  restarts.
- **Why.** If identifiers are unstable, storing them produces config that silently
  breaks.
- **Dependencies.** LEDfx installed. It runs without physical WLED devices, so this
  risks nothing.
- **Acceptance.** Answers recorded in
  [wled_ledfx_architecture.md](wled_ledfx_architecture.md#31-preset-identifiers) and
  D-018 moved to Accepted.
- **Status.** **Done** (accepted: `WLED_Preset.id` = LEDfx scene name; slug resolved
  in memory). Still needs live verification when hardware arrives.
- **Files.** docs; [`backend/ledfx/`](../backend/ledfx/).

### 5.2 LEDfx client adapter
- **Goal.** The only module that knows LEDfx exists: HTTP calls, explicit timeouts,
  bounded retry, dedup of repeat activations, reachability state. Null and recording
  variants; null is the default.
- **Why.** [D-004](decisions.md#d-004-ledfx-owns-wled-output),
  [D-013](decisions.md#d-013-hardware-output-defaults-to-a-null-implementation).
- **Dependencies.** 5.1. Requires an HTTP client dependency.
- **Acceptance.** Client + null client exist; scene sync can upsert names into
  `wled_presets`; nothing activates unless `ledfx.enabled` is true. Full
  beat-thread isolation is satisfied in the operator server via `AsyncCueOutput`.
- **Status.** **Done** — adapter/sync in [`backend/ledfx/`](../backend/ledfx/);
  show engine activates scenes on a WLED worker when `ledfx.enabled` is true.
- **Files.** [`backend/ledfx/`](../backend/ledfx/);
  [`storage/config.py`](../backend/storage/config.py) (`WLEDConfig` → `LedfxConfig`).

---

## WS-6 · Hardware-independent testing

### 6.1 Test harness and storage suite
- **Goal.** pytest configured; the storage layer covered.
- **Why.** [AF-H05](audit_findings.md#af-h05) — the subtlest code in the repository
  (recursive cascade with cycle guarding, reachability pruning, atomic writes,
  quarantine, folder reconciliation) is entirely unverified, and every WS-2 change
  touches it.
- **Dependencies.** None. `LIGHTSAPP_DATA_DIR`
  ([`paths.py:15`](../backend/storage/paths.py#L15)) and the `root` parameter already
  provide the injection point.
- **Acceptance.** Tests run against a temp directory and never touch the real data
  folder; round-trip, dangling-reference rejection, cascade delete (including the
  Scene-destroying single-reference path), orphan pruning, ILDA folder sync,
  corrupt-file quarantine, and migration version handling are all covered.
- **Status.** **Done.**
- **Files.** [`tests/`](../tests/); [`pytest.ini`](../pytest.ini);
  [`requirements.txt`](../requirements.txt).

### 6.2 Null and recording implementations everywhere
- **Goal.** Null/recording variants for the DMX sender, LEDfx client, and audio
  processor; null selected by default.
- **Why.** [D-013](decisions.md#d-013-hardware-output-defaults-to-a-null-implementation).
- **Dependencies.** WS-4.2, WS-5.2, and the audio work.
- **Acceptance.** The full suite runs with no network, no audio device, and no
  hardware. `ScriptedAudioProcessor` drives an end-to-end scene test.
- **Status.** Not started.
- **Files.** `backend/output/`, `tests/`.

---

## WS-7 · ILDA severed from the show path

### 7.1 Take ILDA out of the runtime rather than stubbing it
- **Goal.** No laser concern anywhere on the path a scene takes to output.
- **Why.** Superseded the original plan of a stub ILDA Controller. A stub still has to
  be called from somewhere, and the cheapest correct answer while laser work is parked
  is for nothing to call it at all.
- **Status.** **Done.** `Scene.ilda_frame_list_id` is optional, so scenes are complete
  without one; `runtime/active.py` no longer resolves frames and no longer holds an
  `Active_ILDA_Frame`; `SceneController` never mentions ILDA; and the folder sync is
  opt-in rather than running on every open.
- **Deliberately left alone.** The ILDA models, records, blob store, archive support,
  and their tests are all intact and simply unreferenced — ILDA runs through 112 places
  in `backend/`, and tearing that out would have damaged the integrity checker and
  archive for no gain. Making `ilda_frame_list_id` required again is all it takes to
  bring the path back.
- **Files.** [`models/Scene.py`](../backend/models/Scene.py),
  [`runtime/active.py`](../backend/runtime/active.py),
  [`storage/library.py`](../backend/storage/library.py).

**Explicit non-goal, unchanged:** no laser output code of any kind.

---

## WS-9 · Real beat detection

### 9.1 Choose and adapt an audio library
- **Goal.** A `BeatSource` implementation driven by real audio, behind the protocol
  WS-3.3 already established.
- **Why.** `ManualBeatSource` proves the show logic but cannot run a show.
- **Decision.** Use [`lights-audio-engine`](https://github.com/glane339/lights-audio-engine)
  (pinned by commit SHA in `requirements.txt`, with the `probe` extra for
  `sounddevice`). Capture is blocking `InputStream.read` on a worker thread. Beats
  enter the show as `ShowCommand(BEAT)` ([D-016](decisions.md#d-016-audio-event-delivery-mechanism)).
  `ManualBeatSource` stays for tests. Unset `input_device` uses PortAudio's default
  input; a blank selector or missing device leaves the show on manual tap.
- **Acceptance.** Beats arrive from live audio; the suite still runs with no audio
  device; BPM is display-only.
- **Status.** **Partial.** Capture starts on app lifespan and detected beats advance
  cue lists (integration-tested with a fake `run_engine`). Not done: operator-visible
  silence vs dead capture, BPM/level on `/api/status` or Performance, first-class
  WASAPI loopback (still a raw device name). LEDfx may still compete for the same
  input.
- **Files.** [`backend/audio/`](../backend/audio/),
  [`backend/server/app.py`](../backend/server/app.py),
  [`tests/test_audio_integration.py`](../tests/test_audio_integration.py).

---

## WS-8 · Documentation and contributor onboarding

### 8.1 Document how to run and test
- **Goal.** Record the import root, the data-folder location and override, and the
  test command.
- **Why.** [AF-D02](audit_findings.md#af-d02) — imports are absolute from `backend/`
  with no `__init__.py` and nothing says so.
- **Dependencies.** WS-6.1 for the test command.
- **Acceptance.** A new contributor can install, import, and run tests from the docs
  alone.
- **Status.** **Done** — [`README.md`](../README.md) and
  [platform_support.md](platform_support.md) document install, import root, data
  folder override, and `pytest`.
- **Files.** [`platform_support.md`](platform_support.md), [`README.md`](../README.md).

### 8.2 Keep decisions current
- **Goal.** Move D-016 from Open to Accepted when answered.
- **Why.** Three open decisions block WS-3, WS-4, and WS-5 respectively.
- **Dependencies.** The corresponding investigations.
- **Acceptance.** No Open decision blocks an in-progress workstream.
- **Status.** D-018 **Accepted**. D-017 **Accepted** (unicast). D-016 **Accepted**
  (queue delivery).
- **Files.** [`decisions.md`](decisions.md).

---

## WS-10 · Show authoring frameworks

> **Done.** [`AuthoringService`](../backend/authoring/service.py) owns typed
> create/update/delete for the show graph. HTTP is in
> [`backend/server/routes/scenes.py`](../backend/server/routes/scenes.py) and
> [`backend/server/routes/authoring.py`](../backend/server/routes/authoring.py).
> Contract: [authoring.md](authoring.md). Empty cue lists cannot be authored
> ([D-022](decisions.md#d-022-empty-cue-lists-cannot-be-authored)).

Depends on WS-2 (model) and WS-3 (semantics of `beats` and scene activation).
Unblocked WS-11.2 (now done). The M1 operator server (WS-11.1) already exists.

### 10.1 DMX cue list creation framework
- **Goal.** Create, update, reorder, and validate `DMX_Preset_List` objects: ordered
  `dmx_preset_ids`, list-level `beats`, non-empty guard before a preset references
  the list.
- **Why.** A UI editor needs to assemble looks into a sequence without hand-editing
  JSON or calling `Library.add()` in the wrong order.
- **Dependencies.** WS-2.1, WS-2.4 (partial — `beats` bounded).
- **Acceptance.** A caller can create a list from an ordered id sequence; reorder
  and replace entries; get a clear error when a referenced `DMX_Preset` is missing;
  round-trip through save/load; tests use a temp `Library` root only.
- **Status.** **Done.**
- **Files.** [`backend/authoring/service.py`](../backend/authoring/service.py),
  [`tests/test_authoring.py`](../tests/test_authoring.py).

### 10.2 WLED cue list creation framework
- **Goal.** Same as 10.1 for `WLED_Preset_List`: ordered `wled_preset_ids`, `beats`,
  validation that each id names a known LEDfx scene (from sync or manual add).
- **Why.** WLED cue lists mirror DMX cue lists; the UI should treat them symmetrically.
- **Dependencies.** 10.1 pattern; WS-2.3; WS-5 when live LEDfx sync is wired.
- **Acceptance.** Parallel API shape to 10.1; rejects empty lists and dangling preset
  ids; tests cover reorder and beats update.
- **Status.** **Done.**
- **Files.** [`backend/authoring/service.py`](../backend/authoring/service.py),
  [`tests/test_authoring.py`](../tests/test_authoring.py).

### 10.3 Lighting preset creation framework
- **Goal.** Create or update a `Preset` that pairs one DMX cue list with one WLED cue
  list — either linking existing lists or creating both as part of one operation.
- **Why.** Scenes point at presets, not at cue lists directly; the preset is the
  natural unit an operator names (“Red wash + stripes”).
- **Dependencies.** 10.1, 10.2.
- **Acceptance.** Atomic create: both lists exist and are referenced before save;
  update can swap either list id; delete refuses or returns cascade plan when scenes
  reference the preset ([AF-H04](audit_findings.md#af-h04)).
- **Status.** **Done.**
- **Files.** [`backend/authoring/service.py`](../backend/authoring/service.py),
  [`tests/test_authoring.py`](../tests/test_authoring.py).

### 10.4 Scene creation framework
- **Goal.** Create, update, and list `Scene` objects: `preset_id`, `sensitivity`
  (default from `AudioConfig.default_sensitivity`), optional `ilda_frame_list_id`.
- **Why.** Scene selection is the operator’s top-level action; creation must validate
  that the preset’s cue lists are playable (non-empty) before activation would succeed.
- **Dependencies.** 10.3; [`SceneController`](../backend/runtime/scene_controller.py)
  for optional dry-run / preview activation in tests.
- **Acceptance.** Create scene with bounded sensitivity; reject missing preset;
  reject preset whose cue lists are empty (same rules as `SceneController.activate`);
  list and fetch for UI tables; update sensitivity without touching sequence state.
- **Status.** **Done.**
- **Files.** [`backend/authoring/service.py`](../backend/authoring/service.py),
  [`tests/test_authoring.py`](../tests/test_authoring.py).

### 10.5 Authoring service owner
- **Goal.** One module (or small package) that owns all `Library` mutations from
  non-test callers: batch adds in `COLLECTION_ORDER`, single `save()`, mapped errors.
- **Why.** [AF2-H01](audit_findings.md#af2-h01) — background LEDfx sync must not
  share unsynchronized `Library` access with the UI thread; the authoring service is
  the main-thread mutation path.
- **Dependencies.** 10.1–10.4.
- **Acceptance.** All authoring operations go through one entry type; exposes
  `plan_delete()` (or equivalent) before destructive deletes; no route handler or UI
  code calls `Library.add()` directly; unit tests cover error mapping.
- **Status.** **Done.** LEDfx scene sync upserts through `upsert_wled_presets` on the
  same `AuthoringService` instance (F-06 / AF2-H01).
- **Files.** [`backend/authoring/service.py`](../backend/authoring/service.py),
  [`storage/library.py`](../backend/storage/library.py) (`mutation_lock`),
  [`backend/server/engine.py`](../backend/server/engine.py),
  [`backend/server/app.py`](../backend/server/app.py).

### 10.6 HTTP API surface
- **Goal.** REST (or equivalent) endpoints for scenes, lighting presets, and both cue
  list types — thin handlers delegating to 10.5.
- **Why.** WS-11 frontend needs a stable contract; handlers stay dumb so business
  rules live in one place.
- **Dependencies.** 10.5; app entry point (process lifecycle, `configure_logging()`).
- **Acceptance.** CRUD routes for each authoring type; consistent error JSON for
  validation and `StorageError`; OpenAPI or documented request/response shapes;
  integration tests against an in-memory or temp-root server; no auth scope in v1
  (single-operator LAN).
- **Status.** **Done.** Typed routes (not generic collection CRUD). Looks and WLED
  names included so a scene can be created from an empty library; devices stay
  read-only.
- **Files.** [`backend/server/routes/scenes.py`](../backend/server/routes/scenes.py),
  [`backend/server/routes/authoring.py`](../backend/server/routes/authoring.py),
  [`backend/server/errors.py`](../backend/server/errors.py),
  [`tests/test_authoring_api.py`](../tests/test_authoring_api.py).

### 10.7 Frontend integration contract
- **Goal.** Document the DTOs and flows the `frontend/` app will use: list views,
  create/edit forms, and the scene → preset → cue lists → looks hierarchy.
- **Why.** Avoid duplicating graph knowledge in TypeScript; keep the UI a thin client
  over 10.6.
- **Dependencies.** 10.6 draft shapes stable enough to document.
- **Acceptance.** Doc section (or OpenAPI) lists every endpoint, field, and error
  code; example payloads for “create DMX cue list”, “create preset from two lists”,
  “create scene”; notes which ids are user-visible names vs opaque hex. Page-level UI
  plan in [frontend_architecture.md](frontend_architecture.md).
- **Status.** **Done.**
- **Files.** [authoring.md](authoring.md), [frontend_architecture.md](frontend_architecture.md).

---

## WS-11 · Frontend and HTTP server

> **M1 landed (2026-08-13).** Entry point, control plane, latency harness, and a
> no-build operator page exist. WS-11.2 (2026-08-19 docs status) consumed
> [authoring.md](authoring.md) as Performance + Builder pages in `frontend/`.

### 11.1 App entry point and process lifecycle
- **Goal.** A runnable process: open `Library`, `configure_logging()`, wire
  `SceneController` + outputs + optional LEDfx stack behind a show engine.
- **Dependencies.** WS-3.
- **Acceptance.** `python backend/main.py` serves on `0.0.0.0:8800`; WebSocket
  `/ws/show` and REST `/api/show/*` drive the show thread; sender uses
  `NullTransport`; latency ring buffer exposed at `/api/diag/latency`; p99 scene
  selection → sender ≤ 13 ms (`LATENCY_BUDGET_US` in [`server/latency.py`](../backend/server/latency.py)).
- **Status.** **Done** — [`backend/main.py`](../backend/main.py),
  [`backend/server/`](../backend/server/).
- **Files.** [`backend/main.py`](../backend/main.py), [`backend/server/app.py`](../backend/server/app.py),
  [`backend/server/engine.py`](../backend/server/engine.py).

### 11.2 Frontend application
- **Goal.** Two modes ([frontend_architecture.md](frontend_architecture.md)):
  **Performance** (scene grid + beat indicator on `/ws/show`) and **Builder** (six
  authoring pages over the REST API).
- **Why.** M1 is a latency harness with a scene picker; the operator needs fixture-aware
  editors and a show surface that stays simple during performance.
- **Dependencies.** WS-10 complete ([authoring.md](authoring.md)); fixture channel
  tables in [docs/fixtures/](fixtures/README.md) transcribed into
  `frontend/js/fixtures/`.
- **Acceptance.**
  - Home offers Performance and Builder; Builder sidebar follows leaf-to-root order.
  - GigBAR and Keobin pages save `DMX_Device_Preset` rows using section toggles in
    max-channel mode (`23CH` / `18CH`), not raw channel sliders.
  - dmx_presets page pairs one GigBAR and one Keobin device preset per look.
  - Both cue-list pages support drag-and-drop reorder and list-level `beats`.
  - WLED cue-list palette reflects registered LEDfx names (poll + background sync).
  - Scenes page pairs two cue lists and creates/finds the hidden `Preset` automatically.
  - Performance activates scenes over WebSocket; beat bar flashes on server beat events.
  - No graph logic duplicated in JavaScript; all mutations via authoring routes.
  - M1 latency readout moved to `/diag/` or removed from the show path.
- **Backend gaps (optional follow-ups, not required for the pages to work):**
  `{t:"beat"}` on `/ws/show` is **done**; optional `POST /api/ledfx/refresh`; optional
  scene save helper that accepts two cue-list ids (the Scenes page pairs in JS).
- **Status.** **Done** — pages in `frontend/` as specified in
  [frontend_architecture.md](frontend_architecture.md). Remaining: WS-9 health on
  Performance (BPM / level / silence vs dead capture).
- **Files.** [frontend_architecture.md](frontend_architecture.md); `frontend/`.

---
