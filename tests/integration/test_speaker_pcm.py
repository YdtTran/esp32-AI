"""Actual firmware conversion agrees with Python-produced speaker PCM."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from iot_models.tts_audio import MAX_BYTES, validate_pcm

ROOT = Path(__file__).resolve().parents[2]


class SpeakerCompatibilityTests(unittest.TestCase):
    def test_python_pcm_to_c_i2s_and_length_validation(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        pcm = validate_pcm(bytes.fromhex("0000ff7f0080ffff0100"))
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / "speaker.c", Path(directory) / "speaker.exe"
            source.write_text('''#include <assert.h>
#include <stdio.h>
#include "speaker_pcm.h"
int main(void) {
    assert(!speaker_pcm_length_valid(0));
    assert(!speaker_pcm_length_valid(1));
    assert(!speaker_pcm_length_valid(SPEAKER_PCM_MAX_BYTES + 2));
    assert(speaker_pcm_length_valid(SPEAKER_PCM_MAX_BYTES));
    unsigned char sample[2];
    while (fread(sample, 1, 2, stdin) == 2) printf("%ld\\n", (long)speaker_pcm_word(sample));
    return 0;
}
''', encoding="utf-8")
            subprocess.run([compiler, "-Wall", "-Wextra", "-Werror", "-I",
                            str(ROOT / "firmware/components/voice_stream/include"),
                            str(source), "-o", str(binary)], check=True, capture_output=True)
            words = subprocess.check_output([str(binary)], input=pcm).decode().splitlines()
        self.assertEqual(list(map(int, words)), [0, 2147418112, -2147483648, -65536, 65536])
        self.assertEqual(MAX_BYTES, 1920000)
