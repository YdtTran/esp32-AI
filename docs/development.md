# Development conventions and commands

## Naming and placement

- Directories and Markdown/config artifacts use kebab-case; Python packages,
  C files, symbols and ESP-IDF components use snake_case. Python classes use
  PascalCase and constants use UPPER_SNAKE_CASE. Respect official generated names
  such as `CMakeLists.txt`, `sdkconfig.defaults` and `AGENTS.md`.
- Device code belongs in `firmware/`; reusable ESP-IDF code in `components/`,
  application assembly in `main/`. Keep module unit tests with their module.
- Python code belongs in `models/src/iot_models/`; LLM/STT/TTS packages appear
  only when implemented. Add tests to `models/tests/`.
- ThingsBoard artifacts belong to the relevant module's documented artifact
  directory. Shared interfaces and fixtures belong in `contracts/`.
- Cross-module checks belong in `tests/integration/`; reusable host commands in
  `scripts/`; Dockerfiles/Compose in `infrastructure/`; decisions/specs in `docs/`.
- Root files are entry-point guidance and shared tooling configuration only.
  Avoid empty placeholders, copied authoritative definitions and generated output.

## Environment categories

1. Development environment: `IDF_PATH`, `IDF_TOOLS_PATH`,
   `IDF_PYTHON_ENV_PATH`, initialized by the activation script, not `.env`.
2. Build/hardware configuration: confirmed chip, flash, partitions and pins,
   using ESP-IDF Kconfig/defaults and documented hardware evidence.
3. Service/application configuration: endpoints and credentials delivered via
   explicit service configuration and device provisioning, never compiled private
   tokens or assumed propagation of host variables onto the device.

Copy `.env.example` to `.env` only when an actual service needs it. The values are
safe placeholders and unused by the foundation; `.env` files are ignored. Each
new service documents required variables and how they are delivered.

## Host commands

No dependencies or new Python environment are needed for the checks. Use Python
3.11+. Commands work from the repository root regardless of module ownership.

PowerShell:

```powershell
python .\scripts\validate.py
docker compose -f infrastructure/compose.yaml config --quiet
. .\scripts\activate-idf.ps1 -UseInstallerProfile
idf.py --version
```

Linux:

```bash
python3 scripts/validate.py
docker compose -f infrastructure/compose.yaml config --quiet
source "$IDF_PATH/export.sh"  # existing v6.1 SDK only
idf.py --version
```

The activation script normally uses `export.ps1`; the switch is for the verified
installed-profile workaround described in `firmware/README.md`. Activation is
per shell/subprocess. Python checks do not require ESP-IDF activation.

## Tests and validation

`scripts/validate.py` checks foundation structure, JSON/TOML syntax, Python syntax,
local Markdown file links, contract registry references, supported project role
settings and runs module/integration `unittest` suites. It needs no live servers.
It does not validate a future wire schema, ThingsBoard importability or firmware.

CI runs host checks on Linux and Windows, and Compose configuration checks on
Linux. Firmware CI is deliberately absent until a chip is confirmed; then add
a v6.1 build job for the accepted target, with reproducible defaults. Live
ThingsBoard, inference and hardware tests require separate opt-in jobs after
their dependencies exist. Do not use host metadata checks as evidence for them.

For a change: run affected unit checks and the root validator; for contract
changes add producer/consumer compatibility checks; for firmware run a confirmed
target build; for platform artifacts run import/export; for deployment run
Compose config and relevant container checks. Record skipped checks and reasons.

## Definition of Done

- Implementation is in the owning module and stays within the requested scope.
- Shared interface changes follow the contract review and migration procedure.
- Relevant decisions, module setup/specifications and examples are current.
- No secrets, model weights or generated build/config output are committed.
- Required checks ran and results are reported honestly; unavailable hardware or
  external services are explicit limitations, not passed checks.
- Review covers affected responsibilities; git diff contains only intentional
  changes. New dependencies/configuration keys have a concrete need and source.

