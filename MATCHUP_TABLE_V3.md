# Matchup Table v3 — start here

This branch is a portable research and website-source handoff, not a new release.
The website source and serving database are preserved from the current website
checkout. Newer independently verified correction data remain separate. No new
corrections have been applied to the serving database, and no website rebuild or
deployment is authorized by this handoff.

Read [the captured status](handoff/matchup-table-v3/status.json),
[the campaign/source catalog](handoff/matchup-table-v3/campaign-sources.json), and
[the operating instructions](docs/civ-matchup-mismatch-validation-operations.md).
The JSON status records the exact cutoff, counts, commits and hashes. Work on the
original machine continues after this snapshot; this branch is not a live queue.

The captured November 5 checkpoint has **2,997 reviewed contexts, 484 changed
winner-or-close classifications, 7,230 unfinished contexts (including two known
blockers), and 9,626 saved journal records**. Journal records are individual seeds,
not additional completed matchups. These counts describe the snapshot, not live
progress after its cutoff.

## Goal and current work

The provisional advisor covers 555 variants, 1,540 civilization pairs, 151,223
displayed cells and 68,916 profile pairs. It retains observed, inferred, equivalent
and explicitly unvalidated predicted evidence internally. Public presentation
continues to treat these alike, as requested by the owner; provenance is retained.

We compared the legacy and current tables, froze every selected disagreement, and
are validating that entire list: **18,298 displayed cells / 10,227 distinct
physical battle contexts**. The immutable campaign identifier is
`89c515d0a0341957f5cb86f4ab0f87537f824646fb808ebe0e1b666ccaf0cc7a`.

Each eligible correction needs all prescribed seeds under its original physical
context, followed by an independent exact replay. Existing measured V3 sets are
checked by exact replay and source integrity; other contexts need fresh seeds
0–2 and, when those winners disagree, seeds 3–9 too. A replay must match winner,
ticks, final-state hash and complete event-log hash. A mixed completed seed set
can be legitimately close; a timeout, missing seed or diagnostic cannot.

The current website database includes an older published 2,305-context correction
checkpoint. More recent correction snapshots are research data awaiting analysis.
The latest snapshot path and its reviewed/changed/remaining counts are in
`handoff/matchup-table-v3/status.json`; newer raw journal records may exist beyond
that independently exported snapshot. Partial seed sets remain partial.

## What is included

| Location | Purpose |
| --- | --- |
| `apps/web`, `apps/backend`, `apps/website`, `data/golden` | Current website source and existing serving artifacts |
| `aoe2x/js_simulation/calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05` | Frozen full mismatch list, original evidence, scenarios/profiles, journals, attempts, progress, pair/phase reviews and diagnoses |
| That campaign's `correction-snapshots/` | Immutable independently verified cumulative correction exports |
| `aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31` | Original adaptive first-pass plans, journals and prediction policy history |
| Other campaigns in `campaign-sources.json` | Native repair/replay records with separate physics and provenance; partial and blocked records retained |
| `handoff/matchup-table-v3/files.sha256.json` | File-level integrity inventory for the included research data/runtime and handoff tools |
| `aoe2x/js_simulation/calibration/live_observations/video_archive_indexes/` | Destination for recorded-game result indexes from the recording computer |

The root JavaScript simulation tree is the frozen validation source, not an
attempt to merge multiple physics revisions. Current website files outside that
research tree retain the website source version. Native records from other
physics stay in their original campaign directories; their source branches and
commits are listed rather than silently swapping the active engine. The original
validation history is a merge parent of this branch.

Archive runner/supervisor logs are included under `handoff/matchup-table-v3/logs/`.
Active locks, credentials, dependencies, local environments and build caches are
not transferred. Snapshot state/PIDs describe the source machine, not this one.

## Verify a checkout without running simulations or rebuilding

```bash
git clone --branch matchup-table-v3 https://github.com/ddk220-light/aoe2_matchup.git
cd aoe2_matchup
python tools/verify_matchup_table_v3_handoff.py
```

Use Python 3.10+ (`python3` if required). This only reads files. To independently
re-export captured corrections, use the exact Node version from the campaign
manifest (currently `v24.19.0`) and a clean simulation environment with no
`AOE2X_EXP_*` overrides:

```bash
node aoe2x/js_simulation/node/civ-matchups/export-mismatch-reviews.mjs \
  --reviewed-only --output /tmp/matchup-v3-review-check
```

Choose a new output directory; exports refuse overwriting. This verifies saved
records and replays without starting fights or importing website data. Do not run
website generators, release CI, staging or production commands at this stage.
The branch disables its own Vercel Git deployments; GitHub website CI triggers
remain limited to `main` and `staging`.

## Remaining work and blockers

1. Finish the remaining ordinary contexts on the existing four-worker runner.
2. Keep every new correction independently reviewed/exported with exact context
   and original values; do not classify partial or blocked cases.
3. Discuss the two diagnosed unfinished contexts below. No blind retries or
   physics changes are authorized.
4. Add the real-game recording indexes, map their conditions to table contexts,
   and analyze compatible results separately from engine simulations.
5. Prepare the final cumulative analysis: coverage, unchanged/changed winners,
   close calls, original evidence types/rules, failures and limitations. This
   selected disagreement inventory is not an unbiased global accuracy sample.
6. Stop for owner analysis and explicit approval before one consolidated
   build/test/staging/production release. If only diagnosed blocked cases remain,
   present available data and concrete blockers; do not claim full completion.

Known blocked contexts at this handoff:

| Context | Missing seed | Diagnosis |
| --- | --- | --- |
| `mv_5e1e0d268234acff1d6e9008` — Armenian Champion / Tupi Slinger, 27/27 | 1 | Repeated static patrol-endpoint stall; deliberately canceled after diagnosis; no result |
| `mv_306dd795e5f68374d24e2a99` — Aztec Elite Skirmisher / Hunnic Elite Tarkan, 27/18 | 1 | All prescribed attempts exhausted; prolonged pursuit with no further damage; no result |

Full evidence is under the validation campaign's `diagnostics/<context>/REVIEW.json`.

## Worker ownership and resuming elsewhere

**Do not start another runner merely because this branch is cloned.** The original
Linux machine still owns the supervisor/runner and four workers. Check current
PIDs, locks, state, journals and logs there. A stale timestamp or empty queue does
not prove interruption. This handoff does not transfer worker ownership.

If an actual machine transfer is agreed later, first stop/drain the original
owner safely and push its final checkpoint. Resume the authoritative
`simulations/civ-matchups-mismatch-validation-2026-11-05` branch through
`tools/supervise_civ_mismatch_validation.py`, after verifying the locks and source
hashes. The runner intentionally rejects the handoff branch name when attempting
its automatic checkpoint: do not remove that guard. The supervisor is Linux-only
(`fcntl` and `/proc`) and currently writes logs under `/workspace`; a Windows
computer can upload/analyze indexes without running that supervisor.

Do not restart the old bulk collision replay, completed anchors, serial recovery,
original parallel recovery, static-memo, event-memory, patrol, terminal-goal or
phase-specific recovery runners. Their archived statuses and physics differ.
Do not change forecasts, ranking scores, recommendation formulas or physics.

## Add the real in-game video results from another computer

The real AoE2:DE recording workflow is on
[`codex/video-recorder-v3`](https://github.com/ddk220-light/aoe2_matchup/tree/d6a8ca1697c983ec8a045221698e01a76df34d5d),
pinned at `d6a8ca1697c983ec8a045221698e01a76df34d5d` (September 24, 2026).
The source tools/docs are available there; the full recording indexes were not
present in this cloud workspace. Do not mistake older `sim_v2/results` output or
YouTube description prose for the original recorded-game outcome ledger.

Documented sources include 9 camel variants × 70 comparable opponents (630),
17 knight-line variants × 70 (1,190), and 4 Champi civilizations × 74 (296), plus
other unit sweeps. These overlap other records and are not an additive coverage
claim for this table. See
[recorded rankings](https://github.com/ddk220-light/aoe2_matchup/blob/d6a8ca1697c983ec8a045221698e01a76df34d5d/docs/video-production/RECORDED_RANKING.md),
[knight archives](https://github.com/ddk220-light/aoe2_matchup/blob/d6a8ca1697c983ec8a045221698e01a76df34d5d/docs/video-production/KNIGHT_CANONICAL_ARCHIVE.md),
and [balance policies](https://github.com/ddk220-light/aoe2_matchup/blob/d6a8ca1697c983ec8a045221698e01a76df34d5d/docs/video-production/BALANCE_POLICY.md).

1. Locate `D:/AoE2 Renders` / `E:/AoE2 Renders` on the recording PC. The canonical
   knight collection is `E:/AoE2 Renders/knight-line-canonical/<variant>/run.json`;
   camels use `camel-comparison-<civ>/run.json`, and geometric Champi archives use
   `champi-geometric-<civ>/run.json`. Drive letters may differ.
2. Copy each original small `run.json` into a distinct archive-named folder under
   `aoe2x/js_simulation/calibration/live_observations/video_archive_indexes/`.
   Include existing `chapter-results.json`, `catalog.json`, correction/source
   history and missing-recording indexes when available. Preserve original bytes
   and per-variant results, not just the video's best-unit summary. Do not
   overwrite an earlier intake; use another dated folder for a newer archive.
3. Add a short `source-notes.json` with the original archive path, copied time,
   recording-code commit if known, game build, and any unavailable media or
   missing capture fields. Unknown values stay unknown. Keep video/frame files
   on their archives initially; indexes carry their original references/hashes.
   Never add OAuth state, credentials or unrelated private files.
4. Commit and push only those new intake paths to `matchup-table-v3`. First pull
   the remote branch normally; do not force-push over another computer's uploads.
5. Compare exact civ/unit/upgrade, owner orientation, counts, costs, game patch,
   map/scenario, relics/effects, AI/kiting, and support troops before proposing
   corrections. Some video scenarios add Hussars and use other count policies.
   Keep historical under-10%-HP editorial draws separate from the raw game winner.

Example on the recording computer in PowerShell, after cloning this branch:

```powershell
git switch matchup-table-v3
git pull --ff-only origin matchup-table-v3
$CaptureIntake = 'aoe2x/js_simulation/calibration/live_observations/video_archive_indexes/2026-11-05-paladin-spanish'
New-Item -ItemType Directory -Force -Path $CaptureIntake
Copy-Item -LiteralPath 'E:/AoE2 Renders/knight-line-canonical/paladin-spanish/run.json' -Destination "$CaptureIntake/run.json"
# Add source-notes.json as described above before committing.
git add -f -- $CaptureIntake
git commit -m 'Add original Spanish Paladin recorded-game index for analysis [skip ci]'
git push origin HEAD:matchup-table-v3
```

Use a separate intake folder for each archive; the Spanish path is an example,
not an instruction to substitute Spanish captures for another civilization.

An original index may support analysis even where video is unavailable; say which
records are metadata-only. New project-local `frames.bin` can be used directly
for live calibration, with its exact path/run recorded. No archive packaging or
special source authorization is required to inspect it. A real-game observation
is its own evidence source: never insert it into the frozen V3 seed journal or
claim it is an exact V3 replay. Analysis and any table change still require review.

## Immutable website baseline and eventual release

The current serving DB is already corrected through an earlier checkpoint; do
not use it as the original baseline. The immutable baseline is the Git blob
`a3ce3c996c03a6708f1082a06a85e7c26af98a75:data/golden/civ_matchups_first_pass.db`,
SHA-256 `93e5732f5e1afd08a9be5b292506edb2f4ee41c2be4352a8bc4128184a05ebb8`.
That commit is retained in this branch's website history. Extract binary bytes
with `git show` through Python `subprocess.check_output(...)/Path.write_bytes(...)`
on Windows rather than text-mode PowerShell redirection.

The importer is `scripts/apply_advisor_matchup_corrections.py`. Its eventual
approved release commands and gates are in the operations document. Do not run
them during this handoff or routine data-collection checks. Main, staging,
production data, public UI and recommendation weights remain unchanged.
