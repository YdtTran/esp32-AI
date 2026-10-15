"""Replay a 16 kHz mono PCM16 WAV through the real device UDP contract."""
import argparse
import socket
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1 or not 1024 <= args.port <= 65535:
        parser.error("positive repeat and port 1024..65535 required")
    with wave.open(args.wav, "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
            parser.error("WAV must be uncompressed 16 kHz mono PCM16")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            for _ in range(args.repeat):
                audio.rewind()
                deadline = time.monotonic()
                while packet := audio.readframes(256):
                    sock.sendto(packet, (args.host, args.port))
                    deadline += len(packet) / 32000
                    time.sleep(max(0, deadline - time.monotonic()))
                # Finish the inference window and separate repeated utterances.
                for _ in range(188):
                    sock.sendto(bytes(512), (args.host, args.port))
                    deadline += 0.016
                    time.sleep(max(0, deadline - time.monotonic()))


if __name__ == "__main__":
    main()
