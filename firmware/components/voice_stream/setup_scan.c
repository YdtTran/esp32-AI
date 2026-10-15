#include "setup_scan.h"
#include "setup_networks.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <string.h>

static SemaphoreHandle_t scan_lock;
static TaskHandle_t scanner;
static bool scanning, scanned, scan_error;
static char cached_json[4096] = "[]";

static bool supported(wifi_auth_mode_t mode)
{
    return mode == WIFI_AUTH_WPA2_PSK || mode == WIFI_AUTH_WPA_WPA2_PSK ||
           mode == WIFI_AUTH_WPA3_PSK || mode == WIFI_AUTH_WPA2_WPA3_PSK;
}

static void scan_task(void *argument)
{
    /* Static bounded storage keeps SDK records off the worker/HTTP stacks. */
    static wifi_ap_record_t records[SETUP_NETWORK_LIMIT];
    static setup_network_t networks[SETUP_NETWORK_LIMIT];
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        uint16_t count = SETUP_NETWORK_LIMIT;
        esp_err_t result = esp_wifi_scan_start(NULL, true);
        if (result == ESP_OK) result = esp_wifi_scan_get_ap_records(&count, records);
        if (result != ESP_OK) {
            esp_wifi_clear_ap_list();
            ESP_LOGW("setup_scan", "Scan failed: %s", esp_err_to_name(result));
            count = 0;
        }
        size_t used = 0;
        memset(networks, 0, sizeof(networks));
        for (unsigned i = 0; i < count; ++i) {
            if (!records[i].ssid[0]) continue;
            bool duplicate = false;
            for (size_t j = 0; j < used; ++j)
                if (!strncmp(networks[j].ssid, (const char *)records[i].ssid, 32)) duplicate = true;
            if (duplicate) continue;
            memcpy(networks[used].ssid, records[i].ssid, 32);
            networks[used].rssi = records[i].rssi;
            networks[used].supported = supported(records[i].authmode);
            ++used;
        }
        xSemaphoreTake(scan_lock, portMAX_DELAY);
        scan_error = result != ESP_OK || !setup_networks_json(networks, used, cached_json, sizeof(cached_json));
        if (scan_error) strcpy(cached_json, "[]");
        scanned = true;
        scanning = false;
        xSemaphoreGive(scan_lock);
    }
}

esp_err_t setup_scan_start(void)
{
    scan_lock = xSemaphoreCreateMutex();
    if (!scan_lock) return ESP_ERR_NO_MEM;
    if (xTaskCreate(scan_task, "setup_scan", 4096, NULL, 3, &scanner) != pdPASS) return ESP_ERR_NO_MEM;
    return ESP_OK;
}

esp_err_t setup_scan_get(httpd_req_t *request)
{
    char query[24] = {0};
    httpd_req_get_url_query_str(request, query, sizeof(query));
    bool refresh = !strcmp(query, "refresh=1");
    xSemaphoreTake(scan_lock, portMAX_DELAY);
    if (!scanning && (!scanned || refresh)) {
        scanning = true;
        xTaskNotifyGive(scanner);
    }
    httpd_resp_set_type(request, "application/json; charset=utf-8");
    const char *prefix = scanning ? "{\"scanning\":true,\"error\":false,\"networks\":" :
                         scan_error ? "{\"scanning\":false,\"error\":true,\"networks\":" :
                                      "{\"scanning\":false,\"error\":false,\"networks\":";
    esp_err_t result = httpd_resp_sendstr_chunk(request, prefix);
    if (result == ESP_OK) result = httpd_resp_sendstr_chunk(request, cached_json);
    if (result == ESP_OK) result = httpd_resp_sendstr_chunk(request, "}");
    if (result == ESP_OK) result = httpd_resp_send_chunk(request, NULL, 0);
    xSemaphoreGive(scan_lock);
    return result;
}
