# ThingsBoard module specification

This module owns device profiles, telemetry/attribute mappings, RPC mappings,
rule chains and dashboards. No platform version or edition is selected and no
platform artifacts are claimed to be importable yet.

The first platform change must choose edition/version in an ADR. Create only
the artifact directories needed for that change: `device-profiles/`,
`rule-chains/`, `dashboards/` and `rpc/`. Use kebab-case filenames and sanitized
JSON exports from the selected version's supported exporter/API. Review secrets,
tenant identifiers and environment-specific references before committing.

Each artifact set must include an import guide describing its source version,
required import order, external-ID/reference mapping, environment substitutions,
idempotence behavior and rollback/export procedure. Deployment scripts belong
in `infrastructure/` or `scripts/`, not inside dashboards. Keep UI changes
reproducible by exporting and reviewing their resulting diff.

Shared field semantics and RPC payloads must first be registered under
`contracts/`. Round-trip import/export in a disposable platform instance is the
future acceptance check. Host validation only checks JSON syntax at present;
there is no server to test against.

