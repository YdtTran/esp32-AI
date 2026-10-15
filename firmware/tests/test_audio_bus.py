"""Host regression checks for shared-bus ownership, startup and error cleanup.

Uses a fake I2S driver; electrical behavior and actual DMA output need hardware.
Run: python -m unittest discover -s firmware/tests -v
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


FIRMWARE = Path(__file__).resolve().parents[1]

HEADERS = {
    "freertos/FreeRTOS.h": "#define pdMS_TO_TICKS(ms) (ms)\n",
    "freertos/task.h": "static inline void vTaskDelay(int ticks) { (void)ticks; }\n",
    "esp_err.h": """
#pragma once
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
""",
    "sdkconfig.h": "#define CONFIG_AUDIO_BUS_SAMPLE_RATE 16000\n",
    "soc/gpio_num.h": "\n".join(
        f"#define GPIO_NUM_{pin} {pin}" for pin in range(4, 14)
    ),
    "driver/i2s_std.h": """
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
typedef void *i2s_chan_handle_t;
typedef struct { int id, role; bool auto_clear_after_cb; } i2s_chan_config_t;
typedef struct {
    struct { int sample_rate; } clk_cfg;
    struct { int width, mode, slot_mask; } slot_cfg;
    struct { int mclk, bclk, ws, dout, din; } gpio_cfg;
} i2s_std_config_t;
#define I2S_NUM_AUTO -1
#define I2S_ROLE_MASTER 1
#define I2S_GPIO_UNUSED -1
#define I2S_DATA_BIT_WIDTH_32BIT 32
#define I2S_SLOT_MODE_MONO 1
#define I2S_STD_SLOT_LEFT 1
#define I2S_CHANNEL_DEFAULT_CONFIG(n,r) { .id=(n), .role=(r) }
#define I2S_STD_CLK_DEFAULT_CONFIG(rate) { .sample_rate=(rate) }
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(w,m) { .width=(w), .mode=(m) }
esp_err_t i2s_new_channel(const i2s_chan_config_t *, i2s_chan_handle_t *, i2s_chan_handle_t *);
esp_err_t i2s_channel_init_std_mode(i2s_chan_handle_t, const i2s_std_config_t *);
esp_err_t i2s_channel_enable(i2s_chan_handle_t);
esp_err_t i2s_channel_disable(i2s_chan_handle_t);
esp_err_t i2s_del_channel(i2s_chan_handle_t);
esp_err_t i2s_channel_read(i2s_chan_handle_t, void *, size_t, size_t *, uint32_t);
esp_err_t i2s_channel_write(i2s_chan_handle_t, const void *, size_t, size_t *, uint32_t);
""",
}

HARNESS = r"""
#include <assert.h>
#include <stdlib.h>
#include "driver/i2s_std.h"
#include "audio_bus.h"
#include "audio_input.h"
#include "audio_output.h"
static int step, fail_step, deleted, disabled;
static bool tx_running;
#define TX ((void *)1)
#define RX ((void *)2)
static esp_err_t next(void) { return ++step == fail_step ? ESP_FAIL : ESP_OK; }
esp_err_t i2s_new_channel(const i2s_chan_config_t *c, void **tx, void **rx) {
    assert(tx && rx && c->auto_clear_after_cb);
    esp_err_t err = next();
    if (err == ESP_OK) { *tx = TX; *rx = RX; }
    return err;
}
esp_err_t i2s_channel_init_std_mode(void *h, const i2s_std_config_t *c) {
    assert(!tx_running);
    assert(h == (step == 1 ? TX : RX));
    assert(c->clk_cfg.sample_rate == 16000);
    assert(c->slot_cfg.width == 32 && c->slot_cfg.mode == I2S_SLOT_MODE_MONO);
    assert(c->slot_cfg.slot_mask == I2S_STD_SLOT_LEFT);
    assert(c->gpio_cfg.bclk == 4 && c->gpio_cfg.ws == 5);
    assert(c->gpio_cfg.din == 6 && c->gpio_cfg.dout == 7);
    return next();
}
esp_err_t i2s_channel_enable(void *h) {
    assert(h == (step == 3 ? TX : RX));
    if (h == RX) { assert(tx_running); }
    esp_err_t err = next();
    if (h == TX && err == ESP_OK) { tx_running = true; }
    return err;
}
esp_err_t i2s_channel_disable(void *h) {
    assert(h == TX && tx_running);
    tx_running = false; ++disabled; return ESP_OK;
}
esp_err_t i2s_del_channel(void *h) {
    assert(!tx_running && (h == TX || h == RX));
    ++deleted; return ESP_OK;
}
esp_err_t i2s_channel_read(void *h, void *buf, size_t size, size_t *read, uint32_t ms) {
    assert(h == RX && tx_running && size == 4 * sizeof(int32_t));
    assert(ms == UINT32_MAX);
    ((int32_t *)buf)[0] = 0x12340000;
    *read = 2 * sizeof(int32_t); return ESP_OK;
}
static int writes;
esp_err_t i2s_channel_write(void *h, const void *buf, size_t size, size_t *written, uint32_t ms) {
    assert(h == TX && tx_running && ms == 1000);
    assert(((const int32_t *)buf)[0] == (writes == 0 ? 0x12340000 : 0));
    assert(size == (writes == 0 ? 16 : 8));
    *written = 8; ++writes; return ESP_OK;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    int32_t data[4]; size_t count = 99;
    assert(audio_input_read(data, 4, &count) == ESP_ERR_INVALID_STATE && count == 0);
    assert(audio_input_read(NULL, 4, &count) == ESP_ERR_INVALID_ARG);
    assert(audio_input_read(data, 0, &count) == ESP_ERR_INVALID_ARG);
    assert(audio_input_read(data, SIZE_MAX, &count) == ESP_ERR_INVALID_ARG);
    assert(audio_input_read(data, 4, NULL) == ESP_ERR_INVALID_ARG);
    fail_step = atoi(argv[1]);
    if (fail_step) {
        assert(audio_output_init() == ESP_FAIL);
        assert(deleted == (fail_step == 1 ? 0 : 2));
        assert(disabled == (fail_step == 5 ? 1 : 0));
        assert(audio_input_read(data, 4, &count) == ESP_ERR_INVALID_STATE);
        step = 0; fail_step = 0;
    }
    assert(audio_output_init() == ESP_OK);
    assert(step == 5);
    assert(audio_input_init() == ESP_OK && step == 5);
    assert(audio_output_init() == ESP_OK && step == 5);
    assert(audio_input_read(data, 4, &count) == ESP_OK);
    assert(count == 2 && data[0] == 0x12340000);
    data[1] = data[2] = data[3] = 0;
    assert(!audio_output_active());
    audio_output_begin();
    assert(audio_output_active());
    assert(audio_output_write(data, 4) == ESP_OK && writes == 2);
    audio_output_end();
    assert(!audio_output_active());
    assert(audio_output_write(NULL, 4) == ESP_ERR_INVALID_ARG);
    return 0;
}
"""


class AudioBusTests(unittest.TestCase):
    def test_shared_startup_and_failure_recovery(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is a separate check")
        with tempfile.TemporaryDirectory(prefix="audio-bus-test-") as directory:
            root = Path(directory)
            for name, contents in HEADERS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding="utf-8")
            harness = root / "harness.c"
            harness.write_text(HARNESS, encoding="utf-8")
            executable = root / "audio_bus_test.exe"
            components = FIRMWARE / "components"
            names = ("audio_bus", "audio_input", "audio_output", "board")
            includes = [f"-I{root}"] + [
                f"-I{components / name / 'include'}" for name in names
            ]
            sources = [str(components / name / f"{name}.c") for name in names[:3]]
            subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", *includes,
                 *sources, str(harness), "-o", str(executable)], check=True,
            )
            for failure in range(6):
                with self.subTest(failure_step=failure):
                    subprocess.run([str(executable), str(failure)], check=True)


if __name__ == "__main__":
    unittest.main()
