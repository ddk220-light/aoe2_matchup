# Per-unit HP overlay pilot

This is the user-approved YouTube overlay for `codex/video-recorder-v3`: the revised static stats panels plus the live portrait/HP queues. Approval followed review of the exported video on September 7, 2026.

The Tiger Cavalry / Armenian Composite Bowman export now combines the approved static panels with vertical portrait grids. Each grid fills down a column, then right, with three columns and nine rows. The header shows survivors and total current HP. Portrait bars use each entity's current HP, including healing; casualties turn gray and move behind the stable sequence of survivors. Player 4's golden-scenario frontline is excluded from both matchup grids.

The archived `frames.bin` already contains all necessary per-entity HP updates. No recording restart is needed. `overlay.unit_timeline` decodes each complete FrameSequence with the existing entity decoder, retaining entity ID, unit master ID, current HP and millisecond game timestamp. It reads per-entity own-master maximum HP when available, including growth effects; otherwise initial observed full health provides the denominator. Current HP is never inferred from aggregate army health or spread evenly across portraits.

The pilot contains 15 Tiger Cavalry and 27 Composite Bowmen initially, finishing with 0 and 25 survivors. Its 3,055 decoded state samples reproduce all 52 existing per-second aggregate samples exactly (both counts and summed HP). The stream has a four-byte incomplete trailing record after battle coverage; it is reported and ignored. Original bytes and checksums are preserved.

## Timing

The old sidecar assumes 1.7 game seconds per video second. Visible health-bar transitions establish approximately **2.0** for this recording. Reusing the old mapping would make later deaths noticeably late.

`unit-hp-overlay/alignment.json` binds the measured alignment to the source battle video's SHA-256. For this pilot:

```
video_seconds = game_milliseconds / 2000 - 0.7333333333
```

Two distinctive transitions of the last Tiger (entity 2066) anchor the mapping: game 31.272 seconds at video frame 894 and game 32.328 seconds at frame 926. At 60 fps their residuals are below 0.003 seconds. The first Tiger's death at game 10.432 seconds maps to about video 4.483 seconds and agrees with the visible early death. The end of the decoded stream maps to video 24.813 seconds, covering all 24.8 seconds of video. Frame sampling and pixel quantization limit visual precision to roughly one frame; this is measured alignment, not a claim that wall-clock metadata is frame exact.

The renderer requires verified alignment metadata. Future matchups need their own alignment verification; do not apply this pilot offset universally. Existing raw recordings remain reusable even where the older aggregate sidecar's time scale needs correction.

State lookup holds the latest observed sample at each 60 fps output frame. It never blends a future hit into earlier footage. Entity IDs stay attached to their HP when a death compacts the queue.

## Repeat

First render the approved static panels using `overlay.static_stats`. With the verified `alignment.json` present:

```powershell
$env:PYTHONPATH='apps/video'
New-Item -ItemType Directory -Force 'aoe2x/js_simulation/calibration/lab/runs/tiger_unique_01_armenians_composite/live/run_001/unit-hp-overlay'
Copy-Item 'apps/video/overlay/samples/tiger-composite-alignment.json' 'aoe2x/js_simulation/calibration/lab/runs/tiger_unique_01_armenians_composite/live/run_001/unit-hp-overlay/alignment.json'
& apps/video/.venv/Scripts/python.exe -m overlay.unit_hp 'aoe2x/js_simulation/calibration/lab/runs/tiger_unique_01_armenians_composite/live/run_001'
```

Use `--preview-only` to inspect layouts without encoding. The separate `unit-hp-overlay` folder contains `units.json`, alignment provenance, preview frames, the render log and `battle-with-unit-hp.mp4`. Rendering uses two encoder threads and leaves the running recorder campaign untouched. This pilot uses the two approved portraits and explicitly rejects grids exceeding 27 slots rather than silently dropping units.
