# Phase 009: Scorpion mirror collision failure

The Aztec Heavy Scorpion versus Bengali Heavy Scorpion profile pair
`0fc0de7fa0000250a5e512612a900039c5a496454582bc107f34d3ef85959ccb|b268516967bc84a4d915dc41d17f2cabbfc2715133af8c9e6746cec572d595a6`
uses 27 units per side. Seed 0 completed with a Bengali win. Seed 1 failed
deterministically on all four wall-time steps (180, 600, 1,800 and 3,600
seconds); the failures occurred after about 38–40 simulated seconds, well
before the watchdog limit. It has no valid saved outcome.

The error is `starting overlap between references 9509 and 9518
(ranged-crowd/ranged-crowd-reservation; separation=0.024529046538409816;
extent=0.025)`. The ranged-crowding planner grants allied transit a minimum
collision core of 2.5% of combined body radius. When two moving siege bodies
are already closer than that core and neither is currently attacking or
reloading, a newly published reservation can set its collision extent above
their existing separation. The collision solver then rejects the *start* of
the movement step instead of resolving it. Repeated runs reach the same
reference pair and separation, so increasing wall time cannot fix it.

A possible future engine repair is to cap newly published crowd collision
extent at the pair's current separation, retaining the full collision core
against fresh ingress. That affects collision rules and therefore requires a
separately versioned engine and compatibility review. The frozen campaign
engine and existing journals have not been changed. This seed must remain
incomplete unless an eligible same-engine inference resolves the pair or a
new consistent engine version is approved and validated.
