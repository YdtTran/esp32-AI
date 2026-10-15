"""Opt-in Docker speech -> real STT -> real LLM -> Piper -> HTTP PCM check.

Run inside voice-loop's image, on unused loopback ports. No physical I2S test.
"""
import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

from iot_models.speaker_pipeline import PiperClient
from iot_models.tts_audio import validate_pcm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piper", default="http://piper:5000")
    parser.add_argument("--ollama", default="http://ollama:11434")
    parser.add_argument("--speaches", default="ws://speaches:8000")
    args = parser.parse_args()
    pcm = PiperClient(args.piper).synthesize("Hello. What is two plus two?")
    process = subprocess.Popen([sys.executable, "-u", "-m", "iot_models.orchestrator",
        "--url", args.ollama, "--piper-url", args.piper, "--speaker-port", "15026",
        "--stt", "--", "--listen", "127.0.0.1", "--device-ip", "127.0.0.1",
        "--port", "15025", "--server", args.speaches], stdout=subprocess.PIPE,
        text=True, env=os.environ.copy())
    lines = queue.Queue()
    def collect():
        for line in process.stdout:
            lines.put(line.strip())
    threading.Thread(target=collect, daemon=True).start()
    try:
        time.sleep(3)
        started = time.monotonic()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            audio = b"\0" * 16000 + pcm + b"\0" * 32000
            for offset in range(0, len(audio), 512):
                udp.sendto(audio[offset:offset + 512], ("127.0.0.1", 15025))
                time.sleep(0.016)
        transcript, reply = None, None
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            while not lines.empty():
                line = lines.get_nowait()
                print(line, flush=True)
                if line.startswith("[STT] Text:"):
                    transcript = line
                if line.startswith("[LLM] Response:"):
                    reply = line
            try:
                with urlopen("http://127.0.0.1:15026/audio", timeout=2) as response:
                    if response.status == 200:
                        output = validate_pcm(response.read())
                        if response.headers.get("X-Audio-Format") != "pcm-s16le-16000-mono":
                            raise RuntimeError("Unsupported speaker format")
                        if not transcript or not reply:
                            raise RuntimeError("PCM arrived without transcript/LLM output")
                        print(json.dumps({"result": "pass", "pcm_bytes": len(output),
                            "audio_seconds": len(output) / 32000,
                            "replay_to_collected_seconds": time.monotonic() - started}))
                        return
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("Orchestrator exited during smoke test")
            time.sleep(0.1)
        raise TimeoutError("No speaker PCM received after real STT/LLM")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()


if __name__ == "__main__":
    main()
