#pragma once
#include <stdbool.h>
#include <stddef.h>

/* Accept the setup IPv4 destination in either AF_INET or IPv4-mapped AF_INET6
 * socket representation. The caller supplies the actual getsockname size. */
bool portal_address_is_ap(const void *address, size_t size);
