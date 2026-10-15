# 0001: Minimal native monorepo foundation

- Date: 2026-10-13
- Status: Accepted
- Owners: repository maintainer and module responsibilities

## Context

The requested project separates native ESP-IDF firmware, ThingsBoard management
and Python LLM/STT/TTS services. Hardware variant, transport, platform version and
models are unconfirmed. The existing Windows SDK and Python environment must be
reused, without installing speculative dependencies.

## Decision

Use separate modules with authoritative contracts and shared documentation,
integration checks and Docker infrastructure. Adapt the installed ESP-IDF v6.1
hello_world CMake structure with a minimal log-only entry point. Select no chip.
Use Python 3.11+ and a setuptools `src/` layout with no runtime dependencies.
Setuptools is packaging metadata; bootstrap checks do not install it or the
package. Use stdlib unittest and parsing for host checks.

Use canonical AGENTS.md guidance, CLAUDE.md imports, four domain Claude subagents
and project-local Codex role layers. Do not set agent model, approval or MCP
overrides. Store ThingsBoard artifacts only after its version is selected.
Docker currently hosts validation only, using a development Python image; it
does not imply an inference or ThingsBoard deployment decision.

## Alternatives

Arduino contradicts native ESP-IDF requirements. Selecting MQTT, AI models or
prebuilt platform stacks now would bake in unreviewed assumptions. A shared
implementation directory would weaken ownership; shared definitions instead
belong in contracts. Additional test frameworks are unnecessary for host checks.

## Consequences

The repository is navigable and host validation works without installed runtime
dependencies. Firmware builds and real services remain blocked on decisions.
Production dependency locks and container digest pins are still required before
deployment. Installed-profile activation is a documented workaround for this
machine's export tool-layout mismatch, not an SDK reinstall.

## Validation

See `docs/validation.md` for executed commands and limitations. Contract metadata
checks are not wire compatibility tests, and no hardware verification is claimed.

