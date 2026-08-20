# Frontend Architecture

Plan for WS-11.2: the full operator UI in `frontend/`. The M1 page
([`frontend/index.html`](../frontend/index.html)) is a scene picker plus latency harness;
this document replaces it with two modes — **Performance** (run the show) and
**Builder** (author the show graph).

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](decisions.md#d-023-a-look-is-a-dmx_preset).

Mutations go through the [authoring API](authoring.md). The UI is a thin client: no
parallel graph logic in JavaScript. Show activation stays on `/ws/show` and
`/api/show/*`.

**Status:** Planned — not implemented. Backend gaps listed in [§ Backend additions](#backend-additions).

---

## 1. Two modes

| Mode | Purpose | Primary transport |
| --- | --- | --- |
| **Performance** | Select and activate scenes during a show | WebSocket `/ws/show` |
| **Builder** | Create device presets, looks, cue lists, and scenes | REST [authoring API](authoring.md) |

The home landing page offers exactly two choices. Performance is the show surface;
Builder is authoring. The M1 latency readout moves to a separate diagnostics page
(see [§ Performance mode](#3-performance-mode)).

---

## 2. Routes and file layout

FastAPI already serves `frontend/` as static files with `html=True`
([`backend/server/app.py`](../backend/server/app.py)). WS-11.2 stays **no-build**
(multi-page HTML + shared CSS/JS), matching M1.

| Path | Mode | Role |
| --- | --- | --- |
| `/` | Home | Performance vs Builder |
| `/performance/` | Performance | Scene grid + beat indicator |
| `/builder/gigbar2/` | Builder | GigBAR 2 device presets (`23CH`) |
| `/builder/keobin/` | Builder | Keobin device presets (`18CH`) |
| `/builder/dmx-presets/` | Builder | Pair GigBAR + Keobin into one look |
| `/builder/dmx-preset-lists/` | Builder | Ordered DMX cue list + beats |
| `/builder/wled-preset-lists/` | Builder | Ordered WLED cue list + beats |
| `/builder/scenes/` | Builder | Pair DMX + WLED lists into a scene |
| `/diag/` | Ops | Latency harness (optional; moved from M1) |

Proposed tree:

```text
frontend/
├── index.html                 # Home: Performance | Builder
├── performance/index.html
├── builder/
│   ├── gigbar2/index.html
│   ├── keobin/index.html
│   ├── dmx-presets/index.html
│   ├── dmx-preset-lists/index.html
│   ├── wled-preset-lists/index.html
│   └── scenes/index.html
├── diag/index.html            # M1 latency readout (optional)
├── css/app.css
├── js/
│   ├── api.js                 # Authoring REST client
│   ├── show.js                # WebSocket control plane
│   ├── drag-list.js           # Shared reorder UI
│   └── fixtures/
│       ├── chauvet_gigbar_2.js
│       └── keobin_light_bar.js
```

Builder pages share one chrome: sidebar in **leaf-to-root order** (device presets →
looks → cue lists → scenes), matching the creation hierarchy in [authoring.md](authoring.md).

---

## 3. Performance mode

### Scene grid

- Load scenes from `GET /api/scenes`.
- Large tappable tiles labelled by scene `id` (human slug or short UUID).
- Tap → `{"t":"activate","id":"<scene-id>"}` on `/ws/show`.
- Active tile highlighted from server `state` events (`active_scene_id`, `is_active`).
- Small **Deactivate** and **Blackout** controls (same WebSocket commands as M1).

### Beat indicator

A bar across the top of the page flashes on each beat — the visual metronome.

- **Today:** the server pushes `{t:"beat"}` for both a manual tap and a detected
  beat. Performance must flash from that event, not from a local key-up.
- **Still missing:** BPM, level, and silence-versus-dead capture. Those are WS-9
  remainder, not a second beat path.

Do not put the M1 µs latency panel on this page; it distracts during a show.

---

## 4. Builder mode — show graph

### Creation flow

```text
GigBAR channels  →  gigbar2 page   ↘
Keobin channels  →  keobin page    →  dmx_presets  →  dmx_preset_lists  ↘
LEDfx scene names (sync)           →  wled_preset_lists                 →  Scene
```

The API also has a **lighting preset** (`Preset`) that pairs one DMX cue list with
one WLED cue list. The Scenes builder page hides it: on save, find an existing
`Preset` with the same pair of list ids, or `POST /api/presets`, then
`POST /api/scenes`.

| Builder page | Stored as | Authoring endpoints |
| --- | --- | --- |
| GigBAR 2 / Keobin | `DMX_Device_Preset` | `/api/dmx-device-presets` |
| dmx_presets | `DMX_Preset` | `/api/dmx-presets` |
| dmx_preset_lists | `DMX_Preset_List` | `/api/dmx-preset-lists` |
| wled_preset_lists | `WLED_Preset_List` | `/api/wled-preset-lists` |
| scenes | `Scene` (+ hidden `Preset`) | `/api/presets`, `/api/scenes` |

Build from the leaves up — every parent stores ids of objects that already exist
([authoring.md § Hierarchy](authoring.md#hierarchy)).

### 4.1 GigBAR 2 presets (`/builder/gigbar2/`)

**Device:** `chauvet_gigbar_2`, mode `23CH`, 23 channels — see
[chauvet_gigbar_2.md](fixtures/chauvet_gigbar_2.md). Patched at universe 1,
channels 1–23 ([fixtures/README.md § Patch](fixtures/README.md#patch)).

**UI model:** section toggles and labelled controls, not 23 raw sliders. Channel
semantics live in a static fixture profile (`fixtures/chauvet_gigbar_2.js`)
transcribed from the markdown; the library stores only `channel_values`.

| Section | Controls |
| --- | --- |
| Par 1 / Par 2 | RGB + UV; dimmer/strobe (0–127 level, 128–239 strobe, 240–249 sound, 250–255 full) |
| Derby 1 / Derby 2 | Colour, strobe rate, rotation (dropdowns from value tables) |
| Laser | Colour, strobe, pattern/rotation |
| Strobe | Pattern; white **or** UV dimmer; speed |

**Off** = that section's channels zeroed. Enforce hardware rules in the editor:

- Each par: at most **3 of 4** colours active (manual constraint).
- Channels **21 and 22** are mutually exclusive (white vs UV strobe).

Save → `POST /api/dmx-device-presets` with the seeded GigBAR `device_id` and a
human slug `id` (e.g. `gigbar-red-wash`).

### 4.2 Keobin presets (`/builder/keobin/`)

**Device:** `keobin_light_bar`, mode `18CH`, 18 channels — see
[keobin_light_bar.md](fixtures/keobin_light_bar.md). Patched at channels 24–41.

| Section | Controls |
| --- | --- |
| Lasers | Four intensity sliders + motor |
| Magic ball 1 | RGBW |
| Magic ball 2 | RGB |
| Strobe | Mode (none / on / random / speed) + RGB + violet |

Channel **1** (special access / self-run / sound) defaults to a **not used** range
(000–030 or 211–255) so fixture timing stays under app beat control — see
[keobin_light_bar.md § Ch 1](fixtures/keobin_light_bar.md#ch-1--special-access).

Verify channels 15 vs 16 (red/green strobe LEDs) against hardware before relying on
the default ordering in the fixture doc.

### 4.3 dmx_presets (`/builder/dmx-presets/`)

One complete look across **both** rig fixtures:

- Name (`id` slug).
- Dropdown **GigBAR preset** — `GET /api/dmx-device-presets` filtered by GigBAR
  `device_id`.
- Dropdown **Keobin preset** — same, filtered by Keobin `device_id`.

Save → `POST /api/dmx-presets` with `{id, dmx_device_preset_ids: [gigbar_id, keobin_id]}`.
Both selections required.

### 4.4 dmx_preset_lists (`/builder/dmx-preset-lists/`)

- Name (`id` slug).
- **Beats per iteration** — integer ≥ 1; applies to **every** entry in the list
  (list-level `beats`, not per-entry — [AF-H02](audit_findings.md#af-h02)).
- Drag-and-drop ordered list of `dmx_preset` ids (palette from `GET /api/dmx-presets`).
- Duplicates allowed (`A B A C`). Empty list cannot be saved ([D-022](decisions.md#d-022-empty-cue-lists-cannot-be-authored)).

Save → `POST` or `PUT /api/dmx-preset-lists` with `{id, dmx_preset_ids, beats}`.

### 4.5 wled_preset_lists (`/builder/wled-preset-lists/`)

Same layout as DMX cue lists:

- Name, beats per iteration, drag-and-drop order.
- Palette from `GET /api/wled-presets` (each `id` is an LEDfx scene name — [D-018](decisions.md#d-018-ledfx-preset-identifier-form)).

**Auto-update:** background [`LedFxSceneSync`](../backend/ledfx/scene_sync.py) upserts
new scene names when `ledfx.enabled` is true (~25 s poll). The builder page should
poll `GET /api/wled-presets` on an interval while open. Optional one-shot refresh via
a future `POST /api/ledfx/refresh` (not implemented yet).

Names that disappear from LEDfx remain in the library if cue lists still reference them.

### 4.6 scenes (`/builder/scenes/`)

- Name (`id` slug).
- Dropdown **DMX preset list** — `GET /api/dmx-preset-lists`.
- Dropdown **WLED preset list** — `GET /api/wled-preset-lists`.
- Optional **sensitivity** (0.0–1.0; default from `AudioConfig.default_sensitivity`).

On save:

1. Find or create a `Preset` pairing the two list ids.
2. `POST /api/scenes` with `{id, preset_id, sensitivity?}`.

No ILDA field in v1. Test the scene in Performance mode after saving.

---

## 5. Shared client modules

| Module | Responsibility |
| --- | --- |
| `api.js` | Fetch wrappers, `{error: {code, message}}` handling, list CRUD |
| `show.js` | WebSocket connect/reconnect, `state` / `ack` / `beat` handlers |
| `drag-list.js` | Reorder cue entries; PUT merged `*_ids` + `beats` |
| `fixtures/*.js` | Section UI ↔ `channel_values[]` encode/decode |

**Performance** uses mostly `show.js`. **Builder** uses `api.js` plus fixture
profiles on the two device pages.

---

## 6. Backend additions

Small server changes to support the UI as designed:

| Item | Why | Status |
| --- | --- | --- |
| `{t:"beat"}` on `/ws/show` | Beat indicator must flash for live audio as well as a tap | **Done** — show thread emits `beat` for every `ShowCommand(BEAT)` |
| `POST /api/ledfx/refresh` | One-shot scene sync for WLED list builder | Not implemented |
| Scene save helper (optional) | `POST /api/scenes` accepting `dmx_preset_list_id` + `wled_preset_list_id` without exposing `Preset` ids | Not implemented |
| Fixture profiles in `frontend/js/fixtures/` | Transcribe [docs/fixtures/](fixtures/README.md) for editor UI; storage unchanged | Not implemented |

**Non-goals for v1:**

- Live preview of a look or cue on the rig from Builder (activation requires a full
  scene via Performance).
- Per-entry beat durations (deferred — [WS-2.2](current_sprint.md#22-add-per-entry-beat-durations-to-both-cue-lists)).
- React/Vite or another bundler (optional later; not required for basement scope).

---

## 7. Implementation order

1. **Shell** — home, builder nav, shared `api.js` / `app.css`; retire M1 as home.
2. **Fixture profiles + device editors** — GigBAR and Keobin pages.
3. **dmx_presets** — two dropdowns.
4. **Cue list pages** — shared drag-and-drop + beats (DMX and WLED).
5. **Scenes** — hidden `Preset` pairing.
6. **Performance** — scene grid + beat flash (needs `{t:"beat"}` for full behaviour).
7. **Diagnostics** — move M1 latency harness to `/diag/` if still needed. Budget:
   p99 ≤ 13 ms from scene selection to sender (`LATENCY_BUDGET_US` = 13 000 µs).

---

## 8. Related documents

| Topic | Document |
| --- | --- |
| HTTP contract for Builder | [authoring.md](authoring.md) |
| Channel tables (source of fixture profiles) | [fixtures/](fixtures/README.md) |
| Show activation semantics | [show_control_architecture.md](show_control_architecture.md) |
| LEDfx sync and WLED ids | [wled_ledfx_architecture.md](wled_ledfx_architecture.md) |
| Sprint task | [WS-11.2](current_sprint.md#112-frontend-application) |
| Server control plane | [server_plan/server_plan_combined.md](server_plan/server_plan_combined.md) |
| Latency budget (13 ms → sender) | [`server/latency.py`](../backend/server/latency.py) · [D-019](decisions.md#d-019-send-on-change--keepalive-cadence) |
