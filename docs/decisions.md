# Technical decisions still required

[ADR 0013](adr/0013-expanded-flash-app-partition.md) resolves development flash
capacity and the single factory application layout using recorded 16 MiB flash
detection. PSRAM operation and production OTA/storage layout remain unresolved.

[ADR 0012](adr/0012-open-captive-setup-and-animated-status.md) accepts the user's
requested open captive setup AP and animated status. Automatic popup behavior
depends on the client OS; production provisioning/security remain unresolved.

[ADR 0011](adr/0011-lcd-and-web-setup.md) resolves development LCD configuration
and browser setup with NVS persistence. The user confirmed 240x240 ST7789 and
the documented wiring on 2026-10-14; physical visual/electrical checks and
production credential protection remain open.

[ADR 0010](adr/0010-piper-docker-speaker-loop.md) resolves development Piper CPU
voice selection, unified Docker inference deployment and ESP32 HTTP PCM playback.
Production security, audio/hardware acceptance and model deployment remain open.

[ADR 0009](adr/0009-local-llm-prototype.md) resolves the development-only English
LLM selection (Qwen3 1.7B via independent Ollama Docker) and host orchestrator.
Production LLM/TTS, deployment and tool/control decisions remain open.

[ADR 0007](adr/0007-speech-endpoint-buffer.md) replaces default fixed transcription
windows with adjustable silence detection and a bounded PC-side speech buffer.

[ADR 0006](adr/0006-microphone-realtime-prototype.md) resolves development-only
voice routing (UDP to PC bridge, local Speaches WebSocket), audio (existing
16 kHz PCM16 converted to 24 kHz), English STT model and volatile serial-console
configuration. The table below still applies to production choices, playback,
LLM/TTS and hardware acceptance. These prototype choices do not resolve them.

[ADR 0005](adr/0005-speaches-development-deployment.md) accepts standalone
Speaches GPU infrastructure for local development, without model selection,
inference pipelines or production deployment/access-control decisions.

[ADR 0004](adr/0004-shared-i2s-silent-output.md) accepts a development-only shared
I2S implementation with silent TX and the existing 16 kHz, 32-bit microphone
configuration. Hardware compatibility and production audio requirements remain
unresolved.

None of these choices is implied by the scaffold. Accepted bootstrap choices
are recorded in [ADR 0001](adr/0001-monorepo-foundation.md).

[ADR 0002](adr/0002-proposed-esp32-s3-hardware-scaffold.md) records the requested
ESP32-S3 N16R8 pin/scaffold proposal. It does not resolve the hardware decisions
below; assignments and electrical compatibility still await verification.

[ADR 0003](adr/0003-esp32s3-build-target.md) accepts the esp32s3 build target
after the user confirmed ESP32-S3 N16R8 on 2026-10-13. Carrier-board details
and memory/electrical configuration remain open.

| Decision | Evidence needed / owner | Blocks |
| --- | --- | --- |
| Exact carrier board | ESP32-S3 N16R8 module confirmed by user; carrier-board marking/schematic still needed; firmware | Board-specific configuration and hardware validation |
| Flash, partitions, RAM/PSRAM and GPIOs | Board schematic/specification; firmware | Storage, drivers and resource budgets |
| Microphone, codec, speaker and audio format | Hardware list and audio requirements; firmware + AI | Capture/playback components and audio contract |
| Device management transport | Deployment/network/security requirements; firmware + ThingsBoard | Telemetry/RPC adapters; no MQTT default selected |
| Voice routing and transport | Latency, bandwidth, streaming and failure requirements; all modules | Device-to-inference communication |
| Serialization and payload semantics | Producer/consumer needs; integration | Initial versioned schemas and examples |
| LLM, STT, TTS models and runtimes | Languages, latency, quality, license and compute budget; AI | Inference dependencies and endpoints |
| ThingsBoard edition/version | Required features and supported export/import behavior; ThingsBoard | Reproducible platform artifacts and server images |
| Credentials/provisioning and access control | Trust boundaries and deployment constraints; maintainer + module owners | Secure runtime configuration |
| Deployment and dependency pins | Compute/storage requirements and operational environment; maintainer | Production Compose stack, locked environments |

To resolve an item: gather evidence, propose an ADR with alternatives and
consequences, review affected boundaries, mark it accepted and update this table,
module documentation, contracts and checks together. Do not mark a decision
accepted just because a dependency or SDK has a convenient default.


