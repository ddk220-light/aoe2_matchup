# Farm model comparison with actual online game tests

The model was rerun in a reference-shaped two-farm scenario without changing its mechanics or fitting parameters. These are partial replications because the source does not provide its scenario or exact initial conditions.

## Near versus outer farm: [December 2023 game test](https://www.reddit.com/r/aoe2/comments/18l91t2/did_some_farm_testing_wheelbarrow_math/)

One farm adjacent to a Town Center, another directly outside it. End measurement when each farm empties. Model values are means of five seeds. Food per farmer per game-minute.

| Upgrades | Farm | Published depletion time | Online rate, recomputed | Model rate | Difference |
|---|---|---:|---:|---:|---:|
| None | near | 8:11 | 21.38 | 20.64 | -3.5% |
| None | outer | 10:17 | 17.02 | 16.59 | -2.5% |
| Wheelbarrow + Horse Collar | near | 11:03 | 22.62 | 23.05 | 1.9% |
| Wheelbarrow + Horse Collar | outer | 12:59 | 19.26 | 19.40 | 0.8% |
| Hand Cart + Heavy Plow | near | 15:37 | 24.01 | 23.99 | -0.1% |
| Hand Cart + Heavy Plow | outer | 15:56 | 23.54 | 23.35 | -0.8% |

- Reference is a single reported pair per upgrade level, not a published distribution or shared scenario.
- Exact farm alignment, initial villager positions, civilization, pre-task idle duration, and executable build are unspecified. Scenario Editor mode is reported.
- Our comparison uses east-side farms and the source TC outer box as a solid drop-contact proxy. TC annexes/passability and exact game deposit contact are not reconstructed.
- Default initial pool is zero; separate full-pool diagnostics expose sensitivity to pre-task idle time.
- Rates are recomputed from reported depletion times and standard DAT food budgets; some rounded rates in the post disagree with its times.
- Our endpoint is depletion, before final partial-load deposit, matching the stated measurement as closely as possible.
- The original ten-farm mill results remain unchanged. Similar output does not prove internal movement or civilization modifiers are correct.

## Original ten-farm mill versus older eight-farm TC benchmark

[The 2019/2020 Steam experiment](https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114) is actual DE testing, but differs in geometry, initialization, reseeding and patch. These differences are not isolated simulation error.

| Profile | Published | Our harvested, first 10min | Our banked, first 10min | Harvested difference |
|---|---:|---:|---:|---:|
| none | 20.30 | 18.35 | 17.88 | -9.6% |
| wheelbarrow | 22.78 | 20.71 | 20.10 | -9.1% |
| wheelbarrow-plow | 23.16 | 21.93 | 21.28 | -5.3% |
| full | 24.40 | 23.76 | 22.97 | -2.6% |

The source forces an endpoint deposit, so our harvested column is more comparable to its resource accounting than our unflushed banked column. Layout and maintenance still differ materially.

## Additional independent observations

[June 2025 forum tests](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183) report farm rates of 20.07 base, 22.34 with Wheelbarrow + Horse Collar, and 23.62 with Hand Cart + Heavy Plow. The farm setup is insufficiently specified for matched error calculations. They support the general scale; they do not validate the ten-farm mill arrangement.

[February 2025 multiplayer testing](https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/) supports the roughly 24/min cap. Its author withdrew higher single-player results as a multiplayer benchmark. Other simulators such as AoEBuddy are excluded as independent DE measurements.

Conclusion: upgraded output and the reduction of the outer-farm penalty are supported by measured game results. The unupgraded discrepancy remains visible. No exact ten-farm mill recording was found; exact work-stop policy and collision/deposit behavior remain unvalidated.
