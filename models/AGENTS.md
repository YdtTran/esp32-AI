# Inference guidance

- Read root guidance, this README, relevant decisions and contracts first.
- Python code belongs in `src/iot_models/`; unit tests belong in `tests/`.
- Add `llm/`, `stt/` or `tts/` packages only with a defined capability and accepted
  model/runtime decision. Do not introduce web frameworks or GPU libraries yet.
- Do not import firmware or ThingsBoard implementations. Define external
  request/response and audio semantics in `contracts/` before exposing a service.
- Keep weights, caches and credentials outside Git. Document model license,
  provenance, compute needs and dependency pins when models are selected.
- Use Python 3.11+; run `python scripts/validate.py` from the repository root.
  Inference accuracy and service integration require separate future checks.

