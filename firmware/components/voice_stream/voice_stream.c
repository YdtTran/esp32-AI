#include "voice_stream.h"
#include "voice_pcm.h"
#include "audio_input.h"
#include "audio_output.h"
#include "voice_playback.h"
#include "voice_setup.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include <errno.h>
#include <string.h>

#if CONFIG_AUDIO_BUS_SAMPLE_RATE != 16000
#error "microphone-pcm v1 requires 16000 Hz"
#endif

static const char *TAG = "voice_stream";
static EventGroupHandle_t connected;

static void stream_task(void *arg)
{
    char address[16];
    connected = xEventGroupCreate();
    if (!connected) { vTaskDelete(NULL); return; }
    ESP_ERROR_CHECK(voice_setup_connect(address, connected));
    struct sockaddr_in destination = {
        .sin_family = AF_INET, .sin_port = htons(CONFIG_VOICE_STREAM_PORT)
    };
    if (inet_pton(AF_INET, address, &destination.sin_addr) != 1) {
        ESP_LOGE(TAG, "Invalid saved PC address");
        vTaskDelete(NULL);
        return;
    }
    ESP_ERROR_CHECK(voice_playback_start(address, connected));
    ESP_LOGI(TAG, "UDP destination %s:%d; waiting for Wi-Fi", address, CONFIG_VOICE_STREAM_PORT);

    int32_t raw[256];
    uint8_t pcm[512];
    int sock = -1;
    while (true) {
        size_t count = 0;
        esp_err_t result = audio_input_read(raw, 256, &count);
        if (result != ESP_OK) {
            ESP_LOGW(TAG, "Capture: %s", esp_err_to_name(result));
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        /* Keep draining capture during Wi-Fi loss; never replay stale DMA. */
        if (!(xEventGroupGetBits(connected) & BIT0) || count == 0) continue;
        if (sock < 0) sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (sock < 0) { vTaskDelay(pdMS_TO_TICKS(100)); continue; }
        struct timeval timeout = {.tv_sec = 0, .tv_usec = 100000};
        setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
        /* Keep cadence/silence endpointing without transcribing our own speaker. */
        if (audio_output_active()) memset(pcm, 0, count * 2);
        else voice_pcm_encode(raw, pcm, count);
        if (sendto(sock, pcm, count * 2, 0, (struct sockaddr *)&destination,
                   sizeof(destination)) != (int)(count * 2)) {
            ESP_LOGW(TAG, "UDP send failed (%d)", errno);
            close(sock);
            sock = -1;
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
}

esp_err_t voice_stream_start(void)
{
    return xTaskCreate(stream_task, "voice_stream", 6144, NULL, 5, NULL) == pdPASS
        ? ESP_OK : ESP_ERR_NO_MEM;
}
