# Exhausted Chinese Heavy Scorpion / Polish Heavy Mounted Crossbowman

Job `fv_d94fee4147c5053486b13687`, counts 23 / 27, failed all four normal seed-0 attempts with the same ranged-crowd reservation geometry RangeError during movement resolution. None completed. The error reports separation 0.02350274216190229 versus extent 0.025 for references 9000/9011. Saved diagnostic snapshots precede the failing step; they do not establish the full failing state, exact cause or a winner.

No result, draw, review or correction is assigned. No new simulation, replay, physics change or further retry was performed or authorized. The ordinary queue continues with this case blocked pending separate recovery review. Source `80c66d94fdfedccd255ff21ae3a1428f0f67add9` and all journal-line/progress hashes are retained in `REVIEW.json`.

Reproduce from the repository root into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_d94fee4147c5053486b13687/analyze.py --output <new-directory>
```
