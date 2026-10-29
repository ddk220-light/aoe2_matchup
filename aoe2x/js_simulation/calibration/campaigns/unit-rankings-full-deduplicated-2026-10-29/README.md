# Full Imperial land rankings campaign

Status: **running**. 5727/7593 currently required runs; 2661/3591 complete matchups; 154 flagged for review.

555 civilization/unit variants across 56 civilizations. Infantry 147, Ranged 274, Cavalry 134. Imperial units only; naval and anti-building groups are outside the agreed opponent pools. Scoring remains deferred.

Exact profile sharing reduces this to **2398 distinct matchups** (374 combat profiles), avoiding 3579 baseline runs. Only the civilization label is excluded from equality; every other profile field, cost, count and scenario must match. The summary retains all civilization rows and identifies their shared simulation source. [Equivalence map](equivalence.json).

27 on the cheaper side; expensive side = round(27 × sqrt(cheaper / expensive weighted unit cost)). Weights: food 1, wood 0.9, gold 1.1; full discounts and per-physical-unit batch costs. No buffers or scripted kiting.

Three seeds per matchup, expanding to ten when the initial completed outcomes differ. 150 game seconds / 120 wall seconds per attempt. Undecided/error cases are saved and excluded from decided averages.

Four persistent workers run sequential phases automatically. Each phase verifies coverage, record validity, source hashes, SQLite integrity and a separate exact-seed replay before continuing. Each result commits to SQLite and a flushed JSONL journal. GitHub checkpoints occur at phase boundaries, 250 new results or ten minutes; network failures do not discard results.

- [Plan](PLAN.md), [progress](progress.json), [phase reviews](state.json), [summary table](summary.csv), [undecided](undecided.json).
- Every individual run is in [phase journals](runs/); these restore SQLite after a fresh checkout.
- [Manifest](manifest.json) freezes all profiles, formations, seeds, cost rules and source hashes.
- The [pilot](../unit-rankings-pilot-2026-10-29/) supplies 37 reused results with recorded provenance.

Resume (Node v24.19.0):

```bash
node aoe2x/js_simulation/node/full-ranking-campaign.mjs run --campaign aoe2x/js_simulation/calibration/campaigns/unit-rankings-full-deduplicated-2026-10-29 --publish true
```
