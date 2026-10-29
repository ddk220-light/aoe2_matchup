# Post-campaign timeout diagnosis

Requested on 2026-10-29: finish the existing campaign first, then investigate
processing-time cutoffs with proper diagnostics and retry game-time cutoffs with
the game-time restriction removed. Preserve every original result.

Source: `../unit-rankings-full-deduplicated-2026-10-29/`, campaign hash
`0aebb7b2c73afe3c8cfca5226234b90c0af095bb5be58617f1f4d5af9b9f41a0`.

## Execution order

1. Wait until the bulk campaign is complete, has zero pending seeds, and releases
   its runner lock. No diagnostic battles execute before this gate.
2. Verify the frozen source files, Node version, and simulation switches. Copy
   the runtime locally; add observation hooks to the copy only. Record hashes
   of both modified files. No movement, attacks, targeting, stats, or random
   choices are changed.
3. Replay one completed Infantry, Ranged, and Cavalry run. Require exact final
   state and event hashes before continuing. These controls also record the
   effects of tracing on elapsed time.
4. Retry every final `simulation_timeout` record with the practical game-time
   limit removed and a 120-second processing allowance. Currently six cases;
   the list is frozen only after the bulk campaign completes.
5. Reproduce engine errors with tracing; currently one Scorpion collision error.
6. Rerun every final `wall_timeout` seed, prioritizing matchups where all three
   seeds failed. Currently 97 cases. Preserve the original 150-second game cap
   for this first comparison, and retain the 120-second processing allowance.
7. Export results and checkpoint to the same GitHub branch periodically. Keep
   the original campaign outcomes immutable. Any later corrections must retain
   provenance and require a separate validation of their effect on results.

## Diagnostic evidence

- Real elapsed time, process CPU time, completed ticks, and simulated seconds.
- Progress checkpoints at least once per real second when ticks are advancing,
  or every five simulated seconds, whichever comes first.
- Unit positions, HP, actions, target IDs, timers, ranges, and speeds.
- Counts of combat/movement events, projectiles, and surviving units per side.
- Sampled time since HP/survivor or position changes; these observations flag
  suspicious inactivity but do not establish a deadlock by themselves.
- Tick duration percentiles, the slowest tick, and sampled CPU hotspots.
- Raw CPU profiles retained locally; compact evidence and timelines published.

One diagnostic process runs at a time so timings can be interpreted without
other simulations competing for resources. This differs from the original four
workers, and tracing adds overhead; speed differences alone do not prove a
resource-contention bug. A 120-second cooperative stop returns the latest state
between ticks. A separate 130-second hard stop covers an unresponsive tick or
profile flushing; it preserves the last heartbeat, whose tick is a lower bound.

## Validation and resumption

`tests/ranking-diagnostic-hooks.test.mjs` verifies the instrumented world loop,
winner precedence at the deadline, source-version rejection, and persistence of
both clocks plus a CPU profile at the processing cutoff. Full engine parity is
checked by the three gated replays after the campaign ends.

Resume by running:

```bash
python aoe2x/js_simulation/tools/diagnose_ranking_timeouts.py \
  --campaign aoe2x/js_simulation/calibration/campaigns/unit-rankings-full-deduplicated-2026-10-29 \
  --output aoe2x/js_simulation/calibration/campaigns/unit-rankings-diagnostics-2026-10-29 \
  --publish
```

Finished diagnostic records are reused. Interrupted traces are archived before
a rerun. Source or parity failures stop the diagnostics rather than being waived.
