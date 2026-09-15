# AoE2 matchup video production: start here

This is the handoff entry point for a person or agent producing an entirely new unit episode. Read it in order the first time. It connects the executable workflow, its evidence, the review gates, and the recovery procedures. The companion documents below are part of the handoff; send this file's GitHub link so its relative links travel with it.

**Current procedure, updated September 15, 2026, on `codex/video-recorder-v3`.** Historical episode notes describe what happened at that time. This runbook describes how to operate the current branch. Do not use an old episode's “pending,” roster size, base costs, or upload authorization as current instructions.

## Contents

1. [Deliverables and definition of done](#1-deliverables-and-definition-of-done)
2. [Non-negotiable matchup and presentation rules](#2-non-negotiable-matchup-and-presentation-rules)
3. [Prepare the workstation](#3-prepare-the-workstation)
4. [Register and scaffold a new unit](#4-register-and-scaffold-a-new-unit)
5. [Approve costs, counts, scenarios, and a pilot](#5-approve-costs-counts-scenarios-and-a-pilot)
6. [Capture the campaign and monitor progress](#6-capture-the-campaign-and-monitor-progress)
7. [Run the optional V3 comparison lane](#7-run-the-optional-v3-comparison-lane)
8. [Build and inspect all HP overlays](#8-build-and-inspect-all-hp-overlays)
9. [Create the civilization intro and covers](#9-create-the-civilization-intro-and-covers)
10. [Compile the full video and select ten Shorts](#10-compile-the-full-video-and-select-ten-shorts)
11. [Perform visual and audio QA](#11-perform-visual-and-audio-qa)
12. [Authorize, upload, and verify YouTube processing](#12-authorize-upload-and-verify-youtube-processing)
13. [Archive, report, and hand off](#13-archive-report-and-hand-off)
14. [Documentation and implementation index](#14-documentation-and-implementation-index)

Companion references:

- [Approved army-size formula](video-production/BALANCE_POLICY.md) — geometric mean of resource cost and population, with half-strength food/wood discounts for shared units; default for new episodes.

- [Champi completion and next overlay discussion](video-production/CHAMPI_HANDOFF.md) — current handoff; all 296 standard-template captures are complete.
- [Compact media storage](video-production/COMPACT_STORAGE.md) — current retention policy.
- [Retired four-arena experiment](comp4-champi-campaign.md) — historical only; the owner abandoned this map in favor of separate standard-template captures.
- [Workstation, game data, unit registration, and cost audit](video-production/SETUP_AND_DATA.md)
- [Status, pause/resume, retakes, thermal monitoring, and storage](video-production/OPERATIONS_AND_RECOVERY.md)
- [Intro, narration, media validation, and OAuth publication](video-production/MEDIA_AND_PUBLICATION.md)
- [Maintenance, tests, source boundaries, and known limitations](video-production/MAINTENANCE_AND_VALIDATION.md)

## 1. Deliverables and definition of done

An ordinary episode consists of one featured unit versus the approved unique land-unit roster, excluding that exact unit identity. Keep the subject on **Player 2**, opponents on **Player 3**, sorted by civilization, then unit label. The roster currently has 74 entries: an included subject has 73 opponents; a subject outside that roster can have 74. Derive the count from the manifest, never from a remembered number.

The complete package is:

| Deliverable | Evidence required |
| --- | --- |
| Every requested recorded battle | Scenario and saved plan; raw screen video; original `.frames.bin`; metadata; validated `recording.json`; campaign result `verified` |
| Every chapter's overlay | Stats panels, live per-entity HP timeline, accepted video/HP alignment, playable overlay video |
| Intro | Two untitled pages; sourced copy; civilization campaign backdrop; reviewed unit art; narration and character timing; quiet music |
| Full video | Intro plus every approved canonical chapter; chronological chapters; results/HP description; successful whole-file decode |
| Ten distinct Shorts | Recorded-outcome selection reasons; correct portrait/HP queues; battle crop; panels; original game audio; valid media |
| Covers | One landscape and one reusable vertical cover for the subject, matching its intro parchment/art |
| Review | Real visual/audio review recorded against the final media, not merely an encoder exit code |
| YouTube | Correct channel, returned video IDs, thumbnails submitted, every processing status `succeeded`, saved completion receipt |
| Optional simulation report | Five seeds per supported matchup from the same saved plan; wrong-winner and HP-delta report; unsupported cases explicitly identified |
| Handoff/archive | Final full video and raw frames preserved; manifests, source provenance, narration, results, QA, and upload receipts retained |

**Capture completion, overlay completion, file transfer, YouTube processing, and public publication are different milestones.** Uploads start private. A processed private upload satisfies the established upload workflow; public release requires the owner's requested visibility. Preserve visibility changes the owner makes in Studio.

A concrete recent example is [Elite Monaspa](elite-monaspa-video-production.md): 73 captures, 73 overlays, a 26:49 full video, and 10 Shorts, all 11 uploads processed. [Its full video](https://www.youtube.com/watch?v=5gRrdmf9r24) may require channel access while private. At this handoff, Obuch has 73/73 verified captures and no media package yet. Those are status examples, not commands to restart completed work.

## 2. Non-negotiable matchup and presentation rules

### Costs and army sizes

Use civilization-specific **fully upgraded Imperial purchase cost per physical unit** from [recording-costs.json](../data/recording-costs.json), then calculate the synthetic comparison cost using the [approved balance policy](video-production/BALANCE_POLICY.md). Do not substitute legacy registry prices for audited cost evidence.

- Food, wood, and gold each weigh 1 for this series.
- Standard main-army cap: 27 units per side. Maximum resources per main army: 5,000.
- For shared units, halve the effectiveness of positive food/wood discounts; retain full gold discounts. Exclusive units use actual final costs. Use audited per-unit base costs from the cost catalog only to calculate the shared-unit discount adjustment.
- Let `score = comparisonCost * militaryPopulation`. Give the lower-score army 27 units and the other `max(1, round_half_up(27 * sqrt(lowerScore / higherScore)))`. Ties give equal counts. Reject plans over the actual-resource ceiling; never silently change the formula.
- This balances resource and population efficiency. It does not produce equal spending. Public descriptions and Shorts must use the saved plan's policy, not say “equal resources” for geometric captures.
- Apply civilization bonuses and researched technology discounts before per-resource purchase rounding. Divide by actual units delivered per purchase afterward.
- Blackwood Archers are trained in pairs: divide purchase cost by 2. Karambit Warriors' half population does **not** divide their price.
- Verify Goth infantry, Korean units, Inca units, Italian/Portuguese gold discounts, Mayan Plumed Archers, and all other cost effects using the installed data. Do not maintain an informal discount list instead of the audit.
- Save both catalog hashes in each plan. A changed catalog creates a new plan/version; never rewrite an old captured plan to look corrected. Preserve explicit historical balance modes.

The detailed regeneration procedure and the previous cost incident are in [Setup and data](video-production/SETUP_AND_DATA.md#cost-audit-and-patch-provenance) and [Production correctness audit](production-correctness-audit.md).

### Scenarios and ownership

- P2 is always the featured unit; P3 is the opponent.
- P1 is the spectator and inherits P3's civilization, so opponent-civilization music plays.
- Preserve the Golden camera: first `Starting` trigger, P1 target `(8, 7)` on the 16×16 land map, scrolling enabled. Do not recompute camera position from changing unit counts.
- Choose the Golden family from actual ranged/melee class, not the visual weapon or armor type. Throwing Axemen, Gbeto, and Mamelukes count as ranged here.
- Preserve authored unit-slot ordering, triggers, `NoneAI`, diplomacy, and P4 behavior. The normal mixed ranged/melee Golden has **nine** Spanish screen slots. Starting scenario units are Scout Cavalry and the tested upgraded entities are Hussars. Do not change the count to the earlier recalled “ten Huskarls.”
- The screen is free and excluded from main-army cost, counts, chapter results, and overlay queues. Public copy says: **“Ranged units get a small front line of hussars when fighting melee units.”**
- For an explicit no-buffer experiment, use the native ranged-versus-ranged Golden with `player4Buffer: "none"`. Removing only P4 units from a mixed Golden leaves incompatible diplomacy/triggers and previously caused a crash.
- An explicitly requested smaller screen can retain the mixed Golden with `scenario: {"player4Count": 5}`. This trims its authored P4 roster while preserving the gate, AI and diplomacy; it does not change the nine-slot default. See the [Blackwood five-Hussar experiment](blackwood-five-hussars-experiment.md) for partial recapture, recorded-screen verification, reuse, and winner comparison. Custom counts are recording-only until the simulation has a matching screen fixture.

Special cases, outside the normal scaffold:

| Subject/experiment | Required variation |
| --- | --- |
| Flaming Camel | No P4 buffer, ranged-versus-ranged Golden even against melee; check explosion and mutual elimination |
| Mounted Trebuchet | Ranged opponents only, no buffer; verify exact subject mode and roster |
| War Chariot | Use the requested focused-fire mode identity; do not substitute the other mode |
| Missionary | Conversions transfer entity ownership; end after the last opposing main unit is converted/killed |
| Naval experiment | Committed `water_map` template, cap 15, max 5,000, no P4, capture frames, no naval simulation claim |

See [exception manifests and recovery](video-production/OPERATIONS_AND_RECOVERY.md#special-scenarios).

### Presentation

- Raw footage must begin at the first in-game battle frame, after editor Test/loading. Capture can start earlier internally so no game frames are lost; `battle.mp4` removes that lead-in.
- Keep in-game music/sound. Do not add computer-use narration or record unrelated desktop audio.
- End close to actual battle completion. A timeout, stale entity list, or post-conversion wait is not a valid ending.
- Bottom panels use the game glyph atlas, unit portrait, civilization border, and emblem centered on the portrait's bottom-right corner.
- Unit names only, generous margins, no “Player 2/3” or “Starting Stats” labels.
- Bonus damage is a separate green bracketed annotation, not ordinary attack upgrades and not negative armor on the opponent.
- HP queues use persistent entity IDs and timestamped HP. Living units compact first; dead units are gray. Full-video queues have up to three columns and nine rows. Shorts preserve both queues above the battle, with P2 on the left and P3 on the right.
- Full intro: two untitled pages with speech-aligned letter reveal. Rules, chapter navigation, and results belong in the description.

## 3. Prepare the workstation

Follow [Setup and data](video-production/SETUP_AND_DATA.md) before running any live command. A Git clone does not contain the installed game, private credentials, original captures, machine configuration, or downloaded helper executables.

The commands in this guide run from the repository root in **PowerShell**, with Python 3.12 recommended. Replace the example new unit and machine paths intentionally. The example below is illustrative; it does not authorize an extra capture campaign.

```powershell
Set-Location C:\dev\aoe2\aoe2_matchup
$ErrorActionPreference = 'Stop'
$Repo = (Get-Location).Path
$Py = Join-Path $Repo 'apps\video\.venv\Scripts\python.exe'
$Lab = Join-Path $Repo 'aoe2x\js_simulation\calibration\lab'
$Key = 'elite-kamayuk'
$Slug = 'elite_kamayuk_incas'
$Label = 'Elite Kamayuk'
$Civ = 'Incas'
$Ident = $Key.Replace('-', '_')
$env:PYTHONPATH = 'apps/video;.'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:AOE2_GAME_DIR = 'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE'

.\scripts\bootstrap_aoe2lab.ps1
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap/doctor failed' }
```

If no base Python is detected, supply `-Python C:\Path\To\python.exe` to bootstrap. Configure local `aoe2lab.toml` using [aoe2lab.example.toml](../aoe2lab.example.toml). Full video helpers currently expect the **default Lab path**; for another volume, retain that logical path and use verified junctions as described in [storage setup](video-production/OPERATIONS_AND_RECOVERY.md#storage-and-archive).

Check FFmpeg/FFprobe, H.264 NVENC availability, game assets, reference database, costs, gRPC credentials/connection, audio loopback, and disk space. Record their versions and hashes. Do not assume a detected `python.exe` means the imports work.

Open AoE2:DE in the Scenario Editor, full screen on the primary display. If needed, launch through Steam, choose Editors, then load the dedicated working scenario. The recorder does not navigate arbitrary Steam/profile/main-menu screens safely. Keep the game frontmost throughout capture.

```powershell
.\scripts\aoe2lab.ps1 doctor --live --ui
if ($LASTEXITCODE -ne 0) { throw 'Resolve the live preflight before capturing' }
```

The doctor's normal data/dependency checks do not start a battle. `--ui` observes the editor state. [Doctor implementation](../aoe2x/lab/doctor.py) and [live preflight](../aoe2x/lab/live.py) specify exactly what is checked. Some offline art paths use `AOE2_GAME_DIR`; capture executable/scenario paths use `aoe2lab.toml`.

## 4. Register and scaffold a new unit

Resolve spelling to the canonical game identity first. A display label is not a reliable selector: civilization, upgrade tier, master ID, attack mode, and website slug can differ.

1. Search [unique-unit-roster.json](../data/unique-unit-roster.json) and [recording-subjects.json](../data/recording-subjects.json).
2. If absent, follow [new-unit registration](video-production/SETUP_AND_DATA.md#registering-an-entirely-new-unit). Add exact game-backed metadata and cost evidence; a simulator fixture is a separate requirement.
3. Confirm no existing queue entry/package should be resumed under the same key.
4. Preview the scaffold; it performs no capture, media rendering, narration request, or upload.

```powershell
& $Py apps/video/scaffold_video_episode.py --key $Key --slug $Slug
```

Review the displayed subject, roster size, and output paths. For a normal land-unit episode, create the files:

```powershell
& $Py apps/video/scaffold_video_episode.py --key $Key --slug $Slug --write
if ($LASTEXITCODE -ne 0) { throw 'Scaffold/cost preflight failed' }
```

[The scaffold](../apps/video/scaffold_video_episode.py) checks every plan with `validate_plan_costs`, refuses existing episode paths, and derives counts from the current roster. It creates:

| File | Purpose |
| --- | --- |
| `aoe2lab.recorder.<key>-all-unique.json` | Frozen ordered battle requests |
| `aoe2lab.overlays.<key>-final.json` | Initial canonical chapter list, initially identical to captures |
| `apps/video/run_<key_with_underscores>_capture.py` | Resumable capture wrapper with thermal checks |
| `apps/video/build_<key_with_underscores>_final.py` | Full/battle-only compilation adapter |
| `apps/video/prepare_<key_with_underscores>_final_shorts.py` | Outcome-based ten-Short selection adapter |
| `apps/video/finish_<key_with_underscores>_production.py` | Explicitly authorized publication supervisor |
| `apps/video/intro/<key>.json` | **Unfinished editorial draft**, with TODO copy/art/music |
| `data/local/<key>-capture-preflight.json` | All planned matchups and cost preflight evidence |
| Queue entry in `data/video-production-queue.json` | Planned episode, no implied publication authorization |

The scaffold copies the completed Monaspa land-media implementation with checked identity/count substitutions. Review the generated source, particularly tags, website link, screen wording, and special-ability copy. It is not an automatic writer of historical text or a proof of simulator support. Do not use it unchanged for the special scenarios listed above.

Record the user's requested deliverables and existing authorization on the episode. Do not run the historical multi-episode supervisors bare: their defaults target earlier campaigns. Do not re-enable a previously paused scheduled task merely because files were scaffolded.

## 5. Approve costs, counts, scenarios, and a pilot

Inspect `data/local/<key>-capture-preflight.json` before touching the game. Check every side's `effectiveCost`, `weightedCost`, `count`, `armyWeightedResources`, `scenario.family`, P4 policy, and cost/golden hashes. Verify the subject remains P2 in every row. Spot-check the extreme cheap/expensive opponents and discounted units in the actual game/data.

For the first use of a new unit/civilization/mechanic, record a small pilot with the **same job IDs** intended for the full manifest. Choose representative melee/ranged/discount/special cases; the first five are a basic smoke pass, not comprehensive mechanic coverage.

PowerShell 7 writes UTF-8 without a BOM. For compatibility with Windows PowerShell, use this helper when creating JSON read by Python:

```powershell
function Save-Json([string]$Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
}
$Manifest = Join-Path $Repo "aoe2lab.recorder.$Key-all-unique.json"
$Batch = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$Pilot = Join-Path $Repo "data\local\$Key-pilot.json"
Save-Json $Pilot @{ schemaVersion = 1; matchups = @($Batch.matchups | Select-Object -First 5) }
& $Py -m aoe2x.lab.recording_campaign $Pilot --reports "$Lab\campaigns\$Key-pilot"
if ($LASTEXITCODE -ne 0) { throw 'Pilot needs review/recovery' }
```

That command drives the game. Start it only with live preflight passed and capture authorized. Use the [thermal supervision procedure](video-production/OPERATIONS_AND_RECOVERY.md#thermal-monitoring) for a long manually launched pilot. The full capture wrapper includes thermal checks.

Review the pilot's actual video, audio, centered camera, counts, civilizations, screen, start/end timing, HP samples, and result. Generate one overlay if this is a new unit mechanic or theme. A failed visual pilot is not fixed by setting a success flag. Retake actual gameplay errors under a new job ID; fix offline defects without playing again when raw evidence is intact.

## 6. Capture the campaign and monitor progress

After pilot approval, launch the generated capture wrapper. It uses the entire manifest, reuses validated pilot bundles, and records a durable report. Never run two game drivers at once.

```powershell
$CaptureScript = Join-Path $Repo "apps\video\run_${Ident}_capture.py"
$Capture = Start-Process -FilePath $Py -ArgumentList @('-u', $CaptureScript) `
    -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$Repo\data\local\$Key-capture.stdout.log" `
    -RedirectStandardError "$Repo\data\local\$Key-capture.stderr.log"
$Capture.Id
```

The generated wrapper's merged report is `campaigns/<key>-canonical/status.json`; its active pass is `campaigns/<key>-canonical/resume-pending/status.json`. During the run, read the active pass, not an old merged total. The wrapper merges retained verified rows when the pass exits. Existing Monaspa/Obuch wrappers have historical report names; look at the script/queue rather than assuming the new convention.

```powershell
$ActiveReport = "$Lab\campaigns\$Key-canonical\resume-pending\status.json"
Get-Content -LiteralPath $ActiveReport -Raw | ConvertFrom-Json | `
    Select-Object state,total,completed,failed,pendingExports,currentJob,updatedAt
Get-Content "$Repo\data\local\$Key-capture.stdout.log" -Tail 15
```

The campaign plans the queue first; one process controls the game. One bounded offline finalizer clips/hashes/validates captured bundles while the next fight can run. Reports are persisted every ten matches and at failures/completion. `FINALIZING` can mean all game work has finished while exports catch up. `captureReleased: true` explicitly releases the game lock.

Normal monitoring checks the current matchup, timestamp/log growth, finalizer backlog, disk space, thermal state, and failures. A PID or growing file alone does not establish successful capture. After three consecutive capture failures the campaign stops for attention. Diagnose before restarting.

Before advancing to media, require:

- Exact requested job-ID set covered by the canonical capture report.
- Every intended result `verified`; no unresolved failure or pending export.
- Starting gRPC counts match both saved armies; P4 excluded from those counts.
- No capture interrupted by desktop use, thermal suspension, missing audio, or a stale/incorrect game build.
- `.frames.bin`, raw video, scenario, checksums, and battle clip all retained.

Detailed status meanings, immediate pauses, safe resumes, and prioritizing retakes are in [Operations and recovery](video-production/OPERATIONS_AND_RECOVERY.md). Do not leave the game idle while rendering this subject's videos: it can capture another authorized backlog subject. Offline media still finishes **one subject at a time**.

## 7. Run the optional V3 comparison lane

The video's winner is measured from the real game. Simulation is diagnostic and does not supply chapter results.

First run roster fixture preflight and the focused mechanics tests. Missing fixtures are repaired from installed game data, with real attack delay/windup, bonuses, armor classes, movement, and special effects. Do not invent windup values to force winner agreement. Fixture presence is not empirical calibration.

```powershell
node aoe2x/js_simulation/tools/preflight_recorder_roster.mjs "data/local/$Key-sim-preflight.json"
if ($LASTEXITCODE -ne 0) { throw 'Simulation fixture preflight failed' }
& $Py -m aoe2x.lab.postprocess_campaign `
    --manifest $Manifest --subject-label $Label `
    --campaign "$Lab\campaigns\$Key-canonical\resume-pending" `
    --output "$Lab\campaigns\$Key-v3-comparison" --simulation-only --simulation-workers 6
```

For a completed or resumed campaign with merged history, point `--campaign` at `<key>-canonical` instead. The active pass contains only that pass's jobs; the final comparison must cover the **merged** canonical set. Use `--once` for a bounded partial snapshot. The module now accepts both JSON and TOML manifests.

Each matchup has five seeds in isolated Node processes, with plan/source hashes. Six matchup workers means at most six seeds run simultaneously, not thirty. The source fingerprint changing stops scheduling; restart deliberately with new provenance. Use `--simulation-only` when the dedicated overlay renderer owns the media lane.

Reports include `report.html`, `status.json`, per-job `comparison.json`, seed playbacks/provenance, and `failures-over20.md/.json`. The normal MATCH convention requires 5/5 winner agreement and mean signed remaining HP within 10 percentage points. The requested concern list includes **any wrong seed winner or absolute mean HP delta strictly greater than 20 percentage points**. HP percentage points are not movement speed or damage-per-second. Unsupported conversion/naval/special-scenario cases remain unsupported; never label them accurate because a fallback ran.

See [fixture coverage and comparison semantics](recorder-roster-simulation-coverage.md) and [maintenance limitations](video-production/MAINTENANCE_AND_VALIDATION.md#known-limits).

## 8. Build and inspect all HP overlays

Run media for one subject at a time. Start with its verified canonical captures, including priority retakes. The overlay manifest may substitute corrected job IDs; keep intended civilization order and one authoritative chapter per opponent.

```powershell
$OverlayManifest = Join-Path $Repo "aoe2lab.overlays.$Key-final.json"
$OverlayReport = "$Lab\campaigns\$Key-final-overlays"
& $Py apps/video/render_campaign_overlays.py --manifest $OverlayManifest `
    --recording-status "$Lab\campaigns\$Key-canonical\status.json" `
    --output $OverlayReport --workers 8
```

Eight is the supported maximum in this renderer, not a recommendation to saturate a different workstation. Reduce workers if capture drops frames, disk latency rises, or thermals require it. A missing source bundle is not an overlay failure to hide; fix the canonical capture mapping first.

The per-battle implementation executes:

```powershell
$Run = "$Lab\runs\<exact-job-id>\live\run_001"
& $Py -m overlay.static_stats $Run --panels-only
& $Py -m overlay.auto_alignment $Run
& $Py -m overlay.unit_hp $Run
```

Outputs: `static-stats-overlay/panels.png`, `stats.json`; `unit-hp-overlay/units.json`, `alignment.json`, `battle-with-unit-hp.mp4`.

Alignment correlates visible in-game HP bars to recorded per-unit HP changes. Its quality gates must stay intact: at least 30 observations, RMS HP-fraction error ≤0.045, and alternative-error ratio ≥1.4. A high-frame-rate/short explosion clip may need denser observations:

```powershell
& $Py -m overlay.auto_alignment $Run --sample-rate 15 --color-components
```

This repaired Monaspa versus Flaming Camel from 23 to 66 usable bars without relaxing thresholds or recapturing. It is a recovery option, not permission to accept every denser fit. Inspect visible events. If still ambiguous, use measured source-hash-bound anchors following [HP overlay documentation](per-unit-hp-overlay.md) and [alignment recovery](video-production/OPERATIONS_AND_RECOVERY.md#alignment-and-offline-recovery).

Raw gRPC HP sidecars and derived timelines use different named clock fields. Respect the saved mapping; do not divide an already video-clock sidecar by game speed again. Conversions transfer living entities to the new owner and remove them from the old queue.

Require overlay status COMPLETE with the exact expected job set. Watch representative battle starts, HP reductions, casualties, conversions, and endings. Static attack/armor panels do not promise to display every dynamic buff; the current live portion is entity HP/counts.

## 9. Create the civilization intro and covers

Follow [Media and publication](video-production/MEDIA_AND_PUBLICATION.md#campaign-background-and-copy) for complete asset, extraction, voice, and timing commands. The required sequence is:

1. Resolve the civilization's campaign background from the catalog; distinguish first-scenario P1 evidence from curated art associations. Wei deliberately uses Art of War; narrator selection is independent of that backdrop.
2. Find a suitable unit illustration or generate an original campaign-style sketch using the exact unit sprite as reference. Save the prompt/reference and reviewed output. Use real transparency or plain white for multiply compositing; no painted checkerboard.
3. Replace every TODO in `intro/<key>.json` with two untitled pages of sourced, paraphrased overview/unique-ability text. Put the rules and chapter explanation in the video description.
4. Extract the civilization's available campaign narrator, or Art of War fallback when absent. Reuse an active authorized clone where available. Do not reuse a retired/deleted voice ID for new narration.
5. Generate narration with character timestamps and matching text, then build the intro with quiet background music. Inspect the actual encoded result, not only page PNGs.
6. Build and inspect both parchment covers with the same backdrop and centered unit sketch. Keep the title below the illustration.

```powershell
& $Py apps/video/build_campaign_intro.py --plan "apps/video/intro/$Key-cloned.json" `
    --output "$Lab\compilations\$Key-unique-units\intro-v1"
& $Py apps/video/build_campaign_thumbnail.py --plan "apps/video/intro/$Key-cloned.json" `
    --prefix "apps/video/intro/thumbnails/$Key" --title $Label
```

The `-cloned.json` plan is generated from actual narration; do not create one by renaming the draft. Background parchment shapes differ. Adjust `textX`, `textWidth`, illustration placement, and safe margins for each civilization. Monaspa used x=865 and width=465 to avoid Tamar's foreground artwork. A previous unit's successful layout does not validate a new background.

## 10. Compile the full video and select ten Shorts

```powershell
& $Py "apps/video/build_${Ident}_final.py"
if ($LASTEXITCODE -ne 0) { throw 'Full compilation failed' }
& $Py "apps/video/prepare_${Ident}_final_shorts.py"
if ($LASTEXITCODE -ne 0) { throw 'Short selection failed' }
& $Py apps/video/render_selected_shorts.py `
    --selection "$Lab\shorts\$Key-selected-10\selection.json" --workers 8
```

The full builder normalizes the intro to 2560×1440/60 fps, uses the validated battle overlays, clips unnecessary tails using conversion-aware terminal ownership/HP, preserves compatible battle video packets during concatenation, mixes/normalizes audio format to AAC 48 kHz, embeds chapters, checks total duration/chapter count, and decodes the entire final file with FFmpeg. `manifest.json` is written only after those checks pass.

Keep an eye on exact dependencies: if the intro or a source chapter changes, cached normalized intros, trimmed chapters, final manifest, Shorts selections, and QA may be stale. Use the [invalidation procedure](video-production/OPERATIONS_AND_RECOVERY.md#changing-inputs-after-rendering); existence alone is not sufficient provenance.

Ten-Short selection uses actual recorded results and corrected per-unit costs:

- Most expensive infantry beaten and cheapest infantry lost to.
- Most expensive melee cavalry beaten and cheapest melee cavalry lost to.
- Most expensive archer beaten and cheapest archer lost to, including mounted archers.
- Missionary and Flaming Camel, when eligible and not the subject itself.
- Two other interesting eligible matchups, using the recorded outcome and a written reason.

If a win/loss category has no eligible candidate, record that fact and fill with an interesting actual result. Do not manufacture a category winner, repeat one opponent, or select an exact self-match. Special subjects may require adapting the mandatory-opponent assertions and documenting why.

Each Short is 1080×1920 with the fight visible, live HP portrait queues above, unit panels below, equal-resource/27-cap text, conditional Hussar wording, and original game sound/music. Inspect crop coverage throughout movement, not only at the opening formation. Durations above three minutes fail the current QA expectation and require an editorial decision.

## 11. Perform visual and audio QA

```powershell
& $Py apps/video/production_qa_sheet.py $Key
```

This generates contact sheets from the **actual full compilation** at first/middle/last chapter midpoints and from **all ten actual Shorts**. It does not approve anything automatically.

Open:

- `compilations/<key>-unique-units/final-cost-v2/qa/full-contact.jpg`
- `compilations/<key>-unique-units/final-cost-v2/qa/shorts-contact.jpg`
- Encoded intro frames at early/middle/end and each complete page.
- Both final cover JPEGs.

Also play the intro and samples of original/overlay/Short audio. Check readable names/margins, correct portraits/civ emblems, screen/cost copy, battle visibility, queue HP timing, proper start/end, chapter transitions, no unrelated speech, no clipping, and no missing music. Inspect every anomaly and special ending. Check the description's title, exact chapter count, monotonic timestamps, winner perspective, HP, website selection, and prohibited boilerplate.

The release QA receipt is:

`compilations/<key>-unique-units/final-cost-v2/visual-qa.json`

After actual review, save `passed: true`, reviewer/time, exact final-video SHA-256, reviewed scope, evidence paths, and any accepted limitations. Mark each Short's review state after inspecting it. [QA receipt example](video-production/MEDIA_AND_PUBLICATION.md#release-review-record) explains the schema. **Never write a passing receipt to make a waiting supervisor continue before review.** Revoke/archive it if any reviewed input changes.

Representative frames plus full decoding are useful checks, but are not a claim that a human watched every frame or that V3 simulation is accurate. Ask the owner for any review explicitly requested for that episode; reuse existing approval where its scope already covers the final work.

## 12. Authorize, upload, and verify YouTube processing

**YouTube upload uses OAuth 2.0, not a simple API key.** The ElevenLabs API key is separate and only supplies narration. Follow [OAuth setup](video-production/MEDIA_AND_PUBLICATION.md#youtube-oauth-and-channel-verification) with a Desktop client JSON and user consent for the correct channel. Keep secrets outside Git.

Production account:

| Setting | Established value |
| --- | --- |
| Channel | `@aoe2matchup` |
| Channel ID | `UCKYN-pN4AZ3w4LpRxcdSciA` |
| Initial visibility | Private |
| Category | Gaming (`20`) |
| Languages | English (`en`) |
| Made for kids | False |
| License/embedding | Standard YouTube / enabled |
| Synthetic-media setting | True for narrated cloned-voice full videos; false for gameplay-only Shorts |
| Description | Rules, chapters, WIN/LOSS from subject perspective, winner HP, preselected website link, relevant hashtags |

Do not include the removed narration-disclosure sentence, the “one recorded battle, not an average” sentence, or the “Tiger Cavalry is already selected” suffix. [Description style](../apps/video/youtube-description-style.json) preserves this choice. The separate API synthetic-media setting remains enabled for narrated full videos.

Once final QA and upload authorization exist, use the **generated single-subject** supervisor:

```powershell
& $Py "apps/video/finish_${Ident}_production.py" --upload-authorized
```

It reuses completed stages, waits for QA when necessary, creates concrete preparation/settings files and the episode-specific cost-audit allowlist entries, uploads the full video followed by ten Shorts, and checks all remote processing results. Its status is `data/local/<key>-production-status.json`; the media lock is `data/local/final-production.lock`.

The legacy supervisor module defaults to Champi/Guecha/Temple Guard. **Do not run `finish_pending_production.py` directly to start a new unit.** Existing wrappers such as Monaspa use historical naming and may not take the new authorization flag; their already authorized runs are documented separately.

Each upload has a stable state key, for example `<key>-full-cost-v2` and `<key>-short-01-cost-v2` through `-10-`. Retry using the same key and preparation; the uploader resumes the encrypted session or uses the saved video ID. Never clear the state or start another insert just because Studio shows 0% or processing takes time.

Completion requires all eleven returned IDs on the target channel, expected settings, thumbnail submission receipt, and `processingDetails.processingStatus == "succeeded"`. Studio copyright/checks, quality availability, thumbnail surfaces, and public visibility are additional checks; API transfer success alone does not establish them. The receipt is `compilations/<key>-unique-units/upload-completion.json`.

See [YouTube's official upload workflow](https://developers.google.com/youtube/v3/guides/implementation/videos) and [video status fields](https://developers.google.com/youtube/v3/docs/videos) for the difference between upload and processing. The guide's local implementation uses durable 16 MiB resumable chunks.

## 13. Archive, report, and hand off

Before cleanup, save a release report linking:

1. Subject identity, game build/DAT hash, roster and effective-cost catalog hash.
2. Canonical capture/retake mapping, counts, failures resolved, and any exclusions.
3. Full video, ten Shorts, descriptions, covers, chapters/results, intro/narration provenance.
4. Automated validation and real visual/audio review evidence.
5. All eleven YouTube URLs, remote processing states, and current visibility.
6. Optional V3 report and unsupported/mismatch cases, kept distinct from capture success.
7. Archive location/checksum inventory and exactly what was removed locally.

Keep the final full video and original `.frames.bin` with metadata/scenario/plan. Keep narration audio and alignments: retired cloud voice profiles cannot regenerate it. Only remove individual raw/overlay/Short derivatives under the owner's existing cleanup authorization after uploads are verified and no pending retake, review, or remake depends on them. Prefer copy → verify every file by SHA-256 → remove exact source paths. A folder count or completed copy command is insufficient. See [archive safety](video-production/OPERATIONS_AND_RECOVERY.md#storage-and-archive).

Commit code, source-backed data, intended generated unit art, approved templates/manifests, and documentation. Do not commit private keys, OAuth clients/tokens/sessions, raw captures, full videos, frame streams, downloaded game packages, or machine-local state. Verify the pushed remote commit matches local HEAD. This does not upload the multi-gigabyte evidence archive to GitHub.

## 14. Documentation and implementation index

### Current operating references

| Subject | Documentation | Main implementation |
| --- | --- | --- |
| Setup/plans/live contracts | [AoE2 Lab](aoe2-lab.md) | [CLI](../aoe2x/lab/cli.py), [config](../aoe2x/lab/config.py), [planner](../aoe2x/lab/planner.py) |
| Roster/batch recorder | [All-unique campaign](all-unique-unit-recording-campaign.md) | [campaign](../aoe2x/lab/recording_campaign.py), [scaffold](../apps/video/scaffold_video_episode.py) |
| Corrected costs | [Correctness audit](production-correctness-audit.md) | [cost audit](../scripts/audit_recording_costs.py), [setup audit](../scripts/audit_recording_setup.py), [plan guard](../aoe2x/lab/costs.py) |
| Capture timing/navigation | [Throughput](recorder-loop-throughput.md) | [orchestrator](../apps/video/auto/orchestrate_matchup.py), [end detector](../apps/video/auto/record_until_end.py), [clip](../aoe2x/lab/battle_clip.py) |
| gRPC evidence | [gRPC README](../aoe2x/grpc/README.md) | [logger](../aoe2x/grpc/grpc_hp_log.py), [redecoder](../aoe2x/grpc/redecode_hp.py) |
| Panels and HP | [Static panels](static-stats-overlay.md), [per-unit HP](per-unit-hp-overlay.md) | [static stats](../apps/video/overlay/static_stats.py), [theme](../apps/video/overlay/civ_theme.py), [timeline](../apps/video/overlay/unit_timeline.py), [HP render](../apps/video/overlay/unit_hp.py) |
| Timing validation | [Recovery reference](video-production/OPERATIONS_AND_RECOVERY.md) | [auto alignment](../apps/video/overlay/auto_alignment.py), [battle end](../apps/video/overlay/battle_end.py) |
| Intro/campaign assets | [Asset findings](campaign-intro-assets.md), [intro README](../apps/video/intro/README.md) | [catalog builder](../apps/video/build_campaign_catalog.py), [renderer](../apps/video/build_campaign_intro.py), [voice clone](../apps/video/create_intro_voice_clone.py), [narration](../apps/video/generate_intro_narration.py) |
| Shorts | [Selected matchup Shorts](selected-matchup-shorts.md) | [vertical renderer](../apps/video/build_vertical_short.py), [batch renderer](../apps/video/render_selected_shorts.py) |
| QA/publication | [YouTube workflow](youtube-video-workflow.md) | [QA sheets](../apps/video/production_qa_sheet.py), [OAuth](../apps/video/authorize_youtube.py), [uploader](../apps/video/upload_youtube.py), [supervisor](../apps/video/finish_pending_production.py) |
| Ordering/monitoring | [Ordered production](ordered-video-production.md), [thermal monitor](thermal-monitor.md) | [capture queue](../apps/video/continue_capture_queue.py), [thermal guard](../apps/video/thermal_guard.py) |
| Simulator | [Roster coverage](recorder-roster-simulation-coverage.md) | [preflight](../aoe2x/js_simulation/tools/preflight_recorder_roster.mjs), [mechanics export](../aoe2x/js_simulation/tools/export_roster_mechanics.py), [comparison](../aoe2x/lab/postprocess_campaign.py) |

### Historical design, investigations, and episode records

These explain decisions and retain past evidence; dated claims about completion or pending work may be superseded by later receipts.

- [Recorder v3 analysis](video-recorder-v3-analysis.md), [spike](video-recorder-v3-spike.md), [Tiger pilot](tiger-unique-recorder-pilot.md).
- [Approved Tiger production/review sequence](tiger-cavalry-video-production.md), [release snapshot](tiger-cavalry-approved-release.json), [description](tiger-cavalry-youtube-description.txt).
- [Cataphract/Shotel/Ghulam investigation](tiger-cataphract-shotel-ghulam-analysis.md), [targeted repairs and compilation](tiger-targeted-repairs-and-compilation.md), [Shotel patrol follow-up](shotel-patrol-followup.md).
- [Liao Dao](liao-dao-video-production.md), [Grenadier](grenadier-video-production.md), [Inca Slinger](inca-slinger-video-production.md).
- [War Chariot](war-chariot-video-production.md), [Flaming Camel](flaming-camel-video-production.md), [Mounted Trebuchet](mounted-trebuchet-video-production.md), [Missionary](missionary-video-production.md).
- [Korean War Wagon](korean-war-wagon-video-production.md), [Korean Fire Lancer](korean-fire-lancer-video-production.md), [Magyar Huszar](magyar-huszar-video-production.md).
- [Flemish Militia](flemish-militia-video-production.md), [Elite Monaspa](elite-monaspa-video-production.md), [Elite Obuch](elite-obuch-video-production.md), [naval spike](naval-counter-spike.md).
- [Original narration options/history](../apps/video/intro/NARRATION-OPTIONS.md), [alternative unit-art workflow](flux2-unit-art-workflow.md), [patch workflow](patch-workflow.md), [data artifact producers](../data/golden/README.md).

The implementation inventory, focused verification commands, current limitations, and private/local asset boundaries are in [Maintenance and validation](video-production/MAINTENANCE_AND_VALIDATION.md). Start a future handoff by checking that file and the latest actual status receipts; do not infer a running process from this static document.
