# Exhausted Viking Light Cavalry / Sicilian Elite Skirmisher

Job `fv_c250a7a42ac0230166abf1ef`, counts 23 / 27, exhausted all four normal seed-0 watchdogs at 2026-11-09T04:19:58.749Z. No seed completed. The frozen role key `Vikings|hussar` retains the actual mechanics upgrade Light Cavalry.

Seed 0 exhausted all four normal watchdogs without completing. The short first attempt stops earlier, with fourteen Light Cavalry at 675 combined HP and one Elite Skirmisher at 8 HP, still attacking. The three longer attempts reach identical fixed survivor positions, HP, actions and targets: three Light Cavalry at 136.5 combined HP and one Elite Skirmisher at 8 HP, all idle with null attack targets. Their constant-core suffixes contain 9, 52 and 111 snapshots. Five reservation/pursuit/blocked counters grow while combat counters remain fixed. The exact contact/range/geometry/route cause and real-game outcome remain unknown.

No native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `0789456d2247747e840f1210293f9a536a580945`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_c250a7a42ac0230166abf1ef/analyze.py --output <new-directory>
```
