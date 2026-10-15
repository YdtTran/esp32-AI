#include "setup_networks.h"
#include <stdio.h>
#include <string.h>

static bool append(char **cursor, size_t *remaining, const char *value)
{
    size_t length = strlen(value);
    if (length >= *remaining) return false;
    memcpy(*cursor, value, length + 1);
    *cursor += length;
    *remaining -= length;
    return true;
}

size_t setup_networks_json(const setup_network_t *networks, size_t count, char *output, size_t capacity)
{
    if (count > SETUP_NETWORK_LIMIT || !capacity) return 0;
    char *cursor = output;
    size_t remaining = capacity;
    if (!append(&cursor, &remaining, "[")) return 0;
    for (size_t i = 0; i < count; ++i) {
        size_t length = strnlen(networks[i].ssid, sizeof(networks[i].ssid));
        if (!length || length > 32) return 0;
        if (!append(&cursor, &remaining, i ? ",{\"ssid\":\"" : "{\"ssid\":\"")) return 0;
        for (size_t j = 0; j < length; ++j) {
            unsigned char value = networks[i].ssid[j];
            char escaped[7] = {value, 0};
            if (value == '"' || value == '\\') { escaped[0] = '\\'; escaped[1] = value; escaped[2] = 0; }
            else if (value < 32) snprintf(escaped, sizeof(escaped), "\\u%04x", value);
            if (!append(&cursor, &remaining, escaped)) return 0;
        }
        char tail[64];
        snprintf(tail, sizeof(tail), "\",\"rssi\":%d,\"supported\":%s}", networks[i].rssi,
                 networks[i].supported ? "true" : "false");
        if (!append(&cursor, &remaining, tail)) return 0;
    }
    if (!append(&cursor, &remaining, "]")) return 0;
    return cursor - output;
}
