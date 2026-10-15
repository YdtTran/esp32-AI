"""Final English transcript JSON lines -> local Ollama -> console JSON lines."""
from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import logging
import math
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

LOG = logging.getLogger(__name__)
SYSTEM_PROMPT = (
    "You are a helpful voice assistant. Understand and respond in English only. "
    "Give a concise answer in one or two sentences. You cannot control devices."
)


class OllamaClient:
    """Stateless, bounded non-streaming chat; no SDK or Python GPU dependency."""

    def __init__(self, url="http://127.0.0.1:11434", model="qwen3:1.7b",
                 timeout=60, keep_alive="0"):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("Ollama URL must be a local HTTP origin without credentials")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.url, self.model, self.timeout, self.keep_alive = url.rstrip("/"), model, timeout, keep_alive

    def chat(self, text):
        payload = {"model": self.model, "stream": False, "think": False,
                   "keep_alive": self.keep_alive,
                   "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": text}],
                   "options": {"num_ctx": 2048, "num_predict": 128, "temperature": 0.2}}
        request = Request(self.url + "/api/chat", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        # Local transcripts must not pass through host HTTP proxy settings.
        with build_opener(ProxyHandler({})).open(request, timeout=self.timeout) as response:
            data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("Ollama response exceeded 1 MiB")
        result = json.loads(data)
        content = result.get("message", {}).get("content")
        if result.get("error") or result.get("done") is not True or not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama did not return a completed nonempty response")
        metrics = {key: result[key] for key in (
            "total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
            "prompt_eval_count", "eval_count", "done_reason") if key in result}
        return content.strip(), metrics


def emit(result):
    print(json.dumps(result, ensure_ascii=True), flush=True)


class Orchestrator:
    def __init__(self, client, output=emit):
        self.client, self.output = client, output
        self.queue = asyncio.Queue(maxsize=1)

    def submit(self, event):
        if not isinstance(event, dict) or event.get("type") != "transcript":
            return
        self.output(event)  # Preserve the existing finalized transcript even on LLM failure.
        text = event.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        if len(text) > 4000:
            self.output({"type": "llm_error", "item_id": event.get("item_id"),
                         "error": "Transcript exceeds 4000 characters"})
            return
        if self.queue.full():
            old, _ = self.queue.get_nowait()
            self.queue.task_done()
            self.output({"type": "llm_dropped", "item_id": old.get("item_id"),
                         "reason": "Replaced pending transcript with latest utterance"})
        self.queue.put_nowait((event, time.monotonic()))

    async def work(self):
        while True:
            event, received = await self.queue.get()
            started = time.monotonic()
            try:
                text, metrics = await asyncio.to_thread(self.client.chat, event["text"].strip())
                finished = time.monotonic()
                self.output({"type": "llm_response", "item_id": event.get("item_id"),
                             "model": self.client.model, "text": text,
                             "queue_ms": round((started - received) * 1000, 2),
                             "http_ms": round((finished - started) * 1000, 2),
                             "transcript_to_response_ms": round((finished - received) * 1000, 2),
                             "ollama_metrics": metrics})
            except (OSError, ValueError, KeyError, TypeError, AttributeError, http.client.HTTPException) as exc:
                self.output({"type": "llm_error", "item_id": event.get("item_id"),
                             "error": str(exc)})
            finally:
                self.queue.task_done()


async def run(args, bridge_args, output=emit):
    client = OllamaClient(args.ollama_url, args.llm_model, args.llm_timeout, args.keep_alive)
    orchestrator = Orchestrator(client, output)
    worker = asyncio.create_task(orchestrator.work())
    process = None
    try:
        if args.text is not None:
            orchestrator.submit({"type": "transcript", "item_id": "text-smoke", "text": args.text})
        else:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-u", "-m", "iot_models.realtime_bridge", *bridge_args,
                stdout=asyncio.subprocess.PIPE)  # Bridge diagnostics inherit stderr.
            async for line in process.stdout:
                try:
                    orchestrator.submit(json.loads(line))
                except (ValueError, UnicodeError):
                    LOG.warning("Ignored malformed bridge JSON")
            if await process.wait():
                raise RuntimeError("Transcription bridge exited unsuccessfully")
        await orchestrator.queue.join()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        if process is not None and process.returncode is None:
            process.terminate()
            await process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        "Put realtime_bridge options after --, e.g. -- --listen PC_IP --device-ip ESP_IP")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--llm-model", default="qwen3:1.7b")
    parser.add_argument("--llm-timeout", type=float, default=60)
    parser.add_argument("--keep-alive", default="0", help="Ollama residency; 0 unloads after each request")
    parser.add_argument("--text", help="Test Ollama directly without starting the audio bridge")
    parser.add_argument("bridge_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    bridge_args = args.bridge_args[1:] if args.bridge_args[:1] == ["--"] else args.bridge_args
    if args.text is None and not bridge_args:
        parser.error("supply bridge options after --, including --device-ip")
    try:
        OllamaClient(args.ollama_url, args.llm_model, args.llm_timeout, args.keep_alive)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asyncio.run(run(args, bridge_args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
