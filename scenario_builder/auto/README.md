# auto/ — hands-off matchup-video automation

Turn an AoE2:DE fight scenario into a titled matchup video with one command:
navigate the editor, record the fight, detect the real game-end, stop, OCR the
survivors, compose (intro card -> fight + live HUD + audio -> outro card), and
copy the result out. "Check the stage through screenshot processing" — no human
eyeballing.

## Pieces

- **`vision.py`** — `screencapture` + rapidocr. `detect_state()` (which screen),
  `detect_end()` (game-over banner), `read_counts()` (live readout), `find_text()`
  (locate a button by label -> logical point for clicking). Uses only the Screen
  Recording grant; runs from any host.
- **`record_until_end.py`** — the autonomous back half. Start recorder -> watch for
  the end banner -> stop (graceful finalize) -> OCR -> compose -> copy. No input
  injection, so it works from anywhere. Run it yourself after clicking Test:
  ```
  python -m auto.record_until_end <civ1> <slug1> <civ2> <slug2> \
      --copy-to DIR --name OUT.mp4 --log /tmp/auto_matchup.log
  ```
- **`input_driver.py`** — cliclick wrappers (game-safe move->settle->down/up).
  Needs Accessibility.
- **`orchestrate_matchup.py`** — the full kick-off MACRO (navigation + back half).

## Full macro (one command)

```
python -m auto.orchestrate_matchup <civ1> <slug1> <civ2> <slug2> \
    --scenario MATCHUP_jungle_fight \
    --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos" \
    --name "Fire Archer vs Jian.mp4"
```

The navigation is a fixed sequence — Menu -> Load -> (No) -> Search+type the EXACT
scenario name -> click the matched row -> Load -> Menu -> (record) -> Test — buttons
located by label so it's resolution-robust. Only end-detection stays adaptive.

### Prerequisites (one-time)

Run from a **Terminal** that has BOTH permissions in System Settings ->
Privacy & Security:
- **Screen Recording** (screencapture + the SCK recorder), and
- **Accessibility** (scripted clicks via cliclick — the Screen Recording grant does
  NOT cover input injection).

TCC is read at process launch, so **restart the Terminal** after enabling either.
Leave AoE2:DE open in the Scenario Editor, frontmost, with any scenario loaded.

Progress is logged to `--log` (default `/tmp/auto_matchup.log`); tail it to watch.
