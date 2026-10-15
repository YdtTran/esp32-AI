#include "portal_address.h"
#include "lwip/sockets.h"
#include <string.h>

bool portal_address_is_ap(const void *address, size_t size)
{
    if (size < sizeof(struct sockaddr)) return false;
    const struct sockaddr_storage *storage = address;
    const unsigned char ap[4] = {192,168,4,1};
    if (storage->ss_family == AF_INET && size >= sizeof(struct sockaddr_in)) {
        const struct sockaddr_in *ipv4 = address;
        return memcmp(&ipv4->sin_addr, ap, sizeof(ap)) == 0;
    }
#if LWIP_IPV6
    if (storage->ss_family == AF_INET6 && size >= sizeof(struct sockaddr_in6)) {
        const struct sockaddr_in6 *ipv6 = address;
        const unsigned char *bytes = (const unsigned char *)&ipv6->sin6_addr;
        const unsigned char mapped[12] = {0,0,0,0,0,0,0,0,0,0,255,255};
        return memcmp(bytes, mapped, sizeof(mapped)) == 0 && memcmp(bytes + 12, ap, sizeof(ap)) == 0;
    }
#endif
    return false;
}
