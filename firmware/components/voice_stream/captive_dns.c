/* Bounded single-question adaptation of ESP-IDF's captive_portal DNS example.
 * No dynamic allocation, packed structs, name decompression or upstream DNS. */
#include "captive_dns.h"
#include <string.h>

size_t captive_dns_reply(const uint8_t *query, size_t size, uint8_t *reply, size_t capacity)
{
    if (size < 17 || size > 512 || (query[2] & 0xfe) || (query[3] & 0xcf) ||
        query[4] || query[5] != 1 || query[6] || query[7] || query[8] || query[9]) return 0;
    size_t end = 12;
    while (end < size && query[end]) {
        unsigned length = query[end++];
        if (length > 63 || length > size - end) return 0;
        end += length;
        if (end - 12 > 254) return 0;
    }
    if (end >= size || size - end < 5) return 0;
    ++end;
    unsigned type = (query[end] << 8) | query[end + 1];
    if (query[end + 2] != 0 || query[end + 3] != 1) return 0;
    end += 4;
    size_t length = end + (type == 1 ? 16 : 0);
    if (length > capacity) return 0;
    memcpy(reply, query, end);
    reply[2] = 0x84 | (query[2] & 1); /* QR, authoritative, echo RD; no recursion. */
    reply[3] = 0;
    reply[6] = 0;
    reply[7] = type == 1;
    memset(reply + 8, 0, 4); /* Strip optional additional records, including EDNS. */
    if (type == 1) {
        /* QNAME pointer, A/IN, TTL zero, RDLENGTH four, setup IPv4. */
        const uint8_t answer[16] = {0xc0,12, 0,1, 0,1, 0,0,0,0, 0,4, 192,168,4,1};
        memcpy(reply + end, answer, sizeof(answer));
    }
    return length;
}
