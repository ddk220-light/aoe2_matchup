# Farming walking audit

A routing defect was reproduced independently of gather-rate benchmarks: a farther clear building contact could win over a shorter safe detour to a nearer contact. Farms now compare those alternatives on the existing visibility graph. Mining and wood keep their existing default routing behavior.

Example: 3.900 tiles before, 2.480 tiles after. 61 of 744 valid static test arrangements admit a shorter route. These are synthetic geometry tests, not observed DE paths.

## Rates before and after

| Scenario | Upgrades | Position | Before difference | After difference |
|---|---|---|---:|---:|
| TC | none | near | -3.533% | -2.985% |
| TC | none | outer | -2.070% | -1.538% |
| TC | wheelbarrow | near | 1.774% | 1.219% |
| TC | wheelbarrow | outer | 0.574% | 0.223% |
| TC | full | near | -0.114% | -0.202% |
| TC | full | outer | -0.730% | -0.887% |
| 3x3 ring | none | side | 0.835% | 0.835% |
| 3x3 ring | none | corner | 2.897% | 2.897% |

TC uses the same 32 seeds and mean-of-individual-rates estimator as the previous review. The 3×3 ring uses the same 36 seeds and reciprocal-mean-lifetime estimator as its published table. Every result remains visible. The 3×3 source does not explain how Folwark instant collection was excluded, so that comparison remains conditional.

## Distances implied by the current work-point policy

| Geometry | Outbound tiles | Return tiles | One internal move |
|---|---:|---:|---:|
| TC near | 1.300 | 1.812 | 1.635 |
| TC outer | 4.300 | 4.473 | 1.635 |
| 3x3 side | 1.300 | 1.812 | 1.635 |
| 3x3 corner | 2.106 | 2.152 | 1.635 |

These enumerate all nine start points and all 72 distinct-point return/internal pairs, without other villagers. A return to a different random point need not equal the outbound distance. Rigid collision shapes, exact stop/return selection and contact geometry remain assumptions.

## Original ten-farm mill

| Profile | Before food/villager/min | After |
|---|---:|---:|
| none | 18.3579 | 18.3649 |
| full | 23.7566 | 23.7558 |

Five seeds, 600 seconds, reseeding enabled; this is a model-to-model regression check, not a new live benchmark.

## Evidence and limits

- Walking speeds 0.800 / 0.880 / 0.968 tiles per game-second are replayed from the user DAT and Wheelbarrow/Hand Cart effects. No speed or collision-radius tuning was applied.
- [Official update 50292](https://www.ageofempires.com/news/aoe2de-update-50292/) confirms centering farm work. It does not specify the exact current work-point selection algorithm.
- [2020 community analysis](https://www.reddit.com/r/aoe2/comments/k3bxdp/the_universal_farming_equation/) describes random return points, but contains fitted pause assumptions and subsequent corrections. It is insufficient to establish a new stop-distance or delay parameter.
- [Official update 185872](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/) documents changes to drop-off behavior. Historical game measurements cannot prove current path equivalence.
- [TC benchmark](https://www.reddit.com/r/aoe2/comments/18l91t2/did_some_farm_testing_wheelbarrow_math/) and [repeated 3×3 reference](https://vixark.com/age-of-empires-ii/folwark) do not provide trajectories. Correct graph routing does not prove that DE chooses shortest paths.
- Current run traces include cumulative travel distance and blocked time at each state change, allowing actual per-leg comparisons once a DE recording is available.
