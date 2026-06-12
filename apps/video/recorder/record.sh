#!/bin/bash
# Record the main display (VIDEO + SYSTEM AUDIO, no loopback driver) to a .mov.
#
#   record.sh <out.mov> <seconds> [fps] [width] [height]
#
# Defaults match the matchup-video pipeline: 1920x1248 @60. That keeps the capture
# aspect (no squish) and stays smooth — native Retina res drops to ~11fps in busy
# fights, which is why we downscale at the source. System audio is captured via the
# Screen Recording TCC grant (no BlackHole/Soundflower needed); the recorder's own
# process audio is excluded automatically.
#
# Requires ./sck_record (run ./build.sh once). The host process (Terminal, or the
# app that spawns this) must have macOS Screen Recording permission.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?usage: record.sh <out.mov> <seconds> [fps] [width] [height]}"
SECS="${2:?seconds required}"
FPS="${3:-60}"
W="${4:-1920}"
H="${5:-1248}"
if [[ ! -x "$DIR/sck_record" ]]; then
  echo "sck_record not built — running build.sh first" >&2
  "$DIR/build.sh"
fi
exec "$DIR/sck_record" "$OUT" "$SECS" "$FPS" "$W" "$H"
