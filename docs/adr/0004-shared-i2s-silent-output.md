# 0004: Shared I2S bus with silent speaker output

- Date: 2026-10-14
- Status: Accepted
- Owners: firmware

## Context

The user reports constant speaker hiss/buzz and confirms that the microphone
and speaker share clock pins. Existing code initialized microphone RX only;
speaker output remained a stub. The user requested the shared-clock software
fix. The documented MAX98357A DIN is GPIO7, separate from microphone SD GPIO6.
Undriven DIN is a suspected cause, not a hardware-verified diagnosis.

## Decision

The `audio_bus` component owns one paired standard-I2S TX/RX allocation.
Its public API initializes the pair and reads microphone words; initialization
is idempotent and called serially from app_main. `audio_input` and `audio_output`
delegate to that owner rather than allocating separate clock-generating channels.
Both channels use the existing Philips I2S, 32-bit mono left-slot configuration.
The existing 16 kHz rate becomes a Kconfig setting, persisted in defaults.
These are accepted development settings for this fix, not a verified production
audio contract or electrical configuration.

The installed ESP-IDF v6.1 standard-I2S example documents allocating both handles
together and configuring them before enabling them. Its driver zero-initializes
DMA buffers and documents `auto_clear_after_cb` as transmitting zeros when no
data is supplied. TX therefore supplies continuous digital silence on amplifier
DIN while RX captures the microphone. Initialize audio before waiting for Wi-Fi.
GPIO definitions remain in board_pins.h; the assignments have not changed.

No playback API, amplifier SD/EN pin, carrier-board or memory setting is added.
Startup silence before app_main and analog power/ground noise remain outside
what this software fix can establish. Firmware does not control shutdown.

## Alternatives

Keep the amplifier shut down during microphone-only capture: requires verified
breakout SD/EN wiring, which is not documented. Separate clock pairs: requires
a reviewed wiring change. Independent masters on the shared nets are unsuitable.
A dedicated task writing zeros is unnecessary with the installed DMA behavior.

## Consequences

The speaker data input is driven while capture runs, using one coordinated clock
pair. Microphone reads still return left-slot 32-bit words. Output initialization
now returns esp_err_t and starts silence; it does not play microphone audio.
Shared initialization must run serially. Failure releases allocated channels.
Physical shared-clock compatibility and noise reduction require device testing.

## Validation

SDK evidence: installed components/esp_driver_i2s/i2s_common.c allocates TX DMA
buffers with i2s_dma_calloc; include/driver/i2s_common.h documents auto-clear.
`idf.py build` from firmware passed for esp32s3 on retry with the existing SDK.
The initial final-link failure was a missing generated project ELF source
object; all audio components compiled, and retry regenerated the object.
`python -m unittest discover -s firmware/tests -v` passed its six startup/failure
scenarios against a fake driver. `python scripts/validate.py` passed seven
foundation tests. No flashing, DMA measurement or noise/hardware test was run.
Reproduction commands and SDK warning limitations are in the firmware guide.
