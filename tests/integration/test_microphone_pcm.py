"""Compile the actual firmware serializer and decode its output on the host."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from iot_models.realtime_bridge import decode_packet

ROOT = Path(__file__).resolve().parents[2]


class CompatibilityTests(unittest.TestCase):
    def test_c_producer_python_consumer(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "producer.c"
            binary = Path(directory) / "producer.exe"
            source.write_text('''#include <stdio.h>
#include "voice_pcm.h"
int main(void) {
    int32_t raw[] = {0, INT32_MAX, INT32_MIN, -65536, 65536};
    uint8_t pcm[10];
    voice_pcm_encode(raw, pcm, 5);
    for (int i = 0; i < 10; ++i) printf("%02x", pcm[i]);
    return 0;
}
''', encoding="utf-8")
            subprocess.run([compiler, "-Wall", "-Wextra", "-Werror", "-I",
                str(ROOT / "firmware/components/voice_stream/include"), str(source),
                "-o", str(binary)], check=True, capture_output=True)
            packet = bytes.fromhex(subprocess.check_output([str(binary)], text=True))
        self.assertEqual(decode_packet(packet), (0, 32767, -32768, -1, 1))
