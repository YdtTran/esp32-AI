# 0008: Local compiled development Wi-Fi credentials

- Date: 2026-10-14
- Status: Accepted
- Owners: firmware maintainer

Superseded by [ADR 0011](0011-lcd-and-web-setup.md): firmware now uses saved/web
setup and no longer reads the ignored local Wi-Fi credentials header.

## Context

The user explicitly requested hardcoded Wi-Fi settings for the prototype instead
of entering SSID/password at each boot. The repository must not contain secrets.

## Decision

Support an optional ignored `wifi_credentials.local.h` in the voice_stream
component's include directory. It defines `VOICE_WIFI_SSID` and
`VOICE_WIFI_PASSWORD` string macros. Exclude the header from Git and Docker build
contexts. Validate credential lengths at compile time. When present, omit Wi-Fi
console prompts; otherwise retain console provisioning. The bridge IP remains
entered at boot. Wi-Fi RAM storage and reconnect behavior remain unchanged.

This replaces ADR 0006's console-only Wi-Fi provisioning on this machine under
the user's explicit instruction. It does not change audio or wire interfaces.

## Alternatives

Putting credentials directly in tracked C/Kconfig defaults exposes them to
version control. Console-only settings do not meet the requested boot behavior.
Production provisioning is outside this development-only change.

## Consequences

Local firmware binaries contain the supplied credentials and remain ignored
build output. Changing credentials requires rebuild/flash. Clones without the
local header use console setup. Credentials are never printed by the application.

## Validation

`git check-ignore firmware/components/voice_stream/include/wifi_credentials.local.h`
confirmed exclusion. Build and existing host-check results are recorded in the
firmware README. Flashing and Wi-Fi association require the actual board;
no physical connection success is implied by compilation.
