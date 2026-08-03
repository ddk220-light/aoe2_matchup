# Self-Contained Standard-Unit Calibration Workspace

**Date:** 2026-08-03  
**Status:** Proposed for implementation  
**Scope:** Non-production calibration tooling, fixtures, tests, and documentation

## Objective

Contain all future standard-unit tape calibration work inside
`D:/AI/aoe2_matchup` without moving or changing either production simulation
engine. Make the active calibration corpus reproducible from one ignored local
archive and prevent older recordings, reports, counts, or scale assumptions
from entering any result.

## Sole tape authority

The only allowed tape source is:

```text
calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip
SHA-256: 31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9
```

The archive contains 339 recordings covering all 91 unordered matchups among
the 14 standard units. The archive and its extracted streams are local inputs
and are ignored by Git. A tracked source lock records the expected filename,
hash, and corpus counts.

Every command that reads tape evidence must first verify the archive hash. It
must fail closed when the archive is absent or has a different hash. There is
no fallback to `C:/Users/ddk22/Downloads`, `D:/AI/aoe2_golden`, an older ZIP,
an older manifest, or an older derived report.

## Production boundary

The migration must not change:

- `apps/website/static/js/engine/`, the canonical browser/headless JavaScript
  simulation engine;
- `aoe2x/sim/`, the Python simulation engines and production combat-unit
  loading behavior;
- production matchup data, databases, APIs, deployment configuration, or
  production scales such as `30v30` and `3k`.

Calibration runners continue to import the existing JavaScript engine. They do
not copy, fork, or relocate it. All path and corpus changes occur in
`aoe2x/calibration/`, `tools/simjs/`, calibration-focused tests, and the new
workspace described below.

## Workspace layout

```text
D:/AI/aoe2_matchup/
├── aoe2x/
│   ├── sim/                         # unchanged Python simulator
│   └── calibration/                 # importable calibration pipeline
├── apps/website/static/js/engine/   # unchanged canonical JS simulator
├── tools/simjs/                     # headless runners and diagnostics
├── calibration/
│   ├── README.md                    # one current workflow entry point
│   ├── source/
│   │   ├── aoe2_golden_STANDARD_UNITS_FINAL.zip  # ignored
│   │   └── source_of_truth.json                 # tracked
│   ├── tapes/                       # ignored extracted streams
│   ├── fixtures/                    # tracked, regenerated from FINAL only
│   │   ├── manifest.json
│   │   ├── truth/
│   │   ├── spawns.json
│   │   ├── combat_dicts.json
│   │   ├── matchups.json
│   │   └── fight_sets.json
│   ├── runs/                        # ignored per-seed simulation outcomes
│   ├── reports/                     # current derived scoreboards
│   └── docs/                        # current FINAL-based analysis only
└── .scratch/calibration/            # ignored, disposable intermediates
```

`D:/AI/aoe2_golden` remains untouched as cold historical storage, but no active
calibration code, test, or document may read it. New outputs must not be
written there.

## What replaces `data/calibration`

The current directory mixes four responsibilities. The new layout separates
them:

| Current content | New location | Role |
|---|---|---|
| `source_of_truth.json` | `calibration/source/` | Immutable source identity |
| `manifest.json`, `truth/`, `spawns.json` | `calibration/fixtures/` | Tape-derived evidence |
| `combat_dicts.json`, `matchups.json`, `fight_sets.json` | `calibration/fixtures/` | Runner inputs and corpus definitions |
| `runs/` | `calibration/reports/` for selected scoreboards; `calibration/runs/` for raw outcomes | Derived output |
| `analysis/` | `calibration/docs/` or `calibration/reports/` | Current analysis |

After consumers move, `data/calibration/` is removed. Compatibility aliases,
duplicate copies, and fallback reads are not retained because they would allow
stale data to survive silently.

## Tape ingestion and derivation flow

```text
ignored FINAL ZIP
    -> verify exact SHA-256
    -> extract into ignored calibration/tapes/
    -> rebuild tracked calibration/fixtures/ from an empty staging directory
    -> validate 339 recordings / 91 unordered matchups / FINAL hash on every row
    -> atomically replace the active fixture set
    -> run simulations into ignored calibration/runs/<run-id>/
    -> write selected current summaries to calibration/reports/
```

Derivation never appends to existing fixtures. It builds into a clean temporary
directory and replaces the active set only after all provenance and completeness
checks pass. This prevents removed or renamed recordings from lingering.

## Scale simplification

The standard-unit tape calibration runner uses only the recorded tape
composition, named `tape`. The legacy calibration-only `equal_count` scale is
removed from defaults, plans, report code, and calibration tests. A requested
unknown scale is an error.

This change does not affect the production matchup application's `30v30`, `3k`,
or any other product-facing scale. Those belong to a separate pipeline.

## Documentation cleanup

The active `calibration/docs/` directory contains only:

- the current workflow and corpus definition;
- diagnostics recomputed from FINAL;
- implementation notes that do not assert measurements from older tapes.

Historical calibration documents that quote old winner margins, HP remaining,
fight durations, hit counts, corpus sizes, ZIP names, or conclusions are removed
from the active tree. Git history remains the historical record. Mechanistic
notes may be retained only after removing stale measurements and clearly
labeling them as hypotheses to be retested against FINAL.

Code comments and test descriptions are subject to the same rule: no old tape
path or old measured value may remain as current evidence.

## Test strategy

The migration is accepted only when all of these pass:

1. **Source lock:** the local ZIP hash matches the tracked lock.
2. **Clean rebuild:** a new empty workspace produces exactly 339 manifest rows,
   339 truth cards, and 91 unordered matchups.
3. **Provenance:** every manifest row carries the FINAL SHA-256.
4. **No fallback:** tests prove missing or mismatched FINAL input fails before
   extraction, scoring, or reporting.
5. **Path isolation:** active calibration code contains no reference to
   `D:/AI/aoe2_golden`, Downloads, or `data/calibration`.
6. **Scale isolation:** calibration supports only `tape`; product scale tests
   remain unchanged.
7. **Synthetic unit tests:** tests needing database/report shapes construct
   temporary fixtures instead of relying on historical tape artifacts.
8. **Engine immutability:** no diff exists under `apps/website/static/js/engine/`
   or `aoe2x/sim/` as part of this migration.
9. **Focused regression:** ingestion, extraction, filtering, runner, scoring,
   report, and path tests pass from the new workspace.

## Git policy

These paths are ignored:

```text
calibration/source/*.zip
calibration/tapes/
calibration/runs/
.scratch/calibration/
```

Tracked content is limited to source metadata, reproducible compact fixtures,
selected current reports, current documentation, code, and tests. The ignored
ZIP must never be staged accidentally.

## Migration sequence

1. Add one central calibration-path module rooted at the repository's
   `calibration/` directory; allow tests to override the root explicitly.
2. Add source-lock and clean-rebuild tests before changing paths.
3. Copy the FINAL ZIP into the ignored `calibration/source/` location and verify
   its hash.
4. Regenerate the workspace from FINAL into clean staging.
5. Move active fixtures and current FINAL-based documentation.
6. Update non-production calibration readers and writers to use the central
   paths.
7. Remove the legacy `equal_count` calibration scale.
8. Remove stale calibration documents and old path/value references from the
   active tree.
9. Run path, provenance, focused calibration, and broader regression checks.
10. Leave `D:/AI/aoe2_golden` unchanged; do not delete or archive anything else
    during this migration.

## Success criteria

The work is complete when a developer can place the ignored FINAL ZIP in
`calibration/source/`, run one documented rebuild command, and obtain the full
active calibration corpus and reports without reading or writing outside
`D:/AI/aoe2_matchup`. Production simulator code has no migration diff, active
calibration documentation contains no old tape measurements, and every result
is traceable to the locked FINAL hash.
