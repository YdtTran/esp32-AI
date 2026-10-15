"""Exercise the actual C setup parser against malformed requests and boundaries."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "components" / "voice_stream"
HARNESS = r'''
#include "setup_config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void rejects(const char *body) {
    setup_config_t before;
    memset(&before, 0x55, sizeof(before));
    setup_config_t after = before;
    assert(!setup_config_parse(body, strlen(body), &after));
    assert(!memcmp(&before, &after, sizeof(before)));
}
int main(void) {
    setup_config_t config;
    const char *good = "ssid=Home+WiFi%26Guest&password=A%2Bb%25cd123&pc=192.168.1.100";
    assert(setup_config_parse(good, strlen(good), &config));
    assert(!strcmp(config.ssid, "Home WiFi&Guest"));
    assert(!strcmp(config.password, "A+b%cd123"));
    assert(!strcmp(config.address, "192.168.1.100"));
    const char *bad[] = {
        "", "ssid=x", "ssid=x&password=12345678&pc=192.168.1.1&",
        "ssid=x&password=12345678&pc=192.168.1.1&ssid=y",
        "ssid=x&password=12345678&pc=192.168.1.1&extra=x",
        "ssid=&password=12345678&pc=192.168.1.1",
        "ssid=x%00y&password=12345678&pc=192.168.1.1",
        "ssid=x%0Ay&password=12345678&pc=192.168.1.1",
        "ssid=x%ZZ&password=12345678&pc=192.168.1.1",
        "ssid=x%&password=12345678&pc=192.168.1.1",
        "ssid=x&password=short&pc=192.168.1.1",
        "ssid=x&password=12345678&pc=127.0.0.1",
        "ssid=x&password=12345678&pc=0.0.0.0",
        "ssid=x&password=12345678&pc=224.0.0.1",
        "ssid=x&password=12345678&pc=255.255.255.255",
        "ssid=x&password=12345678&pc=192.168.01.1",
        "ssid=x&password=12345678&pc=192.168.256.1",
        "ssid=x&password=12345678&pc=192.168.1",
        "ssid=x&password=12345678&pc=192.168.1.1:5006",
        "ssid=x&password=12345678&pc=http://192.168.1.1"
    };
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) rejects(bad[i]);
    char body[256], ssid[34], password[66];
    memset(ssid, 's', 32); ssid[32] = 0;
    memset(password, 'a', 64); password[64] = 0;
    snprintf(body, sizeof(body), "ssid=%s&password=%s&pc=10.0.0.2", ssid, password);
    assert(setup_config_parse(body, strlen(body), &config));
    password[0] = 'g';
    snprintf(body, sizeof(body), "ssid=%s&password=%s&pc=10.0.0.2", ssid, password);
    rejects(body);
    password[0] = 'a'; password[64] = 'a'; password[65] = 0;
    snprintf(body, sizeof(body), "ssid=%s&password=%s&pc=10.0.0.2", ssid, password);
    rejects(body);
    password[63] = 0; ssid[32] = 's'; ssid[33] = 0;
    snprintf(body, sizeof(body), "ssid=%s&password=%s&pc=10.0.0.2", ssid, password);
    rejects(body);
    memset(&config, 'a', sizeof(config));
    assert(!setup_config_valid(&config));
    return 0;
}
'''


class SetupConfigTests(unittest.TestCase):
    def test_form_validation_and_atomic_update(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is separate")
        with tempfile.TemporaryDirectory(prefix="setup-config-") as directory:
            root = Path(directory)
            source = root / "test.c"
            source.write_text(HARNESS, encoding="utf-8")
            executable = root / "test.exe"
            subprocess.run([compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                            f"-I{COMPONENT / 'include'}", str(COMPONENT / "setup_config.c"),
                            str(source), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
