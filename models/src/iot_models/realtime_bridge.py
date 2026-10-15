"""Bounded trusted-LAN microphone UDP to the pinned Speaches realtime API."""
from __future__ import annotations

import argparse
import asyncio
import base64
import ipaddress
import json
import logging
import math
import os
import struct
from urllib.parse import urlencode

LOG = logging.getLogger(__name__)
MODEL = "Systran/faster-distil-whisper-small.en"


class SpeechBuffer:
    """PCM16 energy gate with pre-roll, silence endpoint and a hard byte cap."""
    def __init__(self, threshold=0.015, silence_seconds=0.6, max_seconds=10):
        if (not 0 < threshold <= 1 or not 0.1 <= silence_seconds <= max_seconds
                or not 0.5 <= max_seconds <= 10):
            raise ValueError("threshold: (0,1]; silence: 0.1..max; max: 0.5..10 seconds")
        self.threshold = threshold
        self.silence_limit = int(silence_seconds * 16000) * 2
        self.limit = int(max_seconds * 16000) * 2
        self.pre_roll = bytearray()
        self.audio = bytearray()
        self.voiced = 0
        self.silent = 0

    def feed(self, packet):
        samples = decode_packet(packet)
        rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
        speech = rms >= self.threshold
        if not self.audio and not speech:
            self.pre_roll.extend(packet)
            del self.pre_roll[:-6400]  # 200 ms, bounded even during hours of silence.
            return []
        completed = []
        while packet:
            if not self.audio:
                self.audio.extend(self.pre_roll)
                self.pre_roll.clear()
            take = min(len(packet), self.limit - len(self.audio))
            self.audio.extend(packet[:take])
            packet = packet[take:]
            if speech:
                self.voiced += take
                self.silent = 0
            else:
                self.silent += take
            if len(self.audio) == self.limit or self.silent >= self.silence_limit:
                reason = "max_duration" if len(self.audio) == self.limit else "silence"
                if self.voiced >= 5120:  # Reject bursts with less than 160 ms of speech.
                    completed.append((bytes(self.audio), reason))
                self.audio.clear()
                self.voiced = self.silent = 0
                if not speech:
                    self.pre_roll.extend(packet)
                    del self.pre_roll[:-6400]
                    break
        return completed


def decode_packet(packet: bytes) -> tuple[int, ...]:
    if not 2 <= len(packet) <= 512 or len(packet) % 2:
        raise ValueError("microphone-pcm v1 requires 2..512 even bytes")
    return struct.unpack(f"<{len(packet) // 2}h", packet)


class Resampler:
    """Continuous 3:2 linear interpolation, retaining boundary samples."""
    def __init__(self):
        self.pending: list[int] = []

    def feed(self, packet: bytes) -> bytes:
        self.pending.extend(decode_packet(packet))
        output = []
        consumed = 0
        while consumed + 2 < len(self.pending):
            a, b, c = self.pending[consumed:consumed + 3]
            output.extend((a, (a + 2 * b) // 3, (2 * b + c) // 3))
            consumed += 2
        del self.pending[:consumed]
        return struct.pack(f"<{len(output)}h", *output)


class AudioReceiver(asyncio.DatagramProtocol):
    def __init__(self, device_ip: str):
        self.device_ip = device_ip
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=63)
        self.generation = 0
        self.accepted = 0
        self.rejected = 0
        self.overflows = 0

    def clear(self):
        while not self.queue.empty():
            self.queue.get_nowait()

    def datagram_received(self, data, addr):
        try:
            if addr[0] != self.device_ip:
                raise ValueError("unexpected source")
            decode_packet(data)
        except ValueError:
            self.rejected += 1
            return
        if self.queue.full():
            self.clear()
            self.generation += 1
            self.overflows += 1
            LOG.warning("Audio queue overflow; resetting session")
        self.queue.put_nowait(data)
        self.accepted += 1

    def error_received(self, exc):
        LOG.warning("UDP receive error: %s", exc)


def session_update(model: str) -> dict:
    # The installed server rejects input_audio_format updates and ignores intent.
    return {"type": "session.update", "session": {
        "modalities": ["text"],
        "input_audio_transcription": {"model": model, "language": "en"},
        "turn_detection": {"type": "server_vad", "threshold": 1.0,
            "prefix_padding_ms": 0, "silence_duration_ms": 550, "create_response": False},
    }}


async def wait_event(ws, expected: str, timeout: float = 60, allow_padding_warning=False) -> dict:
    async with asyncio.timeout(timeout):
        while True:
            event = json.loads(await ws.recv())
            kind = event.get("type")
            if (allow_padding_warning and kind == "error" and
                event.get("error", {}).get("message", "").startswith(
                    "Specifying `session.turn_detection.prefix_padding_ms` is not supported.")):
                # This installed server still applies other fields and returns
                # session.updated. Verify the resulting configuration below.
                continue
            if kind in {"input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"}:
                raise RuntimeError("Unexpected VAD activity in manual-window session")
            if kind in {"error", "conversation.item.input_audio_transcription.failed"}:
                raise RuntimeError(str(event.get("error", event)))
            if kind == expected:
                return event


async def run_session(ws, receiver: AudioReceiver, model: str, window_seconds=None,
                      speech_threshold=0.015, silence_seconds=0.6, max_audio_seconds=10):
    await wait_event(ws, "session.created", 10)
    await ws.send(json.dumps(session_update(model)))
    updated = await wait_event(ws, "session.updated", 10, allow_padding_warning=True)
    session = updated["session"]
    vad = session.get("turn_detection", {})
    if vad.get("threshold") != 1.0 or vad.get("create_response") is not False or vad.get("prefix_padding_ms") != 0:
        raise RuntimeError("Server did not accept manual-window VAD settings")
    if session.get("input_audio_transcription", {}).get("model") != model:
        raise RuntimeError("Server did not accept transcription model")
    receiver.clear()
    generation = receiver.generation
    resampler = Resampler()
    limit = int(window_seconds * 24000) * 2 if window_seconds is not None else 0
    speech_buffer = SpeechBuffer(speech_threshold, silence_seconds, max_audio_seconds)
    pending = bytearray()
    for _ in range(20):
        reason = "fixed_window"
        duration = window_seconds
        if window_seconds is None:
            while True:
                async with asyncio.timeout(5):
                    packet = await receiver.queue.get()
                if receiver.generation != generation:
                    raise RuntimeError("Audio overflow: discarded stale utterance")
                segments = speech_buffer.feed(packet)
                if segments:
                    audio, reason = segments[0]
                    duration = len(audio) / 32000
                    # Each utterance is independent; never interpolate across silence gaps.
                    utterance_resampler = Resampler()
                    pending = bytearray()
                    for offset in range(0, len(audio), 512):
                        pending.extend(utterance_resampler.feed(audio[offset:offset + 512]))
                    break
            limit = len(pending)
        sent = 0
        while sent < limit:
            if not pending:
                async with asyncio.timeout(5):
                    packet = await receiver.queue.get()
                if receiver.generation != generation:
                    raise RuntimeError("Audio overflow: discarded stale window")
                pending.extend(resampler.feed(packet))
            take = min(len(pending), limit - sent, 24000)
            if not take:
                continue
            await ws.send(json.dumps({"type": "input_audio_buffer.append",
                "audio": base64.b64encode(pending[:take]).decode("ascii")}))
            del pending[:take]
            sent += take
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        event = await wait_event(ws, "conversation.item.input_audio_transcription.completed")
        print(json.dumps({"type": "transcript", "item_id": event["item_id"],
            "text": event["transcript"], "window_seconds": duration,
            "end_reason": reason}), flush=True)
        if receiver.generation != generation:
            raise RuntimeError("Audio overflow while transcribing; previous result preserved")


async def serve(args):
    from websockets.asyncio.client import connect
    from websockets.exceptions import WebSocketException
    receiver = AudioReceiver(args.device_ip)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(lambda: receiver,
        local_addr=(args.listen, args.port))
    token = os.environ.get("SPEACHES_API_KEY")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    url = args.server.rstrip("/") + "/v1/realtime?" + urlencode({"model": args.model})
    LOG.info("Listening UDP %s:%d; accepting %s; model %s",
             args.listen, args.port, args.device_ip, args.model)
    try:
        while True:
            receiver.clear()
            try:
                async with connect(url, additional_headers=headers, open_timeout=10,
                                   max_size=1024 * 1024, max_queue=16) as ws:
                    await run_session(ws, receiver, args.model, args.window_seconds,
                                      args.speech_threshold, args.silence_seconds,
                                      args.max_audio_seconds)
                LOG.info("Recycling bounded session")
            except (OSError, TimeoutError, RuntimeError, ValueError, WebSocketException) as exc:
                LOG.warning("Session reset: %s", exc)
                await asyncio.sleep(2)
    finally:
        transport.close()
        LOG.info("UDP accepted=%d rejected=%d overflows=%d",
                 receiver.accepted, receiver.rejected, receiver.overflows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1", type=ipv4)
    parser.add_argument("--device-ip", required=True, type=ipv4)
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--server", default="ws://127.0.0.1:8000")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--speech-threshold", type=float, default=0.015,
                        help="Normalized PCM RMS energy threshold (default: 0.015)")
    parser.add_argument("--silence-seconds", type=float, default=0.6,
                        help="End an utterance after this much quiet (default: 0.6)")
    parser.add_argument("--max-audio-seconds", type=float, default=10,
                        help="Hard per-utterance cap, 0.5..10 seconds (default: 10)")
    parser.add_argument("--window-seconds", type=float,
                        help="Optional legacy fixed windows; bypass speech detection")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or (args.window_seconds is not None and
                                         not 0.5 <= args.window_seconds <= 10):
        parser.error("port must be 1024..65535; window must be 0.5..10 seconds")
    try:
        SpeechBuffer(args.speech_threshold, args.silence_seconds, args.max_audio_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.server.startswith(("ws://", "wss://")):
        parser.error("server must use ws:// or wss://")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


def ipv4(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


if __name__ == "__main__":
    main()
