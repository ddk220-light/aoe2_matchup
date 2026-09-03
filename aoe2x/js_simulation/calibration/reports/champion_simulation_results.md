# Champion clean-room simulation results

Overall gate: **FAIL**

## Source and clock

- Archive: `aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`
- SHA-256: `33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`
- Authorized recordings: 15 (runner-verified)
- Truth fixture SHA-256: `5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E` (byte-exact runtime lock)
- Mechanics fixture SHA-256: `20F5F9C1422502459986C44474FD9DC278AB9D359070B964BD7E7549DC97B5A6` (byte-exact runtime lock)
- Mechanics reproducibility scope: controlled exporter sources; this report did not re-extract the installed Genie data.
- Simulation clock: 60 Hz; status `provisional_not_published`
- Clock basis: 60 Hz is a provisional simulation hypothesis; it is not selected from HP, winner, or outcome accuracy.

## Strict outcomes

Tape HP percentages below are recomputed from median remaining HP divided by median winner starting HP, then checked against the fixture's reported percentage.

| Ratio | Tape winner | Tape median HP | Tape HP % | Sim winner | Sim HP | Sim HP % | HP delta | HP % delta | Survivors (tape) | Damage events (tape) | Deterministic | Runtime validity | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1v1 | 2 or 3 | 14/70 | 20% | 2 | 14/70 | 20% | +0 | +0 pp | 1 (1) | 9 (9) | yes | FAIL | FAIL |
| 2v1 | 2 | 112/140 | 80% | 2 | 98/140 | 70% | -14 | -10 pp | 2 (2) | 8 (7-8) | yes | FAIL | FAIL |
| 2v3 | 3 | 126/210 | 60% | 3 | 126/210 | 60% | +0 | +0 pp | 2 (2) | 16 (16) | yes | FAIL | FAIL |
| 5v3 | 2 | 252/350 | 72% | 2 | 252/350 | 72% | +0 | +0 pp | 5 (4-5) | 22 (22-25) | yes | FAIL | FAIL |
| 6v3 | 2 | 336/420 | 80% | 2 | 322/420 | 76.66666666666667% | -14 | -3.3333333333333286 pp | 6 (5-6) | 22 (21-23) | yes | FAIL | FAIL |

## Diagnostic traces

Timing and trajectory diagnostics are reported for inspection; they are not calibration targets.

| Ratio | First move | First damage | Final kill | Distance traveled | Blocked ticks | Death-canceled attacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1v1 | tick 78 (1.3s) | tick 183 (3.05s) | tick 663 (11.05s) | 2.1472 tiles | 0 | 1 |
| 2v1 | tick 78 (1.3s) | tick 183 (3.05s) | tick 426 (7.1s) | 5.069398 tiles | 164 | 0 |
| 2v3 | tick 78 (1.3s) | tick 170 (2.833333s) | tick 690 (11.5s) | 10.693144 tiles | 343 | 1 |
| 5v3 | tick 78 (1.3s) | tick 170 (2.833333s) | tick 530 (8.833333s) | 19.041323 tiles | 626 | 2 |
| 6v3 | tick 78 (1.3s) | tick 170 (2.833333s) | tick 510 (8.5s) | 23.480461 tiles | 904 | 1 |

## Tape-repeat diagnostics and playback

Each ratio retains all three authorized repeat tags plus spawn, first-movement, contact, first-damage, interval, hit-count, kill, and winner-HP deltas in the JSON report.

The report stays lean and does not duplicate full traces. The browser viewer must call `createChampionPlaybackData` from `aoe2x/js_simulation/src/champion-comparison.js`; that verified serializer boundary accepts only a supported, deep-immutable run whose target lifecycle, authorized source metadata, terminal state, and canonical state/event hashes validate.

## Determinism hashes

- 1v1: final `1dbd8e65670096884c50f6a89b76a0cf17e3949247b59bf38ba44ee708cdc17d`; events `645cda1510c6952c493640c3dc73ea8cd0840bdb82dae19c9e0acdd3b8c20508`
- 2v1: final `c6d50887e5be851132aed274307dadb682961905b916c16b35a5a1a3dfa0c80e`; events `3a3878083313b7b11131af1b9b4caa7810176d0ccf611e3a8ba39ddab1e74044`
- 2v3: final `a9cb2098e7c41b03acb9f2e9c66784e15412091f59ade8f12cf7d2a795d33d09`; events `4be996bb43e1025b96e04a95b019066e3ed9263d8b49067c1a3e204128a3811b`
- 5v3: final `988b2d3eaba000d60f0dbf45a347317f36b696f364df0929fbb9dd8e3e5687b4`; events `e9c202122982e4485240d214cde986260dfa0b6c82a52eff0564d6830f48fd1e`
- 6v3: final `6ac6457e8fd8e7b276969a8bde195dec1071891402c78844ea43527aa2228d0c`; events `6f527eb51d90c528feca93d9fda8cc64efcda4b58d04a8efff5db698f14b10ec`

## Mechanics audit

Champion 567 (Chinese): 70 HP, 1.0560000228881836 tiles/s, 0.2-tile collision radius, 0-tile range, 2s reload, 0.7500000391155481s attack delay, 14 damage versus self.

- Genie data SHA-256: `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- Reference DB SHA-256: `51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087`
- Heuristic static lint found no unapproved shortcut-pattern matches in 13 audited executable files; 10 expected scenario/map/source-mechanics matches are retained with reasons in JSON.
- Assurance limit: Pattern-based lint plus separate review; this is not a proof of absence or bypass resistance.
- Separate review evidence: `.superpowers/sdd/2026-08-04-cleanroom-champion-small-groups/task-10-report.md`
- Exact lint exclusion: `src/champion-comparison.js` - reporting and static-lint implementation is self-referential and does not advance simulation physics.

The complete JSON companion contains per-unit distance and blocked-tick totals, the target timeline, death-canceled attack records, all repeat/reversal hashes, and field-level mechanics provenance.
