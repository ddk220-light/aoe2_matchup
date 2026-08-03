# Standard-unit calibration workspace

This directory is the complete non-production workspace for comparing the
JavaScript battle simulator with the locked FINAL standard-unit recordings.
The production engine remains in `apps/website/static/js/engine/`; this
workspace only supplies calibration inputs, generated fixtures, runs, and
reports.

## Rebuild and run

Run these commands from the repository root:

```powershell
python -m aoe2x.calibration.source
python -m aoe2x.calibration.rebuild
python tools/simjs/dump_calib_dicts.py
python tools/simjs/dump_calib_spawns.py
node tools/simjs/calib_runner.mjs --seeds 20
python -m aoe2x.calibration.score --all
```

The first command verifies the archive name, SHA-256, ZIP integrity, and
locked corpus counts. The rebuild is clean: it stages all derived data,
validates 339 recordings, 339 truth cards, 91 unordered matchups, and 14
units, then replaces the active tape and fixture directories together.

## Layout

- `source/source_of_truth.json` is the tracked authority lock.
- `source/*.zip` is the ignored local copy of the locked archive.
- `tapes/` is ignored extracted evidence generated only by the rebuild.
- `fixtures/` contains the tracked compact manifest, truth cards, matchup
  authority, combat dictionaries, spawn positions, and unit-group policy.
- `runs/` is ignored raw simulator output.
- `reports/` contains compact scoreboards that may be reviewed and tracked.
- `docs/` contains only current FINAL-backed calibration documentation.

Do not append new tape evidence to the fixture set and do not substitute a
different archive. Replace the lock only through an explicitly approved corpus
change. Simulation count scales—including `tape`, `equal_count`, `30v30`, and
`3k`—are outside this storage migration and retain their existing meanings.

See [docs/TAPE_SOURCE_OF_TRUTH.md](docs/TAPE_SOURCE_OF_TRUTH.md).
