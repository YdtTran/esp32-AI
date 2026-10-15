#pragma once

#include "soc/gpio_num.h"

/* User-confirmed ESP32-S3 N16R8 wiring (2026-10-14); not electrically measured.
 * See firmware/docs/hardware/{pinout,wiring}.md before using these pins.
 * GPIO4 and GPIO5 are intentionally shared audio clocks.
 */

#define BOARD_MIC_BCLK_GPIO GPIO_NUM_4
#define BOARD_MIC_WS_GPIO GPIO_NUM_5
#define BOARD_MIC_SD_GPIO GPIO_NUM_6

#define BOARD_AMP_BCLK_GPIO GPIO_NUM_4
#define BOARD_AMP_LRC_GPIO GPIO_NUM_5
#define BOARD_AMP_DIN_GPIO GPIO_NUM_7

#define BOARD_LCD_MOSI_GPIO GPIO_NUM_11
#define BOARD_LCD_SCLK_GPIO GPIO_NUM_12
#define BOARD_LCD_RST_GPIO GPIO_NUM_10
#define BOARD_LCD_DC_GPIO GPIO_NUM_9
#define BOARD_LCD_CS_GPIO GPIO_NUM_8
#define BOARD_LCD_BLK_GPIO GPIO_NUM_13
