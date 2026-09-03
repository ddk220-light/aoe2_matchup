# Golden tape comparison workflow

This runbook records the clean-room process used to bring an authorized golden
archive into the project, reproduce its tape truth, run the current JavaScript
engine from exact tape starts, and publish a recoverable comparison.

It is the required process for future simulation-versus-tape work. Do not use
the Standard Units aggregate archive, old derived corpora, a reversed matchup,
or a manually selected viewer count as a substitute for a separately named and
authorized golden tape.

## 1. Establish authorization and identity

Before reading tape evidence, establish all of the following:

- the user-designated external file;
- the exact filename;
- the matchup orientation and unit masters;
- the expected golden naming convention;
- the external file's SHA-256;
- explicit authorization for this archive.

The active project-local location is:

`calibration/source/<archive-name>.zip`

The active manifest is:

`calibration/source/dedicated_ranged_melee_sources.json`

The project must stop if the archive is absent, its hash changes, or its name
does not correspond to an expected dedicated matchup. Never substitute another
tape.

## 2. Verify, copy, and verify again

For an incrementally authorized archive, hash the external file before copying:

```powershell
Get-FileHash `
  -LiteralPath 'C:\Users\<user>\Downloads\<archive>.zip' `
  -Algorithm SHA256
```

Copy it byte-for-byte into the project-local source directory:

```powershell
Copy-Item `
  -LiteralPath 'C:\Users\<user>\Downloads\<archive>.zip' `
  -Destination 'calibration\source\<archive>.zip'
```

Hash the project-local copy independently and require equality:

```powershell
Get-FileHash `
  -LiteralPath 'calibration\source\<archive>.zip' `
  -Algorithm SHA256
```

Record the filename, relative project-local path, uppercase SHA-256, source
kind, authorization, original authorized source, date, and byte length in the
manifest. Update `archive_count`, `ratio_count`, and `tape_run_count`.

When one source directory contains the complete known corpus, the intake tool
performs the same hash/copy/rehash sequence and rejects a known hash mismatch:

```powershell
node tools/intake_dedicated_ranged_melee_goldens.mjs `
  'C:\Users\<user>\Downloads'
```

The full intake tool expects every archive currently declared in
`src/dedicated-golden-corpus.js`. For a single new archive, use the explicit
incremental sequence above, then verify the final manifest with the corpus
tests.

## 3. Register the matchup

Add the expected ranged slug, melee slug, optional legacy fixture name, and
exact archive filename to `src/dedicated-golden-corpus.js`.

Add the expected archive hash to the intake tool's known-hash table. Add the
unit masters to `tools/import_dedicated_ranged_melee_goldens.py` if the importer
does not already know the pair.

Registration is intentionally closed-world: loading fails if the manifest or
truth fixture contains an unexpected archive, an unauthorized archive, or a
fixture whose SHA-256 disagrees with the manifest.

## 4. Import truth from `frames.bin`

The Python importer reads each archive directly. It discovers the five ratio
rows and the five repeats per ratio, decompresses the recorded summaries, and
extracts:

- ratio and repeat number;
- owner 2 and owner 3 unit counts and masters;
- exact starting unit IDs, owners, masters, and coordinates;
- starting HP by owner;
- winner, remaining winner HP, and signed tape score;
- archive filename and SHA-256 provenance.

Import all registered archives:

```powershell
python tools/import_dedicated_ranged_melee_goldens.py
```

Import only newly added archives while preserving already verified entries:

```powershell
python tools/import_dedicated_ranged_melee_goldens.py `
  aoe2_golden_kiting_<pair-a>_<date>.zip `
  aoe2_golden_kiting_<pair-b>_<date>.zip
```

Targeted merge mode verifies the selected local archives and retains an
unselected truth entry only when its archive and SHA-256 still agree with the
manifest. Derived truth must never be hand-edited to improve a simulation
score.

The generated fixture is:

`calibration/fixtures/dedicated_ranged_melee/dedicated_ranged_melee_truth.json`

## 5. Validate corpus shape before simulation

Run the focused corpus and runner tests:

```powershell
node --test `
  tests/dedicated-golden-corpus.test.mjs `
  tests/dedicated-golden-runner.test.mjs `
  tests/dedicated-golden-comparison.test.mjs
```

The current expected shape is:

- 19 authorized archives;
- 95 ratio rows;
- 475 tape repeats;
- exactly five ratios per matchup;
- exactly repeats 1–5 per ratio;
- exact starting roster sizes and expected unit masters;
- matching manifest/truth SHA-256 values.

Do not begin a long engine run if these checks fail.

## 6. How an exact-repeat scenario is built

`scenarioFromDedicatedRun()` creates every unit from that repeat's
`starting_units`. It does not use `placement.js`.

For mobile-ranged tapes, the current scenario uses:

- ranged side normalized to owner 2;
- mechanics-derived kite timing;
- cohesive navigation;
- one attack-move order for all melee chasers;
- live target acquisition during the approach;
- chase capture enabled;
- zero chase-engagement dwell;
- no ordinary pairwise allied-transit experiment;
- range-1 wedge transit only when sourced melee range is at least 1;
- preventive contact-graph steering and exclusive overlap control for owner 3.

For Heavy Scorpion, the scenario does not create a kite controller. Scorpions
use native siege AI and minimum-range retreat. The melee owner still receives
preventive crowd steering and exclusive overlap control.

The fight cap is 9,000 ticks. Dedicated workers disable snapshots to reduce
memory but retain the full event log and deterministic hashes.

## 7. Run recoverably and in parallel

### Full corpus

```powershell
node tools/run_recoverable_dedicated_benchmark.mjs `
  --output-dir calibration/reports/<run-name>
```

The full runner checkpoints one complete matchup: five ratios × five repeats.

### Selected matchup families

```powershell
node tools/run_recoverable_dedicated_rows.mjs `
  --output-dir calibration/reports/<run-name> `
  --matchup-ids <matchup-id-a>,<matchup-id-b>
```

The selective runner checkpoints one complete ratio row: five exact repeats.
This is preferred when a mechanic change can affect only named families.

### Worker selection

By default, concurrency is:

`min(pending work, floor(os.availableParallelism() × 0.8))`

Use `--workers N` to leave additional capacity for interactive work or to cap
memory use. Each worker is a separate Node process, allowing CPU-bound
JavaScript simulations to use multiple cores.

### Recovery guarantee

Every checkpoint is written to a temporary file, flushed, and atomically
renamed. `progress.json` records completed, active, and pending work.

The run signature hashes:

- all engine source;
- Golden Arena map fixture;
- unit mechanics fixtures;
- authorized archive manifest;
- imported truth;
- runner and worker code.

Rerun the exact same command after interruption. Valid checkpoints with the
same signature and expected shape are reused; only missing work is dispatched.
A stale, malformed, duplicate, or mismatched checkpoint stops the merge rather
than contaminating the result.

## 8. Scoring

Each tape and simulation repeat receives signed winner-HP percentage:

`100 × winner remaining HP / that owner's starting HP`

- owner 2/ranged win: negative;
- owner 3/melee win: positive;
- sign mismatch: wrong winner;
- magnitude: strength of the surviving army.

For each ratio row, report:

- tape mean, minimum, maximum, and owner-3 win rate;
- simulation mean, minimum, maximum, and owner-3 win rate;
- signed and absolute difference between the two means;
- distance from the simulation mean to the tape's five-repeat range;
- share of simulation repeat scores inside the tape range;
- repeat-aligned deltas;
- unresolved and wrong-winner counts.

The existing review threshold is absolute mean delta greater than 25 points.
Wrong winners and unresolved runs are always reported separately. A row can
have a moderately large mean delta and still sit inside a wide tape band; do
not describe it as a directional failure without checking both sign and band.

## 9. Validate the finished report independently

Before publishing a result:

1. Confirm the expected number of rows and samples.
2. Recompute tape and simulation means from the raw samples.
3. Recompute `abs(sim mean - tape mean)` independently.
4. Verify every repeat has the intended tape score and starting position set.
5. Count unresolved runs and sign mismatches.
6. Rehash the project-local archives and compare them with the manifest.
7. Rerun the focused tests after all fixture/code changes.
8. Inspect `run-manifest.json` for worker count, signature, and selected IDs.

The durable outputs are:

- `results.json`: complete row/sample evidence;
- `results.csv`: compact human-readable table;
- `run-manifest.json`: signature, selection, CPU, and recovery policy;
- `progress.json`: final queue state;
- `checkpoints/`: resumable row or matchup units.

## 10. Hand Cannoneer intake and comparison — 2026-08-15

The newest incremental intake added:

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_kiting_hcvschampion_2026-08-14.zip` | `468AB6CDBAD27FAEED9690E47A6B8BE4865A555DDD1063CFDE8B2A2D8D5C3A99` |
| `aoe2_golden_kiting_hcvspaladin_2026-08-14.zip` | `F472C648A06913B6E0DDAD1A7E2E9DAD17E70A7F62F113C5C2CD6A6F9AEC50F2` |

Both external files and project-local copies matched byte-for-byte hashes. The
import found five ratios and repeats 1–5 for each matchup, for 10 rows and 50
tape runs.

The current-engine command was:

```powershell
node tools/run_recoverable_dedicated_rows.mjs `
  --output-dir calibration/reports/hand_cannoneer_current_engine_2026-08-15 `
  --workers 10 `
  --matchup-ids hand_cannoneer_vs_champion,hand_cannoneer_vs_paladin
```

The machine exposed 24 logical CPUs. All 50 simulations resolved in 277.8
seconds. The result had zero wrong winners, zero rows above 25 points, eight
simulation means inside their tape bands, and 3.67-point mean absolute row
delta.

See the [Hand Cannoneer result summary](../calibration/reports/hand_cannoneer_current_engine_2026-08-15/README.md).

## Failure modes this process prevents

- comparing against a non-golden or differently named archive;
- silently using an old Standard Units derived row;
- copying a tape without proving byte identity;
- losing completed work after a long worker failure;
- resuming checkpoints under different engine code;
- accidentally rerunning unaffected matchup families;
- comparing generated placements with tape placements;
- hiding timeouts or wrong winners inside an aggregate mean;
- hand-editing derived truth to fit the simulator.
