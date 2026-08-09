# Hand Cannoneer Clearance-Grid Kiting Calibration

## Goal

Calibrate one Hand-Cannoneer-specific kiting profile, shared across every
Hand Cannoneer-versus-melee matchup, so that move-ordered Hand Cannoneers
escape attacker contact only when the current unit geometry contains a
body-width route. The candidate must improve the eight-row Hand Cannoneer
golden set without changing any Heavy Cavalry Archer simulation.

## Evidence and source authority

The sole calibration source is the authorized project-local archive:

- `aoe2x/js_simulation/calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip`
- SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Manifest: `aoe2x/js_simulation/calibration/source/standard_units_source.json`

All 34 `frames.bin` recordings for the eight Hand Cannoneer-versus-melee
rows were decoded under
`aoe2x/js_simulation/calibration/analysis/hand_cannoneer_escape/` with the
existing clean-room decoder. The derived measurements are:

- The synchronized Hand Cannoneer volley interval is 3.998-4.001 seconds in
  every row. The existing 240-tick beat is correct and must not be tuned.
- Tape Hand Cannoneer contact exposure is 2.6-5.8% of live unit-frames,
  depending on the opponent. The current engine produces roughly 30-59% in
  the four high-error rows.
- A contacted tape Hand Cannoneer escapes within one second in approximately
  24-73% of measured episodes, depending on crowd geometry. Escape is neither
  universally allowed nor universally denied.
- Enabling the existing Boolean `kitedEscape` for all four high-error rows
  improves mean absolute outcome error by 21.5%, but worsens Elite Steppe
  Lancer and degrades Paladin winner distribution. The Boolean is therefore
  evidence that the movement mechanism matters, not an acceptable final
  policy.

## Scope

The experiment covers these eight canonical owner-2 Hand Cannoneer rows:

1. Champion
2. Halberdier
3. Elite Fire Lancer
4. Heavy Camel Rider
5. Hussar
6. Paladin
7. Elite Battle Elephant
8. Elite Steppe Lancer

The policy is keyed only by the kiting unit profile. It must not contain
opponent names, opponent master IDs, matchup names, desired winners, tape
scores, or per-opponent constants.

## Non-goals

- Do not change attack damage, accuracy, reload, projectile behavior, army
  counts, starting positions, acquisition sampling, or the 240-tick HC beat.
- Do not alter ranged-versus-ranged behavior.
- Do not replace the calibrated HCA-versus-Champion `kitedEscape` path in this
  experiment.
- Do not enable the candidate on the product path unless every acceptance gate
  passes.
- Do not fit a clearance padding constant against outcomes. Collision radii
  and the existing 0.25-tile obstruction grid define clearance.

## Architecture

### Profile boundary

Extend a kite profile with an optional movement policy:

```js
{
  beatTicks: 240,
  firstBeatTick: 240,
  moveOffsetTicks: [40, 120, 200],
  preMoveTicks: [80, 160],
  topupOffsetTicks: [],
  kitedPath: "clearance_grid",
}
```

Only the generated `hand_cannoneer` profile carries this value. Profiles
without it retain their current behavior. The HCA profile remains unchanged,
and HCA-versus-Champion continues to receive its existing scenario-level
`kitedEscape: true` control.

### Planner boundary

Refactor the existing pure `planChaseAim` A* implementation into a generic
body-clearance planner while preserving `planChaseAim` as the chaser-facing
interface. Add a kited-movement interface that accepts:

- the moving kiter;
- its scripted coordinate waypoint;
- live enemy bodies as obstacles; and
- the current map bounds.

The grid remains 0.25 tiles, 8-connected, deterministically tie-broken, and
uses the units' existing collision radii. Friendly formation members are not
planner obstacles because the current formation movement deliberately ignores
friendly overlap while both units hold move orders.

The planner returns one of three results:

- `null`: the direct line is clear, so use the original move proposal;
- `{x, y}`: use the next clearance-safe waypoint;
- `{stand: true}`: no reachable progress exists, so issue a zero movement
  proposal until a later replan.

### Replanning and movement

Each HC stores a kited-path record inside `kiteState`, separate from chaser
waypoints. A plan is invalidated when:

- the scripted move-order coordinate changes;
- the unit no longer has a move order;
- the unit dies; or
- the existing phased 0.5-second replan interval fires.

Only the move-order branch in `moveUnits` consumes this plan. Attack,
targeting, recovery, local avoidance, simultaneous collision resolution, and
the existing chaser planner remain unchanged.

### Provenance generation

Add a reproducible analysis tool that reads only the verified standard-units
archive or its decoded project-local traces and emits a Hand Cannoneer profile
measurement fixture under
`aoe2x/js_simulation/calibration/fixtures/standard_units/`. The fixture records:

- archive filename and SHA-256;
- all 34 source `frames.bin` members;
- per-matchup and aggregate volley intervals;
- contact exposure;
- contact-window duration;
- one-second escape rate and displacement; and
- the derived 240-tick profile plus `kitedPath: "clearance_grid"` provenance.

`tools/derive_kite_profiles.py` consumes that generated measurement rather
than constructing the HC row solely from reload time. Generated fixtures and
`src/kite-profiles.js` are never manually edited.

## Evaluation

### Baseline

Capture the current engine outputs before enabling the candidate. Both arms
use canonical `frames.bin` starting positions, the same deterministic seed,
and identical acquisition ranks.

### Sampling

- Stable tape rows: 5 samples.
- Volatile tape rows: 100 samples.
- Compare candidate and baseline sample-by-sample.

### Primary metrics

For each row record:

- tape and simulation signed winner-HP score;
- absolute mean-score delta;
- tape and simulation side-3 win rate;
- tape-band coverage;
- contact exposure;
- contact-window duration; and
- one-second contacted-kiter escape rate.

### Acceptance gates

The candidate is accepted only if all gates pass:

1. Aggregate absolute mean-score error across all eight HC rows decreases.
2. No stable tape winner becomes a simulated wrong winner.
3. No currently good HC row regresses by more than 10 absolute score points.
4. No row times out or becomes unresolved.
5. Contact exposure moves toward tape in at least three of the four current
   greater-than-25-point HC rows and does not move farther from tape in more
   than one row.
6. Every HCA kiting playback, including HCA-versus-Champion, remains
   bit-identical in final-state hash, event-log hash, winner, winner HP, and
   ticks.
7. All combat, playback, profile-generation, and standard-units tests pass.

If any gate fails, the candidate remains disabled and the report records the
failed gate. No opponent-specific exception is added as a follow-up.

## Testing strategy

Implementation follows red-green-refactor:

1. Pure planner tests prove direct, routed, blocked, deterministic, and
   body-width boundary behavior for coordinate targets.
2. World tests prove only `kitedPath: "clearance_grid"` move-ordered kiters
   consume kited plans and that the plans invalidate on the documented events.
3. Profile-generation tests reproduce the 240-tick HC cadence and reject an
   archive hash mismatch or incomplete source set.
4. An HCA regression test compares hashes with and without the HC code path
   present and requires exact identity.
5. The eight-row A/B calibration runner enforces every acceptance gate and
   writes a JSON and Markdown report under
   `aoe2x/js_simulation/calibration/reports/`.

## Failure handling

This is an offline deterministic experiment. Invalid archive identity,
missing source tapes, malformed decoded rows, non-finite metrics, incomplete
sampling, or timeouts abort the evaluation with a named error. A failed
acceptance gate produces a valid rejected-candidate report; it does not modify
the committed default profile or product behavior.
