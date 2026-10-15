#include "voice_playback.h"
#include "speaker_pcm.h"
#include "audio_output.h"
#include "display.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "sdkconfig.h"
#include "freertos/task.h"
#include <stdio.h>
#include <string.h>
#include <strings.h>

static char audio_url[64];
static EventGroupHandle_t wifi_connected;
static const char *TAG = "voice_playback";

typedef struct {
    bool format;
    bool content_type;
    bool encoded;
} audio_headers_t;

static esp_err_t on_http_event(esp_http_client_event_t *event)
{
    if (event->event_id == HTTP_EVENT_ON_HEADER) {
        audio_headers_t *headers = event->user_data;
        if (!strcasecmp(event->header_key, "X-Audio-Format"))
            headers->format = !strcmp(event->header_value, SPEAKER_PCM_FORMAT);
        if (!strcasecmp(event->header_key, "Content-Type"))
            headers->content_type = !strcasecmp(event->header_value, "application/octet-stream");
        if (!strcasecmp(event->header_key, "Content-Encoding"))
            headers->encoded = true;
    }
    return ESP_OK;
}

static void collect_audio(void)
{
    audio_headers_t headers = {0};
    esp_http_client_config_t config = {
        .url = audio_url, .timeout_ms = 2000, .disable_auto_redirect = true,
        .event_handler = on_http_event, .user_data = &headers,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) { display_server_update(false); return; }
    bool playing = false;
    bool reachable = false;
    if (esp_http_client_open(client, 0) != ESP_OK) goto done;
    int64_t length = esp_http_client_fetch_headers(client);
    int status = esp_http_client_get_status_code(client);
    if (status == 204 && length >= 0) { reachable = true; goto done; }
    if (status != 200 || !speaker_pcm_length_valid(length) || !headers.format ||
        !headers.content_type || headers.encoded || esp_http_client_is_chunked_response(client)) {
        ESP_LOGW(TAG, "Rejected speaker response: status %d, length %lld", status, (long long)length);
        goto done;
    }
    audio_output_begin();
    display_server_update(true);
    playing = true;
    uint8_t pcm[1024];
    int32_t samples[512];
    size_t carry = 0;
    int64_t remaining = length;
    while (remaining > 0) {
        int requested = (int)(sizeof(pcm) - carry);
        if (remaining < requested) requested = (int)remaining;
        int received = esp_http_client_read(client, (char *)pcm + carry, requested);
        if (received <= 0) {
            ESP_LOGW(TAG, "Speaker download interrupted; discarding remainder");
            goto done;
        }
        remaining -= received;
        size_t bytes = carry + received;
        size_t count = bytes / 2;
        for (size_t i = 0; i < count; ++i) samples[i] = speaker_pcm_word(pcm + 2 * i);
        if (count && audio_output_write(samples, count) != ESP_OK) {
            ESP_LOGW(TAG, "Speaker I2S write failed; discarding remainder");
            goto done;
        }
        carry = bytes % 2;
        if (carry) pcm[0] = pcm[bytes - 1];
    }
    ESP_LOGI(TAG, "Speaker PCM streamed to I2S: %lld bytes", (long long)length);
    reachable = true;
done:
    display_server_update(reachable);
    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    if (playing) audio_output_end();
}

static void playback_task(void *arg)
{
    (void)arg;
    while (true) {
        xEventGroupWaitBits(wifi_connected, BIT0, pdFALSE, pdTRUE, portMAX_DELAY);
        collect_audio();
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

esp_err_t voice_playback_start(const char *pc_ipv4, EventGroupHandle_t connected)
{
    snprintf(audio_url, sizeof(audio_url), "http://%s:%d/audio", pc_ipv4,
             CONFIG_VOICE_SPEAKER_PORT);
    wifi_connected = connected;
    return xTaskCreate(playback_task, "voice_playback", 8192, NULL, 5, NULL) == pdPASS
        ? ESP_OK : ESP_ERR_NO_MEM;
}
