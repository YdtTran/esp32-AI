#pragma once

#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

/* Owns the shared I2S RX/TX pair. Initialize from app_main only.
 * Repeated initialization succeeds without allocating another pair.
 * TX sends silence between writes; RX supplies mono left-slot microphone words.
 */
esp_err_t audio_bus_init(void);
esp_err_t audio_bus_read(int32_t *buffer, size_t sample_count, size_t *samples_read);
/* Single playback producer; signed samples already aligned to 32-bit I2S. */
esp_err_t audio_bus_write(const int32_t *buffer, size_t sample_count);
