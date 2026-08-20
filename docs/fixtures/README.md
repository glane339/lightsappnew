# Fixture Channel Tables

One file per device model, documenting the **maximum-channel DMX mode only**. Other
modes are deliberately omitted — the rig runs everything in its widest mode so the
app has full control of every parameter.

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](../decisions.md#d-023-a-look-is-a-dmx_preset). Channel tables here
> are what those `dmx_device_preset` values *mean*.

These files are the reference for what each channel *means*. The library stores only
how many channels a device occupies and where it starts
([`DMX_Device`](../../backend/models/DMX_Device.py)); per-channel semantics live here,
per [D-014](../decisions.md#d-014-fixtures-become-first-class-persisted-objects).

## Index

| Model | `DMX_Device.model` | Mode | Channels | Source |
| --- | --- | --- | --- | --- |
| [Chauvet DJ GigBAR 2](chauvet_gigbar_2.md) | `chauvet_gigbar_2` | `23CH` | 23 | User Manual Rev. 3, pp. 26–28 |
| [Keobin Light Bar](keobin_light_bar.md) | `keobin_light_bar` | `18CH` | 18 | Channel assignment sheet |

## Patch

**Single sACN universe: universe 1.** All fixtures below share that universe; the
app sends one E1.31 stream to the **network switch** (static IP from the switch
manual in local `config.json` only). Box **blackouts when packets stop** —
[fixture_and_transport_strategy.md §6](../fixture_and_transport_strategy.md#6-the-custom-universe-box-boundary).

Seeded by [`backend/seed_devices.py`](../../backend/seed_devices.py), universe 1:

| Device | Channels | Mode |
| --- | --- | --- |
| GigBAR 2 | 1–23 | `23CH` |
| Keobin Light Bar | 24–41 | `18CH` |

The patch is contiguous: each fixture's channel count comes from its manual above,
rather than from the uniform 24-channel blocks the previous version of the app used.
The Keobin is dialled to 24, immediately after the GigBAR's 23 channels.

Everything from channel 42 up is free.

## File format

Each fixture file follows the same shape so a channel table can be read at a glance
and, later, transcribed into a UI:

````markdown
# <Manufacturer> <Model>

| | |
| --- | --- |
| `DMX_Device.model` | `manufacturer_model` |
| Mode | <name from the manual> |
| Channel count | <n> |
| Manual | <file name / revision> |

## Channel table

| Ch | Function | Values | Notes |
| --- | --- | --- | --- |
| 1 | Dimmer | 0–255 | |

## Value tables

Ranges that select a mode, colour, or macro rather than a level.

| Ch | Range | Meaning |
| --- | --- | --- |
````

Channel numbers are **1-based and relative to the device's start address**, exactly
as printed in the manual. `DMX_Device.start_address` supplies the offset, so nothing
here needs to change when a device is re-patched.

## Frontend profiles (WS-11.2)

The Builder UI ([frontend_architecture.md](../frontend_architecture.md)) transcribes
these channel tables into static JavaScript profiles under `frontend/js/fixtures/`
(one file per `DMX_Device.model`). The profiles drive section toggles and labelled
controls in max-channel mode; the library still stores only `channel_values` arrays
via `DMX_Device_Preset`.
