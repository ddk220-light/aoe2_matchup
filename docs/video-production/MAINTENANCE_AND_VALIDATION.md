# Maintenance, verification, and source boundaries

[Return to the complete runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

## Before editing a working production machine

Inspect Git status, branch, current workers, queue state, and artifact versions. Keep the original manifests/plans as evidence. A source change can invalidate comparison fingerprints or change a later render; do not edit files under an active encoder and assume its output reflects one coherent version.

The requested media policy is one subject's overlays → intro/full → Shorts → QA → upload/archive before another subject's media. Game capture is an independent serial lane and may run in parallel. V3 simulation can run as a bounded diagnostic lane. Retakes blocking publication outrank new ordinary captures. Avoid changing the game/recorder while it captures; finish or safely pause first when a change requires it.

The historical queue includes completed/paused episodes, old cost-audit holds, and local paths. On a fresh clone, audit it before any broad queue runner starts. Use a new single-subject adapter for a new authorized episode, not a global “continue everything” command. No scheduled task is silently created/reactivated by the runbook.

## Implementation map and contracts

| Component | Inputs → outputs | Important invariants |
| --- | --- | --- |
| `scaffold_video_episode.py` | Exact registered slug/key → ordered manifests, adapters, draft intro, preflight, planned queue row | Dry run by default; no overwrites; all plan costs pass before writing; derived roster count; no game/API action |
| `aoe2x/lab/planner.py` + Node `aoe2lab_worker.mjs` | Request → canonical plan | Exact identity, costs, weights/counts, Golden family/hash and plan hash |
| `scripts/audit_recording_costs.py` | Isolated installed-DAT extraction + registry → effective-cost catalog and archive audit | Civ/tech cost effects, per-resource rounding, true production batch divisor, unresolved list |
| `aoe2x/lab/costs.py` | Plan + current catalog → validation | No stale/base-price fallback; correct army resources/counts |
| `aoe2x/lab/live.py` | Canonical plan + Golden → scenario and capture | NoneAI, camera, civs, diplomacy, screen and Golden provenance checked |
| `apps/video/build_run.py` | Planned scenario slots/unit identity → generated scenario | First N authored slots, correct form/master/upgrades |
| `auto/orchestrate_matchup.py` | Current editor state → test/run/return navigation | One desktop driver; responsive observed transitions; bounded recovery |
| `auto/record_until_end.py` | Video/gRPC streams → raw capture stop | Elimination/conversion/mutual-death handling and timeout evidence |
| `aoe2x/grpc/grpc_hp_log.py` | Authenticated local frame stream → frames/meta/HP | Real timestamped game state and persistent entity membership |
| `aoe2x/grpc/redecode_hp.py` | Preserved frames → decoded timeline | Ownership transfer, dead IDs, main armies independent of screen/projectile effects |
| `aoe2x/lab/battle_clip.py` | Raw video + start evidence → battle clip/adjusted sidecar | Video and audio trim together; preserve original capture |
| `aoe2x/lab/recording.py` | Run files + canonical plan → recording bundle/validation | Relative indexed paths, hashes, media, clock metadata |
| `recording_campaign.py` | Ordered manifest → verified results/checkpoints | One game mutex, one offline finalizer, reports, three-failure stop |
| `run_<subject>_capture.py` | Queue/report history → pending capture pass + merged results | Preserve verified rows, distinguish active subset from merged total |
| `render_campaign_overlays.py` | Canonical manifest + verified capture report → per-job overlays | Only verified source jobs; one subject; bounded 1–8 workers |
| `overlay/static_stats.py` | Reference/supplemental stats + installed assets → panels | Correct unit/civ, margins, bonus annotation independent of armor |
| `overlay/civ_theme.py` | Civilization → border/emblem assets | Emblem centered on portrait corner; consistent civ theme |
| `overlay/unit_timeline.py` | Frames + recording mapping → entity HP rows | Stable identities and conversion ownership |
| `overlay/auto_alignment.py` | Visible HP bars + timeline → accepted alignment | Observation/error/ambiguity thresholds; hash-bound anchors |
| `overlay/unit_hp.py` | Panels + aligned timeline + battle clip → landscape overlay | Individual live HP/counts, stable audio/duration/geometry |
| `overlay/battle_end.py` | Ownership/HP timeline → terminal battle row | Conversions and special terminal states instead of a long arbitrary tail |
| `build_campaign_catalog.py` | Installed campaigns/scenarios + overrides → civilization art catalog | Evidence separate from artistic choice; explicit fallback |
| `extract_intro_reference.py` | Actual narration event + Wwise packages → WAV/WEM/mapping | Direct verified event chain; reject unsupported structures |
| `create_intro_voice_clone.py` | Authorized sample → cloud voice + provenance | Key from environment; matching sample cache; retired profile rejected |
| `generate_intro_narration.py` | Reviewed text + voice → audio/timestamps/cloned plan | Exact text/timing correspondence; cache identity and reading holds |
| `build_campaign_intro.py` | Cloned plan + game assets → pages, letter animation, mixed intro | Safe text region; stable wrapping; visible character timing |
| `build_campaign_thumbnail.py` | Same plan/art → landscape/vertical JPEG covers | Quiet parchment style; correct unit/title; bounded size |
| `build_<subject>_final.py` | All canonical overlays + intro → full video, chapters, results, description | Whole-file decode, count/duration checks, correct terminal winner/HP |
| `prepare_<subject>_final_shorts.py` | Recorded outcomes + audited costs → inventory/selection | Ten unique cases, cost extremes, mandatory eligible specials, transparent fallback |
| `render_selected_shorts.py` + `build_vertical_short.py` | Selection + raw/timeline/panels → Shorts and validation | Battle stays visible; live queues left/right; game audio retained |
| `production_qa_sheet.py` | Actual final/Short files → representative contact sheets | Evidence generation only, never automatic approval |
| `finish_pending_production.py` | Explicit episode tuple + completed/reviewed media → upload package/receipt | Historic defaults must be overridden; one media lock; review gate |
| `authorize_youtube.py` | Desktop OAuth client + user consent → encrypted local token | PKCE/state, correct channel, no upload |
| `upload_youtube.py` | Authorized preparation/settings + stable state key → remote video/cover | Live channel verification, encrypted resumable session, save ID before thumbnail |
| `check_youtube_upload.py` | Existing ID → refreshed processing receipt | Read-only remote check, preserve Studio changes |
| `thermal_guard.py` | Fresh sensors + identified process tree → readings/pause ledger | Missing is unavailable, exact process identity, no automatic resume |
| `postprocess_campaign.py` | Same saved plans and verified captures → five-seed comparisons | Source/plan hashes, bounded workers, no raw-result substitution |

The entry-point runbook links these files. Existing per-subject adapters are examples, not equally current generic entrypoints. Earlier `produce_*`, cost-repair builders, broad capture queues, and stand-alone upload batches have historical defaults and authorization assumptions; read them before invoking.

## Verification commands

Run from repository root using the video venv and `PYTHONPATH=apps/video;.`. These checks do not launch a live battle, upload a video, or request paid narration.

```powershell
$env:PYTHONPATH = 'apps/video;.'
$env:PYTHONIOENCODING = 'utf-8'
& $Py -m pytest --noconftest -q -p no:cacheprovider `
    apps/video/tests/test_video_handoff.py `
    aoe2x/lab/tests/test_recording_campaign.py `
    aoe2x/lab/tests/test_parallel_postprocess.py `
    aoe2x/lab/tests/test_mutual_elimination.py `
    aoe2x/grpc/tests/test_dynamic_army.py `
    apps/video/tests/test_recorded_battle_end.py `
    apps/video/tests/test_alignment_anchors.py `
    apps/video/tests/test_alignment_bar_recovery.py `
    apps/video/tests/test_continuous_capture.py `
    apps/video/tests/test_deferred_retakes.py `
    tests/test_recording_cost_effects.py `
    aoe2x/lab/tests/test_recorder_navigation.py `
    aoe2x/lab/tests/test_recorder.py `
    aoe2x/lab/tests/test_battle_clip.py `
    aoe2x/lab/tests/test_workflow.py `
    apps/video/tests/test_navigation_save_transition.py `
    apps/video/tests/test_combat_snapshot.py

node --test `
    aoe2x/js_simulation/tests/recording-costs.test.mjs `
    aoe2x/js_simulation/tests/aoe2lab-worker.test.mjs `
    aoe2x/js_simulation/tests/recorder-roster-mechanics.test.mjs `
    aoe2x/js_simulation/tests/unique-special-effects.test.mjs `
    aoe2x/js_simulation/tests/recorded-special-blasts.test.mjs `
    aoe2x/js_simulation/tests/naval-recorder.test.mjs `
    aoe2x/js_simulation/tests/melee-bystander-recovery.test.mjs

& $Py -m unittest apps/video/test_thermal_guard.py
& $Py scripts/check_video_docs.py --output data/local/handoff-doc-links.json
node aoe2x/js_simulation/tools/preflight_recorder_roster.mjs data/local/handoff-roster-preflight.json
& $Py apps/video/scaffold_video_episode.py --key handoff-example-kamayuk --slug elite_kamayuk_incas
```

The scaffold's default is a read-only source preview. It does not prove full capture success for that subject. To validate its `--write` preparation, use an isolated clone/worktree/test directory or a deliberately new approved episode, then inspect the created plans; do not overwrite the current Obuch package merely to test the scaffold.

`--noconftest` is intentional for these isolated recorder/mechanics tests: the top-level website `tests/conftest.py` imports Flask, which is not a video-only runtime dependency. These focused tests do not use its fixtures. The first handoff test attempt encountered missing Flask via that unrelated conftest; the targeted suite then passed with it excluded. This is not a claim that the full website test suite passed.

For code changes, also compile the changed Python modules, run applicable CLI `--help` entrypoints, inspect generated adapter code, and validate all new documentation links. For a cost/mechanic change, test the relevant rules against source-backed values and an actual pilot where needed. Avoid tests that merely repeat a constant without checking the behavior that previously failed.

### Handoff verification snapshot

The handoff verified 73 focused Python tests, 3 thermal tests, and 42 Node tests, including scaffold identity/count/write checks, JSON/TOML manifest compatibility, retired voice rejection, discount/count gates, capture finalization/resume, scenario/camera validation, conversion, terminal battle behavior, alignment anchors, and specialized engine mechanics. Final evidence and the two resolved test-environment/fixture issues are recorded in [handoff audit](HANDOFF_AUDIT.md).

No new unit's capture, paid narration, or YouTube upload is performed merely to document or test this handoff. Existing completed production is evidence that the underlying pipeline has run; the new helper still requires the pilot and QA gates on a genuinely new unit.

## Known limits

1. **Private prerequisites:** the game, DAT, audio assets, CadeRemote credentials, OAuth client/consent, active voice and external storage are not supplied by Git. The setup reference explicitly lists what must be obtained.
2. **Portability:** core Lab storage is configurable, but most offline per-episode media helpers still use the default logical Lab path and current NVIDIA encoder. Use checked junctions or a reviewed code adaptation; don't claim arbitrary paths/GPUs work unchanged.
3. **Scaffold scope:** normal registered land subjects only. It emits editable adapters and an unfinished intro draft. It cannot infer a new unit's history, special scenario, narrator rights, new engine implementation or approvals. Special subject checks must be adapted deliberately.
4. **Goldens:** preserve the known map/triggers/NoneAI/P4 conventions. A future patch/UI change can break navigation or upgraded starting stats despite unchanged source files. Revalidate a pilot after such changes.
5. **Observation versus calibration:** a saved fixture or short smoke sim is not a calibrated movement/targeting model. Missionary conversion and naval simulation are unsupported; explicit no-buffer experiments require matching simulation support. Shotel discrepancies were left unresolved by user instruction. Do not silently “fix” windup to get a desired winner.
6. **Comparison clock/end convention:** the current five-seed comparison computes final HP from the final decoded row; full/Short builders use a conversion-aware terminal battle row. Post-battle regeneration can therefore differ between diagnostic HP and the visible chapter's endpoint. Preserve the distinction; align conventions and invalidate provenance before claiming exact equality.
7. **Caches:** several intro/full/overlay stages reuse files or complete status without exhaustive current asset hashing. Follow the manual invalidation/review procedure when inputs change.
8. **QA gate:** the supervisor checks `visual-qa.json.passed`, not proof that anyone watched the video. Save truthful review scope and hashes; invalidate on changes. Representative contact sheets cannot establish every frame's quality.
9. **Resume totals:** the active pending pass and parent merged campaign are different scopes. The wrapper can need recovery merging after a hard stop; never add already included subsets twice.
10. **Thermals:** CPU sensing is currently unavailable under the user's explicit continuation policy. GPU monitoring works; it is inaccurate to claim both are monitored. The thermal resume guard requires fresh readings; don't bypass an actual thermal latch casually.
11. **Queue concurrency:** queue JSON is a local ledger with multiple historical writers, not a transactional database. Avoid concurrent edits/supervisors, preserve fields, and verify the latest receipts.
12. **Upload finish:** API processing completion does not prove public visibility, copyright-check completion, all-resolution availability, or cover display on every Shorts surface. Inspect Studio and preserve owner changes.
13. **Recreating historical packages:** generated cloned plans can point at local/external narration paths and retired cloud voices. Restore saved audio and paths; do not assume a fresh clone can recreate an identical voice performance.
14. **Old global entrypoints:** historical scripts have fixed episode lists, storage locations and artifact versions. New work uses the single-subject scaffold/manual stages. Do not run every old helper as a “validation” step.

These are practical boundaries to document and check, not reasons to abandon already authorized work. Fix a blocking stage while continuing independent valid work, preserve evidence, and give the operator a precise reason when something cannot progress.

## Source control and archive boundaries

Commit the working workflow's code, tests, audited cost/roster data, intended small fixtures, Golden templates, generated unit illustrations/covers, base/cloned plan provenance, and documentation. The repository already uses generated art as a backup by owner choice.

Keep these ignored/local:

- `data/local/` (tokens, status, local audits, reports, queues' runtime receipts).
- `aoe2lab.toml` (machine settings).
- `.tools/` (downloaded tools, extracted samples, scratch analysis, helper runtimes).
- `aoe2x/js_simulation/calibration/lab/`, `calibration/reports/`, `calibration/live_observations/` (large recorded/simulation evidence).
- `apps/video/media/` and `apps/video/sim_v2/_work/` (older generated media/work files).
- Extracted intro WAV/WEM/OGG music; restoration source/IDs are documented.
- All `.frames.bin`, `.dpapi`, `client_secret_*.json`, and gRPC private `.key/.pem` files.

Some checked-in plan/provenance files contain historical absolute **paths** and voice **IDs**. Those are not portable assets or authentication secrets. Never include an actual API key, access/refresh token, private-key body, OAuth client secret, or resumable-session URL. Check both staged file names and staged content before pushing. Do not print a discovered secret during the check.

Suggested release review:

```powershell
git status --short
git diff --check
git diff --stat
# Stage only the intended workflow files after inspecting them.
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m 'Document and package the complete matchup video workflow'
git push origin HEAD:codex/video-recorder-v3
git rev-parse HEAD
git ls-remote origin refs/heads/codex/video-recorder-v3
```

Compare the two commit hashes. Do not force-push or overwrite someone else's concurrent remote work. A published Git commit includes source and provenance; multi-gigabyte videos/frames remain on the documented local/archive storage, not in Git. Keep the final entry-point link at a branch/commit that contains all linked files.

## Comments and future edits

Document each workflow boundary's purpose, prerequisites, outputs, failure behavior, and identity/provenance rules. Comment why a surprising condition exists: retirement is not a usable clone cache, JSON/TOML keep the same job IDs, screen removal requires a whole Golden family, population is not a purchase divisor, or a finalizer must release the game before encoding finishes. Avoid comments that merely narrate obvious Python statements.

When a new subject is complete, add a short episode record with actual receipts/links and any deviations. Update the main runbook only when the reusable procedure changes. Preserve historical approval records as dated evidence and mark superseded status claims; do not rewrite them to suggest that an old, incomplete version had already passed later checks.
