# One-range melee reach-wedge and updated golden portfolio

Open the self-contained [HTML report](report.html) for the complete portfolio
tables and charts.

## Technical summary

The reach-wedge policy is now a general mechanics rule: any melee chaser with
a sourced attack range of at least one tile may use it against any target. The
engine no longer gates the policy on relative speed or closure per reload and
does not identify Elite Steppe Lancer by name.

The HCA-versus-Steppe winner failure remains repaired. Across the three
eligible dedicated-golden families, all 75 exact-repeat simulations resolved
with no wrong winners. HCA-versus-Steppe has a 9.16-point mean absolute row
delta, Elite Skirmisher-versus-Steppe 0.55, and Arbalester-versus-Steppe 18.06.

Scorpion is the dominant remaining gap, but it is not literally the only
residual. In the updated 85-row portfolio it accounts for nine of 12 rows over
25 points and 30 of 31 wrong-winner attempts. Three non-Scorpion rows remain
over 25, one HCA-versus-Fire-Lancer repeat crosses the winner boundary, and one
accepted Elite-Skirmisher-versus-Champion row reaches the 9,000-tick limit.

## Generic engine contract

A reach-wedge admission requires all of the following:

- sourced `attack_range_tiles >= 1` for the melee chaser and the front ally;
- the rear unit is near its legal engagement envelope and moving toward its
  current enemy target;
- the front ally is physically closer to that target;
- neither ally already belongs to another transit pair; and
- the projected contact does not create a three-neighbor stack or compact
  four-unit clique.

The reservation permits one two-deep allied transit pair and ends after the
rear unit crosses, separates, or reaches attack range. It does not change the
unit collision radius, attack range, speed, reload, damage, or zero-range melee
movement. The dedicated corpus currently contains one eligible melee unit,
Elite Steppe Lancer, but future one-range melee profiles inherit the same rule.

## Required Steppe rerun

All five ratios and all five exact tape starts were rerun for each affected
family. Positive signed score means the Steppe Lancer side won.

| Matchup | Ratio | Tape | Simulation | Absolute delta | Wrong winners |
|---|---:|---:|---:|---:|---:|
| Arbalester vs Steppe | 10v5 | -49.20 | -21.00 | 28.20 | 0 |
| Arbalester vs Steppe | 15v20 | 71.84 | 82.00 | 10.16 | 0 |
| Arbalester vs Steppe | 20v15 | 25.44 | 48.53 | 23.09 | 0 |
| Arbalester vs Steppe | 20v20 | 51.88 | 72.40 | 20.52 | 0 |
| Arbalester vs Steppe | 5v10 | 83.28 | 91.60 | 8.32 | 0 |
| HCA vs Steppe | 10v5 | -86.25 | -61.25 | 25.00 | 0 |
| HCA vs Steppe | 15v20 | 59.20 | 49.25 | 9.95 | 0 |
| HCA vs Steppe | 20v15 | -26.50 | -29.38 | 2.88 | 0 |
| HCA vs Steppe | 20v20 | 29.60 | 33.75 | 4.15 | 0 |
| HCA vs Steppe | 5v10 | 80.20 | 84.00 | 3.80 | 0 |
| Elite Skirmisher vs Steppe | 10v5 | 89.88 | 91.20 | 1.32 | 0 |
| Elite Skirmisher vs Steppe | 15v20 | 97.91 | 97.85 | 0.06 | 0 |
| Elite Skirmisher vs Steppe | 20v15 | 93.37 | 94.27 | 0.89 | 0 |
| Elite Skirmisher vs Steppe | 20v20 | 96.97 | 96.65 | 0.32 | 0 |
| Elite Skirmisher vs Steppe | 5v10 | 98.16 | 98.30 | 0.14 | 0 |

The target-independent rule therefore keeps the HCA repair, improves the
already-good Elite Skirmisher control, and makes Steppe somewhat too strong
against Arbalesters. Only Arbalester 10v5 exceeds 25 points, at 28.20, and its
winner remains correct.

## Updated portfolio status

The portfolio combines the 15 necessary fresh rows above with 70 saved rows
from the completed `dedicated_ranged_melee_steering_050_parallel_2026-08-14`
run. Reuse is valid because no zero-range chaser can enter the new policy.

- 17 dedicated golden matchups, 85 ratio rows, and 425 exact-repeat attempts.
- 420 resolved attempts; five accepted time-limit attempts in one row.
- 12 rows above 25 points; nine are Heavy Scorpion rows.
- 31 wrong-winner attempts; 30 are Heavy Scorpion attempts.
- Mean absolute resolved-row delta: 17.77 points; median: 4.58.

### Remaining non-Scorpion exceptions

| Matchup | Ratio | Issue | Status |
|---|---:|---|---|
| Elite Skirmisher vs Champion | 20v15 | 33.75-point delta | Previously accepted; winner correct |
| Arbalester vs Champion | 20v20 | 29.63-point delta | Winner correct |
| Arbalester vs Elite Steppe | 10v5 | 28.20-point delta | New generic-policy residual; winner correct |
| HCA vs Elite Fire Lancer | 20v20 | One repeat-level wrong winner | 2.02-point mean delta; tape crosses winner boundary |
| Elite Skirmisher vs Champion | 10v5 | Five 9,000-tick timeouts | Previously accepted knife-edge duration case |

## What remains to optimize

Heavy Scorpion is the next major engine problem: Scorpion-versus-Paladin has
five rows over 25 and 20 wrong-winner attempts, while
Scorpion-versus-Champion has four rows over 25 and 10 wrong-winner attempts.
Those two families should be treated as a separate minimum-range, projectile,
and kiting investigation rather than weakening the generic one-range melee
rule.

After Scorpion, the only strict threshold misses are the three correct-winner
rows in the table above. The Fire Lancer repeat and the accepted
Elite-Skirmisher-versus-Champion duration case are monitoring items, not the
next calibration target.

## Evidence and method

The three selected archives were SHA-256 verified before execution:

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_kiting_arbalestervssteppe_2026-08-06.zip` | `3F4D8F0B69AE82A874E28FD1A9B801C9B0DFB4F46A17B4692F4457ADB2CB9C34` |
| `aoe2_golden_kiting_eliteskirmvssteppe_2026-08-06.zip` | `9500E4703ACB48273C83D71CE4313820BA92391EE80CAF2882F92AF12B46414B` |
| `aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip` | `74D83F2EBE0D7EE89AD76C50D68147D4D0B085FA0223B1CECB59FF83198C9373` |

The selective runner used 15 parallel row workers on 24 available logical
CPUs. Each row checkpoint contains its five exact-repeat simulations and was
atomically committed before progress advanced. The merged portfolio records
the 70 reused rows and 15 rerun rows in `run-manifest.json`.

Audit artifacts:

- `results.json` and `results.csv`: merged 85-row portfolio.
- `analysis.json`: threshold, failure, family, and all-row analysis.
- `artifact.json`: portable report payload.
- `report.html`: self-contained report; structural verification passed.
- `recoverable/results.json`: the 15 freshly simulated Steppe rows.
- `recoverable/checkpoints/`: restart-safe per-ratio evidence.

The packager could not find a compatible installed Chromium headless shell,
so browser viewport and source-dialog interaction QA were unavailable. Exact
payload equality and structural verification passed, and the report retains
its semantic no-script fallback.
