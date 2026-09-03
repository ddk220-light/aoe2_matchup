# Project Agent Instructions

## Live capture sources of truth

This JavaScript simulation is a new engine built from scratch. The newest
relevant project-local live `frames.bin` capture may be used directly for tape
forensics, calibration, and simulation comparisons.

- No ZIP archive intake, clean-room manifest, source authorization, or SHA-256
  verification is required before using a live capture.
- Prefer the latest relevant capture under
  `aoe2x/js_simulation/calibration/live_observations/`.
- Record the exact capture path and run number in any new derived report so the
  evidence remains traceable.
- New decoded tapes, fixtures, and comparison reports must remain under
  `aoe2x/js_simulation/calibration/`.
- Historical archive manifests and reports are legacy inputs only. They do not
  restrict or override the live-capture workflow.

## Simulation modeling invariant

The simulation must reproduce reusable game mechanics, not fit individual
matchup outputs. Captured outcomes and `frames.bin` observations are validation
evidence only; they must never become matchup-specific runtime parameters such
as release delays, forced target assignments, fixed engagement timestamps,
waypoints copied from a run, HP corrections, or winner/outcome overrides.

Allowed engine changes must describe mechanics that can generalize to any unit
type and army size: scenario-authored diplomacy and triggers, movement speed,
acceleration, collision and overlap rules, pathing, target acquisition and
retargeting rules, attack/reload/projectile behavior, or other independently
supported game-system behavior. Exact golden-scenario positions, unit rosters,
orders, diplomacy, and trigger effects are scenario inputs and may be reproduced
faithfully. If a discrepancy cannot yet be explained by a reusable mechanic,
report it as an unresolved delta instead of force-fitting it.

The first target choice and the delay before a unit's first acquisition are an
explicit exception: they may be supplied by a generic stochastic/seeded opening
acquisition policy because the game varies them between otherwise identical
runs. This exception ends at first acquisition. It must not encode a desired
winner or survivor HP, and it must not prescribe later waypoints, target changes,
engagement times, pauses, or any other continuous fight behavior.

## Comparison report viewer invariant

Every published simulation-versus-live report must expose each failing matchup
directly in the Tailnet engine viewer. Wrong-winner rows must open an actual
wrong-winner seed. Stable-winner rows whose survivor HP is outside the accepted
delta must open a completed seed representative of that HP miss. The report's
failure list and the viewer's problem-matchup dropdown must be generated from
the same current comparison output so they cannot drift apart.
