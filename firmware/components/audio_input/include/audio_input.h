#ifndef AUDIO_INPUT_H
#define AUDIO_INPUT_H

#pragma once

#include "esp_err.h"
#include <stddef.h>
#include <stdint.h>

esp_err_t audio_input_init (void);

esp_err_t audio_input_read (int32_t* buffer, size_t sample_count, size_t* samples_read);

#endif // AUDIO_INPUT_H