"""Exercise real captive DNS parsing, including truncated and hostile packets."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "components" / "voice_stream"
HARNESS = r'''
#include "captive_dns.h"
#include <assert.h>
#include <string.h>
int main(void) {
    const unsigned char query[] = {
        0x12,0x34,1,0,0,1,0,0,0,0,0,0,
        3,'w','w','w',7,'e','x','a','m','p','l','e',3,'c','o','m',0,0,1,0,1
    };
    unsigned char packet[513], reply[514];
    memset(reply, 0xa5, sizeof(reply));
    size_t n = captive_dns_reply(query, sizeof(query), reply + 1, 512);
    assert(n == sizeof(query) + 16);
    assert(reply[0] == 0xa5 && reply[513] == 0xa5);
    assert(reply[1] == 0x12 && reply[2] == 0x34);
    assert(reply[3] == 0x85 && reply[8] == 1);
    assert(!memcmp(reply + 1 + n - 4, "\xc0\xa8\x04\x01", 4));
    assert(!memcmp(reply + 1 + sizeof(query), "\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x00\x00\x04", 12));
    for (size_t size = 0; size < sizeof(query); ++size)
        assert(!captive_dns_reply(query, size, reply + 1, 512));
    assert(!captive_dns_reply(query, sizeof(query), reply, n - 1));
    const int offsets[] = {2, 3, 4, 5, 6, 8, 12, 32};
    const unsigned char values[] = {0x81, 1, 1, 2, 1, 1, 0xc0, 2};
    for (unsigned i = 0; i < sizeof(offsets)/sizeof(offsets[0]); ++i) {
        memcpy(packet, query, sizeof(query));
        packet[offsets[i]] = values[i];
        assert(!captive_dns_reply(packet, sizeof(query), reply, 512));
    }
    memcpy(packet, query, sizeof(query));
    packet[30] = 28; /* AAAA: successful empty answer, no invalid IPv6 payload. */
    assert(captive_dns_reply(packet, sizeof(query), reply, 512) == sizeof(query));
    assert(reply[7] == 0);
    memcpy(packet, query, sizeof(query));
    packet[3] = 0x20; /* DNSSEC AD bit and EDNS are common in OS queries. */
    packet[11] = 1;
    const unsigned char opt[] = {0,0,41,2,0,0,0,0,0,0,0};
    memcpy(packet + sizeof(query), opt, sizeof(opt));
    assert(captive_dns_reply(packet, sizeof(query) + sizeof(opt), reply, 512) == sizeof(query) + 16);
    assert(reply[10] == 0 && reply[11] == 0);
    assert(!captive_dns_reply(packet, 513, reply, 512));
    /* Maximum legal uncompressed name, then a name exceeding 255 wire bytes. */
    memcpy(packet, query, 12);
    packet[3] = packet[11] = 0;
    size_t offset = 12;
    for (int part = 0; part < 4; ++part) {
        unsigned count = part == 3 ? 61 : 63;
        packet[offset++] = count;
        memset(packet + offset, 'a', count); offset += count;
    }
    packet[offset++] = 0;
    memcpy(packet + offset, "\x00\x01\x00\x01", 4); offset += 4;
    assert(captive_dns_reply(packet, offset, reply, 512) == offset + 16);
    packet[204] = 63;
    memset(packet + 205, 'a', 63);
    packet[268] = 0;
    memcpy(packet + 269, "\x00\x01\x00\x01", 4);
    assert(!captive_dns_reply(packet, 273, reply, 512));
    return 0;
}
'''


class CaptiveDnsTests(unittest.TestCase):
    def test_redirect_answers_and_malformed_packets(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is separate")
        with tempfile.TemporaryDirectory(prefix="captive-dns-") as directory:
            root = Path(directory)
            harness = root / "test.c"
            harness.write_text(HARNESS, encoding="utf-8")
            executable = root / "test.exe"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            f"-I{COMPONENT / 'include'}", str(COMPONENT / "captive_dns.c"),
                            str(harness), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
