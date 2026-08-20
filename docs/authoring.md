# Authoring API

Contract for creating and editing the show graph. Performance is selection-only;
Builder ([WS-11.2](current_sprint.md#112-frontend-application),
[frontend_architecture.md](frontend_architecture.md)) is a thin client of these routes.

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](decisions.md#d-023-a-look-is-a-dmx_preset).

Mutations go through [`AuthoringService`](../backend/authoring/service.py). Route handlers do not call `Library.add()` ([D-015](decisions.md#d-015-the-reference-graph-stays-declarative), [D-022](decisions.md#d-022-empty-cue-lists-cannot-be-authored)).

## Hierarchy

A playable **scene** points at a **lighting preset**, which pairs one non-empty **DMX cue list** with one non-empty **WLED cue list**. Build from the leaves up: every parent stores ids of objects that already exist. The rig patch (`DMX_Device`) is seeded and read-only here.

```text
channel values → DMX_Device_Preset → DMX_Preset → DMX_Preset_List ↘
LEDfx name     → WLED_Preset                      → WLED_Preset_List → Preset → Scene
```

Do **not** nest children inside a parent create. `POST /api/presets` pairs two existing cue lists. `POST /api/scenes` only names a playable preset. A scene is refused unless the DMX side traces to at least one `dmx_device_preset` and the WLED side traces to registered LEDfx names.

## Ids

There is no separate `name` field on scenes, presets, or cue lists. `id` is optional on create; omit it for a generated hex UUID, or pass a human slug (`"red-wash"`). Slugs must be unique within the collection. `WLED_Preset.id` **is** the LEDfx scene name (e.g. `"Living Room"`) — [D-018](decisions.md#d-018-ledfx-preset-identifier-form).

## Errors

Every authoring failure uses one JSON shape:

```json
{"error": {"code": "not_found" | "invalid" | "conflict", "message": "..."}}
```

| `code` | HTTP | When |
| --- | --- | --- |
| `not_found` | 404 | The addressed object does not exist |
| `invalid` | 400 | Bad values, missing references, empty cue lists, unplayable preset |
| `conflict` | 409 | Duplicate id, delete while referenced, delete that would empty a still-referenced list |

Malformed JSON / wrong types still return FastAPI's 422. Show activation stays on `/api/show/*` and `/ws/show`.

## Endpoints

Devices have no write routes. ILDA is parked (`ilda_frame_list_id` is optional on scenes).

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/dmx-devices` | Patch, address order; includes `end_address` |
| GET/POST | `/api/dmx-device-presets` | One device's channel values. POST `{device_id, channel_values, id?}` |
| GET/PUT/DELETE | `/api/dmx-device-presets/{id}` | PUT replaces `channel_values`; the device does not change |
| GET | `/api/dmx-device-presets/{id}/delete-plan` | Cascade preview ([AF-H04](audit_findings.md#af-h04)) |
| GET/POST | `/api/dmx-presets` | POST `{dmx_device_preset_ids, id?}` — ids must already exist |
| GET/PUT/DELETE | `/api/dmx-presets/{id}` | PUT replaces the device-preset id list |
| GET | `/api/dmx-presets/{id}/delete-plan` | |
| GET/POST | `/api/dmx-preset-lists` | POST `{dmx_preset_ids, beats, id?}` |
| GET/PUT/DELETE | `/api/dmx-preset-lists/{id}` | PUT replaces `dmx_preset_ids` and beats together (reorder is an update) |
| GET | `/api/dmx-preset-lists/{id}/delete-plan` | |
| GET/POST | `/api/wled-presets` | POST `{name}` registers an LEDfx scene name |
| GET/DELETE | `/api/wled-presets/{id}` | No PUT; the name is the id |
| GET | `/api/wled-presets/{id}/delete-plan` | |
| GET/POST | `/api/wled-preset-lists` | POST `{wled_preset_ids, beats, id?}` — names must already be registered |
| GET/PUT/DELETE | `/api/wled-preset-lists/{id}` | |
| GET | `/api/wled-preset-lists/{id}/delete-plan` | |
| GET/POST | `/api/presets` | POST `{dmx_preset_list_id, wled_preset_list_id, id?}` — both lists must exist and be playable |
| GET/PUT/DELETE | `/api/presets/{id}` | PUT swaps list ids |
| GET | `/api/presets/{id}/delete-plan` | |
| GET | `/api/scenes` | Picker summaries: `id`, `preset_id` |
| POST | `/api/scenes` | Create; optional `id` slug |
| GET/PUT/DELETE | `/api/scenes/{id}` | PUT replaces `preset_id` (and optional `ilda_frame_list_id`) |
| GET | `/api/scenes/{id}/delete-plan` | |

POST create returns **201**. DELETE takes `?force=true` to cascade; without it, a referenced object is `409`. DELETE and delete-plan bodies:

```json
{
  "removes": [{"collection": "presets", "id": "..."}],
  "detaches": [{"collection": "dmx_preset_lists", "id": "...", "attribute": "dmx_preset_ids"}]
}
```

Editing a **running** scene: a preset swap applies on the next activation.

## Example payloads

### Save a device's channel values

```http
POST /api/dmx-device-presets
```

```json
{
  "id": "gigbar-red",
  "device_id": "<gigbar-id>",
  "channel_values": [255, 0, 0]
}
```

`channel_values` length must match the device's `channel_count`; each value is 0–255. The same device can have many device presets (one per `dmx_preset`, or reused across them).

### Create a dmx_preset from ordered device presets

```http
POST /api/dmx-presets
```

```json
{"id": "all-red", "dmx_device_preset_ids": ["gigbar-red", "keobin-red"]}
```

List order is the `dmx_preset`'s order. Universe placement still comes from each device's patched `start_address`, not this sequence. A `dmx_preset` holds one set of values per device — two rows for the same `device_id` is `invalid`. Every id must already exist; there is no inline channel-value create.

### Create a DMX cue list

```http
POST /api/dmx-preset-lists
```

```json
{"id": "wash-cycle", "dmx_preset_ids": ["all-red", "all-blue"], "beats": 4}
```

An empty `dmx_preset_ids` is `invalid` ([D-022](decisions.md#d-022-empty-cue-lists-cannot-be-authored)). Duplicates are allowed (`A B A C`).

### Register a WLED / LEDfx name (if sync has not already)

```http
POST /api/wled-presets
```

```json
{"name": "Living Room"}
```

### Create a WLED cue list

```http
POST /api/wled-preset-lists
```

```json
{"id": "strip-cycle", "wled_preset_ids": ["Living Room"], "beats": 2}
```

Each name must already be registered. Empty lists are `invalid`; duplicates are allowed.

### Create a lighting preset

```http
POST /api/presets
```

```json
{
  "id": "red-wash-stripes",
  "dmx_preset_list_id": "wash-cycle",
  "wled_preset_list_id": "strip-cycle"
}
```

Both lists must already exist, be non-empty, and (on the DMX side) trace to device presets. Nothing is saved unless both sides validate.

### Create a scene

```http
POST /api/scenes
```

```json
{"id": "red-wash", "preset_id": "red-wash-stripes"}
```

Omit `id` for a hex UUID. The preset's cue lists must be non-empty — the same rule `SceneController.activate` uses. Schema 5 dropped per-scene sensitivity.

Then activate with the existing control plane: `POST /api/show/activate` `{"id": "red-wash"}` or `{"t":"activate","id":"red-wash"}` on `/ws/show`.

## UI mapping (WS-11.2)

The [frontend architecture](frontend_architecture.md) maps builder pages to these
endpoints. Performance mode uses `/ws/show` (plus `GET /api/scenes` for the grid).

| Builder page | Primary endpoints |
| --- | --- |
| GigBAR 2 / Keobin | `GET/POST/PUT/DELETE /api/dmx-device-presets`, `GET /api/dmx-devices` |
| dmx_presets | `GET/POST/PUT/DELETE /api/dmx-presets`, device presets for dropdowns |
| dmx_preset_lists | `GET/POST/PUT/DELETE /api/dmx-preset-lists`, `GET /api/dmx-presets` |
| wled_preset_lists | `GET/POST/PUT/DELETE /api/wled-preset-lists`, `GET /api/wled-presets` |
| scenes | `GET/POST/PUT/DELETE /api/scenes`, `GET/POST /api/presets` (hidden pairing) |

The Scenes page does not expose lighting `Preset` ids to the operator: it finds or
creates a `Preset` from the selected cue-list pair, then saves the `Scene`.
