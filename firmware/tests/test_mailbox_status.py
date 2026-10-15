"""Actual mailbox polling must not label errors or invalid audio as PC ready."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "components" / "voice_stream"
HEADERS = {
    "esp_err.h": "#pragma once\ntypedef int esp_err_t;\n#define ESP_OK 0\n#define ESP_FAIL -1\n#define ESP_ERR_NO_MEM 1\n",
    "sdkconfig.h": "#define CONFIG_VOICE_SPEAKER_PORT 5006\n",
    "freertos/FreeRTOS.h": "#pragma once\n#define BIT0 1\n#define pdFALSE 0\n#define pdTRUE 1\n#define pdPASS 1\n#define portMAX_DELAY 0\n#define pdMS_TO_TICKS(x) (x)\n",
    "freertos/event_groups.h": "#pragma once\ntypedef void *EventGroupHandle_t;\nstatic inline int xEventGroupWaitBits(void *a,int b,int c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;return 1;}\n",
    "freertos/task.h": "#pragma once\n#include <stddef.h>\nstatic inline void vTaskDelay(int t) {(void)t;}\nstatic inline int xTaskCreate(void (*f)(void *),const char *n,int s,void *a,int p,void *h) {(void)f;(void)n;(void)s;(void)a;(void)p;(void)h;return 1;}\n",
    "esp_log.h": "#pragma once\n#define ESP_LOGW(tag, ...) ((void)(tag))\n#define ESP_LOGI(tag, ...) ((void)(tag))\n",
    "audio_output.h": "#pragma once\n#include <stdint.h>\n#include <stddef.h>\nvoid audio_output_begin(void);\nvoid audio_output_end(void);\nint audio_output_write(const int32_t *, size_t);\n",
    "display.h": "#pragma once\n#include <stdbool.h>\nvoid display_server_update(bool reachable);\n",
    "esp_http_client.h": r'''
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
typedef void *esp_http_client_handle_t;
typedef struct {int event_id; void *user_data; const char *header_key, *header_value;} esp_http_client_event_t;
typedef struct {const char *url; int timeout_ms; bool disable_auto_redirect; int (*event_handler)(esp_http_client_event_t *); void *user_data;} esp_http_client_config_t;
#define HTTP_EVENT_ON_HEADER 1
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t *);
int esp_http_client_open(void *, int);
int64_t esp_http_client_fetch_headers(void *);
int esp_http_client_get_status_code(void *);
bool esp_http_client_is_chunked_response(void *);
int esp_http_client_read(void *, char *, int);
int esp_http_client_close(void *);
int esp_http_client_cleanup(void *);
''',
}
HARNESS = r'''
#include <assert.h>
#include "voice_playback.c"
static int scenario, updates, begun, ended;
static bool last;
static esp_http_client_config_t saved;
void display_server_update(bool reachable) {last = reachable; ++updates;}
void audio_output_begin(void) {++begun;}
void audio_output_end(void) {++ended;}
int audio_output_write(const int32_t *p, size_t n) {assert(p && n);return scenario == 8 ? ESP_FAIL : ESP_OK;}
void *esp_http_client_init(const esp_http_client_config_t *c) {saved = *c;return scenario == 1 ? NULL : &saved;}
int esp_http_client_open(void *c, int n) {(void)c;(void)n;return scenario == 2 ? ESP_FAIL : ESP_OK;}
static void header(const char *key, const char *value) {
    esp_http_client_event_t e = {HTTP_EVENT_ON_HEADER, saved.user_data, key, value};
    saved.event_handler(&e);
}
int64_t esp_http_client_fetch_headers(void *c) {
    (void)c;
    if (scenario != 5) header("X-Audio-Format", SPEAKER_PCM_FORMAT);
    header("Content-Type", "application/octet-stream");
    if (scenario == 10) header("Content-Encoding", "gzip");
    return scenario == 0 || scenario == 3 ? 0 : scenario == 11 ? -1 : scenario == 12 ? 3 : 2;
}
int esp_http_client_get_status_code(void *c) {(void)c;return scenario == 0 || scenario == 11 ? 204 : scenario == 3 ? 500 : 200;}
bool esp_http_client_is_chunked_response(void *c) {(void)c;return scenario == 9;}
int esp_http_client_read(void *c, char *out, int n) {(void)c;assert(n == 2);out[0] = out[1] = 0;return scenario == 7 ? 0 : 2;}
int esp_http_client_close(void *c) {(void)c;return 0;}
int esp_http_client_cleanup(void *c) {(void)c;return 0;}
int main(void) {
    for (scenario = 0; scenario <= 12; ++scenario) {
        updates = begun = ended = 0; last = true;
        collect_audio();
        bool valid_audio = scenario == 4 || scenario == 6;
        assert(last == (scenario == 0 || valid_audio));
        assert(updates >= 1);
        assert(begun == ended);
        assert(begun == (valid_audio || scenario == 7 || scenario == 8));
    }
    return 0;
}
'''


class MailboxStatusTests(unittest.TestCase):
    def test_only_valid_mailbox_responses_mark_ready(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is separate")
        with tempfile.TemporaryDirectory(prefix="mailbox-status-") as directory:
            root = Path(directory)
            for name, value in HEADERS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            harness = root / "test.c"
            harness.write_text(HARNESS, encoding="utf-8")
            executable = root / "test.exe"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            f"-I{root}", f"-I{COMPONENT}", f"-I{COMPONENT / 'include'}",
                            str(harness), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
