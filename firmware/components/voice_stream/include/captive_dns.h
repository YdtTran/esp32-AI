#pragma once
#include <stddef.h>
#include <stdint.h>

/* One-question DNS responder for setup: wildcard A -> 192.168.4.1;
 * other IN types return no answers. Malformed/compressed questions are dropped.
 * Buffers must not overlap. Returns response size, or zero for rejected input. */
size_t captive_dns_reply(const uint8_t *query, size_t size, uint8_t *reply, size_t capacity);
