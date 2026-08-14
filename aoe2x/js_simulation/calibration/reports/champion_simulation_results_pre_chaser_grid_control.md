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
| 2v3 | 3 | 126/210 | 60% | 3 | 126/210 | 60% | +0 | +0 pp | 3 (2) | 16 (16) | yes | PASS | FAIL |
| 5v3 | 2 | 252/350 | 72% | 2 | 252/350 | 72% | +0 | +0 pp | 5 (4-5) | 22 (22-25) | yes | PASS | PASS |
| 6v3 | 2 | 336/420 | 80% | 2 | 322/420 | 76.66666666666667% | -14 | -3.3333333333333286 pp | 6 (5-6) | 22 (21-23) | yes | PASS | PASS |

## Diagnostic traces

Timing and trajectory diagnostics are reported for inspection; they are not calibration targets.

| Ratio | First move | First damage | Final kill | Distance traveled | Blocked ticks | Death-canceled attacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1v1 | tick 72 (1.2s) | tick 184 (3.066667s) | tick 664 (11.066667s) | 2.1296 tiles | 0 | 1 |
| 2v1 | tick 68 (1.133333s) | tick 184 (3.066667s) | tick 439 (7.316667s) | 5.258562 tiles | 174 | 0 |
| 2v3 | tick 65 (1.083333s) | tick 172 (2.866667s) | tick 539 (8.983333s) | 9.662412 tiles | 241 | 0 |
| 5v3 | tick 62 (1.033333s) | tick 172 (2.866667s) | tick 594 (9.9s) | 19.599311 tiles | 822 | 3 |
| 6v3 | tick 62 (1.033333s) | tick 172 (2.866667s) | tick 554 (9.233333s) | 24.269148 tiles | 867 | 2 |

## Tape-repeat diagnostics and playback

Each ratio retains all three authorized repeat tags plus spawn, first-movement, contact, first-damage, interval, hit-count, kill, and winner-HP deltas in the JSON report.

The report stays lean and does not duplicate full traces. The browser viewer must call `createChampionPlaybackData` from `aoe2x/js_simulation/src/champion-comparison.js`; that verified serializer boundary accepts only a supported, deep-immutable run whose target lifecycle, authorized source metadata, terminal state, and canonical state/event hashes validate.

## Determinism hashes

- 1v1: final `d7744c658d6142e60b29250e6fcae9a2a52d9e8d40db557fef175ecca1a0c558`; events `98944b2bb93ed4056601cb3d3107e2ffbd6ce8abe949fee3687fe7ba65f5ef81`
- 2v1: final `df5e29ac258be72ff1613335a2772338b50bb62ea214ae22270445014c8a451c`; events `fcb2ccc63e22160165543285e6f24489fc5e2ce912103c5009252ba33aaa25e7`
- 2v3: final `3d21da378aa057507540f12fbcaf7befdae4e7ec601f24c4ca7689e38ece9679`; events `00baff8237ee67ac686f2d16bb2c2e397df1ba602fc48a353ef8b6f1e0f8d60b`
- 5v3: final `9f330dbee831add2c2ebc0873beb59c52acf50fd163abc8ac2a36c6ba818b852`; events `b0fedec5edd39ab314e58a47b11d742ba19a36d62e98abdf17dad1bf6704adaa`
- 6v3: final `e5a283a66893687518cc81fe067cdef169895c87fbfd75efa71bb786eb562543`; events `2ffa02992a9907db24df1d63a500dbb0b1a4f5c94a910da3ea369f4e49ca4dcb`

## Mechanics audit

Champion 567 (Chinese): 70 HP, 1.0560000228881836 tiles/s, 0.2-tile collision radius, 0-tile range, 2s reload, 0.7500000391155481s attack delay, 14 damage versus self.

- Genie data SHA-256: `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- Reference DB SHA-256: `51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087`
- **Audit failed:** 2 prohibited source finding(s) and 0 exact-fingerprint count mismatch(es).

The complete JSON companion contains per-unit distance and blocked-tick totals, the target timeline, death-canceled attack records, all repeat/reversal hashes, and field-level mechanics provenance.
