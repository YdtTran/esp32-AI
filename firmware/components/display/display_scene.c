#include "display_scene.h"
#include <stdbool.h>

static int triangle(unsigned value)
{
    int step = value % 24;
    return step < 12 ? step : 24 - step;
}

uint16_t display_scene_pixel(int x, int y, unsigned phase, display_scene_t scene)
{
    const uint16_t background = 0x10e4;
    bool ready = scene >= DISPLAY_SCENE_LISTENING;
    bool speaking = scene == DISPLAY_SCENE_SPEAKING;
    uint16_t accent = ready ? (speaking ? 0x5fff : 0x5fba) : 0xfdaa;
    int dx = x - 120, dy = y - 104;
    int distance = dx * dx + dy * dy;
    int radius = 43 + triangle(phase) / 3;
    if (distance >= (radius - 2) * (radius - 2) && distance <= radius * radius) {
        /* Traveling gap while waiting, breathing full ring when ready. */
        unsigned quadrant = (dx >= 0 ? 0 : 2) + (dy >= 0 ? 0 : 1);
        if (ready || quadrant != (phase / 3) % 4) return accent;
    }
    if (distance <= 34 * 34) {
        int eye_height = phase % 50 >= 47 ? 1 : 6;
        int look = ready ? 0 : triangle(phase) / 3 - 2;
        if (((x >= 101 + look && x <= 108 + look) ||
             (x >= 132 + look && x <= 139 + look)) &&
            y >= 94 && y < 94 + eye_height) return 0xffff;
        int mouth_height = speaking ? 4 + triangle(phase * 2) / 2 : 2;
        if (x >= 112 && x <= 128 && y >= 116 && y < 116 + mouth_height) return accent;
        return 0x1945;
    }
    for (unsigned bar = 0; bar < 5; ++bar) {
        int left = 85 + 16 * bar;
        int height = (speaking ? 7 : 3) + triangle(phase * (speaking ? 2 : 1) + bar * 4) * (speaking ? 2 : 1) / 2;
        if (x >= left && x < left + 6 && y >= 170 - height && y <= 170) return accent;
    }
    return background;
}
