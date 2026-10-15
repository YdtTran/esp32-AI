#include "audio_input.h"
#include "audio_output.h"
#include "nvs_flash.h"
#include "voice_stream.h"
#include "display.h"

void app_main(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES || result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);
    ESP_ERROR_CHECK(display_init());
    ESP_ERROR_CHECK(audio_output_init());
    ESP_ERROR_CHECK(audio_input_init());
    ESP_ERROR_CHECK(voice_stream_start());
}
