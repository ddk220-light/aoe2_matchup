# Scenario → Game → Record → Overlay pipeline — Mac setup & handoff

Cross-platform tooling for: generate an AoE2:DE matchup scenario → run it in-game →
record → OCR the result → produce a titled matchup video. Built on Windows;
this doc gets it running on the **Mac native AoE2:DE** for the recording phase.

## What's here
- `make_scenario.py` — parameterized scenario generator. Current design: **AI vs AI +
  spectator** — army1→Player 2 (AI), army2→Player 3 (AI), Player 1 = human spectator
  who owns the arena walls and is **allied to both** (just watches/records; never
  "defeated"). Triggers: cinematic title + 3-2-1 countdown, force-engage, full-upgrade
  research, **looping live on-screen survivor readout**, and "ArmyX wiped → other wins"
  end conditions. Demo: `build_matchup_scenario(MatchupSpec(...))`.
- `overlay/` — video overlay pipeline:
  - `overlay_data.py` — pull stats/cost/upgrades/unique-techs from `webapp/aoe2_reference.db`.
  - `render_card.py` — site-themed intro + outro cards (HTML → headless Chrome → PNG).
  - `hud.py` — Pillow live HUD strip (survivor counts + HP bars).
  - `results.py` — sim-based results timeline (position-based engine).
  - `video_extract.py` — OCR survivor counts off a recording (rapidocr) → MatchResult.
  - `compose.py` — ffmpeg: intro → fight+liveHUD → outro.

## Mac install
```bash
git clone <repo> && cd aoe2-unit-analyzer
pip install AoE2ScenarioParser rapidocr-onnxruntime pillow opencv-python-headless
brew install ffmpeg
# OCR alt (lighter on numpy): brew install tesseract && pip install pytesseract
# Chrome for card rendering: install Google Chrome (or Chromium) into /Applications
```
Code is already cross-platform: `hud.py` font map and `render_card.py` browser paths
include macOS locations; `ffmpeg` is found via PATH.

## Mac-specific paths to find/confirm (do this first on the Mac)
- **Scenario folder** (drop generated `.aoe2scenario` here so it shows in-game):
  search for it — likely under `~/Library/Application Support/...` or a Steam
  userdata path. `find ~ -name '*.aoe2scenario' 2>/dev/null` to locate it, then point
  `build_matchup_scenario` output there (or copy after generating).
- **Launch the game:** `open "steam://rungameid/813780"` (same Steam app id as Windows).

## Recording on Mac (the reason we switched)
macOS captures Metal games reliably (no Windows exclusive-fullscreen black-screen issue).
List capture devices, then record:
```bash
ffmpeg -f avfoundation -list_devices true -i ""        # find the screen device index
ffmpeg -f avfoundation -framerate 30 -i "<screen_idx>" -c:v libx264 -preset ultrafast \
       -pix_fmt yuv420p battle.mkv
```
**Record to `.mkv` (or stop ffmpeg gracefully by sending `q`), NOT mp4 hard-killed** —
on Windows we lost a recording to a missing `moov` atom when force-killing an `.mp4`.

## Run flow (on Mac)
1. Generate (or reuse) the scenario; copy it into the Mac scenario folder.
2. Launch AoE2:DE → **Editors → Scenario Editor → Load Scenario** → pick it →
   **Menu (top-right) → Test**. (Skirmish/custom-scenario path also works.)
3. Start the `.mkv` screen recording as the test begins.
4. Watch the looping top-center readout ("Army1: N vs Army2: M"); the game ends via the
   "wiped → wins" trigger to a clean result screen.
5. `video_extract.extract_video_results(clip, roi_left=..., roi_right=...)` — **tune
   ROI_LEFT/ROI_RIGHT** to where the game draws the readout (one real frame is enough).
6. `compose.make_matchup_video(result, u1, u2, out, battle_clip=clip)`.

## Key finding from the Windows spike (Fire Archer vs Jian, Wu, 30v30)
Real game: **Jian Swordsmen dominate** (last readout 4 Fire Archer vs 22 Jian, then Fire
Archers wiped). This **contradicts the position-based sim** (`simulation_real.py`, used by
the matchup table), which predicted Fire Archers 30-0 in some runs and Jian in others —
i.e. it's **unstable/wrong for this matchup** (overrates Fire Archer blast vs Jian's 9
pierce armor + bonus-vs-archer). The abstract `simulation.py` got the winner right (Jian).
Ground-truthing matchups like this is the whole point of the pipeline.
