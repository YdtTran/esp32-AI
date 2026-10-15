#pragma once
#include "esp_err.h"
#include <stdbool.h>
/* Owns ST7789 SPI2 and board LCD pins. Updates copy strings for its render task. */
esp_err_t display_init(void);
void display_status(const char *state, const char *detail, const char *pc);
void display_setup(const char *ssid);
/* Success means a valid response from the configured speaker mailbox, not
 * health of every inference service. Call on each poll or download failure. */
void display_server_update(bool reachable);
