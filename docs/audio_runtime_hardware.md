# Lights Audio Engine: Runtime Hardware and Validation

## 1. Purpose and scope

This document records the runtime prerequisites and the observed 2026-08-22
validation of the Lights App integration with `lights-audio-engine`. It is an
operator/reproduction record, not a claim of detector accuracy or a production
show-library specification.

**Evidence labels used below:** *Repository configuration* is visible in this
repository or its installed dependency; *externally observed* is a machine or
hardware observation from the validation run; *measured* is a recorded result;
and *operator observation* is qualitative.

## 2. Hardware specification

| Item | Value | Evidence |
| --- | --- | --- |
| Audio interface | M-Audio M-Track Solo and Duo | Externally observed |
| Input mode | LINE | Externally observed |
| Driver | M-Audio 7.0.0.3502 (2025-07-29) | Externally observed |
| M-Audio control panel | 1.0.4 | Externally observed |
| ASIO sample rate | 48,000 Hz | Externally observed |
| Runtime format | 48,000 Hz, 2 channels | Externally observed; engine default expects 48,000 Hz |
| Preferred ASIO buffer size | 256 frames | Externally observed |

The local selector is the stable device name
`"M-Audio M-Track Solo and Duo..."`, not a numeric PortAudio index. With
`SD_ENABLE_ASIO=1` during validation, the app resolved that selector to PortAudio
device 12 on the ASIO host API. Enumeration can change, so index 12 is not
persisted.

## 3. Required runtime configuration

Repository configuration:

- `requirements.txt` pins
  `lights-audio-engine[probe,aubio]` to
  `55530e40a5996e3c895212b9f32324032cf2810e`.
- The app constructs
  `AudioEngine(AudioEngineConfig(detector="aubio"))` in
  `backend/server/app.py`.
- The local `.devdata/config.json` input selector is the M-Audio name above.
- ASIO enumeration and capture require `SD_ENABLE_ASIO=1` before Python starts.

## 4. Integrated audio processing path

```text
M-Audio → ASIO → SoundDeviceAudioSource → AudioEngine/Aubio → BeatEvent
       → Lights App adapter → beat queue → scene controller → DMX/WLED action
```

The app synchronously calls `SoundDeviceAudioSource.prime(timeout=5.0)` on its
owning/lifespan thread before the adapter worker consumes it. This preserves the
ASIO capture lifecycle while bounding startup. The upstream source retains the first
item for the worker, so no downstream priming wrapper consumes or replays it.

## 5. Audio Engine / Aubio configuration

The selected detector is Aubio. In the installed, pinned audio-engine source its
tempo tracker uses:

| Setting | Value |
| --- | --- |
| Method | `complex` |
| Window/buffer | 1,024 samples |
| Hop | 512 samples |
| Expected sample rate | 48,000 Hz |

The package still supports its `energy` detector; choosing Aubio in this app does
not remove rollback capability.

## 6. Startup procedure

```powershell
cd C:\Users\oxbas\Projects\lightsappnew
$env:SD_ENABLE_ASIO="1"
$env:LIGHTSAPP_DATA_DIR="$PWD\.devdata"
.\.venv\Scripts\python.exe backend\main.py
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8800/api/status |
  ConvertTo-Json -Depth 12
```

## 7. Runtime health indicators

For live capture, `/api/status` should show `audio.capture: "live"` and
`audio.running: true`. The status also exposes BPM/level and
`detected_beat_timing` counters. `capture: "silent"` means analysis results are
arriving but no recent beat was accepted; it is not a claim that the device is
disconnected.

## 8. Validation results — 2026-08-22

### ASIO probe and runtime

Measured ASIO probe results: 48,000 Hz × 2 channels was supported; a request for
240,000 frames (5 seconds) received 240,000 frames in 5.000000 seconds; reported
input latency was approximately 0.047125 s; and overflowed reads were 0.

The earlier blocking `InputStream.read()` path failed with PortAudio `-9987`.
The callback-based capture implementation was validated, the runtime ASIO path
completed 30-second diagnostics without timeout, and the app-owned lifecycle
remained active for at least 31 seconds.

### Aubio behavior

Measured/observed live behavior: initial lock took approximately 3 seconds;
tracking was stable around 130–134 BPM; no obvious rapid double triggers occurred;
silence suppressed BeatEvents; tracking resumed after silence; and a song
transition had an approximately 3-second reacquisition period before stabilizing.

**Operator observation:** live BeatEvents appeared almost completely aligned with
perceived musical beats. This is not a measured accuracy result and is not a
ground-truth F1 claim.

### Lights App integration and disposable scene

A successful live status included `audio.capture = "live"`, `audio.running = true`,
BPM approximately 133.858, `detected_beat_timing.recorded = 32`,
`detected_beat_timing.dropped = 0`, latest outcome `processed`, and a populated
`beat_action_ns`.

The disposable local validation scene `aubio-beat-cycle` deterministically cycled
`red → green → blue → red` for activation plus accepted beat commands. With live
music and that scene active, the app showed an active scene, live audio, processed
BeatEvents, and a populated `beat_action_ns`. This scene was validation-only local
data, not production content.

## 9. Measured software timing

Latest observed timing was:

| Software segment | Time |
| --- | ---: |
| Publish → submit | 5,000 ns |
| Submit → process | 105,700 ns |
| Publish → process | 110,700 ns |
| Process → action | 19,400 ns |
| Publish → action | 130,100 ns |

These are software-path timings only. They are **not** measurements of total
acoustic-input-to-visible-light latency.

## 10. Known limitations / not yet validated

- Physical DMX fixture illumination was not validated by this exact integrated
  test: the sACN destination was loopback `127.0.0.1:5568`.
- Total acoustic-input-to-visible-light latency is not measured.
- Production ASIO latency optimization was not performed.
- Long-duration DJ-set robustness remains unvalidated.
- Formal ground-truth beat-detection accuracy remains unvalidated.

## 11. Validation status summary

| Area | Status | Basis |
| --- | --- | --- |
| ASIO capture | Validated | Five-second probe; no overflow |
| Runtime ASIO stability | Validated | 30-second diagnostics and 31-second app lifecycle |
| Aubio live tracking | Observed | Stable approximately 130–134 BPM after lock |
| Silence suppression | Validated | No BeatEvents during silence |
| Transition recovery | Observed | Approximately three-second reacquisition |
| Lights App BeatEvent ingestion | Validated | Processed outcome and populated action timestamp |
| BeatEvent → scene action | Validated | Disposable cycle advanced red → green → blue → red |
| Physical DMX fixture output | Not validated | Loopback sACN destination |
| Total acoustic-to-light latency | Not validated | No end-to-end physical measurement |
