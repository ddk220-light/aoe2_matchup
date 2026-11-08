# Exhausted Danish Elite Jomsviking / Muisca Elite Guecha Warrior seed

Job `fv_9c07f592c61760a424b461f4`, original counts **27 / 23**, has no completed seed.
Seed 0 exhausted the 180/600/1800/3600-wall-second watchdogs. The final attempt
ended at tick 4,426,130; its last fsynced snapshot
is earlier, at tick 4,388,417.

All four attempts reproduce twelve idle Jomsvikings at **(2,13)** with **666 HP**
combined and one idle Guecha Warrior at **(13,2)** with **16.027777777777807 HP**.
All thirteen survivors have null pursuit, engagement and attack targets. Their
positions, HP, actions, targets and every event counter remain constant in each
late suffix. The final attempt has **119** such consecutive snapshots,
from game second 382.3666666666667 to
73140.28333333334, while the simulation ticks advance.
The snapshots establish nontermination in the frozen runtime; they do not explain
precisely how these idle corner states arose or establish a real-game winner.

No seed 0 measurement, pair review, native outcome, draw or correction is assigned.
Additional seed requirements remain conditional on a completed first result.
Same-seed replays are not required and were not performed under the current v3
amendment. No simulation was executed for this diagnosis.

The immutable source is `cded99b0b044a7bcfe108bc7a80453a193eeee63`. `REVIEW.json` retains physical profile order,
counts, original evidence and flags, four attempt-line hashes and all progress
hashes, plus the source manifest, sampling policy, journal and phase-review hashes.
The phase-030 `complete_with_blocked` status is not full completion.

No physics, forecasts, inventory order or queue controls changed. The existing
four-worker ordinary queue continues; this job stays blocked. A separate recovery
review is required before another retry. No old or cross-engine winner is imported.

From the repository root, reproduce with:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_9c07f592c61760a424b461f4/analyze.py --output <new-directory>
```
