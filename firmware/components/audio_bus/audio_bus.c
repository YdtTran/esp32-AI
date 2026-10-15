#include "audio_bus.h"
#include <stdbool.h>
#include "board_pins.h"
#include "driver/i2s_std.h"
#include "sdkconfig.h"

_Static_assert(BOARD_MIC_BCLK_GPIO == BOARD_AMP_BCLK_GPIO,
               "Shared audio bus requires the same BCLK pin");
_Static_assert(BOARD_MIC_WS_GPIO == BOARD_AMP_LRC_GPIO,
               "Shared audio bus requires the same WS pin");

static i2s_chan_handle_t rx_handle;
static i2s_chan_handle_t tx_handle;
static bool initialized;

esp_err_t audio_bus_init(void)
{
    if (initialized) {
        return ESP_OK;
    }

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    chan_cfg.auto_clear_after_cb = true;

    esp_err_t err = i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle);
    if (err != ESP_OK) {
        return err;
    }

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(CONFIG_AUDIO_BUS_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
            I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = BOARD_MIC_BCLK_GPIO,
            .ws = BOARD_MIC_WS_GPIO,
            .dout = BOARD_AMP_DIN_GPIO,
            .din = BOARD_MIC_SD_GPIO,
        },
    };
    /* Preserve the existing INMP441 L/R-to-GND, left-slot configuration. */
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;

    bool tx_enabled = false;
    err = i2s_channel_init_std_mode(tx_handle, &std_cfg);
    if (err != ESP_OK) {
        goto fail;
    }
    err = i2s_channel_init_std_mode(rx_handle, &std_cfg);
    if (err != ESP_OK) {
        goto fail;
    }

    /* ESP-IDF v6.1 zero-initializes every DMA buffer. Auto-clear keeps TX
     * sending zeros indefinitely without a playback producer or extra task.
     * Initialize both channels before enabling the common clock source.
     */
    err = i2s_channel_enable(tx_handle);
    if (err != ESP_OK) {
        goto fail;
    }
    tx_enabled = true;
    err = i2s_channel_enable(rx_handle);
    if (err != ESP_OK) {
        goto fail;
    }

    initialized = true;
    return ESP_OK;

fail:
    if (tx_enabled) {
        i2s_channel_disable(tx_handle);
    }
    i2s_del_channel(rx_handle);
    i2s_del_channel(tx_handle);
    rx_handle = NULL;
    tx_handle = NULL;
    return err;
}

esp_err_t audio_bus_read(int32_t *buffer, size_t sample_count, size_t *samples_read)
{
    if (!buffer || !samples_read || sample_count == 0 ||
        sample_count > SIZE_MAX / sizeof(*buffer)) {
        return ESP_ERR_INVALID_ARG;
    }
    *samples_read = 0;
    if (!initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    size_t bytes_read = 0;
    /* i2s_channel_read uses milliseconds, not FreeRTOS ticks. */
    esp_err_t err = i2s_channel_read(rx_handle, buffer,
                                   sample_count * sizeof(*buffer), &bytes_read,
                                   UINT32_MAX);
    *samples_read = bytes_read / sizeof(*buffer);
    return err;
}

esp_err_t audio_bus_write(const int32_t *buffer, size_t sample_count)
{
    if (!buffer || sample_count == 0 || sample_count > SIZE_MAX / sizeof(*buffer)) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!initialized) return ESP_ERR_INVALID_STATE;
    size_t remaining = sample_count * sizeof(*buffer);
    const char *cursor = (const char *)buffer;
    while (remaining) {
        size_t written = 0;
        esp_err_t err = i2s_channel_write(tx_handle, cursor, remaining, &written, 1000);
        if (err != ESP_OK) return err;
        if (!written || written > remaining) return ESP_FAIL;
        cursor += written;
        remaining -= written;
    }
    return ESP_OK;
}
