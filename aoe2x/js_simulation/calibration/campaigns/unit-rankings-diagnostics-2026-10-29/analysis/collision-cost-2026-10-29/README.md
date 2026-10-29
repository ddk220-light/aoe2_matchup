# Collision processing analysis

Analyzed 49 completed reruns of original processing-time cutoffs. 43 again
hit the processing allowance. Collision and pair-interaction functions account for
82.6–95.3% of sampled execution time in these runs (median 92.8%).
The diagnostic queue prioritizes three-seed failures, so these are not a random
sample of all battles.

The original campaign had 100 processing-time cutoffs: 97 in the Ranged group and
three Portuguese Cavalier versus Spanish Paladin seeds. None occurred in the
1,769 Infantry runs. The three Cavalier cases finished in the diagnostic reruns.

| Representative rerun | Real processing seconds | Simulated seconds | Result |
|---|---:|---:|---|
| Viking Mounted Crossbowman vs Saracen Heavy Cavalry Archer, seed 0 | 120.4 | 11.5 | Processing cutoff |
| Frank Crossbowman vs Spanish Hussar, seed 0 | 120.3 | 12.35 | Processing cutoff |
| Chinese Heavy Scorpion vs Spanish Elite Skirmisher, seed 0 | 120.2 | 24.25 | Processing cutoff |
| Bohemian Elite Hussite Wagon vs Saracen Heavy Cavalry Archer, seed 0 | 120.5 | 73.47 | Processing cutoff |

The strongest pattern is dense allied ranged formations: Scorpions versus
Skirmishers, mounted ranged units versus other ranged units, and archers contacted
by Hussars. In the inspected Viking and Chinese examples, the opposing formations
were still more than 4.5 tiles apart at the cutoff. Allied crowd handling is
therefore involved even when enemies never touch. HP and survivor totals were
still changing near the cutoff; these examples are advancing battles.

## Measured collision behavior

The solver repeatedly adjusts proposed movements until geometry passes validation.
Every pass scans every body against all 152 scenario obstacles and every body pair.
It also rebuilds pair-interaction objects and keys during repeated checks.

Three observational prefix probes confirmed:

- Viking mounted ranged fight: 32,008 sweeps over 279 ticks; maximum 715 in one tick.
- Chinese Scorpion fight: 38,899 sweeps over 352 ticks; maximum 260 in one tick.
- Frank Crossbowman–Hussar: 26,781 sweeps over 415 ticks; one tick used the entire
  4,096-sweep ceiling. Its remaining obstacle overlap was approximately
  7.6e-12 tiles, larger than the strict 1e-12 epsilon but vastly smaller than the
  existing 1e-4 geometry tolerance. The solver accepted it under that tolerance
  after exhausting the sweep budget. Other ticks also required hundreds of passes.

This establishes repeated collision convergence work as a concrete bottleneck.
The tiny-overlap fallback is one demonstrated trigger, not an explanation for
all slow runs. Broad per-pass scans and per-pair recomputation amplify that cost.

## Candidate fixes to validate

1. Cache pair-interaction properties for the lifetime of one movement solve.
2. Conservatively skip obstacles/pairs that cannot interact along any proposed
   movement, preserving the current ordering of relevant checks.
3. Investigate why negligible residual overlap uses the full sweep budget when
   the result is ultimately accepted with the existing geometry tolerance.
   Any convergence-policy change must be checked for effects on movement/outcomes.
4. Compare exact state/event hashes and performance on both slow cases and clean
   controls before promoting an optimization. Keep numerical correctness and the
   separate reproducible Scorpion overlap error under review.

No production engine behavior was changed in this analysis. Diagnostic traces add
overhead; timings above are measured reruns, not an unbiased benchmark. See
[evidence.json](evidence.json) and the three probe records for counters and source
record paths; the exact extra observation hooks are preserved beside this report.
