# 0003: Confirmed ESP32-S3 build target

- Date: 2026-10-13
- Status: Accepted
- Owners: firmware

The bootstrap flash-size and partition defaults below are replaced by
[ADR 0013](0013-expanded-flash-app-partition.md); target selection remains valid.

## Context

The first firmware build was requested. The user explicitly confirmed the
hardware as ESP32-S3 N16R8 in this session. This is user-provided module
identification; no board photo, carrier schematic or connected-device inspection
was performed. Earlier generated sdkconfig selected esp32 implicitly.

## Decision

Select esp32s3 with the existing ESP-IDF v6.1 installation and persist
CONFIG_IDF_TARGET="esp32s3" in firmware/sdkconfig.defaults. This resolves the
chip target for software compilation. ADR 0002 remains proposed for pins and
peripherals. Exact carrier-board identification, memory operating settings,
partitions and electrical compatibility require separate evidence and review.

## Alternatives

Keeping the implicit esp32 target would compile for the wrong chip. Delaying
software compilation until every peripheral is verified is unnecessary for the
log-only foundation. Enabling PSRAM or changing flash parameters without
reviewed operating settings would exceed target selection.

## Consequences

Fresh configurations have an explicit chip target. ESP-IDF set-target preserved
the previous generated configuration as sdkconfig.old. The initial build uses
SDK defaults (2 MB flash image setting, PSRAM disabled and factory partition);
these are software bootstrap settings, not acceptance of the N16R8 memory
configuration. The minimal build includes main and its dependencies; unused
peripheral component stubs remain unchanged and are not compiled.

## Validation

Executed from the repository root on Windows:

```powershell
. .\scripts\activate-idf.ps1 -UseInstallerProfile
idf.py -C firmware set-target esp32s3
idf.py -C firmware build
```

Activation verified all three documented paths, ESP-IDF v6.1, both compilers,
CMake and Ninja. Target selection and build passed. Generated voice_device.bin
is 0x249f0 bytes (150000), with 86% of the 1 MB app partition free. Bootloader
size is 0x5280 bytes. Build output remains ignored. Git version discovery
reported unavailable HEAD because the repository has no initial commit; it did
not prevent compilation.

The initial sandbox activation failed because Git could not read user ignore
configuration; rerunning with approved access passed. Flashing, boot monitoring,
peripheral and electrical tests were not run. Compilation does not establish
hardware functionality. See firmware/README.md for reproduction commands.
