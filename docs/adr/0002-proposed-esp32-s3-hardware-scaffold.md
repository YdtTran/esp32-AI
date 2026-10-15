# 0002: Proposed ESP32-S3 hardware scaffold

- Date: 2026-10-13
- Status: Proposed
- Owners: firmware

The user confirmed the documented wiring and 240x240 LCD on 2026-10-14.
[ADR 0011](0011-lcd-and-web-setup.md) accepts LCD implementation using that map;
physical verification remains separate from this confirmation.

## Context

The requested hardware foundation identifies ESP32-S3 N16R8, INMP441,
MAX98357A and an 8-pin ST7789 SPI breakout. Exact board schematics, breakout
configuration and electrical evidence are unavailable. The task explicitly
limits changes to pin definitions, documentation and official component stubs.

## Decision

Propose the GPIO map in
[board_pins.h](../../firmware/components/board/include/board_pins.h), documented
in the [pinout](../../firmware/docs/hardware/pinout.md) and
[wiring](../../firmware/docs/hardware/wiring.md). Generate `board`, `audio_input`,
`audio_output` and `display` using the existing ESP-IDF v6.1 CLI, preserving its
raw output. Do not implement drivers, configure peripherals or accept memory,
audio or production target settings. All assignments remain proposed until
hardware verification and review.

## Alternatives

Separate I2S clock pairs remain an option if shared clocks prove incompatible.
Selecting alternate GPIOs without board evidence would replace one unverified
map with another. Peripheral implementation is outside this task.

## Consequences

Future drivers have a central proposed pin map and documented validation gaps.
GPIO4/5 are intentionally shared, requiring a compatible clock configuration.
Amplifier SD/EN and LCD backlight wiring depend on the actual breakouts. Raw
component placeholders do not define functional APIs. Existing application
composition and build defaults remain unchanged.

## Validation

Executed on 2026-10-13 from the repository root, using the existing v6.1 SDK:

```powershell
. .\scripts\activate-idf.ps1 -UseInstallerProfile
idf.py --version
idf.py create-component --help
```

The activation verified all three documented environment paths and compiler,
CMake and Ninja availability. From `firmware/`, all four generation commands
passed:

```powershell
idf.py create-component -C components board
idf.py create-component -C components audio_input
idf.py create-component -C components audio_output
idf.py create-component -C components display
```

Configure-only and host checks passed, from the repository root:

```powershell
$scaffoldBuildPath = Join-Path (Get-Location) 'firmware\build-scaffold'
idf.py -C firmware -B $scaffoldBuildPath -D IDF_TARGET=esp32s3 -D "SDKCONFIG=$scaffoldBuildPath\sdkconfig" -D 'COMPONENTS=main;board;audio_input;audio_output;display' reconfigure
python scripts/validate.py
```

`project_description.json` lists all four components for `esp32s3`. CMake
reported the expected `MINIMAL_BUILD` override for this explicit component list
and unavailable Git version metadata because the repository has no `HEAD` yet;
configuration still passed. Generated config/output stays in the ignored
`firmware/build-scaffold/`; production defaults and application files are unchanged.
The host validator passed, including seven unit tests.

Inline Python checks (`python -`, script supplied on standard input) verified
the generated template content, component file sets, all twelve intended header
constants and ten distinct pins. The only duplicate assignments are the shared
BCLK and WS/LRC pairs. An initial byte comparison failed on template line endings;
the corrected comparison normalizes line endings and passes. No scaffold files
were altered to satisfy that check.

The header also passed twelve C11 static assertions supplied on standard input
to this compiler command in the activated shell:

```powershell
xtensa-esp32s3-elf-gcc -std=c11 -Wall -Wextra -Werror -fsyntax-only -x c -I firmware/components/board/include -I E:/esp/.espressif/v6.1/esp-idf/components/esp_hal_gpio/esp32s3/include -
```

`idf.py build`, flashing and hardware tests were skipped: the exact board and
electrical assumptions remain unverified, and this task only requires scaffold
validation. These software checks do not establish physical compatibility.
Acceptance still needs
board/module identification, schematic review, power/backlight/enable checks
and measured shared I2S timing compatibility. No build or hardware test is
required for this proposal.
