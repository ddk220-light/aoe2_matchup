"""orchestrate_matchup.py — full kick-off MACRO for a matchup video.

One command: navigate the Scenario Editor (deterministic clicks, scenario picked
by typing its exact name into Search) -> start recording -> Test -> watch for the
real game-end -> stop -> OCR -> compose titled video (with audio) -> copy out.

PREREQUISITES (one-time): run from a Terminal that has BOTH
  * Screen Recording   (for screencapture + the SCK recorder), and
  * Accessibility       (for scripted clicks via cliclick)
in System Settings -> Privacy & Security. Leave AoE2:DE open in the Scenario
Editor, frontmost, with any scenario loaded.

  python -m auto.orchestrate_matchup <civ1> <slug1> <civ2> <slug2> \
      --scenario MATCHUP_jungle_fight \
      --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos" \
      --name "Fire Archer vs Jian.mp4"

The navigation is a fixed sequence; buttons are located by their label text (so
coordinates adapt to resolution) but NOT state-gated between steps — just clicked
one after another, exactly as a macro. Only the end-detection stays adaptive.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AOE2_BUNDLE = "com.feralinteractive.ageofempires2"


def bring_game_to_front(logfile=None, settle=2.0):
    """Activate AoE2:DE so the scripted clicks land on it (the launching Terminal is
    frontmost right after you press Enter)."""
    subprocess.run(["open", "-b", AOE2_BUNDLE], capture_output=True)
    time.sleep(settle)

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import vision, input_driver as ui          # noqa: E402
from auto.record_until_end import (                  # noqa: E402
    start_recorder, watch_until_end, stop_recorder, ocr_and_compose, log)

# search regions (fractional) to disambiguate repeated labels like "Load Scenario"
R_MENU_BTN = (0.85, 0.0, 1.0, 0.10)      # top-right "Menu"
R_DIALOG = (0.33, 0.38, 0.67, 0.78)      # menu-dialog buttons (Load/Test/...)
R_SAVE = (0.30, 0.50, 0.70, 0.66)        # "No" on the save prompt
R_SEARCH = (0.10, 0.25, 0.42, 0.34)      # "Search" label
R_LIST = (0.12, 0.33, 0.60, 0.76)        # scenario list rows
R_LOAD_BTN = (0.38, 0.78, 0.62, 0.90)    # bottom "Load Scenario" button


def find_and_click(pattern, region, logfile, label=None, retries=4, dbl=False):
    """Grab screen, locate `pattern` in `region`, click it. Retries briefly if the
    screen hasn't settled yet. Returns True on success."""
    for i in range(retries):
        pt = vision.find_text(vision.grab(), pattern, region=region)
        if pt:
            (ui.double_click if dbl else ui.click)(pt)
            log(f"[nav] clicked {label or pattern!r} at {int(pt[0])},{int(pt[1])}", logfile)
            return True
        time.sleep(0.8)
    log(f"[nav] FAILED to find {label or pattern!r} in {region}", logfile)
    return False


def navigate_to_test_menu(scenario_name, logfile):
    """Editor -> Menu -> Load -> (No) -> search+pick scenario -> Load -> Menu.
    Leaves the Main Menu open with Test visible. Returns True on success."""
    # 1) open the editor Menu (top-right; often needs two presses)
    if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
        return False
    time.sleep(0.8)
    # 2) Load Scenario (menu dialog)
    if not find_and_click("Load Scenario", R_DIALOG, logfile, "Load Scenario (menu)"):
        return False
    time.sleep(1.0)
    # 3) save-changes prompt? click No (skip silently if absent)
    if vision.detect_state(vision.grab()) == "save_dialog":
        find_and_click("No", R_SAVE, logfile, "No (save prompt)")
        time.sleep(1.0)
    # 4) focus Search (click just right of the label) and type the exact name
    s = vision.find_text(vision.grab(), "Search", region=R_SEARCH)
    if not s:
        log("[nav] FAILED to find Search field", logfile)
        return False
    ui.click((s[0] + 130, s[1]))           # into the field
    log(f"[nav] focus Search; typing {scenario_name!r}", logfile)
    ui.type_text(scenario_name)
    time.sleep(1.0)
    # 5) click the matching row (search filters the list to it)
    if not find_and_click(scenario_name, R_LIST, logfile, f"row {scenario_name!r}"):
        return False
    time.sleep(0.5)
    # 6) Load Scenario (bottom button)
    if not find_and_click("Load Scenario", R_LOAD_BTN, logfile, "Load Scenario (button)"):
        return False
    time.sleep(2.5)                        # editor loads the scenario
    # 7) open Menu again, ready for Test
    if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
        return False
    time.sleep(0.8)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("civ1"); ap.add_argument("slug1")
    ap.add_argument("civ2"); ap.add_argument("slug2")
    ap.add_argument("--scenario", required=True, help="exact scenario name to load")
    ap.add_argument("--out-mov", default="/tmp/auto_fight.mov")
    ap.add_argument("--final", default="/tmp/auto_matchup_FINAL.mp4")
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--log", default="/tmp/auto_matchup.log")
    a = ap.parse_args()
    open(a.log, "w").close()
    log(f"=== orchestrate {a.slug1} vs {a.slug2} on {a.scenario} ===", a.log)

    if not ui.accessibility_ok():
        log("ERROR: Accessibility not granted to this terminal — scripted clicks "
            "will fail. System Settings -> Privacy & Security -> Accessibility.", a.log)
        sys.exit(2)

    # bring AoE2 to the front (the Terminal is frontmost after you press Enter)
    log("[nav] bringing AoE2:DE to the front...", a.log)
    bring_game_to_front(a.log)
    st = vision.detect_state(vision.grab())
    log(f"[nav] starting screen: {st}", a.log)

    # NAVIGATE (deterministic macro)
    if not navigate_to_test_menu(a.scenario, a.log):
        log("ERROR: navigation failed — aborting before recording.", a.log)
        sys.exit(1)

    # RECORD: start recorder, then click Test so the fight is captured from the start
    rec = start_recorder(a.out_mov, a.cap, logfile=a.log)
    if not find_and_click("Test", R_DIALOG, a.log, "Test"):
        stop_recorder(rec, a.out_mov, a.log)
        log("ERROR: could not click Test — aborting.", a.log)
        sys.exit(1)
    t0 = time.time()

    # WATCH -> STOP -> COMPOSE -> COPY
    watch_until_end(t0, a.cap, logfile=a.log)
    stop_recorder(rec, a.out_mov, a.log)
    final = ocr_and_compose(a.civ1, a.slug1, a.civ2, a.slug2, a.out_mov, a.final,
                            a.copy_to, a.name, a.log)
    log(f"DONE -> {final}", a.log)


if __name__ == "__main__":
    main()
