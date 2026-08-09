# Hand Cannoneer Cohort Contact-Motion Calibration

## Goal

Add one Hand-Cannoneer-specific movement policy, shared across all eight
Hand Cannoneer-versus-melee tape rows, that keeps a move-ordered formation
coherent while it escapes enemy contact. The candidate must improve the
authorized standard-units comparison without altering Heavy Cavalry Archer
output or enabling an outcome-tuned matchup exception.

## Evidence

The sole calibration source is the authorized project-local archive:

- `aoe2x/js_simulation/calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip`
- SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`

The 34 decoded `frames.bin` recordings establish:

- Hand Cannoneer volleys recur every 3.998-4.001 seconds, so the existing
  240-tick beat is correct.
- Tape Hand Cannoneer contact exposure is 2.6-5.8% of live unit-frames;
  the engine produces roughly 30-59% in the high-error rows.
- Contacted tape Hand Cannoneers escape within one second in 24-73% of
  episodes, depending on current crowd geometry. Escape is conditional.
- The HCA-style per-unit local steer improves aggregate HC tape-band error
  from 185.816 to 154.330, but leaves Hussar, Elephant, and Steppe more than
  25 points outside the tape band and produces two 9,000-tick fights.
- Per-unit clearance-grid movement improves aggregate error to 151.176, but
  fragments the formation and also produces two 9,000-tick fights.

The experiments show that contact motion is the dominant shared lever, but
independent per-unit decisions are the wrong boundary. The existing order
layer already assigns a compact absolute slot to every kiter. The missing
mechanism is coordinated execution of those slots through enemy contact.

## Alternatives considered

### Per-unit A* with stronger clearance

Rejected. The measured grid experiment already grants too much independent
freedom, separates shooters, and creates indefinite endgames. A wider or
more frequently replanned path changes degree rather than architecture.

### Continuous flow-field blending

Rejected for this calibration. Blending slot attraction, target progress,
enemy repulsion, and group cohesion requires several new weights without a
direct tape-derived value for each. It would be difficult to identify which
weight closed an outcome delta.

### Contact-gated cohort heading

Selected. Keep the existing slot path under normal conditions. Only when a
move-ordered HC's next step intersects an enemy body does the formation
choose a single deterministic detour heading. Applying one heading preserves
relative geometry while still allowing the ordinary collision solver to
stop genuinely trapped members. The system returns immediately to slot
convergence when the direct formation motion clears.

## Profile boundary

The experiment extends a kite profile with:

```js
{
  cohortMotion: "contact_heading"
}
```

Only the calibration harness adds this property to the Hand Cannoneer
profile. The generated product profile remains unchanged until every gate
passes. No opponent name, master ID, speed, unit count, result, or desired
winner is visible to the policy.

## Cohort definition

On each movement tick, the cohort contains every living unit that:

- belongs to the kiting owner;
- currently has a move order; and
- is allowed to move because it is not holding an unreleased attack windup.

A single unit is not a formation and uses the existing movement path. Two or
more units form a cohort. This structural threshold is not matchup-tuned and
prevents formation logic from granting a lone survivor indefinite escape.

## Heading selection

The executor receives the cohort, its existing direct movement proposals,
all living enemy bodies, the map bounds, and the kite ring direction.

1. If no direct proposal intersects an enemy body, return the proposals
   unchanged.
2. Compute the normalized mean direction of the nonzero direct proposals.
   This is the formation's requested translation for the tick.
3. Generate full-speed shared headings at deterministic 15-degree increments
   from the mean direction through 90 degrees on both sides, with the side
   matching the established ring direction considered first.
4. Score each heading lexicographically by:
   - number of cohort members whose proposed full step does not intersect an
     enemy body or map boundary;
   - summed forward projection onto each member's original slot proposal;
   - smallest total angular turn; and
   - deterministic side order.
5. Replace every nonzero cohort proposal with its unit-speed step on the
   winning shared heading. Units already at their slot remain stopped.
6. The ordinary local-avoidance and collision layers execute those proposals.
   They remain authoritative and can stop a member that has no physical
   clearance.

No cached route is required. The current unit geometry completely determines
the next tick, so a newly opened corridor is used immediately and stale paths
cannot sustain an orbit.

## Cohesion and volley preservation

The new layer never edits move-order destinations, attack assignments, attack
timers, targets, or the 240-tick HC cycle. It changes only the wanted movement
step during a contacted formation move. Once no direct step hits an enemy,
the existing absolute slots reform the group.

The acceptance report must measure more than final score:

- live-unit contact exposure;
- median and p90 contact-window duration;
- one-second contacted-kiter escape rate;
- formation spread around the kiter centroid;
- shooters assigned and damage events delivered per volley; and
- unresolved simulations.

This distinguishes genuine formation flow from a candidate that merely runs
away or suppresses combat.

## State, events, and determinism

The policy is a pure function of the current tick. It introduces no RNG and
stores no per-unit route. Existing unit records and published hashes retain
their shape. Calibration diagnostics may add cohort-heading events to the
comparison report, but no diagnostic field is stamped on canonical units.

Profiles without `cohortMotion: "contact_heading"` do not invoke the new
function. Their proposals, events, and hashes must remain byte-identical.

## Acceptance gates

Use exact canonical `frames.bin` starts and the existing seed. Run five
samples for stable rows and 100 for the three volatile HC rows. The other
seven volatile standard-units rows remain covered by their existing
100-sample report because the candidate is HC-profile-only.

The candidate is enabled in the generated product profile only if all are
true:

- aggregate eight-row HC tape-band error improves;
- no stable tape winner regresses;
- no currently good HC row regresses by more than 10 band-error points;
- no candidate fight reaches the 9,000-tick ceiling;
- HCA-versus-Champion scores, final-state hashes, and event-log hashes are
  identical across the five pinned control samples;
- the 240-tick Hand Cannoneer volley cadence remains unchanged; and
- contact, formation-spread, and volley-participation diagnostics improve
  without an indefinite-escape signature.

Rows still more than 25 points outside the tape band must be listed even if
the aggregate gate passes. A failed candidate remains available only through
the explicit calibration experiment harness.

## Scope exclusions

- Do not change starting positions or automatic placement.
- Do not tune attack damage, accuracy, reload, projectile flight, target
  assignment, or opponent movement in this experiment.
- Do not add opponent-specific flags or constants.
- Do not change HCA `kitedEscape` behavior.
- Do not enable the policy on the product path before all gates pass.
