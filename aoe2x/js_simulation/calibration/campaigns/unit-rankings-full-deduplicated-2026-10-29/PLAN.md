# Complete ranking dataset: execution plan

## Coverage and elimination of duplicate work

Collect raw Imperial land-combat data for all **555 unit/civilization variants across 56 civilizations**, using the owner's three opponent pools. Preserve every civilization's ranking-table row. Ranking scores and the browser update remain deferred until a scoring formula is chosen.

| Group | Unit variants | Ranking matchup rows | Distinct simulations | Baseline runs |
|---|---:|---:|---:|---:|
| Infantry | 147 | 735 | 550 | 1,650 |
| Ranged | 274 | 1,918 | 1,099 | 3,297 |
| Cavalry | 134 | 938 | 749 | 2,247 |
| Total | 555 | 3,591 | 2,398 | 7,194 |

There are **374 distinct combat profiles**. Matching profiles share one set of simulated seeds. This avoids **3,579 baseline runs (33.2%)** while retaining all 3,591 ranking matchup rows. Fourteen civilizations, for example, have the same fully upgraded Halberdier profile.

Equality ignores **only the civilization label**. Every other mechanics field must match exactly, including unit identity, HP, attack/armor classes, reload and animation timing, projectiles, movement, collision, costs, population and all nested effects. New/unknown fields participate in equality automatically. A matchup also requires identical opposing profiles, physical unit counts and the entire scenario. There is no rounding, approximate matching or assumption that equal headline stats imply equal behavior.

The [equivalence map](equivalence.json) links each ranking row to its actual simulated matchup. [Cross-civilization checks](equivalence-verification.json) tested Halberdiers, Skirmishers, Hussars, Scorpions and Hand Cannoneers: combat events, final animation state, remaining HP, winners and durations matched exactly. Full-state hashes retain the civilization label, so those hashes are not used to compare different labels. Every shared row reports its simulation source rather than claiming to be an independent observation.

## Fixed simulation rules

- Same V3 physics and unit profiles as the accepted pilot. Preserve golden formations and patrols; no buffers or scripted kiting.
- Cheaper side: **27 physical units**. Expensive side: `round(27 * sqrt(cheaperWeightedCost / expensiveWeightedCost))`.
- Cost: food + 0.9 wood + 1.1 gold, after all civilization discounts and batch-cost division.
- Infantry opponents: Spanish Champion, Spanish Hussar, Chinese Arbalester, Spanish Paladin, Turkish Cavalier.
- Ranged opponents: Spanish Champion, Chinese Arbalester, Turkish Cavalier, Saracen Heavy Cavalry Archer, Saracen Hand Cannoneer, Spanish Hussar, Spanish Elite Skirmisher.
- Cavalry opponents: Spanish Champion, Chinese Arbalester, Spanish Paladin, Spanish Halberdier, Turkish Heavy Camel, Turkish Cavalier, Saracen Heavy Cavalry Archer.
- Jarl and Elephant Archers are Ranged. Existing ranged siege entries remain in the Ranged group. War Chariot uses focus fire. Patched Mounted Crossbowman, Guard, Hearth Troop, Jomsviking and Jarl entries are included. Naval and anti-building groups are explicitly outside these opponent pools.
- Run seeds 0, 1 and 2. If the initial decided outcomes differ, add seeds 3–9. Save every physical run; summarize decided results and list unresolved results separately.

## Phases: automatic checks, then continuation

1. **Preflight, passed.** Validate all profiles, costs, opponents and formations. Ten pilot replays reproduced exact final-state/event hashes with the persistent worker. Five cross-civilization equivalence checks passed. Import the 37 pilot results and six additional completed runs after comparing their exact inputs and unchanged engine source.
2. **Phase 01 — 18 mechanics checks.** Exercise Iron Pagoda, Ordo, Guard and Hearth charges, Jarl, Jomsviking, Monaspa, Shrivamsha shields, War Chariot focus fire, Mounted Trebuchet, fighting gold, Liao Dao, Tiger Cavalry, Guecha, Blackwood, Elephant Archer, Bolas Rider and Scorpion behavior.
3. **Phases 02–06 — Infantry.** Finish the remaining 546 distinct matchups, in batches of at most 120.
4. **Phases 07–16 — Ranged.** Finish the remaining 1,091 distinct matchups, in batches of at most 120.
5. **Phases 17–23 — Cavalry.** Finish the remaining 743 distinct matchups, in batches of at most 120.
6. **Final coverage audit.** Verify all required seeds for all 2,398 distinct matchups, resolve the shared-results mapping for every ranking row, export the full summary and review queue, and push the final checkpoint.

Every phase checks required-seed coverage, uniqueness, valid counts and finite HP, SQLite integrity and unchanged source hashes. A separate replay must reproduce a completed seed's final-state/event hashes. Results go into `state.json`; passing phases advance automatically without approval prompts. Undecided/error cases are retained and do not block unrelated work. Integrity or reproducibility failures are explicit failures, never waived to declare completion.

## Cloud efficiency and duration

Use **four persistent worker threads**, matching this container's four-core quota and 16 GiB memory. Reuse loaded modules and JIT work across jobs. One parent owns SQLite; workers run only combat jobs. Keep all cores occupied within each phase and execute extra seeds only for matchups that need them.

The bulk path saves final results, seeds and exact frozen replay inputs rather than writing every animation frame. The pilot's full playbacks remain available locally. Combat physics are unchanged.

The initial ten-job parity batch took 63.8 seconds including cold starts. After removing duplicates, the remaining minimum workload is approximately **13 hours at that initial rate**, plus additional seeds. This is an initial estimate, not a deadline. `progress.json` updates throughput and estimated remaining time from actual completed jobs. No extra paid cloud resources are assumed.

## Persistence and unattended operation

- Save every completed physical run immediately in SQLite (WAL, synchronous FULL) and a flushed per-phase JSONL journal.
- Recover a fresh SQLite database from those journals and saved attempt records. Completed seeds are never recomputed during resume.
- Freeze every profile, scenario, source file and simulation switch in [manifest.json](manifest.json). Resume rejects mixed engine versions.
- Stop an individual attempt at 150 game seconds or 120 wall seconds. Label timeouts **undecided**, not draws. Record worker errors and replace failed workers.
- Export progress and matchup summaries approximately every 30 seconds. Raw run records are durable individually between exports.
- Commit and push the campaign to `simulations/v3-engine-ranking-pilot-2026-10-29` every 250 new results, ten minutes, and at every phase boundary. Failed uploads preserve local progress and are retried at the next checkpoint.
- Run under a detached supervisor. Transient process failures receive up to three automatic restarts, each resuming from saved data. Integrity failures remain visible.

Run or resume all remaining phases, including GitHub checkpoints:

```bash
python aoe2x/js_simulation/tools/supervise_ranking_campaign.py \
  --campaign aoe2x/js_simulation/calibration/campaigns/unit-rankings-full-deduplicated-2026-10-29 \
  --workers 4 --publish true
```

Monitor [progress](progress.json), [phase reviews](state.json), [ranking matchup summary](summary.csv), [individual physical runs](runs/), and [unresolved cases](undecided.json). Local process output is in `runner.log`.
