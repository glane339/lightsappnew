# Fixture Channel Tables

One file per device model, documenting the **maximum-channel DMX mode only**. Other
modes are deliberately omitted — the rig runs everything in its widest mode so the
app has full control of every parameter.

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

Seeded by [`backend/seed_devices.py`](../../backend/seed_devices.py), universe 1:

| Device | Channels | Mode |
| --- | --- | --- |
| GigBAR 2 | 1–23 | `23CH` |
| Keobin Light Bar | 25–42 | `18CH` |

Channel 24 is deliberately spare. The previous version of the app addressed devices
positionally in 24-channel blocks, so the fixtures are dialled to 1 and 25; the seed
keeps those addresses so nothing has to be re-addressed at the rig, while taking the
true channel counts from the manuals above.

Everything from channel 43 up is free.

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
