"""Opt-in live UDP/WebSocket/GPU smoke test with a supplied English test WAV."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav")
    parser.add_argument("--expect", default="hello")
    parser.add_argument("--port", default=15005, type=int)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "transcripts.jsonl"
        errors = Path(folder) / "bridge.log"
        with output.open("w") as out, errors.open("w") as err:
            bridge = subprocess.Popen([sys.executable, "-m", "iot_models.realtime_bridge",
                "--device-ip", "127.0.0.1", "--port", str(args.port)], stdout=out, stderr=err)
            replay = None
            try:
                time.sleep(1)
                replay = subprocess.Popen([sys.executable, "-m", "iot_models.replay_microphone",
                    args.wav, "--port", str(args.port), "--repeat", "8"])
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if bridge.poll() is not None:
                        raise RuntimeError("Bridge exited: " + errors.read_text())
                    lines = output.read_text().splitlines()
                    for line in lines:
                        try:
                            result = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if args.expect.lower() in result["text"].lower():
                            print("PASS: paced UDP -> bridge -> live Speaches GPU: " + line)
                            return
                    time.sleep(0.2)
                raise RuntimeError("No matching transcript. " + output.read_text() + errors.read_text())
            finally:
                for process in (replay, bridge):
                    if process is not None and process.poll() is None:
                        if sys.platform == "win32":
                            # Stop the venv launcher and its interpreter together.
                            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            process.terminate()
                        process.wait(timeout=10)


if __name__ == "__main__":
    main()
