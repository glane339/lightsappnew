# Keobin Light Bar

> **Terminology.** A "look" is a `dmx_preset` (`DMX_Preset`). Use `dmx_preset` going
> forward — [D-023](../decisions.md#d-023-a-look-is-a-dmx_preset).

| | |
| --- | --- |
| `DMX_Device.model` | `keobin_light_bar` |
| Mode | `18CH` — the only mode the supplied channel chart documents |
| Channel count | 18 |
| Manual | Keobin light bar channel assignment sheet (single page) |

The unit combines four lasers with motor control, two magic-ball sections, and a
strobe with its own RGB plus violet emitters.

> **Transcription note.** The supplied PDF embeds its text with a non-standard font
> encoding, so the channel chart had to be transliterated rather than copied. The
> tables below are that transliteration. Verify against the printed sheet before a
> show, and see the caveat on channels 15–16.

## Channel table

| Ch | Function | Values | Notes |
| --- | --- | --- | --- |
| 1 | Special access | see below | Selects auto / sound modes |
| 2 | Green laser 1 | 000–255 | |
| 3 | Red laser 2 | 000–255 | |
| 4 | Blue laser 3 | 000–255 | |
| 5 | Red laser 4 | 000–255 | |
| 6 | Laser motors | 000–255 | |
| 7 | Magic ball 1 — red | 000–255 | |
| 8 | Magic ball 1 — green | 000–255 | |
| 9 | Magic ball 1 — blu-ray | 000–255 | Sheet's wording for the blue emitter |
| 10 | Magic ball 1 — white | 000–255 | |
| 11 | Magic ball 2 — red | 000–255 | |
| 12 | Magic ball 2 — green | 000–255 | |
| 13 | Magic ball 2 — blue-ray | 000–255 | |
| 14 | Strobe | see below | |
| 15 | Strobe LED red | 000–255 | ⚠ see caveat |
| 16 | Strobe LED green | 000–255 | ⚠ see caveat |
| 17 | Strobe LED blue | 000–255 | |
| 18 | LED violet light | 000–255 | |

### ⚠ Channels 15 and 16

The transliterated text emitted the channel numbers `16` and `15` out of order
against the labels "strobe LED red" and "strobe LED green", so which of the two is
red and which is green could not be read unambiguously. The table above assumes
**15 = red, 16 = green**, matching channel 17 being blue and the red-green-blue
ordering every other section of this fixture uses.

This costs nothing to confirm: set channel 15 to 255 with 16 and 17 at 0 and see
which colour lights. If it is green, swap the two rows above.

## Value tables

### Ch 1 — special access

| Range | Meaning |
| --- | --- |
| 000–030 | Not used |
| 031–060 | Self-running 1 |
| 061–090 | Self-running 2 |
| 091–120 | Self-running 3 |
| 121–150 | Sound control 1 |
| 151–180 | Sound control 2 |
| 181–210 | Sound control 3 |
| 211–255 | Not used |

The self-running and sound-control ranges hand the fixture's timing to the fixture
itself. Because this app drives cues from its own beat detection, channel 1 should
normally sit in a "not used" range so the rig stays under app control — see
[audio_reactivity_architecture.md](../audio_reactivity_architecture.md).

### Ch 14 — strobe

| Range | Meaning |
| --- | --- |
| 000 | None |
| 001–004 | On |
| 005–029 | Random strobe |
| 030–255 | Strobe speed, slow to fast |

## Laser note

These lasers are built into the bar and are driven over DMX. They are unrelated to
the ILDA projector path, which stays behind the safety boundary in
[laser_and_haze_safety.md](../laser_and_haze_safety.md).
