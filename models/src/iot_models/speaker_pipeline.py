"""Piper HTTP adapter and volatile one-reply ESP32 playback mailbox."""
import http.client
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .tts_audio import FORMAT, MAX_BYTES, validate_pcm

LOG = logging.getLogger(__name__)


class PiperClient:
    def __init__(self, url, timeout=30):
        endpoint = urlsplit(url)
        if (endpoint.scheme != "http" or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.path not in {"", "/"}
                or endpoint.query or endpoint.fragment):
            raise ValueError("Piper URL must be an HTTP origin without credentials")
        self.endpoint, self.timeout = endpoint, timeout

    def synthesize(self, text):
        import json
        connection = http.client.HTTPConnection(self.endpoint.hostname, self.endpoint.port,
                                                timeout=self.timeout)
        try:
            connection.request("POST", "/synthesize", json.dumps({"text": text}).encode(),
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200 or response.getheader("X-Audio-Format") != FORMAT:
                raise RuntimeError(f"Piper returned HTTP {response.status} or unsupported audio")
            return validate_pcm(response.read(MAX_BYTES + 1))
        finally:
            connection.close()


class SpeakerPipeline:
    def __init__(self, client, address=("0.0.0.0", 5006), ttl=30):
        self.client, self.ttl = client, ttl
        self.pending = None
        self.lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    return
                if self.path != "/audio":
                    self.send_error(404)
                    return
                with owner.lock:
                    pending, owner.pending = owner.pending, None
                if pending is None or time.monotonic() - pending[0] > owner.ttl:
                    self.send_response(204)
                    self.end_headers()
                    return
                pcm = pending[1]
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("X-Audio-Format", FORMAT)
                self.send_header("Content-Length", str(len(pcm)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    # Content-Length framing remains unchanged. Small writes
                    # let a realtime I2S consumer apply TCP backpressure without
                    # spending its whole clip in one socket sendall deadline.
                    for offset in range(0, len(pcm), 8192):
                        self.wfile.write(pcm[offset:offset + 8192])
                except OSError:
                    LOG.warning("Speaker download interrupted; reply discarded")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(address, Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def speak(self, text):
        pcm = self.client.synthesize(text)
        with self.lock:
            if self.pending is not None:
                LOG.warning("Replacing uncollected speaker reply")
            self.pending = (time.monotonic(), pcm)
        LOG.info("TTS ready: %.3f seconds of audio (delivery is not playback confirmation)",
                 len(pcm) / 32000)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
