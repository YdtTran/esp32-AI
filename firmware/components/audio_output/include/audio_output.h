#ifndef AUDIO_OUTPUT_H
#define AUDIO_OUTPUT_H


#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Starts the shared bus with continuous digital silence between playback writes. */
esp_err_t audio_output_init (void);
/* One caller owns begin/write/end; capture observes active to upload silence. */
void audio_output_begin(void);
bool audio_output_active(void);
esp_err_t audio_output_write(const int32_t *samples, size_t count);
void audio_output_end(void);

#endif // AUDIO_OUTPUT_H
