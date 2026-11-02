# Subcell probe v1 — not adopted

Checking the actual starting position instead of its rounded cell centre fixes a generic false-reach condition, with 24 routing tests passing. It did not resolve the Kona forest pocket within the bounded 300-wall-second probe. One complete Kona control kept its winner but changed ticks/hashes; the Elephant control remained exact. These are diagnostics, not campaign measurements or table projections. The candidate has not been adopted.

Further inspection shows the nearest melee actors still receive `stand: true` because the coarse raster leaves no usable goal cell in a narrow region among static circles and allied bodies. A continuous route might exist; that must be demonstrated without altering collision extents, attack reach or outcomes.
