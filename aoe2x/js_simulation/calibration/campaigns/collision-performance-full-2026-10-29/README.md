# Collision optimization validation

114 exact state/event checks; 0 mismatches. 107 flagged-run retries recorded.

Retry outcomes: {'win': 95, 'processing_timeout': 11, 'engine_error': 1}.

The candidate preserves solver order, tolerances, random seeds, unit stats, and attack mechanics. 
It caches pair properties and repeated static-obstacle passes within one solve, conservatively 
rejects unreachable obstacles, and skips exactly repeated fixed-point sweeps. 
A full-state hash checks movement and other state; an event hash additionally checks the event sequence.

Full retry runs use only the 120-second wall watchdog. Prefix runs deliberately stop at their 
reference tick, so their timeout result is expected and does not represent a failed retry.

| Matchup / seed | Baseline processing seconds | Optimized processing seconds | Exact complete fight |
|---|---:|---:|---|
| Franks Crossbowman vs. Spanish Hussar / 0 | 179.52 | 47.55 | True |
| Chinese Heavy Scorpion vs. Spanish Elite Skirmisher / 0 | 379.94 | 24.36 | True |
| Vikings Mounted Crossbowman vs. Saracens Heavy Cavalry Archer / 0 | 250.15 | 17.60 | True |

See [summary.json](summary.json) for each partial-run hash comparison, 
[runs.jsonl](runs.jsonl) for every run, and [manifest.json](manifest.json) for the task list.

Prefix baselines had CPU profiling and detailed tracing; candidates use lightweight progress reporting. Concurrent workloads differ. Exact state/event comparisons are independent of timing.

Verification also includes 1,200 seeded exact movement comparisons and 119 passing 
focused/active V3 tests. Two legacy collision-recovery assertions fail identically on 
the unchanged baseline and candidate; their expectations have not been rewritten.
