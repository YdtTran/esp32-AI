"""Scan SSIDs are untrusted: exercise actual JSON escaping and output bounds."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "components" / "voice_stream"
HARNESS = r'''
#include "setup_networks.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    setup_network_t networks[SETUP_NETWORK_LIMIT] = {0};
    strcpy(networks[0].ssid, "Home\"\\\n</script>");
    networks[0].rssi = -42; networks[0].supported = true;
    strcpy(networks[1].ssid, "Guest");
    networks[1].rssi = -80;
    char output[4096];
    size_t length = setup_networks_json(networks, 2, output, sizeof(output));
    assert(length && length == strlen(output));
    puts(output);
    assert(!setup_networks_json(networks, 2, output, length));
    assert(!setup_networks_json(networks, 2, output, 0));
    assert(!setup_networks_json(networks, SETUP_NETWORK_LIMIT + 1, output, sizeof(output)));
    assert(setup_networks_json(networks, 0, output, sizeof(output)) == 2);
    assert(!strcmp(output, "[]"));
    for (unsigned i = 0; i < SETUP_NETWORK_LIMIT; ++i) {
        memset(networks[i].ssid, 1, 32); networks[i].ssid[32] = 0;
    }
    assert(setup_networks_json(networks, SETUP_NETWORK_LIMIT, output, sizeof(output)));
    memset(networks[0].ssid, 'a', sizeof(networks[0].ssid));
    assert(!setup_networks_json(networks, 1, output, sizeof(output)));
    networks[0].ssid[0] = 0;
    assert(!setup_networks_json(networks, 1, output, sizeof(output)));
    return 0;
}
'''


class SetupNetworkTests(unittest.TestCase):
    def test_escape_round_trip_and_worst_case_capacity(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host gcc unavailable; ESP-IDF build is separate")
        with tempfile.TemporaryDirectory(prefix="setup-networks-") as directory:
            root = Path(directory)
            harness = root / "test.c"
            harness.write_text(HARNESS, encoding="utf-8")
            executable = root / "test.exe"
            subprocess.run([compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                            f"-I{COMPONENT}", str(COMPONENT / "setup_networks.c"),
                            str(harness), "-o", str(executable)], check=True)
            result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout), [
                {"ssid": 'Home"\\\n</script>', "rssi": -42, "supported": True},
                {"ssid": "Guest", "rssi": -80, "supported": False},
            ])
