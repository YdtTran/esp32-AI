# Shared interface guidance

- Read root guidance and this README before changing any interface.
- These specifications are authoritative for every producer and consumer.
- Define payloads and semantics before module implementations; transport and
  serialization choices need an accepted ADR, not an implicit example default.
- Apply the change procedure in this README and update all consumers and tests.
- Registry metadata is tooling configuration, not an on-wire message envelope.

