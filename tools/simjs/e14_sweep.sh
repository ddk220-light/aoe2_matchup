#!/usr/bin/env bash
# E14 sweep driver: for each (MELEE_QUEUE_TILES, MELEE_QUEUE_CAP) pair, patch
# constants.js, run the full 155-fight x 20-seed calibration, and print the
# melee-gate block. Restores the file's original values on exit.
#
#     bash tools/simjs/e14_sweep.sh "0.3:4 0.6:3 0.6:2"
set -euo pipefail
cd "$(dirname "$0")/../.."
C=apps/website/static/js/engine/constants.js
ORIG_T=$(grep -oP '(?<=^export const MELEE_QUEUE_TILES = )[0-9.]+' "$C")
ORIG_C=$(grep -oP '(?<=^export const MELEE_QUEUE_CAP = )[0-9]+' "$C")
restore() {
  sed -i "s/^export const MELEE_QUEUE_TILES = .*/export const MELEE_QUEUE_TILES = ${ORIG_T};/" "$C"
  sed -i "s/^export const MELEE_QUEUE_CAP = .*/export const MELEE_QUEUE_CAP = ${ORIG_C};/" "$C"
}
trap restore EXIT

for pair in $1; do
  T="${pair%%:*}"; K="${pair##*:}"
  DIR="D:/AI/aoe2_golden/simruns_e14_t${T/./}c${K}"
  sed -i "s/^export const MELEE_QUEUE_TILES = .*/export const MELEE_QUEUE_TILES = ${T};/" "$C"
  sed -i "s/^export const MELEE_QUEUE_CAP = .*/export const MELEE_QUEUE_CAP = ${K};/" "$C"
  echo "=== tiles=${T} cap=${K} -> ${DIR}"
  node tools/simjs/calib_runner.mjs --seeds 20 --out-dir "$DIR" >/dev/null
  PYTHONPATH=. python tools/simjs/melee_hp_report.py --sim-runs-dir "$DIR" --worst 0 | head -8
done
