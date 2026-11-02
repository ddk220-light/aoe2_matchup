# Exact static-geometry memoization candidate

CPU profiling identifies collision validation as the dominant processing cost in the failed Armenian Skirmisher/Mapuche Kona seed. The candidate reuses identical static-geometry checks only within one movement solve, keeping original arithmetic, first-error order and tolerance. Cache keys include exact displacement and tolerance; origins, obstacles and bounds are immutable for the lifetime of these temporary bodies. No cache is published in world state or reused across ticks.

The isolated 40-game-second probe matches the original frozen V2 final-state hash, event-log hash, outcome and tick. The completed seed-1 control also matches its saved V2 record exactly. Collision/movement regressions passed (30 tests), plus two tests that compare cached and uncached solvers across strict/slop recovery and 30 deterministic changing-displacement/map cases. Bounded wall time fell from 70.10 to 24.59 seconds (2.85x) on a shared machine; this is indicative, not a stable throughput guarantee.

Earlier reachability changes are not in this candidate's runtime. Only collision.js differs from the 62-file certified V2-stream runtime. Earlier experiments remain in Git history and reports.

A separately frozen targeted campaign recomputes all required seeds of the failed Kona pair and performs an exact replay review. It never imports old outcomes and cannot fill a first-pass gap until its seed set and review are complete. Candidate-native observations must remain separate; their table projection is explicitly unvalidated under frozen V3. The forest-pocket fidelity question remains open. Nothing here authorizes bulk replay or forecast retraining.
