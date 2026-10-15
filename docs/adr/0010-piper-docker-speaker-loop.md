# 0010: Docker Piper and ESP32 speaker loop

- Date: 2026-10-14
- Status: Accepted
- Owners: AI, infrastructure, firmware and integration responsibilities

## Context

The user selected Piper TTS, Docker deployment for the complete inference path,
and playback on the ESP32 speaker. Existing development capture, shared clocks,
English STT and Qwen3 remain the starting point.

## Decision

Run the existing bridge and streaming orchestrator in a container, Speaches and
Ollama in GPU containers, and Piper 1.8.0 in a separate CPU container. Select
en_US-ljspeech-medium (22,050 Hz mono, approximately 64 MB), from the pinned
rhasspy/piper-voices revision c10ece1aade47bb51c153c893d14e5bf8e5b7117.
Its model card identifies a public-domain LJ Speech dataset. Piper is GPL-3.0;
redistribution and production licensing need their own review. CPU synthesis
does not reserve VRAM. Exact runtime CPU/RAM and latency require measurement.

Piper exposes only an internal HTTP synthesis endpoint, returning resampled
16 kHz mono PCM16. The orchestrator synthesizes only completed successful LLM
responses, keeps successful history on TTS failure, and never retries TTS.
The speech mailbox holds one reply for at most 30 seconds; newer audio replaces
uncollected audio. Docker publishes microphone UDP 5005 and speaker HTTP 5006
on an explicitly selected PC LAN address. Firmware polls that same PC for
audio and streams PCM16 converted to existing 32-bit left-slot I2S. It drains
but replaces microphone upload with silence during playback and a 300 ms tail. No barge-in,
echo cancellation, playback acknowledgement, GPIO or memory-setting change.
The wire semantics are authoritative in speaker-pcm v1.

Verified Docker Desktop forwarding rewrites device UDP source to the Compose
bridge gateway. The Windows launcher inspects that gateway after network creation
and sets the bridge's expected source explicitly; a caller can override it with
the observed source. Keep original device filtering for native host/Linux paths.
The Docker gateway filter cannot identify the original LAN sender; firewall
restriction is required. Microphone PCM 1.0.1 clarifies this without byte changes.

Use a unified iot-voice Compose project with external references to the existing
Speaches and Ollama cache volumes, preserving downloaded models. Stop the old
service containers before starting their unified replacements to avoid port/GPU
conflicts. Native Ollama remains outside this deployment and is not terminated.
The prototype exposes Ollama on localhost 11435 to avoid its existing native
11434 listener. This supersedes ADR 0009's separate-project deployment choice
for this optional complete loop; its text-only workflow remains available.

## Alternatives

PC playback does not meet the selected destination. UDP return audio would add
loss/reordering handling. HTTP pull avoids introducing device server discovery
and bounds device RAM independently of reply length. CPU Piper preserves scarce
GPU capacity. Docker Desktop cannot run ESP32 firmware; the device stays native.

## Consequences

Trusted LAN development only: HTTP/UDP are unencrypted and unauthenticated.
Anyone able to reach the mailbox can collect a reply. Bind only the intended
interface and restrict firewall access to the device. This is not production
provisioning or authentication. Interrupted playback is discarded without retry;
there is no claim that an HTTP download establishes audible playback. Missing
device audio makes the unchanged STT bridge reconnect after its idle limit.
Physical amplifier/channel compatibility and acoustic behavior remain unverified.

## Validation

Run model/integration tests, root validation, ESP-IDF v6.1 esp32s3 build, Compose
configuration, live Piper and synthetic STT -> LLM -> TTS -> HTTP collection.
Record executed results and hardware limitations in the speaker loop guide.

Sources: [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md),
[voice model card](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/en/en_US/ljspeech/medium/MODEL_CARD),
[Piper license](https://github.com/OHF-Voice/piper1-gpl/blob/main/COPYING).
