import socket
import wave

PORT = 5005
SAMPLE_RATE = 16000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(0.5)  # Wait at most 0.5 seconds per receive

print(f"Listening on UDP {PORT}. Press Ctrl+C to stop.")

try:
    with wave.open("recording.wav", "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)

        while True:
            try:
                data, addr = sock.recvfrom(2048)
                wav.writeframesraw(data)

            except socket.timeout:
                continue

except KeyboardInterrupt:
    print("\nRecording stopped. WAV file saved.")

finally:
    sock.close()