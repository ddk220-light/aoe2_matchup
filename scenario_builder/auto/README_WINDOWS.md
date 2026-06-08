# Running the matchup automation on Windows

The automation is one cross-platform codebase. The only OS-specific bits live in
**`auto/platform_io.py`**, which has a macOS backend (the verified one) and a
**Windows backend** selected automatically on Windows. Everything else — scenario
generation (`build_run.py`), the cards/compose (`overlay/`), the navigation/watch
logic, the unique-units list — is the same on both.

> The Windows backend is a **working draft to adjust + test on a Windows box.** It
> mirrors each macOS primitive with a Windows one; you'll likely tune a couple of
> config values (scenario folder, display scale, audio device) for your machine.

## What maps to what

| Primitive | macOS | Windows backend |
|---|---|---|
| Screenshot | `screencapture` | Pillow `ImageGrab.grab()` |
| Click / keys | `cliclick` | `pydirectinput` (DirectInput, game-safe) |
| Keep app frontmost | `osascript activate` | `pygetwindow .activate()` |
| Screen recorder | ScreenCaptureKit (`recorder/sck_record`) | `ffmpeg -f gdigrab -i desktop` |
| Scenario folder | Feral VFS path | `%USERPROFILE%\Games\Age of Empires 2 DE\<id>\resources\_common\scenario` |
| Click scale | Retina = 2 | usually 1 |

## Setup (one time)

1. **Python 3.12** (not 3.13+ — onnxruntime/opencv wheels). Create a venv.
2. **Shared deps:** `py -3.12 -m pip install AoE2ScenarioParser rapidocr-onnxruntime opencv-python pillow numpy`
3. **Windows deps:** `py -3.12 -m pip install -r auto/requirements_windows.txt`
   (pydirectinput, pygetwindow, optionally mss + pywin32)
4. **ffmpeg** on PATH (for capture + compose), and **Google Chrome** on PATH (the cards
   are rendered with headless Chrome — see `overlay/render_card.py`).
5. **AoE2:DE** installed. Find your scenario folder (where the editor's Load list reads):
   usually `C:\Users\<you>\Games\Age of Empires 2 DE\<steamid>\resources\_common\scenario`.

## Configure (env vars — set for your machine)

| Env var | Purpose |
|---|---|
| `AOE2_SCENARIO_DIR` | **Required.** Full path to your scenario folder (above). |
| `AOE2_WIN_TITLE` | Window title to focus (default `Age of Empires II: Definitive Edition`). |
| `AOE2_SCALE` | Click-point scale. Start at `1`; if clicks land off, set to your display scaling (e.g. `1.25`, `1.5`). Best: run Windows display scaling at 100%. |
| `AOE2_AUDIO_DEVICE` | dshow audio device for system sound in the recording (e.g. `Stereo Mix (Realtek...)` or a VB-CABLE). Unset = **video-only**. |
| `AOE2_OS` | Force the backend (`windows`/`mac`) — normally auto-detected. |

PowerShell example:
```powershell
$env:AOE2_SCENARIO_DIR = "C:\Users\me\Games\Age of Empires 2 DE\76561198…\resources\_common\scenario"
$env:AOE2_SCALE = "1"
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

## Things you'll likely need to adjust / verify

- **Click accuracy (scale/DPI):** if the macro clicks the wrong spot, it's almost always
  display scaling. Set Windows scaling to 100% (cleanest), or set `AOE2_SCALE`. Making the
  Python process DPI-aware helps too.
- **Window focus:** `pygetwindow` matches `AOE2_WIN_TITLE`; confirm the exact title (it can
  differ slightly). `pywin32` is a fallback if needed.
- **Audio:** `gdigrab` records video only. For system audio you need a loopback capture
  device (Stereo Mix, VB-CABLE, or OBS's virtual audio) and set `AOE2_AUDIO_DEVICE`. Many
  people just record video-only here and it's fine.
- **Recorder:** ffmpeg `gdigrab` grabs the whole desktop (AoE2 fullscreen). If you'd rather
  capture the window or use a different recorder, edit `_win_recorder_start` in `platform_io.py`.
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
