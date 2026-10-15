# Native Ollama JSON voice prototype

`iot_models.voice_orchestrator` uses the existing native Windows Ollama 0.40.4
on localhost:11434. It starts the unchanged realtime bridge, preserves final
transcript JSON, and prints correlated English LLM response JSON. The separate
[streaming guide](local-llm-prototype.md) describes another implementation in this
workspace. Run one Ollama server per port and one bridge per UDP port.

From the repository root, using the existing environment:

```powershell
ollama pull qwen3:1.7b
models/.venv/Scripts/python.exe -m iot_models.voice_orchestrator --text "Hello. What is two plus two?"
models/.venv/Scripts/python.exe -m iot_models.voice_orchestrator -- --listen 192.0.2.10 --device-ip 192.0.2.20
```

Replace example IPs with the PC and ESP32 addresses. Bridge settings go after
`--`. Firmware and Speaches configuration remain unchanged. No Python dependency
is added. Qwen3 1.7B Q4_K_M is about 1.4 GB on disk, Apache 2.0; weights stay in
Ollama's external cache. Only completed nonempty transcripts trigger inference.

Stateless `/api/chat` requests disable thinking/streaming, limit context to 2048
tokens/output to 128, and instruct concise English replies without device control.
Input cap: 4000 characters. Response cap: 1 MiB. HTTP socket timeout: 60 seconds
(`--llm-timeout`). Local HTTP bypasses proxies. Default `--keep-alive 0` unloads
after each response; `--keep-alive 30s` enables warm-model comparison with higher
memory residency. This differs from the streaming implementation's settings.

One request runs at a time with one pending transcript. Newer transcripts replace
pending work with `llm_dropped`. Errors print `llm_error`, preserving transcripts
and allowing later requests. Ctrl+C closes the owned bridge; active HTTP can take
its socket timeout to finish. English is instructed, not language-detected. Logs
contain utterances/replies. No TTS, MQTT, ThingsBoard or device actions.

`llm_response` includes item ID, model, text, `queue_ms`, `http_ms`,
`transcript_to_response_ms` and Ollama metrics. Ollama duration values are
nanoseconds; orchestrator timing is milliseconds. Receipt-to-response excludes
capture and STT. `done_reason: length` indicates token-cap truncation.

With an English mono PCM16 16 kHz WAV, measure the host pipeline and GPU on
loopback UDP port 15009:

```powershell
models/.venv/Scripts/python.exe models/tests/live_voice_smoke.py C:/path/hello.wav --expect hello
python scripts/validate.py
docker compose -f infrastructure/compose.yaml config --quiet
```

Replay-start-to-response includes paced audio, endpoint silence, STT and LLM;
it excludes physical ESP32 capture/Wi-Fi. Whole first-GPU samples include other
processes; sampled peak is a lower bound. Missing nvidia-smi yields null metrics.
No firmware build/flash or hardware verification is claimed.

Sources: [chat API](https://docs.ollama.com/api/chat),
[model](https://ollama.com/library/qwen3:1.7b).

## Executed evidence, 2026-10-14

Native Ollama 0.40.4 installed qwen3:1.7b, model ID `8f68893c685c`, 1.4 GB.
Installed full digest:
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
The API labels this tag's parameter count 2.0B; selection uses the requested
`qwen3:1.7b` library tag and Q4_K_M quantization, not a different downloaded model.
The first direct text request returned "Four." in 55.296 seconds (28.562 seconds
server load, 18.127 seconds prompt evaluation). This is a cold-start observation,
not an expected steady-state latency; other work was active in the workspace.

The following executed commands passed, from the repository root:

```powershell
python scripts/validate.py
docker compose -f infrastructure/compose.yaml config --quiet
docker compose -f infrastructure/services/ollama/compose.yaml config --quiet
$env:PYTHONPATH = (Resolve-Path models/src).Path
models/.venv/Scripts/python.exe -m unittest discover -s models/tests -p test_voice_orchestrator.py -v
models/.venv/Scripts/python.exe models/tests/live_realtime_smoke.py "$env:TEMP/iot-local-llm-smoke.wav" --expect hello --port 15011
models/.venv/Scripts/python.exe models/tests/live_voice_smoke.py "$env:TEMP/iot-local-llm-smoke.wav" --expect hello --port 15012
```

Root validation passed 37 tests, including seven new JSON orchestrator tests.
The temporary WAV was generated with Windows System.Speech, mono PCM16 16 kHz,
saying "Hello. What is two plus two?". The unchanged bridge split this into two
utterances because of the pause; the measured first turn was "Hello." with reply
"Hello! How can I assist you today?". Replay start to final transcript: 1.688 s;
HTTP/LLM: 2.656 s; replay start to reply: 4.344 s. Server load: 2.333 s.
Twelve whole-GPU samples observed baseline 2077 MiB, peak 3263 MiB/4096 MiB,
peak utilization 100%. Other-process usage and concurrent requests can affect
these observations; they do not establish isolated performance or stability.

Speaches remained healthy with the same container and port. Owned bridge/replay
processes exited, UDP port 15012 was released, and a later whole-GPU snapshot was
574 MiB after unloading. No failures in final checks. An earlier combined smoke
using the separately added streaming implementation also passed. Docker Ollama
deployment was not started by this work: native Ollama already owned port 11434.
Firmware builds/flash, physical microphone/Wi-Fi, sustained load, and TTS/device
integration were skipped because this change is a host-only prototype.

A follow-up text request with `--keep-alive 30s` returned "4." in 3.047 seconds,
including 2.804 seconds loading. `ollama ps` then confirmed 100% GPU offload,
2048-token context and 1.5 GB model allocation; whole-GPU usage was 2073 MiB.
This residency snapshot does not include simultaneous active STT inference.
Repeating that same short text prompt while resident took 93 ms, then unloaded
with keep_alive=0. This warm/cached result is not comparable to an arbitrary
uncached microphone utterance; first-use loading can dominate latency.
