import http.client
import io
import struct
import threading
import unittest
import wave
from io import StringIO
from unittest.mock import patch

from iot_models.ollama_client import ChatResult
from iot_models.orchestrator import Conversation, print_reply
from iot_models.piper_service import make_server
from iot_models.speaker_pipeline import PiperClient, SpeakerPipeline
from iot_models.tts_audio import FORMAT, MAX_BYTES, validate_pcm, wav_to_pcm


class AudioTests(unittest.TestCase):
    def test_resampling_and_limits(self):
        data = io.BytesIO()
        with wave.open(data, "wb") as wav:
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(struct.pack("<h", 1000) * 22050)
        pcm = wav_to_pcm(data.getvalue())
        self.assertAlmostEqual(len(pcm) / 32000, 1, places=3)
        self.assertEqual(struct.unpack("<h", pcm[:2])[0], 1000)
        for invalid in (b"", b"x", b"x" * (MAX_BYTES + 2)):
            with self.assertRaises(ValueError):
                validate_pcm(invalid)

    def test_only_successful_final_response_is_spoken_and_tts_failure_retains_history(self):
        class Client:
            def chat(self, messages):
                return ChatResult("Final reply.", 0.1, 0.2)
        class Speaker:
            calls = []
            def speak(self, text):
                self.calls.append(text)
                raise TimeoutError("offline")
        conversation, speaker = Conversation(Client()), Speaker()
        with patch("sys.stdout", new=StringIO()), self.assertLogs(level="ERROR"):
            self.assertTrue(print_reply(conversation, "Hello", speaker=speaker))
        self.assertEqual(speaker.calls, ["Final reply."])
        self.assertEqual(conversation.history[-1]["content"], "Final reply.")
        with patch.object(conversation.client, "chat", side_effect=TimeoutError("LLM offline")), \
                patch("sys.stdout", new=StringIO()), self.assertLogs(level="ERROR"):
            self.assertFalse(print_reply(conversation, "Again", speaker=speaker))
        self.assertEqual(len(speaker.calls), 1)


class HttpTests(unittest.TestCase):
    def test_piper_http_to_mailbox_once_replacement_and_expiry(self):
        class Voice:
            def synthesize_wav(self, text, wav):
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00\x00\xff\x7f\x00\x80")
        piper = make_server(("127.0.0.1", 0), Voice())
        worker = threading.Thread(target=piper.serve_forever, daemon=True)
        worker.start()
        speaker = SpeakerPipeline(PiperClient(f"http://127.0.0.1:{piper.server_port}"),
                                  ("127.0.0.1", 0))
        speaker.start()
        connection = http.client.HTTPConnection("127.0.0.1", speaker.server.server_port)
        try:
            for text in ("old", "latest"):
                speaker.speak(text)
            connection.request("GET", "/audio")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("X-Audio-Format"), FORMAT)
            self.assertEqual(response.read(), b"\x00\x00\xff\x7f\x00\x80")
            connection.request("GET", "/audio")
            response = connection.getresponse()
            self.assertEqual(response.status, 204)
            response.read()
            speaker.speak("expired")
            speaker.ttl = -1
            connection.request("GET", "/audio")
            response = connection.getresponse()
            self.assertEqual(response.status, 204)
            response.read()
        finally:
            connection.close()
            speaker.close()
            piper.shutdown()
            piper.server_close()
            worker.join()

    def test_invalid_client_url_and_server_format_rejected(self):
        with patch("iot_models.speaker_pipeline.http.client.HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.getheader.return_value = "wrong"
            with self.assertRaises(RuntimeError):
                PiperClient("http://localhost:5000").synthesize("Hello")
        for url in ("file:///tmp/test", "http://user:secret@localhost", "http://localhost/path"):
            with self.assertRaises(ValueError):
                PiperClient(url)

    def test_reply_larger_than_one_network_write_is_complete(self):
        pcm = bytes.fromhex("0000ff7f0080") * 40000
        class Client:
            def synthesize(self, text):
                return pcm
        speaker = SpeakerPipeline(Client(), ("127.0.0.1", 0))
        speaker.start()
        connection = http.client.HTTPConnection("127.0.0.1", speaker.server.server_port)
        try:
            speaker.speak("Long response")
            connection.request("GET", "/audio")
            response = connection.getresponse()
            self.assertEqual(int(response.getheader("Content-Length")), len(pcm))
            self.assertEqual(response.read(), pcm)
        finally:
            connection.close()
            speaker.close()
