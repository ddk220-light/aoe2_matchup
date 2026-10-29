# Ranking timeout diagnostics

Status: **running**. Completed 0/110 diagnostic tasks.

The bulk campaign and its saved outcomes remain the source records. These are supplemental diagnostic reruns.

Three controls must reproduce exact final-state and event hashes before any flagged run is investigated. 
Runs execute one at a time after the bulk campaign stops. The nominal processing allowance is 120 seconds; 
an external 130-second cutoff covers an unresponsive tick and profile flushing. 
Game-time-cutoff cases have no practical game-time cap. Original processing-time-cutoff cases 
first retain the original 150-game-second cap to make their timings interpretable. 
Tracing and CPU profiling add overhead, and the original campaign used four workers. 
A faster rerun alone does not prove a contention bug. Inactivity observations require inspection.

| Task | Matchup / seed | Stop reason | Processing seconds | Last game seconds |
|---|---|---|---:|---:|

Per-run `result.json` includes CPU hotspots, tick timings, last unit states, and original provenance. 
`timeline.jsonl` records progress, positions, targets, HP, and event counts. 
Raw CPU profiles and the copied runtime remain local to keep Git checkpoints manageable.
