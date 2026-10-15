# Realtime microphone transcription prototype

Status: implemented development prototype. English transcription only.
[ADR 0006](../adr/0006-microphone-realtime-prototype.md) records the selected
model and transport. [PCM contract](../../contracts/microphone-pcm/v1/specification.md)
defines the device bytes. Wiring remains hardware-unverified.

ESP32-S3 INMP441 capture -> PCM16 UDP -> Python PC bridge -> 24 kHz realtime
WebSocket -> local Speaches CUDA/int8 -> JSON transcript on the PC terminal.
Shared speaker TX continues sending silence; no spoken reply or display output.
The PC bridge buffers speech and sends it to Speaches after 600 ms of quiet.
A normalized PCM RMS threshold of 0.015 starts speech, with 200 ms of pre-roll
and at least 160 ms of above-threshold audio to reject clicks. Silence alone
does not trigger inference. This energy gate is not a learned speech detector;
background noise can trigger it and quiet speech can be missed.
Each utterance is capped at ten seconds (320 KB of 16 kHz PCM16, including
pre-roll/silence); continuous speech is split at the cap. See
[ADR 0007](../adr/0007-speech-endpoint-buffer.md).

## Run from the repository root

Use the existing Speaches deployment:

```powershell
docker compose -f infrastructure/compose.yaml up -d --wait speaches
Invoke-WebRequest -Method Post -Uri http://localhost:8000/v1/models/Systran/faster-distil-whisper-small.en -TimeoutSec 600
python -m venv models/.venv
models/.venv/Scripts/python.exe -m pip install -e 'models[realtime]'
```

Model download is needed once and persists in the Docker cache. The selected
[English model](https://huggingface.co/Systran/faster-distil-whisper-small.en)
uses the MIT license. Bridge dependency is pinned independently from system
Python and ESP-IDF. No SDK upgrades or GPU dependencies are installed on the PC.

Find the PC Wi-Fi IPv4 and the ESP32 DHCP address in your router. Start the bridge
using those actual addresses; the following documentation addresses are examples:

```powershell
models/.venv/Scripts/python.exe -m iot_models.realtime_bridge --listen 192.0.2.10 --device-ip 192.0.2.20
```

Tune `--speech-threshold 0.015`, `--silence-seconds 0.6` and
`--max-audio-seconds 10` on that command. Raise the speech threshold if noise
triggers transcripts; lower it if quiet speech is missed. Silence must be
0.1 seconds or more and no longer than the cap; the cap accepts 0.5–10 seconds.
`--window-seconds 3` explicitly enables the previous fixed-window mode and
bypasses speech detection. Thresholds apply in the PC bridge; the ESP32 still
sends its continuous PCM UDP stream. No firmware reflash is needed for this change.

Allow inbound UDP port 5005 from that device on the private LAN if Windows asks
or the firewall blocks it. This task does not modify the firewall. Bind only the
intended LAN interface. Speaches remains bound to localhost. Optional server
authentication uses SPEACHES_API_KEY in the bridge environment, without URL keys.

In a separate terminal, activate the existing SDK and build:

```powershell
. ./scripts/activate-idf.ps1 -UseInstallerProfile
idf.py -C firmware build
```

After verifying the documented wiring and selecting the actual serial port:

```powershell
idf.py -C firmware -p COM_PORT flash monitor
```

Flashing is an operator step; no flash or hardware validation was performed
during implementation. Generated flash/partition defaults remain development
settings, not verified N16R8 production settings.

At every boot the serial console asks for bridge PC IPv4. This machine uses
compiled Wi-Fi settings from the ignored local header documented in the
[firmware guide](../../firmware/README.md). Without that header, the console also
asks for Wi-Fi SSID and password.
Enter each followed by Enter. Use a trusted console; entries are not logged or
saved to NVS. Supported prototype networks use WPA2 or newer authentication;
nonempty ASCII settings only (SSID up to 32 bytes, password up to 64).
Console-entered credentials stay in Wi-Fi RAM; restart to change them. Local
compiled credentials require rebuilding/flashing to change. UDP port is the
VOICE_STREAM_PORT menuconfig setting; update bridge --port to match.

Speak short English phrases. The PC prints:

```json
{"type":"transcript","item_id":"...","text":"Hello world.","window_seconds":1.44,"end_reason":"silence"}
```

`window_seconds` is the actual buffered duration. `end_reason` is `silence` or
`max_duration` (`fixed_window` in legacy mode). Ctrl+C stops the bridge.
Noise-triggered segments may still yield empty text or hallucinations.
Overload drops stale queued
audio and resets sessions. Sessions also recycle after 20 windows to bound the
installed server's retained buffers. Logs report resets; raw UDP cannot detect
loss/reordering. Inference still runs sequentially; if it falls behind the
one-second ingress queue, audio is dropped and the session resets. Partial
utterances are discarded on shutdown/reconnect. No partial token output is promised.

## Repeatable checks

```powershell
python scripts/validate.py
python -m unittest discover -s firmware/tests -v
docker compose -f infrastructure/compose.yaml config --quiet
```

To test the real bridge without the board, supply a recorded or synthesized
English WAV: uncompressed PCM16, mono, 16 kHz. This opt-in check runs the bridge
on loopback port 15005, replays real-time UDP packets, checks an expected word,
and stops its subprocesses:

```powershell
models/.venv/Scripts/python.exe models/tests/live_realtime_smoke.py C:/path/test.wav --expect hello
```

The synthetic smoke test establishes the host UDP/WebSocket/inference path only.
For physical acceptance, verify power/wiring, flash intentionally, confirm the
device appears on Wi-Fi, speak a known phrase and compare the transcript. Observe
caption latency, clipping, background noise and Wi-Fi reconnect behavior. A build
or synthetic replay does not establish microphone accuracy or electrical safety.

Implementation verification on 2026-10-14: `idf.py build` from firmware passed
with ESP-IDF v6.1 for esp32s3 (806816-byte application, 23% free in the generated
1 MB app partition). `python scripts/validate.py` from the root passed 16 tests;
`python -m unittest discover -s firmware/tests -v` passed the existing audio
harness; `docker compose -f infrastructure/compose.yaml config --quiet` passed.
The opt-in smoke command above passed with a Windows System.Speech-generated
16 kHz WAV, producing "Hello world. This is a microphone pipe." The input's
final words crossed the window boundary. Build warnings about existing Wi-Fi
private include directories and missing Git HEAD metadata remain. Initial live
failures and version-specific fixes are recorded in ADR 0006. Flashing, physical
capture and sustained latency/reconnect measurements were skipped: no board was
tested. The smoke subprocesses were stopped; Speaches remains healthy/running.
