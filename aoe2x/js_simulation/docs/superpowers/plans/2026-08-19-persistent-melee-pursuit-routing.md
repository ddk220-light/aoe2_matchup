# Persistent Melee Pursuit Routing Implementation Plan

1. Add failing chase-path tests for an attack-envelope waypoint chain, allied
   congestion routing, and deterministic mirrored paths.
2. Implement a pure persistent-route planner and route-advance/validation
   helpers in `src/combat/chase-path.js`.
3. Add failing world tests proving that a route survives the next tick and that
   tangent/contact steering does not rewrite a routed pursuit proposal.
4. Store experimental routes in kiting-world state, update them from resolved
   progress, and expose diagnostics without changing canonical unit state.
5. Run focused path/world tests, then the complete JavaScript suite.
6. Run only the exact Elite Boyar-HCA and Paladin-HCA golden rows and compare
   movement diagnostics and outcomes to baseline and tape.
7. Enable the experiment in their viewer playback and supply the Tailnet URLs.
