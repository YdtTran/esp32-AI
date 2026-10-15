# Architecture and module ownership

Firmware now includes a 240x240 ST7789 status screen and NVS-backed first-time
Wi-Fi/PC web setup. See [ADR 0011](adr/0011-lcd-and-web-setup.md) and the
[firmware guide](../firmware/README.md). Setup HTTP exists only during setup;
the microphone and speaker contracts are unchanged.

[ADR 0012](adr/0012-open-captive-setup-and-animated-status.md) adds the requested
open setup AP, captive DNS/HTTP discovery and animated Wi-Fi/mailbox/playback
status. A recent speaker mailbox response establishes PC reachability only.

The complete development loop adds Docker CPU Piper and ESP32 HTTP PCM playback
after the streaming LLM orchestrator. STT, Ollama, Piper and bridge/orchestration
run in the unified optional voice stack. See
[ADR 0010](adr/0010-piper-docker-speaker-loop.md),
[speaker contract](../contracts/speaker-pcm/v1/specification.md) and
[run guide](specs/speaker-loop.md). The earlier terminal-only flow below remains
available without TTS options.

The local English LLM prototype adds completed bridge transcripts -> host Python
orchestrator -> independent Ollama Qwen3 1.7B -> terminal, preserving the existing
firmware and STT path. See [ADR 0009](adr/0009-local-llm-prototype.md) and the
[run guide](specs/local-llm-prototype.md). No tools, device control or TTS.

Status: English microphone transcription prototype through a PC UDP/WebSocket
bridge ([ADR 0006](adr/0006-microphone-realtime-prototype.md),
[run guide](specs/realtime-microphone-prototype.md)), with a standalone Speaches GPU deployment
([ADR 0005](adr/0005-speaches-development-deployment.md)). Read [open decisions](decisions.md) before implementing
device communication, inference or platform deployment.
Firmware now has development microphone capture and shared-clock silent speaker
output; [ADR 0004](adr/0004-shared-i2s-silent-output.md) defines bus ownership and
the remaining hardware validation limits.
The confirmed esp32s3 software build target is recorded in
[ADR 0003](adr/0003-esp32s3-build-target.md); peripheral hardware remains proposed.

| Module | Owns | Boundary |
| --- | --- | --- |
| Firmware engineer / `firmware/` | Device composition, drivers, audio I/O, device adapters | No server inference or platform dashboard logic |
| ThingsBoard engineer / `thingsboard/` | Device profiles, telemetry mappings, RPC mappings, rule chains, dashboards | No firmware drivers or AI model implementation |
| AI engineer / `models/` | Inference adapters and future LLM/STT/TTS execution | No board configuration or authoritative platform payload copies |
| Integration reviewer / `contracts/`, `tests/` | Shared semantics, compatibility and integration evidence | Review involves every affected producer/consumer |
| Maintainer / `infrastructure/`, `scripts/`, `docs/` | Setup, deployment definitions, CI, architecture and decisions | No environment-specific secrets in tracked files |

These are responsibilities, not invented human assignments. A change touching
several modules needs review across those responsibilities. Adapters implement
contracts; modules do not import another module's implementation.

## Prototype and intended production interaction

The prototype sends microphone PCM over UDP to a PC bridge, which buffers speech
until silence or a hard duration cap ([ADR 0007](adr/0007-speech-endpoint-buffer.md)), then uploads to
local Speaches and prints English transcripts. This does not route through
ThingsBoard. Its transport/audio contract and volatile console setup are
development-only choices in ADR 0006.
Optional local compiled Wi-Fi settings are accepted in
[ADR 0008](adr/0008-local-compiled-wifi.md).

Production firmware will exchange management data and RPC with ThingsBoard and voice
requests/results with inference services. Whether the latter is direct or routed
through a gateway/platform remains undecided. ThingsBoard manages devices;
LLM/STT/TTS execution belongs in `models/`. Routing, security, audio encoding,
streaming, retries and timeouts need accepted decisions and contracts first.

The development microphone PCM wire interface is in `contracts/registry.json`.
Management and production voice interfaces remain undecided. Repository
metadata must not be mistaken for a wire protocol.

## Documentation conventions

This file is the architecture index: keep ownership, boundaries, current state
and decision links here. Put module specifications and setup in module READMEs;
add focused `docs/specs/<kebab-case-topic>.md` files only when a feature needs one.
Specs state status, scope, inputs/outputs, contract links, behavior and validation.
Identify planned behavior explicitly rather than presenting it as implemented.

ADRs describe significant cross-module, hardware, transport, model and deployment
choices. Use numbered records in `docs/adr/`, following its README and template.
Use relative links to canonical definitions rather than copying specifications.
Record discoveries with evidence, command output summaries and limitations in the
relevant module guide or decision log; transient work notes need not be committed.


