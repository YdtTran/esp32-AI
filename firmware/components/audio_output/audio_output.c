#include "audio_output.h"
#include "audio_bus.h"
#include <stdatomic.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static atomic_bool active;

esp_err_t audio_output_init(void) {
    return audio_bus_init();
}

void audio_output_begin(void) { atomic_store(&active, true); }
bool audio_output_active(void) { return atomic_load(&active); }
esp_err_t audio_output_write(const int32_t *samples, size_t count)
{
    return audio_bus_write(samples, count);
}
void audio_output_end(void)
{
    /* Covers the default TX DMA tail and room echo; actual acoustics need testing. */
    vTaskDelay(pdMS_TO_TICKS(300));
    atomic_store(&active, false);
}
