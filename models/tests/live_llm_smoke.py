"""Opt-in paced WAV -> unchanged bridge -> Ollama test, with GPU snapshots.

Run first with --stt-only for a baseline, then without it for the combined path.
Replay-start timing includes audio playback/endpointing and is not STT compute time.
"""
import argparse
import json
import queue
import subprocess
import sys
import threading
import time


def snapshot():
    result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free",
                             "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=10)
    print("[GPU] used/free MiB: " + (result.stdout.strip() or result.stderr.strip()), flush=True)


def stop(process):
    if process is not None and process.poll() is None:
        if sys.platform == "win32":
            # Include the orchestrator's bridge child and any venv launcher.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            process.terminate()
        process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", help="English uncompressed mono PCM16/16 kHz WAV")
    parser.add_argument("--expect", default="hello")
    parser.add_argument("--port", type=int, default=15009)
    parser.add_argument("--stt-only", action="store_true")
    args = parser.parse_args()
    bridge_flags = ["--device-ip", "127.0.0.1", "--port", str(args.port)]
    module_flags = (["iot_models.realtime_bridge", *bridge_flags] if args.stt_only else
                    ["iot_models.orchestrator", "--stt", "--", *bridge_flags])
    snapshot()
    process = subprocess.Popen([sys.executable, "-u", "-m", *module_flags],
                               stdout=subprocess.PIPE, text=True, encoding="utf-8")
    lines = queue.Queue()
    def read():
        for line in process.stdout:
            lines.put((time.monotonic(), line.strip()))
    threading.Thread(target=read, daemon=True).start()
    replay = None
    try:
        time.sleep(2)
        started = time.monotonic()
        replay = subprocess.Popen([sys.executable, "-m", "iot_models.replay_microphone",
                                   args.wav, "--port", str(args.port)])
        deadline = started + 120
        matched = False
        completed = False
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Bridge/orchestrator exited before completion")
            if replay.poll() is not None and replay.returncode != 0:
                raise RuntimeError("Audio replay failed")
            try:
                received, line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            print(line, flush=True)
            if args.stt_only:
                event = json.loads(line)
                matched = args.expect.lower() in event.get("text", "").lower()
            elif line.startswith("[STT] Text:"):
                matched = args.expect.lower() in line.lower()
            if matched and (args.stt_only or line.startswith("[STT] Text:")):
                print(f"[SMOKE] Replay start -> final transcript observed: {received - started:.3f} s",
                      flush=True)
                snapshot()
                if args.stt_only:
                    completed = True
                    break
            if matched and line.startswith("[METRICS] Final-transcript receipt"):
                completed = True
                snapshot()
                break
        if not completed:
            raise RuntimeError("No matching completed turn within 120 seconds")
        print("PASS: live STT" if args.stt_only else "PASS: live STT -> LLM", flush=True)
    finally:
        stop(replay)
        stop(process)
        process.stdout.close()


if __name__ == "__main__":
    main()
