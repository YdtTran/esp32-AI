# Local English LLM prototype

For the Docker STT -> LLM -> Piper -> ESP32 speaker loop and the updated Docker
launcher, follow [speaker-loop.md](speaker-loop.md). The host-only commands below
remain available after stopping the Docker voice-loop service. Historical
launcher `-OllamaUrl` is replaced by `-OllamaPort` for the unified stack.

ESP32 microphone -> existing 16 kHz PCM16 UDP -> unchanged Python realtime bridge
-> Speaches English final transcript -> host orchestrator -> Ollama -> console.
The existing STT model is **Systran/faster-distil-whisper-small.en**, as selected
in [ADR 0006](../adr/0006-microphone-realtime-prototype.md). It is not replaced.
[ADR 0009](../adr/0009-local-llm-prototype.md) records the prototype LLM decision.

## Setup (PowerShell, repository root)

```powershell
Set-Location E:\Workspace\Projects\IoT
docker compose -f infrastructure/services/ollama/compose.yaml config --quiet
docker compose -f infrastructure/services/ollama/compose.yaml up -d --wait ollama
docker compose -f infrastructure/services/ollama/compose.yaml exec -T ollama ollama pull qwen3:1.7b
docker compose -f infrastructure/services/ollama/compose.yaml exec -T ollama ollama list
```

Only this model is downloaded. The independent `iot-ollama` Compose project
keeps `/root/.ollama` in its own named volume and publishes 127.0.0.1:11434.
Keep using the existing Speaches stack and cache. Do not create a second Speaches
container or reinstall the working Python environment. If not already set up,
follow the [STT guide](realtime-microphone-prototype.md) for the existing
`models/.venv` and `pip install -e 'models[realtime]'`.

If native Ollama already owns 11434, quit it before starting this Docker service.
Do not terminate it while another task is using it. Live validation in this
session used a temporary override on 11435 to preserve an active native model
download. To repeat that arrangement without changing the delivered configuration:

```powershell
@'
services:
  ollama:
    ports: !override
      - "127.0.0.1:11435:11434"
'@ | Set-Content -Encoding utf8 "$env:TEMP/iot-ollama-validation.yaml"
docker compose -f infrastructure/services/ollama/compose.yaml -f "$env:TEMP/iot-ollama-validation.yaml" up -d --wait ollama
$env:OLLAMA_URL = 'http://127.0.0.1:11435'
```

The override requires Compose 2.24.4+; this machine has 5.6.0. Use the same two
`-f` arguments for subsequent `up` operations during alternate-port validation.
`exec`, `logs` and `stop` still target the same `iot-ollama` project.

The orchestrator uses Python's standard library; there is no requirements file,
Dockerfile, web framework or new host dependency. `websockets==15.0.1` is needed
only by the existing STT bridge.

## Mode A: text only

```powershell
models/.venv/Scripts/python.exe -m iot_models.orchestrator
```

Enter English questions at `User:`; `/quit` or Ctrl+C exits. Ask "My name is Alex"
then "What is my name?" to check context. Three successful user/assistant pairs
are retained; failed turns do not enter history. Model settings are qwen3:1.7b,
thinking disabled, 2048 context, at most 100 output tokens, temperature 0.3.
The limit can truncate a response; the system prompt requests brief English.
No tools are connected and no device action is performed.

## Mode B: microphone STT to LLM

This machine's addresses are saved in
[the PowerShell launcher](../../scripts/start-voice-assistant.ps1): ESP32
`192.168.1.16`, PC `192.168.1.4`, UDP 5005, Docker Ollama on 11435. Stop the
existing bridge first with Ctrl+C, then run from the repository root:

```powershell
./scripts/start-voice-assistant.ps1
```

Run `./scripts/start-voice-assistant.ps1 -DryRun` to inspect the command without
starting services. If DHCP addresses change, edit the launcher defaults or pass
`-DeviceIP` and `-ListenIP`. After switching Docker to its standard port, use
`-OllamaUrl http://127.0.0.1:11434`. The ESP32's destination remains the PC
address and port; the host launcher does not provision the device.

Stop any existing bridge that owns the same UDP port, then launch:

```powershell
models/.venv/Scripts/python.exe -m iot_models.orchestrator --stt -- --listen 192.0.2.10 --device-ip 192.0.2.20
```

Replace the documentation addresses with the PC LAN interface and ESP32 address.
All options after `--` belong to the unchanged bridge, including `--port`,
`--speech-threshold`, `--silence-seconds` and `--max-audio-seconds`. Firmware
continues using its current PC destination and port; no reflash is required.
Do not run two bridges on the same UDP port.

Only completed bridge events with nonempty text and an item ID trigger inference.
Partials are ignored; duplicate item IDs within the latest 256 are ignored.
Different utterances with identical text still trigger distinct requests.
Processing is sequential, with four pending finals. Overflow drops the newest
turn with a warning rather than blocking STT. Errors/timeouts log a failure,
preserve successful history, and allow the next turn; no automatic retries.
Ctrl+C stops the orchestrator and its bridge.

Existing bridge JSONL can alternatively be supplied on stdin:

```powershell
'{"type":"transcript","item_id":"test-1","text":"What can you do?"}' | models/.venv/Scripts/python.exe -m iot_models.orchestrator --transcripts
```

## Configuration and measured metrics

[models/.env.example](../../models/.env.example) documents optional host settings.
It is not read automatically. Set variables explicitly or use `--url`/`--timeout`:

```powershell
$env:OLLAMA_URL = 'http://127.0.0.1:11434'
$env:LLM_TIMEOUT_SECONDS = '90'
```

The client uses a bounded request deadline and streaming NDJSON. First-content
latency measures request start to receipt of the first nonempty content chunk;
this is a practical first-token approximation, not per-token server timing.
Total request/generation time measures through the final `done` event, including
HTTP, loading and prompt processing. Final-transcript receipt -> response includes
any local queue wait. **STT finalization time is unavailable**, because the
unchanged bridge has no endpoint/commit timestamp. Audio `window_seconds` is a
duration, not an inference latency. This does not measure physical speech-to-reply.

## Repeatable host and live validation

```powershell
python scripts/validate.py
$env:PYTHONPATH = (Resolve-Path models/src).Path
models/.venv/Scripts/python.exe -m unittest discover -s models/tests -v
docker compose -f infrastructure/compose.yaml config --quiet
docker compose -f infrastructure/services/ollama/compose.yaml config --quiet
```

With an English mono PCM16/16 kHz WAV, replay the same audio at device cadence
on an unused loopback UDP port. These commands require live Speaches and Ollama:

```powershell
docker compose -f infrastructure/services/ollama/compose.yaml exec -T ollama ollama stop qwen3:1.7b
models/.venv/Scripts/python.exe models/tests/live_llm_smoke.py C:\path\hello.wav --stt-only --expect hello
models/.venv/Scripts/python.exe -m iot_models.orchestrator
models/.venv/Scripts/python.exe models/tests/live_llm_smoke.py C:\path\hello.wav --expect hello
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv
docker stats --no-stream infrastructure-speaches-1 iot-ollama-ollama-1
docker compose -f infrastructure/services/ollama/compose.yaml exec -T ollama ollama ps
docker compose -f infrastructure/services/ollama/compose.yaml logs --tail 100 ollama
Invoke-RestMethod http://127.0.0.1:11434/api/ps | ConvertTo-Json -Depth 6
```

Run the combined test promptly after a text turn (60-second LLM residency).
The live helper prints replay-start -> final receipt, including paced audio,
endpoint silence and STT. Compare repeated warmed runs with the same WAV, not
different audio or a cold baseline. GPU snapshots are global usage and can
include desktop/other processes; `ollama ps`, `/api/ps` and logs determine GPU
offload. Snapshots do not establish peak allocation or long-running stability.

If capacity is insufficient, first stop unused GPU workloads and reduce residency
by sending `keep_alive: 0` in the adapter to unload after each response, accepting
reload latency. A next small adjustment is Ollama flash attention plus q8_0 KV
cache (see official FAQ); repeat checks before adopting it. Do not change the
working STT model, download alternative LLMs or silently force CPU fallback.

Stop only Ollama, preserving models:

```powershell
docker compose -f infrastructure/services/ollama/compose.yaml stop ollama
```

`down` preserves the model volume unless `--volumes` is passed. Restart with
`up -d --wait ollama`. Neither command targets the Speaches project.

## Execution evidence

Executed on 2026-10-14, Windows/Docker Desktop, RTX 2050 4096 MiB, NVIDIA driver
595.79, Docker Engine 29.8.2 and Compose 5.6.0. Official Ollama 0.40.4 image is
pinned to `sha256:926d40fd6eeeebd346b5c358a63de2a10ec995371cd93dd22f1843200694b1a6`.
Installed **only qwen3:1.7b** in the new Docker model volume, digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
Its current library artifact reports 2.0B parameters, Q4_K_M, while retaining
the requested `qwen3:1.7b` tag. `/api/ps` reports 1,469,809,949 bytes VRAM and
2048 context; `ollama ps` shows **100% GPU**, logs show 29/29 layers offloaded.

| Measurement | Actual observation |
| --- | --- |
| Before Docker LLM load, with existing STT resident | 574 MiB used; 3389 MiB free |
| Docker LLM and STT resident, native LLM unloaded | 2077 MiB used; 1886 MiB free |
| Additional native LLM simultaneously resident | 3553 MiB used; one observed STT snapshot 3681 MiB |
| STT-only replay start -> `Hello.` final receipt | 1.656 s |
| Combined replay start -> same final, native LLM unloaded | 1.656 s; subsequent repeat 1.579 s |
| First combined request after native LLM unloaded | First content 2.063 s; total/end-to-end 2.188 s |
| Warm identical-prompt combined repeat | First content 0.062 s; total/end-to-end 0.187 s |
| Initial text request, overlapping native inference | First content 41.985 s; total 50.188 s |
| Warm text follow-up recalling Alex | First content 0.047 s; total 0.234 s |
| Combined request while native LLM also resident | First content 7.437 s; total/end-to-end 7.578 s |
| Idle container RAM after final combined test | Speaches 888.8 MiB; Ollama 2.233 GiB |

These are individual samples, **not a latency distribution or stability claim**.
The fast repeated-prompt result benefits from prompt caching. The initial cold
result is confounded by simultaneous native Ollama loading/inference, and must
not be interpreted as isolated Docker cold-start performance. Global VRAM
snapshots are not a continuously sampled peak. The two requested models coexisted
successfully in the observed tests, with no CPU fallback or OOM observed. Avoid
running duplicate native and Docker LLMs: this is the smallest useful adjustment
on this machine and needs no STT/model/configuration change.

Used a temporary Windows System.Speech-generated mono PCM16/16 kHz WAV saying
"Hello. What can you do?", paced through the real UDP contract. The energy gate
finalized `Hello.` separately. The same first utterance was compared in all
smoke tests. Logs for the last combined first utterance show Speaches generation
0.45 s; an earlier STT-only logged sample was 0.43 s. These isolated samples do
not quantify performance impact under continuous microphone use/concurrent load.
The Speaches container retained its ID, start time and healthy status; firmware,
realtime_bridge and the Speaches Compose file were not edited for this task.

Commands executed: both Compose `config --quiet` commands; Ollama `pull`, `up`,
`list`, `ps`, `logs`; `nvidia-smi`; `docker stats --no-stream`; `/api/ps`;
`python scripts/validate.py`; model unittest discovery; text-only two-turn chat;
STT-only and combined live smoke tests on loopback UDP ports 15009, 15019 and
15020. A repeat on port 15009 failed with WinError 10048; the sequential retry on
15019 succeeded. Default Docker startup on 11434 failed because native Ollama
owned it; the documented temporary override on 11435 succeeded. An unreachable
endpoint test logged a timeout and continued to accept input.

The installed Speaches Config inspection reports CUDA/int8 and an effective
300-second Whisper idle TTL despite the existing Compose's STT_MODEL_TTL=60
setting. This pre-existing version/configuration discrepancy was left unchanged;
do not assume STT unloads after 60 seconds when planning capacity.

Unit/host checks passed; physical ESP32 microphone/Wi-Fi regression and
long-running concurrent-load tests were not performed by this task. No firmware
build/flash was run because firmware was unchanged. The existing LAN bridge was
left running; live tests used distinct loopback UDP ports. No foundation Docker
image rebuild was needed. The Docker Ollama service remains on temporary port
11435 for this session; quit unused native Ollama and run the default `up`
command to switch it to 11434.
