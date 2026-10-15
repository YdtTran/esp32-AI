#pragma once
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
/* Initializes Wi-Fi and blocks until configured and connected. Call once.
 * BIT0 tracks station IPv4 connectivity; address receives the saved PC IPv4. */
esp_err_t voice_setup_connect(char address[16], EventGroupHandle_t connected);
