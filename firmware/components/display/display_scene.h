#pragma once
#include <stdint.h>

typedef enum {
    DISPLAY_SCENE_WIFI,
    DISPLAY_SCENE_SERVER,
    DISPLAY_SCENE_LISTENING,
    DISPLAY_SCENE_SPEAKING
} display_scene_t;

/* RGB565 vector animation; deterministic, no frame buffer or graphics library. */
uint16_t display_scene_pixel(int x, int y, unsigned phase, display_scene_t scene);
