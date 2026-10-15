"""Regression coverage for final-only sequential chat and streaming failures."""
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest.mock import patch

from iot_models.ollama_client import ChatResult, OllamaClient
from iot_models.orchestrator import Conversation, FinalTranscripts, transcript_mode


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.events = [{"message": {"content": "Hello "}, "done": False},
                       {"message": {"content": "world."}, "done": True}]
        self.payloads = []
        self.status = 200
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.payloads.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(owner.status)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                try:
                    for event in owner.events:
                        time.sleep(owner.delay)
                        self.wfile.write((json.dumps(event) + "\n").encode())
                        self.wfile.flush()
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = OllamaClient(f"http://127.0.0.1:{self.server.server_port}", 2)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_stream_and_required_settings(self):
        result = self.client.chat([{"role": "user", "content": "Hello"}])
        self.assertEqual(result.text, "Hello world.")
        self.assertLessEqual(result.first_token_seconds, result.total_seconds)
        payload = self.payloads[0]
        self.assertEqual(payload["model"], "qwen3:1.7b")
        self.assertIs(payload["think"], False)
        self.assertIs(payload["stream"], True)
        self.assertEqual(payload["options"], {"num_ctx": 2048, "num_predict": 100, "temperature": 0.3})

    def test_http_failure(self):
        self.status = 503
        with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
            self.client.chat([])

    def test_incomplete_and_error_streams(self):
        for events, message in [([self.events[0]], "without a completed"),
                                ([{"error": "out of memory"}], "out of memory"),
                                ([{"message": {"thinking": "secret"}}], "thinking"),
                                ([{"done": True}], "empty response")]:
            with self.subTest(events=events):
                self.events = events
                with self.assertRaisesRegex(RuntimeError, message):
                    self.client.chat([])

    def test_total_deadline_during_stream(self):
        self.delay = 0.08
        self.client.timeout = 0.12
        with self.assertRaises(TimeoutError):
            self.client.chat([])


class OrchestratorTests(unittest.TestCase):
    def test_final_filter_dedup_and_repeated_words(self):
        finals = FinalTranscripts()
        for event in [None, [], {"type": "partial", "text": "hi"},
                      {"type": "transcript", "text": ""},
                      {"type": "transcript", "text": "hi"}]:
            self.assertIsNone(finals.accept(json.dumps(event)))
        event = {"type": "transcript", "item_id": "a", "text": " hi "}
        self.assertEqual(finals.accept(json.dumps(event)), "hi")
        self.assertIsNone(finals.accept(json.dumps(event)))
        event["item_id"] = "b"
        self.assertEqual(finals.accept(json.dumps(event)), "hi")
        for index in range(300):
            event["item_id"] = str(index)
            finals.accept(json.dumps(event))
        self.assertEqual(len(finals.seen), 256)

    def test_bounded_history_and_failed_turn(self):
        class Client:
            fail = False
            def chat(self, messages):
                self.messages = messages
                if self.fail:
                    raise TimeoutError("timeout")
                return ChatResult("OK", 0.1, 0.2)
        client = Client()
        conversation = Conversation(client)
        for index in range(5):
            conversation.reply(str(index))
        self.assertEqual(len(conversation.history), 6)
        self.assertEqual(conversation.history[0]["content"], "2")
        self.assertEqual(client.messages[0]["role"], "system")
        prior = list(conversation.history)
        client.fail = True
        with self.assertRaises(TimeoutError):
            conversation.reply("failed")
        self.assertEqual(list(conversation.history), prior)

    def test_final_input_one_call_per_id_and_continues_after_failure(self):
        events = [{"type": "partial", "text": "one"},
                  {"type": "transcript", "item_id": "1", "text": "one"},
                  {"type": "transcript", "item_id": "1", "text": "one"},
                  {"type": "transcript", "item_id": "2", "text": "two"}]
        class Client:
            calls = []
            def chat(self, messages):
                self.calls.append(messages[-1]["content"])
                if len(self.calls) == 1:
                    raise TimeoutError("offline")
                return ChatResult("OK", 0.01, 0.02)
        client = Client()
        with patch("sys.stdout", new=StringIO()), self.assertLogs(level="ERROR"):
            transcript_mode(Conversation(client), StringIO("\n".join(map(json.dumps, events))))
        self.assertEqual(client.calls, ["one", "two"])


if __name__ == "__main__":
    unittest.main()
