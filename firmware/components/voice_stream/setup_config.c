#include "setup_config.h"
#include <stdint.h>
#include <string.h>

static int hex(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static bool decode(const char *source, size_t n, char *out, size_t capacity)
{
    size_t used = 0;
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = source[i];
        if (c == '%') {
            if (i + 2 >= n || hex(source[i + 1]) < 0 || hex(source[i + 2]) < 0) return false;
            c = (hex(source[i + 1]) << 4) | hex(source[i + 2]);
            i += 2;
        } else if (c == '+') c = ' ';
        if (c < 32 || c == 127 || used + 1 >= capacity) return false;
        out[used++] = c;
    }
    out[used] = 0;
    return true;
}

bool setup_config_valid(const setup_config_t *config)
{
    size_t ssid = strnlen(config->ssid, sizeof(config->ssid));
    size_t password = strnlen(config->password, sizeof(config->password));
    if (!ssid || ssid > 32 || password < 8 || password > 64) return false;
    for (size_t i = 0; i < password; ++i) {
        unsigned char c = config->password[i];
        if (c < 32 || c > 126 || (password == 64 && hex(c) < 0)) return false;
    }
    /* Require a canonical unicast IPv4 literal, never a URL/hostname. */
    size_t length = strnlen(config->address, sizeof(config->address));
    if (!length || length >= sizeof(config->address)) return false;
    const char *p = config->address;
    unsigned first = 0;
    uint32_t ip = 0;
    for (int part = 0; part < 4; ++part) {
        unsigned value = 0, digits = 0;
        const char *start = p;
        while (*p >= '0' && *p <= '9') {
            value = value * 10 + (*p++ - '0');
            if (++digits > 3 || value > 255) return false;
        }
        if (!digits || (digits > 1 && *start == '0')) return false;
        if (part == 0) first = value;
        ip = (ip << 8) | value;
        if (part < 3) { if (*p++ != '.') return false; }
        else if (*p) return false;
    }
    return first > 0 && first < 224 && first != 127 && ip != UINT32_MAX;
}

bool setup_config_parse(const char *body, size_t length, setup_config_t *config)
{
    setup_config_t parsed = {0};
    unsigned seen = 0;
    size_t offset = 0;
    while (offset < length) {
        size_t end = offset;
        while (end < length && body[end] != '&') ++end;
        size_t equal = offset;
        while (equal < end && body[equal] != '=') ++equal;
        if (equal == end) return false;
        char key[16];
        if (!decode(body + offset, equal - offset, key, sizeof(key))) return false;
        char *out;
        size_t capacity;
        unsigned bit;
        if (!strcmp(key, "ssid")) { out = parsed.ssid; capacity = sizeof(parsed.ssid); bit = 1; }
        else if (!strcmp(key, "password")) { out = parsed.password; capacity = sizeof(parsed.password); bit = 2; }
        else if (!strcmp(key, "pc")) { out = parsed.address; capacity = sizeof(parsed.address); bit = 4; }
        else return false;
        if ((seen & bit) || !decode(body + equal + 1, end - equal - 1, out, capacity)) return false;
        seen |= bit;
        offset = end + 1;
        if (offset == length) return false;
    }
    if (seen != 7 || !setup_config_valid(&parsed)) return false;
    *config = parsed;
    return true;
}
