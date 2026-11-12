# Farm refinement: depletion timing correction

A real state-ordering bug was fixed. The improvement against the published rates is modest; this is not a fitted one-percent model. The original review artifacts remain in ../farms-2026-11-09/.

## What changed

1. Gathering ends at the exact reserve-plus-pool depletion time, including when it occurs within a simulation step. Previously the integrator consumed the rest of that step.
2. Depletion takes precedence over the next internal work-spot move. Previously an exact quarter-load ending could send a farmer to an already-empty spot.
3. The benchmark reads an explicit depletion event, rather than inferring depletion from the later walk-to-mill transition.

For no-upgrade seed 0 / near farm, the resource emptied at 512.476s but the old benchmark reported 514.726s after an unnecessary walk. The fixed event reports 512.476s. Full before/after events are in depletion-trace-example.json.

No gathering, movement, collision, carry, work-stop count or deposit-distance parameters were tuned. Reseeding order remains provisional: construction auto-deposit alone does not establish whether automatic reseeding first makes a mill trip.

## Same five seeds as the previous comparison

Rates: food per farmer per game-minute. Reference: [2023 near/outer farm lifetime test](https://www.reddit.com/r/aoe2/comments/18l91t2/).

| Profile | Farm | Online | Before | After | Before error | After error |
|---|---|---:|---:|---:|---:|---:|
| No upgrades | near | 21.38 | 20.64 | 20.72 | -3.49% | -3.11% |
| No upgrades | outer | 17.02 | 16.59 | 16.66 | -2.50% | -2.10% |
| Wheelbarrow + Horse Collar | near | 22.62 | 23.05 | 23.05 | +1.86% | +1.86% |
| Wheelbarrow + Horse Collar | outer | 19.26 | 19.40 | 19.40 | +0.76% | +0.77% |
| Hand Cart + Heavy Plow | near | 24.01 | 23.99 | 23.99 | -0.08% | -0.07% |
| Hand Cart + Heavy Plow | outer | 23.54 | 23.35 | 23.35 | -0.78% | -0.78% |

## Thirty-two paired seeds

Both old and fixed engines run the same seeds 0–31. This prevents selecting a favorable short random sample. Model variation is not the uncertainty of the online experiment, which reported only one result per case.

| Profile | Farm | Online | Old mean | Fixed mean | Old error | Fixed error | Fixed seed range |
|---|---|---:|---:|---:|---:|---:|---|
| No upgrades | near | 21.38 | 20.55 | 20.63 | -3.92% | -3.53% | 19.64–21.57 |
| No upgrades | outer | 17.02 | 16.61 | 16.67 | -2.39% | -2.07% | 16.15–17.23 |
| Wheelbarrow + Horse Collar | near | 22.62 | 23.03 | 23.03 | +1.77% | +1.77% | 22.53–23.70 |
| Wheelbarrow + Horse Collar | outer | 19.26 | 19.37 | 19.37 | +0.57% | +0.57% | 18.89–19.94 |
| Hand Cart + Heavy Plow | near | 24.01 | 23.99 | 23.99 | -0.11% | -0.11% | 23.95–24.00 |
| Hand Cart + Heavy Plow | outer | 23.54 | 23.36 | 23.36 | -0.73% | -0.73% | 22.87–23.77 |

The 32-seed near-farm baseline remains 3.53% low (previously 3.92% on these same seeds). The expanded sample should take precedence over interpreting the five-seed 3.11% miss as precise accuracy.

## Evidence limits

[Official update 185872, September 22, 2026](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/) documents changes to TC drop-off tile selection, villager bumping, drop-site choice and paths around drop sites. This confirms that old measurements are not exact validation of current engine pathing. It does not prove which change explains our remaining error.

The source test omits exact worker starts, initial pool, civilization and farm alignment. We still use a solid outer TC box as a drop-contact proxy; annex/passability details are not reconstructed. Historical observations support roughly quarter-load moves, but do not establish their exact thresholds or the probability of an extra move. No unsupported work-rate uplift or distance-specific correction has been introduced.

## Verification

Eleven mechanics tests pass, including two regressions that failed on the previous engine. All 40 original review variants and all 96 fixed-engine reference runs pass food conservation, time accounting, speed and overlap checks. The new report and playback are in this directory. The original reports and original engine snapshot are retained.

## Original mill scenario

First ten-minute harvested rates, five seeds, ten farms with reseeding:
- No upgrades: 18.3518 → 18.3579 food per farmer/minute.
- Hand Cart + Heavy Plow: 23.7566 → 23.7566 food per farmer/minute.

The tiny ten-minute change is expected: the fix affects depletion boundaries rather than every gather cycle.
