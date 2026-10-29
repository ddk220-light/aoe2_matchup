# Unit rankings pilot — October 29, 2026

Raw results only; scoring is deferred. Campaign: `1c5f5ec95034f949e812d8256fca1965c1f5386875d9ed0a7c47cc24c3f0fc76`.

27 units on the cheaper side; expensive count = round(27 × sqrt(cheap/expensive weighted cost)). Resource weights: food 1, wood 0.9, gold 1.1. Full discounts and cost per physical unit. No buffers or scripted kiting; current golden formations and patrols. Jarl is Ranged.

Three seeds initially; seven additional seeds if completed outcomes differ. 150 game-second limit; 120s wall-clock watchdog. Timeouts/errors are flagged for review.

Recorded 6/37 currently required runs; 1 complete matchups; 0 need review.

| Unit | Opponent | Counts | Runs | W/L/D | Undecided | Mean unit HP%* | Mean opponent HP%* |
|---|---|---|---|---|---|---|---|
| Spanish Champion | Spanish Champion | 27:27 | 3/10 | 1/2/0 | 0 | 5.43 | 6.67 |
| Spanish Champion | Spanish Paladin | 27:19 | 3/3 | 0/3/0 | 0 | 0.00 | 60.70 |
| Chinese Arbalester | Turks Cavalier | 27:19 | 0/3 | 0/0/0 | 0 | — | — |
| Saracens Heavy Cavalry Archer | Spanish Elite Skirmisher | 20:27 | 0/3 | 0/0/0 | 0 | — | — |
| Saracens Hand Cannoneer | Chinese Arbalester | 23:27 | 0/3 | 0/0/0 | 0 | — | — |
| Persians Elite War Elephant | Spanish Halberdier | 13:27 | 0/3 | 0/0/0 | 0 | — | — |
| Varangians Elite Varangian Guard | Chinese Arbalester | 21:27 | 0/3 | 0/0/0 | 0 | — | — |
| Varangians Elite Jarl | Spanish Hussar | 21:27 | 0/3 | 0/0/0 | 0 | — | — |
| Bulgarians Elite Konnik | Turks Heavy Camel Rider | 25:27 | 0/3 | 0/0/0 | 0 | — | — |
| Tupi Elite Blackwood Archer | Spanish Hussar | 27:20 | 0/3 | 0/0/0 | 0 | — | — |

*Descriptive averages over decided runs only, not ranking scores. Review rows remain incomplete.

- [Every run (CSV)](runs.csv), [lossless JSONL](runs.jsonl), [matchup summary](summary.csv), [undecided](undecided.json).
- [Frozen profiles, setup and source hashes](manifest.json); seeds reconstruct every run.
- SQLite commits each run immediately. JSONL can restore the database on another checkout.
- Full per-tick playbacks are saved locally as compressed JSONL in playbacks/.

The checkpoint contains data and source hashes. Engine source publication was not approved; resume requires the frozen engine retained in the cloud workspace. Do not resume using mismatched source files.

Resume from the repository root using Node v24.19.0:

```bash
node aoe2x/js_simulation/node/ranking-campaign.mjs run --campaign aoe2x/js_simulation/calibration/campaigns/unit-rankings-pilot-2026-10-29 --workers 3
```
