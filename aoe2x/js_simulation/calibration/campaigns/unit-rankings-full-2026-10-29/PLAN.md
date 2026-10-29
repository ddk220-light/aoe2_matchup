# Full unit-ranking data collection

## Scope and fixed rules

Collect the remaining raw combat data for every Imperial unit/civilization variant in the agreed Infantry, Ranged and Cavalry groups. Ranking scores and the website cutover remain a later step, after the owner chooses the scoring formula.

| Group | Variants | Opponents per variant | Matchups | Minimum runs |
|---|---:|---:|---:|---:|
| Infantry | 147 | 5 | 735 | 2,205 |
| Ranged | 274 | 7 | 1,918 | 5,754 |
| Cavalry | 134 | 7 | 938 | 2,814 |
| Total | 555 | | 3,591 | 10,773 |

The roster spans 56 civilizations. It follows the existing ranking groups, adds the patched Mounted Crossbowman, Varangian Guard, Hearth Troop, Jomsviking and Jarl entries, and de-duplicates units listed in multiple lines. Jarl and Elephant Archers are Ranged; ranged siege units already in the Ranged ranking remain there. War Chariot uses focus fire. Naval and anti-building groups have no opponent pool in this campaign and are explicitly listed as excluded in the manifest.

- Infantry: Spanish Champion, Spanish Hussar, Chinese Arbalester, Spanish Paladin, Turkish Cavalier.
- Ranged: Spanish Champion, Chinese Arbalester, Turkish Cavalier, Saracen Heavy Cavalry Archer, Saracen Hand Cannoneer, Spanish Hussar, Spanish Elite Skirmisher.
- Cavalry: Spanish Champion, Chinese Arbalester, Spanish Paladin, Spanish Halberdier, Turkish Heavy Camel, Turkish Cavalier, Saracen Heavy Cavalry Archer.
- The Turkish `paladin` database slug correctly resolves to **Cavalier**, including its actual stats.
- Cheaper side: **27 physical units**. Expensive side: `round(27 * sqrt(cheaperWeightedCost / expensiveWeightedCost))`.
- Weighted cost: food + 0.9 wood + 1.1 gold, using full civilization discounts and per-unit batch division.
- No buffers or scripted kiting. Keep the pilot's golden formations, patrols, physics and unit effects.
- Seeds 0, 1 and 2 first; add seeds 3–9 when those initial decided outcomes differ. Save every result. Average decided results; keep undecided cases separate.

## Phases and automatic review

1. **Preflight, completed:** validate every profile, category, opponent, cost and formation. Compare all ten pilot seed-0 runs against the persistent headless worker: final-state and event hashes match exactly. Reuse all 37 pilot results only after comparing their profiles, counts and scenarios.
2. **Phase 01: mechanics validation, 18 matchups.** Cover Iron Pagoda, Ordo regeneration, Guard/Hearth charges, Jarl, Jomsviking, Monaspa, Shrivamsha shields, War Chariot focus fire, Mounted Trebuchet, fighting gold, Liao Dao, Tiger Cavalry, Guecha, Blackwood, Elephant Archer, Bolas Rider and Scorpion/Rocket Cart profiles.
3. **Phases 02–08: remaining Infantry.** 731 matchups, batches of at most 120.
4. **Phases 09–24: remaining Ranged.** 1,910 matchups, batches of at most 120.
5. **Phases 25–32: remaining Cavalry.** 932 matchups, batches of at most 120.
6. **Completion audit:** verify the entire manifest has all required seeds, export the combined summaries and review queue, and publish the final checkpoint.

At each phase boundary, verify required-seed coverage, unique result keys, valid counts and finite HP values, SQLite integrity and frozen source hashes. Replay a completed seed separately and require exact final-state and event hashes. Review results are saved in `state.json`. Passing phases advance automatically without user confirmation. Undecided and failed matchups are flagged and do not stop unrelated matchups. An integrity or reproducibility failure stops the affected campaign rather than silently accepting corrupt results.

## Use of the cloud

The current container has a four-core CPU quota and 16 GiB memory. Use **four persistent worker threads** to occupy the available CPU without oversubscribing it. Persistent workers retain module loading/JIT work between fights. A shared parent owns the database; workers only simulate fights.

The engine is unchanged. Bulk runs save complete result records, replay seeds and frozen inputs instead of serializing every animation frame. This avoids unnecessary disk work and keeps the data portable. Any matchup can later be replayed using those inputs. The pilot's full per-tick playbacks remain available locally.

The initial ten-job parity batch took 63.8 seconds including cold starts. At that initial rate, the remaining minimum work would take about 19 hours; use the live throughput in `progress.json` to revise this estimate. Additional seeds and unusually slow fights increase the duration. No extra cloud instances or paid services are assumed.

## Persistence, recovery and publication

- Commit each completed run immediately to SQLite (WAL, synchronous FULL) and a flushed per-phase JSONL journal.
- Restore a fresh database from the committed phase journals and saved attempt records. Never repeat a saved matchup/seed.
- Keep source, profile, database and scenario hashes. Reject attempts to resume with different simulation code or switches.
- Enforce 150 game seconds and 120 wall seconds per attempt. Record timeouts as **undecided**, never as draws or forced winners. Worker crashes are recorded; the worker is replaced and other jobs continue.
- Save summaries and progress approximately every 30 seconds; preserve all raw results individually between exports.
- Commit and push to `simulations/v3-engine-ranking-pilot-2026-10-29` at each phase boundary, every 250 new results, or every ten minutes. If GitHub is unavailable, retain the checkpoint and retry at the next interval while continuing simulations.
- A detached supervisor retries transient process failures up to three times. Every restart resumes from saved results. Reproducibility/data-integrity failures remain explicit failures.

Run or resume the entire campaign:

```bash
python aoe2x/js_simulation/tools/supervise_ranking_campaign.py \
  --campaign aoe2x/js_simulation/calibration/campaigns/unit-rankings-full-2026-10-29 \
  --workers 4
```

Progress: `progress.json`. Phase reviews: `state.json`. Every run: `runs/*.jsonl`. Matchup averages: `summary.csv`. Slow/error cases: `undecided.json`. Process log: `runner.log` (local, ignored by Git).
