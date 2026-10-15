"""Regression: ESP-IDF's IPv6 HTTP listener reports mapped IPv4 destinations."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "components" / "voice_stream"
HARNESS = r'''
#include "portal_address.h"
#include "lwip/sockets.h"
#include <assert.h>
#include <string.h>
int main(void) {
    struct sockaddr_in ipv4 = {0};
    ipv4.sin_family = AF_INET;
    const unsigned char ap[4] = {192,168,4,1};
    memcpy(&ipv4.sin_addr, ap, 4);
    assert(portal_address_is_ap(&ipv4, sizeof(ipv4)));
    assert(!portal_address_is_ap(&ipv4, sizeof(ipv4) - 1));
    const unsigned char station[4] = {192,168,1,16};
    memcpy(&ipv4.sin_addr, station, 4);
    assert(!portal_address_is_ap(&ipv4, sizeof(ipv4)));
    struct sockaddr_in6 ipv6 = {0};
    ipv6.sin6_family = AF_INET6;
    unsigned char *bytes = (unsigned char *)&ipv6.sin6_addr;
    bytes[10] = bytes[11] = 255;
    memcpy(bytes + 12, ap, 4);
    assert(portal_address_is_ap(&ipv6, sizeof(ipv6)));
    assert(!portal_address_is_ap(&ipv6, sizeof(ipv6) - 1));
    memcpy(bytes + 12, station, 4);
    assert(!portal_address_is_ap(&ipv6, sizeof(ipv6)));
    memcpy(bytes + 12, ap, 4);
    bytes[0] = 1;
    assert(!portal_address_is_ap(&ipv6, sizeof(ipv6)));
    memset(bytes, 0, 16); bytes[15] = 1;
    assert(!portal_address_is_ap(&ipv6, sizeof(ipv6)));
    assert(!portal_address_is_ap(&ipv6, 0));
    return 0;
}
'''


class PortalAddressTests(unittest.TestCase):
    def test_ap_only_for_ipv4_and_mapped_ipv6(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is separate")
        with tempfile.TemporaryDirectory(prefix="portal-address-") as directory:
            root = Path(directory)
            (root / "lwip").mkdir()
            (root / "lwip" / "sockets.h").write_text(
                "#pragma once\n#define LWIP_IPV6 1\n#ifdef _WIN32\n#include <winsock2.h>\n#include <ws2tcpip.h>\n#else\n#include <sys/socket.h>\n#include <netinet/in.h>\n#endif\n",
                encoding="utf-8",
            )
            harness = root / "test.c"
            harness.write_text(HARNESS, encoding="utf-8")
            executable = root / "test.exe"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            f"-I{root}", f"-I{COMPONENT}", str(COMPONENT / "portal_address.c"),
                            str(harness), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
