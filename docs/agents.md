# Agent setup

`AGENTS.md` is canonical global guidance. Module guidance narrows local behavior;
agents working from the root must read it explicitly before edits. Root
`CLAUDE.md` imports the canonical file with `@AGENTS.md`, avoiding copied rules.

The four `.claude/agents/*.md` files use documented YAML `name`, `description`
and `model: inherit` fields, followed by task instructions. No custom permission
mode, undocumented field or project MCP server is configured. Restart Claude
Code after introducing its first `.claude/agents/` directory, then inspect the
available agents in its agent interface. Claude Code is not installed by setup.

`.codex/config.toml` declares a compact maintenance roster using documented
`agents.<name>.description` and `agents.<name>.config_file`. Each TOML layer in
`.codex/agents/` supplies `developer_instructions`, without overriding models or
permissions. The roster covers exploration, planning, architecture, review,
security, build recovery, TDD, cleanup, E2E, docs verification and maintenance.
Project configuration requires a trusted project and a compatible Codex client.
Syntax validation does not prove a client's runtime loading; inspect agent
availability in the installed client after trusting the repository.

When delegating, assign ownership, use the configured role and report commands
and evidence. Domain Claude agents work within their module; the integration
reviewer covers contracts and reproducibility. Firmware agents activate the SDK
in each shell and distinguish builds from hardware tests.

Authoritative configuration references (checked during bootstrap):

- [Codex project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Claude subagent fields](https://code.claude.com/docs/en/sub-agents)
- [Claude canonical-file imports](https://code.claude.com/docs/en/memory)

