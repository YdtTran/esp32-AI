import asyncio
import io
import json
import threading
import unittest
from unittest.mock import patch

from iot_models.voice_orchestrator import OllamaClient, Orchestrator, SYSTEM_PROMPT


class ClientTests(unittest.TestCase):
    def test_request_and_duration_metrics(self):
        response = {"done": True, "message": {"content": " Hello. "},
                    "load_duration": 123, "eval_count": 2}
        with patch("iot_models.voice_orchestrator.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
            text, metrics = OllamaClient().chat("Hi")
            request = opener.return_value.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(text, "Hello.")
        self.assertEqual(metrics, {"load_duration": 123, "eval_count": 2})
        self.assertEqual(payload["messages"], [{"role": "system", "content": SYSTEM_PROMPT},
                                                {"role": "user", "content": "Hi"}])
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["keep_alive"], "0")

    def test_reject_remote_urls_and_invalid_timeout(self):
        for url in ("https://localhost", "http://example.com", "http://localhost/api",
                    "http://user:secret@localhost", "http://localhost?key=secret"):
            with self.assertRaises(ValueError):
                OllamaClient(url)
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                OllamaClient(timeout=timeout)

    def test_invalid_server_responses(self):
        for response in ({"done": False, "message": {"content": "partial"}},
                         {"error": "missing model"}, {"done": True, "message": {"content": ""}}):
            with patch("iot_models.voice_orchestrator.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
                with self.assertRaises(ValueError):
                    OllamaClient().chat("Hi")


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_llm_does_not_block_ingress_and_only_latest_waits(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        class Client:
            model = "test"
            def chat(self, text):
                calls.append(text)
                if text == "active":
                    entered.set()
                    release.wait(2)
                return "reply", {}
        output = []
        orchestrator = Orchestrator(Client(), output.append)
        worker = asyncio.create_task(orchestrator.work())
        try:
            orchestrator.submit({"type": "transcript", "text": "active"})
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            for text in ("stale", "latest"):
                orchestrator.submit({"type": "transcript", "text": text})
            self.assertEqual(len([event for event in output if event["type"] == "transcript"]), 3)
            release.set()
            await asyncio.wait_for(orchestrator.queue.join(), 2)
            self.assertEqual(calls, ["active", "latest"])
        finally:
            release.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    async def test_only_final_nonempty_transcripts_and_latest_pending(self):
        output = []
        orchestrator = Orchestrator(None, output.append)
        orchestrator.submit({"type": "delta", "text": "partial"})
        orchestrator.submit({"type": "transcript", "text": "  "})
        self.assertTrue(orchestrator.queue.empty())
        orchestrator.submit({"type": "transcript", "item_id": "1", "text": "one"})
        orchestrator.submit({"type": "transcript", "item_id": "2", "text": "two"})
        self.assertEqual(orchestrator.queue.qsize(), 1)
        self.assertEqual(orchestrator.queue.get_nowait()[0]["item_id"], "2")
        self.assertEqual(output[-2]["type"], "transcript")
        self.assertEqual(output[-1]["type"], "llm_dropped")
        self.assertEqual(output[-1]["item_id"], "1")

    async def test_failure_preserves_transcript_and_next_request_succeeds(self):
        class Client:
            model = "test"
            def chat(self, text):
                if text == "fail":
                    raise TimeoutError("timed out")
                return "English response", {"eval_count": 2}
        output = []
        orchestrator = Orchestrator(Client(), output.append)
        worker = asyncio.create_task(orchestrator.work())
        try:
            for text in ("fail", "succeed"):
                orchestrator.submit({"type": "transcript", "item_id": text, "text": text})
                await asyncio.wait_for(orchestrator.queue.join(), 2)
            self.assertEqual([event["type"] for event in output],
                             ["transcript", "llm_error", "transcript", "llm_response"])
            self.assertEqual(output[-1]["item_id"], "succeed")
            self.assertGreaterEqual(output[-1]["transcript_to_response_ms"], 0)
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    async def test_oversized_transcript_preserved_without_request(self):
        output = []
        orchestrator = Orchestrator(None, output.append)
        orchestrator.submit({"type": "transcript", "text": "x" * 4001})
        self.assertEqual([event["type"] for event in output], ["transcript", "llm_error"])
        self.assertTrue(orchestrator.queue.empty())
