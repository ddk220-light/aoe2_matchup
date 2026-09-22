# Final v15 source reference — 2026-09-22

These are text-identical snapshots of the small local scripts used to finish
the ten approved-format Shorts. They preserve the exact audio/timing and
cached-combat assembly logic alongside the [operator procedure](../../SHORTS_FROM_RAW.md).
They are **not** a newly generalized CLI or a media archive.

Restore the files into `data/local/<batch-name>/` with the relative layout below
before running them. Do not execute them under `docs/`: their relative paths
expect the local layout. Configure machine-specific paths before using another
workstation. Import `run_batch.py` for environment setup; do not launch its old
batch `main()`.

The test snapshot is stored as `test_final_batch.py.txt` so repository-wide
test discovery does not execute an archive-dependent reference under `docs/`.
Rename that copy to `test_final_batch.py` in the restored local folder.

```text
<batch-name>/
  run_batch.py
  batch.json
  render_final_batch.py
  test_final_batch.py
  finish_final_batch.py
  final-v15/voices/
    build_catalog.py
    build_editorial_candidates.py
    inspect_xianbei_actions.py
```

`batch.json` records the original ten source locations and substitutions chosen
because footage existed. Replace it for new work. Original MP4s, telemetry,
plans, prepared animation PNGs, WAV/WEM files, bank dumps, model weights,
intermediate battle exports and approval evidence stay in the local archive,
not Git. The Git checkout alone does not contain those external dependencies.

For the original batch, the renderer reuses number 3's corrected Teutonic export,
number 4's existing Seed export, and the approved number 10 file. Its test and
finisher scripts intentionally require that dataset. For a new raw matchup,
use number 1 and the explicit preparation/composition calls in the procedure.

Do not run `finish_final_batch.py` until the ten actual exported review sheets
have been inspected: it writes that review assertion. Do not silently rerun
completed clips or replace approved files just because these source snapshots
have been restored.
