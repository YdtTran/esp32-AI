# 0011: LCD status and first-time web setup

- Date: 2026-10-14
- Status: Accepted (development implementation; physical validation pending)
- Owners: firmware

[ADR 0012](0012-open-captive-setup-and-animated-status.md) supersedes this
record's password-protected/manual-only setup and static normal-status screen
at the user's request. NVS configuration, hardware and audio semantics remain.

## Context

The user requests useful status on the connected LCD and first-time setup for
Wi-Fi and the PC address. The user confirms a 240x240 ST7789 and that the recorded
hardware information, including GPIO13 backlight wiring, is correct. This is
user confirmation, not schematic, electrical or visual measurement evidence.

## Decision

Use the existing LCD pin map with the native v6.1 ST7789 driver, SPI2 mode 0 at
10 MHz, RGB565, active-high GPIO13 backlight and a small built-in text renderer.
No extra graphics dependency or full-frame buffer. Transfer one 16-row DMA
stripe at a time and wait for completion before reusing its memory. Show setup
SSID/password/URL, station IPv4, provisioned PC IPv4, Wi-Fi signal, uptime and
listening/speaking state. Listening describes capture mode, not PC health or STT
success. RAM offsets and color inversion are Kconfig settings for panel variants;
initial offsets are zero and inversion is enabled, pending visual verification.
The implementation follows the installed official SPI LCD example and
[Espressif's LCD API](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/lcd/index.html).

The existing voice_stream component owns saved configuration, Wi-Fi and the
setup-only HTTP server. Store one validated versioned NVS blob with SSID,
WPA2-or-better personal password and canonical unicast PC IPv4. This supersedes
the console-only/compiled Wi-Fi selection in ADRs 0006 and 0008. The ignored
local credentials header remains private but is no longer consumed.

Missing/invalid settings, serial `s` in the three-second boot window, or no
station IPv4 within 30 seconds opens an AP with a fresh random 12-hex-digit
WPA2 password. Show credentials on LCD and trusted serial console. The setup
page is at http://192.168.4.1; there is no captive DNS or automatic redirect.
Only HTTP requests addressed to the AP interface with matching Host and
same-origin browser submissions are accepted. Bound request sizes and receive
timeouts, reject malformed/duplicate/unknown fields and invalid values, commit
the complete blob and reboot after sending the success response. No server or
AP runs during a normal configured session. Wi-Fi loss during streaming retains
the existing automatic reconnection behavior; reboot to enter setup recovery.

Audio, UDP 5005 and speaker HTTP 5006 contracts remain unchanged. The PC IPv4
is shared by both paths. No PC services or ThingsBoard implementation changes.

## Alternatives

Serial setup requires a PC cable at every boot. ESP-IDF provisioning managers
would add a phone application/protocol for this small browser-only prototype.
A permanent LAN management server adds an unnecessary access-control boundary.

## Consequences

Trusted local development only. HTTP is protected by the setup AP's WPA2 link;
NVS credentials are plaintext at rest without flash/NVS encryption. No production
provisioning or authentication claim. Settings persist across reflash when NVS
is retained; erasing NVS removes them. Bad Wi-Fi values can be corrected via
the automatic boot fallback. A wrong but reachable Wi-Fi network or changed PC
address can be corrected via serial `s`. No reset GPIO is allocated.

## Validation

Run actual C parser regression tests, existing audio tests, repository validator,
and an ESP-IDF v6.1 esp32s3 build. Record device flashing, setup HTTP/NVS/reboot,
LCD layout and voice-loop checks separately in the firmware guide. Compilation
does not establish backlight polarity, image alignment, audibility or radio
association. Panel offsets/inversion may require adjustment after inspection.

Executed results are in the [firmware guide](../../firmware/README.md). The user
subsequently confirmed the backlight, full text visibility and alignment are
correct with the initial display settings.
