# Matchup run records: what to keep

Owner question: *"there is useful data and not-so-useful data; keep what we need to redo analysis
somewhere retrievable."* This document measures the 2026 campaign records on the research branch
(`RB` = `origin/simulations/civ-forecast-recovery-2026-11-10`, tip `3344324f`), classifies every
kind, and proposes one archive. The tool is `python -m aoe2x.matchups archive`
(`aoe2x/matchups/archive.py`; the same path rules produce the table and the archive).

## In short

- RB holds **4.37 GB**; the matchup records are 3.93 GB in 149,081 files.
- **310 MB (8 %) is essential**; 1.46 GB can be regenerated from it; 2.16 GB is disposable
  (diagnostic snapshots, status reports, superseded model outputs).
- The essential set plus the 2026 result index, as one deterministic `tar.gz`:
  **178.0 MB** (341 MB uncompressed, 292 files), sha256 `8bb50b0c…`
  (receipt: `aoe2x/matchups/baselines/campaign-2026/records-archive.json`). Most bytes are
  64-hex hashes, which do not compress well (`xz` gains only ≈ 10 %).
- With that archive, the bundle, the scenario set and the pinned engine (all in this repo), any 2026
  battle can be re-run exactly, every published cell can be traced to its seeds, and the result
  index can be rebuilt without RB.
- Recommendation: keep it as a **release asset of a separate private GitHub repository** that is not
  connected to Vercel, with its sha256 pinned in this repo (the receipt above). Do not keep records
  on branches of this repository.

## What can already be regenerated cheaply

The pinned engine reproduces archived seeds exactly (`replay-check`: 60/60 on Node 22 and 24;
`reproduce-2026`: 468/468). So any *result* can be regenerated from the seed journals' inputs
(context = bundle + scenario set + battle rules) - at simulation cost: the 2026 campaigns took
≈ 586 worker-hours. Everything that only restates the journals (reviews, snapshots, indexes,
status) is cheap to regenerate (seconds to minutes, no battles). What cannot be regenerated:
timing and run history, human/owner decisions, and the ML forecasts (their training inputs were
never committed).

## Triage by record kind (2026, measured)

Sizes are uncompressed git blob sizes. "Archived" = in the essential archive.

| Kind | Campaigns | Files | MB | Class | Archived | Unique information (beyond journals + inventory + bundle + engine) / how to regenerate |
|---|---|---:|---:|---|---|---|
| Seed journals (`runs.jsonl`, `adaptive/runs/NNN.jsonl`, `pilot/runs`) | pilot, adaptive, mismatch, forecast, recovery | 56 | 154.9 | ESSENTIAL | yes | The measurements: per seed outcome, HP, survivors, ticks, `finalStateHash`/`eventLogHash`, plus wall times and start/finish times (throughput, the cost hold). Regenerable only by re-simulating (≈ 586 worker-hours) and never the timings. |
| Ranking-era seed journals (`unit-rankings-consolidated-2026-10-29/runs.jsonl`, `additional-recorded-runs.jsonl`) | ranking | 3 | 19.5 | ESSENTIAL | yes | The 294 ranking-era seeds behind 98 published first-pass results (`import-results` reads them by `path:line`). |
| Failed attempts (`attempts.jsonl`) | all | 8 | 0.3 | ESSENTIAL | yes | Timeouts/crashes per seed and watchdog step: why a context was blocked. Regenerable only by re-running (up to 6,180 s per exhausted seed). |
| Diagnoses (`diagnostics/<job>/{README,REVIEW.json,analyze.py}`, `recovery-review/`, `diagnosis/`) | mismatch, forecast, recovery | 56 | 1.9 | ESSENTIAL | yes | Human diagnosis of exhausted contexts (stalls, collisions) with reproducible readers. |
| Final correction snapshots (forecast `070`, mismatch `review-ready-2026-11-07`, recovery `002`) | mismatch, forecast, recovery | 13 | 41.9 | ESSENTIAL | yes | The reviewed-only exports actually imported into the website DB; their hashes are pinned in `baselines/campaign-2026/result-index.json`. |
| First-pass delivery (`reports/civ-matchups-first-pass-provisional-2026-11-02/`) | first pass | 15 | 35.8 | ESSENTIAL | yes | The first published table (inferred, identity, forecast rows; `import-results` input). |
| Rule-inference table (`civ-matchups-inference-phase1-2026-10-31/`) | inference | 13 | 16.8 | ESSENTIAL | yes | Why the 10,193 inferred results hold (rules, anchors, evidence ledger). Regenerable only with RB code that was not ported (`build-civ-matchup-inference.mjs`). |
| Forecast record v2 (`civ-matchups-prediction-first-pass-v2-2026-11-01/`) | predictions | 6 | 25.5 | ESSENTIAL | yes | The original ML forecasts (and generator source) that 39,112 contexts were checked against (3,476 overturned). Not regenerable: training inputs are not on RB. Needed only to study forecast accuracy. |
| Frozen ranking definition (`unit-rankings-path-recovery-2026-10-29/manifest.json`) | ranking | 1 | 5.6 | ESSENTIAL | yes | Source of the committed 2026 mechanics bundle (`import-2026 --check`). |
| Manifests, policies, state, docs (`manifest.json`, `sampling-policy-v*.json`, `state.json`, `launch-approval.json`, READMEs, `CAMPAIGN_PLAN.md`, …) | all | 37 | 3.2 | ESSENTIAL | yes | Campaign identities (campaign hashes), policies and their amendments, final state, plans. |
| Owner declarations, approvals, releases (`user-reviews/`, `website-releases/`, cost-hold authorizations/verifications, closeout README/authorization) | mismatch, forecast, recovery | 27 | 0.2 | ESSENTIAL | yes | Owner-supplied winners (stored as declarations, not measurements), release authorizations, cost-hold record. |
| Recovery campaign tables and helpers | recovery | 53 | 4.0 | ESSENTIAL | yes | Inputs/runners of the three recovery engine variants (36 published contexts). |
| Pair reviews (`pair-reviews/<job>.json`) | mismatch, forecast | 49,334 | 148.1 | DERIVABLE | no | The per-context decision record (incl. `reviewedAt` and, for mismatch, the independent same-seed replay hashes `exactReplay`). **Every one is contained field for field in its campaign's final correction snapshot** (`reviewed-contexts.jsonl.gz` rows carry the review plus `reviewFile` and `reviewFileSha256`; checked for all 49,334: every field equal and every file's sha256 equal to the recorded `reviewFileSha256`). Re-create the files from the snapshot (seconds). |
| Inventories read by the importers (`all-forecast-contexts`, `held-contexts`, adaptive `inventory.jsonl.gz`) | adaptive, forecast | 3 | 9.5 | DERIVABLE | yes | Regenerable from bundle + config (`inventory`, seconds; adaptive reproduced row for row), but `import-results` / `check-inventory-2026` read them directly, so they are kept (small). |
| Intermediate correction snapshots (`correction-snapshots/001…069`, mismatch checkpoints, recovery `001`) | mismatch, forecast, recovery | 416 | 1,153.3 | DERIVABLE | no | Cumulative copies: each is a prefix of the final snapshot. Regenerable from journals + reviews with the RB exporters (minutes). |
| Copies of serving-DB evidence / baseline DB (`original-evidence.jsonl.gz`, `sources/production-baseline.db`) | mismatch, forecast | 8 | 82.2 | DERIVABLE | no | Copies of `data/golden/civ_matchups_first_pass.db` content at campaign start: in this repo's git history. |
| Closeout indexes, audits, pre-amendment journal copies (`closeout/*-index.jsonl.gz`, `cost-holds/…/integrity-audit.json`, `policy-transitions/*/runs-before-amendment`) | forecast | 14 | 29.3 | DERIVABLE | no | Indexes/audits recomputable from journals and snapshots (minutes); journal copies are prefixes of `runs.jsonl`. |
| Phase reviews (`reviews/NNN.json`, `adaptive/phases/`, `PHASE_*.md`, `checks/`) | adaptive, mismatch, forecast | 569 | 25.8 | DERIVABLE | no | Per-phase lists of reviewed/changed/blocked jobs and review hashes: recomputable from pair reviews (seconds). The two `PHASE_*.md` notes are tiny and could be kept by hand. |
| Inventories / job lists (`jobs.jsonl.gz`, `expected-native-records`, `mismatches`, `yardstick-comparison`) | mismatch, forecast | 6 | 10.7 | DERIVABLE | no | Regenerable from bundle + config + serving DB history (seconds). |
| Adaptive selector baselines (`civ-matchups-adaptive-rule-v1-2026-11-01/`) | adaptive | 5 | 0.5 | DERIVABLE | no | Inputs of the adaptive selector (not ported; proposal §3.4). |
| Progress diagnostics (`progress/*.jsonl`) | pilot, mismatch, forecast, recovery | 98,020 | 768.9 | DISPOSABLE | no | 30-s snapshots (positions, targets, HP) of slow attempts; never results. Re-create for any seed by re-running it with `execution.diagnostics: "always"` (cost: that seed's wall time). The exhausted contexts are summarised in their diagnoses. |
| Monitor reports (`monitor-reports/milestone-*.json`) | forecast | 38 | 288.8 | DISPOSABLE | no | Hourly status reports; each embeds the cumulative list of source references (why they grow to 15 MB). Status is recomputable from journals at any point. |
| Adaptive selector predictions/estimates/refinement (`adaptive/{predictions,estimates,refinement}/`) | adaptive | 368 | 1,085.3 | DISPOSABLE | no | Per-phase predicted tables of the adaptive selector, superseded by the first-pass delivery; nothing published depends on them. |
| Forecast record v1 (`civ-matchups-prediction-first-pass-v1-2026-11-01/`) | predictions | 4 | 13.3 | DISPOSABLE | no | Superseded by v2 before publication. Keep only if the owner wants the v1→v2 comparison. |
| Other (runner logs, `STOP`, lock files, test logs) | forecast, recovery | 8 | 0.1 | DISPOSABLE | no | Operational leftovers. |
| **Total** | | **149,081** | **3,925** | | | ESSENTIAL 309.6 MB, DERIVABLE 1,459 MB, DISPOSABLE 2,156 MB |

Per campaign (MB): forecast 2,060, adaptive 1,137, mismatch 603, recovery 8.3, inference 16.8,
predictions 38.8, first pass 35.8 (of RB's 149 MB of reports), ranking definition/runs 25.1.

Regenerate `python -m aoe2x.matchups archive --triage` (markdown) or `--triage --json`.

## The essential archive

```bash
python -m aoe2x.matchups archive --rb-2026 --with-index --out <dir>/campaign-2026-essential.tar.gz [--write-receipt]
```

Measured (this machine, 12 s): **178,047,155 bytes**, sha256
`8bb50b0c14c06d84dcbf7c6ed29a37d87a3c18f2c91fcdd5dd3a4c74bde70ba5`, 292 files, 340,999,002 bytes
uncompressed; built twice, byte-identical. Contents by kind (uncompressed MB): seed journals 154.9,
final snapshots 41.9, first pass 35.8, forecast record 25.5, result index 21.8, ranking-era journals
19.5, inference 16.8, importer inventories 9.5, frozen definition 5.6, the rest 9.6. Including the
49,334 pair-review files as well (redundant with the final snapshots) would add 148 MB uncompressed,
≈ 28 MB compressed.

Layout (one file per campaign set; one more per future run):

```
campaign-2026-essential.tar.gz
  MANIFEST.json                      first member: source (RB ref + commit), every member's
                                     path, campaign, kind, class, bytes, sha256; totals
  rb/<original RB path>              essential files at their RB paths (so RB tools and
                                     aoe2x.matchups.rbsource paths still apply)
  derived/result-index.jsonl.gz      the import-results output (sha256 d672f226…)
campaign-2026-essential.tar.gz.manifest.json   sidecar: the manifest + the archive's own sha256
aoe2x/matchups/baselines/campaign-2026/records-archive.json   (in this repo) receipt without the file list
```

Determinism: members sorted by path, mtime 0, uid/gid 0, no owner names, mode 0644, gzip mtime 0
and no file name, read straight from git blobs (`git cat-file --batch`), two passes (hash, then
write) so nothing large is held in memory.

For a new run: `python -m aoe2x.matchups archive <records> --config <config> --out <runId>-records.tar.gz`.
It keeps `manifest.json`, `config.json`, `inventory/inventory-summary.json`, `runs.jsonl`,
`attempts.jsonl`, `sessions.jsonl`, `pair-reviews/`, `reviews/`, `reuse.json`, `state.json`,
`export/` and the progress files of exhausted attempts; it drops `inventory/jobs.jsonl.gz`
(`inventory` regenerates it), other `progress/`, `logs/` and control files. Measured on the 40-context
end-to-end slice: see `aoe2x/matchups/README.md` (a patch run of ~370 contexts is a few MB).

## Where to keep it (no external resources were created)

| Option | Pros | Cons |
|---|---|---|
| **Release asset of a separate private GitHub repo** (e.g. `<owner>/aoe2_matchup-records`, one release per campaign/run) | Free, versioned, same access control as the code; 2 GiB per asset (the 2026 archive is 208 MB); fetch with `gh release download` and check the pinned sha256; the repo has no Vercel project, so no preview builds | A second repo to administer; assets are not diffable; keep the repo private (records include owner decisions) |
| Object storage (S3/R2/GCS bucket, as `scripts/migration/restore_retained.py` already does for the retained release archive) | Any size, lifecycle rules, cheap; fits automated restores | Needs credentials and a paid account; access policy is separate from GitHub; must pin hashes in the repo |
| Owner's disk (plus a second copy) | No setup, no cost | Single point of failure unless copied; not reachable from cloud sessions |
| Branch of this repo (status quo on RB) | Already there | 4.4 GB in every full clone; pushes to Vercel-connected remotes triggered ≥ 300 preview builds and the Nov 10 cost hold; GitHub 100 MiB file limit |

Recommendation: a separate private repo's release asset for the 2026 archive and each future
run's archive, sha256 pinned in this repo (receipt files under `aoe2x/matchups/baselines/`);
optionally mirror to the owner's disk. Once the archive is stored and verified (download, check
sha256, `tar -tzf` lists the manifest), RB can stop being the only copy; deleting RB is a separate
owner decision (it also holds non-matchup research: ranking campaigns, apps, tools).
