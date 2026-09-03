# General-engine invariant audit — 2026-08-29

## Rule

Replay observations are evidence, not runtime instructions. Continuous combat
must emerge from reusable mechanics and exact scenario inputs. Per-matchup
release times, copied trajectories, forced later targets, winner/HP
corrections, and outcome overrides are prohibited. A generic seeded first
target/first-scan policy is the sole exception and ends at first acquisition.

The repository-level `AGENTS.md` records this as a permanent implementation
invariant.

## Removed in this pass

1. **Ranged-vs-melee release profile.** The previous implementation derived a
   median tick for each matchup and withheld attacks until that tick. The JSON
   fixture, generator, runtime plumbing, and invalid generated reports were
   removed. A live Player-4 army and owner-defeat trigger now create the phase
   transition.
2. **Per-unit melee opening trajectories.** Three older five-run comparison
   workflows generated per-unit movement starts, intermediate coordinates,
   endpoint clocks, and target slots. The world then divided remaining
   distance by remaining observed ticks to arrive on those points. This
   continuous profile input was removed from `createWorld`/`runFight`; the
   comparison tools now use the generic opening seed. The source captures and
   derived profiles remain historical evidence only.
3. **Current-golden owner targeting switches.** The current ranged server path
   no longer enables owner-specific target-pressure, opportunity-retarget, or
   windup-retarget switches. Current RvR and mixed families use shared engine
   targeting.

## Older mechanisms still present but isolated from current goldens

The following predate the current scenario work and need their own future
generalization audit. They are not enabled by the current ranged-vs-ranged,
ranged-vs-melee, or melee-vs-ranged server configurations.

- `src/combat/kite-timing.js` retains per-ranged-unit opening-phase and
  formation policies for the legacy kiting lab. Its recurring beat is derived
  from reload and a shared order clock, but Hand Cannoneer/HCA opening choices
  are still unit-keyed empirical policy.
- `src/combat/ai-orders.js` contains a global tape-measured AI sweep and idle
  rescue cadence. It is not matchup-keyed, but it is an inferred behavioral
  layer rather than DAT physics; all current goldens disable it.
- `src/phase2-batch1-comparison.js` still opts into owner-specific ranged
  retarget switches and viewer/dedicated kiting controls. Its historical
  Phase-2 results must not be cited as validation of the new current-golden
  engine.
- War Wagon and kiting-viewer policies remain special-purpose legacy behavior.
  They must not be silently extended to new units or used to tune a current
  matchup result.

This disclosure is deliberate: removing the two active output-fitting paths
does not by itself prove that every older calibration subsystem is a complete
general model. Future work should either derive these behaviors from shared AI
state/mechanics or retire them before using that subsystem for arbitrary units.

## Current acceptance evidence

Arbalester/Paladin in both mixed orientations now runs with exact positions,
directional diplomacy, nine physical P4 Scouts, defeat-triggered hostility,
and ordinary post-acquisition movement/combat. The correct Paladin winner is
stable across five opening seeds. Mean winner-HP delta is 9.8% in the five-run
ranged→melee set; the opposite orientation is 9.1% for seed 0 and 9.9% for the
five-seed mean against the one existing replay. See
`RANGED_MATRIX_LIVE_OBSERVATIONS_2026-08-29.md`.

Across all 14 existing RvR/RvM matchups, the same five-seed physical engine has
0 wrong winner directions and 14.758 mean absolute signed-score points. Only
6/14 rows currently meet the stricter 20% relative winner-HP target; the other
rows remain explicit mechanics deltas, not calibration constants.

The engine also enforces a causal first-acquisition invariant: a scenario
PATROL unit cannot begin an engagement while it is still waiting for its first
AI scan. Tests require every first attack tick to be at or after that unit's
first pursuit-acquisition tick. First target and first-scan variance remain the
only permitted seeded boundary; this invariant does not prescribe any later
target or delay.

A replay-derived half-tile formation-compaction prototype was explicitly
rejected after it flipped three winner directions across the 14-match matrix.
It is not active. Formation compression, ally overlap, and catch-up speed must
be implemented as one reusable group-movement model and validated outside as
well as inside combat before being enabled.
