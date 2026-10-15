#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SPEAKER_PCM_MAX_BYTES 1920000
#define SPEAKER_PCM_FORMAT "pcm-s16le-16000-mono"

static inline bool speaker_pcm_length_valid(int64_t length)
{
    return length > 0 && length <= SPEAKER_PCM_MAX_BYTES && length % 2 == 0;
}

static inline int32_t speaker_pcm_word(const uint8_t *sample)
{
    int32_t value = (int32_t)sample[0] | ((int32_t)sample[1] << 8);
    if (value >= 32768) value -= 65536;
    return value * 65536;
}
