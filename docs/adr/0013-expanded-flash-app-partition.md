# 0013: Expand the development application partition

- Date: 2026-10-15
- Status: Accepted
- Owners: firmware

## Context

The user requested more firmware capacity after the application reached
1,020,464 bytes in a 1 MiB factory partition. The confirmed module is ESP32-S3
N16R8. The recorded device boot log described in firmware/README.md detects
16,384 KiB of physical flash while the old image header selects 2 MiB.

## Decision

Select 16 MiB flash in sdkconfig.defaults and a custom partitions.csv using
the existing single factory application layout. Preserve NVS at 0x9000 with
size 0x6000, PHY initialization at 0xf000 with size 0x1000, and the application
start at 0x10000. Expand the application to 0xff0000 bytes (15.9375 MiB), ending
at the 16 MiB flash boundary. This replaces the bootstrap flash-size and
partition defaults described in [ADR 0003](0003-esp32s3-build-target.md).

The user's capacity request accepts this development layout based on the
existing hardware evidence. Flash mode/frequency, PSRAM, pins, audio and shared
interfaces retain their existing settings. OTA and filesystem storage are
outside this layout; adding them requires repartitioning.

## Alternatives

A smaller factory partition would leave unallocated space with no current
consumer. Two OTA slots would reduce per-image capacity and introduce an update
layout before an OTA implementation exists.

## Consequences

Fresh configurations reproduce the expanded layout. Existing sdkconfig files
must also select 16 MiB flash and the custom partition table: defaults do not
override existing choices. Flash the complete build, including bootloader and
partition table, to apply the layout. Keep NVS intact; do not erase flash.
The unchanged NVS offsets preserve saved setup settings during a normal flash.
Flash capacity is separate from runtime RAM and does not enable PSRAM.

## Validation

Executed on 2026-10-15 with the existing ESP-IDF v6.1 installation:

- `idf.py -C firmware build` passed for esp32s3: 1,020,464-byte application,
  0xef6dd0 bytes (94%) free in the 0xff0000-byte partition.
- The SDK's `gen_esp32part.py --flash-size 16MB` accepted the CSV; decoding the
  generated partition-table binary confirmed the three intended offsets/sizes.
  Generated flasher arguments select 16MB and retain DIO/80 MHz.
- `python scripts/validate.py` passed foundation structure/syntax/link checks,
  but its model suite failed on the existing unexpected `speaker` argument to
  `print_reply` in `models/tests/test_speaker_pipeline.py` (34 passed, 1 error).
  Later suites were not reached by that command.
  After the separate orchestrator speaker fix, the validator passed all 37
  model tests and 8 integration tests.
- `git diff --check` passed.

Compilation does not establish physical access across all 16 MiB. This change
has not been flashed; on-device boot and capacity checks were not run.
