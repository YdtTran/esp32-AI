# Voice AI IoT monorepo

Native ESP-IDF firmware, ThingsBoard artifacts and Python inference services.
The development voice loop runs STT, Ollama and Piper in Docker and returns
speech to ESP32 shared I2S. See the [speaker loop guide](docs/specs/speaker-loop.md)
for startup, firmware flashing and the remaining physical hardware checks.

| Path | Responsibility / read first |
| --- | --- |
| `firmware/` | Device application and ESP-IDF components; `AGENTS.md`, `README.md` |
| `thingsboard/` | Versioned profiles, rule chains, dashboards and RPC mappings |
| `models/` | Python bridge, LLM orchestration, Piper synthesis and speaker mailbox |
| `contracts/` | Authoritative cross-module specifications and examples |
| `docs/` | Architecture, ADRs, decisions and development conventions |
| `infrastructure/` | Docker voice stack and development checks |
| `tests/` | Cross-module integration and compatibility checks |
| `scripts/` | Reproducible activation and validation commands |

Start with [project guidance](AGENTS.md), [architecture](docs/architecture.md),
[development commands](docs/development.md) and [open decisions](docs/decisions.md).
Agent configuration is explained in [the agent guide](docs/agents.md).

PowerShell (Python 3.11+):

```powershell
python .\scripts\validate.py
. .\scripts\activate-idf.ps1
```

On this machine, `export.ps1` currently fails to locate the flat installer tool
layout. Use its existing installed profile, without installing anything:

```powershell
. .\scripts\activate-idf.ps1 -UseInstallerProfile
```

Linux (Python 3.11+):

```bash
python3 scripts/validate.py
# Only when using an existing ESP-IDF v6.1 installation:
source "$IDF_PATH/export.sh"
idf.py --version
```

Do not run a firmware build until the actual chip is confirmed. See
[firmware setup](firmware/README.md) and [bootstrap validation](docs/validation.md).
