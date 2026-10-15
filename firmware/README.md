# Firmware specification and setup

## Expanded application capacity

[ADR 0013](../docs/adr/0013-expanded-flash-app-partition.md) selects the recorded
16 MiB physical flash and the custom `partitions.csv`. The factory application
has 0xff0000 bytes (15.9375 MiB), up from 1 MiB. NVS, PHY and application start
offsets are preserved. There are no OTA or filesystem partitions.

Fresh builds use `sdkconfig.defaults`. For an existing `sdkconfig`, use
`idf.py menuconfig` to select **Serial flasher config > Flash size > 16 MB**
and **Partition Table > Custom partition table CSV**, filename `partitions.csv`,
then run `idf.py build`. Defaults alone do not override existing configuration.
Apply with `idf.py -p <PORT> flash`, which includes the bootloader and partition
table; an application-only update does not apply the expanded layout. Do not
erase flash: a normal flash preserves the saved setup settings in NVS.

The original 2 MiB image-header and 1 MiB partition measurements below are
historical. This change does not enable PSRAM or increase runtime RAM.

On 2026-10-15, `idf.py -C firmware build` passed with a 1,020,464-byte app and
94% partition space free. The generated partition binary and 16MB flash arguments
were verified. This layout has not been flashed or tested on the device.
After restoring the orchestrator's optional speaker integration,
`python scripts/validate.py` passed all 37 model and 8 integration tests.

## Open setup network and animated status

The latest update follows
[ADR 0012](../docs/adr/0012-open-captive-setup-and-animated-status.md):

1. Join **VOICE-SETUP-XXXX** with **no password** when setup is active. If your
   phone remembers the old secured network, forget it once and join again.
2. The phone should open its captive sign-in page or show a **Sign in to Wi-Fi**
   notification. Tap that notification if needed. Choose your home Wi-Fi from
   the scanned dropdown, enter its password and PC LAN IPv4, then save. Refresh
   networks to scan again; **Hidden network...** enables manual entry only for
   a network that is not listed. Unsupported security modes are disabled in
   the list. The home password field is
   still required; only the ESP32 setup network's password was removed.
3. Settings persist and the board restarts. Existing settings from the previous
   firmware remain valid. Rejoin normal Wi-Fi. Boot Wi-Fi failure after 30
   seconds or serial `s` during the three-second boot window reopens setup.

The board advertises AP DNS and DHCP captive-portal discovery. HTTP connectivity
checks and unknown GET paths redirect to the setup URL. Actual automatic popup
behavior depends on the client OS, VPN/private DNS and cached network state;
HTTPS-only browsing cannot be intercepted. `http://192.168.4.1` remains a fallback
on LCD. Setup DNS/HTTP disappear during a normal configured session.

Scanning runs in a background task with at most 16 nearby network records,
deduplicated by name. Setup uses AP+STA radio mode for scanning, with cleared
station credentials and no station connection/reconnect. HTTP requests still
require the setup AP destination. No home-network bridge or Internet access is
provided by the setup AP.

The setup AP is intentionally open and uses HTTP: nearby clients can access
setup and observe submitted values while it is active. Existing saved passwords
are never returned to clients. NVS storage remains unencrypted. This supersedes
the initial password-protected setup described in the historical section below.

After setup, the LCD shows a breathing ring, blinking face and waveform. Amber
means waiting for Wi-Fi or the PC mailbox, teal means listening with a reachable
mailbox, and cyan with a larger mouth/wave means speaking (microphone muted).
The footer alternates IP/PC addresses with signal strength/uptime. Speaker
mailbox reachability is verified by its existing valid 204/PCM 200 responses;
it does not establish health of the rest of the inference stack. Failures clear
readiness; idle success expires after five seconds. Capture can continue while
the display waits for the mailbox.

The vector animation uses no image assets, graphics library or full-frame
buffer. Only the animation region is redrawn between text changes, retaining
the existing 7,680-byte stripe and waiting for DMA completion before reuse.

### Open captive setup validation (2026-10-14)

Commands from `firmware/`, using the unchanged existing SDK and verified paths:

```powershell
. ../scripts/activate-idf.ps1 -UseInstallerProfile
idf.py --version
python -m unittest discover -s tests -v
python ../scripts/validate.py
idf.py build
idf.py -p COM19 flash
node --check build/setup-script.js
# After joining the open setup Wi-Fi (does not save settings):
python tests/probe_captive_portal.py
```

Six host C harnesses cover audio, saved-config parsing, hostile/truncated DNS,
mapped IPv6 AP guarding, mailbox-ready classification and untrusted SSID JSON
escaping/capacity. Root validation also runs 35 model and 8 integration checks.
All 49 checks passed. The final esp32s3 v6.1 build and COM19 flash passed with
verified hashes: 1,020,464-byte application, 28,112 bytes (3%) free in the existing
1 MiB app partition. Existing SDK private-include/Git metadata warnings and the
nearly-full app warning remain. No partition changes, packages or SDK upgrades.
Native animation frames were rendered from the actual C scene code to the
ignored `build/display-scene-preview.png` for visual review.

After flashing the dropdown update, the real device probe again passed DNS,
Windows/Android/Apple redirects, page/captive API responses and invalid-write
rejection. Its asynchronous scan returned **9 nearby networks**. Headless Edge
loaded the actual page from the board, executed its JavaScript and populated
all 9 dropdown options; `node --check` also passed. Browser output/screenshot
are ignored at `build/setup-dropdown-dom.html` and `build/setup-dropdown.png`.
The probe submitted no real settings. The diagnostic Wi-Fi switch restored the
original profile with Internet access; the serial port is released.

The first Windows connection test resolved DNS correctly but every HTTP request
returned 403. The v6.1 server uses IPv4-mapped IPv6 socket addresses; the original
IPv4-sized destination guard misread them. The new address guard retains AP-only
destination checking while accepting both representations. A real PC-on-AP probe
then passed Windows/Android/Apple HTTP redirects, landing-page fields, captive
JSON, foreign Host/Origin rejection and invalid-form rejection without saving.
Windows NCSI event 4038 reported **Hotspot detected**, with event 4042 reason
`ActiveHttpProbeFailedHotspotDetected`. The user confirmed the setup page opened.

During diagnostics, attempts from normal home Wi-Fi timed out as expected
because the setup AP is isolated. Adding a duplicate current-user Windows Wi-Fi
profile was rejected because the existing profile belonged to another scope;
the existing open profile was reused. A first restore command included trailing
whitespace in the captured profile name; the corrected/trimmed command restored
normal Wi-Fi and Internet. The first reusable device-probe run also exposed a
Python helper/module name collision; it was renamed and the full probe passed.
No user Wi-Fi policy, DNS setting or saved home password was changed.

Real settings submission, NVS save/reboot, the 30-second bad-password recovery
and physical animation synchronized with the live voice stack remain unverified
for this update. Mailbox classification and the animation were checked on the
host; this does not establish audible output or full inference service health.

## Initial LCD status and first-time setup (historical)

The user confirmed the 240x240 ST7789 and documented wiring on 2026-10-14.
Firmware now displays setup instructions, Wi-Fi state/device IP, saved PC IP,
RSSI, uptime and listening/speaking status (microphone muted during playback).
Listening indicates capture mode, not successful PC/STT service health.
See [ADR 0011](../docs/adr/0011-lcd-and-web-setup.md). The serial provisioning,
compiled credential and unused display descriptions below are historical.
The private local credentials header is no longer compiled into firmware.

1. On first boot, join `VOICE-SETUP-XXXX` from a phone or PC. Its generated
   password appears on the LCD and serial console. Keep the Wi-Fi connection
   if your phone warns that it has no Internet.
2. Open `http://192.168.4.1` manually. Enter your 2.4 GHz WPA2/WPA3 personal SSID,
   password (8-63 printable ASCII characters, or a 64-digit hex PSK), and the
   PC's LAN IPv4 address. SSIDs allow 1-32 UTF-8 bytes. Open/enterprise Wi-Fi,
   hostnames and IPv6 are unsupported in this prototype.
3. Save. Settings persist in NVS and the board restarts. Rejoin your normal
   Wi-Fi; the LCD shows the device and PC addresses. Existing PC UDP 5005 and
   HTTP 5006 services are unchanged. Reserve the PC address in your router.
4. If boot cannot obtain Wi-Fi IPv4 within 30 seconds, setup opens again with
   a fresh AP password. To change settings while Wi-Fi still works, open the
   serial monitor, reset the board and send `s` within the three-second boot
   window. During normal operation, Wi-Fi outages trigger reconnection; reboot
   to activate setup recovery. No factory-reset GPIO has been assigned.

Setup HTTP accepts only requests addressed to the setup AP. The AP/server is
absent during a normal configured session. There is no captive portal redirect.
Saved passwords are never returned by the page or printed. They remain plaintext
in NVS: this is local development provisioning, not production credential storage.
NVS erase removes settings; a normal flash preserves them. The existing startup
recovery may erase NVS if its format is incompatible or it has no free pages.

The LCD uses existing GPIO8-13, native v6.1 `esp_lcd`, SPI2 mode 0 at 10 MHz and
an active-high backlight. It allocates one 7,680-byte DMA stripe, waiting for
completion before reuse. No graphics package or GPIO reassignment. In
`idf.py menuconfig`, **ST7789 240x240 display** exposes X/Y offsets (initially
zero) and inversion (initially on). Verify alignment/colors on the actual
panel before adjusting these values; some 240x240 breakouts need a Y offset.

### Executed validation (2026-10-14)

From `firmware/`, with the existing SDK (all three documented paths and v6.1
compiler availability verified per shell):

```powershell
. ../scripts/activate-idf.ps1 -UseInstallerProfile
idf.py --version
python -m unittest discover -s tests -v
python ../scripts/validate.py
python -m esptool --port COM19 --chip esp32s3 chip-id
idf.py build
idf.py -p COM19 flash
git diff --check
```

Both firmware C regression harnesses passed, including the strict setup parser
with encoded symbols, maximum lengths, malformed/duplicate/unknown fields,
invalid PC IPv4 and rejection without partial config updates. Root validation
passed its 35 model and 8 integration tests (45 tests including firmware).
The esp32s3 v6.1 build and COM19 flash passed with verified hashes. The application
is 1,000,736 bytes, leaving 47,840 bytes (5%) in the existing 1 MiB app partition.
No memory or partition settings were changed. Existing SDK warnings about
private Wi-Fi includes, missing Git HEAD and the nearly-full app remain.

Initial chip identification failed because COM19 was busy. The user closed
the monitor and retry identified ESP32-S3 revision v0.2 with 8 MiB embedded
PSRAM. The boot log reports a 16 MiB physical flash but uses the existing 2 MiB
image header; this observation does not accept new flash/PSRAM settings.

A bounded Python/pyserial reset-and-read on COM19 confirmed setup AP
`VOICE-SETUP-544D`, DHCP at 192.168.4.1 and the setup URL. An initial boot
revealed legacy SDK station credentials were loaded before RAM storage was
selected. The final implementation explicitly replaces that config and runs
AP-only during setup. A final nine-second boot sample confirmed AP-only mode,
no legacy station association, panic, stack canary failure or LCD transfer error.
The redacted local log is ignored at `build/lcd-setup-boot.log`; COM19 is released.
The user confirmed that the backlight is on and text is readable, fully visible
and correctly aligned. No offset/inversion adjustment was necessary.

Browser submission, saved-config reboot/reconnect, bad-password 30-second
recovery, mobile browser layout and the complete audio/service loop have not
been tested for this update; they require connecting a client and provisioning
real network settings. No electrical measurements were performed. Host tests
and boot logs do not establish those behaviors.

## Piper speaker loop

Firmware now polls the console-provisioned PC IPv4 on HTTP 5006 for bounded
16 kHz PCM16 replies and writes them to shared I2S TX. Microphone upload sends
silence during playback and its 300 ms tail. See the
[Docker setup/build guide](../docs/specs/speaker-loop.md),
[speaker contract](../contracts/speaker-pcm/v1/specification.md) and
[ADR 0010](../docs/adr/0010-piper-docker-speaker-loop.md). GPIOs are unchanged.
Updated firmware needs flashing before playback is available on the device.
Earlier silent-output descriptions below record historical behavior.

Verified on 2026-10-14: v6.1 esp32s3 build and COM19 flash passed (927424-byte
application, 12% partition free). Wi-Fi boot obtained 192.168.1.16 and physical
microphone transcripts reached the Docker stack after source-forwarding setup.
Serial logs confirmed return PCM buffers of 88792, 89164 and 147492 bytes written
to I2S.
Audible playback and acoustic feedback checks remain unverified; the user will
test listening later. See the speaker guide's executed evidence for commands,
service integration measurements and limitations.

## Microphone to Speaches prototype

`main/app_main.c` composes NVS, shared audio and `voice_stream_start()`.
The reusable `voice_stream` component reads development Wi-Fi/PC settings from
the serial console at each boot, reconnects Wi-Fi and sends 16 kHz PCM16 UDP.
Wi-Fi credentials can be compiled from the ignored local header
`components/voice_stream/include/wifi_credentials.local.h`, using string macros
`VOICE_WIFI_SSID` and `VOICE_WIFI_PASSWORD`. This machine uses that option at the
user's request; boot prompts only for the bridge PC IPv4. Without the header,
SSID/password are entered through the console. Credentials are not logged and
Wi-Fi uses RAM storage. Rebuild and flash after changing the local header;
compiled firmware contains the credentials and must remain private.
See [ADR 0008](../docs/adr/0008-local-compiled-wifi.md).
Verified on 2026-10-14: after sourcing `scripts/activate-idf.ps1
-UseInstallerProfile`, `idf.py -C firmware build` passed for esp32s3 with ESP-IDF
v6.1 (806,848-byte application, 23% app partition free).
`python -m unittest discover -s firmware/tests -v` and
`python scripts/validate.py` passed (23 host tests). Flashing and physical Wi-Fi
association were skipped because the board/serial port was not identified.
GPIOs and the shared-clock silent speaker implementation remain unchanged.
Follow the [complete prototype guide](../docs/specs/realtime-microphone-prototype.md)
for PC bridge setup, build/flash steps, test procedures and limitations.

The earlier development descriptions below are historical; app_main now runs
the prototype composition rather than a foundation-only log or hardcoded stream.

## Shared-clock audio development update

The current audio implementation supersedes the original stub description
below. `audio_bus` owns paired I2S TX/RX channels; `audio_input` reads mono
left-slot 32-bit microphone words and `audio_output_init()` starts silent output.
Both initialization calls return esp_err_t and share an idempotent initializer
called serially from app_main before Wi-Fi startup. There is no playback API.
`CONFIG_AUDIO_BUS_SAMPLE_RATE=16000` preserves the existing development rate.
See [ADR 0004](../docs/adr/0004-shared-i2s-silent-output.md).

The driver supplies zero-filled TX DMA buffers and clears consumed buffers,
driving amplifier DIN rather than leaving it floating while microphone clocks
run. This targets a suspected cause of idle noise. No SD/EN GPIO is assigned;
the amplifier is not shut down by firmware. Noise before audio initialization,
power/ground noise and breakout compatibility require hardware investigation.
Pins remain proposed and unchanged; no flashing or hardware verification has
been performed for this fix.

Validation commands from the repository root, in the existing activated SDK:

```powershell
. .\scripts\activate-idf.ps1 -UseInstallerProfile
idf.py -C firmware build
python -m unittest discover -s firmware/tests -v
python scripts/validate.py
```

On 2026-10-14, `idf.py build` from firmware passed for esp32s3 with ESP-IDF
v6.1 on retry. The first attempt compiled the audio components but failed at
the final link because the generated project_elf_src_esp32s3.c.obj was missing;
the retry regenerated it. Existing SDK component-validation warnings for Wi-Fi
private include directories and unavailable Git HEAD metadata remain.
Host regression checks passed for paired startup, idempotent initialization,
microphone reads and all five initialization failure points with retry.
`python scripts/validate.py` passed. Host tests use a fake I2S driver and do not
test actual DMA output. Flashing, noise measurements and hardware tests were
skipped because no device was tested; compilation does not establish silence.

The original foundation description follows for setup history.

The application is adapted from the installed ESP-IDF v6.1
`examples/get-started/hello_world` CMake structure. Only source/CMake structure
is retained; chip inspection, example test dependencies and example build output
are excluded. `app_main.c` logs a foundation message and returns. No drivers,
networking or runtime provisioning exist yet. `board`, `audio_input`,
`audio_output` and `display` are raw ESP-IDF-generated stubs; only
[board_pins.h](components/board/include/board_pins.h) adds proposed hardware
definitions. See the [pinout](docs/hardware/pinout.md) and
[wiring](docs/hardware/wiring.md); no peripheral functionality is implemented.

`main/` owns application composition. `components/<snake_case_name>/` will own
reusable code, with public headers in `include/`. Read `components/README.md`
before creating components.

## Windows PowerShell

Source into the current session, including inside every independent agent shell:

```powershell
. .\scripts\activate-idf.ps1
idf.py --version
idf.py --help
```

Confirmed development paths:

| Variable | Path |
| --- | --- |
| `IDF_PATH` | `E:\esp\.espressif\v6.1\esp-idf` |
| `IDF_TOOLS_PATH` | `C:\Espressif\tools` |
| `IDF_PYTHON_ENV_PATH` | `C:\Espressif\tools\python\v6.1\venv` |

The default script calls the SDK's `export.ps1` and fails with an actionable
error if activation fails. The installed tools currently have a flat directory
layout incompatible with that exporter. The existing installer profile activates
these same tools successfully:

```powershell
. .\scripts\activate-idf.ps1 -UseInstallerProfile
```

This selects `C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1`, not
another SDK or Python environment. The script validates the SDK version and
tool commands. It never installs or changes the system installation.

## Linux

Use an already-installed v6.1 SDK and its environment:

```bash
source "$IDF_PATH/export.sh"
idf.py --version
idf.py --help
```

Windows paths are not portable to Linux; do not create another environment on
the confirmed Windows machine. Linux provisioning is outside this bootstrap.

## Target and reproducible build

The user confirmed the ESP32-S3 N16R8 module on 2026-10-13. The accepted build
target is `esp32s3`, recorded in `sdkconfig.defaults` and
[ADR 0003](../docs/adr/0003-esp32s3-build-target.md). Exact carrier-board details,
flash/PSRAM operating settings and electrical compatibility remain unverified;
the [pin scaffold](../docs/adr/0002-proposed-esp32-s3-hardware-scaffold.md)
remains proposed. This foundation uses ESP-IDF's generated memory/partition
defaults; they are not accepted production hardware settings. `sdkconfig` and
build directories remain generated and ignored.

The first `set-target` and build passed on 2026-10-13 with ESP-IDF v6.1.
`build/voice_device.bin` is 150,000 bytes, leaving 86% of the default 1 MB app
partition free. Generated settings currently use 2 MB flash and disable PSRAM;
the full N16R8 memory configuration is still pending review. `MINIMAL_BUILD`
compiles `main` and its dependencies; unused peripheral stubs are excluded.
Git version discovery warned about missing `HEAD` in the uncommitted repository;
the build succeeded. Flashing and hardware tests have not run.

From `firmware/`, in an activated shell:

```text
idf.py set-target esp32s3
idf.py build
```

Changing targets may discard
generated configuration; preserve intentional settings in reviewed defaults.
Use `idf.py save-defconfig` after deliberate menuconfig changes and review its
output. Build and hardware results must be recorded separately.
