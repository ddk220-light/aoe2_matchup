# sck_record — ScreenCaptureKit screen+audio recorder

Captures the main display's **video + system audio** to a `.mov`, using macOS
ScreenCaptureKit. No loopback driver (BlackHole/Soundflower) needed — system
audio is captured via the Screen Recording permission. The recorder's own
process audio is excluded automatically.

This is the capture stage of the matchup-video pipeline: record an in-game
fight, then feed the `.mov` to `../overlay/make_real_video.py`.

## Build (once, and after editing the .swift)

```bash
./build.sh        # swiftc -O sck_record.swift -o sck_record
```

## Record

```bash
./record.sh <out.mov> <seconds> [fps] [width] [height]
# defaults: fps=60, 1920x1248  (matches the video pipeline's SIZE)
./record.sh /tmp/fight.mov 20            # 20s at 1920x1248@60
```

`sck_record` directly: `sck_record <out.mov> <seconds> [fps] [width] [height]`
(omit width/height for native display resolution).

**Why 1920x1248, not native?** Native Retina res can't sustain a high capture
framerate in busy fights (drops to ~11 fps). 1920-wide keeps the capture aspect
(no squish) and stays smooth. SCK only emits frames when screen content changes,
so an idle scene reads lower fps than a busy fight — that's expected.

## macOS Screen Recording permission (required)

System audio capture is gated by the **Screen Recording** TCC grant of the
process that *launches* `sck_record`:

- Running from **Terminal** → grant Terminal "Screen Recording"
  (System Settings → Privacy & Security → Screen Recording).
- Launched by another app (e.g. an automation host) → that app needs the grant.

TCC is read at process **launch**, so after enabling the checkbox you must
**restart** the launching app for it to take effect.

Verify a capture has real (non-silent) audio:

```bash
ffmpeg -i out.mov -af volumedetect -f null - 2>&1 | grep -iE 'mean_volume|max_volume'
# silence ≈ -91 dB;  real audio is much higher (e.g. -22 dB mean / -1 dB peak)
```

## Notes

- System audio is the full output **mix** — mute notifications/other apps so only
  the game is recorded. Capture level is independent of the hardware volume knob.
- The composer (`../overlay/compose.py`) currently maps **video only** — to keep
  the captured audio in the final composed video its `_fight_segment`/`_concat`
  steps need to carry/mux the fight clip's audio (cards are silent). TODO.
