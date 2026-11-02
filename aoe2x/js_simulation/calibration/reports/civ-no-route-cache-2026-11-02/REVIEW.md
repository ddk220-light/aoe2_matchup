# Exact negative-cache experiment — not adopted

The cache reuses only an exhaustive negative search with identical grid
topology, directed crowd constraints, start cell and complete goal mask.
It does not change collision precision or approximate an outcome.

All 28 focused routing/cache tests passed. The blocked Kona seed's first
40 game seconds matched the original engine's outcome, tick, final-state hash
and event-log hash exactly. A completed Kona seed also matched its saved V2
record exactly. However, the bounded benchmark took 76.42 seconds with the
cache versus 70.10 seconds without it. Only 109 of 1,604 lookups hit. This
version is not a useful speedup and has not been applied to any campaign.

Reports and source are retained so this unsuccessful approach is not repeated.
All measurements here are diagnostics, never campaign records.
