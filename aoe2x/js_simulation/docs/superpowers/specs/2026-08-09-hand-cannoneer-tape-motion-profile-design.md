# Hand Cannoneer Tape-Motion Profile Design

## Goal

Replace the constructed Hand Cannoneer formation width with one HC-wide value
measured from the authorized standard-units `frames.bin` recordings, then test
whether that geometry closes the remaining tape-outcome deltas.

The experiment must preserve each tape row's exact canonical starting
positions. It changes only mid-fight destinations issued by the scripted kite
controller.

## Evidence

The active archive is
`aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip`, SHA-256
`38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.
The movement corpus contains 34 HC-versus-melee `frames.bin` recordings.

The current Hand Cannoneer kite profile is explicitly marked `constructed,
not measured`. Its movement destinations use the engine-wide 0.50-tile slot
spacing. Representative tape-frame measurements give:

| HC count / opponent | Median formation width x height | Implied grid spacing | Median centroid distance from 5..11 ring | Median 4 s centroid displacement |
| --- | ---: | ---: | ---: | ---: |
| 10 / Halberdier | 1.15 x 1.19 | 0.38-0.40 | 0.55 | 2.63 |
| 14 / Champion | 1.35 x 1.31 | 0.44-0.45 | 0.42 | 2.48 |
| 14 / Hussar | 1.02 x 1.04 | 0.34-0.35 | 0.45 | 2.75 |
| 19 / Elite Fire Lancer | 1.51 x 1.59 | 0.38-0.40 | 0.66 | 2.40 |
| 21 / Heavy Camel | 1.73 x 2.02 | 0.43-0.51 | 0.64 | 2.30 |
| 21 / Paladin | 1.21 x 1.29 | 0.30-0.32 | 0.58 | 2.61 |
| 21 / Elite Battle Elephant | 1.26 x 1.28 | 0.32 | 0.49 | 2.72 |
| 21 / Elite Steppe Lancer | 1.26 x 1.16 | 0.29-0.32 | 0.49 | 2.57 |

The shared median implied spacing is approximately 0.35 tile. For a 21-unit
five-column formation, changing spacing from 0.50 to 0.35 also reduces the
mean trailing offset behind the ring waypoint from about 0.95 to 0.67 tile,
matching the observed centroid offset without changing the already-supported
square-ring topology.

The rejected cohort-motion experiment reduced blocked events by 31-68% while
worsening aggregate outcome error. That result rules out collision relief by
itself and points upstream to the commanded formation geometry.

## Considered approaches

1. **Measured HC slot spacing (selected).** Add an optional
   `formationSpacingTiles` kite-profile property and set it to 0.35 only in the
   explicit HC experiment. This is one unit-wide value derived across opponent
   classes, changes the smallest plausible cause, and preserves all existing
   timing and targeting behavior.
2. **Replace the square ring with an opponent-relative trajectory.** The
   recordings show outcome-dependent realized motion, but do not yet support
   one invariant opponent-relative rule. This would conflate formation width,
   collision, and path topology in one test.
3. **Replay each recorded centroid path.** Rejected because it would encode
   per-recording outcomes and would not generalize to free-selection fights.

## Runtime design

- `kite-profiles.js` remains unchanged for the product path during the screen.
- `runTapeConditioned` accepts the explicit calibration experiment
  `{ formationSpacingTiles: 0.35 }` and copies it onto the selected kiter's
  profile.
- `createKiteState` validates and copies a finite positive optional spacing.
- `kiteMoveOrder` uses the optional value, otherwise retaining the current
  0.50-tile default exactly.
- No opponent names, masters, counts, tape scores, or per-row constants enter
  combat code.
- Heavy Cavalry Archer never receives the experimental property; its scores,
  final-state hashes, and event-log hashes must remain bit-identical.

## Test and acceptance design

1. Pin the default 0.50 behavior and validation in focused unit tests.
2. Prove that an explicit HC spacing experiment changes one HC run while the
   default run remains hash-identical to its baseline.
3. Run five samples for all eight HC-versus-melee rows.
4. Stop before the 100-sample expansion unless the five-sample screen has:
   no timeout, no wrong stable winner, lower aggregate tape-band error, and no
   more than a 10-point regression on a baseline-good row.
5. If the screen passes, run 100 samples for the volatile Hussar, Paladin, and
   Elite Battle Elephant rows and five for the other five rows.
6. List every row still more than 25 points outside its tape band.
7. Run the five-sample HCA-versus-Champion identity control.

The product Hand Cannoneer profile is updated only if the full acceptance gate
passes. A rejected candidate remains calibration-only infrastructure and is
reported as such.
