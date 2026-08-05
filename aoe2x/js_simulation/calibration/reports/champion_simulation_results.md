# Champion clean-room simulation results

Overall gate: **PASS**

## Source and clock

- Archive: `aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`
- SHA-256: `33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`
- Authorized recordings: 15 (runner-verified)
- Truth fixture SHA-256: `5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E` (byte-exact runtime lock)
- Mechanics fixture SHA-256: `06CDE4E98AD95E8D387CEDA58217F3B1CFB90E7A57ADD9536EB82B090AD86595` (byte-exact runtime lock)
- Mechanics reproducibility scope: controlled exporter sources; this report did not re-extract the installed Genie data.
- Simulation clock: 60 Hz; status `provisional_not_published`
- Clock basis: 60 Hz is a provisional simulation hypothesis; it is not selected from HP, winner, or outcome accuracy.

## Strict outcomes

Tape HP percentages below are recomputed from median remaining HP divided by median winner starting HP, then checked against the fixture's reported percentage.

| Ratio | Tape winner | Tape median HP | Tape HP % | Sim winner | Sim HP | Sim HP % | HP delta | HP % delta | Survivors (tape) | Damage events (tape) | Deterministic | Runtime validity | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1v1 | 2 or 3 | 14/70 | 20% | 2 | 14/70 | 20% | +0 | +0 pp | 1 (1) | 9 (9) | yes | PASS | PASS |
| 2v1 | 2 | 112/140 | 80% | 2 | 112/140 | 80% | +0 | +0 pp | 2 (2) | 7 (7-8) | yes | PASS | PASS |
| 2v3 | 3 | 126/210 | 60% | 3 | 126/210 | 60% | +0 | +0 pp | 2 (2) | 16 (16) | yes | PASS | PASS |
| 5v3 | 2 | 252/350 | 72% | 2 | 252/350 | 72% | +0 | +0 pp | 4 (4-5) | 22 (22-25) | yes | PASS | PASS |
| 6v3 | 2 | 336/420 | 80% | 2 | 336/420 | 80% | +0 | +0 pp | 6 (5-6) | 21 (21-23) | yes | PASS | PASS |

## Diagnostic traces

Timing and trajectory diagnostics are reported for inspection; they are not calibration targets.

| Ratio | First move | First damage | Final kill | Distance traveled | Blocked ticks | Death-canceled attacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1v1 | tick 1 (0.016667s) | tick 69 (1.15s) | tick 549 (9.15s) | 2.428428 tiles | 2 | 1 |
| 2v1 | tick 1 (0.016667s) | tick 69 (1.15s) | tick 309 (5.15s) | 5.300149 tiles | 165 | 1 |
| 2v3 | tick 1 (0.016667s) | tick 52 (0.866667s) | tick 491 (8.183333s) | 11.362857 tiles | 333 | 0 |
| 5v3 | tick 1 (0.016667s) | tick 52 (0.866667s) | tick 473 (7.883333s) | 22.535491 tiles | 1103 | 1 |
| 6v3 | tick 1 (0.016667s) | tick 52 (0.866667s) | tick 447 (7.45s) | 30.043307 tiles | 1306 | 0 |

## Tape-repeat diagnostics and playback

Each ratio retains all three authorized repeat tags plus spawn, first-movement, contact, first-damage, interval, hit-count, kill, and winner-HP deltas in the JSON report.

The report stays lean and does not duplicate full traces. The browser viewer must call `createChampionPlaybackData` from `aoe2x/js_simulation/src/champion-comparison.js`; that verified serializer boundary accepts only a supported, deep-immutable run whose target lifecycle, authorized source metadata, terminal state, and canonical state/event hashes validate.

## Determinism hashes

- 1v1: final `d207783befedf1f54d80ee74af854dcb92255e959556173505e1f82307095afe`; events `b2af1db03f2991849fef5413f79f1d5aa23a1db86a507df2219342fc34411fa8`
- 2v1: final `c3cb6125e41c35c1d1528ef315a22ea70dacba51a8785f5eb1345c8c337979b2`; events `1848cec0ae09d0884bf768180507a7a33931b49e73073e369db70fe761bedc2a`
- 2v3: final `2d60c6215279ad6bc2056f2a51af64605a726d7829cf16425cd018d93a10459a`; events `1a13e87a2e0578451d789ed6a3c76617458a9d645663f18a5e7392d5cb9f57f8`
- 5v3: final `b8cb121f56543a9ecab87c0043dbec710022f324e805442b7b87cfae17bcfcec`; events `1ab75b8ef40978ccbcbc2e5a51bbb765bf7519e669309bb515042c28fb7cab2c`
- 6v3: final `aec628da3b56154fa83ffbf8f038274c01977c0fa715931e775e3635ac8a6752`; events `8edc23d209e98884dd4c925db6214c5332960bd1246b12ca44d33b4ccbba72c4`

## Mechanics audit

Champion 567 (Chinese): 70 HP, 1.06 tiles/s, 0.2-tile collision radius, 0-tile range, 2s reload, 0s attack delay, 14 damage versus self.

- Genie data SHA-256: `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- Reference DB SHA-256: `51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087`
- Heuristic static lint found no unapproved shortcut-pattern matches in 13 audited executable files; 10 expected scenario/map/source-mechanics matches are retained with reasons in JSON.
- Assurance limit: Pattern-based lint plus separate review; this is not a proof of absence or bypass resistance.
- Separate review evidence: `.superpowers/sdd/2026-08-04-cleanroom-champion-small-groups/task-10-report.md`
- Exact lint exclusion: `src/champion-comparison.js` - reporting and static-lint implementation is self-referential and does not advance simulation physics.

The complete JSON companion contains per-unit distance and blocked-tick totals, the target timeline, death-canceled attack records, all repeat/reversal hashes, and field-level mechanics provenance.
