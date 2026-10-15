"""Small streaming Ollama chat adapter; no SDK or GPU dependency on the host."""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
import time
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ChatResult:
    text: str
    first_token_seconds: float | None
    total_seconds: float


class OllamaClient:
    def __init__(self, url="http://127.0.0.1:11434", timeout=90):
        self.endpoint = urlsplit(url)
        if (self.endpoint.scheme not in {"http", "https"} or not self.endpoint.hostname
                or self.endpoint.username or self.endpoint.password
                or self.endpoint.query or self.endpoint.fragment):
            raise ValueError("Ollama URL must be an HTTP(S) base URL without credentials/query")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        self.timeout = timeout

    def chat(self, messages):
        payload = {"model": "qwen3:1.7b", "messages": messages,
                   "think": False, "stream": True,
                   "options": {"num_ctx": 2048, "num_predict": 100, "temperature": 0.3}}
        started = time.monotonic()
        deadline = started + self.timeout
        connection_type = (http.client.HTTPSConnection if self.endpoint.scheme == "https"
                           else http.client.HTTPConnection)
        connection = connection_type(self.endpoint.hostname, self.endpoint.port,
                                     timeout=self.timeout)
        first = None
        parts = []
        try:
            connection.connect()
            sock = connection.sock

            def remaining():
                seconds = deadline - time.monotonic()
                if seconds <= 0:
                    raise TimeoutError("Ollama request deadline exceeded")
                sock.settimeout(seconds)

            remaining()
            connection.request("POST", self.endpoint.path.rstrip("/") + "/api/chat",
                               json.dumps(payload).encode("utf-8"),
                               {"Content-Type": "application/json"})
            remaining()
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"Ollama HTTP {response.status}: {response.reason}")
            pending = b""
            while True:
                remaining()
                chunk = response.read1(4096)
                if not chunk:
                    raise RuntimeError("Ollama stream ended without a completed response")
                pending += chunk
                if len(pending) > 1024 * 1024:
                    raise RuntimeError("Ollama stream frame exceeds 1 MiB")
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise RuntimeError("Invalid Ollama stream event")
                    if event.get("error"):
                        raise RuntimeError(f"Ollama: {event['error']}")
                    message = event.get("message", {})
                    if not isinstance(message, dict):
                        raise RuntimeError("Invalid Ollama message")
                    if message.get("thinking"):
                        raise RuntimeError("Ollama emitted thinking despite think=false")
                    content = message.get("content", "")
                    if not isinstance(content, str):
                        raise RuntimeError("Invalid Ollama content")
                    if content:
                        if first is None:
                            first = time.monotonic() - started
                        parts.append(content)
                    if event.get("done") is True:
                        text = "".join(parts).strip()
                        if not text:
                            raise RuntimeError("Ollama returned an empty response")
                        return ChatResult(text, first, time.monotonic() - started)
        finally:
            connection.close()
