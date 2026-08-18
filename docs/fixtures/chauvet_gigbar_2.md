# Chauvet DJ GigBAR 2

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](../decisions.md#d-023-a-look-is-a-dmx_preset).

| | |
| --- | --- |
| `DMX_Device.model` | `chauvet_gigbar_2` |
| Mode | `23CH` — the widest mode the manual documents |
| Channel count | 23 |
| Manual | GigBAR 2 User Manual Rev. 3, pp. 26–28 |

The unit is one bar containing two pars, two derbies, a laser, and a strobe. In
`23CH` every section is addressed independently; the narrower `11CH` mode gangs the
pars and derbies onto shared colour channels and is deliberately not used here.

## Channel table

| Ch | Function | Values | Notes |
| --- | --- | --- | --- |
| 1 | Par 1 — Red | 000–255 | 0–100% |
| 2 | Par 1 — Green | 000–255 | 0–100% |
| 3 | Par 1 — Blue | 000–255 | 0–100% |
| 4 | Par 1 — UV | 000–255 | 0–100% |
| 5 | Par 1 — dimmer / strobe | see below | Drives channels 1–3 |
| 6 | Par 2 — Red | 000–255 | 0–100% |
| 7 | Par 2 — Green | 000–255 | 0–100% |
| 8 | Par 2 — Blue | 000–255 | 0–100% |
| 9 | Par 2 — UV | 000–255 | 0–100% |
| 10 | Par 2 — dimmer / strobe | see below | Drives channels 6–8 |
| 11 | Derby 1 — colour | see below | |
| 12 | Derby 1 — strobe rate | see below | |
| 13 | Derby 1 — rotation | see below | |
| 14 | Derby 2 — colour | see below | Same table as ch 11 |
| 15 | Derby 2 — strobe rate | see below | Same table as ch 12 |
| 16 | Derby 2 — rotation | see below | Same table as ch 13 |
| 17 | Laser — colour | see below | |
| 18 | Laser — strobe | see below | |
| 19 | Laser — pattern / rotation | see below | |
| 20 | Strobe — patterns | see below | |
| 21 | Strobe — white dimmer | 000–255 | White 0–100% |
| 22 | Strobe — UV dimmer | 000–255 | UV 0–100% |
| 23 | Strobe — speed | 000–255 | Slow to fast, applies to ch 21 or ch 22 |

Two constraints the manual states explicitly, both of which the app has to respect
because the hardware will not:

- Each par can show **at most 3 of its 4 colours at a time** (ch 1–4, ch 6–9).
- **Channels 21 and 22 cannot be used simultaneously** — white and UV strobe are
  mutually exclusive.

## Value tables

### Ch 5, 10 — par dimmer / strobe

| Range | Meaning |
| --- | --- |
| 000–127 | RGB level, based on the preceding colour channels |
| 128–239 | Strobe speed, slow to fast |
| 240–249 | Strobe to sound |
| 250–255 | RGB 100% |

### Ch 11, 14 — derby colour

| Range | Meaning |
| --- | --- |
| 000–024 | Blackout |
| 025–049 | Red |
| 050–074 | Green |
| 075–099 | Blue |
| 100–124 | Red + Green |
| 125–149 | Red + Blue |
| 150–174 | Green + Blue |
| 175–199 | Red + Green + Blue |
| 200–224 | Automatic, single colours only |
| 225–255 | Automatic, two colours at a time |

### Ch 12, 15 — derby strobe rate

| Range | Meaning |
| --- | --- |
| 000–009 | No function |
| 010–239 | Strobe, 0–30 Hz |
| 240–255 | Strobe to sound |

### Ch 13, 16 — derby rotation

| Range | Meaning |
| --- | --- |
| 000–004 | Stop |
| 005–127 | Rotate clockwise, slow to fast |
| 128–133 | Stop |
| 134–255 | Rotate counter-clockwise, slow to fast |

### Ch 17 — laser colour

| Range | Meaning |
| --- | --- |
| 000–039 | Blackout |
| 040–079 | Red on |
| 080–119 | Green on |
| 120–159 | Red + Green on |
| 160–199 | Red on, Green strobe |
| 200–239 | Green on, Red strobe |
| 240–255 | Red + Green, alternate strobe |

### Ch 18 — laser strobe

| Range | Meaning |
| --- | --- |
| 000–009 | No function |
| 010–239 | Strobe speed, slow to fast |
| 240–255 | Strobe to sound |

### Ch 19 — laser pattern

| Range | Meaning |
| --- | --- |
| 000–004 | Stop |
| 005–127 | Rotate clockwise, slow to fast |
| 128–133 | Stop |
| 134–255 | Rotate counter-clockwise, slow to fast |

### Ch 20 — strobe patterns

| Range | Meaning |
| --- | --- |
| 000–009 | Blackout |
| 010–019 | White auto strobe program 1 |
| 020–029 | White auto strobe program 2 |
| 030–039 | White auto strobe program 3 |
| 040–049 | White auto strobe program 4 |
| 050–059 | White auto strobe program 5 |
| 060–069 | White auto strobe program 6 |
| 070–079 | White auto strobe program 7 |
| 080–089 | White auto strobe program 8 |
| 090–099 | White auto strobe program 9 |
| 100–109 | White manual strobe, slow to fast |
| 110–119 | UV auto strobe program 1 |
| 120–129 | UV auto strobe program 2 |
| 130–139 | UV auto strobe program 3 |
| 140–149 | UV auto strobe program 4 |
| 150–159 | UV auto strobe program 5 |
| 160–169 | UV auto strobe program 6 |
| 170–179 | UV auto strobe program 7 |
| 180–189 | UV auto strobe program 8 |
| 190–199 | UV auto strobe program 9 |
| 200–209 | UV manual strobe, slow to fast |
| 210–229 | UV strobe to sound |
| 230–255 | White strobe to sound |

## Laser note

The GigBAR's laser is part of the bar and is driven over DMX like any other section
here — it is unrelated to the ILDA projector path, which stays behind the safety
boundary in [laser_and_haze_safety.md](../laser_and_haze_safety.md).
