# Exhausted Burgundian Elite Skirmisher / Mapuche Elite Kona

Job `fv_02521b013b039fe6f65c73ca`, counts 27 / 19, exhausted all four normal seed-0 watchdogs at 2026-11-09T12:30:36.891Z. No seed completed.

Seed 0 exhausted all four normal watchdogs without completing. All four timelines have constant-survivor/HP suffixes: one Elite Skirmisher at 22 HP and eighteen Elite Kona at 2,460 combined HP. Those suffixes contain 5, 19, 59 and 119 snapshots. All sampled survivors in those suffixes are idle with null attack targets, but positions and pursuit/engagement targets keep changing. The four suffixes have 5, 19, 59 and 118 distinct position states and two distinct target states each. Twelve movement/pursuit/reservation/blocked counters grow while combat counters remain fixed. This is continuing movement and replanning without HP progress, not a fixed-position diagnosis. The precise contact/range/geometry/route cause and real-game outcome remain unknown.

No native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `191ff4a05b031a6f5989681bdf0afe0acdedfc2d`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_02521b013b039fe6f65c73ca/analyze.py --output <new-directory>
```
