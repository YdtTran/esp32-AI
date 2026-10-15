#pragma once
#include <stdbool.h>
#include <stddef.h>

typedef struct {
    char ssid[33];
    char password[65];
    char address[16];
} setup_config_t;

/* Strict application/x-www-form-urlencoded parser; no partial updates. */
bool setup_config_parse(const char *body, size_t length, setup_config_t *config);
bool setup_config_valid(const setup_config_t *config);
