#pragma once
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

/* Start once after saved/web Wi-Fi setup; poll the provisioned PC mailbox. */
esp_err_t voice_playback_start(const char *pc_ipv4, EventGroupHandle_t connected);
