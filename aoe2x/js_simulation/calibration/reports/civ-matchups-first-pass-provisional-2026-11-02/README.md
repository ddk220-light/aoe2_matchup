# PROVISIONAL civilization-matchup first pass

Complete first-pass coverage: **555 variants, 1,540 civilization pairs, 151,223 displayed cells and 68,916 distinct profile pairs**, with **zero unresolved rows**. The source snapshot is reviewed phase 048. This is a provisional dataset containing explicitly unvalidated predictions.

| Evidence type | Profile pairs |
| --- | ---: |
| Observed source pairs | 11,778 |
| Inferred by the recorded source rules | 11,197 |
| Equivalent combat profiles (`identity`) | 45 |
| Explicitly unvalidated predictions | 45,896 |
| Unresolved | 0 |

All 45,896 predictions retain `predicted_unvalidated`, `verified: false` and `needsValidation: true`. This includes 19 cross-engine recovery projections. These predictions require a later validation discussion and pass; no exhaustive second pass was started. Original forecasts, physical contexts, source/rule hashes, weak-support and contested flags, observed failures and later validation statuses are preserved wherever an original forecast exists. A recovery projection created for a gap without an original forecast does not invent one.

## Data files

- [civilization-table.jsonl.gz](civilization-table.jsonl.gz): one JSON object per displayed cross-civilization cell, 151,223 rows.
- [profile-table.jsonl.gz](profile-table.jsonl.gz): 68,916 distinct profile pairs with evidence types, contexts, outcomes and provenance.
- [variant-profiles.json](variant-profiles.json): the 555 approved civilization/unit variants and their combat-profile mapping.
- [summary.json](summary.json): coverage, evidence counts, prediction tiers and remaining validation work.
- [manifest.json](manifest.json): delivery-builder version, original source/review hashes and data-file checksums.
- [publication-manifest.json](publication-manifest.json): checksums for the complete published bundle, including this documentation and integrity reports.
- [bundle-check.json](bundle-check.json): independent full-grid, orientation, original-row/context/flag and ledger checks.
- [coverage-and-integrity.json](coverage-and-integrity.json): all 48 phase reviews, required-seed accounting, source checks and exact-replay references.
- [source-publication.json](source-publication.json): pinned GitHub source commits and hashes, including every inference input, all 62 frozen runtime files and the frozen prediction policy.

The gzip tables contain UTF-8 JSON Lines. In profile rows, `a_win` and `b_win` refer to the row's `profiles` order. Displayed-cell outcomes refer to that cell's civilization/unit order. The stored physical `context` and `sourceContext` preserve army counts and owner orientation; an outcome must not be transferred into a reversed physical scenario.

## Separate recovery evidence

The 19 recovery-supported rows remain `predicted_unvalidated`, tier `repaired_engine_projection`, for the frozen V3 table. Their 57 native seed records stay in five separate ledgers:

| Ledger | Native seed records | Projected profile pairs |
| --- | ---: | ---: |
| [repaired-evidence-ledger.jsonl.gz](repaired-evidence-ledger.jsonl.gz) | 27 | 9 |
| [patrol-candidate-evidence-ledger.jsonl.gz](patrol-candidate-evidence-ledger.jsonl.gz) | 6 | 2 |
| [static-memo-candidate-evidence-ledger.jsonl.gz](static-memo-candidate-evidence-ledger.jsonl.gz) | 0 | 0 |
| [event-stream-candidate-evidence-ledger.jsonl.gz](event-stream-candidate-evidence-ledger.jsonl.gz) | 21 | 7 |
| [terminal-goal-candidate-evidence-ledger.jsonl.gz](terminal-goal-candidate-evidence-ledger.jsonl.gz) | 3 | 1 |

Every included recovery pair has a complete required native seed set and passed exact replay review. Partial or unreviewed sets, diagnostics, timeouts and old-engine ranking measurements are excluded. Campaign hashes, original source references, source/target physics, physical contexts and replay hashes remain intact. Patrol and forest-pocket game-fidelity limitations remain explicit. Native replay parity does not validate a cross-engine projection under V3.

All 31 historical missing V3 seeds remain missing in their original journals, with failures preserved. Their 19 pairs are fully accounted for in this first pass through the separate reviewed projections; they are not relabeled as V3 measurements. Bulk engine replay remains outside this delivery.

## Validation status

All 48 phase reviews passed their required-seed accounting and exact replay checks, allowing only the explicitly recorded historical blockers. The independent inference validator checked source hashes, rule-root evidence and the full matrix. The final exporter ran with `--require-complete`; independent bundle checks verified exact matrix membership, cell orientation, unchanged approved forecast rows/flags/contexts, no unresolved rows and unique native records. Ten delivery regression tests and four audit-provenance regression tests passed.

Frozen-policy screening recorded 880 checks with 133 wrong-winner or close-called-decisive cases. Subsequent prospective checks recorded 682 checks with 106 such cases. These are separate audit populations, not a combined accuracy estimate. Their failures remain archived; 3,489 surviving forecasts carry contested flags. Predictions are included under the approved first-pass scope and are not called validated.

The final selection audit needed a provenance-only repair when phase 048 contributed no eligible common-opponent cases: its reviewed source phase is 048, while its latest eligible observation phase remains 047. The freshness/review gates remain enforced. Candidate rules, cases, source hashes, forecast pool and physics were verified unchanged. The failed audit and regression evidence are retained in the [campaign delivery review](../civ-first-pass-event-stream-delivery-2026-11-02/README.md).

## Pinned source publication

Main source campaign and code: [80288894](https://github.com/ddk220-light/aoe2_matchup/tree/8028889425c6e5651404c474cb0d4d3ad9310356). Original absolute recovery references resolve against the matching pinned source tree below; their bytes and record hashes are preserved in the ledgers.

| Source worktree | Pushed source commit |
| --- | --- |
| `aoe2_civ_first_pass_parallel` | [19b97586](https://github.com/ddk220-light/aoe2_matchup/tree/19b975868ba2200bd8eea1318c42f9997bdcd6af) |
| `aoe2_civ_stream_hash` | [17172058](https://github.com/ddk220-light/aoe2_matchup/tree/17172058454961c5ce796ce7df7b20d09b2c5f0a) |
| `aoe2_civ_patrol_repair` | [4d735614](https://github.com/ddk220-light/aoe2_matchup/tree/4d73561486b10d4dc459bff9585f042a210f2e68) |
| `aoe2_civ_path_cache` | [c94477e3](https://github.com/ddk220-light/aoe2_matchup/tree/c94477e3c652c158cd73bbf1194b9d99013d19c9) |
| `aoe2_civ_event_stream` | [6cc3f8f2](https://github.com/ddk220-light/aoe2_matchup/tree/6cc3f8f2d9084ef31d09a114830a3e83a4359e0d) |
| `aoe2_civ_subcell_route` | [4bfe02ed](https://github.com/ddk220-light/aoe2_matchup/tree/4bfe02edf847a4a47b4cc0cb8ad47beb536434d1) |
| `aoe2_civ_phase038_stream` | [6109d06a](https://github.com/ddk220-light/aoe2_matchup/tree/6109d06a2e444e108a1b38bb36d4c87d3a4c70f6) |
| `aoe2_civ_phase039_stream` | [662ce5b1](https://github.com/ddk220-light/aoe2_matchup/tree/662ce5b1ef367c6923224ddcb9bad282e73416c9) |
| `aoe2_civ_phase040_early_stream` | [ffee4401](https://github.com/ddk220-light/aoe2_matchup/tree/ffee4401bb0e36fd5d8a1539492bda2470ab44c6) |
| `aoe2_civ_phase040_stream` | [1cea1cca](https://github.com/ddk220-light/aoe2_matchup/tree/1cea1cca6adade3bfd8c2297a4ebaaf6665fc8bf) |
