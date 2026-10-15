#pragma once
#include <stdbool.h>
#include <stddef.h>

#define SETUP_NETWORK_LIMIT 16
typedef struct {
    char ssid[33];
    int rssi;
    bool supported;
} setup_network_t;

/* Serialize untrusted SSIDs as JSON strings, rejecting overflow. */
size_t setup_networks_json(const setup_network_t *networks, size_t count, char *output, size_t capacity);
