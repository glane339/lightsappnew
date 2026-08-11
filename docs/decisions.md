# Architecture Decision Log

Each decision is **Accepted** (implemented in the repository or fixed by the
supplied project requirements), **Proposed** (a recommendation from the architecture
review, not yet adopted), or **Open** (a choice that must be made and cannot be
inferred from the repository or supplied requirements).

Format: Decision · Status · Context · Rationale · Consequences · Alternatives ·
Follow-up.

| ID | Decision | Status |
| --- | --- | --- |
| [D-001](#d-001-scene-is-the-top-level-manually-selected-unit) | Scene is the top-level manually selected unit | Accepted |
| [D-002](#d-002-audio-processing-owns-timing-not-lighting-decisions) | Audio processing owns timing, not lighting decisions | Proposed |
| [D-003](#d-003-dmx-and-wled-share-one-beat-sequencing-implementation) | DMX and WLED share one beat-sequencing implementation | Proposed |
| [D-004](#d-004-ledfx-owns-wled-output) | LEDfx owns WLED output | Accepted |
| [D-005](#d-005-transient-runtime-state-is-never-persisted) | Transient runtime state is never persisted | Accepted |
| [D-006](#d-006-stable-definitions-persist-as-normalized-json-collections) | Stable definitions persist as normalized JSON collections | Accepted |
| [D-007](#d-007-e131--sacn-is-the-dmx-transport) | E1.31/sACN is the DMX transport | Accepted |
| [D-008](#d-008-ilda-stays-behind-a-separate-processor-boundary) | ILDA stays behind a separate processor boundary | Accepted |
| [D-009](#d-009-basement-deployment-is-the-immediate-target) | Basement deployment is the immediate target | Accepted |
| [D-010](#d-010-basement-reliability-outranks-generality) | Basement reliability outranks generality | Proposed |
| [D-011](#d-011-hold-between-scenes-blackout-on-clean-shutdown) | Hold between scenes, blackout on clean shutdown | Proposed |
| [D-012](#d-012-network-failures-must-not-reach-persistent-state) | Network failures must not reach persistent state | Proposed |
| [D-013](#d-013-hardware-output-defaults-to-a-null-implementation) | Hardware output defaults to a null implementation | Proposed |
| [D-014](#d-014-fixtures-become-first-class-persisted-objects) | Fixtures become first-class persisted objects | Proposed |
| [D-015](#d-015-the-reference-graph-stays-declarative) | The reference graph stays declarative | Accepted |
| [D-016](#d-016-audio-event-delivery-mechanism) | Audio event delivery mechanism | Open |
| [D-017](#d-017-sacn-unicast-versus-multicast) | sACN unicast versus multicast | Open |
| [D-018](#d-018-ledfx-preset-identifier-form) | LEDfx preset identifier form | Accepted |

---

## D-001: Scene is the top-level manually selected unit

**Status:** Accepted — supplied project requirement, partially represented by the
data model; scene activation is not implemented.

**Context.** Something has to be the unit an operator picks. `Scene` sits at the top
of the reference graph: it is a `ROOT_COLLECTION`
([`records.py:87`](../backend/storage/records.py#L87)), nothing references it, and
everything else is reachable from it. It holds exactly the three things the intended
design calls for — a lighting preset, an ILDA frame list, and a sensitivity value
([`models/Scene.py`](../backend/models/Scene.py)).

**Rationale.** Manual selection removes an entire class of complexity: no cue stacks,
no timecode, no automatic transitions, no scheduling. The operator is the sequencer
at the top level; audio is the sequencer within a scene.

**Consequences.** Orphan pruning is anchored on scenes
([`library.py:365-388`](../backend/storage/library.py#L365-L388)), so anything a
scene cannot reach is collectable. Scene activation is the only entry point to the
runtime. There is no concept of layering two scenes.

**Alternatives.** A cue stack with fades (rejected: unnecessary for the target
installation); timecode-driven playback (rejected: no timecode source).

**Follow-up.** Scene *activation* is not implemented — only the model exists. See
[show_control_architecture.md](show_control_architecture.md#3-scene-lifecycle).

---

## D-002: Audio processing owns timing, not lighting decisions

**Status:** Proposed — no audio code exists.

**Context.** The audio subsystem could plausibly be given responsibility for
"reacting" — mapping levels straight to channel values. The intended design says it
publishes BPM, beat events, count, and intensity, and nothing else.

**Rationale.** Any component that both analyses audio and decides fixture output is
untestable without a microphone and a rig. Publishing timing keeps the analysis pure
and makes the entire show-control layer testable with a synthetic beat list.

**Consequences.** The audio module must not import from `backend/models/` or
`backend/storage/`. Beat events, not BPM, are the sequencing input, which means
tempo drift needs no resync logic (D-003). Level-reactive effects (intensity →
dimmer) are deliberately deferred — they would reintroduce the coupling.

**Alternatives.** Direct audio-to-fixture mapping (rejected: untestable, and it
duplicates what LEDfx already does well for LED strips).

**Follow-up.** Sensitivity semantics are undefined — see
[AF-M02](audit_findings.md#af-m02) and
[audio_reactivity_architecture.md](audio_reactivity_architecture.md#51-sensitivity).

---

## D-003: DMX and WLED share one beat-sequencing implementation

**Status:** Proposed — no sequencer exists.

**Context.** Both cue lists advance on beats, hold entries for a configured number of
beats, and loop. The obvious shortcut is to implement counting inside each output
controller.

**Rationale.** Two implementations of the same state machine drift. Bug fixes and
loop-behaviour changes get applied to one and not the other, and the two paths then
behave differently in ways that are very hard to diagnose during a show.

**Consequences.** One `BeatSequencer` class, instantiated once per cue list, with no
knowledge of its consumer — it emits "cue changed" and nothing more. Requires the
two cue lists to have the *same entry shape*, which is why the beat-field fix
([AF-H02](audit_findings.md#af-h02)) must be applied to DMX and WLED together. It is
fully unit-testable with no I/O and is the highest-value test suite in the project.

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

**Status:** Accepted — supplied project requirement; no transport code exists.

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

**Follow-up.** `DMXConfig` lacks a destination, unicast/multicast setting, source
name, and priority; `universe` defaults to an invalid 0
([AF-M06](audit_findings.md#af-m06)). **The box's actual expectations are
unverified** and must be confirmed before this is marked Accepted.

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

**Status:** Proposed — no evidence in the repository either way.

**Context.** When a scene is deactivated, the DMX universe buffer either keeps its
values or is zeroed.

**Rationale.** Holding avoids a visible black gap on every scene change, which is
what an operator wants mid-show. Blacking out on clean exit avoids leaving the rig
lit with nothing controlling it.

**Consequences.** Deactivation is cheap; the sender keeps transmitting the last look
until the next scene loads. Shutdown must explicitly write zeros and send one final
frame *before* closing the socket. LEDfx needs an equivalent explicit action
([wled_ledfx_architecture.md](wled_ledfx_architecture.md#64-shutdown)) since it keeps
rendering regardless.

**Alternatives.** Blackout on every deactivation (rejected: visible gap); hold
always, including on exit (rejected: rig stays lit after the app closes).

**Follow-up.** Depends on what the universe box does when packets stop — unverified.
An abnormal termination cannot send a blackout frame, so if the box holds last
values, a crash leaves the rig lit.

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

**Status:** Proposed.

**Context.** Development happens without the rig powered on, and tests must never
emit anything.

**Rationale.** Making null the *default* rather than an opt-in means no test run,
no debugging session, and no accidental import can transmit a packet or an HTTP
call. Opting in to real output is a deliberate act.

**Consequences.** Each output path defines a narrow interface with a null, a
recording, and a real implementation. Config selects; the default is null. This is
what makes the whole system developable and testable with no hardware, and it is a
precondition for any laser work.

**Alternatives.** Real-by-default with a test flag (rejected: one forgotten flag
sends real traffic).

**Follow-up.** Nothing implements this yet — it must land with the first output
component. See [current_sprint.md](current_sprint.md#ws-6--hardware-independent-testing).

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

**Status:** **Open.**

Callback-on-audio-thread versus a queue drained by a show-control thread. Recommended:
queue, so lighting logic never runs on the real-time audio callback. Blocks the
threading design. See
[audio_reactivity_architecture.md](audio_reactivity_architecture.md#6-timing-ownership-and-event-delivery).

---

## D-017: sACN unicast versus multicast

**Status:** **Open.**

Recommended: unicast to the box's configured IP — one known receiver, no IGMP
concerns, trivially debuggable. Cannot be settled until the box's actual
expectations are verified. See
[fixture_and_transport_strategy.md](fixture_and_transport_strategy.md#52-open-transport-decisions).

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
