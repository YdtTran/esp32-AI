# 0009: Local English STT to LLM prototype

The optional unified Docker speaker deployment in
[ADR 0010](0010-piper-docker-speaker-loop.md) supersedes the separate-project and
no-TTS constraints for that workflow. This record retains its original evidence.

- Date: 2026-10-14
- Status: Accepted
- Owners: AI module and infrastructure responsibilities

## Context

The user explicitly selected Qwen3 1.7B through Ollama for a Windows/Docker
Desktop RTX 2050 (4 GB) prototype. Existing English Speaches transcription works
through the UDP/WebSocket bridge in ADRs 0006 and 0007 and must be preserved.

## Decision

Keep firmware, the PCM contract, Speaches configuration and realtime_bridge
unchanged. A host Python orchestrator launches that bridge and consumes its
completed `type=transcript` JSON lines. This is an internal host process boundary;
no new network service or cross-module wire interface is exposed.

Use the official ollama/ollama:0.40.4 image (version selected from the official
release API and pinned by validated digest), independent Compose project `iot-ollama`, localhost port 11434,
NVIDIA reservation and persistent ollama-models volume. Do not include it in the
existing root stack: starting/stopping Ollama must not manage Speaches. Explicit
environment mappings set one loaded model, one parallel request, a four-request
server queue, 2048 context and 60-second idle residency. Cloud use is disabled.

Only download qwen3:1.7b from the official Ollama library, Apache-2.0, Q4_K_M,
approximately 1.4 GB on disk; runtime VRAM needs measurement. The model tag is
mutable; record its installed digest in validation. Image version updates require
repeating the checks. No host SDK/GPU library or additional Python dependency.

Isolate streaming `/api/chat` in ollama_client.py. Set think=false, num_ctx=2048,
num_predict=100, temperature=0.3 and an English system prompt forbidding unsupported
device/sensor claims. Keep three successful conversation pairs, reject inputs
over 1000 characters, and let Ollama enforce the token window (character limits
are not token counts). Process one utterance at a time. Retain 256 item IDs for
bounded duplicate suppression; identical text with a new ID is a valid new turn.
Drain bridge stdout on a separate thread; queue four finals, dropping newest
with a warning on overload. Failed requests are logged and never retried.

## Alternatives

Modifying firmware or STT is unnecessary. An orchestrator container would add
UDP networking and interactive-console complexity. LangChain or the Ollama SDK
adds no needed capability. Unloading after every request reduces residency but
forces repeated load latency; measure before changing the 60-second default.

## Consequences

Both services share the GPU without a VRAM reservation guarantee. Capacity and
STT impact require live checks. Ingress overload can drop audio as before; the
LLM queue can drop turns. Deduplication/history last only for this process.
Measurements start at host receipt of bridge output; the bridge supplies no
endpoint timestamp, so true STT finalization and speech-to-response time remain
unavailable. First-content latency approximates first-token latency at streamed
chunk granularity and includes model loading, prompt processing and HTTP overhead.
No TTS, tools, device control, MQTT or ThingsBoard integration.

## Validation

See the [run and measurements guide](../specs/local-llm-prototype.md) for executed
checks and hardware limitations.

Sources: [Docker](https://docs.ollama.com/docker),
[runtime settings](https://docs.ollama.com/faq),
[chat API](https://docs.ollama.com/api/chat),
[selected model](https://ollama.com/library/qwen3:1.7b).
