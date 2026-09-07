# Recorder v3 spike — 2026-09-07

The spike completed through aoe2lab on `codex/video-recorder-v3`. It recorded
26 Wei Elite Tiger Cavalry versus 27 Spanish Paladins (the canonical lab
equal-resource plan, cap 27). The raw recording has no added overlay and is
stored with the original gRPC stream in an expanded folder, not a ZIP.

## Repeat command

From the repository root:

```powershell
.\scripts\aoe2lab.ps1 batch .\aoe2lab.recorder.example.toml --phase recorder
```

The checked-in example selects job `tiger_paladin_recorder_v3`. Repeating this
command validates/reuses the existing recording. To capture a new trial, use
a new job ID or request additional repeats with `--live-repeats`.

Single-matchup equivalent:

```powershell
.\scripts\aoe2lab.ps1 record --side2 elite_tiger_cavalry_wei --civ2 Wei `
  --side3 paladin --civ3 Spanish --job-id tiger_paladin_recorder_v3
```

## Camera correction

Read the latest `default1.aoe2scenario` from profile `76561198690498042`, saved
2026-09-07 08:30 local time. Its SHA-256 was
`0b1124f2f9aa850ae9d5f873c4899df2713552495ab062384f392b707fe107b6`.

The first `Starting` trigger moves player 1's view to `(8, 7)` on the 16x16 map,
with scroll enabled and no object target. All four committed lab goldens already
have this exact authored setting. The error was in `build_run.py`: `_set_camera`
overwrote it with an army midpoint or ranged-army centroid, changing as the roster
changed. Removed that rewrite. Golden binaries and their hashes remain unchanged.
Added camera validation before Test and regression checks for all four families
with unequal 11-versus-23 rosters, including rejection of a tampered camera.

## Recorder behavior

- `record`, `live --mode recorder`, `run --mode recorder`, and
  `batch --phase recorder` retain expanded raw files and suppress composition.
- The per-repeat `recording.json` indexes the scenario, MOV, original frames,
  metadata, END marker, and decoded HP sidecar with sizes/hashes, explicit player
  mapping, game version, clocks, and probed video properties.
- Resume verifies the bundle without operating the game. Missing/altered files
  fail validation. A later statistics-mode resume cannot delete an explicitly
  requested recorder bundle. Recorder mode rejects stats/archive retention.
- Recorder/logger startup now participates in cleanup handling. Failed recorder
  attempts preserve footage and stream diagnostics. ffmpeg/ffprobe are checked
  before new live captures. The game returns to the editor after completion.

This main-based branch lacked the tracked lab package and JavaScript planner.
Imported the coherent lab/runtime baseline from `simulationv3-fixed`
(`6a43fe18af12844aef519fbe0bce4f27b7308f29`): lab package, launcher/docs/examples,
JS source/fixtures/tests/viewer and lab worker, goldens, and matching video/gRPC
dependencies. Existing local simulation/capture artifacts were preserved;
untracked collisions were checked before import. No branch merge or engine
mechanics tuning was performed. The compatible recorder signature avoids the
cached `origin/main` mismatch identified in the preceding analysis.

## Actual output

Relative to this checkout, the job is at:

```text
aoe2x/js_simulation/calibration/lab/runs/tiger_paladin_recorder_v3/
```

The repeat folder is `live/run_001/`. Its `raw recordings/` folder contains:

| Artifact | Result |
|---|---|
| `elite_tiger_cavalry_wei_vs_paladin.mov` | 279,286,196 bytes; H.264; 2560x1440; 60 fps; 63.411 seconds; audio present |
| `elite_tiger_cavalry_wei_vs_paladin.frames.bin` | 15,393,484 bytes; original gRPC stream |
| `elite_tiger_cavalry_wei_vs_paladin.hp.json` | 111 decoded rows in video-duration seconds |
| `.meta.json` / `.END` | Original game/clock metadata and completion evidence |

Video SHA-256:
`f9c967e503afb9999f60366fe9b4e223d4ebc6ebf8aa31c1d8fef2977382ae90`.
Frames SHA-256:
`2acc2e6f9e9c27e8d4ed8246c11ce3530d84766ddc718c39b6a819d8b5226a6f`.

Game build: 180059. Start counts: 26/27. The game ended with **five Spanish
Paladins**, total remaining HP **362**, or **7.45%** of their starting army HP.
The generated scenario's camera, AI, player settings, first-N positions, and
trigger structure all passed validation.

The raw tape intentionally includes the editor-menu/load lead-in and the final
hold. This preserves the original capture for later trimming/overlay alignment.
Use the saved end/video timing and inspect footage when anchoring a future HUD;
wall-clock offsets alone are not a guarantee of frame-accurate synchronization.
No overlay was rendered in this spike.

## Validation

- 17 Python lab/recorder/dynamic-army tests passed.
- 3 Node lab planner tests passed.
- Full recorded video/audio decoded through ffmpeg without errors.
- Inspected saved frames at 0, 10, 60 seconds and intermediate battle samples:
  opening editor menu, centered approach/combat, and final survivors are present.
- Ran the same recorder batch again: checksums validated, no new capture or game
  navigation, same original recording creation time and video hash.
- Initial preflight correctly refused an unrecognized screen while the game was
  behind the desktop in windowed mode. Raised/maximized AoE2 and retried the same
  job successfully. Future runs require foreground, primary-display fullscreen
  or maximized AoE2, as the existing desktop recorder expects.
- Also completed one JavaScript simulation seed for the identical plan through
  `aoe2lab simulate --seeds 1`. It predicted Spanish Paladins winning with 1,313 HP
  (27.02% remaining). This differs from the measured 362 HP; simulator calibration
  was not part of the recorder change. The simulation evidence is stored alongside
  the live capture under `simulation/`.

Large capture/playback files and machine settings remain gitignored. The code,
repeatable request, and this report are the versioned deliverables; the actual
video and gRPC evidence remain available in the local job folder.
