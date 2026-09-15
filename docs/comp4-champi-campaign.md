# Champi four-civilization capture and overlay pilot

This is the separate eight-player workflow requested September 14, 2026. It keeps the approved four-arena Golden and compares Incas, Mapuche, Muisca and Tupi Champi Warriors against the same opponent simultaneously. The standard two-army production pipeline remains separate.

## Approved scope

- Capture the approved unique-unit roster in civilization/name order, retaining raw video and full `frames.bin`. The present roster has 74 opponents; Champi is not a roster entry. Derive future totals from the manifest.
- Four subject owners: P1 Incas, P2 Mapuche, P3 Muisca, P4 Tupi. Opponents P5–P8 share one civilization/unit and red color. P4 is a main army, never a buffer.
- P1 fights P5, P2 fights P6, P3 fights P7, P4 fights P8. Retain the Golden's mutual alliances between other owners, AI, patrol rectangles, terrain, colors and Post-Imperial settings. All Techs remains off.
- Eight physical units maximum per owner, 5,000-resource ceiling. No extra Hussars or other buffer units.
- Only the existing Armenian Bowman pilot receives the new overlay pending owner review. No other new overlay, compilation, Shorts or YouTube upload is authorized for this format yet.

## Source and cost calculation

Read [the original scenario analysis](comp-4-no-buffer-scenario-analysis.md) and [the approved fractional-HP pilot](comp4-champi-equal-resources-spike.md) first. The immutable template and its hash manifest are in `apps/video/templates/comp4_goldens/`. Never overwrite the owner's original game-folder scenario or substitute a legacy two-player Golden.

`build_comp4_scenario.py` hashes the Golden, audits the four Champi costs from the installed-DAT extraction, and validates the serialized scenario after writing. `prepare_comp4_campaign.py` obtains opponent cost evidence from `data/recording-costs.json`; its purchase rounding and units-per-purchase division already include discounts and Blackwood training in pairs. Population fractions do not divide unit cost.

The most expensive Champi costs 75 (50 food, 25 gold); Incas cost 60 (35 food, 25 gold). Determine the integer army counts against the 75-cost reference first. Keep that Champi count for all four variants. Scale the **reference opponent HP pool** by the variant/reference cost ratio, retaining full-health opponents and at most one partially injured opponent. Do not round up to another full-health unit.

For Armenians, the reference is eight Champi versus seven 50-HP bowmen. Incas receive the specifically approved six bowmen: five at 50 HP and one at 30 HP. The 60/75 discount makes the reference 350-HP opponent pool become 280 HP. This approved method is an HP handicap based on an integer reference, **not exact purchase-cost equality**. A partially injured opponent still has full attack until it dies.

The injury is a selected-object damage effect placed before the unchanged starting camera/patrol effects. Scenario slots, IDs and rotations remain Golden slots. All opponent owners get the selected civilization. The original Armenian pilot retained editor master 1800 with observed upgraded 50 HP; its separate validation receipt is preserved. New catalog-generated Armenian jobs explicitly place master 1802. Do not rewrite old evidence to change the recorded master.

### Runtime discrepancies found by the opening gate

The first all-roster pass accepted 72 captures and rejected two. Their original `scenario.json`, `scenario.aoe2scenario`, raw video and frames remain unchanged; retakes use separate `scenario-v2` files. `apps/video/comp4_runtime_profiles.json` records the build-specific evidence and the generator applies those profiles only to this Comp4 workflow.

- **Elite Mameluke:** all four opponent armies actually start at 120 HP per unit in build 180059; the reference DB expects 125. The installed DAT has base HP 80, tech 312's 1.25 multiplier and tech 435's +20. The reference analyzer's add-then-multiply order yields 125, while the observed Post-Imperial scenario gives 120. Use the observed opening profile: the Inca opponent pool is three at 120 plus one at 24, versus four at 120 for the reference variants. Do not change unit combat attributes to force the reference number. A future Mameluke card for this campaign must also use 120; broader reference/simulation behavior needs its own audit.
- **Elite White Feather Guard:** the seven-unit Inca opponent army starts at 100 HP each, but its selected-object damage of 60 leaves 43 HP before combat. The installed Shu technology includes the nearby-unit HP ability. This observation does not establish a universal armor or flat-damage-reduction rule. The Comp4 profile uses an empirically checked extra 3 points in that startup damage effect, and requires the retake to actually show six units at 100 and one at 40. Maximum HP and all Shu technologies remain unchanged. The generator refuses this compensation if the injured army has a different number of units.

The recorder rejects a runtime profile on a different game build. Retakes must still pass the full original opening test; these profiles do not loosen validation or promote the rejected videos.

## Prepare, run, pause and resume

Use the workstation prerequisites in [the main runbook](VIDEO_PRODUCTION_RUNBOOK.md). Game data and the local gRPC mTLS credentials are prerequisites; do not commit private keys. Run from the repository root with the existing video virtual environment:

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
& apps/video/.venv/Scripts/python.exe apps/video/prepare_comp4_campaign.py
& apps/video/.venv/Scripts/python.exe apps/video/run_comp4_campaign.py
```

FFmpeg must resolve in this process's PATH. If execution is restricted, use the environment's authorized execution mechanism; do not turn a missing executable into a successful render receipt. To leave the campaign running, start the same Python command with `Start-Process -WindowStyle Hidden`, repository working directory, and redirected output/error logs. Inherit the environment variables above. The existing production task starts its GUI navigation through `auto.orchestrate_matchup`; it selects the dedicated **Comp4 Matchup Run** staging name and uses the normal editor/load/test flow.

The game worker holds the same `recorder-campaign.lock` as the standard Lab campaign. Do not start another game controller. The recorder runs once per scenario while a single offline QA thread processes the preceding raw. Overlay work may run separately; it must not keep the game waiting for rendering.

The default campaign root is `data/local/comp4-champi-all-unique/`. Create its `PAUSE` marker to stop after the current recording. Resume only when authorized: remove that marker, verify the old worker exited, then run the same command. A resume accepts only verified receipts matching the scenario and retained media evidence. Failed or missing jobs are captured again into new attempt directories; existing bytes remain intact. `--limit N` supports a bounded pilot; `--seconds N` changes each capture's wall-clock cap (default 240).

## Recorder contract and failure handling

`capture_comp4_spike.py --plan <scenario.json> --out <new-attempt-directory>` arms video/audio and gRPC before the caller presses Test. It performs no UI inputs. The old P2/P3 end detector cannot be used here.

The capture must actually observe every planned count, subject HP, opponent HP distribution and placed master in the opening two game seconds, including the one-second starting trigger. A plan alone does not pass validation. All combat units belonging to owners 1–8 are counted after the opening: a converted Champi belongs to its new owner; dismounted replacement units still count. Revealers/support objects, dead units and projectile models are excluded.

Each pair resolves when one owner's army is empty, with a short stability check that is invalidated if a replacement appears. Record the first terminal time and HP then. Stop only once all four pairs are resolved and **three real seconds** have elapsed since the last terminal event. A timeout, missing initial state or incomplete pair result is a failed attempt, not a valid zero-unit victory.

Keep `raw.mp4`, the full length-prefixed protobuf `frames.bin`, snapshots `seed-*.bin`, `sequence-times.jsonl`, per-owner/per-unit `timeline.jsonl`, `initial-verified.json`, `status.json`, navigation logs, scenario and plan. Raw video includes the editor/loading lead-in; `validation.json.videoStartSeconds` identifies the first arena frame for later trimming. Save failed attempts too.

Offline QA checks opening validation, four results, video decodability, resolution, final hold, the complete protobuf container, and hashes. Opening/middle/ending contact frames are saved for visual inspection. Automated `VERIFIED` is distinct from a human/agent visual review. The worker stops after repeated failures or below 8 GiB free on the capture drive. Diagnose the actual failed matchup before retrying; do not restart completed captures simply because a display name differs from an editor master ID.

The established thermal guard runs every 900 seconds. Confirmed CPU ≥90°C or GPU ≥85°C pauses workloads. The owner's existing policy permits continued work when the CPU sensor is unavailable; do not repeatedly request the declined sensor setup or claim a CPU reading exists.

The 15-minute Codex heartbeat is named **Champi four-arena capture progress** (ID `liao-dao-recording-progress`, repurposed from the paused old monitor). It checks the current worker and advancing raw/frames, prioritizes suspicious/failed jobs, and reports meaningful changes or ten newly verified captures. Respect explicit pause requests and the thermal marker; never revive superseded supervisors. It must not proceed to the unapproved overlay batch.

Refresh the complete local table with:

```powershell
& apps/video/.venv/Scripts/python.exe apps/video/report_comp4_campaign.py
```

This writes `report.html` and `report.json` next to the campaign manifest. Each opponent has four rows with counts, opponent opening HP, result, winning side's remaining HP percentage and end time. A defeat's percentage is enemy HP relative to that enemy army's actual opening pool, including fractional injury.

## Armenian overlay review

```powershell
& apps/video/.venv/Scripts/python.exe -m overlay.comp4 --assets-only
& apps/video/.venv/Scripts/python.exe -m overlay.comp4
```

Default source: `data/local/comp4-champi-spike/capture-01/`. Default output: `data/local/comp4-champi-overlay-review/Champi_Four_Civilizations_Armenian_Overlay.mp4`.

The renderer uses the installed game's font atlas, stat icons, civilization panel art, emblems and existing unit portraits. Four cards occupy the outer corners in P1/P2/P3/P4 order, with civilization names and team-color markers. The common opponent card is a concave X following the two forest strips in screen space. Its diagonal unit title and stat positions are deliberately fitted inside that shape. The ordinary rectangular central card would hide the arenas.

The four result panels sit inside their completed arenas. They use the **Champi civilization emblem** for both outcomes: green victory or red defeat. Victory HP is the surviving Champi army's percentage; defeat uses clearly labeled enemy HP. Results derive independently from the timestamped gRPC owners, not the order in which the game shows defeat toasts. The original pilot's raw-to-video cut is 28.9166667 seconds; its gRPC game-zero anchor and per-frame wall timestamps determine the result events. The last frame is extended to provide the full three-second ending hold where the original raw ends earlier. Original game audio is retained; added hold beyond that original recording is silent.

The review is 2560×1440, 60 fps H.264/AAC, approximately 16.73 seconds. All four Champi variants win this original pilot: Incas 62.7%, Mapuche 51.2%, Muisca 17.7%, Tupi 37.9% HP left. The new raw campaign's Armenian result is a different recorded battle and must not replace this pilot's HP numbers in its overlay.

`overlay.json` stores event times and layout; PNG layers, preview frames, encoder log and `encoded-qa.json` remain with the video. Verify the actual encoded opening, first result and final frame, decode the complete file, then transfer the exact reviewed hash. The requested iPhone Taildrop uses the device's Tailscale address discovered from current status; do not assume a remembered peer is still the same device. File-transfer success does not mean the owner has reviewed or approved the layout.

## Combined raw review

The owner requested all 74 completed raw battles as one iPhone review video while the overlay design is revised. Build this independently of `overlay.comp4`:

```powershell
$env:PYTHONPATH='apps/video;.'
& apps/video/.venv/Scripts/python.exe apps/video/build_comp4_raw_compilation.py `
  data/local/comp4-champi-all-unique data/local/comp4-champi-raw-compilation
```

The builder follows the manifest's matchup order and resolves **each accepted capture from `status.json.completed`**, including the two corrected retakes. It checks the raw file hashes against their verified receipts. It trims only the loading lead-in at `validation.json.videoStartSeconds`, rounding to the first complete frame, and keeps every subsequent recorded frame including the ending hold. The output remains 2560×1440 at 60 fps, with original game audio, direct cuts and embedded matchup chapters. It adds no overlay, introduction, narration or music.

Temporary MOV segments contain re-encoded H.264 video and lossless PCM audio; the final MP4 copies that video and encodes AAC audio once. `clips.json` preserves source paths/hashes and frame-accurate trim/chapter boundaries. `chapters.txt` is the readable matchup index. `validation.json` binds the final file hash to the source-hash, frame-count, chapter-count, duration and full-file decode checks. Inspect the encoded openings/joins before sending it with the same fresh-device Taildrop procedure above. Preserve all canonical raws, frames and rejected-attempt evidence; only temporary compilation segments can be removed once the final MP4 passes QA.

## Relevant checks

```powershell
& apps/video/.venv/Scripts/python.exe -m unittest apps/video/tests/test_comp4_balance.py apps/video/tests/test_comp4_capture.py
```

These cover the approved HP example and rounding boundaries, original Golden/player/diplomacy/patrol preservation, exact opening HP/master rejection, and owner accounting for converted or replacement units. Final font placement and scene coverage still require real image/video review.
