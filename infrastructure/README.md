# Docker infrastructure

The optional complete speaker loop uses `voice-compose.yaml` for Speaches,
Ollama, CPU Piper and bridge/orchestration, reusing the existing model volumes.
Start via `scripts/start-voice-assistant.ps1`; see the
[speaker guide](../docs/specs/speaker-loop.md) and
[ADR 0010](../docs/adr/0010-piper-docker-speaker-loop.md). Compose 2.24.4+ is needed
for its port override. The earlier independent service workflows below remain
available after stopping the unified stack.

Ollama is an independent optional Compose project under
`services/ollama/compose.yaml`, with its own GPU reservation/model volume and
localhost port 11434. It is deliberately not included in the working Speaches
stack. See the [LLM run guide](../docs/specs/local-llm-prototype.md) and
[ADR 0009](../docs/adr/0009-local-llm-prototype.md) for setup and measurements.

The English realtime prototype uses the same pinned deployment and cache.
`LOOPBACK_HOST_URL=http://127.0.0.1:8000` lets this image's realtime handler reach
its own transcription API; the default internal ASGI path returned HTTP 404.
The prototype installed Systran/faster-distil-whisper-small.en into the persistent
cache and verified paced UDP transcription. See the
[run guide](../docs/specs/realtime-microphone-prototype.md) and
[ADR 0006](../docs/adr/0006-microphone-realtime-prototype.md). Earlier setup-only
model-cache observations below describe the initial deployment, not current state.

`compose.yaml` is the central entry point and includes definitions from
`services/<service>/compose.yaml`. Docker Compose 2.20.3+ is required.
Speaches needs Docker Desktop's WSL2 backend with NVIDIA GPU support. Its official
`latest-cuda` image is pinned by digest to the image validated during setup;
updates require changing the digest and repeating deployment checks.

From `E:\Workspace\Projects\IoT` (the repository root):

```powershell
docker compose -f infrastructure/compose.yaml config --quiet
docker compose -f infrastructure/compose.yaml pull speaches
docker compose -f infrastructure/compose.yaml up -d --wait speaches
docker compose -f infrastructure/compose.yaml logs -f speaches
docker compose -f infrastructure/compose.yaml ps speaches
docker compose -f infrastructure/compose.yaml exec speaches nvidia-smi
docker compose -f infrastructure/compose.yaml stop speaches
```

API base: <http://localhost:8000/v1>. Health: <http://localhost:8000/health>.
API documentation: <http://localhost:8000/docs>. The host port is bound to
localhost; remote/device access and authentication need a separate decision.
To change the host port, copy `.env.example` to `.env` in this directory and add
`--env-file infrastructure/.env` before `-f` in the commands above. These values
control Compose interpolation; Speaches settings are explicitly mapped in its
service definition. The root repository's `.env.example` is unrelated.

The named `speaches-hf-hub-cache` volume persists across container recreation.
`stop` preserves the container and cache; `down` removes this Compose project's
containers/network but keeps the cache unless `--volumes` is supplied.
Do not remove the volume when retaining downloaded models.

No models are preloaded or downloaded by setup. The Gradio UI is disabled.
Setup verified a healthy container, RTX 2050 visibility, HTTP 200 from health/API
schema endpoints, and an empty model cache on 2026-10-14.
For later STT use, CUDA/int8 and 60-second idle unloading reduce memory pressure;
they do not guarantee that a model fits the RTX 2050's 4 GB VRAM. Model selection
and inference pipelines remain undecided. Inference/model-install requests can
download models; do not issue them during infrastructure validation.

The existing `foundation-checks` configuration is under its service directory
and uses the `checks` profile so normal startup runs only Speaches. The unchanged
root `Dockerfile` builds the repository-wide Python validation environment;
it stays here because `scripts/validate.py` requires this foundation path.
Run it explicitly as before:

```powershell
docker compose -f infrastructure/compose.yaml run --build --rm foundation-checks
```

Future services should keep their Compose settings and any Dockerfile/config
under `services/<service>/`, then add an include to the root Compose file.
Relative paths resolve from each included service directory. Use unique service
and volume names; document ports, persistence and explicit environment mappings.
Ollama uses a separate Compose project as documented above. See [ADR 0005](../docs/adr/0005-speaches-development-deployment.md)
for the development deployment decision and validation limits.

References: [official installation](https://speaches.ai/installation/),
[configuration variables](https://speaches.ai/configuration/),
[Compose include](https://docs.docker.com/compose/how-tos/multiple-compose-files/include/).
