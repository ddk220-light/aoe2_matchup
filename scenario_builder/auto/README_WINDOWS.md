# Running the matchup automation on Windows

The automation is one cross-platform codebase. The only OS-specific bits live in
**`auto/platform_io.py`**, which has a macOS backend (the verified one) and a
**Windows backend** selected automatically on Windows. Everything else — scenario
generation (`build_run.py`), the cards/compose (`overlay/`), the navigation/watch
logic, the unique-units list — is the same on both.

> The Windows backend has been **verified on a Windows box** (capture / input / OCR /
> scenario folder all pass `auto.win_selftest`). It mirrors each macOS primitive with a
> Windows one; most machines need no config — the scenario folder is auto-detected and
> the process is made DPI-aware so clicks land at any display scaling.

## What maps to what

| Primitive | macOS | Windows backend |
|---|---|---|
| Screenshot | `screencapture` | Pillow `ImageGrab.grab()` (process is DPI-aware) |
| Click / keys | `cliclick` | `pydirectinput` (DirectInput, game-safe) |
| Keep app frontmost | `osascript activate` | `pygetwindow .activate()` |
| Screen recorder | ScreenCaptureKit (`recorder/sck_record`) | ffmpeg **ddagrab + h264_nvenc** (GPU, native res); auto-falls back to `gdigrab + libx264` when ddagrab/nvenc are unavailable; stderr → `<out>.ffmpeg.log` |
| Scenario folder | Feral VFS path | auto-detected `%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\resources\_common\scenario` |
| Output canvas | 1920×1248 (game window) | **native primary-display resolution** (compose scales+pads, preserving aspect; override with `AOE2_OUT_W/H`) |
| Click scale | Retina = 2 | 1 (DPI-aware) |

## Setup (one time)

1. **Python 3.12** (not 3.13+ — onnxruntime/opencv wheels). Create a venv.
2. **Shared deps:** `py -3.12 -m pip install AoE2ScenarioParser rapidocr-onnxruntime opencv-python pillow numpy`
3. **Windows deps:** `py -3.12 -m pip install -r auto/requirements_windows.txt`
   (pydirectinput, pygetwindow, optionally mss + pywin32)
4. **ffmpeg** (for capture + compose) — `winget install Gyan.FFmpeg`. PATH edits don't
   reach an already-open shell, but the backend also looks in the WinGet install
   location, so a fresh install works without restarting. **Google Chrome** on PATH or
   in `Program Files` (the cards render with headless Chrome — see `render_card.py`).
5. **AoE2:DE** installed. The scenario folder (where the editor's Load list reads) is
   **auto-detected** under `%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\resources\_common\scenario`;
   only set `AOE2_SCENARIO_DIR` if you have multiple profiles and want a specific one.

## Verify the machine (recommended first step)

```powershell
cd scenario_builder
.venv\Scripts\python.exe -m auto.win_selftest
```

Exercises all three capabilities — **capture** (screenshot + recorder), **actions**
(input injection + window focus), **saves** (OCR + scenario folder) — and prints a
PASS/FAIL report. A screenshot + a 3-second test recording land in `%TEMP%`. Everything
green ⇒ you're ready to run a batch.

## Configure (env vars — all optional; defaults work on a standard 100%-scaling setup)

| Env var | Purpose |
|---|---|
| `AOE2_SCENARIO_DIR` | Override the auto-detected scenario folder (multi-profile machines). |
| `AOE2_WIN_TITLE` | Window title to focus (default `Age of Empires II: Definitive Edition`). |
| `AOE2_SCALE` | Click-point scale (default `1`). The process is DPI-aware, so `1` is correct even at 125/150% scaling; bump only if clicks land off. |
| `AOE2_OUT_W` / `AOE2_OUT_H` | Output canvas size (default: **native primary-display resolution**). The recorder grabs native res; compose scales+pads to this, preserving aspect. |
| `AOE2_AUDIO_DEVICE` | dshow loopback device for the game's sound (default `virtual-audio-capturer`). The device is **probed at start**: if it doesn't exist the run records **video-only** with a warning instead of failing. Set to `''` for deliberate video-only. |
| `AOE2_OS` | Force the backend (`windows`/`mac`) — normally auto-detected. |
| `AOE2_GRPC_PRIMARY` | `1` (default): a sane gRPC redecode drives the overlay outright — exact game data, no OCR pass. `0` forces the OCR readout (with gRPC HP merged in when the series agree). The decoder was fixed + clock-corrected 2026-06-10 (deaths 24/24 timed, sidecar in video seconds via `AOE2_GAME_SPEED`=1.7) and cross-checked against footage offline (rmse 0.43) and live (merge rmse 0.41, end counts exact). |
| `AOE2_GAME_SPEED` | Game-sim-to-video clock ratio for the gRPC stream (default `1.7`, AoE2:DE "normal" speed). Change only if you run scenario tests at a different game speed. |
| `AOE2_NO_READOUT` | `1` (default): generated scenarios have no on-screen title/count readout — clean footage; the overlay counts come from the gRPC stream and the WINS banner remains as the stop signal. Set `0` to put the readout back for a one-off decoder cross-check run (e.g. after a game patch). |

PowerShell example (only if you need to override the profile):
```powershell
$env:AOE2_SCENARIO_DIR = "C:\Users\me\Games\Age of Empires 2 DE\76561198…\resources\_common\scenario"
```

## Run

Same commands as macOS (the backend auto-selects). With AoE2:DE **fullscreen in the
Scenario Editor**, then hands-off:

```powershell
cd scenario_builder
py -3.12 -m auto.batch_matchups --resources `
  --list auto/unique_units.json --slice 1:5 `
  --opponent "Muisca:elite_temple_guard_muisca" `
  --join "Temple Guard vs Uniques 01-05 (resources).mp4" `
  --copy-to "D:\AOEII_videos\3kResMatchUpVideos"
```

Raw recordings are archived to `<copy-to>\raw recordings\`, same as macOS.

For long sweeps, split recording and rendering — the game runs are wait-bound and the
compose is CPU-bound, so alternating them wastes wall-clock:

```powershell
py -3.12 -m auto.run_guecha_sweep --record-only          # game runs only, archives raws
py -3.12 -m auto.recompose_from_raws --jobs 3            # render 3 clips in parallel
py -3.12 -m auto.run_guecha_sweep --stitch-only          # join the compilation
```

## Things you'll likely need to adjust / verify

- **Click accuracy (scale/DPI):** the process calls `SetProcessDpiAwareness` at import, so
  screenshots and clicks share one physical-pixel space and `AOE2_SCALE=1` is correct even at
  125/150% scaling (verified: `win_selftest` lands a cursor move at 0px error). If clicks are
  still off, run `win_selftest` and, as a last resort, set `AOE2_SCALE`.
- **Window focus:** `pygetwindow` matches `AOE2_WIN_TITLE`; confirm the exact title (it can
  differ slightly). `pywin32` is a fallback if needed.
- **Audio:** system audio needs a loopback capture device (`virtual-audio-capturer`,
  Stereo Mix, VB-CABLE, or OBS's virtual audio); set `AOE2_AUDIO_DEVICE` if yours differs
  from the default. The device is probed at recorder start — missing ⇒ video-only with a
  warning, never a dead capture.
- **Recorder:** ffmpeg `ddagrab` (Desktop Duplication) grabs the desktop at **native
  resolution** and encodes on the GPU (`h264_nvenc`); machines without that support fall
  back automatically to `gdigrab + libx264`. The raw `.mov` archive is full-res. If the
  recorder dies at start you get the error immediately (not an empty file later) and the
  ffmpeg log sits next to the output as `<out>.ffmpeg.log`.
- **Game input quirks:** the in-game engine drops "teleport-then-click" events; the macro
  uses move → settle → down → up (same as macOS). If a click doesn't register, bump the
  `settle`/`hold` in `input_driver.click()`.
- **Scenario version:** the golden template is format `1.57` (Feral/Mac lags one patch).
  Windows DE (1.58+) loads older 1.57 scenarios fine. If you regenerate the template on
  Windows, save it at your game's version.
- **No build step:** unlike macOS (`recorder/build.sh`), Windows just needs ffmpeg.

## Where to look

- `auto/platform_io.py` — all the Windows primitives (`_win_*`). This is the file to tune.
- `auto/orchestrate_matchup.py` / `batch_matchups.py` — the run flow (OS-agnostic).
- `build_run.py`, `overlay/` — scenario + video (OS-agnostic).
