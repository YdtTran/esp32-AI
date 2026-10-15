# Integration test guidance

- Read root guidance, contracts and affected module guidance before tests.
- Put cross-module compatibility checks in `integration/`; module unit tests
  stay with their module. Hardware tests must identify board and test procedure.
- Test authoritative contract examples across producer/consumer boundaries.
- Use dependency-free `unittest` for foundation checks. Introduce additional
  harnesses only for a concrete need, with setup and CI documentation.
- Report host checks, firmware builds, live platform tests and hardware tests
  separately. Do not label metadata tests as end-to-end system validation.

