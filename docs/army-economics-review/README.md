# Army economics data review (2026-11-12)

Independent audit of the army-economics dataset on branch `matchup-timings`
(commit 829c65bec): `data/golden/army_context.db` and the reviewed sources
under `aoe2x/js_simulation/calibration/economy/`. Nothing in that dataset was
changed by this review.

| Area | Report | Comparison rows |
|---|---|---|
| Unit production: training times, buildings, bonuses, unit prices | [PRODUCTION.md](PRODUCTION.md) | `production-comparison.csv` (7,482) |
| Unit research: upgrades needed, costs, research times | [RESEARCH.md](RESEARCH.md) | `research-comparison.csv` (56,076) |
| Villager gathering rates in the Imperial Age | [GATHERING.md](GATHERING.md) | `gathering-comparison.csv` (379) |

Sources: the decoded game file used by the dataset (patch 188329 changes),
aoe2techtree.net data for update 188329, this repo's reference databases, the
Age of Empires wiki and published community gathering measurements.

`scripts/<area>/` holds the comparison scripts. They expect the sparse
`matchup-timings` checkout and restored sources described in
`docs/matchup-timings-handoff.md` on that branch, plus downloaded copies of the
online data, so treat them as a record of method rather than a one-command rerun.
