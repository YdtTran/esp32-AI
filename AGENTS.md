# Project guidance

This is a foundation for an ESP-IDF voice device, ThingsBoard management and
Python inference services. Production behavior is not implemented yet.

- Before editing, read this file, the affected module's `AGENTS.md` and README,
  `docs/architecture.md`, relevant ADRs and applicable `contracts/` entries.
- Keep firmware, platform configuration and inference implementation within
  their modules. Shared interfaces in `contracts/` are authoritative.
- Follow `docs/development.md` for naming, placement, testing and Definition of
  Done. Record architectural decisions in `docs/adr/`; distinguish proposals,
  verified discoveries and accepted decisions.
- Do not assume a chip, board pinout, audio format, transport or AI model.
  Resolve the corresponding item in `docs/decisions.md` before implementation.
- Never commit credentials, real `.env` files, model weights or build output.
  Host environment variables do not provision device runtime configuration.
- Use the existing ESP-IDF v6.1 installation. Never reinstall or upgrade it
  without explicit approval. Firmware work must follow `firmware/AGENTS.md`.
- Make small changes, preserve others' work, avoid speculative abstractions
  and dependencies, and run `python scripts/validate.py` plus affected checks.
  Report exact commands, failures, skipped checks and hardware limitations.
- Treat `.codex/config.toml` as the project baseline. Keep MCP task-driven;
  no project MCP servers are needed yet. Use `.codex/agents/` role files when
  delegating, with explicit ownership; do not embed large ad hoc role prompts.
- Future `.agents/skills/` entries must use Codex-natural triggers, concrete
  workflows and artifact expectations, without Claude-only runtime assumptions.

