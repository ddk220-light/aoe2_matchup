# Elite Blackwood Archer with five Hussars

This is an isolated revision of the existing Tupi episode, requested on 2026-09-13. It reruns the 40 ranged-versus-melee fights with **five** Spanish screen units, retains the 33 ranged-versus-ranged fights, and compares recorded winners with the previous **nine**-Hussar baseline. The default Golden screen remains nine for other episodes.

## Conditions and baseline

- P2 is Elite Blackwood Archer, Tupi; P3 is the opponent; P1 copies P3's civilization for music.
- Equal resources, maximum 5,000, cap 27 main units. Use the current audited Imperial cost per physical unit, including Blackwood pair production. The actual Blackwood price is 17.5 wood + 22.5 gold per archer, total 40.
- The screen is outside the resource budget. Keep the first five authored P4 records, their positions, civilization, AI, diplomacy, and gate triggers. Do not edit the shared Golden.
- Classify by attack range, not damage type: Throwing Axeman, Gbeto, Mameluke, etc. remain ranged and reuse their old ranged-versus-ranged chapters.
- Before comparing, replace the original Huskarl, Chakram Thrower, Shrivamsha Rider, Kamayuk, War Wagon, and Plumed Archer recordings with their verified `cost_v2` captures. Only the latter three ranged opponents need newly rendered overlays for reuse: Chakram Thrower, War Wagon, Plumed Archer.
- For all 73 baseline chapters, fresh audited plans must reproduce both old recorded main-army counts and the Golden family/hash. A price correction that leaves rounded counts unchanged does not require recapturing the same fight. Preserve the old plan; record fresh cost evidence separately.
- Compare recorded game outcomes only. The simulator deliberately refuses a custom P4 count until its screen fixture supports it; it must not silently simulate nine against a five-screen recording.

## Entry points

Run from the repository root using the video virtual environment and environment documented in the [production runbook](VIDEO_PRODUCTION_RUNBOOK.md#3-prepare-the-workstation).

```powershell
$env:PYTHONPATH = 'apps/video;.'
$env:PYTHONIOENCODING = 'utf-8'
$Py = 'apps/video/.venv/Scripts/python.exe'

# Read-only with respect to the game; writes isolated manifests and preflight evidence.
& $Py apps/video/blackwood_five_hussars.py prepare

# One actual battle. Validate before proceeding to the remaining recordings.
& $Py apps/video/blackwood_five_hussars.py capture --pilot
& $Py apps/video/verify_recorded_screen.py aoe2x/js_simulation/calibration/lab/runs/blackwood_archer_five_hussars_02_armenians_warrior_priest/live/run_001

# Reuses the verified pilot; creates the remaining new captures serially.
& $Py apps/video/blackwood_five_hussars.py capture

# In a separate background process while capture runs. Media belongs to this
# one subject; full-video assembly starts after all overlays pass.
& $Py apps/video/build_blackwood_five_hussars.py run --workers 3

# Refresh the comparison independently at any point.
& $Py apps/video/blackwood_five_hussars.py compare
```

Use `Start-Process -WindowStyle Hidden` with stdout/stderr logs for long-running helpers. The capture and media supervisors honor the production/thermal pause latches and run the thermal guard every 15 minutes. Do not reactivate the paused recurring capture task. CPU sensor availability remains a machine-level limitation described in the runbook.

Before launching, use the live doctor and confirm the game is in the Scenario Editor. Only one capture process may hold the recorder lock. The ordinary status/report files remain authoritative; the supervisors do not replace capture validation.

## Artifacts and provenance

Manifests:

- [40 new captures](../aoe2lab.recorder.blackwood-five-hussars.json)
- [43 overlay renders](../aoe2lab.overlays.blackwood-five-hussars.json): 40 new fights plus three corrected ranged chapters.

Local report root: `aoe2x/js_simulation/calibration/lab/campaigns/blackwood-five-hussars/`.

| File | Purpose |
|---|---|
| `baseline.json` | Every old/new job mapping, cost-validated plan, old capture outcome, and reuse source |
| `preflight.json` | All 40 generated scenarios validated before game interaction |
| `pilot/status.json` | First capture evidence |
| `status.json`, `verified_010.json`, etc. | Recorder progress and ten-match checkpoints |
| `media-source-status.json` | Verified new/corrected recordings eligible for rendering |
| `overlays/status.json` | Per-chapter rendering and alignment status |
| `winner-comparison.md` / `.json` | Flips plus every completed/reused chapter, counts, HP, and source frame hashes |
| `production-status.json` | Capture/render/assembly/review state |

New capture IDs start `blackwood_archer_five_hussars_`. On this machine, their LAB run directories are junctions into `D:\AoE2 Renders\blackwood-five-hussars\captures\`. The separate compilation junction points to `D:\AoE2 Renders\blackwood-five-hussars\compilation\`. Originals and their frames remain intact.

Every new bundle receives `screen-verification.json`, tied to its `.frames.bin` hash. gRPC retains authored master ID 448 for these upgraded screen entities; they start with 95 HP. Requiring master 441 would incorrectly reject valid footage. The verifier checks five live screen entities and both planned main armies near the beginning of the game.

## Reuse, assembly, and review

The media worker reuses existing trimmed overlay chapter files when present. If an individual file was cleaned up, it extracts that chapter's interval from the retained original full video. The three corrected ranged sources use their own raw footage and frames. No ranged matchup needs a new game capture.

The approved Tupi campaign intro and its original narration/music are reused. The final remains 2560×1440 at 60 fps with game audio, live HP overlays, and 74 chapters including the intro. New clips end at the recorded terminal state, including residual damage. The assembler validates each source's format, full duration/chapter count, performs a complete error-sensitive decode, and saves SHA-256 provenance. Assembly writes a separate full video, not an overwrite of the original episode.

Final directory: `aoe2x/js_simulation/calibration/lab/compilations/blackwood-archer-five-hussars/final/`:

- `blackwood-archer-five-hussars-complete.mp4`
- `manifest.json`: sources, hashes, chapter times, results, automatic QA, review state
- `youtube-description-draft.txt`: explicitly explains five Hussars and reused ranged footage
- `render.log`, `chapters.ffmeta`, `concat.txt`
- `assembly-validation.json`: exact input/output hashes and a successful decode receipt, written before renaming the completed partial so a temporary Windows preview lock can be retried without rebuilding unchanged media

Inspect the pilot and representative new chapters at the opening, during damage, and near the ending. Inspect the recovered ranged chapters at their cut points. Confirm music/audio, readable panels, synchronized HP queues, complete fights, and the five-screen formation. `READY_FOR_REVIEW` means automated checks have passed; it does not claim a person viewed the entire final video.

The report uses Blackwood's perspective for win/loss. HP excludes P4. Baseline cost repairs are separate from screen effects, and reused chapters are labeled `reuse`. A flip is an observed outcome difference between single recordings, not proof that the smaller screen alone caused it. The capture/assembly scripts do not upload, synthesize new narration, create Shorts, or clean up sources.

The report also compares against the **originally compiled full video**. Chakram Thrower, War Wagon, and Plumed Archer had already flipped in the earlier cost-correction captures. Their ranged footage is reused in this version, so those three changes are reported separately from the new five-Hussar comparisons.

Recovery QA found one predecessor frame at each of the two fractional-PTS chapter cuts. The recovered clips remove that frame and the same 1/60 second of audio, with `.recovery-trim.json` evidence. The original full video is unchanged.

The completed 40-capture comparison found eight Blackwood wins becoming losses: Ratha (Melee), Ghulam, Tarkan, Iron Pagoda, Savar, Boyar, Keshik, and Tiger Cavalry. Relative to the originally compiled video there are eleven flips, including the three earlier ranged cost corrections described above. Exact counts and remaining HP are in the local comparison report.

Final HP is refreshed from the per-unit timeline when available, including the last pending damage ticks after the recorder's coarser outcome sample. The refresh verifies frame provenance and refuses a changed winner for manual investigation. Original recorder summaries remain intact; `terminal-hp/` records the small HP adjustments and timeline fingerprints. This refinement does not change the eight/eleven winner-flip totals.

## Authorized publication order

The owner subsequently requested all pending earlier uploads, specifically Obuch, followed by this Blackwood revision. Use the same title as the original Blackwood video, keep both uploads available, and let the owner decide whether to remove the older video. The current default visibility remains private.

After Obuch's full video and ten Shorts have completed processing, and after recording actual visual QA for the revised Blackwood master:

```powershell
& $Py apps/video/publish_blackwood_five_hussars.py --upload-authorized
```

The [publisher](../apps/video/publish_blackwood_five_hussars.py) verifies Obuch's eleven-video receipt, checks the reviewed master hash, reads the current original YouTube title, and creates a separate upload identity `blackwood-archer-full-five-hussars-v1`. It reuses the approved Blackwood thumbnail and keeps the revised five-Hussar conditions in the description. Rerunning resumes the same new upload. It never deletes or edits the original video.

## Recovery and code

- Capture can resume with the same `capture` command: validated raw bundles are reused. Inspect failures first; do not blindly delete evidence or claim progress from an inactive PID.
- Overlay failures are explicit in `overlays/status.json` and their job logs. Repair alignment using the [existing alignment workflow](video-production/OPERATIONS_AND_RECOVERY.md#alignment-and-offline-recovery), then rerun `overlays` or `run`. Preserve quality thresholds.
- War Elephant recovered with 15 Hz HP-bar sampling. Flaming Camel and Tiger Cavalry required a [reviewed event alignment](../apps/video/overlay/event_alignment.py): four visible explosions and three visible death transitions respectively. Saved before/after image hashes, source-video/frame hashes, exact gRPC death/count transitions, and bounded timing intervals are retained in each alignment receipt. This is explicitly a manual visual measurement, not a successful automatic HP fit. Rejected automatic candidates remain intact.
- If only assembly needs a retry: `build_blackwood_five_hussars.py assemble`. Versioned trim receipts prevent stale source reuse.
- Stop at a game-version/count/Golden provenance mismatch. Do not silently compare materially different setups.

Implementation: [experiment coordinator](../apps/video/blackwood_five_hussars.py), [media builder](../apps/video/build_blackwood_five_hussars.py), [recorded-screen verifier](../apps/video/verify_recorded_screen.py), [planner](../aoe2x/js_simulation/tools/aoe2lab_worker.mjs), [scenario builder](../apps/video/build_run.py), [live validator](../aoe2x/lab/live.py).

The reusable manifest option is `scenario: {"player4Count": 5}`. Valid values are integers 1–9 on a mixed Golden with P4 enabled; default requests retain all nine. The option participates in the plan hash. It cannot be combined with `player4Buffer: "none"` or a ranged-versus-ranged Golden.
