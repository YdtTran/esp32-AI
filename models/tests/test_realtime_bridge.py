import asyncio
import base64
import contextlib
import io
import json
import struct
import unittest

from iot_models.realtime_bridge import AudioReceiver, Resampler, SpeechBuffer, decode_packet, run_session, wait_event


class SpeechBufferTests(unittest.TestCase):
    loud = struct.pack("<256h", *([3000] * 256))
    quiet = bytes(512)

    def test_silence_is_bounded_and_does_not_emit(self):
        gate = SpeechBuffer()
        for _ in range(2000):
            self.assertEqual(gate.feed(self.quiet), [])
        self.assertEqual(len(gate.pre_roll), 6400)
        self.assertEqual(len(gate.audio), 0)

    def test_speech_waits_for_silence_and_retains_pre_roll(self):
        gate = SpeechBuffer(silence_seconds=0.1)
        for _ in range(20):
            gate.feed(self.quiet)
        for _ in range(13):
            self.assertEqual(gate.feed(self.loud), [])
        for _ in range(6):
            self.assertEqual(gate.feed(self.quiet), [])
        audio, reason = gate.feed(self.quiet)[0]
        self.assertEqual(reason, "silence")
        self.assertEqual(audio, bytes(6400) + self.loud * 13 + self.quiet * 7)
        self.assertEqual(gate.feed(self.quiet), [])

    def test_click_is_rejected(self):
        gate = SpeechBuffer(silence_seconds=0.1)
        gate.feed(self.loud)
        for _ in range(20):
            self.assertEqual(gate.feed(self.quiet), [])

    def test_long_speech_is_split_without_exceeding_cap_or_losing_bytes(self):
        gate = SpeechBuffer(silence_seconds=0.1, max_seconds=0.5)
        output = []
        for _ in range(100):
            output.extend(gate.feed(self.loud))
            self.assertLess(len(gate.audio), 16000)
        self.assertEqual([len(audio) for audio, _ in output], [16000] * 3)
        self.assertTrue(all(reason == "max_duration" for _, reason in output))
        self.assertEqual(b"".join(audio for audio, _ in output) + gate.audio,
                         self.loud * 100)

    def test_invalid_settings(self):
        for settings in ({"threshold": 0}, {"threshold": float("nan")},
                         {"silence_seconds": 0}, {"max_seconds": 11},
                         {"max_seconds": 0.5, "silence_seconds": 0.6}):
            with self.assertRaises(ValueError):
                SpeechBuffer(**settings)


class ProtocolTests(unittest.TestCase):
    def test_examples_and_limits(self):
        self.assertEqual(decode_packet(bytes.fromhex("0000ff7f0080")), (0, 32767, -32768))
        for data in (b"", b"\x00", bytes(514)):
            with self.assertRaises(ValueError):
                decode_packet(data)
        self.assertEqual(len(decode_packet(bytes(512))), 256)

    def test_resampling_is_continuous(self):
        samples = list(range(-150, 150))
        packet = struct.pack("<300h", *samples)
        whole = Resampler()
        expected = b"".join(whole.feed(packet[i:i + 512]) for i in range(0, len(packet), 512))
        split = Resampler()
        actual = b"".join(split.feed(packet[i:i + 2]) for i in range(0, len(packet), 2))
        self.assertEqual(actual, expected)
        self.assertEqual(struct.unpack("<3h", actual[:6]), (-150, -150, -149))
        self.assertLessEqual(len(split.pending), 2)

    def test_resampling_extremes(self):
        data = Resampler().feed(struct.pack("<3h", -32768, 32767, -32768))
        self.assertEqual(struct.unpack("<3h", data), (-32768, 10922, 10922))

    def test_receiver_rejects_sources_and_resets_overflow(self):
        receiver = AudioReceiver("192.0.2.1")
        receiver.datagram_received(bytes(512), ("192.0.2.2", 1234))
        receiver.datagram_received(b"x", ("192.0.2.1", 1234))
        self.assertEqual(receiver.rejected, 2)
        for _ in range(64):
            receiver.datagram_received(bytes(512), ("192.0.2.1", 1234))
        self.assertEqual(receiver.generation, 1)
        self.assertEqual(receiver.queue.qsize(), 1)


class FakeSocket:
    def __init__(self, error=False):
        self.events = asyncio.Queue()
        self.events.put_nowait({"type": "session.created"})
        self.sent = []
        self.error = error

    async def send(self, message):
        event = json.loads(message)
        self.sent.append(event)
        if event["type"] == "session.update":
            self.events.put_nowait({"type": "session.updated", "session": event["session"]})
        elif event["type"] == "input_audio_buffer.commit":
            if self.error:
                self.events.put_nowait({"type": "error", "error": "model unavailable"})
            else:
                self.events.put_nowait({"type": "conversation.item.input_audio_transcription.completed",
                                       "item_id": "test", "transcript": "Hello world."})

    async def recv(self):
        return json.dumps(await self.events.get())


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_audio_uploaded_before_endpoint(self):
        receiver = AudioReceiver("127.0.0.1")
        ws = FakeSocket()
        task = asyncio.create_task(run_session(ws, receiver, "test-model",
                                               silence_seconds=0.1))
        try:
            await asyncio.sleep(0.01)
            for _ in range(13):
                await receiver.queue.put(SpeechBufferTests.loud)
            await asyncio.sleep(0.01)
            self.assertEqual([event["type"] for event in ws.sent], ["session.update"])
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(7):
                    await receiver.queue.put(SpeechBufferTests.quiet)
                await asyncio.sleep(0.01)
            self.assertEqual(sum(event["type"] == "input_audio_buffer.commit"
                                 for event in ws.sent), 1)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_speech_segments_are_sent_only_after_quiet(self):
        receiver = AudioReceiver("127.0.0.1")
        ws = FakeSocket()
        async def feed():
            await asyncio.sleep(0.01)
            for _ in range(20):
                for _ in range(13):
                    await receiver.queue.put(SpeechBufferTests.loud)
                for _ in range(7):
                    await receiver.queue.put(SpeechBufferTests.quiet)
        task = asyncio.create_task(feed())
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                await asyncio.wait_for(run_session(ws, receiver, "test-model",
                    silence_seconds=0.1, max_audio_seconds=0.5), 10)
            rows = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(len(rows), 20)
            self.assertTrue(all(row["end_reason"] == "silence" for row in rows))
            size = 0
            for event in ws.sent:
                if event["type"] == "input_audio_buffer.append":
                    size += len(base64.b64decode(event["audio"]))
                elif event["type"] == "input_audio_buffer.commit":
                    self.assertGreater(size, 0)
                    self.assertLessEqual(size, 24000)
                    size = 0
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def feed_audio(self, receiver):
        # Wait for session setup before sending (setup deliberately clears backlog).
        await asyncio.sleep(0.01)
        while True:
            await receiver.queue.put(bytes(512))

    async def test_twenty_bounded_windows_and_transcripts(self):
        receiver = AudioReceiver("127.0.0.1")
        ws = FakeSocket()
        task = asyncio.create_task(self.feed_audio(receiver))
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                await asyncio.wait_for(run_session(ws, receiver, "test-model", 0.5), 10)
            self.assertEqual(len(output.getvalue().splitlines()), 20)
            size = 0
            for event in ws.sent:
                if event["type"] == "input_audio_buffer.append":
                    size += len(base64.b64decode(event["audio"]))
                elif event["type"] == "input_audio_buffer.commit":
                    self.assertEqual(size, 24000)
                    size = 0
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_errors_and_timeout_are_not_silent(self):
        ws = FakeSocket()
        ws.events.put_nowait({"type": "error", "error": "model unavailable"})
        with self.assertRaisesRegex(RuntimeError, "model unavailable"):
            await wait_event(ws, "session.updated")
        with self.assertRaises(TimeoutError):
            await wait_event(ws, "session.updated", 0.01)

    async def test_only_known_padding_warning_is_tolerated(self):
        ws = FakeSocket()
        ws.events.put_nowait({"type": "error", "error": {"message":
            "Specifying `session.turn_detection.prefix_padding_ms` is not supported. More detail."}})
        ws.events.put_nowait({"type": "session.updated", "session": {}})
        result = await wait_event(ws, "session.updated", allow_padding_warning=True)
        self.assertEqual(result["type"], "session.updated")
        ws.events.put_nowait({"type": "error", "error": {"message": "unexpected error"}})
        with self.assertRaisesRegex(RuntimeError, "unexpected error"):
            await wait_event(ws, "session.updated", allow_padding_warning=True)

    async def test_unexpected_vad_resets_manual_window(self):
        ws = FakeSocket()
        ws.events.put_nowait({"type": "input_audio_buffer.speech_started"})
        with self.assertRaisesRegex(RuntimeError, "Unexpected VAD"):
            await wait_event(ws, "conversation.item.input_audio_transcription.completed")


if __name__ == "__main__":
    unittest.main()
