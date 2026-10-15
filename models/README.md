# AI inference module specification

## Complete Docker speaker prototype

The streaming orchestrator accepts `--piper-url` to synthesize completed replies
and serve a bounded ESP32 PCM mailbox. `piper_service` owns CPU synthesis;
`speaker_pipeline` owns its client/mailbox; `tts_audio` owns conversion and
validation. See [setup and checks](../docs/specs/speaker-loop.md) and
[ADR 0010](../docs/adr/0010-piper-docker-speaker-loop.md). All inference/bridge
runtime processes run in Docker; `voice_orchestrator` remains a text-only alternate.

## Local English LLM prototype

`iot_models.orchestrator` adds text-only chat and completed-transcript integration
through the unchanged realtime bridge. `iot_models.ollama_client` isolates the
streaming Qwen3 1.7B API; it uses only the Python standard library. See the
[run and measurements guide](../docs/specs/local-llm-prototype.md) and
[ADR 0009](../docs/adr/0009-local-llm-prototype.md). No firmware change or TTS.

For the optional native-Ollama JSON entry point and host/GPU measurements, see
the [voice orchestrator guide](../docs/specs/voice-orchestrator.md).

## English realtime prototype

The implemented `iot_models.realtime_bridge` consumes firmware PCM16 UDP,
buffers speech until silence or a duration cap, resamples 16 kHz to 24 kHz and
emits completed English utterance transcripts through
the pinned Speaches realtime API. `iot_models.replay_microphone` replays a test
WAV at device cadence. Optional dependency: `websockets==15.0.1`; no Python GPU
library is needed. Setup, device console provisioning, operational limits and
live test commands are in the
[prototype guide](../docs/specs/realtime-microphone-prototype.md).
See [ADR 0006](../docs/adr/0006-microphone-realtime-prototype.md).
Speech endpoint thresholds and the bounded buffer are defined in
[ADR 0007](../docs/adr/0007-speech-endpoint-buffer.md).

The following foundation description is retained as setup history.

`src/iot_models/` is the installable Python package. It currently supplies package
metadata only, with no inference model, service endpoint or transport dependency.
LLM, STT and TTS implementations will go into packages of those names after their
capabilities and runtime decisions are accepted. Module unit tests go in `tests/`.

Python 3.11+ is the host-check baseline (ADR 0001). The existing ESP-IDF Python
environment can run these dependency-free checks; no extra environment is needed.

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path .\models\src).Path
python -m unittest discover -s models/tests -v
```

```bash
PYTHONPATH=models/src python3 -m unittest discover -s models/tests -v
```

`python scripts/validate.py` sets the source path for test subprocesses
automatically. An editable install is optional later; no installation is required
for bootstrap validation. Future dependencies belong in `pyproject.toml`, with
a reproducible lock strategy decided before service deployment.
