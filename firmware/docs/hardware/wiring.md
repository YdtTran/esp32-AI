# Proposed hardware wiring

Update 2026-10-14: the user confirms all recorded hardware information and a
240x240 ST7789. Firmware now uses the listed LCD pins and active-high GPIO13
backlight control, SPI2 mode 0 at 10 MHz, RGB565, zero RAM offsets and inverted
panel colors. Offsets/inversion are configurable in menuconfig for panel
variants. This supersedes the undecided LCD software settings below; existing
proposed wording records historical scaffold limits. Physical electrical and
visual verification remain outstanding. See
[ADR 0011](../../../docs/adr/0011-lcd-and-web-setup.md).

Status: **Proposed; all connections require hardware verification.** Consult
[pinout.md](pinout.md) and the canonical
[board_pins.h](../../components/board/include/board_pins.h). Development firmware
now initializes shared-clock microphone RX and amplifier TX; see
[ADR 0004](../../../docs/adr/0004-shared-i2s-silent-output.md). Electrical
compatibility remains unverified and firmware does not control amplifier SD/EN.
The [Piper speaker loop](../../../docs/adr/0010-piper-docker-speaker-loop.md)
adds PCM playback on the same bus and GPIOs. Serial writes to I2S were verified;
audibility and electrical/audio timing measurements remain unverified.

## INMP441 microphone

| Breakout signal | Proposed connection |
| --- | --- |
| BCLK / SCK | ESP32-S3 GPIO4 |
| WS | ESP32-S3 GPIO5 |
| SD | ESP32-S3 GPIO6 |
| L/R | GND |
| VDD | 3V3 |
| GND | Common GND |

Confirm the breakout pin labels and L/R channel selection against its schematic
and microphone datasheet before selecting software slots. No sample rate,
sample width or channel format has been accepted.

## MAX98357A amplifier

| Breakout signal | Proposed connection |
| --- | --- |
| BCLK | ESP32-S3 GPIO4 (shared with microphone BCLK) |
| LRC | ESP32-S3 GPIO5 (shared with microphone WS) |
| DIN | ESP32-S3 GPIO7 |
| VIN | 5V supply |
| GND | Common GND |
| SPK+ / SPK- | The two speaker terminals |
| SD / EN | Verify breakout configuration; no GPIO assigned |
| GAIN | Default / unconnected, subject to breakout verification |

Verify SD/EN pull resistors, enable behavior and channel selection on the actual
breakout; do not assume that an unconnected pin enables the intended output.
Check default gain and speaker impedance/power rating before power-up. Connect
the speaker across SPK+ and SPK-; neither terminal goes to common ground.

## ST7789 8-pin SPI LCD

| Breakout signal | Proposed connection |
| --- | --- |
| MOSI / SDA | ESP32-S3 GPIO11 |
| SCLK / SCL | ESP32-S3 GPIO12 |
| RST | ESP32-S3 GPIO10 |
| DC | ESP32-S3 GPIO9 |
| CS | ESP32-S3 GPIO8 |
| BLK | ESP32-S3 GPIO13, pending backlight circuit verification |
| VCC | 3V3 |
| GND | Common GND |

SDA/SCL are the SPI data/clock labels on this proposed breakout. Verify all eight
pins against the actual display module. Check whether BLK is a logic input or
exposes the LED load, its polarity, current limiting and any onboard transistor.
Direct GPIO drive is not approved without that check; an external driver may
be required. Display dimensions, SPI host/mode/speed and PWM are undecided.

## Power and grounding

Use a common ground between ESP32-S3, microphone, amplifier, LCD and both supply
rails. The proposed microphone and LCD supply is 3.3 V; amplifier VIN is 5 V.
All ESP32-S3 signal connections use 3.3 V logic, regardless of amplifier VIN.
Never route the 5 V rail into a GPIO or the proposed 3.3 V supply pins.

Verify board power-input rules, regulator capacity and the complete current
budget, especially speaker and backlight loads. Confirm decoupling and supply
stability using the actual breakout documentation. Do not assume USB and an
external 5 V supply can be connected together without checking backfeed paths.

## Shared I2S clock compatibility remains open

GPIO4 and GPIO5 form one proposed BCLK/WS pair feeding both audio devices.
Microphone SD on GPIO6 and amplifier DIN on GPIO7 are separate data paths.
Do not connect independent clock outputs to the same nets.

ESP-IDF documents shared BCLK/WS in standard full-duplex I2S and requires
compatible RX/TX configuration; see the
[ESP-IDF v6.1 I2S reference](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html).
Before implementation, verify both devices support a common sample rate,
slot count/width, framing, polarity and channel selection. Establish a single
clock owner and check timing and signal integrity on the assembled hardware.
If incompatible, revise the proposed wiring and header before adding drivers.
The development implementation allocates paired RX/TX on one available I2S port
and retains the existing 16 kHz, 32-bit Philips I2S mono left-slot format.
TX sends zeros on GPIO7. These software settings require physical validation;
they do not resolve the shared-clock electrical review or production audio format.

Acceptance needs exact board/breakout evidence, continuity and power checks,
GPIO conflict review and measured shared-clock compatibility. Documentation
and CMake checks alone cannot verify electrical operation.
