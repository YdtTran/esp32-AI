# Cross-module tests

`integration/` currently tests the contract registry's ownership and reference
rules using valid and malformed metadata. These are host foundation tests,
not network, inference or hardware tests. `scripts/validate.py` runs them along
with module tests. Future integration tests should consume the authoritative
contract examples and validate both producers and consumers.

Use explicit opt-in commands for live services and hardware, documenting
required versions, credentials, cleanup and expected outputs. Keep fixtures
sanitized. Do not make basic validation depend on private infrastructure.

