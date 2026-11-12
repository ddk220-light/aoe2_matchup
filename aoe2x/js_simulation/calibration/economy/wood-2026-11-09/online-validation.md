# Online evidence audit for wood gathering

Partial corroboration of rates and basic mechanics; exact current-DE navigation/felling behavior remains unvalidated.

Public sources checked on 2026-11-09. Existing simulation outputs were reused; no engine parameter was changed to match a source.

## Comparable totals and endpoint accounting

All rates below are wood per worker per game-minute. The source column is the reported rate; its inventory endpoint definition is not always explicit.

| Case | Online rate | Model banked | Difference | Model with carry change | Difference |
|---|---:|---:|---:|---:|---:|
| [Double-Bit Axe, four workers/camp, one-tile gap](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/) | 23.50 | 23.21 | -1.22% | 23.68 | +0.76% |
| [Fully upgraded, four workers/camp, one-tile gap](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/) | 31.60 | 31.43 | -0.54% | 32.56 | +3.05% |
| [Double-Bit Axe, adjacent camp alternative](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/) | 23.50 | 25.00 | +6.38% | 25.29 | +7.61% |
| [Fully upgraded, adjacent camp alternative](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/) | 31.60 | 32.86 | +3.98% | 33.92 | +7.34% |
| [12 workers, one camp, three minutes](https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/) | 20.94 | 18.89 | -9.81% | 20.09 | -4.08% |
| [Fully upgraded older analytical estimate](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/) | 30.42 | 29.50 | -3.02% | 30.29 | -0.44% |
| [Without Two-Man Saw, older analytical estimate](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/) | 28.32 | 27.17 | -4.07% | 28.13 | -0.66% |

The strongest low-density comparison is the 14-minute, four-worker-per-camp experiment. One-tile-gap banked rates differ by -1.22% for Double-Bit Axe and -0.54% fully upgraded; the carry-adjusted differences are +0.76% and +3.05%. Adjacent-camp cases are higher and retained above rather than omitted. Matching worker/camp density and duration does not establish matching geometry or upgrades.

The twelve-worker test is less reassuring: banked output is 680 wood against the published 754, a 9.81% deficit. Adding the 43.21 wood still carried gives 723.21 harvested, reducing the numerical gap to 4.08%, but the source does not establish that this is its measurement definition. This discrepancy cannot be labelled a pass.

The older analytical estimates agree in broad scale, but are weaker evidence than a controlled current-game experiment. The previous report labelled this source as 2019; the exact publication year is unverified in the fetched page, so this audit avoids that date attribution.

## Mechanics

- [The DE Infosheet](https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705) corroborates the 20-HP/15-damage/two-hit generic-tree calculation.
- Exact impact timing remains unresolved: the historical report gives 2.25 seconds, while the current model assumes 3 seconds from different current DAT animation/reload fields. The already-run historical-timing sensitivity changes full-run collection from 30.2851 to 30.3749 wood/worker-minute (+0.297%). This small rate effect does not prove either timing model correct.

## Source quality

- [2025 direct test](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/): twelve lumberjacks, three camps, fourteen minutes; exact forest/spacing/civ and endpoint inventory unspecified.
- [2021 direct test](https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/): twelve workers, one camp, three-minute trials; source supplies total wood but not all upgrade/geometry details.
- [Older wood analysis](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/): analytical full-upgrade and no-Two-Man-Saw rates; light congestion and older assumptions.
- [AoE Buddy](https://aoebuddy.com/villager-calculator) explicitly describes measurements in its own engine. It was reviewed but excluded as independent DE validation.
- Spirit of the Law video fetching failed; uninspected video values were not used.

## Assessment

The model has partial external support for low-density rates and generic hit counts. A same-layout current-DE observation is still needed to validate busy-camp navigation, exact felling timing and target selection. Published references do not justify treating the numerical/model-invariant test passes as proof of DE fidelity.
