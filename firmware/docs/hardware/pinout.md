# Proposed ESP32-S3 N16R8 pinout

Update 2026-10-14: the user confirms the recorded hardware information and
240x240 ST7789 wiring, including GPIO13 backlight control. Assignments below
are user-confirmed and unchanged; earlier proposed status records scaffold
history. Electrical measurements and exact carrier-board evidence remain
outstanding. LCD implementation is in
[ADR 0011](../../../docs/adr/0011-lcd-and-web-setup.md).

Status: **Proposed; every assignment awaits hardware verification.** The task
identifies ESP32-S3 N16R8 as the intended hardware, but the exact development
board, schematic and exposed pins have not been verified. This proposal does
not accept flash/PSRAM settings or configure a build target. See
[ADR 0002](../../../docs/adr/0002-proposed-esp32-s3-hardware-scaffold.md).

The canonical GPIO definitions are in
[board_pins.h](../../components/board/include/board_pins.h). All rows below are
proposed. Supply and fixed connections are described in [wiring.md](wiring.md).

| Device | Signal | ESP32-S3 GPIO | Header definition |
| --- | --- | --- | --- |
| INMP441 | BCLK / SCK | GPIO4 | `BOARD_MIC_BCLK_GPIO` |
| INMP441 | WS | GPIO5 | `BOARD_MIC_WS_GPIO` |
| INMP441 | SD (microphone data out) | GPIO6 | `BOARD_MIC_SD_GPIO` |
| MAX98357A | BCLK | GPIO4 | `BOARD_AMP_BCLK_GPIO` |
| MAX98357A | LRC | GPIO5 | `BOARD_AMP_LRC_GPIO` |
| MAX98357A | DIN (amplifier data in) | GPIO7 | `BOARD_AMP_DIN_GPIO` |
| ST7789, 8-pin SPI breakout | MOSI / SDA | GPIO11 | `BOARD_LCD_MOSI_GPIO` |
| ST7789, 8-pin SPI breakout | SCLK / SCL | GPIO12 | `BOARD_LCD_SCLK_GPIO` |
| ST7789, 8-pin SPI breakout | RST | GPIO10 | `BOARD_LCD_RST_GPIO` |
| ST7789, 8-pin SPI breakout | DC | GPIO9 | `BOARD_LCD_DC_GPIO` |
| ST7789, 8-pin SPI breakout | CS | GPIO8 | `BOARD_LCD_CS_GPIO` |
| ST7789, 8-pin SPI breakout | BLK | GPIO13 | `BOARD_LCD_BLK_GPIO` |

## GPIO restrictions and conflict review

The ten distinct GPIOs are GPIO4 through GPIO13. The only repeated assignments
are GPIO4 (BCLK) and GPIO5 (WS/LRC), intentionally shared between microphone and
amplifier. There are no other assignment collisions. Electrical compatibility
of the shared clocks remains unresolved; see [wiring.md](wiring.md).

According to the [ESP-IDF v6.1 ESP32-S3 GPIO reference](https://docs.espressif.com/projects/esp-idf/en/v6.1/esp32s3/api-reference/peripherals/gpio.html):

- GPIO0, GPIO3, GPIO45 and GPIO46 are strapping pins.
- GPIO26 through GPIO32 are normally used for flash/PSRAM; GPIO33 through GPIO37
  are also occupied with octal flash/PSRAM. Keep memory pins reserved pending
  exact module confirmation.
- GPIO19 and GPIO20 are used by USB-JTAG by default.
- GPIO4 through GPIO13 support input and output and avoid these listed groups.

This chip-level check does not establish board-level availability. Check the
actual board schematic for LEDs, onboard peripherals and header routing before
connecting anything or adding hardware. GPIO labels are chip GPIO numbers,
not physical header positions. Use 3.3 V logic; do not connect 5 V to GPIOs.

No GPIO direction, pull resistor, clock, peripheral or backlight mode is selected
by this header. Update both hardware documents when assignments change.

The [shared I2S development implementation](../../../docs/adr/0004-shared-i2s-silent-output.md)
uses this map for microphone RX and TX, with
[PCM speaker playback](../../../docs/adr/0010-piper-docker-speaker-loop.md) now
available. Assignments remain
hardware-unverified; the software change does not establish electrical compatibility.
