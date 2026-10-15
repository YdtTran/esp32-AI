# 0012: Open captive setup and animated device status

- Date: 2026-10-14
- Status: Accepted
- Owners: firmware

## Context

The user confirms the initial LCD looks correct and requests removal of the
ESP32 setup Wi-Fi password, automatic setup-page opening after joining, and
an animated LCD after connection to Wi-Fi and the PC server. Hardware, saved
home Wi-Fi credentials and existing audio contracts remain unchanged.
After confirming automatic Windows opening, the user also requests a dropdown
of available Wi-Fi networks instead of manual SSID entry.

## Decision

Supersede ADR 0011's password-protected AP and manual-only page navigation.
`VOICE-SETUP-XXXX` is an open setup-only AP. The home Wi-Fi password field remains
required; no NVS format migration is needed. Preserve setup isolation, the boot
recovery conditions, serial `s`, bounded form parsing and commit/reboot behavior.

Setup uses AP+STA radio mode so the station radio can scan. Cancel station
connection attempts, clear its credentials and suppress reconnect callbacks
throughout setup; the station does not join the home network in this mode.
A setup-only worker performs SDK scans without blocking DNS/HTTP, caches up to
16 records, deduplicates SSIDs and serves `/networks`. Serialize SSIDs with
bounded JSON escaping; render them as option text, never HTML. The dropdown
shows signal strength and disables unsupported security modes. A refresh button
starts another scan; hidden networks retain an explicit manual-entry option.
The existing SSID/password/PC form and NVS format are unchanged. All setup tasks
end at the save/reboot boundary.

Follow the installed ESP-IDF v6.1
[captive portal example](https://github.com/espressif/esp-idf/tree/v6.1/examples/protocols/http_server/captive_portal):
advertise AP DNS and a DHCP option 114 URI, run a bounded UDP DNS responder
bound to 192.168.4.1:53, and redirect HTTP probe GETs to the absolute canonical
http://192.168.4.1/ URL. A small captive API returns captive=true and the landing
URL. Wildcard A queries resolve to the AP with TTL zero; other IN question
types receive empty answers. Reject truncated/oversized packets, unsupported
flags, multiple questions, compressed names and excessive label/name lengths.
Strip optional additional records from replies. Do not forward DNS upstream.

Probe GETs accept foreign Host values only on the AP interface and redirect;
the form and POST still require the canonical Host and, when supplied, Origin.
The destination guard accepts native IPv4 and IPv4-mapped IPv6 socket addresses:
the installed v6.1 HTTP server listens on an IPv6 socket when IPv6 is enabled.
DNS and HTTP exist only during setup and disappear on reboot into normal mode.
Phones may show a sign-in notification requiring a tap, depending on OS settings,
VPN/private DNS and cached network state. Arbitrary HTTPS sites cannot be
transparently redirected. Retain the IP URL on LCD as a fallback. Devices may
need to forget the previous secured setup network once after this update.

The display renders a code-native breathing ring, blinking face and waveform:
amber while waiting for Wi-Fi/PC, teal while listening, cyan with a larger
mouth/wave during speaker playback. Existing GPIOs, SPI settings and the single
7,680-byte DMA stripe remain unchanged. Redraw just the animation region between
text changes, with a 100 ms delay after rendering. Alternate the footer between
device/PC addresses and RSSI/uptime every six seconds.

Readiness requires station IPv4 and a recent valid response from the existing
PC speaker mailbox: HTTP 204 or contract-valid PCM 200. Do not introduce a new
health endpoint. Expire idle readiness after five seconds without success;
keep it during an active download, and clear it on poll/download failure or
Wi-Fi/IP loss. This indicates speaker mailbox reachability, not health of STT,
the LLM, Piper or UDP delivery. Capture can continue when the mailbox is absent.

## Alternatives

Manual URL entry does not meet the requested setup experience. A platform
provisioning app adds dependencies and installation steps. A full graphics
library or bitmap asset collection is unnecessary for this small animation.
Always showing server-connected after Wi-Fi association would misrepresent
service availability.

## Consequences

The open setup AP is intentionally unauthenticated. Anyone in radio range can
join, inspect unencrypted setup traffic or change settings while setup is active.
No existing saved password is returned by the page. NVS remains plaintext at
rest. This is the user's requested development convenience, not production
provisioning. No permanent LAN management interface is introduced.

## Validation

Exercise the real C DNS parser with A/AAAA, EDNS, flags, truncation, capacity,
maximum names and malformed queries; exercise mapped IPv6 address guarding,
mailbox readiness and JSON escaping/bounds. Retain config/audio tests and run
root validation. Compile for esp32s3 with existing v6.1, flash COM19 and inspect
bounded boot logs for AP/DNS startup and display/panic failures. Review native
animation frames on the host. Phone sign-in popup behavior and visual animation
on the physical LCD require separate user/device observation. Record executed
commands, size and remaining limitations in the firmware guide.

Executed Windows diagnosis found that the original IPv4-only interface check
returned 403 for both probe and landing-page requests. DNS was already correct.
After the mapped-address fix, the device probe passed and Windows NCSI logged
HotspotDetected; the user confirmed automatic opening. See the firmware guide
for the scan update's final checks and remaining physical limitations.
The final radio scan returned nine networks, and a headless Edge session on
the real device page populated all nine dropdown entries. Portal device checks,
the v6.1 build/flash and all 49 host checks passed. Live voice/physical animation
synchronization still awaits provisioning; see the guide for exact limitations.
