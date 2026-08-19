# Persistent Melee Pursuit Routing Design

## Scope

Replace the per-tick tangent loop for melee units chasing a moving ranged unit
with a persistent, deterministic route. The first experiment is evaluated only
on Elite Boyar versus Heavy Cavalry Archer and Paladin versus Heavy Cavalry
Archer. The mechanism itself must remain unit-, owner-, and matchup-neutral.

## Evidence

- Elite Boyar simulation spends 27.1% of pursuit moving laterally versus 19.7%
  on tape, and local avoidance is active for 81.5% of pursuit time.
- Champion versus War Wagon stalls during 43.9% of simulated pursuit versus
  12.1% on tape; 88% of those simulated stalls occur while avoidance is active.
- Disabling preventive contact steering does not solve the defect. The War
  Wagon control stalls slightly more and runs longer.

The present pipeline aims directly at the live target, computes a tangent around
one blocker, rotates that tangent again for compact-contact prevention, and then
clips it in collision resolution. The next tick starts from the direct target
again. A lateral step therefore has no persistent continuation around the
blocking group.

## Design

1. Keep direct live pursuit when the corridor to the target's physical stop
   envelope is clear.
2. When the direct corridor is obstructed, calculate a deterministic A* route
   on the existing 0.25-tile obstruction grid.
3. The goal is any reachable grid cell inside the actor/target melee stop
   envelope, not the target centre.
4. Static geometry and obstructing enemy bodies are hard constraints. Allied
   bodies contribute a geometric traversal cost derived from the amount by
   which the candidate cell penetrates their collision extent. Costs therefore
   accumulate naturally for a dense pack without a unit-specific threshold or
   timer; a single shallow allied contact can remain cheaper than a long detour.
5. Return a waypoint chain and persist it per chaser. Advance through the chain
   rather than re-aiming directly after every lateral step.
6. Invalidate a route only when its target changes/dies, its next segment is no
   longer traversable, or resolved motion makes no progress toward the active
   waypoint. These are physical state changes, not calibrated time intervals.
7. While a valid pursuit route is active, it is the sole direction authority.
   The local tangent and preventive contact-graph layers remain available for
   other movement regimes but do not rotate a certified pursuit-route step.
   Collision resolution remains the final safety constraint.
8. Preserve deterministic mirrored behavior and existing pairwise overlap and
   contact-reservation physics.

## Observability

Expose each active pursuit route, waypoint index, and replan reason in retained
viewer snapshots so route continuation can be inspected visually.

## Validation

- Unit tests cover attack-envelope goals, persistent waypoint advancement,
  dense allied-pack detours, shallow single-ally transit, target invalidation,
  and mirrored symmetry.
- Run Elite Boyar versus HCA as the defect case and Paladin versus HCA as the
  regression control, using exact authorized golden rows and at most five
  initial samples.
- Compare winner/HP delta plus direct, lateral, stall, lateral-to-stall, and
  avoidance-active shares. No wider Phase 2 batch is run in this experiment.
