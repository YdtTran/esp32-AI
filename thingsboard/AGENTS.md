# ThingsBoard guidance

- Read root guidance, this README and applicable contracts/ADRs first.
- Store sanitized, reproducible platform artifacts here; no UI-only changes.
- Select and record edition/version before creating exports or deployment files.
- Keep telemetry fields, RPC methods, units and compatibility in `contracts/`;
  platform mappings implement those specifications rather than redefining them.
- Never export real device tokens, tenant data or credentials into Git.
- Test import/export against the documented platform version and record evidence.
  Repository JSON validation alone does not prove platform compatibility.

