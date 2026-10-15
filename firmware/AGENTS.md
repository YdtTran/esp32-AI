# Firmware guidance

- Read the root guidance, this module's README and applicable contracts/ADRs.
- Inspect the environment on every new shell/subprocess. In PowerShell source
  `scripts/activate-idf.ps1` from the repository root; use the documented
  `-UseInstallerProfile` switch for this machine's current export-layout issue.
  Verify the three paths, `idf.py --version` and compiler availability.
- Use native ESP-IDF v6.1 CMake. Adapt official examples and use supported
  `idf.py` project/component commands rather than duplicating generated files.
- Confirm chip and board first. Do not accept ESP-IDF's implicit default target.
  No flash, partition, pin or audio settings may be invented.
- Keep `main/app_main.c` for composition; reusable code belongs in `components/`.
  Define a component's responsibility and public interface before creating it.
- Use Kconfig and reviewed `sdkconfig.defaults` for compile-time configuration;
  design runtime provisioning separately. Never embed device tokens.
- After firmware changes, build for the documented confirmed target. Until
  confirmation, run host foundation checks and report the build as skipped.
  Compilation never establishes hardware functionality.
- Never reinstall or upgrade ESP-IDF without explicit approval.
- Consult `components/board/include/board_pins.h` for GPIO assignments; do not
  hardcode GPIO numbers in peripheral implementations. The current assignments
  are proposed, not hardware-verified; read `docs/hardware/pinout.md` and
  `docs/hardware/wiring.md` before using them.
- When assignments change, update the header and both hardware documents.
  Check GPIO conflicts, memory/boot restrictions and board-specific usage
  before adding hardware; shared audio clocks require compatibility validation.
- Keep generated component stubs unchanged during scaffolding. Do not implement
  peripheral drivers or initialize hardware unless explicitly requested.

