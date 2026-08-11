# Architecture

The primary architecture document. Assumes the terminology defined in
[project_overview.md](project_overview.md#key-terminology).

Throughout, **Current** describes code that exists in the repository today and
**Target** describes proposed design that does not. Nothing marked Target has been
implemented.

---

## 1. Architectural goals

1. A scene selection must never construct a network packet directly. Layers between
   them are what make the system testable.
2. Audio processing publishes *timing*. It does not decide what any light does.
3. DMX and WLED must share one beat-sequencing concept, not two parallel
   implementations that drift.
4. Stable definitions (scenes, looks, cue lists, fixtures, network config) are
   persisted. High-frequency runtime state (universe buffer, cue index, beat count)
   is never written to disk.
5. Every hardware-touching component must be runnable against a null/simulated
   implementation so the show can be developed without the rig powered on.
6. Optimize for one basement installation. Generality is a later concern —
   see [decisions.md](decisions.md#d-010-basement-reliability-outranks-generality).

---

## 2. Current architecture

### 2.1 What physically exists

```text
backend/
├── config/
│   └── config.py            Compile-time defaults; seeds LedfxConfig in AppConfig
├── ledfx/
│   ├── client.py            HTTP adapter + NullLedFxClient
│   ├── scene_sync.py        Polls LEDfx; upserts WLED_Preset names
│   └── service.py           build_ledfx_stack factory
├── logging_setup.py         File + stderr logging into data-folder logs/
├── models/                  Runtime pydantic models (11 files)
│   ├── Scene.py
│   ├── Preset.py            wled_preset_list_id → WLED_Preset_List
│   ├── DMX_Preset_List.py
│   ├── DMX_Preset.py
│   ├── DMX_Device_Preset.py
│   ├── WLED_Preset.py       id = LEDfx scene name
│   ├── WLED_Preset_List.py  registered in storage (schema v2)
│   ├── ILDA_Frame_List.py
│   ├── ILDA_Frame.py
│   ├── Active_DMX_Channels.py
│   └── Active_ILDA_Frame.py
├── runtime/
│   └── active.py            Module-global live state + look flattening (82 lines)
└── storage/
    ├── paths.py             Data-folder layout, platformdirs
    ├── json_store.py        Atomic write, corrupt-file quarantine
    ├── records.py           On-disk schemas + the reference graph (9 collections)
    ├── library.py           In-memory object graph, CRUD, integrity, cascade
    ├── migrations.py        Schema v2; v1→v2 wraps wled_preset_id in lists
    ├── ilda_blobs.py        .ild file storage, id validation
    ├── config.py            AppConfig (dmx/ledfx/ilda/audio/ui)
    └── archive.py           Zip export/import with traversal guards

tests/                       pytest storage suite (temp data root)
pytest.ini                   pythonpath = backend
```

There is no `__init__.py` anywhere. Imports are absolute from the `backend/`
directory (`from models.Scene import Scene`). `pytest.ini` sets `pythonpath = backend`
for tests; see [platform_support.md](platform_support.md#import-root).

### 2.2 Current module dependency graph

```mermaid
flowchart TD
    active["runtime/active.py"]
    ledfx["ledfx/*.py"]
    library["storage/library.py"]
    records["storage/records.py"]
    jsonstore["storage/json_store.py"]
    paths["storage/paths.py"]
    migrations["storage/migrations.py"]
    cfg["storage/config.py"]
    devcfg["config/config.py"]
    blobs["storage/ilda_blobs.py"]
    archive["storage/archive.py"]
    models["models/*.py"]

    ledfx --> library
    ledfx --> models
    active --> library
    active --> models
    active --> records
    active --> jsonstore
    library --> models
    library --> records
    library --> jsonstore
    library --> migrations
    library --> cfg
    library --> blobs
    library --> paths
    archive -.->|"deferred import<br/>to break a cycle"| migrations
    migrations --> jsonstore
    migrations --> paths
    cfg --> jsonstore
    cfg --> migrations
    cfg --> paths
    cfg --> devcfg
    blobs --> jsonstore
    blobs --> paths
    jsonstore --> paths
```

Dependency direction is clean and acyclic. The one latent cycle
(`archive` ↔ `migrations`) is broken with a deliberate function-local import and
documented in place at [`archive.py:71`](../backend/storage/archive.py#L71). This
is a genuine strength — see [audit_findings.md](audit_findings.md#confirmed-strengths).

### 2.3 Current data model

```mermaid
classDiagram
    class Scene {
        +str id
        +str preset_id
        +str ilda_frame_list_id
        +float sensitivity
    }
    class Preset {
        +str id
        +str dmx_preset_list_id
        +str wled_preset_list_id
    }
    class DMX_Preset_List {
        +str id
        +List~str~ dmx_preset_ids
    }
    class DMX_Preset {
        +str id
        +List~str~ dmx_device_preset_ids
    }
    class DMX_Device_Preset {
        +str id
        +int order
        +int channel_count
        +List~int~ channel_values
    }
    class WLED_Preset_List {
        +str id
        +List~str~ wled_preset_ids
        +int beats
    }
    class WLED_Preset {
        +str id
    }
    class ILDA_Frame_List {
        +str id
        +List~str~ ilda_frame_ids
    }
    class ILDA_Frame {
        +str id
    }

    Scene --> Preset : preset_id
    Scene --> ILDA_Frame_List : ilda_frame_list_id
    Preset --> DMX_Preset_List : dmx_preset_list_id
    Preset --> WLED_Preset_List : wled_preset_list_id
    DMX_Preset_List --> DMX_Preset : dmx_preset_ids[]
    DMX_Preset --> DMX_Device_Preset : dmx_device_preset_ids[]
    WLED_Preset_List --> WLED_Preset : wled_preset_ids[]
    ILDA_Frame_List --> ILDA_Frame : ilda_frame_ids[]
```

This graph is declared once, canonically, in
[`storage/records.py`](../backend/storage/records.py) as the `REFERENCES` table and
is what drives integrity checks, cascade delete, orphan pruning and referrer lookup.
Encoding the schema as data rather than as traversal code is the strongest design
decision in the repository.

Remaining structural gaps:

- **Beat duration is unrepresented.** No entry in either cue list carries a per-entry
  beat count. `WLED_Preset_List.beats` is a single scalar on the whole list.
- **No fixture identity.** DMX addresses are still derived positionally in
  [`runtime/active.py`](../backend/runtime/active.py).

### 2.4 Current DMX address derivation

This is the most consequential piece of current logic. From
[`runtime/active.py:23-50`](../backend/runtime/active.py#L23-L50):

```mermaid
flowchart TD
    A["DMX_Preset"] --> B["fetch each DMX_Device_Preset"]
    B --> C["sort by .order"]
    C --> D["cursor = 0"]
    D --> E["copy channel_values into the buffer<br/>from cursor to cursor + channel_count"]
    E --> F["cursor += channel_count"]
    F --> G{"more devices?"}
    G -->|yes| E
    G -->|no| H["512-value list"]
```

**A device's DMX start address is the sum of the `channel_count` of every device
before it.** It is not stored anywhere. Consequences:

| Consequence | Why it matters |
| --- | --- |
| No stable device identity | The same physical fixture is a *different* `DMX_Device_Preset` row in every look, with no shared key. Nothing links them. |
| Addressing is duplicated per look | The rig's patch is implicitly restated in every `DMX_Preset`, with no single source of truth to check against the fixtures' actual DIP switches. |
| One edit re-addresses a whole look | Changing one device's `channel_count` silently shifts every subsequent device in that look, and *only* in that look — the rig's looks then disagree with each other. |
| Address gaps cannot be expressed | A real patch with a fixture at 1 and the next at 20 has no representation; devices must be contiguous. |
| Single universe only | `Active_DMX_Channels` is one 512-value list and `build_channels` raises when the cursor exceeds 512 ([`active.py:40-45`](../backend/runtime/active.py#L40-L45)). |

This is finding [AF-H01](audit_findings.md#af-h01) and the single highest-value
thing to fix.

### 2.5 Current runtime state

[`runtime/active.py:19-20`](../backend/runtime/active.py#L19-L20) declares two
module-level mutable singletons:

```python
active_dmx_channels = Active_DMX_Channels()
active_ilda_frame = Active_ILDA_Frame()
```

Correctly marked as never persisted (`Active_DMX_Channels` is absent from
`RECORD_TYPES`, and its docstring says so explicitly). But:

- They are process globals with no owner, no lifecycle, and no locking. Once an
  audio thread and a sender thread exist, this becomes a data race —
  see [AF-M03](audit_findings.md#af-m03).
- `update_active_dmx_channels` **replaces** `.channels` with a new list. A consumer
  holding the model object sees updates; a consumer that cached `.channels`
  directly does not. The docstring's "rebuilt in place" is true of the model, not
  of the list.
- The `index: int = 0` parameter on `active_dmx_preset_id` and `active_ilda_frame_id`
  is the explicit seam left for beat sequencing — the docstrings say *"Audio input
  will pick the index later"* ([`active.py:54`](../backend/runtime/active.py#L54)).
  That seam is where the Target beat sequencer plugs in.

### 2.6 Current persistence boundaries

| State | Where it lives today | Correct? |
| --- | --- | --- |
| Scenes, presets, cue lists, device states | JSON in `data/*.json` | Yes |
| App config (dmx/wled/ilda/audio/ui) | `config.json` | Yes |
| `.ild` blobs | `ilda/*.ild`, id = filename | Yes |
| Universe buffer | Module global, never written | Yes |
| Active ILDA frame | Module global, never written | Yes |
| Cue index, beat count, BPM | *does not exist* | n/a |
| `ui.last_scene_id` | `config.json` | Borderline — this is session state in the config file. Acceptable for a single-operator app; noted as [AF-L03](audit_findings.md#af-l03). |

The separation is already correct in principle. One violation of read/write
purity: `Library.load()` calls `sync_ilda_folder(persist=True)`, so **opening the
library writes files** ([`library.py:134-135`](../backend/storage/library.py#L134-L135),
[`library.py:449-451`](../backend/storage/library.py#L449-L451)). See
[AF-M05](audit_findings.md#af-m05).

---

## 3. Target architecture

### 3.1 System context

```mermaid
flowchart LR
    OP(["Operator"])
    MIC(["Audio source<br/>line-in or loopback"])

    subgraph APP["Lights App"]
        UI["Operator UI"]
        CORE["Show control core"]
    end

    BOX["DMX universe box<br/>(custom hardware)"]
    FIX["DMX fixtures"]
    LEDFX["LEDfx<br/>(separate process)"]
    WLED["WLED controllers"]
    STRIP["LED strips"]
    ILDA["ILDA laser<br/>NOT ENABLED"]

    OP --> UI --> CORE
    MIC --> CORE
    CORE -->|"E1.31 / sACN<br/>UDP"| BOX
    BOX -->|"DMX512"| FIX
    CORE -->|"HTTP REST"| LEDFX
    LEDFX -->|"WLED protocol"| WLED --> STRIP
    CORE -.->|"deferred"| ILDA
```

The two transports are independent and must not be conflated: **E1.31 carries DMX
universe data; LEDfx owns everything about WLED output.** The application never
generates WLED pixel data — see
[wled_ledfx_architecture.md](wled_ledfx_architecture.md).

### 3.2 Target component boundaries

```mermaid
flowchart TD
    SC["Scene Controller<br/>owns current scene + lifecycle"]
    AP["Audio Processor<br/>publishes BPM / beats / intensity"]
    LPR["Lighting Preset Resolver<br/>Scene → DMX cue list + WLED cue list"]
    BSC["Beat Sequence Controller<br/>one implementation, two instances"]

    subgraph DMXC["DMX Controller"]
        DPR["Look Resolver"]
        ADS["Active DMX State<br/>universe buffers"]
        E131["E1.31 Sender"]
    end
    subgraph WLEDC["WLED Controller"]
        LFC["LEDfx API Client"]
    end
    subgraph ILDAC["ILDA Controller"]
        ILP["ILDA Processor (stub)"]
    end

    LIB["Library<br/>persistence, read-mostly at runtime"]

    SC --> AP
    SC --> LPR
    LPR --> LIB
    AP -->|"beat events"| BSC
    SC --> BSC
    BSC -->|"cue index changed"| DPR
    BSC -->|"cue index changed"| LFC
    DPR --> LIB
    DPR --> ADS
    ADS --> E131
    SC --> ILP
```

**Component responsibilities** (all Target; none exist today):

| Component | Owns | Must not |
| --- | --- | --- |
| Scene Controller | Current scene, activate/deactivate, propagating sensitivity | Know about channels, packets, or HTTP |
| Audio Processor | BPM, beat events, intensity, silence detection | Know about fixtures, presets, or devices |
| Lighting Preset Resolver | Turning `Scene` → concrete cue lists via `Library` | Cache runtime sequence state |
| Beat Sequence Controller | Cue index, beats elapsed, loop/reset rules | Know whether it drives DMX or WLED |
| Look Resolver | Turning a `DMX_Preset` + fixture patch → channel writes | Own the buffer or the socket |
| Active DMX State | Universe buffers, dirty tracking | Perform I/O |
| E1.31 Sender | Packet framing, sequence numbers, cadence, socket lifecycle | Interpret presets or fixtures |
| LEDfx API Client | HTTP calls, retry, dedup, connection state | Decide *when* to change preset |
| ILDA Processor | Frame handling behind an explicit safety gate | Emit anything until the gate exists |

The critical rule: **the Beat Sequence Controller is one class instantiated twice**
(once per cue list), not two implementations. Duplicating it is how DMX and WLED
sequencing drift apart. See
[decisions.md](decisions.md#d-003-dmx-and-wled-share-one-beat-sequencing-implementation).

### 3.3 Target scene activation flow

```mermaid
sequenceDiagram
    participant OP as Operator
    participant SC as Scene Controller
    participant LIB as Library
    participant AP as Audio Processor
    participant BD as DMX Sequencer
    participant BW as WLED Sequencer
    participant ADS as Active DMX State
    participant LFC as LEDfx Client

    OP->>SC: select scene
    SC->>SC: deactivate previous scene
    SC->>LIB: read Scene, Preset, cue lists
    LIB-->>SC: resolved definitions
    SC->>AP: set sensitivity
    SC->>BD: load DMX cue list, reset to index 0
    SC->>BW: load WLED cue list, reset to index 0
    BD->>ADS: apply look at index 0
    BW->>LFC: activate LEDfx preset at index 0
    Note over SC,LFC: scene is now active — audio drives it from here
```

Deactivation must be explicit and deterministic: reset both sequencer indices,
clear beat counters, and decide the DMX blackout policy. The repository defines
none of this today — see
[show_control_architecture.md](show_control_architecture.md#3-scene-lifecycle).

### 3.4 Target beat-driven sequencing

```mermaid
flowchart TD
    A["beat event from Audio Processor"] --> B["beats_elapsed += 1"]
    B --> C{"beats_elapsed >=<br/>entry.beats?"}
    C -->|no| Z["no output change"]
    C -->|yes| D["beats_elapsed = 0"]
    D --> E["index += 1"]
    E --> F{"index past end?"}
    F -->|"loop"| G["index = 0"]
    F -->|"hold"| H["index = last"]
    G --> I["emit cue-changed"]
    H --> I
    F -->|"in range"| I
    I --> J["consumer applies new cue"]
```

The consumer differs (universe buffer write vs. LEDfx HTTP call) but the state
machine above is identical and belongs in one place. Note it emits on *change
only* — a beat that does not advance the index must not produce an HTTP call. See
[wled_ledfx_architecture.md](wled_ledfx_architecture.md#61-call-deduplication).

### 3.5 Target DMX / E1.31 output flow

```mermaid
flowchart TD
    A["DMX cue index changed"] --> B["DMX_Preset (look)"]
    B --> C["for each device state:<br/>look up fixture by device_id"]
    C --> D["fixture gives universe +<br/>start address + profile"]
    D --> E["write values into the universe buffer<br/>from start_address onward"]
    E --> F["mark universe dirty"]
    F --> G["E1.31 Sender tick"]
    G --> H["frame packet:<br/>seq no, priority, source name,<br/>universe, 512 slots"]
    H --> I["UDP to configured destination"]
    I --> J["DMX universe box"]
    J --> K["physical DMX512 bus"]

    style C fill:#ffe6e6
    style D fill:#ffe6e6
```

Steps shaded red do not exist. Today the chain stops at a positionally-packed
512-value list with no fixture lookup and no sender. Details and the open
questions on cadence, unicast/multicast, priority, and sequence numbering are in
[fixture_and_transport_strategy.md](fixture_and_transport_strategy.md).

### 3.6 Target WLED / LEDfx flow

```mermaid
flowchart TD
    A["WLED cue index changed"] --> B{"same LEDfx preset<br/>as currently active?"}
    B -->|yes| C["do nothing"]
    B -->|no| D["LEDfx API Client"]
    D --> E["HTTP call to LEDfx<br/>for each mapped virtual device"]
    E --> F{"success?"}
    F -->|yes| G["record active preset"]
    F -->|no| H["log, keep last known state,<br/>retry with backoff"]
    G --> I["LEDfx renders → WLED → strips"]
```

The application's responsibility ends at "tell LEDfx which preset to run". It does
not generate pixels and must not be documented as doing so.

### 3.7 Current versus target, side by side

```mermaid
flowchart TB
    subgraph T["Target"]
        direction TB
        t1["Scene Controller"] --> t2["Audio Processor"]
        t1 --> t3["Preset Resolver"]
        t2 --> t4["Beat Sequencer x2"]
        t3 --> t4
        t4 --> t5["Look Resolver + Fixture patch"]
        t5 --> t6["Universe buffers"]
        t6 --> t7["E1.31 Sender"]
        t4 --> t8["LEDfx Client"]
        t1 --> t9["ILDA Processor"]
    end
    subgraph C["Current"]
        direction TB
        c1["(no controller)"]
        c2["(no audio)"]
        c3["Library.get chain<br/>in active.py"]
        c4["index: int = 0<br/>placeholder param"]
        c5["build_channels<br/>positional packing"]
        c6["one global 512 list"]
        c7["(no sender)"]
        c8["(no client)"]
        c9["(blob storage only)"]
        c3 --> c4 --> c5 --> c6
    end
```

---

## 4. Known architectural debt

Full detail with severities in [audit_findings.md](audit_findings.md). Summary:

| # | Debt | Impact |
| --- | --- | --- |
| 1 | No fixture/device identity; addresses derived positionally | Blocks correct multi-look rigs and any second universe |
| 2 | Beat duration absent from cue-list entries | Blocks beat-driven sequencing |
| 3 | Show loop absent; LEDfx client unwired | No automatic preset activation |
| 4 | Model/record duplication with hand-written converters | Every field change requires multiple edits |
| 5 | Module-global runtime state, no concurrency story | Will race once audio and sender threads exist |
| 6 | No value-range validation on DMX or sensitivity fields | Out-of-range values reach the wire unclamped |
| 7 | Storage tests only; no runtime/output coverage | Show loop changes still unverified |
| 8 | Logging exists but no app entry point calls `configure_logging()` yet | Failures visible once a process starts |

Item 4 deserves nuance: separating the on-disk schema (`records.py`) from the
runtime model (`models/`) is a *legitimate and deliberate* choice — it lets the
persisted format evolve independently under `migrations.py`. The cost is currently
paid in hand-written converters. That cost is acceptable now and should be
revisited only if the model grows substantially.

---

## 5. Migration principles

Rules for moving from Current to Target without a rewrite:

1. **Additive schema changes first.** Add `Fixture` and beat fields as new
   collections/fields with defaults; bump `SCHEMA_VERSION` and register a step in
   [`migrations.py`](../backend/storage/migrations.py). The snapshot-before-migrate
   machinery already exists and works.
2. **Keep `REFERENCES` canonical.** Any new relationship goes in
   [`records.py`](../backend/storage/records.py) first; integrity, cascade, and
   pruning then work for free. Never hand-roll traversal.
3. **Tests before transport.** No socket code lands before there is a test that
   asserts on generated bytes without opening a socket.
4. **Null implementations before real ones.** Every output component gets a
   no-op/dry-run variant that the default config selects, so nothing emits
   accidentally.
5. **Never persist transient state.** If a value changes on a beat, it does not go
   in a JSON collection.
6. **One sequencer.** Resist adding beat logic to either output controller.
7. **The universe box is opaque.** Do not encode assumptions about its internals;
   configure it as an IP address and a universe number.
