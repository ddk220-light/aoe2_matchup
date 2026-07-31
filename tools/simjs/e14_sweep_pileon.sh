#!/usr/bin/env bash
# E14 round-2 sweep: MELEE_PILE_ON_TILES, at whatever queue point is currently
# in constants.js. Restores the original value on exit.
#
#     bash tools/simjs/e14_sweep_pileon.sh "0.5 1.0 2.0"
set -euo pipefail
cd "$(dirname "$0")/../.."
C=apps/website/static/js/engine/constants.js
ORIG=$(grep -oP '(?<=^export const MELEE_PILE_ON_TILES = )[0-9.]+' "$C")
restore() {
  sed -i "s/^export const MELEE_PILE_ON_TILES = .*/export const MELEE_PILE_ON_TILES = ${ORIG};/" "$C"
}
trap restore EXIT

for P in $1; do
  DIR="D:/AI/aoe2_golden/simruns_e14_p${P/./}"
  sed -i "s/^export const MELEE_PILE_ON_TILES = .*/export const MELEE_PILE_ON_TILES = ${P};/" "$C"
  echo "=== pile_on=${P} -> ${DIR}"
  node tools/simjs/calib_runner.mjs --seeds 20 --out-dir "$DIR" >/dev/null
  PYTHONPATH=. python tools/simjs/melee_hp_report.py --sim-runs-dir "$DIR" --worst 0 | head -8
done
