# Champion clean-room simulation results

Overall gate: **FAIL**

## Source and clock

- Archive: `aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`
- SHA-256: `33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`
- Authorized recordings: 15 (runner-verified)
- Truth fixture SHA-256: `5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E` (byte-exact runtime lock)
- Mechanics fixture SHA-256: `4D4FE28BBBD2C5BDAC76AC7C2594C8FE569B877A75F230BB47B965848455D0F0` (byte-exact runtime lock)
- Mechanics reproducibility scope: controlled exporter sources; this report did not re-extract the installed Genie data.
- Simulation clock: 60 Hz; status `provisional_not_published`
- Clock basis: 60 Hz is a provisional simulation hypothesis; it is not selected from HP, winner, or outcome accuracy.

## Strict outcomes

Tape HP percentages below are recomputed from median remaining HP divided by median winner starting HP, then checked against the fixture's reported percentage.

| Ratio | Tape winner | Tape median HP | Tape HP % | Sim winner | Sim HP | Sim HP % | HP delta | HP % delta | Survivors (tape) | Damage events (tape) | Deterministic | Runtime validity | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1v1 | 2 or 3 | 14/70 | 20% | 2 | 14/70 | 20% | +0 | +0 pp | 1 (1) | 9 (9) | yes | PASS | PASS |
| 2v1 | 2 | 112/140 | 80% | 2 | 98/140 | 70% | -14 | -10 pp | 2 (2) | 8 (7-8) | yes | PASS | PASS |
| 2v3 | 3 | 126/210 | 60% | 3 | 126/210 | 60% | +0 | +0 pp | 2 (2) | 16 (16) | yes | PASS | PASS |
| 5v3 | 2 | 252/350 | 72% | 2 | 252/350 | 72% | +0 | +0 pp | 5 (4-5) | 22 (22-25) | yes | PASS | PASS |
| 6v3 | 2 | 336/420 | 80% | 2 | 322/420 | 76.66666666666667% | -14 | -3.3333333333333286 pp | 6 (5-6) | 22 (21-23) | yes | PASS | PASS |

## Diagnostic traces

Timing and trajectory diagnostics are reported for inspection; they are not calibration targets.

| Ratio | First move | First damage | Final kill | Distance traveled | Blocked ticks | Death-canceled attacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1v1 | tick 72 (1.2s) | tick 184 (3.066667s) | tick 664 (11.066667s) | 2.1296 tiles | 0 | 1 |
| 2v1 | tick 68 (1.133333s) | tick 184 (3.066667s) | tick 439 (7.316667s) | 5.258562 tiles | 174 | 0 |
| 2v3 | tick 65 (1.083333s) | tick 172 (2.866667s) | tick 700 (11.666667s) | 11.151722 tiles | 394 | 1 |
| 5v3 | tick 62 (1.033333s) | tick 172 (2.866667s) | tick 539 (8.983333s) | 19.988324 tiles | 695 | 2 |
| 6v3 | tick 62 (1.033333s) | tick 172 (2.866667s) | tick 521 (8.683333s) | 24.622072 tiles | 948 | 1 |

## Tape-repeat diagnostics and playback

Each ratio retains all three authorized repeat tags plus spawn, first-movement, contact, first-damage, interval, hit-count, kill, and winner-HP deltas in the JSON report.

The report stays lean and does not duplicate full traces. The browser viewer must call `createChampionPlaybackData` from `aoe2x/js_simulation/src/champion-comparison.js`; that verified serializer boundary accepts only a supported, deep-immutable run whose target lifecycle, authorized source metadata, terminal state, and canonical state/event hashes validate.

## Determinism hashes

- 1v1: final `d7744c658d6142e60b29250e6fcae9a2a52d9e8d40db557fef175ecca1a0c558`; events `98944b2bb93ed4056601cb3d3107e2ffbd6ce8abe949fee3687fe7ba65f5ef81`
- 2v1: final `df5e29ac258be72ff1613335a2772338b50bb62ea214ae22270445014c8a451c`; events `f823c22eab8451df3cbd6f8cda3bc854dba4d62bcc6335caeb7231fc21f5b483`
- 2v3: final `ac1c0c9ba0c2392dfef105e0f29678f21e9d93b568d06a4613644a397d6a5da7`; events `c8532bf940cf07345a765993a6933e7478f893a633f0e94003fd1fddc162c8c4`
- 5v3: final `21b88ceac1d98bbc6d647dac6c51be8cdc5393bfd47975ade4da1595e3b0e471`; events `fb591bf48306c87b02e090fbfc0d6c1fb942be8ba34178fc95247afc2f0cf1a3`
- 6v3: final `cc11ffc90f55bc21ef5f5ca4cd0b097f1afc9762806ce77a78adf8647244f799`; events `17311606a0e59bdd922f02b4110521c37c989bc777570b719b1d604ad738bb07`

## Mechanics audit

Champion 567 (Chinese): 70 HP, 1.0560000228881836 tiles/s, 0.2-tile collision radius, 0-tile range, 2s reload, 0.7500000391155481s attack delay, 14 damage versus self.

- Genie data SHA-256: `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- Reference DB SHA-256: `51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087`
- **Audit failed:** 2 prohibited source finding(s) and 0 exact-fingerprint count mismatch(es).

The complete JSON companion contains per-unit distance and blocked-tick totals, the target timeline, death-canceled attack records, all repeat/reversal hashes, and field-level mechanics provenance.
