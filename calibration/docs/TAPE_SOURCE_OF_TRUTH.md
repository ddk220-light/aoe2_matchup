# Tape source of truth

The only permitted tape authority for standard-unit calibration is the local
ignored archive:

`calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip`

Its required SHA-256 is:

`31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`

The locked corpus contains exactly:

- 339 recordings
- 91 unordered matchups
- 14 standard units

The machine-readable authority is
`calibration/source/source_of_truth.json`. Always run
`python -m aoe2x.calibration.source` before analysis or fixture regeneration.
If verification fails, stop; never search for or substitute another tape.

The permitted data flow is:

```text
locked FINAL archive
  -> verified clean rebuild
  -> ignored calibration/tapes
  -> tracked calibration/fixtures
  -> ignored calibration/runs
  -> current calibration/reports
```

No manifest, truth card, winner, surviving-HP value, duration, hit count,
survivor count, median, report, or diagnostic from a superseded recording is
active evidence. Historical calibration material remains available only in
Git history and must not be restored into this workspace.
