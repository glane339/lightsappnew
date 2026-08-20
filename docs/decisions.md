# Architecture Decision Log

Each decision is **Accepted** (implemented in the repository or fixed by the
supplied project requirements), **Proposed** (a recommendation from the architecture
review, not yet adopted), or **Open** (a choice that must be made and cannot be
inferred from the repository or supplied requirements).

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](#d-023-a-look-is-a-dmx_preset).

Format: Decision · Status · Context · Rationale · Consequences · Alternatives ·
Follow-up.

| ID | Decision | Status |
| --- | --- | --- |
| [D-001](#d-001-scene-is-the-top-level-manually-selected-unit) | Scene is the top-level manually selected unit | Accepted |
| [D-002](#d-002-audio-processing-owns-timing-not-lighting-decisions) | Audio processing owns timing, not lighting decisions | Accepted |
| [D-003](#d-003-dmx-and-wled-share-one-beat-sequencing-implementation) | DMX and WLED share one beat-sequencing implementation | Accepted |
| [D-004](#d-004-ledfx-owns-wled-output) | LEDfx owns WLED output | Accepted |
| [D-005](#d-005-transient-runtime-state-is-never-persisted) | Transient runtime state is never persisted | Accepted |
| [D-006](#d-006-stable-definitions-persist-as-normalized-json-collections) | Stable definitions persist as normalized JSON collections | Accepted |
| [D-007](#d-007-e131--sacn-is-the-dmx-transport) | E1.31/sACN is the DMX transport | Accepted |
| [D-008](#d-008-ilda-stays-behind-a-separate-processor-boundary) | ILDA stays behind a separate processor boundary | Accepted |
| [D-009](#d-009-basement-deployment-is-the-immediate-target) | Basement deployment is the immediate target | Accepted |
| [D-010](#d-010-basement-reliability-outranks-generality) | Basement reliability outranks generality | Proposed |
| [D-011](#d-011-hold-between-scenes-blackout-on-clean-shutdown) | Hold between scenes, blackout on clean shutdown | Accepted |
| [D-012](#d-012-network-failures-must-not-reach-persistent-state) | Network failures must not reach persistent state | Proposed |
| [D-013](#d-013-hardware-output-defaults-to-a-null-implementation) | Hardware output defaults to a null implementation | Accepted |
| [D-014](#d-014-fixtures-become-first-class-persisted-objects) | Fixtures become first-class persisted objects | Proposed |
| [D-015](#d-015-the-reference-graph-stays-declarative) | The reference graph stays declarative | Accepted |
| [D-016](#d-016-audio-event-delivery-mechanism) | Audio event delivery mechanism | Accepted |
| [D-017](#d-017-sacn-unicast-versus-multicast) | sACN unicast versus multicast | Accepted |
| [D-018](#d-018-ledfx-preset-identifier-form) | LEDfx preset identifier form | Accepted |
| [D-019](#d-019-send-on-change--keepalive-cadence) | Send-on-change + keepalive cadence | Accepted |
| [D-020](#d-020-hand-rolled-e131-framing) | Hand-rolled E1.31 framing | Accepted |
| [D-022](#d-022-empty-cue-lists-cannot-be-authored) | Empty cue lists cannot be authored | Accepted |
| [D-023](#d-023-a-look-is-a-dmx_preset) | A "look" is a `dmx_preset` | Accepted |

---

## D-001: Scene is the top-level manually selected unit

**Status:** Accepted and implemented — `SceneController.activate()` is the sole entry
point. No UI calls it yet.

**Context.** Something has to be the unit an operator picks. `Scene` sits at the top
of the reference graph: it is a `ROOT_COLLECTION`
([`records.py:87`](../backend/storage/records.py#L87)), nothing references it, and
everything else is reachable from it. It holds a lighting preset and an optional ILDA
frame list ([`models/Scene.py`](../backend/models/Scene.py)). Detector sensitivity is
not a scene field (schema 5).

**Rationale.** Manual selection removes an entire class of complexity: no cue stacks,
no timecode, no automatic transitions, no scheduling. The operator is the sequencer
at the top level; audio is the sequencer within a scene.

**Consequences.** Orphan pruning is anchored on scenes
([`library.py:365-388`](../backend/storage/library.py#L365-L388)), so anything a
scene cannot reach is collectable. Scene activation is the only entry point to the
runtime. There is no concept of layering two scenes.

**Alternatives.** A cue stack with fades (rejected: unnecessary for the target
installation); timecode-driven playback (rejected: no timecode source).

**Follow-up.** Scene activation is implemented in
[`runtime/scene_controller.py`](../backend/runtime/scene_controller.py); an app
entry point that calls it is not. See
[show_control_architecture.md](show_control_architecture.md#3-scene-lifecycle).

---

## D-002: Audio processing owns timing, not lighting decisions

**Status:** Accepted and implemented — [`audio/beat_source.py`](../backend/audio/beat_source.py)
is the lighting-side protocol; [`audio/audio_engine_source.py`](../backend/audio/audio_engine_source.py)
adapts `lights-audio-engine`. `backend/audio/` does not import `models` or `storage`.
Detection itself lives in the other repository.

**Context.** The audio subsystem could plausibly be given responsibility for
"reacting" — mapping levels straight to channel values. The intended design says it
publishes BPM, beat events, count, and intensity, and nothing else.

**Rationale.** Any component that both analyses audio and decides fixture output is
untestable without a microphone and a rig. Publishing timing keeps the analysis pure
and makes the entire show-control layer testable with a synthetic beat list.

**Consequences.** The audio module must not import from `backend/models/` or
`backend/storage/`. Beat events, not BPM, are the sequencing input, which means
tempo drift needs no resync logic (D-003). Level-reactive effects (intensity →
dimmer) are deliberately deferred — they would reintroduce the coupling. The app
factory may subscribe the adapter to the show command queue; that is wiring, not
analysis.

**Alternatives.** Direct audio-to-fixture mapping (rejected: untestable, and it
duplicates what LEDfx already does well for LED strips).

**Follow-up.** Per-scene sensitivity was unused and dropped in schema 5. Engine
threshold stays in `AudioEngine` until a later config owns it. See
[audio_reactivity_architecture.md](audio_reactivity_architecture.md#51-sensitivity).

---

## D-003: DMX and WLED share one beat-sequencing implementation

**Status:** **Accepted and implemented** —
[`runtime/sequencer.py`](../backend/runtime/sequencer.py).

**Context.** Both cue lists advance on beats, hold entries for a configured number of
beats, and loop. The obvious shortcut is to implement counting inside each output
controller.

**Rationale.** Two implementations of the same state machine drift. Bug fixes and
loop-behaviour changes get applied to one and not the other, and the two paths then
behave differently in ways that are very hard to diagnose during a show.

**Consequences.** One `CueSequencer` class, instantiated once per cue list, with no
knowledge of its consumer — it reports the new cue id and nothing more. This required
the two cue lists to have the *same entry shape*, so `beats` was added to
`DMX_Preset_List` and normalised on `WLED_Preset_List` in one change
([AF-H02](audit_findings.md#af-h02)). It is fully unit-testable with no I/O, and the
resulting suite is the highest-value one in the project.

**Confirmed in practice.** Sharing the class cost nothing: the two outputs differ in
what `apply()` does, not in when it is called, so the sequencer never needed to know
which it was feeding.

**Alternatives.** Per-controller counting (rejected as above); a global tick that
both consult (rejected: makes independent cue-list lengths awkward).

**Follow-up.** Neither cue list can currently express beat duration.

---

## D-004: LEDfx owns WLED output

**Status:** Accepted — supplied project requirement; no WLED or LEDfx code exists.

**Context.** The application could render pixels itself and push them to WLED over
DDP or the WLED JSON API, or it could delegate to LEDfx and only select presets.

**Rationale.** LEDfx already solves effect rendering, audio reactivity for strips,
device management, and virtual-device grouping. Reimplementing that is a large
project with no payoff for this installation.

**Consequences.** The app's WLED responsibility reduces to "activate preset X when
the cue changes". It never generates pixel data and no documentation should imply it
does. LEDfx becomes a required external process, and its availability is a runtime
dependency that must degrade gracefully. Virtual-device layout is LEDfx's concern,
not a model in this repository.

**Alternatives.** Direct WLED control (rejected: scope); E1.31 to WLED alongside the
DMX universe (rejected: conflates two very different transports and discards LEDfx's
effect engine).

**Follow-up.** `WLED_Preset.id` is the LEDfx scene name ([D-018](#d-018-ledfx-preset-identifier-form));
`WLED_Preset_List` is registered; `Preset.wled_preset_list_id` references it (schema v2).
Per-entry beats and show-loop wiring remain open — [AF-H02](audit_findings.md#af-h02).

---

## D-005: Transient runtime state is never persisted

**Status:** Accepted — implemented.

**Context.** Universe buffers, cue indices, and beat counters change many times per
second. Preset definitions change when an operator edits them.

**Rationale.** Writing high-frequency state to disk destroys SSDs, makes every write
a potential corruption window, and confuses "what the show is configured to do" with
"what it is doing right now".

**Consequences.** `Active_DMX_Channels` and `Active_ILDA_Frame` are deliberately
absent from `RECORD_TYPES` ([`records.py:62-71`](../backend/storage/records.py#L62-L71))
and the docstring at [`Active_DMX_Channels.py:8`](../backend/models/Active_DMX_Channels.py#L8)
says so explicitly. State is lost on restart, which is correct — a restarted app has
no show running until a scene is selected.

**Alternatives.** Persisting the last universe state for restart continuity
(rejected: reintroduces the confusion, and the correct restart behaviour is
"no scene active").

**Follow-up.** `ui.last_scene_id` is a borderline case
([AF-L03](audit_findings.md#af-l03)). Once sequence state exists it must follow this
rule too.

---

## D-006: Stable definitions persist as normalized JSON collections

**Status:** Accepted — implemented.

**Context.** Options were a single document, one file per object, a relational
database, or one JSON file per model class holding an id-keyed map.

**Rationale.** The chosen approach — one file per collection, objects holding ids
rather than nested objects ([`library.py:82-88`](../backend/storage/library.py#L82-L88)) —
gives deduplication (a `Preset` used by two `Scene`s is stored once), human-readable
and diffable files, and no database dependency or server process. Appropriate for a
dataset that is tens to hundreds of records.

**Consequences.** Nothing can be reached by attribute traversal; everything goes
through `Library.get()`/`find()`. Referential integrity has to be enforced in
application code, which it is (D-015). The whole library is loaded into memory,
which is fine at this scale. Data lives outside the repository via `platformdirs`
([`paths.py:26-32`](../backend/storage/paths.py#L26-L32)), so no user data can leak
into git.

**Alternatives.** SQLite (rejected: adds a dependency and loses diffability at this
scale; reconsider only if the dataset grows by orders of magnitude); nested
documents (rejected: duplicates shared objects).

**Follow-up.** The runtime-model/record duplication cost is
[AF-M04](audit_findings.md#af-m04).

---

## D-007: E1.31 / sACN is the DMX transport

**Status:** Accepted — supplied project requirement; only a symbolic sender exists.

**Context.** The rig uses a custom DMX universe box that receives Ethernet traffic
and drives the physical DMX bus. Options are E1.31/sACN, Art-Net, or a USB DMX
interface.

**Rationale.** E1.31 is the stated intent for this hardware. It is a simple,
well-specified UDP protocol, standard across the industry, and keeps the sender
component trivially narrow: take 512 bytes, frame them, send them.

**Consequences.** The sender knows nothing about scenes, looks, or beats. The
universe box becomes an opaque endpoint defined only by IP and universe number
([fixture_and_transport_strategy.md](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary)).
Multi-universe becomes an addressing question rather than a hardware one. A network
library dependency will be required.

**Alternatives.** Art-Net (viable; the box's actual protocol has not been verified
from the repository); USB DMX (rejected: the hardware is networked).

**Follow-up.** `DMXConfig` carries `universe` (default **1**), `host`, `port`, and
`priority`, recovered from the previous version of the app's config file
([AF-M06](audit_findings.md#af-m06)). **Universe 1 and a single-universe rig are
confirmed**; E1.31 is addressed to the **network switch** (static IP from the switch
manual in local `config.json` only —
[fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary)).
**Unicast** to the switch IP ([D-017](#d-017-sacn-unicast-versus-multicast)); `source_name`
is on `DMXConfig`. Box **blackouts when packets stop**
([§6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary)). A symbolic
sender ([`runtime/sender.py`](../backend/runtime/sender.py)) exists and defaults to
`NullTransport`; no E1.31 packet is framed or sent.

---

## D-008: ILDA stays behind a separate processor boundary

**Status:** Accepted for the boundary; the processor itself does not exist.

**Context.** Laser output is safety-critical, lower priority, and technically
unrelated to DMX and WLED.

**Rationale.** Keeping it behind one interface means the rest of the system can be
built, tested, and run with zero laser code in the process, and a laser fault cannot
affect the lighting rig.

**Consequences.** `Scene.ilda_frame_list_id` is the only coupling. `.ild` files are
stored as opaque blobs and never parsed
([`ilda_blobs.py:62-66`](../backend/storage/ilda_blobs.py#L62-L66)) — so the app also
cannot validate content, which is a real limitation, not just a simplification.
`Active_ILDA_Frame` is in memory and unpersisted, consistent with D-005.

**Alternatives.** Integrating laser control into the DMX path (rejected: entirely
different data and hazard model).

**Follow-up.** No output code may be added until the prerequisites in
[laser_and_haze_safety.md](laser_and_haze_safety.md#4-what-must-exist-before-output-is-enabled)
are met.

---

## D-009: Basement deployment is the immediate target

**Status:** Accepted — supplied project requirement, not evidence of an implemented
deployment.

**Context.** The system could be built for one known installation or as
general-purpose lighting software.

**Rationale.** One room, one rig, one operator, one network. Every unknown that a
general product must handle is a known constant here.

**Consequences.** Fixture definitions can describe the actual rig rather than a
profile library. Unicast to one known IP is sufficient. Discovery, multi-user, and
remote access are all out of scope. Hardware assumptions can be verified by
measurement instead of by specification.

**Alternatives.** Building general from the start (rejected: see D-010).

**Follow-up.** Record the actual rig — fixtures, addresses, universe, box IP — in
configuration, not in code. No IPs or hostnames belong in the repository.

---

## D-010: Basement reliability outranks generality

**Status:** Proposed.

**Context.** A recurring temptation in lighting software is to build the abstraction
first — profile libraries, plugin transports, multi-protocol output layers.

**Rationale.** The failure mode of premature generality here is specific and
predictable: abstractions built to satisfy imagined requirements, none exercised,
all of them making the real path harder to debug at 1 a.m. with the rig running.

**Consequences.** Prefer one concrete implementation with a narrow seam (D-013) over
a plugin architecture. Prefer a fixture table describing this rig over a fixture
profile database. Defer semantic parameters until raw channel values demonstrably
hurt. Generalise only when a second real requirement appears.

**Alternatives.** Building the general system first (rejected).

**Follow-up.** Re-evaluate at the end of [roadmap.md](roadmap.md#phase-8--operator-ui-and-recovery-behaviour).

---

## D-011: Hold between scenes, blackout on clean shutdown

**Status:** **Accepted and implemented** — `engine.stop()` sends zeros before
`E131Transport.close()`, which repeats the blackout and then terminates the stream.

**Context.** When a scene is deactivated, the DMX universe buffer either keeps its
values or is zeroed.

**Rationale.** Holding avoids a visible black gap on every scene change, which is
what an operator wants mid-show. Blacking out on clean exit avoids leaving the rig
lit with nothing controlling it.

**Consequences.** Deactivation is cheap: `SceneController.deactivate()` drops both
sequencers and touches no output, so the buffer keeps the last look. Shutdown does
the opposite in two places ([F-05](audit_findings.md#f-05) closed): `engine.stop()`
zeroes the buffer and hands one final frame to the transport while the socket is
still open, and `E131Transport.close()` repeats the blackout and then sends a
Stream_Terminated frame. A test asserts the last frame before close is all zeros.
Note the remaining shutdown ordering hazard: the sender is stopped before the show
thread is joined, so a blackout *command* racing shutdown can still be dropped
([F-09](audit_findings.md#f-09)), and `stop-server.ps1`'s force-kill bypasses the
lifespan entirely ([F-04](audit_findings.md#f-04)) — though the box blacking out on
packet loss covers that case. LEDfx needs an equivalent explicit action
([wled_ledfx_architecture.md](wled_ledfx_architecture.md#64-shutdown)) since it
keeps rendering regardless.

**Alternatives.** Blackout on every deactivation (rejected: visible gap); hold
always, including on exit (rejected: rig stays lit after the app closes).

**Follow-up.** The universe box **blackouts when packets stop**
([§6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary)), so a
crash stops DMX output without a final frame. Clean-shutdown blackout
(`E131Transport.close()`, engine `stop()`) remains required for a controlled exit,
Stream_Terminated semantics, and LEDfx coordination
([wled_ledfx_architecture.md](wled_ledfx_architecture.md#64-shutdown)).

---

## D-012: Network failures must not reach persistent state

**Status:** Proposed.

**Context.** Output components fail routinely — the box is unplugged, LEDfx is not
running, the LAN drops.

**Rationale.** A transport failure is an expected operating condition, not an
exceptional one. It must never be able to modify or corrupt the operator's scenes
and presets.

**Consequences.** The E1.31 sender and the LEDfx client hold no `Library` reference
and never write to disk. Send failures are logged and retried, never fatal. The show
keeps running with a degraded output path. This also means a failed output cannot
"clean up" configuration on the way down.

**Alternatives.** Recording device state back into config on failure (rejected:
couples transport health to persistent data).

**Follow-up.** Requires the logging that does not exist yet
([AF-M08](audit_findings.md#af-m08)).

---

## D-013: Hardware output defaults to a null implementation

**Status:** Accepted for the DMX path (`NullTransport`); LEDfx still defaults off via
`LedfxConfig.enabled`.

**Context.** Development happens without the rig powered on, and tests must never
emit anything.

**Rationale.** Making null the *default* rather than an opt-in means no test run,
no debugging session, and no accidental import can transmit a packet or an HTTP
call. Opting in to real output is a deliberate act.

**Consequences.** The DMX path is `DmxTransport` with `NullTransport` as the only
implementation. A real E1.31 class is not in the tree. Config still carries
destination fields, but nothing reads them for a socket.

**Alternatives.** Real-by-default with a test flag (rejected: one forgotten flag
sends real traffic).

**Follow-up.** Real sACN is implemented behind `dmx.transport = "e131"` (WS-4.4); hardware
sign-off remains. See [project_overview.md § Next steps](project_overview.md#next-steps-priority-order).

---

## D-019: Send-on-change + keepalive cadence

**Status:** Accepted — implemented in the operator server.

**Context.** A fixed-cadence sender alone blows the 13 ms software budget (scene
selection → sender): polling
at 40 Hz adds 12.5 ms average queueing before a changed buffer leaves the machine.
The old transport doc assumed a tick-driven loop.

**Decision.** Hybrid cadence: wake immediately when the universe buffer changes
(`publish()` sets `dmx_dirty`); re-send on a keepalive timeout when idle so a
receiver that missed a packet can recover. `SenderThread` owns the wait loop;
`DmxTransport.send` is the only output seam.

**Consequences.** [`runtime/active.py`](../backend/runtime/active.py) exposes
`publish()` and `dmx_dirty`. [`runtime/sender.py`](../backend/runtime/sender.py)
implements the thread. Keepalive interval comes from `DMXConfig.refresh_hz` (still
defaults to 120 Hz — [AF-L01](audit_findings.md#af-l01) recommends lowering once a
real transport exists). Latency is measured to the transport `send()` call (p99 ≤ 13 ms
from scene selection — `LATENCY_BUDGET_US` in [`server/latency.py`](../backend/server/latency.py)),
so swapping `NullTransport` for `E131Transport` does not change the instrumentation
shape.

**Alternatives.** Fixed tick only (rejected: violates latency budget). Change-only
with no keepalive (rejected: fragile over UDP).

**Follow-up.** Real transport must preserve this wake model; only `DmxTransport`
changes.

---

## D-020: Hand-rolled E1.31 framing

**Status:** **Accepted and implemented** — [`runtime/e131.py`](../backend/runtime/e131.py).

**Context.** WS-4.4 needed to frame 512 DMX slots into E1.31 DATA packets. Options
were a library (`sacn`, `python-sacn`) or hand-rolled bytes (638-byte layout).

**Decision.** Hand-rolled framing in `runtime/e131.py` with byte-asserted unit tests.
Keeps the send-on-change wake fully under our control and avoids a new production
dependency for a layout that never changes.

**Consequences.** `E131Transport` in [`runtime/sender.py`](../backend/runtime/sender.py)
calls the framer and owns the UDP socket. Tests inject a fake socket — no real packets
in CI. The CID is derived from the source name via UUID5, so it survives restarts
without being stored. The `sacn` library remains the fallback if framing maintenance
becomes costly.

**Alternatives.** `sacn` library (viable; adds a dependency and its own threading).
Art-Net (rejected: wrong protocol for this hardware).

**Follow-up.** [D-017](decisions.md#d-017-sacn-unicast-versus-multicast) is settled:
unicast to the switch IP. `dmx.transport` stays `"null"` until deliberate opt-in.
Checklist in [current_sprint.md § 4.4](current_sprint.md#44-real-sacn-sender--next-hardware-milestone).

---

## D-014: Fixtures become first-class persisted objects

**Status:** Proposed — the single most important pending change.

**Context.** DMX start addresses are currently derived by packing device states
contiguously in `order` sequence
([`active.py:37-49`](../backend/runtime/active.py#L37-L49)); no fixture definition
exists.

**Rationale.** The physical rig's patch is a stable fact about the installation and
belongs in one place. Deriving it per look means the rig is redescribed in every
look, with no source of truth to check against the fixtures' DIP switches.

**Consequences.** A new `fixtures` collection (id, name, universe, start_address,
channel_count); `DMX_Device_Preset.order` becomes `fixture_id`. Address gaps and
multiple universes become expressible. Integrity checking and cascade delete work
automatically once the relationship is added to `REFERENCES` (D-015). Requires a
schema migration — the machinery exists and snapshots first
([`migrations.py:66`](../backend/storage/migrations.py#L66)).

**Alternatives.** Keeping positional derivation (rejected: [AF-H01](audit_findings.md#af-h01));
adding a full fixture-profile library now (rejected: D-010 — identity and addressing
first, semantics later).

**Follow-up.** This is the recommended next implementation branch, and it needs the
storage test suite ([AF-H05](audit_findings.md#af-h05)) in place first.

---

## D-015: The reference graph stays declarative

**Status:** Accepted — implemented, and worth protecting explicitly.

**Context.** The object graph could be traversed by hand-written code per operation.

**Rationale.** `REFERENCES` in [`records.py:91-103`](../backend/storage/records.py#L91-L103)
declares every relationship as `(attribute, child collection, is_list)`. Integrity
checking, cascade delete, orphan pruning, and referrer lookup are all driven from it.
One table, four behaviours.

**Consequences.** Adding a relationship is a one-line change that makes all four work
correctly. Hand-rolling traversal anywhere else would silently bypass them. The
declaration order in `COLLECTION_ORDER` (leaves first) is load-bearing and must be
maintained when collections are added.

**Alternatives.** Per-operation traversal (rejected: four places to get wrong);
an ORM (rejected: D-006).

**Follow-up.** Every schema change in this document — fixtures, cue entries,
`WLED_Preset_List` registration — must go through this table.

---

## D-016: Audio event delivery mechanism

**Status:** Accepted (2026-08-19).

**Decision.** **Queue.** Detected beats enter the show as `ShowCommand(BEAT)` on the
existing command queue. The capture worker (blocking `InputStream.read`, not a
PortAudio callback) must not run lighting logic. `AudioEngineBeatSource` notifies
subscribers on that worker; the app factory subscriber only calls
`ShowEngine.submit` with `put_nowait`. `SceneController.on_beat()` runs on the show
thread. Manual tap uses the same command kind.

**Rationale.** Isolates PortAudio from cue sequencing, LEDfx HTTP, and universe
writes. One show thread already owns `SceneController` without a lock; another
producer on that queue is the seam WS-9 needed. A callback into the controller from
the capture thread would put lighting on the audio path and reintroduce the races
in [show_control_architecture.md](show_control_architecture.md#6-concurrency-and-race-conditions).

**Consequences.** A full 64-slot queue drops the beat (`ShowBusyError`) rather than
blocking capture. Detected beats currently share that queue with activate,
deactivate, and blackout. Mid-cue beats still exercise the F-01 ack-by-position
path. Those are residual risks under dense live audio, not a reason to move
lighting onto the capture thread.

**Alternatives.** Callback-on-audio-thread (rejected: a slow listener causes
dropouts). A second dedicated beat queue (possible later if operator commands are
starved).

**Follow-up.** Operator-visible silence vs dead capture, and whether beats should
have reserved queue slots. See
[audio_reactivity_architecture.md](audio_reactivity_architecture.md#6-timing-ownership-and-event-delivery).

---

## D-017: sACN unicast versus multicast

**Status:** Accepted (2026-08-17).

**Decision.** **Unicast** to the network switch IP (`dmx.host`). One known receiver on
a home LAN: no IGMP snooping concerns, no multicast flooding to unrelated devices,
trivially debuggable. `DMXConfig.mode` defaults to `"unicast"`. The code still
supports `"multicast"` for other rigs; this installation does not use it.

**Verified (2026-08-16).** Single universe, universe **1**; E1.31 destination is
the **network switch** (static IP from the switch manual in local `config.json` only);
box **blackouts when packets stop**. See
[fixture_and_transport_strategy.md §6](fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).

---

## D-018: LEDfx preset identifier form

**Status:** Accepted.

**Decision.** A `WLED_Preset` maps to a **LEDfx scene**. `WLED_Preset.id` is the
LEDfx scene **name** (e.g. `"Living Room"`). Available scenes are polled from
`GET http://127.0.0.1:8888/api/scenes` every 25 seconds and missing names are
auto-inserted into the `wled_presets` collection. Activation uses the LEDfx slug
id resolved in memory from the latest list (`PUT /api/scenes` with
`{"id": "<slug>", "action": "activate"}`). Scenes removed in LEDfx are not
auto-deleted from storage.

**Rationale.** Names are what the operator sees and edits in LEDfx; storing them
as the preset id keeps cue lists human-readable and avoids a second identifier
field. Slugs are only needed for the activate call and can be refreshed each poll.

**Consequences.** `WLED_Preset` no longer uses a generated UUID. Cue lists that
name a scene deleted in LEDfx keep a dangling-but-valid library id until the
operator cleans them up. See
[wled_ledfx_architecture.md](wled_ledfx_architecture.md#31-preset-identifiers).

---

## D-022: Empty cue lists cannot be authored

**Status:** Accepted and implemented — [`AuthoringService`](../backend/authoring/service.py)
refuses empty lists on create/update, and refuses a force-delete that would empty a
still-referenced list.

**Context.** `SceneController.activate` rejects a scene whose DMX or WLED cue list
has no entries. If authoring allowed those lists (or let a delete empty them while a
preset still pointed at them), the library could hold shows that can never run.

**Rationale.** Playability is an authoring invariant, not only a runtime check. An
empty list is never a valid intermediate state an operator meant to persist.

**Consequences.** Cue lists are non-empty by construction. Duplicates within a list
remain allowed (`A B A C`). Force-delete of the last look or LEDfx name in a list
that a `Preset` still references is a `conflict`, not a silent empty-out. HTTP maps
that to 409.

**Alternatives.** Allow empty lists and fail at activation (rejected: the operator
would store unplayable shows).

**Follow-up.** Per-entry beats ([WS-3.5](current_sprint.md#35-per-entry-beat-counts))
does not change this; a list with zero entries is still unplayable.

---

## D-023: A look is a dmx_preset

**Status:** Accepted.

**Context.** Docs and conversation used **look** for one static lighting state across
the DMX rig. The stored type is [`DMX_Preset`](../backend/models/DMX_Preset.py)
(`dmx_presets`). Calling the same object a look, a DMX preset, and a preset made the
graph harder to follow than the code.

**Rationale.** The collection name is the name. New writing should say `dmx_preset`
(or `DMX_Preset` for the type), not "look". Older pages may still say look; treat
that as this object.

**Consequences.** Cue lists hold `dmx_preset_ids`. Authoring routes are
`/api/dmx-presets`. A lighting `Preset` is a different layer (DMX list + WLED list).

**Alternatives.** Keep "look" as the docs term (rejected: it is not in the model).

**Follow-up.** Historical audits keep their original wording; they are not rewritten.
