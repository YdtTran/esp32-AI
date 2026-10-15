#pragma once
#include "esp_err.h"
/* Call once after AP IPv4 is configured. DNS socket lives until setup reboot. */
esp_err_t captive_portal_dns_start(void);
