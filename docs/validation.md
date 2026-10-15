# Bootstrap validation

Date: 2026-10-13. This file records bootstrap evidence, not continuous build
status. See `docs/development.md` for commands to rerun after changes.

The repository was empty except for `.git`, with no initial commits. All three
confirmed ESP-IDF development paths existed; the three environment variables
were initially unset in the agent shell.

Official `export.ps1` failed: it expected tool versions below the SDK tool
manager's conventional directory layout, while this installer stores tools
directly below `C:\Espressif\tools`. The existing
`Microsoft.v6.1.PowerShell_profile.ps1` successfully activated those same paths.
No installation, SDK upgrade or new Python environment was performed.

Observed in the installed profile environment:

- `idf.py --version`: ESP-IDF v6.1.
- `idf.py --help`: available, including `create-component`; no target selected.
- Xtensa and RISC-V GCC: esp-15.2.0_20251204, GCC 15.2.0.
- CMake: 4.0.3; Ninja: 1.12.1; existing Python: 3.11.15.

Executed foundation checks:

| Command / check | Result |
| --- | --- |
| `python scripts/validate.py` on Windows | Passed structure, JSON/TOML/Python syntax, file links, registry and agent settings; 7 host tests passed |
| PowerShell parser on `scripts/activate-idf.ps1` | Passed |
| `. ./scripts/activate-idf.ps1` in a fresh agent shell | Expected actionable failure for the existing exporter layout mismatch; no installation attempted |
| `. ./scripts/activate-idf.ps1 -UseInstallerProfile` | Passed path checks, SDK version and compiler/CMake/Ninja command execution |
| `idf.py -C firmware create-component --help` after activation | Passed; `-C` component output option supported; no component generated |
| `docker compose -f infrastructure/compose.yaml config --quiet` | Passed with Compose v5.6.0 |
| `docker compose -f infrastructure/compose.yaml run --build --rm foundation-checks` | Image built and Linux container validation passed, including all 7 tests; Docker server 29.8.2 |
| YAML parsing of workflow, Compose and four Claude frontmatter blocks | Passed using already-installed PyYAML in the confirmed ESP-IDF Python environment; not a new project dependency |
| Git ignore spot checks | Secrets, firmware generated output and model weights ignored; `.env.example` and `sdkconfig.defaults` remain trackable |

Generated firmware files: `CMakeLists.txt`, `main/CMakeLists.txt`,
`main/app_main.c`, `sdkconfig.defaults`, module guidance and component placement
documentation. No example-generated configuration/build directories were copied.
No reusable component has a defined interface yet, so none was generated.

Firmware target is unconfirmed: `set-target`, firmware build, flash and hardware
tests are deliberately not run. No ThingsBoard import or inference accuracy
tests are possible yet. GitHub Actions jobs have not run remotely; workflow YAML
syntax and their equivalent local checks were exercised. Agent runtime loading
requires the corresponding installed client; configuration syntax checks alone
do not prove it. Python wheel packaging was not built or installed.

