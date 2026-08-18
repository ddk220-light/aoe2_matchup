# War Wagon contact and attack-move experiments (2026-08-17)

## Decision

**Promote the final formation/contact policy for Elite War Wagon kiting.** The
first experiment correctly rejected fixed overlap as a complete explanation,
but the follow-up found a wiring bug: `formationSpacingTiles` reached the kite
order layer while cohesive navigation silently rebuilt the group on its fixed
`0.48`-tile lattice. For a `0.9`-tile War Wagon body that produced a much denser
block than the tape and prevented melee units from forming an effective
perimeter.

The accepted policy has three mechanics-backed pieces:

1. Elite War Wagons use the tape-measured `0.60`-tile allied formation lattice.
   Cohesive navigation now consumes the same profile value as kite orders.
2. Attack-moving melee units keep live targets, and coordinated acquisition
   pressure is one chaser collision diameter. This prevents the artificial
   single-target queue without imposing a target cap.
3. The transient Wagon/enemy contact allowance is the chaser's excess collision
   diameter over an ordinary `0.20`-tile infantry half-extent. That yields
   `0.10` tiles for a `0.25` Paladin and zero extra penetration for a `0.20`
   Champion. The rule is War-Wagon-specific but not matchup- or outcome-named.

All non-War-Wagon scenarios retain their previous formation and contact policy.
The shared policy helper is used by both the Phase 2 golden runner and the
interactive `runFight`/viewer path, so the visual fight and the report do not
silently exercise different physics.

## Authorized source

- Archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- Project-local path:
  `aoe2x/js_simulation/calibration/source/aoe2_golden_phase2_WITH_TAPES.zip`
- SHA-256:
  `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Exact controls:
  - 15 Elite War Wagons versus 17 Paladins, four tape repeats
  - 8 Elite War Wagons versus 21 Champions, four tape repeats

Positive scores mean owner 3 won; negative scores mean owner 2 won.

## What the tape establishes

### Contact

War Wagon enemy overlap is real but sparse at the pair-observation level. The
pooled Chebyshev contact analysis finds an overlap share of about `0.88%` for
Paladin/Wagon pairs and `0.58%` for Champion/Wagon pairs. A fight frame can
still contain one or more overlaps because every frame has many eligible
enemy pairs.

Conditional median overlap depth by repeat is `0.0684` to `0.1088` tiles for
Paladins and `0.0346` to `0.1010` for Champions. Median episode duration is
about `0.33` to `0.49` seconds for Paladins and `0.32` to `0.50` seconds for
Champions. Roughly `68%` to `73%` of overlap observations occur while the
opponent is stopped in decoded attack state 7. This supports short attack-lock
contact, not continuous pursuit penetration.

`analyze_contact_states.mjs` writes the reproducible category and episode
measurements to `contact_state_analysis.json`.

### Attack-move target distribution

Tape target acquisition is asynchronous. The first valid melee targets appear
at roughly `1.0` to `1.25` seconds. In the first Paladin repeat, the target
state grows from no assignment at `1.0 s` to 15 Paladins assigned across five
Wagons at `2.0 s`; at `4.0 s`, all 17 are assigned across five Wagons. Across
the four Paladin tapes, the active-frame median is five to six distinct Wagon
targets.

The Champion tape is intentionally more concentrated. In its first repeat, all
21 Champions are assigned across four Wagons at `2.0 s`, with 14 Champions on
the largest target; the active-frame median is four to five distinct targets.

The pre-experiment Paladin sim differs sharply: it has 13 assigned Paladins on
only two targets at `2.0 s`, then all 17 on one target by `4.0 s`. It records
290 Paladin pursuit acquisitions, about 17 per unit, but only 35 Paladin attack
starts. Individual Paladins reacquire 30 to 61 times. The tapes average only
about four to five live target switches per Paladin.

`analyze_target_distribution.mjs` writes the per-repeat samples and persistence
measurements to `target_distribution_analysis.json`.

## Candidate mechanics

### Fixed and attack-locked enemy penetration

The War-Wagon-exclusive `warWagonEnemyOverlapDepthTiles` hook applies a bounded
reduction to the enemy-pair collision extent through starting validation,
movement, stopping, chase planning, steering, recovery, and final geometry
validation. Its state modes can limit the allowance to any attack lock, the
selected target, or another Wagon.

Every mode was rejected. A complete fixed-depth policy helped the Paladin score
but kept the wrong winner and flipped the previously accurate Champion control.
Attack-locked target penetration gave no Paladin improvement; other-Wagon
penetration improved the Paladin score by only 8.5 points and degraded the
Champion control.

### Coordinated attack-move scan

`attackMoveTargetPressureTiles` adds a soft score to target acquisition:

`surface gap + current allied claims * pressure tiles`

The claim map is updated during the scan, so a later unit observes assignments
made earlier in the same tick. This is not a target cap and it does not force a
uniform spread. The candidate sweep tried `0.25` and `0.50` tiles.

This fixed the early distribution symptom. At `0.50`, Paladins reached six
distinct targets by `3 s`, close to tape, and improved from `-83.33` to
`-53.67`. It did not fix the winner and it flipped the Champion control.

### Sticky attack-move pursuit

`attackMoveStickyPursuit` prevents a blocked attack-mover from abandoning a
still-live target merely because its current movement step was blocked. Normal
retargeting after target death remains intact. The tested pressure was derived
from mechanics as twice the chaser collision half-extent: `0.50` tiles for a
Paladin and `0.40` for a Champion.

This reduced Paladin pursuit acquisitions from 290 to 49 and raised attack
starts from 35 to 120. It kept the Champion control correct. It still left the
Paladin side about 100 attacks below the tape's 219 to 223, so it is promising
infrastructure rather than a completed calibration.

### Pairwise allied transit

Enabling the existing one-reservation-per-unit allied transit together with
sticky targeting was rejected. Paladin attacks fell from 120 to 95 and the
score worsened from `-44.33` to `-56.67`. The Champion control stayed within 25
points. More generic allied pass-through is therefore not the missing rule.

## Tape versus simulation

One-sample candidates use exact canonical positions, seed `20260817`, the
golden map, cohesive kiting, mechanics-derived kite timing, attack-move melee
opening, zero melee dwell, and the 9,000-tick ceiling.

| Engine state | Matchup | Tape mean | Sim score | Absolute delta | Result |
|---|---|---:|---:|---:|---|
| Pre-experiment engine | Wagon vs Paladin 15v17 | +35.44 | -83.33 | 118.77 | Wrong winner |
| Attack-lock, target only | Wagon vs Paladin 15v17 | +35.44 | -83.33 | 118.77 | Wrong winner |
| Attack-lock, other Wagon | Wagon vs Paladin 15v17 | +35.44 | -74.83 | 110.27 | Wrong winner |
| Target pressure 0.25 | Wagon vs Paladin 15v17 | +35.44 | timeout | — | Timed out at 150 s; residual HP was not retained |
| Target pressure 0.50 | Wagon vs Paladin 15v17 | +35.44 | -53.67 | 89.11 | Wrong winner |
| Sticky + diameter pressure | Wagon vs Paladin 15v17 | +35.44 | **-44.33** | **79.77** | Wrong winner; best completed candidate |
| Sticky + pressure + pairwise transit | Wagon vs Paladin 15v17 | +35.44 | -56.67 | 92.11 | Wrong winner |
| Pre-experiment engine | Wagon vs Champion 8v21 | +20.10 | +18.50 | 1.60 | Correct |
| Target pressure 0.25 | Wagon vs Champion 8v21 | +20.10 | -13.44 | 33.54 | Wrong winner |
| Target pressure 0.50 | Wagon vs Champion 8v21 | +20.10 | -30.94 | 51.04 | Wrong winner |
| Sticky + diameter pressure | Wagon vs Champion 8v21 | +20.10 | **+37.55** | **17.45** | Correct, within 25 |
| Sticky + pressure + pairwise transit | Wagon vs Champion 8v21 | +20.10 | +38.50 | 18.40 | Correct, within 25 |

The target-pressure results are in `attack_move_target_pressure_results.json`.
The sticky and pairwise results are in `sticky_target_pressure_results.json`.
All sweep scripts publish atomically after every matchup and resume without
rerunning completed candidates.

## Final accepted comparison

The final results come from `run_final_diagnostic.mjs`, which calls the normal
`runPhase2Batch1Sample` path after the policy was promoted. They use canonical
golden positions, sample `0`, seed `20260817`, and no combat-stat or outcome
adjustment.

| Matchup | Tape mean (band) | Final sim | Delta | Winner |
|---|---:|---:|---:|---|
| Elite War Wagon 15 vs Paladin 17 | +35.44 (+30.00 to +39.80) | +22.75 | 12.70 | Correct: Paladin |
| Elite War Wagon 8 vs Champion 21 | +20.10 (+9.12 to +25.44) | +43.27 | 23.16 | Correct: Champion |

The Paladin diagnostic also closes the physical clocks that exposed the bug:
225 attack starts versus 219-223 on tape, 208 damage events versus 209-210,
and a 108.2-second fight versus the tape's 94.2-106.6 seconds. War Wagon allied
overlap now has a `0.30`-tile conditional median, exactly the tape median, rather
than being forced back onto the hidden `0.48` cohesive lattice.

The remaining score error is under 25 points for both controls. It should not be
reduced with damage, accuracy, or matchup-specific winner constants.

## Run budget

The original fixed-depth experiment used 15 simulations. After the user
authorized trying additional mechanisms, the follow-up used exactly 14 more:

- six attack-lock variants (three modes across two controls);
- four target-pressure variants (two strengths across two controls);
- two sticky-target variants (one per control);
- two sticky-target plus pairwise-transit variants (one per control).

No broader matchup suite was run.

The final follow-up used 15 bounded simulations: one root-cause diagnostic,
eleven one-variable/isolation candidates, one Champion control, and the two
final normal-engine verification runs. Each run was limited to these two golden
War Wagon rows; no Phase 2-wide suite was executed.
