#pragma once
#include "esp_http_server.h"

/* Owns the setup-only scan worker/cache. Caller must validate AP Host/Origin
 * before calling the GET handler. Scanning never blocks HTTP/DNS handling. */
esp_err_t setup_scan_start(void);
esp_err_t setup_scan_get(httpd_req_t *request);
