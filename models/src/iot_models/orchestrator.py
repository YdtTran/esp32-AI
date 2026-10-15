"""Sequential English terminal assistant using completed bridge JSON transcripts."""
from __future__ import annotations

import argparse
from collections import deque
import http.client
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time

from .ollama_client import OllamaClient

LOG = logging.getLogger(__name__)
SYSTEM_PROMPT = (
    "You are a concise English-speaking AI assistant for an IoT system. "
    "Always respond in English, clearly, accurately, and briefly. "
    "Do not claim to have controlled devices or accessed sensor data unless "
    "a connected tool actually performed that action. No tools are connected."
)


class Conversation:
    """Keep only three successful user/assistant pairs; never retry failed turns."""
    def __init__(self, client):
        self.client = client
        self.history = deque(maxlen=6)

    def reply(self, text):
        if len(text) > 1000:
            raise ValueError("Utterance exceeds prototype limit of 1000 characters")
        result = self.client.chat([{"role": "system", "content": SYSTEM_PROMPT},
                                  *self.history, {"role": "user", "content": text}])
        self.history.extend([{"role": "user", "content": text},
                             {"role": "assistant", "content": result.text}])
        return result


class FinalTranscripts:
    """Filter bridge finals and remember the most recent 256 item IDs."""
    def __init__(self):
        self.seen = deque(maxlen=256)

    def accept(self, line):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            LOG.warning("Ignoring non-JSON transcription line")
            return None
        if not isinstance(event, dict) or event.get("type") != "transcript":
            return None
        text, item_id = event.get("text"), event.get("item_id")
        if not isinstance(text, str) or not text.strip():
            return None
        if not isinstance(item_id, str) or not item_id:
            LOG.warning("Ignoring final transcript without an item_id")
            return None
        if item_id in self.seen:
            return None
        self.seen.append(item_id)
        return text.strip()


def print_reply(conversation, text, finalized_at=None):
    print("[LLM] Generating response...", flush=True)
    try:
        result = conversation.reply(text)
    except (OSError, RuntimeError, ValueError, http.client.HTTPException) as exc:
        LOG.error("LLM request failed (not retried): %s", exc)
        return False
    print(f"[LLM] Response: {result.text}", flush=True)
    first = (f"{result.first_token_seconds:.3f} s" if result.first_token_seconds is not None
             else "unavailable")
    print(f"[METRICS] LLM first-content latency: {first}\n"
          f"[METRICS] LLM total request/generation time: {result.total_seconds:.3f} s",
          flush=True)
    if finalized_at is not None:
        print("[METRICS] STT finalization: unavailable (bridge emits no timing)\n"
              f"[METRICS] Final-transcript receipt -> response: "
              f"{time.monotonic() - finalized_at:.3f} s", flush=True)
    return True


def transcript_mode(conversation, stream):
    # Drain bridge stdout even while Ollama runs: do not stall the working STT
    # bridge. One active turn plus four pending; drop newest when overloaded.
    pending = queue.Queue(maxsize=4)
    finished = threading.Event()
    finals = FinalTranscripts()

    def receive():
        try:
            for line in stream:
                received_at = time.monotonic()
                text = finals.accept(line)
                if text is not None:
                    try:
                        pending.put_nowait((text, received_at))
                    except queue.Full:
                        LOG.warning("LLM queue full; dropping finalized utterance")
        finally:
            finished.set()

    threading.Thread(target=receive, daemon=True).start()
    while not finished.is_set() or not pending.empty():
        try:
            text, received_at = pending.get(timeout=0.2)
        except queue.Empty:
            continue
        print(f"[STT] Turn finalized\n[STT] Text: {text}", flush=True)
        print_reply(conversation, text, received_at)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stt", action="store_true", help="Launch the unchanged PCM bridge")
    modes.add_argument("--transcripts", action="store_true", help="Read bridge JSONL from stdin")
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=float, default=os.environ.get("LLM_TIMEOUT_SECONDS", "90"))
    parser.add_argument("bridge_args", nargs=argparse.REMAINDER,
                        help="With --stt: -- followed by existing bridge flags")
    args = parser.parse_args()
    if args.bridge_args and not args.stt:
        parser.error("bridge flags require --stt")
    try:
        conversation = Conversation(OllamaClient(args.url, args.timeout))
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    bridge = None
    try:
        if args.stt:
            flags = args.bridge_args
            if flags[:1] == ["--"]:
                flags = flags[1:]
            bridge = subprocess.Popen([sys.executable, "-u", "-m",
                "iot_models.realtime_bridge", *flags], stdout=subprocess.PIPE,
                text=True, encoding="utf-8")
            transcript_mode(conversation, bridge.stdout)
            if bridge.wait() != 0:
                raise SystemExit("STT bridge failed; see its error output above")
        elif args.transcripts:
            transcript_mode(conversation, sys.stdin)
        else:
            while True:
                try:
                    text = input("User: ").strip()
                except EOFError:
                    break
                if text.lower() in {"/quit", "/exit"}:
                    break
                if text:
                    print_reply(conversation, text)
    except KeyboardInterrupt:
        pass
    finally:
        if bridge is not None:
            if bridge.poll() is None:
                bridge.terminate()
                try:
                    bridge.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    bridge.kill()
                    bridge.wait()
            bridge.stdout.close()


if __name__ == "__main__":
    main()
