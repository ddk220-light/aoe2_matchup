# Production operations and recovery

[Return to the complete runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

## Find the truth before starting anything

Read the episode's manifest, queue entry, current report, and actual process/log state. A prior conversational status or a `pid` saved yesterday is not proof of a live worker. The queue is an operator ledger, not a transactional scheduler/database. Concurrent writers can overwrite each other's queue edits; serialize manual changes and preserve unrelated fields.

Useful read-only checks, using the variables established in the runbook:

```powershell
Get-Content 'data/video-production-queue.json' -Raw | ConvertFrom-Json
Get-Content "data/local/$Key-production-status.json" -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe','node.exe','ffmpeg.exe','AoE2DE_s.exe') -and
    ($_.CommandLine -like "*$Repo*" -or $_.Name -eq 'AoE2DE_s.exe')
} | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine
Get-Volume | Select-Object DriveLetter,FileSystemLabel,SizeRemaining,Size
```

Inspect only relevant process command lines; never dump environment variables or secret-bearing command histories. For CPU load, use measured process/system CPU and observed capture health; elapsed process CPU time alone is not current utilization.

### Authoritative state files

| Stage | State/evidence | How to interpret |
| --- | --- | --- |
| Episode list | `data/video-production-queue.json` | Requested order, pause, retakes, per-episode artifact locations |
| Recorder | `campaigns/<report>/status.json` | `currentJob`, `results`, `completed`, `failed`, `pendingExports`, timestamp |
| Resume wrapper | `.../resume-pending/status.json` | Current subset; merged parent report updates after pass exits |
| Capture bundle | `runs/<job>/live/run_001/recording.json` | File checksums, plan linkage, clocks, media, retention |
| Overlays | `campaigns/<key>-final-overlays/status.json` | Per-job media completion/error; exact manifest coverage |
| Simulator | `campaigns/<key>-v3-comparison/status.json` | Per-job five-seed comparison/unsupported error and source revision |
| Shorts | `shorts/<key>-selected-10/status.json` | Ten selected artifacts and render validation |
| Media supervisor | `data/local/<key>-production-status.json` | Current stage; not necessarily capture activity |
| Release QA | `compilations/<key>-unique-units/final-cost-v2/visual-qa.json` | Actual review of exact final media |
| Upload | `data/local/youtube/<state-key>-upload-status.json` | Durable byte progress, returned video ID, processing state |
| Package upload receipt | `compilations/<key>-unique-units/upload-completion.json` | All 11 transfers/processing checks |
| Thermal monitor | `data/local/thermal/status.json`, `history.jsonl`, `PAUSED.json` | Fresh readings, sensor availability, suspension ledger |

New scaffold wrappers use `<key>-canonical` capture reports. Historical Obuch uses `elite-obuch-all-unique`; Monaspa capture and later canonical reports differ. Follow the actual queue/script paths. A Monaspa production status file uses the historical underscore spelling `elite_monaspa-production-status.json`.

### Recorder states

- `RUNNING`: recording or progressing between battles. Inspect `currentJob` and log movement.
- `FINALIZING`: game capture phase exhausted; offline export/checksums still running. `captureReleased: true` means the game mutex was released.
- Per-row `finalizing`: raw evidence exists, but the bundle has not passed all export validation.
- Per-row `verified`: scenario/raw hashes, initial counts, terminal battle evidence, and media export passed the automated bundle checks.
- `COMPLETE`: all requested jobs in **this manifest/pass** verified. Check whether it is a subset before announcing the whole episode done.
- `COMPLETE_WITH_FAILURES`: pass exhausted with failures. Media cannot treat those rows as ready.
- `STOPPED`: soft operator stop after the active iteration, resumable.
- `STOPPED_AFTER_ERRORS`: three consecutive capture failures; inspect the first failure and current UI before any restart.
- `CRASHED`: unexpected supervisor failure; logs/partial evidence may be recoverable.
- `PAUSED_BY_USER`: an operator-maintained wrapper/report state used after immediate interruption; not an engine result.

Reports count completed work, not just scheduled jobs. `verified_010.json` and subsequent ten-match reports are durable checkpoints. The user wants reports every ten captures; do not claim “10 good videos” based only on ten launched matches.

## Pause and resume

There are separate controls:

1. **User/queue pause** prevents scheduling new production work in wrappers that check it.
2. **Campaign `STOP` file** stops the recorder between iterations.
3. **Thermal pause** suspends identified processes and retains a persistent safety latch.
4. **Paused Codex scheduled task** prevents scheduled follow-ups. It does not, by itself, stop detached Python/FFmpeg processes.

### Soft pause after the current matchup

Create `STOP` in the **active report directory**, not an obsolete parent report:

```powershell
$Report = "$Lab\campaigns\$Key-canonical\resume-pending"
New-Item -ItemType File -Path (Join-Path $Report 'STOP') -Force | Out-Null
```

Set `queue.userPause.state` to `PAUSED` while preserving all other queue fields if the user paused the whole workflow. This prevents a wrapper/queue from immediately scheduling another subject. A pause flag is a scheduling gate; it does not retroactively stop an already executing encoder or game round.

Wait for the active match and finalization to drain, then verify no capture worker owns the game. Never report it safe for the owner to use the desktop merely because a STOP file exists.

### Immediate game handoff

When the user needs the game immediately, inspect the specific capture wrapper, recorder process, and their descendants by PID **and creation time/command line**. Stop only that capture control tree after recording the interrupted job ID. Leave the user's AoE2 process open. A finalizer may be allowed to finish offline if it no longer drives the game. Do not kill every `python.exe`/`ffmpeg.exe` by name.

Preserve partial artifacts and logs. Do not mark the interrupted battle verified. A recording can span a pause in video/wall time while game time stops; the ending and alignment require review, often a retake. User/thermal pauses do not justify fabricating complete status rows.

### Resume safely

1. Confirm the user's current authorization to resume; do not let old “keep going” override a newer pause.
2. Inspect processes, the actual game screen, active/merged reports, STOP files, and thermal latch.
3. Clear only the intended user pause and active STOP after the pause is released. A thermal latch has its own resume checks below.
4. Reopen AoE2 if closed and return to the Scenario Editor full-screen. Main menu is insufficient: a previous resume reached three preflight failures because the game was open but not in the editor.
5. Retain the manifest/job IDs and run the same wrapper. It filters previously verified merged rows and writes a pending manifest and baseline under `data/local/`.
6. If a forced stop prevented merging the active pass, inspect its verified results too. Re-running the original manifest revalidates existing bundles and does not blindly recapture verified raw footage, but can take several minutes hashing prior work.
7. Merge/resume evidence without duplicates and verify the final full-manifest job set. Never sum a merged total and its already included subset.

The recorder's Windows file lock prevents two campaigns controlling the game simultaneously. A lock file's presence is normal; the OS-held lock, not file existence, is ownership. Do not delete locks to defeat an active worker. The full production supervisor separately locks `data/local/final-production.lock`.

## Retakes before ordinary backlog

Retakes needed by a pending publication take priority over new units. Separate capture validity from offline rendering validity:

| Failure | Correct response |
| --- | --- |
| Wrong unit/civ, count, upgrade, Golden, camera, game build, interrupted desktop, missing raw audio | New corrected capture job ID; preserve original evidence |
| Raw and frames valid, battle-start trim failed | Retry offline battle clipping/bundle finalization |
| HP alignment ambiguous | Inspect source events; denser bar sampling or measured anchors; hold if still ambiguous |
| Wrong border, emblem, label, or bonus annotation | Fix panel/overlay source and rerender from existing raw/frames |
| Long post-conversion/after-explosion tail | Use terminal ownership/HP and rerender/trim offline when captured evidence proves the end |
| Corrupt/missing frames | Recapture; don't synthesize per-unit HP from aggregate HP |
| Sim fixture unavailable or wrong mechanics | Repair/export fixture and rerun sims; raw game footage can remain valid |
| Upload transfer interrupted | Resume same preparation/state key; don't recapture/re-render |

For a retake, add a new job such as `<original>_retake_02`, with corrected canonical request. Track `original job → replacement job`, reason, changed counts, and validation. Update the overlay chapter manifest at that opponent's original position, then prepare a canonical capture status containing the selected verified rows. The final chapter list must have exactly one job per intended opponent; keep old reports untouched.

Audit-generated winner reports come from [report_cost_repair_winners.py](../../apps/video/report_cost_repair_winners.py). It compares verified captures and reports changed outcomes/counts/HP; it is not an instruction to replace public videos automatically. Uploaded YouTube media cannot be replaced through this pipeline under the same video ID. A corrected compilation is a new upload; leave old uploads alone until the owner decides.

## Special scenarios

Manifest rows support:

```json
{
  "scenario": {
    "goldenFamily": "ranged_vs_ranged",
    "player4Buffer": "none"
  }
}
```

This is the approved no-screen method for Flaming Camel. It changes the Golden family while preserving each unit's actual combat class. Do not manufacture a ranged Flaming Camel class, strip just P4's army, or borrow a default mixed scenario's simulation.

Examples to read, not blindly re-run:

- [Flaming Camel manifest](../../aoe2lab.recorder.flaming-camel-all-unique.toml)
- [Mounted Trebuchet manifest](../../aoe2lab.recorder.mounted-trebuchet-all-unique.toml)
- [Focused-fire War Chariot](../../aoe2lab.recorder.war-chariot-focus-fire-all-unique.toml)
- [Naval counter spike](../../aoe2lab.recorder.naval-counter-spike.json)
- [Water template](../../apps/video/templates/lab_goldens/water_map.aoe2scenario)

Water plans use `goldenFamily: "water"`, no buffer, cap 15, max resources 5,000, and actual naval unit identities. Preserve the map as a template. The V3 worker intentionally rejects naval simulation. A no-buffer land plan without a matching engine scenario is also rejected rather than compared against the wrong screen.

Missionary/Warrior Priest endings must inspect ownership, not original unit type alone. Mutual elimination, resurrection/dismount forms, and damage-over-time tails require their own terminal checks. The decoder keeps initial army identities stable and transfers conversion membership; otherwise newly spawned projectiles/effects can be mistaken for extra army members.

## Alignment and offline recovery

Keep these clocks distinct:

- Raw frame `gameMs`: game simulation time.
- Raw video and battle clip seconds: elapsed encoded video time.
- `battle.hp.json`: offsets shifted to battle-video time; do not scale a video-clock sidecar again.
- `unit-hp-overlay/units.json`: explicit game-to-video mapping plus each entity's HP/ownership rows.

Inspect `alignment-candidate.json` after a rejection. Normal automatic mode samples at 3 Hz and can retry at 6 Hz with color components. Short or cluttered clips may need 15 Hz or compact-bar handling. New observations must pass the same quality thresholds. `--recheck` compares with an accepted measured alignment and rejects shifts beyond two video frames; it is not a command to overwrite disagreement.

For event anchors, follow [test_alignment_anchors.py](../../apps/video/tests/test_alignment_anchors.py) and [auto_alignment.py](../../apps/video/overlay/auto_alignment.py) for the exact schema. Bind the evidence to the source video SHA-256 and mark visible game/video event intervals from real frames. Never guess an offset just to get a green status. Preserve rejected candidates and the reviewed anchor evidence.

Use [recover_campaign_alignments.py](../../apps/video/recover_campaign_alignments.py) only after reading its target/options and confirming it selects the intended episode. Existing recovery scripts contain historical defaults.

## Changing inputs after rendering

Several production helpers cache by file existence or prior complete status; they do not all hash every asset. Treat cache invalidation as a release operation:

1. Stop/drain this episode's media supervisor before changing its inputs; don't let it upload the old master during a re-render.
2. Preserve the prior final package and its QA receipt in a versioned directory.
3. For panel/theme/timeline changes, archive the affected overlay outputs and prior overlay status, then rerender the intended source jobs. Do not delete raw frames.
4. For intro/copy/voice/music changes, generate a new narration version where needed, rebuild the intro and cached `intro-1440p60.mp4`, and rebuild the compilation. Timestamped speech must match the new text exactly.
5. For changed chapter sources/ends, invalidate the cached trimmed chapter, concatenated full master, full manifest, chapters, and description.
6. If counts/results/costs/crop/overlay change, regenerate Shorts selection/affected Shorts and their validation.
7. Invalidate `visual-qa.json`, re-run automated checks and actual review, and save new source hashes.
8. If an upload already began, do not reuse its identity for different bytes/metadata. Inspect the saved video/session, decide the replacement version explicitly, and use a new state key only for an intentionally new upload.

## Thermal monitoring

The requested interval is 15 minutes. The current capture/full-production wrappers call `thermal_guard.py` through `pause_check()` at that cadence. A standalone overlay/simulation command does **not** automatically create a thermal monitor; use the existing authorized monitor/supervisor or a separately managed checker loop while long offline work runs. Avoid duplicate monitors/production schedulers.

The old Codex recurring capture task is **paused by user request** at this handoff. Do not unpause it as part of setup. Older [thermal notes](../thermal-monitor.md) include a superseded five-minute heartbeat arrangement. Current wrappers' 15-minute checks and the current user pause take precedence.

```powershell
& $Py apps/video/thermal_guard.py --dry-run
& $Py apps/video/thermal_guard.py
```

The first checks readings/targets without suspending work. The second acts on a confirmed threshold breach. Current thresholds: CPU ≥90°C or GPU ≥85°C. GPU is read via `nvidia-smi`; CPU uses a fresh Libre Hardware Monitor broker sample (≤90 seconds old), taking the hottest relevant core/package sensor.

**Current machine limitation:** the CPU sensor is unavailable/stale, and the user previously declined administrator sensor setup and authorized continued GPU-monitored production. Missing CPU temperature is reported as unavailable, never “safe.” Do not ask for that same setup again on this machine without a changed need or user instruction. New machines must establish their own monitoring policy and sensor availability.

On a real trip, the guard suspends the identified game and repository workers/descendants, saves exact PID/creation-time actions in `PAUSED.json`, and does not auto-resume. It does not alter fans/clocks/voltages. Its resume command requires explicit user resume plus fresh CPU <80°C and GPU <75°C. With missing CPU readings, that command remains unable to establish the documented safe resume condition; inspect the condition and obtain a deliberate operator decision, not a blind latch deletion. Review/retake any interrupted capture.

Installing/restarting the CPU broker uses [setup_thermal_sensor.ps1](../../apps/video/setup_thermal_sensor.ps1) and [thermal_sensor.ps1](../../apps/video/thermal_sensor.ps1), with administrator-controlled hardware access. No startup task is installed automatically. A 15-minute poll cannot catch every brief temperature spike and is additional to hardware protection.

## Storage and archive

Core paths are logical; record their actual target volumes. Current episodes commonly use:

```text
LAB/runs/<job-id>                         -> D:/AoE2 Renders/<key>/captures/<job-id>
LAB/compilations/<key>-unique-units        -> D:/AoE2 Renders/<key>/compilation
LAB/shorts/<key>-selected-10               -> D:/AoE2 Renders/<key>/shorts
```

Precreate a destination and a junction **only when the logical path does not exist**. Example for a new compilation:

```powershell
$Destination = "D:\AoE2 Renders\$Key\compilation"
$Logical = Join-Path $Lab "compilations\$Key-unique-units"
if (Test-Path -LiteralPath $Logical) { throw 'Inspect existing directory/junction instead of replacing it' }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
New-Item -ItemType Junction -Path $Logical -Target $Destination | Out-Null
Get-Item -LiteralPath $Logical | Select-Object FullName,LinkType,Target
```

Repeat deliberately for the subject's Shorts and each manifest job if its captures must live on D:. Do not move existing active folders while workers use them. A junction is not a second backup. Verify the external volume identity before relying on a drive letter that can change.

Capacity planning must include raw video + frames + battle clips + overlays + intermediate end trims + intro letter PNGs + final master + ten Shorts + temporary encodes. Estimate from actual pilot bytes per second/match and remaining jobs. The recorder's 2 GiB reserve and 1 GiB estimate are only a last gate, not a sufficient whole-episode budget. A previous 365-match backlog forecast required about 72 GiB while only 25 GiB was free; checking the gate alone would not have been adequate.

Archive procedure under the owner's authorized scope:

1. Identify exact inactive source roots and resolved targets. Confirm no active or pending review/retake needs them.
2. Create an inventory: relative path, bytes, SHA-256, associated job/episode, and retained plans/metadata.
3. Copy to the external HDD using one filesystem/shell end-to-end. Avoid `/MOVE`, `/MIR`, wildcard deletion, or pipeline-built `cmd /c` deletes.
4. Verify every destination file size/hash against the inventory. Keep a receipt and rerunnable verification report.
5. Only after successful verification, delete specifically inventoried source files using `Remove-Item -LiteralPath`, with resolved absolute targets checked inside the intended source root. Never recursively delete a junction target based on an unchecked computed path.
6. Update manifests/archive index so future redecoding can locate frames, metadata, scenario and plan together.

Keep full masters locally if re-upload may be needed; preserve original frames and narration even after individual videos are removed. Git ignores production binaries intentionally. Do not create “verified” receipts merely because a copy process exited zero. Archive transfer was already completed for previously approved old folders; do not add it to every future capture-status check.
