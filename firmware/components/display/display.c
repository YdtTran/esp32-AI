#include "display.h"
#include "display_scene.h"
#include "board_pins.h"
#include "audio_output.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <ctype.h>
#include <stdio.h>
#include <string.h>

static SemaphoreHandle_t lock, transfer_done;
static esp_lcd_panel_handle_t panel;
static uint16_t *pixels;
static char lines[9][33];
static bool setup_mode;
static bool server_reachable;
static int64_t last_server_response;

/* Compact 5x7 column font: digits, uppercase letters and punctuation. */
static const uint8_t digits[10][5] = {
    {62,81,73,69,62},{0,66,127,64,0},{98,81,73,73,70},{34,65,73,73,54},
    {24,20,18,127,16},{39,69,69,69,57},{62,73,73,73,50},{1,113,9,5,3},
    {54,73,73,73,54},{38,73,73,73,62}
};
static const uint8_t letters[26][5] = {
    {126,9,9,9,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,65,62},
    {127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},
    {0,65,127,65,0},{32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},
    {127,2,12,2,127},{127,4,8,16,127},{62,65,65,65,62},{127,9,9,9,6},
    {62,65,81,33,94},{127,9,25,41,70},{38,73,73,73,50},{1,1,127,1,1},
    {63,64,64,64,63},{31,32,64,32,31},{63,64,56,64,63},{99,20,8,20,99},
    {7,8,112,8,7},{97,81,73,69,67}
};

static uint8_t glyph(char value, int column)
{
    unsigned char c = toupper((unsigned char)value);
    if (c >= '0' && c <= '9') return digits[c - '0'][column];
    if (c >= 'A' && c <= 'Z') return letters[c - 'A'][column];
    if (c == '.') return column == 2 ? 64 : 0;
    if (c == ':') return column == 2 ? 36 : 0;
    if (c == '-') return 8;
    if (c == '/') return (uint8_t)(64 >> column);
    if (c == '_') return 64;
    return c == ' ' ? 0 : (column == 2 ? 95 : 0);
}

static bool color_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *event, void *context)
{
    BaseType_t wake = pdFALSE;
    xSemaphoreGiveFromISR(transfer_done, &wake);
    return wake == pdTRUE;
}

void display_status(const char *state, const char *detail, const char *pc)
{
    if (!lock) return;
    xSemaphoreTake(lock, portMAX_DELAY);
    memset(lines, 0, sizeof(lines));
    snprintf(lines[0], sizeof(lines[0]), "VOICE DEVICE");
    snprintf(lines[1], sizeof(lines[1]), "%s", state);
    snprintf(lines[2], sizeof(lines[2]), "%s", detail);
    snprintf(lines[3], sizeof(lines[3]), "PC ADDRESS");
    snprintf(lines[4], sizeof(lines[4]), "%s", pc);
    setup_mode = false;
    server_reachable = false;
    xSemaphoreGive(lock);
}

void display_setup(const char *ssid)
{
    if (!lock) return;
    xSemaphoreTake(lock, portMAX_DELAY);
    memset(lines, 0, sizeof(lines));
    snprintf(lines[0], sizeof(lines[0]), "FIRST-TIME SETUP");
    snprintf(lines[1], sizeof(lines[1]), "JOIN WIFI:");
    snprintf(lines[2], sizeof(lines[2]), "%s", ssid);
    snprintf(lines[3], sizeof(lines[3]), "NO PASSWORD");
    snprintf(lines[4], sizeof(lines[4]), "TAP WIFI SIGN-IN");
    snprintf(lines[5], sizeof(lines[5]), "OR OPEN HTTP://");
    snprintf(lines[6], sizeof(lines[6]), "192.168.4.1");
    snprintf(lines[8], sizeof(lines[8]), "SAVE TO RESTART");
    setup_mode = true;
    xSemaphoreGive(lock);
}

void display_server_update(bool reachable)
{
    if (!lock) return;
    xSemaphoreTake(lock, portMAX_DELAY);
    server_reachable = reachable;
    if (reachable) last_server_response = esp_timer_get_time();
    xSemaphoreGive(lock);
}

static void render_task(void *arg)
{
    char previous[9][33] = {0};
    bool previous_setup = true;
    unsigned phase = 0;
    for (;;) {
        char frame[9][33];
        xSemaphoreTake(lock, portMAX_DELAY);
        memcpy(frame, lines, sizeof(frame));
        bool setup = setup_mode;
        bool server = server_reachable;
        int64_t last_response = last_server_response;
        xSemaphoreGive(lock);
        display_scene_t scene = DISPLAY_SCENE_WIFI;
        if (!setup) {
            wifi_ap_record_t ap;
            bool online = esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
            esp_netif_t *netif = online ? esp_netif_get_handle_from_ifkey("WIFI_STA_DEF") : NULL;
            esp_netif_ip_info_t network;
            online = online && netif && esp_netif_get_ip_info(netif, &network) == ESP_OK && network.ip.addr;
            bool speaking = audio_output_active();
            int64_t now = esp_timer_get_time();
            bool ready = online && server && (speaking || now - last_response < 5000000);
            char ip[33], pc[33];
            memcpy(ip, frame[2], sizeof(ip));
            memcpy(pc, frame[4], sizeof(pc));
            if (online) snprintf(frame[1], sizeof(frame[1]), "%s", ready ?
                                 (speaking ? "SPEAKING: MIC MUTED" : "LISTENING") : "WAITING FOR SERVER");
            for (int row = 2; row <= 6; ++row) frame[row][0] = 0;
            snprintf(frame[7], sizeof(frame[7]), "%s", ip);
            snprintf(frame[8], sizeof(frame[8]), "PC %.15s", pc);
            if (online && (now / 6000000) % 2) {
                snprintf(frame[7], sizeof(frame[7]), "WIFI %d DBM", ap.rssi);
                snprintf(frame[8], sizeof(frame[8]), "UP %llu S", (unsigned long long)(now / 1000000));
            }
            scene = !online ? DISPLAY_SCENE_WIFI : !ready ? DISPLAY_SCENE_SERVER :
                    speaking ? DISPLAY_SCENE_SPEAKING : DISPLAY_SCENE_LISTENING;
        }
        bool full = setup || setup != previous_setup || memcmp(frame, previous, sizeof(frame));
        memcpy(previous, frame, sizeof(frame));
        previous_setup = setup;
        for (int y = full ? 0 : 48; y < (full ? 240 : 176); y += 16) {
            for (int dy = 0; dy < 16; ++dy) for (int x = 0; x < 240; ++x) {
                int row = (y + dy - 8) / 24;
                int gy = (y + dy - 8) % 24;
                int col = (x - 6) / 12, gx = (x - 6) % 12;
                bool ink = y + dy >= 8 && x >= 6 && row < 9 && col < 19 &&
                           gy >= 0 && gy < 14 && gx < 10 &&
                           (size_t)col < strlen(frame[row]) &&
                           (glyph(frame[row][col], gx / 2) & (1 << (gy / 2)));
                uint16_t rgb = ink ? (row == 0 ? 0x5fba : 0xffff) : 0x10e4;
                if (!setup && y + dy >= 48 && y + dy < 176)
                    rgb = display_scene_pixel(x, y + dy, phase, scene);
                pixels[dy * 240 + x] = (rgb << 8) | (rgb >> 8);
            }
            esp_err_t result = esp_lcd_panel_draw_bitmap(panel, 0, y, 240, y + 16, pixels);
            if (result != ESP_OK) {
                ESP_LOGE("display", "Drawing failed: %s", esp_err_to_name(result));
                vTaskDelete(NULL);
            }
            /* DMA must finish before its source buffer is reused. */
            xSemaphoreTake(transfer_done, portMAX_DELAY);
        }
        ++phase;
        vTaskDelay(pdMS_TO_TICKS(setup ? 1000 : 100));
    }
}

esp_err_t display_init(void)
{
    lock = xSemaphoreCreateMutex();
    transfer_done = xSemaphoreCreateBinary();
    pixels = heap_caps_malloc(240 * 16 * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!lock || !transfer_done || !pixels) return ESP_ERR_NO_MEM;
    gpio_config_t backlight = {.pin_bit_mask = 1ULL << BOARD_LCD_BLK_GPIO, .mode = GPIO_MODE_OUTPUT};
    ESP_ERROR_CHECK(gpio_config(&backlight));
    ESP_ERROR_CHECK(gpio_set_level(BOARD_LCD_BLK_GPIO, 0));
    spi_bus_config_t bus = {
        .sclk_io_num = BOARD_LCD_SCLK_GPIO, .mosi_io_num = BOARD_LCD_MOSI_GPIO,
        .miso_io_num = -1, .quadwp_io_num = -1, .quadhd_io_num = -1,
        .max_transfer_sz = 240 * 16 * sizeof(uint16_t)
    };
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO));
    esp_lcd_panel_io_spi_config_t io_config = {
        .dc_gpio_num = BOARD_LCD_DC_GPIO, .cs_gpio_num = BOARD_LCD_CS_GPIO,
        .pclk_hz = 10000000, .lcd_cmd_bits = 8, .lcd_param_bits = 8,
        .spi_mode = 0, .trans_queue_depth = 1, .on_color_trans_done = color_done
    };
    esp_lcd_panel_io_handle_t io;
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI2_HOST, &io_config, &io));
    esp_lcd_panel_dev_config_t device = {
        .reset_gpio_num = BOARD_LCD_RST_GPIO,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB, .bits_per_pixel = 16
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io, &device, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_set_gap(panel, CONFIG_DISPLAY_X_OFFSET, CONFIG_DISPLAY_Y_OFFSET));
#ifdef CONFIG_DISPLAY_INVERT_COLORS
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, true));
#else
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, false));
#endif
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));
    display_status("BOOTING", "Starting audio...", "");
    if (xTaskCreate(render_task, "display", 4096, NULL, 2, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    return gpio_set_level(BOARD_LCD_BLK_GPIO, 1);
}
