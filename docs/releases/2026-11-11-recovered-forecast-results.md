# Completed forecast recovery results

The owner requested “Push and deploy” after reviewing completion of the 36-case
recovery. This authorizes this data release and publication of the recovery
archive. Recurring research tasks remain stopped; future automatic releases
remain unauthorized.

All 36 previously unfinished contexts now have complete recovery evidence:
11 single-seed confirmations and 25 multi-seed validations. They update 220
displayed cells, with 34 retained outcomes and two changed outcomes. One changed
context has mixed winners across ten seeds and remains `close_uncertain`.

The published archive contains 93 individual seed records: 80 new recovery runs
and 13 preserved original runs, including all 57 authorized reruns for the 19
older-engine contexts. Six contexts combine original and recovery engine versions.
Each result retains its actual engine version, source commit, hashes, remaining
HP and survivors. These are separately versioned recovery results, not
homogeneous frozen-engine validation or a new comprehensive live-game fidelity
validation. Agreement-dependent stopping cannot estimate unbiased accuracy.

The original 39,112 frozen-protocol reviews remain byte-identical, as do the
10,222 previous mismatch reviews. Overall forecast coverage is now 39,148
contexts / 50,228 cells, with 31,906 single-seed confirmations and 7,242
multi-seed validations. The original campaign still honestly records 36
historically unfinished contexts; additive `recovery_validation` and
`forecastCoverage` metadata describe their recovery without rewriting history.

The import preserves all 68,880 other evidence blobs and 151,003 other cells.
Original forecasts, flags, source contexts and recovery-projection provenance
remain available in each recovered evidence object's `originalEvidence`.
The recovery review's original `productionEligible: false` preparation record is
preserved together with the new owner release authorization.

Research source: `8f0f09930839f44da57ebc3df756917150f81fc5`, snapshot 002,
on `simulations/civ-forecast-recovery-2026-11-10`. The source archive and run
ledger were published at `be3db171438da99dfc86f12535db168baba66822`.
The serving DB SHA-256 is
`bdbbeacfc8dffc190d3b477fc0e7657f1d324d69ec4704f43211af0a774f34ea`
(99,188,736 bytes, below GitHub's 100 MiB file limit).

The reviewed export, authorization, full-grid import verification and per-run
records are in `data/validation/civ-matchups-forecast-recovery-2026-11-10/2026-11-11/`.
The advisor component becomes
`cae47bc6fcbb4948c0c132effd700d1c1e0e5952f85d3253a8b39f265f06577b`.
Civilization, ranking, simulator and engine components stay unchanged. This
release includes no simulation execution, UI redesign or recommendation formula
change. Synthetic importer tests use archived original evidence now that
production has no remaining unreviewed forecasts.

Local checks: 522 website Python tests passed (26 existing skips), 11 advisor
model tests passed, and all 195 public feature projections validated. Full-grid
and committed-source checks passed without rerunning a simulation.
