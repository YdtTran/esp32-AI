#pragma once
#include "esp_err.h"
/* Call once after NVS, display and audio initialization. Starts saved/web setup and UDP. */
esp_err_t voice_stream_start(void);
