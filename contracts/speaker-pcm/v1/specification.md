# Speaker PCM 1.0.0

Producer: models. Consumer: firmware. Development prototype, ADR 0010.

Firmware polls `GET http://<provisioned-PC-IPv4>:5006/audio` every 500 ms when
connected to Wi-Fi and idle. HTTP 204 means no pending audio; HTTP 200 carries
1..960000 signed little-endian PCM16 mono samples at 16000 samples/second.
Content-Length must be positive, even and no more than 1920000 bytes (60 s).
`X-Audio-Format: pcm-s16le-16000-mono` and
`Content-Type: application/octet-stream` are required. No WAV/header bytes.
No transfer chunking, redirect or compression. Convert each signed sample to a
left-slot 32-bit I2S word by multiplication by 65536; clocks/pins stay unchanged.

Valid hex: `0000ff7f0080` (zero, maximum positive, minimum negative).
Invalid: empty 200 body, `00`, missing/wrong format, odd length, over 1920000
bytes, compressed/chunked response, or truncated download. Firmware retains
at most 1024 PCM bytes plus conversion buffers; an odd network read preserves
its trailing byte until the next read. Partial download can produce partial
speech before failure; abandon the remainder without replay or automatic retry.
HTTP read inactivity timeout is 2 s. After completion/failure, drain TX and mute
microphone speech for 300 ms before returning to capture. The existing capture
task continues draining I2S and sends zero PCM at the normal UDP cadence during
playback and the tail; this keeps STT endpointing alive without speaker echo.

The mailbox holds one reply, replacing uncollected audio with newer audio and
expiring after 30 s. Collection consumes a reply even if delivery fails. No
ordering IDs, persistence, playback acknowledgement or multi-device routing.
HTTP is reliable within a connection but does not guarantee audio reached I2S.
New polling requests after failure retrieve only a new pending reply. Shutdown
discards pending replies. HTTP health is `/health`, with no audio consumption.

Trusted LAN only: no encryption/authentication. Bind host ports to the chosen
PC LAN interface; restrict firewall access to the ESP32. Internal Piper HTTP
`POST /synthesize` accepts JSON `{"text":"Hello."}` (1..2000 characters, 16 KiB
request cap), produces the same PCM format, and rejects concurrent synthesis
with 503. Piper is not published on the host. This internal API belongs to models.

Breaking rate/encoding/delivery changes need a new major and coordinated
migration. Test Python PCM production against firmware conversion and framing.
