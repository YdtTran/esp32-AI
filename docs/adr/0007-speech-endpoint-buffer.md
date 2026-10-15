# 0007: Bounded speech endpoint buffer

- Date: 2026-10-14
- Status: Accepted
- Owners: AI module and infrastructure maintainer

## Context

The user requested sending captured audio after they stop talking, with a
buffer threshold preventing long-audio overhead. ADR 0006 used fixed windows.
The firmware PCM transport is already defined and stays unchanged.

## Decision

Replace the bridge's default fixed windows with a local normalized PCM16 RMS
energy gate. Defaults: speech threshold 0.015, 600 ms trailing quiet, 200 ms
pre-roll, at least 160 ms above-threshold speech and a ten-second hard cap.
Expose speech threshold, silence duration and cap as CLI options. Cap duration
includes all buffered audio and splits continuous speech without losing bytes
at the cap. Each segment is resampled independently and uploaded only after
endpoint detection; manual server commits and version compatibility remain.

Keep explicit `--window-seconds` as the legacy fixed-window mode. Preserve the
JSON text field and report actual `window_seconds` plus `end_reason`. Preserve
bounded ingress, overflow/session reset and twenty-utterance session recycling.
This supersedes ADR 0006's default segmentation only. Firmware, transport,
model selection, server image and UDP bandwidth remain unchanged.

## Alternatives

Server VAD uploads continuous audio and does not satisfy sending after silence.
A learned local VAD adds a model/dependency before energy detection has been
tested on the microphone. Firmware segmentation requires a new wire framing
contract and hardware verification; local bridge buffering is sufficient here.

## Consequences

The raw utterance buffer holds at most 320,000 bytes; pre-roll holds 6,400 bytes.
Resampled audio, JSON/base64 and the one-second ingress queue add bounded memory
overhead. Silence endpoints are packet-granular (up to 16 ms beyond the quiet
threshold) and transcripts arrive after quiet plus inference time. Long speech
can lose linguistic context across forced splits. Noise can trigger the energy
gate; quiet speech can be missed. Tune thresholds on the real microphone.
Slow inference may overflow ingress and discard audio rather than queueing
unbounded requests. Shutdown/disconnection discards partial utterances.

## Validation

`models/.venv/Scripts/python.exe -m unittest discover -s models/tests -v` passed
16 tests with `PYTHONPATH` set to `models/src`. Checks cover silence suppression,
bounded pre-roll, endpoint retention, click rejection, exact cap splitting,
invalid settings, no upload before endpoint detection, segmented session commits
and legacy fixed windows. `python scripts/validate.py` passed all 23 host tests.
An initial cancellation test failed under the older repository Python runtime;
replacing queue `wait_for` calls with `asyncio.timeout` resolved it, including
clean task cancellation. The final repository check passed.

`models/.venv/Scripts/python.exe models/tests/live_realtime_smoke.py <temporary-synthesized-16-kHz-WAV> --expect hello --port 15007`
passed against the running Speaches GPU server: `Hello World`, buffered duration
1.44 seconds, `end_reason: silence`. The smoke bridge/replay processes stopped.
This verifies the host path; physical microphone thresholds, background noise
and ESP32 Wi-Fi behavior were not tested. No firmware build/flash is required.
