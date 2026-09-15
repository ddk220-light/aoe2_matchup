# Champi geometric reruns

## Completed September 15, 2026

All 296 captures verified, zero failures; all 296 compact archives verified on
the external disk. Original standard captures preserved. Wins changed from
42 to 22 (Incas), 33 to 24 (Mapuche), 28 to 18 (Muisca), and 24 to 16 (Tupi).
There were 49 observed winner changes: 48 wins became losses, one loss became a
win. The Mapuche/Ghulam new win had identical starting counts. Twenty-six
opponents changed their cross-civilization winner pattern; eight lost a previous
Inca-only victory. Imperial Camel and Korean War Wagon changed from all four
Champi winning to all four losing. Reports are in the work directory below.

This formula is now the approved default for new work. See
[BALANCE_POLICY.md](BALANCE_POLICY.md). No captures or scheduler are running for
this completed campaign; do not restart it to implement code cleanup.

Authorized after reviewing the completed 296 standard captures. This is a new
296-game capture campaign: 74 opponents for each of Incas, Mapuche, Muisca, Tupi.
Rerun even the 28 matchups whose rounded counts do not change. Do not overwrite
the standard captures, modify game prices, render overlays, or upload videos.

## Count policy

`geometric_shared_discount_v1` uses per-physical-unit costs from
`data/recording-costs.json` and population/classification from
`data/recording-balance.json`.

For shared units, comparison cost is final purchase cost plus half the positive
food and wood savings from the undiscounted per-unit price. Gold savings remain
fully effective. Civilization-exclusive units use the actual final price. A cost
increase is never halved. Production batches are divided before applying this
rule; population is never used as a purchase-cost divisor.

Shared entries in this roster: Champi, Genitour, Condottiero, Imperial Skirmisher.
The catalog additionally supports Spanish Paladin for the agreed examples.
Savar, Houfnice and Imperial Camel are civilization-exclusive final upgrades.
Blackwood and Karambit each use 0.5 population, read from installed DAT resource
storage 4 and cross-checked against storage 11; remaining entries use 1.

Let `S = comparisonCost * militaryPopulation`. The lower-S army receives 27
physical units. The other receives `round_half_up(27 * sqrt(lowerS / higherS))`,
clamped to 1..27. Retain the 5,000 actual-resource ceiling; fail preflight rather
than silently change the formula if an army exceeds it. All 296 plans passed.
The constant population surcharge discussed earlier is NOT used.

Examples: Inca Champi comparison cost 67.5, other Champi 75. Against Spanish
Paladin: 27 vs 19 for Incas, 27 vs 20 for others. Against Monaspa: 27 vs 22 and
27 vs 23, respectively. Standard Golden templates, placements, full HP, camera,
P1 civilization=P3, and the nine-Hussar mixed-matchup screen remain unchanged.

## Start/resume and inspect

Work directory: `data/local/champi-geometric-comparison`.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
apps/video/.venv/Scripts/python.exe apps/video/prepare_champi_geometric.py
apps/video/.venv/Scripts/python.exe apps/video/run_champi_comparison_capture.py --work data/local/champi-geometric-comparison
```

Use one hidden background worker on Windows; inspect `worker.json`, `worker.log`,
`worker.err.log` and `capture/status.json` before starting another. The recorder
holds the existing exclusive game-driver lock. Jobs use `champi_geometric_*`,
distinct from `champi_standard_*`. Opponents are grouped with four civilizations
in sequence, so each cross-civ comparison completes early. `PAUSE` in this work
directory requests a boundary stop. Thermal pauses and an 8-GiB local-space
reserve also stop at a boundary. CPU sensor setup was previously declined; GPU
checks remain active, and CPU sensor absence must not be described as a valid
CPU temperature check.

The previously paused scheduled monitor was never reactivated: automatic
approval review required renewed approval, which was not supplied. The capture
worker completed independently. Leave that scheduled monitor paused.

## Reporting

`report_champi_geometric.py` reads frozen `baseline.json`, new approved plans,
and verified new capture manifests. It writes `comparison.json` and
`comparison.md` throughout the run and at completion. It includes old/new counts,
results, winner HP percentages, survivors, individual flips, all-win to all-loss
patterns, loss of an Inca-only win, and pairwise Incas-vs-each-other-civ contrasts.
Pending groups must not be interpreted as losses. The report flags result changes
with identical counts: these cannot be attributed to this count-policy change.
One battle per condition cannot prove causality even when counts differ.

## Storage

The runner invokes report and archive maintenance once per minute while the
separate game process continues capturing. `archive_champi_geometric.py` copies
only newly verified runs into `D:/AoE2 Renders/champi-geometric-{civ}`. Each folder
holds descriptively named MP4/frames.bin pairs, `run.json` and frozen baseline
metadata. SHA-256 checks precede each individual local media deletion. Preserve
all small local recording/plan/result metadata. The archive index retains timing
and provenance needed by `materialize_compact_recording.py` for later overlays.
Never delete or overwrite the old `champi-standard-*` archives.

Interrupted deletion resumes from a durable `copied_verified` receipt; never
assume a partially pruned original bundle remains a complete recorder bundle.
An absent disk or failed checksum retains remaining local sources. Inspect
`archive-status.json` and worker errors before claiming archival completion.

Broader unrelated legacy cleanup remains separate. The prohibited old
`scripts/archive_uploaded_champi_storage.ps1` is not used by this workflow.

## Validation

- Node tests: `recording-balance.test.mjs` plus existing `recording-costs.test.mjs`.
- Python independently rederives policy evidence and counts in `validate_plan_costs`.
- Preparation validates all 296 costs, counts, resource ceilings and unchanged
  Golden configuration before game interaction, saving `preflight.json`.
- Captures validate real gRPC opening counts and terminal ownership, raw hashes,
  and completed battle clip exports before publication as `verified`.
- Review the first four clips for orientation and battle framing; automated
  validation alone does not establish that the picture is correct.

See [original handoff](CHAMPI_HANDOFF.md) and
[compact storage](COMPACT_STORAGE.md) for old captures and restore tooling.
