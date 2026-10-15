#pragma once
#include <stddef.h>
#include <stdint.h>

/* microphone-pcm v1: independent of host byte order. */
static inline void voice_pcm_encode(const int32_t *raw, uint8_t *pcm, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        uint16_t value = (uint16_t)(raw[i] >> 16);
        pcm[2 * i] = (uint8_t)value;
        pcm[2 * i + 1] = (uint8_t)(value >> 8);
    }
}
