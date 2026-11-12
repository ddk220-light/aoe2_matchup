# Wood gathering simulation and reference comparison

**Prototype model estimate; current-DE same-layout gathering has not been validated.**

Source is the supplied DAT (SHA-256 `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`). No civilization bonuses. Standard full upgrades are Double-Bit Axe, Bow Saw, Two-Man Saw, Wheelbarrow and Hand Cart; Sappers is excluded.

Default scenario: one 2×2 Lumber Camp, one empty tile from an eight-wide/six-deep forest of 48 oak trees. Each tree has source HP 20, 100 wood and a 1×1 footprint. Ten workers initially stand along the front edge. The camp stays fixed and depleted trees disappear, exposing deeper trees.

## Main results

| Profile | Active-work ceiling | First minute, adjusted | Minutes 2–7 | Minutes 7–12 |
|---|---:|---:|---:|---:|
| No upgrades | 23.40 | 20.82 | 19.38 | 17.78 |
| All standard upgrades | 37.07 | 33.92 | 31.24 | 28.38 |

Units: wood per worker per game-minute. Rates count banked wood plus changes in carried inventory; carried wood is not yet spendable. Active-work ceilings exclude felling and all movement and are not delivered-rate predictions.

| Profile, first minute | Banked wood | Still carried | Wood removed from trees |
|---|---:|---:|---:|
| No upgrades | 180.00 | 28.22 | 208.22 |
| All upgrades | 200.00 | 139.18 | 339.18 |

## Crowding, felling and recession diagnostics

| Case | Minutes 2–7 | Minutes 7–12 |
|---|---:|---:|
| none-ten | 19.38 | 17.78 |
| full-ten | 31.24 | 28.38 |
| none-ten-walking | 19.51 | 17.49 |
| full-ten-walking | 31.33 | 28.12 |
| bow-saw-ten | 28.80 | 26.57 |
| double-bit-four-adjacent | 26.31 | 24.55 |
| full-four-adjacent | 35.14 | 32.93 |
| double-bit-four-gap-one | 24.46 | 22.82 |
| full-four-gap-one | 33.68 | 31.69 |
| full-ten-historical-felling | 31.30 | 28.35 |
| full-ten-prefelled | 31.41 | 28.48 |

Pre-felled trees and historical felling timing are labelled diagnostics. Felling lowers HP without harvesting; collecting depletes the separate wood store. Workers with partial loads keep them when moving to a new tree.

Current DAT attack: 15 total damage against armor-less trees, reload 2 seconds, animation 2 seconds, coded frame_delay 0. The default assumes the first hit at half animation (1s), then a second hit after reload (total 3s). The precise worker-task impact timing is unresolved. Historical 2.25s felling and no-felling runs show sensitivity rather than silently replacing current inputs.

## Published comparisons

| Reference | Published wood/worker/min | Our related case | Model value | Comparability |
|---|---:|---|---:|---|
| [2025 test](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/), Double-Bit Axe | 23.50 | 4/camp, adjacent, 14min | 25.29 | Density/horizon match; forest/gap/other upgrades unspecified |
| [2025 test](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/), fully upgraded | 31.60 | 4/camp, adjacent, 14min | 33.92 | Same limits; gross output comparison |
| [2025 test](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/), Double-Bit Axe | 23.50 | 4/camp, one-tile gap, 14min | 23.68 | Camp gap is a scenario assumption, not specified by source |
| [2025 test](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/), fully upgraded | 31.60 | 4/camp, one-tile gap, 14min | 32.56 | Same limits |
| [2019 analysis](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/), fully upgraded | 30.42 | 10/camp, minutes 2–12 | 29.81 | Older light-congestion analytical estimate |
| [2019 analysis](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/), no Two-Man Saw | 28.32 | Bow Saw + Hand Cart, minutes 2–12 | 27.68 | Same limits |
| [2021 DE test](https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/), 12/camp, 3min | 20.94 | 12/camp, 3min, assumed no upgrades | 20.09 | Exact upgrades/layout/endpoint carry unspecified |

These are independent references, not matching DE scenarios. The four-worker one-tile-gap alternatives are exported too; changing camp placement changes the result. No work, movement, collision or delay parameter was adjusted to fit reference values.

## Twelve upgrade combinations: one worker

| Wood level | Carry level | Nominal | Minutes 2–7 | Minutes 7–12 |
|---|---|---:|---:|---:|
| 0 | 0 | 23.40 | 21.88 | 21.80 |
| 0 | 1 | 23.40 | 22.32 | 22.12 |
| 0 | 2 | 23.40 | 22.68 | 22.52 |
| 1 | 0 | 28.08 | 25.97 | 25.68 |
| 1 | 1 | 28.08 | 26.52 | 25.93 |
| 1 | 2 | 28.08 | 26.99 | 26.48 |
| 2 | 0 | 33.70 | 30.39 | 29.86 |
| 2 | 1 | 33.70 | 31.05 | 30.74 |
| 2 | 2 | 33.70 | 31.82 | 31.69 |
| 3 | 0 | 37.07 | 33.06 | 32.17 |
| 3 | 1 | 37.07 | 33.99 | 33.00 |
| 3 | 2 | 37.07 | 34.85 | 34.29 |

Wood levels: 0 none, 1 Double-Bit Axe, 2 +Bow Saw, 3 +Two-Man Saw. Carry levels: 0 none, 1 Wheelbarrow, 2 +Hand Cart. Nominal gathering multiplies by 1.2, 1.2, 1.1; carry rounds after each selected upgrade.

## Numerical sensitivity

| Profile | Step | Mean over three update-order variants |
|---|---:|---:|
| No upgrades | 0.025 | 19.2932 |
| No upgrades | 0.0125 | 19.3230 |
| No upgrades | 0.00625 | 19.2278 |
| Full | 0.025 | 31.2510 |
| Full | 0.0125 | 31.1671 |
| Full | 0.00625 | 30.9952 |

No upgrades: mean change when halving 0.0125s to 0.00625s = -0.493%.
Full: mean change when halving 0.0125s to 0.00625s = -0.551%.

Checks enforce wood conservation, speed limits, rectangular obstacle exclusion and rigid worker non-overlap. Unit tests cover source upgrade values, felling before gathering, nominal collection, tree depletion, partial loads and deterministic behavior.

## Assumptions

- Generic Byzantine lumberjack values; only selected standard economic upgrades applied. Sappers is absent.
- Live tree: source 20 HP and 100 wood. Felling HP and remaining wood are separate. Felled tree keeps its resource footprint until depleted.
- No armor entries on tree; summed worker attack classes give 15 damage per swing, two swings to fell.
- First swing assumed at half of the current DAT 2-second animation; subsequent swings use coded reload 2 seconds. Raw frame_delay=0 does not resolve worker-task impact timing.
- Historical measured 2.25-second total felling is a separate sensitivity case, not silently imposed on the current DAT.
- Rigid circular workers and conservative rectangular resource obstacles reuse the gold experiment geometry/pathfinder.
- Instant deposits at contact. Partial loads continue to the next tree; all resources exhausted causes final partial deposit.
- Workers return to their tree while it is available, choose another accessible tree on depletion or blocked destination, and retry blocked paths after 0.5 game-seconds.
- No camp rebuilding. Depletion exposes inner trees and removes empty-tree obstacles; stumps do not obstruct.
- One fixed camp, eight-tile-wide six-deep forest, workers initially spread on the front edge at 0.6-tile center spacing.
- Observed rates are scenario/model estimates; the same-layout current DE trajectories have not been captured.

## Files and reproduction

`fixture-w*-c*.json` contain source technology evidence and raw inputs; `felling-source.json` includes the fresh DAT attack/animation subset. `comparison.json` and `results.csv` hold all results. Trace files record positions, tree HP/wood, inventories, swings, tree depletion and deposit events.

```sh
/workspace/scratch/production-effects-trace/.venv/bin/python tools/extract_wood_felling_source.py
python tools/export_wood_gathering_fixtures.py
node tools/wood-gathering-sim.test.mjs
node tools/run_wood_gathering_review.mjs
```

## Plot and playback

[Interactive forest playback](playback.html) · [Comparison plot](comparison.png)

Verification: six mechanics tests and nine Chromium playback checks passed. All selected upgrade commands match the raw source; generic wood task multiplier 189 is 1. The gold experiment geometry code remains unchanged. `validation.json` records checks.

The frozen fixtures let you rerun the Node simulation without re-extracting the DAT.
