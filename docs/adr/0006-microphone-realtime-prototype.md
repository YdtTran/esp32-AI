# 0006: Microphone realtime prototype

- Date: 2026-10-14
- Status: Accepted
- Owners: firmware, AI, integration responsibilities

Default fixed-window segmentation is superseded by
[ADR 0007](0007-speech-endpoint-buffer.md); other decisions below remain applicable.

Console provisioning is superseded by [ADR 0011](0011-lcd-and-web-setup.md),
which adds browser setup, saved settings and LCD status without wire changes.

## Context

The user requests a full prototype, confirms UDP through a PC bridge and English
only. Existing firmware captures 16 kHz mono audio. Inspection of the installed
Speaches image from ADR 0005 shows an older realtime API: 24 kHz PCM16,
session.update and manual commits, without the current intent=transcription API.

## Decision

Retain the existing audio bus and UDP bytes, defined in
[microphone PCM v1](../../contracts/microphone-pcm/v1/specification.md).
The voice_stream component owns serial provisioning, Wi-Fi reconnect and UDP;
voice_stream_start() starts its task after audio and NVS initialization.
Read Wi-Fi credentials and PC IPv4 address on the existing console each boot;
use RAM Wi-Fi storage. No compiled credentials or GPIO changes.

The models Python bridge uses optional websockets==15.0.1, continuous linear
16-to-24 kHz resampling and English Systran/faster-distil-whisper-small.en.
Suppress automatic VAD with threshold 1.0, disable response creation, commit
three-second windows, print JSON results
and wait for completion before committing again. Bound incoming audio to one
second; discard stale audio on reconnect/overflow. Recycle sessions after 20
windows because the installed server retains committed buffers.

Model provenance: [Systran model card](https://huggingface.co/Systran/faster-distil-whisper-small.en),
MIT license, English Distil-Whisper converted to CTranslate2. Download into the
existing Docker cache as part of this prototype. CUDA/int8 remains from ADR 0005;
4 GB GPU capacity and latency require measurement. No LLM, TTS or playback.

The installed PartialSession type rejects null turn detection. Its required
prefix_padding_ms field emits an unsupported-field warning even though other
VAD settings apply. Ignore only that exact warning during configuration and
verify session.updated threshold, response flag, padding and model; reset on
unexpected speech events. This is a version-specific compatibility adapter.
Set supported LOOPBACK_HOST_URL=http://127.0.0.1:8000 in the service: its default
internal ASGI transcription client returns 404. Keep the same image and cache.

## Alternatives

Direct WebSocket needs firmware JSON/resampling changes. Upgrading Speaches would
invalidate deployment evidence. Fixed windows bound buffering without relying on
the installed implementation's server VAD behavior.

## Consequences

Trusted LAN only: UDP is unauthenticated, unencrypted and lossy. Raw packets
cannot detect reordering/loss. Completed window captions arrive after three
seconds plus inference; words crossing boundaries can be truncated. This is not
token streaming. Session recycling causes a brief capture gap. Serial console
is trusted; credentials remain in RAM until reboot. Production provisioning,
security and hardware verification remain open.

## Validation

Run resampling, protocol, overload and compatibility tests, repository validation,
ESP32-S3 build and synthetic English audio through UDP to the pinned live server.
Physical microphone, Wi-Fi and electrical behavior require a device test.

Verified: ESP-IDF v6.1 ESP32-S3 build, 16 root host tests, existing firmware
audio regression harness and Compose config passed. Installed the English model
using POST /v1/models/Systran/faster-distil-whisper-small.en (HTTP 200).
Paced synthetic 16 kHz UDP replay through websockets 15.0.1 produced
"Hello world. This is a microphone pipe." on the RTX 2050. The three-second
boundary truncates the longer input phrase, as expected. No device was flashed.
Initial live tests exposed null-VAD rejection and internal transcription 404;
both are handled by the compatibility settings above. A concurrent smoke run
failed because its UDP port was already in use; sequential rerun passed.
