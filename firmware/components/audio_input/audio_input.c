#include "audio_input.h"
#include "audio_bus.h"

esp_err_t audio_input_init(void)
{
    return audio_bus_init();
}

esp_err_t audio_input_read(int32_t *buffer, size_t sample_count, size_t *samples_read)
{
    return audio_bus_read(buffer, sample_count, samples_read);
}
