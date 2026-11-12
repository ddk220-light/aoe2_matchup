# Economy and close-matchup review

This is an economic attrition screen, not a rerun of reinforced combat. A battlefield loser can lose less replacement labor than the winner. That can support a prolonged-war strategy, but does not erase the winner’s surviving army or positional advantage.

Source: the user-supplied Google Drive DAT archive and its 56 civilization tech trees. The archive dates the DAT to 2026-10-29 (timezone unspecified). Its stored provenance identifies patch 188329 balance changes; the exact executable version is not embedded in the file. No external bonus tables were substituted.

DAT SHA-256: `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`.

## Coverage

- civilizations: 56
- unit_variants: 1030
- resource_rows: 224
- modeled_resource_rows: 223
- source_battle_runs: 7600
- matchup_rows: 3591
- close_battle_contexts: 2280
- close_matchup_directions: 781
- economic_candidate_directions: 150
- strongest_candidate_directions: 12
- queue_advantage_directions: 96
- shared_research_faster_directions: 30
- shared_research_cheaper_directions: 157
- gold_exhaustion_directions: 116
- conditional_candidate_directions: 27
- unresolved_close_contexts: 45

The analysis expands mechanically equivalent battle results using each actual civilization’s economy. Counts of matchup directions and seed contexts are not independent new simulations.

## Strongest modeled attrition reversals

Every recorded seed has the same close winner; replacement-labor advantage survives the stated ±5% rate sensitivity; no flagged conditional mechanics. This is a screening definition, not 95% confidence.

| Battlefield loser | Battlefield winner | Winner HP left | Loser replacement-labor saving | Loser buildings per one winner building | Close seeds |
|---|---|---:|---:|---:|---:|
| Byzantines Halberdier | Spanish Paladin | 6.4% | 37.0% | 2 | 3/3 |
| Spanish Halberdier | Burmese Elite Battle Elephant | 8.0% | 22.1% | 3 | 3/3 |
| Chinese Arbalester | Goths Heavy Scorpion | 12.5% | 22.1% | 2 | 3/3 |
| Chinese Arbalester | Mayans Heavy Scorpion | 12.5% | 21.4% | 2 | 3/3 |
| Chinese Arbalester | Gurjaras Heavy Scorpion | 12.5% | 19.3% | 2 | 3/3 |
| Chinese Arbalester | Persians Heavy Scorpion | 12.5% | 16.4% | 2 | 3/3 |
| Chinese Arbalester | Wu Heavy Scorpion | 12.5% | 16.4% | 2 | 3/3 |
| Magyars Halberdier | Spanish Paladin | 10.2% | 16.0% | 2 | 3/3 |
| Portuguese Halberdier | Spanish Paladin | 10.2% | 16.0% | 2 | 3/3 |
| Vikings Pikeman | Spanish Paladin | 9.8% | 16.0% | 2 | 3/3 |
| Khmer Halberdier | Spanish Paladin | 10.2% | 14.0% | 2 | 3/3 |
| Chinese Arbalester | Armenians Heavy Scorpion | 12.5% | 12.0% | 2 | 3/3 |

Cheap armies may need more production buildings because they replace more bodies. The building column is the maximum over the observed close seeds: ceil(loser deaths / floor(winner queue seconds / loser unit train seconds)). This respects whole-unit queues; no finite building count helps if even one loser unit takes longer than the winner’s recovery window. `extra_building_payback_exchanges` estimates how many repeated economic savings fund the extra building resource costs; construction labor, build delay and reinforcements walking to the battlefield are excluded, so this is a capital-cost diagnostic, not a combat schedule.

All close results—including non-reversals, variable winners, unresolved cases and gold-exhaustion candidates—are in `matchup-summary.csv` and SQLite. Shared/exclusive upgrade comparisons are in `upgrade_comparisons`; detailed research and production tables include all routes and costs.

## Other advantages in close losses

| Advantage for battlefield loser | Matchup directions |
|---|---:|
| Faster one-building replacement queue in at least one close seed | 96 |
| Less time for the common research package | 30 |
| Cheaper common research package | 157 |
| Gold-free unit facing a gold-costing winner | 116 |

These categories overlap and are not additional proven reversals. Common research is matched by technology ID; cheaper means no resource costs more and at least one costs less, after source-recorded rewards. Exclusive upgrades and research-building costs remain separate. Research speed can indicate an earlier timing opportunity, but cannot change the already fully upgraded battle on its own. Gold exhaustion requires a finite-gold scenario.

## Gather rates

| Civilization | Food/min | Wood/min | Gold/min | Stone/min | Farm wood/food |
|---|---:|---:|---:|---:|---:|
| Armenians | 23.56 | 30.88 | 29.45 | 23.77 | 0.1600 |
| Aztecs | 23.72 | 29.13 | 27.62 | 26.00 | 0.1091 |
| Bengalis | 23.52 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Berbers | 23.66 | 28.64 | 27.36 | 25.97 | 0.1091 |
| Bohemians | 23.68 | 30.95 | 27.40 | 26.21 | 0.1600 |
| Britons | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Bulgarians | 23.52 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Burgundians | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 |
| Burmese | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Byzantines | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 |
| Celts | 23.53 | 31.41 | 27.06 | 25.59 | 0.1600 |
| Chinese | 23.53 | 30.43 | 27.06 | 25.59 | 0.1455 |
| Cumans | 23.52 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Danes | 23.53 | 28.24 | 27.06 | 25.59 | 0.1600 |
| Dravidians | 23.53 | 30.43 | 23.75 | 22.44 | 0.1600 |
| Ethiopians | 23.53 | 30.43 | 27.06 | 25.59 | 0.1600 |
| Franks | 23.54 | 28.24 | 27.06 | 22.44 | 0.1091 |
| Georgians | 23.54 | 28.02 | 23.91 | 25.90 | 0.1091 |
| Goths | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Gurjaras | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Hindustanis | 23.53 | 30.43 | 29.09 | 25.59 | 0.1600 |
| Huns | 23.53 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Incas | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Italians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Japanese | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Jurchens | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 |
| Khitans | unresolved | 30.43 | 23.75 | 25.59 | 0.3429 |
| Khmer | 23.78 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Koreans | 23.56 | 30.43 | 27.06 | 30.14 | 0.1600 |
| Lithuanians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Magyars | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Malay | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Malians | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Mapuche | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Mayans | 23.44 | 31.01 | 23.78 | 25.79 | 0.0949 |
| Mongols | 23.53 | 28.24 | 27.06 | 25.59 | 0.1600 |
| Muisca | 23.54 | 30.43 | 27.07 | 25.59 | 0.1091 |
| Persians | 23.52 | 30.43 | 27.06 | 25.59 | 0.1091 |
| Poles | 26.51 | 28.24 | 23.75 | 25.59 | 0.1091 |
| Portuguese | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Romans | 24.73 | 29.44 | 28.14 | 23.72 | 0.1091 |
| Saracens | 23.53 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Saxons | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Shu | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Sicilians | 23.80 | 28.24 | 27.06 | 25.59 | 0.0589 |
| Slavs | 27.09 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Spanish | 23.57 | 30.43 | 23.75 | 25.59 | 0.1600 |
| Tatars | 23.54 | 28.24 | 27.06 | 22.44 | 0.1091 |
| Teutons | 23.52 | 30.43 | 23.75 | 25.59 | 0.0655 |
| Tupi | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |
| Turks | 23.56 | 30.43 | 32.61 | 22.44 | 0.1600 |
| Varangians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Vietnamese | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |
| Vikings | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |
| Wei | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |
| Wu | 23.56 | 30.43 | 27.06 | 25.59 | 0.1600 |

## Limits that matter

- Khitan pasture food gathering is unresolved: the source has distinct herders, shared/annex objects and animal resources. No generic farm rate was substituted. Food-consuming Khitan units remain unscored for labor.
- Church auras, coupled resource generation and death refunds are retained as explicit conditional flags. Relics, trade, garrison income, combat bounties, starting resources and free-upgrade timing are outside the settled post-Imperial villager baseline.
- Farm motion remains an approximation; prior online comparisons have errors up to about 3%. Extra work stops and special-civilization trajectories are not validated against current DE captures. Three model seeds do not measure real-game uncertainty.
- Rates depend on the stated layout, congestion, resource depletion and sampling window. Faster raw work or movement need not produce a monotonic gain in a small congested simulation.
- Production queues, building capital and upgrades are separate dimensions. Research totals are common-tech workload, not simultaneous completion time. Missing upgrades do not earn a speed bonus.
- Konnik dismounting and other flagged casualty/refund effects cannot be treated as ordinary replaceable deaths. Survivor HP damage is recorded separately; survivors may heal without replacing the unit.
- The database is a complete joined review inventory for the supplied advisor roster; it is not a claim that every compiled-engine economic hook now has a validated numerical model.

## Reproduce

Run `python tools/export_army_economy.py`, `node tools/run_army_economy.mjs`, then `python tools/build_army_context.py`. Original source databases and battle results are read-only inputs.

Run `python tools/validate_army_context.py` to compare every copied source row, preserve saved battle outcomes, verify civilization identities and recompute casualty, labor, whole-unit queue and common/exclusive research relationships. Results are in `independent-validation.json`. Engine tests are `tools/farm-bonuses.test.mjs`, `tools/farm-gathering-sim.test.mjs`, `tools/gold-mining-sim.test.mjs`, and `tools/wood-gathering-sim.test.mjs`.
