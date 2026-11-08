# Exhausted Incan Elite Skirmisher / Polish Cavalier seed

Job `fv_5c08b7d3266df27dbb057abc`, original physical counts **27 / 19**, has no completed seed.
Frozen role keys are `Incas|imp_elite_skirm` and `Poles|paladin`; the unchanged
mechanics profiles name the actual upgrades **Elite Skirmisher / Cavalier**.

Seed 0 exhausted the 180/600/1800/3600-wall-second watchdogs. The first attempt
ended at an earlier state with one skirmisher and fourteen cavalry survivors.
The three longer attempts reach identical late positions, HP, actions and
targets: one skirmisher at **9 HP**, and three Cavaliers at **339 combined HP**.
All four are idle with null attack targets, although some pursuit/engagement
targets remain assigned. Five pursuit/contact/blocked counters continue growing;
other event counters, including combat, remain unchanged in each saved late suffix.

The final attempt ended at tick 1,877,033.
Its last fsynced snapshot is earlier, at tick 1,862,026.
Its constant core suffix contains **106 snapshots**, from game second
2075.7 to 31033.766666666666.
The saved timelines establish a reproducible late stall within the tested limits,
not its exact contact/range/geometry/route cause or a real-game winner or draw.

No seed 0 measurement, pair review or correction is assigned. Later seed
requirements depend on a completed first result. No same-seed replay is required
or performed under the current v3 amendment. No simulation was executed for this
diagnosis, and no physics, forecasts, contexts, inventory order or queue controls changed.

The immutable source is `d5144b0ac57335b017b6d7ca0fe2b3d2f8315e03`. `REVIEW.json` retains original context/profile
order, counts, evidence and flags, four attempt-line hashes and all progress hashes,
plus source manifest, frozen-profile, sampling-policy, journal and phase-review hashes.
The phase-044 `complete_with_blocked` status is not full completion. The ordinary
queue continues, and this job remains blocked pending a separate recovery review.

From the repository root, reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_5c08b7d3266df27dbb057abc/analyze.py --output <new-directory>
```
