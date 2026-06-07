# auto/ — hands-off matchup-video automation

Turn an AoE2:DE fight scenario into a titled matchup video with **one command**:
navigate the Scenario Editor, record the fight, detect the real game-end, stop,
OCR the survivors, compose (intro card → fight + live HUD + audio → outro card),
and copy the result out. The "stage" is checked by **screenshot processing**, not a
human watching — and scenario selection needs **no search** (option B, below).

Verified end-to-end: one Terminal command → finished video in Orchid, ~6 min,
zero interaction.

---

## The run, step by step

```
orchestrate_matchup.py
  1. stage_single_scenario()   keep ONLY the target .aoe2scenario in the game's
                               scenario folder; move the rest to _archive/
  2. bring_game_to_front()     activate AoE2, wait until a known screen shows
  3. navigate_to_test_menu()   Load → click the ONE list row → Load → editor → Menu
                               (no search box — the list has a single entry)
  4. start_recorder()          SCK recorder: video + system audio, 1920x1248@60
  5. click Test                fight begins; recorder captures from the countdown
  6. watch_until_end()         poll the screen; detect the "defeated" banner = end
  7. stop_recorder()           SIGINT → the .mov finalizes exactly at the end
  8. ocr_and_compose()         OCR survivors+window → trim → cards+HUD+audio video
  9. copy → --copy-to          drop the finished mp4 in the target folder
```

Each click locates its button by **label text** (`vision.find_text`), so coordinates
adapt to resolution; only the end-detection is adaptive (fights vary in length).

## Modules

- **`vision.py`** — `screencapture` + rapidocr (Screen-Recording-only; runs from any
  host). `detect_state()` (which screen), `detect_end()` (game-over banner),
  `read_counts()` (live readout), `find_text(img, label, region)` → the button's
  **logical point** (screencapture is Retina 2×, so point = pixel ÷ `SCALE`=2).
- **`input_driver.py`** — cliclick wrappers. `click()` is the game-safe pattern
  (move → settle → discrete down/up; a warp+click is dropped by the engine).
  `accessibility_ok()` checks the input-injection grant.
- **`record_until_end.py`** — the autonomous **back half** (no input injection, so it
  runs from anywhere with just Screen Recording). `start_recorder` /
  `watch_until_end` / `stop_recorder` / `ocr_and_compose`. Run it on its own after
  you click Test yourself:
  ```
  python -m auto.record_until_end <civ1> <slug1> <civ2> <slug2> \
      --copy-to DIR --name OUT.mp4 --log /tmp/auto_matchup.log
  ```
- **`orchestrate_matchup.py`** — the full kick-off **macro** (navigation + back half).

## Run the full macro

```
python -m auto.orchestrate_matchup <civ1> <slug1> <civ2> <slug2> \
    --scenario MATCHUP_jungle_fight \
    --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos" \
    --name "Elite Fire Archer vs Jian Swordsman (Wu, 30v30).mp4"
```

Progress → stdout and `--log` (default `/tmp/auto_matchup.log`); `tail -f` it to watch.

### Prerequisites (one-time)

Run from a **Terminal** (Terminal.app or iTerm) that has BOTH, in System Settings →
Privacy & Security:
- **Screen Recording** — for `screencapture` + the SCK recorder, and
- **Accessibility** — for scripted clicks via cliclick. *Separate from Screen
  Recording; the latter does NOT cover input injection.*

TCC is read at process **launch** — **restart the Terminal** after enabling either.
Leave AoE2:DE in the **Scenario Editor or its main menu** (not on an already-open
Load page, so the macro opens the Load list fresh).

## Option B — dedicated scenario folder, no search

The Load dialog's search box keeps its **previous query** and has **no select-all**,
so typing a name again appends to the stale text → zero results. Rather than fight
that, the macro **dedicates the folder**: `stage_single_scenario()` keeps exactly the
target `.aoe2scenario` and moves every other one into `_archive/` (recoverable, and
auto-restored when a different `--scenario` is requested). The Load list then shows a
single entry — the macro just clicks it. No search, no typing, no stale-query bug,
and faster.

`SCEN_DIR` (in `orchestrate_matchup.py`) points at the Feral VFS scenario folder.

## Adding a new matchup

1. Pre-generate the fight scenario so the file exists in the folder, e.g.
   `python make_showcase.py --fight` (writes `MATCHUP_<theme>_fight`), or a custom
   `make_scenario.py` spec.
2. Run the macro with `--scenario <that name>`, the two `<civ> <slug>` pairs, and a
   descriptive `--name` for the output video. (The descriptive identity lives in the
   output filename; the scenario file name is just the staging key.)

## Notes / limitations

- **Whole-display capture:** video is the full screen and audio is the full system
  mix. During a run, don't switch apps or play other sounds — they'd appear in the
  video / audio. (A future upgrade: ScreenCaptureKit per-window + per-app audio so
  you could multitask.)
- **OCR is the slow part** (~3.5 min of the ~6 min total) — it samples the recording
  frame-by-frame to read the survivor timeline.
- Cosmetic: the outro subtitle still reads "Position-based sim …" (a one-line fix in
  `overlay/render_card.py` + re-render).
- The recorder is built at `../recorder/sck_record` (run `../recorder/build.sh`).
