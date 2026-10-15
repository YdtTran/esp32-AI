# Shared contracts

`registry.json` tracks authoritative interfaces, including the development
[microphone PCM stream](microphone-pcm/v1/specification.md) accepted by ADR 0006.
Its `format_version` versions repository bookkeeping only.

Before a module communicates with another, add a versioned specification under
`<kebab-case-interface>/v<major>/`, with its schema/IDL in the agreed format,
human-readable semantics, valid and invalid examples, and compatibility tests.
Do not put authoritative copies of schemas into individual modules. Generated
bindings may be placed there only with documented generation commands.

Each registry entry records `id` (kebab-case), `version` (MAJOR.MINOR.PATCH),
`specification` (repository-relative path), `producers` and `consumers` (nonempty
lists of `firmware`, `thingsboard`, `models`). These fields describe ownership;
they do not select transport or serialization.

## Change procedure

1. Identify all producers/consumers and read existing semantics and accepted ADRs.
2. Propose payload/schema and document units, encoding, errors, limits, timeout,
   ordering, authentication expectations and compatibility where relevant.
3. Record transport/serialization decisions in an ADR before implementation.
4. Classify compatibility. Breaking removals/type or semantic changes require
   a new major version and migration plan; compatible additions increment minor;
   clarifications/corrections without behavior changes increment patch.
5. Update specification, registry, examples, affected implementations and
   `tests/integration/` together. Existing consumers must tolerate any supposedly
   compatible addition; otherwise treat it as breaking.
6. Obtain review covering every listed module, including integration review.
   Retire old major versions only after all consumers migrate.

The foundation validator checks registry metadata and referenced files; actual
schema conformance requires a validator for the chosen format when introduced.
