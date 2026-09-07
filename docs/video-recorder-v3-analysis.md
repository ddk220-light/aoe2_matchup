# Video recorder v3: real AoE2 footage in aoe2lab

Analysis date: 2026-09-07. Scope: repository and branch inspection, integration design, and implementation acceptance criteria. No game was launched, footage captured, or functionality changed during this analysis.

## Findings

The requested pipeline already exists under `apps/video`: generate a matchup scenario, load it into the AoE2:DE Scenario Editor, Test/play it, record the desktop and optional game audio, collect the live gRPC state, decode army HP, and burn an animated HP/count HUD into the footage. Reuse this pipeline behind aoe2lab rather than build another recorder.

Aoe2lab already wraps the live recording path on newer branches. Its missing feature is a supported video-rendering/output lifecycle: `run_live()` deliberately passes `compose=False`, and the default `stats` retention removes recordings after validation. Simply switching composition on would conflict with validation, raw archival, cleanup, and resume behavior.

There is also a concrete API mismatch in the inspected cached `origin/main`: its lab caller passes keywords removed from the recorder's current signature. Resolve that before implementing the feature.

The existing added HUD is **aggregate HP per army**, with surviving-unit counts, unit information cards, and a result card. It does not add a separate tracked HP label above every individual battlefield unit. Individual in-game HP bars may already be visible in the captured screen. A request for custom entity-following labels would need an additional entity/position/camera projection pipeline.

## Branch provenance

The analysis branch is `codex/video-recorder-v3`, created directly from local `main`. Spaces in the requested display name were normalized to hyphens, with the repository's default `codex/` prefix.

| Inspected ref | Commit | Relevant content |
|---|---|---|
| local `main` / analysis branch base | `fb18b47b4ec5e7c2a5ff4c02a3f0fe5c1842163f` | Existing real-game recording, gRPC HP sidecars, and overlay composer; no tracked `aoe2x/lab` package. |
| `simulationv3-fixed` | `6a43fe18af12844aef519fbe0bce4f27b7308f29` | Portable aoe2lab workflow and matching expanded recorder API. |
| cached `origin/main` | `0ce703be6db8c4c54b65578bf61f0255c44cf1a8` | Same lab package as `simulationv3-fixed`, newer video stack, and the caller/signature mismatch described below. |
| local `staging` | `7fca54d1f23a737fead1fea65647291feae9896b` | Older golden recording/calibration work; not the portable lab source. |

These are local Git refs, not a fresh remote fetch. Local `main` is an ancestor of cached `origin/main`; they are not interchangeable. No merge, rebase, or fetch was performed. The portable workflow introduction is `96c9404d` (`feat(lab): add portable capture and simulation workflow`). Video history also includes `9b9e5374` (golden recording), `8dbe6b67` (unit-analysis recording/stitching), and `13182370` (analysis video/reel pipeline). The `feature/unit-analysis-video` and `feature/unit-analysis-reel` refs were inspected for that lineage.

Existing untracked files, including `aoe2lab.toml`, simulation artifacts, `.tools/`, and video media, were left untouched and are not source dependencies committed by this analysis. Historical `lab/README.md` describes replay research; the CLI being extended is **`aoe2x/lab`**, not that directory.

## Existing end-to-end flow

| Stage | Source / entry points | Behavior |
|---|---|---|
| Resolve matchup | `apps/video/auto/orchestrate_matchup.py`: `resolve_side`, `equal_resource_counts`; `overlay/overlay_data.py`: `get_unit_card` | Resolve civ/unit slugs, scenario IDs, counts, display stats, and icons. Legacy default is 30-per-side count mode; lab uses its own canonical plan. |
| Build scenario | `apps/video/build_run.py`: `build_run`; supplied golden templates | Retarget armies, civs, counts, and scenario controls. Lab chooses one of four family goldens and preserves authored positions/AI/trigger mechanics. |
| Stage and navigate | `orchestrate_matchup.py`: `stage_generated`, `navigate_to_test_menu`, `return_to_editor`; `vision.py`, `input_driver.py` | Copy the generated scenario into the game profile, find/load it, reach Test, and return to the editor afterward. Code stages its named file without clearing all user scenarios; old README instructions about clearing the folder are stale. |
| Capture screen | `record_until_end.py`: `start_recorder`, `stop_recorder`; `platform_io.py` | Windows ffmpeg desktop capture: ddagrab/NVENC with gdigrab/libx264 fallback. Audio uses a configured loopback device, otherwise video-only. Graceful stop finalizes the MOV. |
| Capture state | `auto/grpc_capture.py`; `aoe2x/grpc/grpc_hp_log.py` | Separate process records CadeRemote state frames and metadata. The live tailer writes `.END` for fight completion. |
| Detect completion | `watch_until_result` | `.END` is the primary signal; OCR of the scenario WINS result is a fallback. Hold the result briefly; stop at the safety cap if needed. A no-result marker identifies suspect/truncated outputs in the legacy path. |
| Decode | `grpc_capture.redecode`, `write_sidecar`; `aoe2x/grpc/redecode_hp.py` | Decode recorded state offline into HP/count rows and synchronization metadata. Archive the stream so decoding can be repeated after fixes. |
| Select/synchronize timeline | `record_until_end.select_sidecar`, `detect_game_start`; `overlay/hp_merge.py` | Prefer structurally sane gRPC HP. Newer code prefers an end anchor, then detected video start; legacy fallback can use OCR counts or merged OCR/gRPC. |
| Render | `compose_live_overlay`; `overlay/compose.py`: `make_live_overlay_video`; `overlay/overlay_hp.py`, `hud.py` | Generate a top-band HUD, add information/results cards, trim footage, speed up long middle sections, and preserve captured audio through corresponding time transforms. |
| Deliver / re-render | `archive_raw`, `copy_sidecar`, `archive_stream`; `auto/recompose_from_raws.py` | Deliver MP4 plus the actual selected HP sidecar; retain raw MOV/state artifacts for offline recomposition. Existing sweep CLI is specialized; lab should render from its manifest instead of reconstructing matchup identity from names. |

Windows is the supported backend. The macOS ScreenCaptureKit implementation is historical. The old recorder README's statement that composition drops audio is also stale relative to the current live-overlay composer. Source code should drive the integration.

## HP and time contract

The sidecar contains `video_game_start_s`, `clock: "video"`, `game_speed`, `wall0_epoch`, `recorder_start_epoch`, game version, optional end timing, and rows shaped as:

```json
{"game_s": 12.5, "side1": {"count": 20, "hp": 1450.0}, "side2": {"count": 18, "hp": 1280.0}}
```

Despite the name `game_s`, sidecar rows are in video-duration seconds after `write_sidecar()` divides stream simulation time by `AOE2_GAME_SPEED` (default 1.7). Raw video time is `video_game_start_s + row.game_s`. Do not divide these rows by speed a second time.

In cached `origin/main`, `select_sidecar()` prefers `end_video_s - last_count_change_s` as its origin. This accommodates continuous streams whose zero predates scenario start. Pixel-detected game start is the next anchor. Preserve the anchor method and any correction in render metadata; do not assume the initial wall-clock offset is final truth.

The HUD interpolates aggregate HP, steps count changes, and normalizes against initial army HP. It renders at 5 Hz before output encoding. `clean_rows()` repairs presumed transient dropouts, including forcing counts to be non-increasing. That assumption needs explicit review for dismount/spawn-on-death units: actual temporary count dips/recoveries must not silently become fabricated history. The lab already detects the final stable elimination interval when summarizing these units.

Lab plan `side2` is player 2 and maps to sidecar `side1`; plan `side3` is player 3 and maps to sidecar `side2`. Newer video code heuristically swaps sides when unequal initial counts are reversed. Equal counts cannot identify ownership that way. Persist explicit player/slug/civ mappings in the capture/render contract and use them for labels and verdicts.

## What aoe2lab already supplies

Sources below are from `simulationv3-fixed` and are byte-identical in cached `origin/main` for `aoe2x/lab`:

- `cli.py`: `plan`, `simulate`, `live`, `run`, `batch`, `compare`, `status`, and `serve`; no video-render subcommand.
- `planner.py`: canonical plan from `aoe2x/js_simulation/tools/aoe2lab_worker.mjs`. Counts, balance weights, ranged classification, and scenario family must remain authoritative.
- `live.py`: serial repeats, bounded retries, hashed family goldens, scenario validation before play, required gRPC capture, decoded count/end validation, run manifests, and resumability.
- `live.py::_validate_scenario`: first-N of 27 golden positions for players 2/3, unchanged player 4, AI, player settings, and trigger structure.
- `live.py::_validate_capture`: requires MOV, frames, metadata, END, and HP sidecar; validates start counts and exactly one defeated army; stores statistics and artifact paths.
- `retention.py`: `stats` deletes raw captures, `archive` ZIPs then removes expanded raw files, and `raw` retains them. Its recursive suffix list includes **both `.mov` and `.mp4`**, so placing finished videos inside the run directory without adjusting retention would also delete/archive them.
- `artifacts.py`: job directories and phase/checkpoint metadata; `config.py` bridges TOML settings into legacy environment variables before imports; `doctor.py` handles machine preflight.
- `scripts/aoe2lab.ps1`, `scripts/bootstrap_aoe2lab.ps1`, `docs/aoe2-lab.md`: launcher, environment setup, and user documentation on the newer refs.

## Blocking integration mismatch

In `simulationv3-fixed`, `run_matchup()` accepts `template`, `counts_override`, `ranged_override`, `scenario_validator`, and `require_grpc`, which `aoe2x/lab/live.py::run_live()` supplies.

In cached `origin/main`, the recorder instead exposes `build_fn`, `restart`, and `fixed_counts`, without those five lab keywords. The lab package remains unchanged. Calling it with the lab arguments therefore raises an unexpected-keyword `TypeError` once that call is reached. This is a static contract finding, not a claim that a live run was executed.

Restore a compatible interface or introduce a typed capture adapter. Map exact counts to `fixed_counts`; supply a builder that applies the selected golden and canonical ranged values and invokes the validator **before staging/Test**. Preserve required-gRPC startup/readiness checks rather than treating `require_grpc` as a disposable argument. Do not just rename counts and drop the remaining safeguards.

The analysis branch does not contain the tracked lab package at all. Implementation must first bring a coherent lab/planner/golden/launcher/dependency baseline onto this main-based branch, then reconcile the recorder API. Copying `live.py` alone or cherry-picking the workflow commit without its prerequisites is insufficient. Keep that integration separate from the rendering feature for review.

## Proposed implementation

1. **Reconcile the capture contract.** Preserve canonical plan counts, golden selection, scenario validation, gRPC readiness, cleanup, and artifact return paths across the selected baseline. Add a contract test that binds the lab call to the actual recorder signature without operating the UI.
2. **Add `aoe2x/lab/video.py`.** Consume a job/repeat manifest and validated capture artifacts. Adapt to `compose_live_overlay` or its lower-level composer with explicit matchup sides/counts; emit a final MP4, the selected sidecar, render log, and render manifest. Keep canonical decoded evidence unchanged when the renderer cleans or aligns rows.
3. **Expose two user paths.** Proposed commands: `aoe2lab live ... --video` to capture then render, and `aoe2lab video JOB_ID --repeat N` to render an existing capture without the game. Add corresponding full-run/batch options. These commands/options are proposals, not implemented commands in this branch.
4. **Protect the inputs until render success.** Video-enabled capture must retain raw footage through render validation regardless of the statistics default. After success apply the requested raw retention policy. Failed rendering retains its inputs for retry. A stats-only historical run with no footage needs recapture; HP JSON cannot reconstruct real gameplay pixels. Archive inputs can be extracted into an isolated render workspace after checking the archive checksum and safe member paths.
5. **Store delivery artifacts outside raw cleanup.** Suggested layout: `runs/JOB/video/run_001/{matchup.mp4,matchup.hp.json,manifest.json,render.log}` beside `runs/JOB/live/run_001/`. Explicitly distinguish raw capture inputs from final outputs in retention and status. Do not rely on filename suffix alone.
6. **Make rendering resumable independently.** Track capture and render statuses separately. Rendering failure must not mark good capture evidence invalid or force another game run. Resume keys should include raw/sidecar hashes, canonical plan hash, render settings, and renderer version. Record owner mapping, decoder version, anchor choice, clock/speed, selected data source, trim/ramp settings, output media metadata, and validation results.
7. **Add video preflight.** Validate ffmpeg/ffprobe, encoder fallback, card-render browser/assets, gRPC configuration for fresh capture, audio policy, and disk space for raw copies, HUD frames, and encoded output. Offline rendering should not require game focus, input injection, or a running gRPC service. Serialize game captures; initially serialize renders too because legacy modules use environment globals and temporary paths. Enable parallel rendering only with proven per-job isolation.

A minimum working delivery is a single requested matchup producing a real-game MP4 with a correctly synchronized aggregate HP HUD and result, plus sufficient artifacts to re-render it. Compilation stitching and vertical reels can follow; they are not required to establish this feature.

## Reliability requirements and acceptance checks

- Never label OCR count-as-HP as measured HP. For a video requiring true HP, invalid/missing gRPC evidence must fail clearly rather than quietly selecting `grpc-unverified` or rendering without a HUD. Clean footage often disables the count readout, so OCR fallback may have nothing to read.
- Verify that wrong-scenario loads cannot pass solely because the unit counts match; include unit/player identity evidence in validation where available. Remove blind top-row selection as an accepted success path unless subsequent identity checks prove the intended scenario.
- Enclose both recorder and logger startup in cleanup handling. Inspected recorder code starts the logger and then the recorder before entering the `try/finally`; recorder startup failure can bypass logger cleanup. Ensure each cleanup action still runs if an earlier cleanup fails.
- Mocked integration checks: exact counts/golden/side mapping preserved; incompatible recorder signatures fail in preflight; renderer failure leaves capture resumable; stats cleanup preserves finished MP4; archive and raw inputs re-render without recapture.
- Deterministic timeline fixtures: 1.7 conversion once, end/V0 anchoring, equal-count side ownership, first damage, stable final elimination, regeneration/dismount, and consistent HUD/audio time transforms through a speed ramp.
- Media smoke test from retained fixture footage: ffprobe confirms decodable video, nonzero duration, intended geometry/frame rate, and audio presence when requested. Inspect frames at the opening, first damage, ramp boundaries, final elimination, and result card against the selected HP rows.
- Controlled live acceptance after implementation: one melee matchup and one ranged matchup using known goldens; an unequal-count case; a spawn-on-death case; successful offline re-render; repeated invocation skips completed capture/render work. Confirm final stats agree with lab evidence and incomplete/capped fights are not presented as verified wins.

Only read-only source/history inspection and documentation checks were performed here. Existing README claims of prior live verification are historical evidence, not fresh validation of this machine or the current mixed branch interfaces.
