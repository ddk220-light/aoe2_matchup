# Exhausted Malay Light Cavalry / Khitan Elite Skirmisher seed

Job `fv_e0d18588ecc82161d1d74801`, original physical counts **23 / 27**, has no completed seed.
Frozen role keys are `Malay|hussar` and `Khitans|imp_elite_skirm`; the unchanged
mechanics profiles name the actual upgrades **Light Cavalry / Elite Skirmisher**.

Seed 0 exhausted the 180/600/1800/3600-wall-second watchdogs. All four attempts
reach identical late positions, HP, actions and targets: three Light Cavalry at
**96 combined HP** and one Elite Skirmisher at **27 HP**. All four are idle with
null attack targets, although some pursuit/engagement targets remain assigned.
Five pursuit/contact/blocked counters keep growing; all other event counters,
including combat, remain unchanged within each saved late suffix.

The final attempt ended at tick 2,479,557.
Its last fsynced snapshot is earlier, at tick 2,461,539.
Its constant core suffix contains **118 snapshots**, from game second
441.95 to 41025.65.
These observations establish a reproducible late stall within the tested limits,
not its exact contact/range/geometry/route cause or a real-game winner or draw.

No seed 0 measurement, pair review or correction is assigned. Later seed
requirements depend on a completed first result. No same-seed replay is required
or performed under the current v3 amendment. No simulation was executed for this
diagnosis, and no physics, forecasts, contexts, inventory order or queue controls changed.

The immutable source is `4e05f22c28840dbaa8350f227144941a53a62e88`. `REVIEW.json` retains original context/profile
order, counts, evidence and flags, four attempt-line hashes and all progress hashes,
plus source manifest, frozen-profile, sampling-policy, journal and phase-review hashes.
The phase-049 `complete_with_blocked` status is not full completion. The ordinary
queue continues, and this job remains blocked pending a separate recovery review.

From the repository root, reproduce into a new directory:

```sh
python aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/diagnostics/fv_e0d18588ecc82161d1d74801/analyze.py --output <new-directory>
```
