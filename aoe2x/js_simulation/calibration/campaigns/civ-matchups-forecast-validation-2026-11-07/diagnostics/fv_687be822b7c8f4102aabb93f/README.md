# Exhausted Burmese Elite Skirmisher / Mapuche Elite Kona

Job `fv_687be822b7c8f4102aabb93f`, counts 27 / 19, exhausted all four normal seed-0 watchdogs at 2026-11-09T14:04:05.015Z. No seed completed.

Seed 0 exhausted all four normal watchdogs without completing. All four timelines have constant-survivor/HP suffixes: one Elite Skirmisher at 21 HP and eighteen Elite Kona at 2,460 combined HP. Those suffixes contain 5, 19, 59 and 119 snapshots. All sampled survivors in those suffixes are idle with null attack targets, but positions and pursuit/engagement targets keep changing. The four suffixes have 5, 19, 59 and 118 distinct position states and two distinct target states each. Twelve movement/pursuit/reservation/blocked counters grow while combat counters remain fixed. This is continuing movement and replanning without HP progress, not a fixed-position diagnosis. The precise contact/range/geometry/route cause and real-game outcome remain unknown.

No native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `c40618ff041961ffcb7abdb79ad8ed3a3f2d1f64`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_687be822b7c8f4102aabb93f/analyze.py --output <new-directory>
```
