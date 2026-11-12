# Generic post-Imperial gold mining: first simulation

**Model estimate. No matching current-DE gathering capture has been validated.**

Ten villagers, four 800-gold tiles in a 2×2 square, one 2×2 Mining Camp separated by a one-tile gap, all standard mining/movement/carry upgrades. Source values are from the user-supplied DAT (SHA-256 `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`).

## Reference comparison

The [Forgotten Empires reference](https://www.forgottenempires.net/strategy/age-of-empires-ii-strategy-center/gold-relics) gives 20.5 seconds per 10 gold, or **29.27 gold per villager-minute**, one tile from the camp with Gold Shaft Mining and Hand Cart. It excludes bumping and does not identify its patch or precise geometry.

| Case | Gold/villager/minute | Difference from reference |
|---|---:|---:|
| Reference, no bumping | 29.27 | — |
| One simulated worker, completed delivery cycles | 29.24 | -0.09% |
| Ten workers, walking only, inventory-adjusted 120–420s | 28.07 | -4.10% |
| Ten workers, with rigid-body collisions, inventory-adjusted 120–420s | 27.06 | -7.53% |

The single-worker cycle is derived from source work, rounded carry 20 and a 0.6-tile center travel each way at 0.968 tiles/second. There is no fitted rate multiplier. Agreement checks this model’s uncongested cycle; it does not validate DE crowd navigation. The four-tile setup adds walking around the patch and simulated congestion.

## Requested first minute

| Time window | Deposited | Carried at start | Carried at end | Gold extracted |
|---|---:|---:|---:|---:|
| 0–60 seconds | 200.00 | 0.00 | 70.10 | 270.10 |
| 120–180 seconds | 300.00 | 141.03 | 114.30 | 273.27 |
| 120–420 seconds | 1420.00 | 141.03 | 74.20 | 1353.18 |

For the 120–420s window, deposited gold alone gives 28.40 per worker-minute. Its carried inventory changes by -66.82 gold, so the inventory-adjusted rate is 27.06. Both quantities are reported: carried gold is not spendable until deposited. The adjusted rate controls load-cycle endpoint bias; it is not the banked amount at a deadline.

Time shares for ten workers over 120–420s: working 89.75%, walking 8.20%, blocked 2.05%. Enabling collisions changes both path length and blocked time; the total reduction versus the walking-only run is 3.58%.

## Diagnostics

| Case | Inventory-adjusted gold/villager/minute, 120–420s | Depleted tiles at end |
|---|---:|---:|
| single-worker | 29.16 | 0 |
| ten-walk-only | 28.07 | 0 |
| ten-workers | 27.06 | 0 |
| five-workers | 27.58 | 0 |
| fifteen-workers | 25.58 | 1 |
| gap-zero | 26.08 | 0 |
| gap-two | 25.93 | 0 |
| fractional-carry | 27.45 | 0 |

The fifteen-worker trial includes depletion and retargeting, so its complete-window rate also reflects changed resource geometry. The gap-zero trial starts workers in legal positions around the accessible sides; initial geometry differs from the baseline.

## Numerical sensitivity

| Timestep (game seconds) | Mean over ten initial-order variants | Minimum | Maximum |
|---|---:|---:|---:|
| 0.1 | 27.6967 | 27.5972 | 27.7966 |
| 0.05 | 27.6522 | 27.5360 | 27.7524 |
| 0.025 | 27.2037 | 26.9393 | 27.5102 |
| 0.0125 | 27.0920 | 26.9292 | 27.2974 |
| 0.00625 | 27.0665 | 26.7872 | 27.4165 |

The default is 0.0125 seconds (80 Hz), selected after testing timestep sensitivity. Halving it changes the ten-variant mean by -0.094%. The largest change within a paired variant is 1.869%; individual path interactions remain sensitive. These variants change initial update order/target ties, not the assumed work rate or DE RNG.

Resource conservation, speed limits, static-obstacle exclusion, rigid-body non-overlap, full-load timing, deterministic replay, analytic single-worker cycle and finite-resource depletion are checked. Test output is in `test-results.txt`.

## Model assumptions and remaining fidelity limits

- Generic mining inputs from Byzantine records; no civilization/team bonuses used.
- Carry rounded to nearest integer after each technology, consistent with historical community tests; current DE not captured.
- Workers are rigid circles of source radius; minimum collision multiplier is preserved but not activated.
- Gold and camp are rectangles; navigation uses conservative expanded-rectangle corners.
- Continuous source work rate; instantaneous deposit and task switch at contact.
- Workers return to their assigned gold object, selecting reachable contact points; retarget on depletion.
- Visibility routing around current worker positions; blocked paths retry after 0.5 game-seconds.
- Movement updates are sequential, priority rotates once per game-second; no physical pushing.
- No parameter is fitted to the external reference; this is an unvalidated economic model.

The [DE Infosheet](https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705) provides historical support for effective carry 20; current rounding still needs a matched capture. The [four-tile community test](https://www.reddit.com/r/aoe2/comments/1ibcnqu/where_to_place_your_mining_camp_and_how_many/) uses ten workers and a one-tile gap but explicitly no upgrades and no stated duration; it supplies no comparable rate.

## Files

- `playback.html`: standalone animation with timeline, worker states, inventory, reference table and diagnostic plots.
- `fixture.json`: source-derived inputs, technology evidence, geometry and assumptions.
- `ten-workers.json`, `single-worker.json`, `ten-walk-only.json`: sampled trajectories, bank/inventory histories and exact deposit events.
- `comparison.json`, `results.csv`: full trial windows, numerical comparisons and checks.
- `manifest.json`: source identity, code hashes and reproduction commands.

No battle-simulation code, serving database or advisor UI was changed.

## Playback verification and plot

[Open playback](playback.html) · [Comparison plot](comparison.png)

Chromium checks: 9 passed, including animation, time seeking, trial selection, reset, mobile layout and no JavaScript errors. Desktop/mobile screenshots are included.
