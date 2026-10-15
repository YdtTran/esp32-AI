# Docker Piper to ESP32 speaker loop

Status: development prototype. [ADR 0010](../adr/0010-piper-docker-speaker-loop.md)
and [speaker-pcm v1](../../contracts/speaker-pcm/v1/specification.md) define the
choices and limits. ESP32 microphone -> Docker bridge/Speaches -> Docker Ollama
Qwen3 -> Docker Piper CPU -> HTTP PCM mailbox -> ESP32 shared I2S speaker.
Device firmware runs on ESP32, outside Docker.

## Start on this machine

From the repository root:

```powershell
./scripts/start-voice-assistant.ps1 -DryRun
./scripts/start-voice-assistant.ps1
```

Defaults: ESP32 192.168.1.16, PC 192.168.1.4, microphone UDP 5005, speaker HTTP
5006, localhost Ollama 11435. Pass `-DeviceIP`, `-ListenIP`, `-OllamaPort` after
address changes. Stop any host bridge using UDP 5005 first. The launcher builds
images before stopping only legacy Docker Speaches/Ollama, then starts the
unified `iot-voice` stack. It leaves native Ollama and unrelated containers alone.

For direct Compose commands set variables explicitly in each shell:

```powershell
$env:VOICE_LISTEN_IP = '192.168.1.4'
$env:VOICE_DEVICE_IP = '192.168.1.16'
$env:VOICE_OLLAMA_PORT = '11435'
$env:VOICE_UDP_SOURCE_IP = (docker network inspect iot-voice_default --format '{{(index .IPAM.Config 0).Gateway}}').Trim()
docker compose -f infrastructure/voice-compose.yaml config --quiet
docker compose -f infrastructure/voice-compose.yaml ps
docker compose -f infrastructure/voice-compose.yaml logs -f voice-loop piper
```

Service DNS addresses are explicit command arguments. Only microphone/speaker
ports publish on the chosen LAN interface; STT/Ollama host APIs stay on localhost
and Piper has no host port. Windows firewall must allow device UDP 5005/TCP 5006;
firewall rules are not changed automatically. Docker Desktop was verified to
forward microphone UDP from its bridge gateway, rather than the ESP32 source IP.
The Windows launcher detects it; `-UdpSourceIP` overrides the observed source.
The bridge rejects other sources, but the gateway filter cannot distinguish LAN
senders. Restrict firewall access to the device. Native Linux normally preserves
source IP; set `VOICE_UDP_SOURCE_IP` to the ESP32 address for that deployment.

## Models and persistence

External volumes `infrastructure_speaches-hf-hub-cache` and
`iot-ollama_ollama-models` preserve existing STT/LLM weights. Fresh machines must
follow the [STT](realtime-microphone-prototype.md) and
[LLM](local-llm-prototype.md) guides to create/populate them. Compose fails if
they are absent. The pinned Speaches image and English
Systran/faster-distil-whisper-small.en remain; the pinned Ollama 0.40.4 image uses
qwen3:1.7b. The launcher downloads no alternate STT/LLM.

Piper 1.8.0 loads en_US-ljspeech-medium on CPU. First startup downloads only the
selected ~64 MB ONNX and JSON configuration from a revision-pinned source,
verifies SHA256, and caches them in `iot-voice_piper-voices`. Its 22,050 Hz mono
speech is resampled to 16 kHz PCM16. The model card identifies public-domain LJ
Speech recordings; Piper runtime is GPL-3.0. Consult upstream notices before
redistribution. The tested CPU dependencies and Python base image are pinned.
Python 3.11 supplies the standard-library audioop resampler.

```powershell
docker compose -f infrastructure/voice-compose.yaml stop
```

`stop`/`down` retain weights; do not use `down --volumes` when retaining Piper.
Rollback: stop this stack, restart the original Speaches/Ollama services (Ollama
may need the existing 11435 override in its guide), and run the original host
orchestrator. Do not run old/unified services together: ports, caches and GPU
capacity are shared. No volume migration/deletion is needed.

## Firmware and playback

```powershell
. ./scripts/activate-idf.ps1 -UseInstallerProfile
idf.py --version
idf.py -C firmware build
# After identifying the device and releasing its serial monitor:
idf.py -C firmware -p COM_PORT flash monitor
```

Enter the same PC IPv4 at boot. `CONFIG_VOICE_SPEAKER_PORT` defaults to 5006.
Firmware checks HTTP status/content type/format and bounded Content-Length,
preserves odd network-read boundaries, and streams fixed buffers into shared
I2S TX. GPIOs and the existing 16 kHz/32-bit left-slot configuration stay the
same; physical amplifier channel selection must match
[wiring](../../firmware/docs/hardware/wiring.md). Old firmware must be reflashed
to poll/play replies.

Only successful completed LLM replies trigger TTS. Text/history survive TTS
failure. One active turn plus four pending finals; LLM/TTS process serially.
Piper rejects concurrent synthesis (503), caps text at 2000 characters and audio
at 60 s; client timeout is 30 s. Failures log without retry. The mailbox keeps
one reply for 30 s and replaces older uncollected speech; restart discards it.

Microphone capture drains I2S and uploads zero PCM during playback and its 300 ms
tail to maintain cadence and avoid self-transcription. Half-duplex: no barge-in
or echo cancellation. Interrupted HTTP/I2S can produce partial speech; discard
the remainder. Collection consumes audio without playback acknowledgement.
`TTS ready` means queued; firmware logs mean bytes written to I2S. Neither proves
audible speech. This unauthenticated HTTP/UDP prototype requires a trusted LAN
and firewall access limited to the device.

## Verification

```powershell
python scripts/validate.py
python -m unittest discover -s firmware/tests -v
docker compose --env-file infrastructure/voice.env.example -f infrastructure/voice-compose.yaml config --quiet
docker compose -f infrastructure/compose.yaml config --quiet
docker compose -f infrastructure/voice-compose.yaml run --rm --no-deps --entrypoint python -v "${PWD}/models/tests:/tests:ro" voice-loop /tests/live_speaker_smoke.py
```

The opt-in helper uses real Piper input, paced loopback UDP, real STT/Ollama,
and collects generated Piper speech via HTTP on isolated container ports
15025/15026. It does not consume the device mailbox or test physical Wi-Fi/I2S,
audibility or acoustics. Hardware acceptance needs a speaking/listening test
with updated firmware, including no self-transcription and reconnect recovery.

Sources: [Piper API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md),
[voice card](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/en/en_US/ljspeech/medium/MODEL_CARD).

## Executed evidence, 2026-10-14

`python scripts/validate.py` passed 35 model tests and 8 integration tests.
`python -m unittest discover -s firmware/tests -v` passed the fake-I2S harness,
including six startup/failure configurations, partial TX writes and playback
mute state. Both Compose `config --quiet` commands above passed. The launcher
passed `-DryRun` and actual startup after the Docker forwarding adjustment.

In every firmware shell, activated with
`. ./scripts/activate-idf.ps1 -UseInstallerProfile`, verified IDF_PATH,
IDF_TOOLS_PATH, IDF_PYTHON_ENV_PATH, `idf.py --version` (v6.1) and
`Get-Command xtensa-esp32s3-elf-gcc`. `idf.py -C firmware build` passed for
esp32s3; application 927424 bytes, 12% app partition free.
`idf.py -C firmware -p COM19 flash` passed and verified written hashes after the
user released serial monitors. Short temporary pyserial monitors supplied the
existing PC IPv4 prompt and observed boot/Wi-Fi at 192.168.1.16. No serial monitor
was terminated by the agent. Generated flash defaults remain 2 MB and boot warns
that the detected flash is 16 MB; memory configuration was not changed.

The first live Docker helper recognized “Allow, what is 2 plus 2?”, received LLM
“4.” and collected 15604 PCM bytes (0.488 s). Replay-to-audio collection was
63.686 s; LLM request 57.504 s. A repeat after the network-write fix recognized
“Hello, what is 2 plus 2?”, received “4.” and collected 16718 bytes (0.522 s).
Repeat replay-to-collection: 6.353 s; LLM request: 2.136 s. These are individual
cold/warm observations, not a latency distribution or physical speech latency.
One idle snapshot: Piper 163 MiB RAM, voice-loop 31 MiB, Speaches 741 MiB,
Ollama 2.347 GiB; observed LLM offload was 100% GPU. No stability claim.

Initial physical UDP did not produce transcripts because Docker Desktop forwarded
512-byte packets from 172.23.0.1, which the original device-IP filter rejected.
A temporary Compose UDP probe established that source; the final launcher detects
the network gateway and keeps an explicit source filter. After correction the
running stack processed physical microphone finals including “Thanks.” and
“Hello.”, produced English LLM replies and queued Piper speech. A sampled
established TCP connection to the speaker port was observed in the container.
Subsequent serial readback confirmed three complete HTTP buffers written to I2S:
88792, 89164 and 147492 bytes. This establishes the firmware write path, not
physical DMA timing or audibility.

All four final services remained healthy and running. Original Speaches/Ollama
containers are stopped; their model volumes are reused. Native Ollama and
unrelated Docker projects were left alone. Initial shell SDK activation removed
`rg` from PATH during inspection; reads continued through PowerShell. Windows
`Get-NetUDPEndpoint -LocalPort 5005` found no native socket for Docker's published
port; the container probe verified actual ingress. No build/flash or final
validation failure remains. Sustained load, measured DMA timing/noise, complete
physical DMA/audio measurements and listening were skipped; the user chose to test listening
later. Firewall rules were not changed.
