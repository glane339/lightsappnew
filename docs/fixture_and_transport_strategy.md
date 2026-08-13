# Fixture and Transport Strategy

How DMX data is modelled, addressed, held in memory, and (eventually) put on the
wire. Companion to [architecture.md](architecture.md).

> **Status: model implemented; E1.31 packets absent.** Looks resolve into
> [`Active_DMX_Channels`](../backend/models/Active_DMX_Channels.py) by patched
> address. [`runtime/sender.py`](../backend/runtime/sender.py) is a symbolic sender:
> `DmxTransport` + `NullTransport` + a send-on-change/keepalive thread. There is no
> packet framing, no socket, and no UDP. Everything in §5 (the real sACN path) remains
> Target.

---

## 1. Current device model

There is no device model. There is only a *device state*:

```python
# backend/models/DMX_Device_Preset.py
class DMX_Device_Preset(BaseModel):
    id: str
    order: int
    channel_count: int
    channel_values: List[int]
```

A `DMX_Preset` (a **look**) owns a list of these
([`models/DMX_Preset.py`](../backend/models/DMX_Preset.py)). That is the entire DMX
data model.

Note what is **not** present anywhere in the repository:

- device / fixture identity (`device_id`)
- device name
- universe assignment
- DMX start address
- fixture profile or channel layout
- semantic parameters (dimmer, red, green, blue, pan, tilt, strobe)

### 1.1 How addressing actually works today

From [`runtime/active.py:23-50`](../backend/runtime/active.py#L23-L50), device
states are sorted by `order` and packed contiguously from channel 0:

```python
channels = [0] * UNIVERSE_SIZE
cursor = 0
for device in devices:
    ...
    channels[cursor : cursor + device.channel_count] = values
    cursor += device.channel_count
```

**A device's start address is the running sum of the `channel_count` of every
device before it.** The docstring states this explicitly, so it is intentional
rather than accidental. It is nevertheless the repository's most significant
architectural problem.

| Problem | Detail |
| --- | --- |
| **No cross-look identity** | The same physical fixture is a distinct `DMX_Device_Preset` row in every look, with nothing linking them. Renaming, re-patching, or replacing a fixture means editing every look by hand. |
| **The patch is restated per look** | There is no single source of truth to compare against the fixtures' physical DIP switches. Two looks can silently disagree about the rig. |
| **Fragile under edit** | Changing one device's `channel_count` re-addresses every subsequent device in that look only. |
| **Gaps are inexpressible** | A real patch (fixture at 1, next at 20) cannot be represented; devices must be contiguous from channel 0. |
| **Raw values only** | `channel_values` is an opaque `List[int]`. Nothing knows that index 3 is "red". |
| **One universe** | `Active_DMX_Channels` is a single 512-value list; `build_channels` raises when the cursor exceeds 512 ([`active.py:40-45`](../backend/runtime/active.py#L40-L45)). |

Tracked as [AF-H01](audit_findings.md#af-h01).

### 1.2 Raw versus semantic: what the repository does

**Raw channel values, exclusively.** No semantic parameter appears anywhere. To be
clear about what this means in practice: setting a wash light to red requires
knowing, out of band, that its third channel is red, and writing
`channel_values = [255, 255, 0, 0]` by hand.

The current approach is not *wrong* for a small fixed rig — raw values are simple,
have no profile-database dependency, and always work. It is the missing *identity*
and *address*, not the missing semantics, that cause the problems in §1.1. Semantic
profiles are a recommendation (§3), not a prerequisite.

---

## 2. Current active DMX state

```python
# backend/models/Active_DMX_Channels.py
UNIVERSE_SIZE = 512

class Active_DMX_Channels(BaseModel):
    """The one channel map the DMX sender reads. Rebuilt in place, never persisted."""
    channels: List[int] = Field(default_factory=lambda: [0] * UNIVERSE_SIZE)
```

A single module-level instance lives at
[`runtime/active.py:19`](../backend/runtime/active.py#L19). Correctly excluded from
`RECORD_TYPES` and therefore never written to disk — the persistence boundary here
is right, and the docstring says so. Gaps:

- **No dirty tracking.** Every update rebuilds all 512 values, so change-only
  transmission is impossible without adding it.
- **No merge semantics.** A look fully replaces the buffer; channels not covered by
  any device state are forced to 0. There is no concept of layering or of leaving a
  channel untouched.
- **No clamping.** `channel_values` is `List[int]` with no `0..255` constraint, and
  `build_channels` truncates and pads the list length but never checks values.
  A stored `300` or `-1` will be copied straight into the buffer.
  See [AF-M01](audit_findings.md#af-m01).
- **Single universe** (§1.1).
- **No lock**, and it is a process global — see
  [show_control_architecture.md](show_control_architecture.md#6-concurrency-and-race-conditions).

---

## 3. Target fixture model

**Implemented**, as `DMX_Device` rather than `Fixture` — the name matches the existing
`DMX_*` models and the term the rig owner uses.

```text
DMX_Device                       persisted root collection — the rig's patch
├── id
├── name                         "front wash L"
├── model                        "chauvet_gigbar_move" → docs/fixtures/<model>.md
├── mode                         the manual's max-channel mode name
├── universe                     1.. (only 1 is rendered today)
├── start_address                1..512
└── channel_count                1..512

DMX_Device_Preset                a device's values inside one look
├── id
├── device_id                    replaces positional `order`
└── channel_values
```

Per-channel semantics are **documented, not stored** — see
[docs/fixtures/](fixtures/README.md). `model` is the link between the two.

Why this specific shape:

- It removes `order`-based address derivation without changing the storage
  architecture. `fixture_id` becomes one more entry in the `REFERENCES` table in
  [`records.py`](../backend/storage/records.py) and integrity checking, cascade
  delete, and orphan pruning then work for it automatically.
- `channel_count` moves to the fixture, where it belongs — it is a property of the
  hardware, not of a look.
- Multi-universe falls out for free: the universe is a fixture property, so a look
  can span universes with no change to the look model.
- Semantic profiles can be added later as an optional `profile_id`, without
  reworking anything.

**Migration path.** Landed as the schema v2 → v3 step in
[`migrations.py`](../backend/storage/migrations.py): one `DMX_Device` per distinct
`order`, addressed by the old packing rule so existing looks resolve to the same
channels, then device states rewritten to point at it. Where looks disagreed on
`channel_count` for the same `order`, the widest claim wins so no device loses
channels.

**Fixture profiles** (mapping `dimmer`/`red`/`green`/`blue`/`pan`/`tilt`/`strobe`
to channel offsets) are a genuine convenience for a rig with a handful of fixture
types, but they are a *second* step. Getting identity and addressing right is what
unblocks everything else. Do not build a profile library before the patch exists.

---

## 4. Target universe state

```text
ActiveUniverses
└── per universe number:
    ├── channels[512]
    ├── dirty: bool
    └── last_sent_at
```

The important behaviours to add alongside it:

- **Clamp on write** to `0..255`. Do it at the buffer boundary so no path can put
  an invalid value on the wire, in addition to model-level validation.
- **Dirty flag per universe**, set on write and cleared on send — the prerequisite
  for any change-detection strategy in §7.
- **Explicit blackout**, so shutdown and deactivation policies
  ([show_control_architecture.md](show_control_architecture.md#32-deactivation))
  have something to call.

---

## 5. E1.31 / sACN transport

> **Nothing below is implemented.** The symbolic sender in
> [`runtime/sender.py`](../backend/runtime/sender.py) stops at `NullTransport.send`.
> There is no sACN library in [`requirements.txt`](../requirements.txt), no socket
> call, and no packet code anywhere in the repository. This section documents intent
> and the open decisions, and deliberately makes no claim about how the receiving
> hardware behaves.

E1.31 (ANSI E1.31, "sACN") carries DMX512 universe data over UDP. Its role in this
system is narrow: **take a 512-byte universe buffer and put it on the network.** It
knows nothing about scenes, looks, fixtures, or beats.

```mermaid
flowchart LR
    A["universe buffer<br/>512 values"] --> B["E1.31 Sender"]
    B --> C["UDP datagram<br/>port 5568"]
    C --> D["DMX universe box"]
    D --> E["DMX512 bus"] --> F["fixtures"]
```

### 5.1 Current configuration surface

```python
# backend/storage/config.py
class DMXConfig(BaseModel):
    universe: int = Field(default=1, ge=1, le=63999)
    host: str = "127.0.0.1"
    port: int = Field(default=5568, ge=1, le=65535)
    priority: int = Field(default=100, ge=0, le=200)
    interface: Optional[str] = None
    refresh_hz: int = Field(default=120, ge=1)
```

`host`, `port`, and `priority` were recovered from the previous version of the app's
config file, which is the only record of what the rig was actually driven with;
`universe` was corrected from an invalid 0 at the same time
([AF-M06](audit_findings.md#af-m06)). **None of it is verified against the universe
box** — it is a starting point recovered from history, not a tested configuration.

What still needs attention:

| Field | Issue |
| --- | --- |
| `host = "127.0.0.1"` | Loopback, so this is whatever the old app was tested against rather than the box's real address. Unicast/multicast selection is still not expressible. |
| `interface` | Ambiguous: is this a local NIC to bind to, or a destination? Both are needed and this is one field. |
| `refresh_hz = 120` | Physical DMX512 tops out near 44 Hz for a full 512-slot frame. 120 Hz of E1.31 traffic cannot be reproduced on the bus and will be coalesced or dropped by the gateway. [AF-L01](audit_findings.md#af-l01) |

Still absent: unicast/multicast selection, source name, and per-universe destination
mapping. Slot count is deliberately not configurable — it is `UNIVERSE_SIZE`, fixed
by the protocol, where the old config restated it as `total_channels: 512`.

### 5.2 Open transport decisions

Each of these needs a recorded decision before code is written. None can be
answered from the repository.

| Decision | Options | Note |
| --- | --- | --- |
| **Unicast vs multicast** | Unicast to the box's IP; multicast to `239.255.x.y` derived from universe | **Unicast recommended** for a single known receiver on a home LAN: no IGMP snooping concerns, no multicast flooding to unrelated devices, trivially debuggable. Multicast is for rigs with many receivers. |
| **Destination** | Static IP in config; discovery | Static. Discovery is unnecessary complexity for one box. |
| **Universe numbering** | Must match the box's expectation | **Unverified.** Do not guess. |
| **Cadence** | Continuous at N Hz; on change only; hybrid | **Decided — hybrid** ([D-019](decisions.md#d-019-send-on-change--keepalive-cadence)): implemented in `SenderThread`; keepalive from `DMXConfig.refresh_hz` |
| **Sequence numbers** | Per-universe `uint8`, incrementing, wrapping | Required by the protocol for out-of-order detection. Must be per universe. |
| **Priority** | Default 100 | Only matters with multiple sources. Expose it, default it, do not agonise over it. |
| **Source name** | A stable, human-readable CID/name | Helps enormously when sniffing traffic. Pick one and keep it constant. |
| **Library vs hand-rolled** | `sacn`, `python-sacn`; or build the packet | A library is the right call — the packet layout, CID handling, and sequence semantics are fiddly and already solved. Adding one is a new production dependency and therefore out of scope for this documentation task. |

### 5.3 Error handling and shutdown

Requirements for the **real** transport (`E131Transport`, not yet in the tree):

- **A network failure must never touch persistent configuration.** The sender has
  no reason to hold a `Library` reference at all. See
  [decisions.md](decisions.md#d-012-network-failures-must-not-reach-persistent-state).
- **Send errors are logged and retried, never fatal.** A transient `ENETUNREACH`
  should not take the show down.
- **Explicit start and stop.** The transport owns a socket; shutdown must be
  idempotent.
- **Clean shutdown sends a blackout frame**, then closes. Otherwise the box holds
  the last received values indefinitely and the rig stays lit after the app exits.

`NullTransport` today satisfies none of the wire requirements by design — it only
proves the wake path.

### 5.4 Next: actual E1.31 transport (WS-4.4)

The symbolic half is done. Adding real output should **not** rewrite `SenderThread`.

| Step | Work |
| --- | --- |
| 1. Verify box | Answer §6 questions; settle [D-017](decisions.md#d-017-sacn-unicast-versus-multicast); add `source_name` and transport mode to `DMXConfig` (WS-4.3) |
| 2. Framing | New [`runtime/e131.py`](../backend/runtime/e131.py): `build_data_packet()`, sequence wrap, CID from source name ([D-020](decisions.md#d-020-hand-rolled-e131-framing)) |
| 3. Transport | `E131Transport` in [`runtime/sender.py`](../backend/runtime/sender.py): `send()` + `close()`; inject socket in tests |
| 4. Opt-in | Default remains `NullTransport`; config flag enables `E131Transport` only after manual box test |
| 5. Accept | Byte tests without real UDP; p99 ≤ 10 ms with transport enabled; shutdown blackout verified on hardware |

Full checklist: [current_sprint.md § 4.4](current_sprint.md#44-real-sacn-sender--next-hardware-milestone).

---

## 6. The custom universe box boundary

The repository contains **no information whatsoever** about the custom DMX universe
box — no firmware, no schematic, no protocol notes, no IP, no model number.

It is therefore treated as an opaque network endpoint characterised entirely by:
an IP address, the universe number(s) it listens for, and whether it expects
unicast or multicast. Nothing about its internal PCB, refresh behaviour, buffering,
or failure modes should be documented or assumed until it is measured.

Three things need to be established empirically and written down here:

1. What universe number(s) does it accept?
2. Does it require multicast, or accept unicast?
3. What does it do when packets stop — hold last values, or blackout?

Question 3 determines whether the shutdown-blackout requirement in §5.3 is
essential or merely tidy.

---

## 7. Change detection

This is now implemented, symbolically, in [`SenderThread`](../backend/runtime/sender.py):
`publish()` sets `dmx_dirty`, the sender wakes immediately, and a keepalive timeout
re-sends the last buffer. The transport it calls is still `NullTransport`. The
diagram below is the same policy a real E1.31 class will inherit.

```mermaid
flowchart TD
    A["sender tick"] --> B{"universe dirty?"}
    B -->|yes| C["send frame, clear dirty,<br/>increment sequence"]
    B -->|no| D{"keepalive interval elapsed?"}
    D -->|yes| C
    D -->|no| E["skip"]
```

This gives immediate response on cue changes, bounded idle traffic, and recovery
for a receiver that rebooted — without either flooding the network or risking a
silently-stale rig.

---

## 8. Hardware abstraction, simulation, and testing

This is the part that makes the rest safe to develop. The symbolic half exists
**before** any real sender.

The live interface is `DmxTransport.send(channels)` plus `SenderThread.start()` /
`stop()`, with one implementation today:

| Implementation | Purpose | Default? |
| --- | --- | --- |
| `NullTransport` | Counts frames, opens no socket | **Yes** — nothing transmits |
| `RecordingDmxSender` | Captures frames in memory for assertions | Test only (not a named class; tests use a local fake) |
| Real E1.31 transport | The actual packet path | **Not present** — parked on universe-box verification |

With that in place, the testable surface without any hardware or network is:

- `build_channels` / look resolution → expected 512-value buffer, including the
  over-512 error path at [`active.py:40-45`](../backend/runtime/active.py#L40-L45)
  which is currently untested.
- Fixture address resolution → correct slot ranges, gap handling, multi-universe.
- Clamping and padding behaviour on malformed `channel_values`.
- Packet framing → assert on generated bytes with `RecordingDmxSender`; never open
  a socket in a unit test.
- Dirty/keepalive logic → drive a fake clock, assert on send counts.

**No test in this repository should ever transmit a real packet.** Integration
against the physical box is a manual, deliberate activity. See
[current_sprint.md](current_sprint.md#ws-6--hardware-independent-testing).

---

## 9. Failure behaviour summary

| Failure | Required behaviour |
| --- | --- |
| Destination unreachable | Log once, keep retrying, keep the show running. Never crash. |
| Socket creation fails at startup | Surface clearly; fall back to `NullTransport` rather than exiting. |
| Look references a missing fixture | Reject at load time via the `REFERENCES` integrity check, not at send time. |
| Channel value out of range | Clamp at the buffer boundary and log. Never transmit invalid data. |
| App exits | Blackout frame, then close the socket (§5.3). |
| App crashes | The box holds its last state — behaviour unverified (§6). A watchdog is out of scope for now. |
