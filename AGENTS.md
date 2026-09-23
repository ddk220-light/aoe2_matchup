# Project Agent Instructions

## Ask explicitly before every unrequested change

- Preserve the existing product unless the owner explicitly requests a change. Adding civilizations or units means extending the existing roster, shared assets and normal UI, not inventing a separate architecture or new controls.
- Before implementing any unrequested change, ask the owner a clear, separate question describing that specific change and why it is proposed; wait for an explicit answer. Raise it during the design/brainstorming discussion, or immediately if discovered during implementation. Do not silently bundle it into an implementation plan, review, commit or release. Approval of a plan or "go ahead" does not authorize additions that were never individually raised and approved.
- This includes titles, subtitles, civilization descriptions, search/SEO metadata, footer copy, product claims, navigation, accessibility/keyboard behavior, media controls, asset organization and quality substitutions. An apparently beneficial improvement is still a separate decision. Routine internal implementation and verification of the explicitly requested result do not require duplicate approval.
- Partial or sequential delivery is intentional. Do not rewrite "Best Units" or ranking-related language, add interim states, redesign assets, or add compatibility work merely because simulations/rankings will arrive later. Explain any concern and ask; do not invent a workaround. Production-action approvals remain separately required.
- Civilization correction approved on 2026-09-23: restore the original Best Units titles, descriptions/SEO wording and subtitles, retaining the correct count of 56; keep resource costs; remove the added media selectors and keyboard/focus interactions; restore in-place civilization switching; use the existing shared asset system without changing simulation/ranking data. Preserve existing civilization strategy paragraphs and approved image quality.
- Before completion/publication, compare the actual diff against the owner's requests and explicit answers, not merely the agent-authored plan. List every material change and stop for any unapproved addition.

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
