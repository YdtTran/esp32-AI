# Reusable firmware components

Open captive setup and animation
([ADR 0012](../../docs/adr/0012-open-captive-setup-and-animated-status.md)):
`voice_stream` also owns the bounded captive DNS parser/socket task and HTTP
probe redirects. `display_setup(ssid)` shows an open network; no AP password is
generated. `display_server_update(reachable)` receives valid speaker mailbox
poll/download outcomes. `display` owns the vector face/ring/wave animation and
readiness timeout without importing voice_stream or changing audio ownership.
The setup scan worker owns its bounded SDK scan/cache and `/networks` JSON;
setup AP+STA mode permits scanning while cleared station settings and guarded
callbacks prevent joining another network. SSID selection keeps the existing
form/NVS interface. The AP address guard supports mapped IPv6 HTTP sockets.

Current LCD/setup interfaces ([ADR 0011](../../docs/adr/0011-lcd-and-web-setup.md)):
`display` owns ST7789 SPI2/backlight and its render task; `display_init`,
`display_status` and `display_setup` copy status for asynchronous rendering.
`voice_stream` owns `voice_setup_connect`, the setup-only AP/HTTP server, strict
form validation and versioned NVS settings. It connects Wi-Fi before starting
UDP capture upload and speaker polling. It no longer consumes the local
credentials header. Historical serial/stub descriptions below are superseded.

Speaker loop additions (ADR 0010): `audio_bus_write` owns bounded shared TX;
`audio_output` exposes begin/write/end/active for one playback producer and
capture muting; `voice_stream` now also owns HTTP polling and PCM framing through
`voice_playback_start`. No new I2S channel or GPIO is allocated. The
[speaker contract](../../contracts/speaker-pcm/v1/specification.md) is authoritative.
Earlier no-playback descriptions below record the previous implementation.

`voice_stream` owns serial prototype configuration, Wi-Fi connection/reconnect
and microphone PCM16 UDP. Public `voice_stream_start()` starts its task once
after NVS and audio initialization. `voice_pcm_encode()` implements the
[microphone-pcm v1 contract](../../contracts/microphone-pcm/v1/specification.md).
It consumes audio_input; it does not allocate I2S channels or change GPIOs.

Current audio ownership supersedes the original scaffold descriptions below:

| Component | Responsibility | Public interface |
| --- | --- | --- |
| `audio_bus` | Own paired I2S RX/TX, shared clocks and continuous silent TX | `audio_bus_init`, `audio_bus_read` |
| `audio_input` | Microphone capture facade | `audio_input_init`, `audio_input_read` |
| `audio_output` | Start the shared bus with silent speaker output | `audio_output_init`, returning esp_err_t |

Initialize serially from app_main. Neither facade independently allocates I2S
channels. No playback producer or wire contract is introduced. See
[ADR 0004](../../docs/adr/0004-shared-i2s-silent-output.md). The board component
now exports its esp_hal_gpio dependency for consumers of board_pins.h.

The installed v6.1 CLI generated the following raw components. Sources, CMake
files and generated headers remain unchanged; they contain no driver behavior.

| Component | Intended responsibility | Current public interface |
| --- | --- | --- |
| `board` | Central GPIO assignments | [board_pins.h](board/include/board_pins.h), proposed constants only |
| `audio_input` | Future INMP441 microphone input | Generated header only; no accepted functional API |
| `audio_output` | Future MAX98357A speaker output | Generated header only; no accepted functional API |
| `display` | Future ST7789 display output | Generated header only; no accepted functional API |

No cross-module contract applies yet. See the proposed
[pinout](../docs/hardware/pinout.md) and [wiring](../docs/hardware/wiring.md).
`board_pins.h` includes the SDK's `soc/gpio_num.h` for `GPIO_NUM_x` constants.
When a future component consumes it, declare the corresponding public
`esp_hal_gpio` dependency in `board/CMakeLists.txt`; the raw scaffold does not
yet consume the header. The generated `func` declarations are template
placeholders, not accepted APIs; review them before implementing components.

The project retains `MINIMAL_BUILD ON`; unused stubs are not automatically
included in the application. For configure-only scaffold validation, explicitly
select `main`, `board`, `audio_input`, `audio_output` and `display` with the CMake
`COMPONENTS` variable. This does not require changing application composition.

Specify responsibility, public headers and contract dependencies before adding
further components. The installed v6.1 CLI supports `create-component`.

After activation and interface review, run from `firmware/`:

```text
idf.py create-component --help
idf.py create-component -C components <defined_component_name>
```

Verify the generated CMake and source files before adapting them. Do not create
`audio_capture` until audio hardware, ownership and its public interface are
defined. Avoid generating speculative component directories.
