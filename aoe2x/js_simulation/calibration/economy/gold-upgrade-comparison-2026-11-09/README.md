# Gold gathering without upgrades and reference comparisons

The engine is unchanged. Profile exports replay only selected source technology effects; no upgrades means 0.38 nominal gold/game-second, 0.8 tiles/game-second and carry 10. Civilization and team gathering bonuses are absent. Geometry/positions remain the same four-tile square and one-tile camp gap.

## Unupgraded results

| Case | Gold/worker/minute | Measurement |
|---|---:|---|
| Forgotten Empires, no bumping | 21.58 | 27.8 seconds per 10 gold |
| One worker | 21.57 | Completed deposit cycles |
| ten-no-upgrades-walk-only | 20.14 | Inventory-adjusted 120–420s |
| ten-no-upgrades | 19.32 | Inventory-adjusted 120–420s |
| eight-no-upgrades | 19.40 | Inventory-adjusted 120–420s |

The ten-worker first minute deposits **130.00 gold**, retains **66.61 gold carried**, and extracts **196.61 gold**.

## All nine published upgrade combinations

[Forgotten Empires reference](https://www.forgottenempires.net/strategy/age-of-empires-ii-strategy-center/gold-relics) supplies a 3×3 table of mining upgrades versus carry upgrades. Each row below is an independent one-worker simulation using the same engine and geometry; rates are computed from completed delivery cycles.

| Mining | Carry/movement | Reference | Simulation | Difference |
|---|---|---:|---:|---:|
| No mining upgrades | No carry upgrades | 21.58 | 21.57 | -0.057% |
| No mining upgrades | Wheelbarrow | 21.90 | 21.93 | 0.129% |
| No mining upgrades | Wheelbarrow + Hand Cart | 22.22 | 22.28 | 0.239% |
| Gold Mining | No carry upgrades | 24.59 | 24.61 | 0.069% |
| Gold Mining | Wheelbarrow | 25.21 | 25.07 | -0.553% |
| Gold Mining | Wheelbarrow + Hand Cart | 25.53 | 25.53 | -0.013% |
| Both mining upgrades | No carry upgrades | 28.04 | 28.04 | 0.007% |
| Both mining upgrades | Wheelbarrow | 28.57 | 28.64 | 0.251% |
| Both mining upgrades | Wheelbarrow + Hand Cart | 29.27 | 29.24 | -0.089% |

Maximum absolute difference: **0.553%**. This supports the mining/hauling arithmetic and contact-distance interpretation across upgrade states, rather than only at the fully upgraded point. The source is rounded to 0.1 second and its patch is unspecified; small differences should not be over-interpreted. It expressly excludes bumping.

## Independent measurements and comparability

- [DE gold crowding test by akimbofmg9 (2020)](https://www.reddit.com/r/aoe2/comments/hw06k7/villager_overcrowding_does_anyone_know_how_mining/): Independent qualitative crowding comparison: ten Arabia shapes plus a two-tile stress case; camp pre-built, workers pre-positioned. **Limit:** Layout differs; upgrade state and exact inventory-endpoint accounting are not explicit in the retrieved comment; rates are not a matched target for our square.
- [Four-tile, ten-worker mining camp test (2025)](https://www.reddit.com/r/aoe2/comments/1ibcnqu/where_to_place_your_mining_camp_and_how_many/): Confirms someone tested the same tile/worker counts and gap without mining/Wheelbarrow/Hand Cart upgrades. **Limit:** No duration or exact mine shape supplied. The 890-gold total cannot be converted to gold/minute.
- [DE vs Voobly resource pathing test (2021)](https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/): Additional severe-crowding observation, about 11.61 gold/worker-minute. **Limit:** Different worker count and patch geometry; camp count/placement and upgrades are not fully specified. Not simulated as a matched scenario.

Our eight-worker square gives 19.40 gold/worker-minute, below the independent 20–21.6 range. This is a warning that the current setup/model is more costly in walking and/or congestion. The layout, task assignments, game version and unspecified upgrade/endpoint details prevent assigning the entire difference to the collision model. No penalty, radius or work rate was adjusted to fit these reports.

## Longer window and timestep sensitivity

| Case | 120–420s, adjusted | 120–720s, adjusted | 120–720s, banked only | Depleted tiles at 720s |
|---|---:|---:|---:|---:|
| ten-no-upgrades-walk-only | 20.14 | 20.18 | 20.30 | 0 |
| ten-no-upgrades | 19.32 | 19.48 | 19.20 | 0 |
| eight-no-upgrades | 19.40 | 19.66 | 19.50 | 0 |

| Step | Ten-order-variant mean | Minimum | Maximum |
|---|---:|---:|---:|
| 0.0125s | 19.4210 | 19.1673 | 19.7363 |
| 0.00625s | 19.4898 | 19.1720 | 19.7947 |

Halving the timestep changes the ten-variant mean by 0.354%. This is a numerical-sensitivity check, not validation against DE. Resource conservation, speed limits and rigid-body non-overlap pass for these runs.

## Reproduce

```sh
python tools/export_gold_mining_fixture.py --grid-output aoe2x/js_simulation/calibration/economy/gold-upgrade-comparison-2026-11-09
node tools/run_gold_upgrade_comparison.mjs
```

The folder includes nine frozen fixtures, the full reference grid, three crowd traces, the single-worker trace, comparisons and source metadata. The prior fully upgraded experiment remains at `../gold-2026-11-09/`.

## Plot

[Comparison plot](comparison.png) · [Reference grid CSV](reference-grid.csv)
