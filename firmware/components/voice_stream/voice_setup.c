#include "voice_setup.h"
#include "setup_config.h"
#include "captive_portal.h"
#include "portal_address.h"
#include "setup_scan.h"
#include "display.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "nvs.h"
#include <stdio.h>
#include <stdatomic.h>
#include <string.h>

#define SAVED_BIT BIT1
static EventGroupHandle_t events;
static esp_netif_t *station;
static char pc_address[16];
static char portal_name[33];
static atomic_bool portal_active;
extern const char setup_html_start[] asm("_binary_setup_html_start");

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        if (!portal_active) esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(events, BIT0);
        if (!portal_active) display_status("WIFI RECONNECTING", "Waiting for network", pc_address);
        if (!portal_active) esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_LOST_IP) {
        xEventGroupClearBits(events, BIT0);
        if (!portal_active) display_status("WAITING FOR IP", "Waiting for network", pc_address);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ip = data;
        char address[32];
        snprintf(address, sizeof(address), "IP " IPSTR, IP2STR(&ip->ip_info.ip));
        if (!portal_active) display_status("WIFI CONNECTED", address, pc_address);
        xEventGroupSetBits(events, BIT0);
    }
}

/* Probe GETs may use arbitrary Hosts; writes require the canonical portal origin. */
static bool ap_request(httpd_req_t *request)
{
    struct sockaddr_storage local = {0};
    socklen_t size = sizeof(local);
    if (getsockname(httpd_req_to_sockfd(request), (struct sockaddr *)&local, &size) ||
        !portal_address_is_ap(&local, size)) return false;
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    return true;
}

static bool portal_request(httpd_req_t *request)
{
    if (!ap_request(request)) return false;
    char header[80];
    if (httpd_req_get_hdr_value_str(request, "Host", header, sizeof(header)) != ESP_OK ||
        (strcmp(header, "192.168.4.1") && strcmp(header, "192.168.4.1:80"))) return false;
    if (httpd_req_get_hdr_value_len(request, "Origin")) {
        if (httpd_req_get_hdr_value_str(request, "Origin", header, sizeof(header)) != ESP_OK ||
            (strcmp(header, "http://192.168.4.1") && strcmp(header, "http://192.168.4.1:80"))) return false;
    }
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    httpd_resp_set_hdr(request, "X-Content-Type-Options", "nosniff");
    httpd_resp_set_hdr(request, "Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'");
    return true;
}

static esp_err_t redirect_to_setup(httpd_req_t *request)
{
    if (!ap_request(request) || request->method != HTTP_GET)
        return httpd_resp_send_err(request, HTTPD_403_FORBIDDEN, "Use the device setup network.");
    httpd_resp_set_status(request, "302 Found");
    httpd_resp_set_hdr(request, "Location", "http://192.168.4.1/");
    httpd_resp_set_type(request, "text/html; charset=utf-8");
    /* A nonempty body is needed by some Apple captive-portal detectors. */
    return httpd_resp_sendstr(request, "<!doctype html><a href='http://192.168.4.1/'>Set up your voice device</a>");
}

static esp_err_t captive_api(httpd_req_t *request)
{
    if (!portal_request(request)) return redirect_to_setup(request);
    httpd_resp_set_type(request, "application/captive+json");
    return httpd_resp_sendstr(request, "{\"captive\":true,\"user-portal-url\":\"http://192.168.4.1/\"}");
}

static esp_err_t show_page(httpd_req_t *request)
{
    if (!portal_request(request)) return redirect_to_setup(request);
    httpd_resp_set_type(request, "text/html; charset=utf-8");
    return httpd_resp_send(request, setup_html_start, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t list_networks(httpd_req_t *request)
{
    if (!portal_request(request)) return httpd_resp_send_err(request, HTTPD_403_FORBIDDEN, "Use the device setup page.");
    return setup_scan_get(request);
}

static esp_err_t save_settings(httpd_req_t *request)
{
    if (!portal_request(request)) return httpd_resp_send_err(request, HTTPD_403_FORBIDDEN, "Use the device setup network.");
    if (xEventGroupGetBits(events) & SAVED_BIT) return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST, "Restart pending.");
    char type[64];
    if (httpd_req_get_hdr_value_str(request, "Content-Type", type, sizeof(type)) != ESP_OK ||
        strcmp(type, "application/x-www-form-urlencoded")) {
        return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST, "Use the setup form.");
    }
    char body[512] = {0};
    if (!request->content_len || request->content_len >= sizeof(body)) {
        return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST, "Settings too long.");
    }
    size_t received = 0;
    while (received < request->content_len) {
        int count = httpd_req_recv(request, body + received, request->content_len - received);
        if (count <= 0) return ESP_FAIL;
        received += count;
    }
    setup_config_t config = {0};
    bool valid = setup_config_parse(body, received, &config);
    memset(body, 0, sizeof(body));
    if (!valid) return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST,
        "Invalid settings. Use an SSID of 1-32 bytes, WPA password of 8-63 printable characters (or 64 hex digits), and a unicast PC IPv4 address.");
    nvs_handle_t storage;
    esp_err_t result = nvs_open("voice_setup", NVS_READWRITE, &storage);
    if (result == ESP_OK) {
        result = nvs_set_blob(storage, "config_v1", &config, sizeof(config));
        if (result == ESP_OK) result = nvs_commit(storage);
        nvs_close(storage);
    }
    memset(&config, 0, sizeof(config));
    if (result != ESP_OK) return httpd_resp_send_err(request, HTTPD_500_INTERNAL_SERVER_ERROR, "Could not save. Please retry.");
    httpd_resp_set_type(request, "text/html; charset=utf-8");
    result = httpd_resp_sendstr(request, "<!doctype html><meta name='viewport' content='width=device-width'><h1>Settings saved</h1><p>The device is restarting. Rejoin your normal Wi-Fi. If connection fails, use the setup network again. You can close this page.</p>");
    xEventGroupSetBits(events, SAVED_BIT);
    return result;
}

static esp_err_t start_portal(void)
{
    uint8_t mac[6];
    ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP));
    snprintf(portal_name, sizeof(portal_name), "VOICE-SETUP-%02X%02X", mac[4], mac[5]);
    portal_active = true;
    /* STA is needed for scanning, but must not connect to saved/legacy Wi-Fi. */
    esp_wifi_disconnect();
    wifi_config_t empty_station = {0};
    empty_station.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &empty_station));
    esp_netif_t *ap = esp_netif_create_default_wifi_ap();
    if (!ap) return ESP_ERR_NO_MEM;
    /* Set a documented URL explicitly instead of relying on SDK defaults. */
    esp_netif_ip_info_t ip = {0};
    ip.ip.addr = ip.gw.addr = inet_addr("192.168.4.1");
    ip.netmask.addr = inet_addr("255.255.255.0");
    ESP_ERROR_CHECK(esp_netif_dhcps_stop(ap));
    ESP_ERROR_CHECK(esp_netif_set_ip_info(ap, &ip));
    esp_netif_dns_info_t dns = {.ip = {.type = ESP_IPADDR_TYPE_V4}};
    dns.ip.u_addr.ip4.addr = ip.ip.addr;
    ESP_ERROR_CHECK(esp_netif_set_dns_info(ap, ESP_NETIF_DNS_MAIN, &dns));
    uint8_t offer_dns = 1;
    ESP_ERROR_CHECK(esp_netif_dhcps_option(ap, ESP_NETIF_OP_SET, ESP_NETIF_DOMAIN_NAME_SERVER,
                                         &offer_dns, sizeof(offer_dns)));
    static char captive_uri[] = "http://192.168.4.1/captive-portal";
    ESP_ERROR_CHECK(esp_netif_dhcps_option(ap, ESP_NETIF_OP_SET, ESP_NETIF_CAPTIVEPORTAL_URI,
                                         captive_uri, strlen(captive_uri)));
    ESP_ERROR_CHECK(esp_netif_dhcps_start(ap));
    wifi_config_t config = {0};
    memcpy(config.ap.ssid, portal_name, strlen(portal_name));
    config.ap.ssid_len = strlen(portal_name);
    config.ap.max_connection = 2;
    config.ap.authmode = WIFI_AUTH_OPEN;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &config));
    memset(&config, 0, sizeof(config));
    httpd_config_t server_config = HTTPD_DEFAULT_CONFIG();
    server_config.stack_size = 6144;
    server_config.max_open_sockets = 3;
    server_config.lru_purge_enable = true;
    server_config.recv_wait_timeout = 5;
    server_config.uri_match_fn = httpd_uri_match_wildcard;
    httpd_handle_t server;
    esp_err_t result = httpd_start(&server, &server_config);
    if (result != ESP_OK) return result;
    const httpd_uri_t page = {.uri = "/", .method = HTTP_GET, .handler = show_page};
    const httpd_uri_t save = {.uri = "/save", .method = HTTP_POST, .handler = save_settings};
    const httpd_uri_t api = {.uri = "/captive-portal", .method = HTTP_GET, .handler = captive_api};
    const httpd_uri_t probes = {.uri = "/*", .method = HTTP_GET, .handler = redirect_to_setup};
    const httpd_uri_t networks = {.uri = "/networks", .method = HTTP_GET, .handler = list_networks};
    ESP_ERROR_CHECK(setup_scan_start());
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &page));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &save));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &api));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &networks));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &probes));
    ESP_ERROR_CHECK(captive_portal_dns_start());
    printf("\nJoin open Wi-Fi: %s (no password)\nTap the Wi-Fi sign-in prompt. Fallback: http://192.168.4.1\n", portal_name);
    display_setup(portal_name);
    xEventGroupWaitBits(events, SAVED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);
    display_status("SETTINGS SAVED", "Restarting...", "");
    vTaskDelay(pdMS_TO_TICKS(1500));
    httpd_stop(server);
    esp_restart();
    return ESP_OK;
}

esp_err_t voice_setup_connect(char address[16], EventGroupHandle_t connected)
{
    events = connected;
    setup_config_t saved = {0};
    nvs_handle_t storage;
    bool configured = false;
    if (nvs_open("voice_setup", NVS_READONLY, &storage) == ESP_OK) {
        size_t size = sizeof(saved);
        configured = nvs_get_blob(storage, "config_v1", &saved, &size) == ESP_OK &&
                     size == sizeof(saved) && setup_config_valid(&saved);
        nvs_close(storage);
    }
    puts("Send s within 3 seconds to reopen web setup.");
    bool force_setup = false;
    for (int i = 0; i < 150; ++i) {
        int ch = getchar();
        if (ch == 's' || ch == 'S') { force_setup = true; break; }
        if (ch == EOF) clearerr(stdin);
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    station = esp_netif_create_default_wifi_sta();
    if (!station) return ESP_ERR_NO_MEM;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    wifi_config_t config = {0};
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    if (configured && !force_setup) {
        memcpy(config.sta.ssid, saved.ssid, strlen(saved.ssid));
        memcpy(config.sta.password, saved.password, strlen(saved.password));
        memcpy(pc_address, saved.address, sizeof(pc_address));
    }
    /* Replace any legacy SDK Wi-Fi config loaded before RAM storage selection. */
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    memset(&config, 0, sizeof(config));
    memset(&saved, 0, sizeof(saved));
    display_status("CONNECTING WIFI", "Please wait...", pc_address);
    ESP_ERROR_CHECK(esp_wifi_start());
    if (!configured || force_setup || !(xEventGroupWaitBits(events, BIT0, pdFALSE, pdTRUE,
                                                           pdMS_TO_TICKS(30000)) & BIT0)) {
        return start_portal();
    }
    memcpy(address, pc_address, sizeof(pc_address));
    return ESP_OK;
}
