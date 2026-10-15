# Microphone PCM 1.0.1

Producer: firmware. Consumer: models. Development prototype, ADR 0006.

UDP packets carry 1–256 mono samples, signed little-endian PCM16, exactly 16000
samples/second: 2–512 bytes, even length. No header or acknowledgements.
Destination: user-provisioned PC IPv4, port 5005 (configurable on both ends).
Convert left-slot I2S words by arithmetic right-shift of 16 bits.
Valid hex: `0000ff7f0080` (zero, maximum positive, minimum negative).
Invalid: empty, `00`, or 514 bytes. Full packets cover 16 ms.

Use arrival order; loss, duplication and reordering are undetectable. No replay.
Reject invalid lengths/unexpected source IPs. Accept changed source ports after
device socket reconnects. Queue at most about one second. On overflow discard queued audio
and reconnect inference to prevent stale captions. Five seconds without audio
reconnects; server failures retry after two seconds. Shutdown may discard a
partial window. Only one device per process.

Docker Desktop published UDP rewrites the source to its bridge gateway. The
Docker launcher explicitly configures that observed forwarding source instead
of the original ESP32 address. Native host/Linux deployments normally configure
the original device IP. This does not change packet bytes. The gateway filter
cannot distinguish individual LAN senders; restrict published UDP/firewall
access to the intended device. Source filtering is not authentication.

Trusted LAN only: no encryption, authentication or integrity protection.
Bridge requires device IP and explicitly selected listen interface (loopback
default). Firewall changes are operator-controlled; Speaches stays localhost.
Print transcripts as stdout JSON lines without credentials.

This formalizes existing packet bytes. Framing or rate changes require a new
major version and coordinated migration. Test a C producer against Python decode.
