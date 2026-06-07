"""orchestrate_matchup.py — full kick-off MACRO for a matchup video.

One command: stage the scenario folder to a single file -> navigate the Scenario
Editor (deterministic clicks; the Load list has ONE entry so no search/typing) ->
start recording -> Test -> watch for the real game-end -> stop -> OCR -> compose
titled video (with audio) -> copy out.

OPTION B (dedicated folder): the AoE2 scenario folder is kept holding exactly the
target scenario (others moved to _archive/, recoverable), so the macro never has
to use the Load search box — which keeps a stale query and has no select-all.

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
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AOE2_BUNDLE = "com.feralinteractive.ageofempires2"

# The AoE2:DE scenario folder, DEDICATED to these simulations (option B): the macro
# keeps exactly the target scenario here so the Load list has a single entry and no
# search/typing is needed. Everything else is moved aside into _archive/ (recoverable).
SCEN_DIR = Path(
    "/Users/deepak/Library/Application Support/Feral Interactive/Age Of Empires II/"
    "VFS/User/Games/Age of Empires 2 DE/76561198053842894/resources/_common/scenario"
)


def stage_single_scenario(target, scen_dir=SCEN_DIR, archive="_archive", logfile=None):
    """Make `target` the SOLE .aoe2scenario in scen_dir (recovering it from the
    archive if needed); move every other scenario into scen_dir/<archive>/. Returns
    the target's display name. So the Load list shows just this one entry."""
    scen = Path(scen_dir)
    arch = scen / archive
    arch.mkdir(exist_ok=True)
    fname = target if target.endswith(".aoe2scenario") else target + ".aoe2scenario"
    # recover the target from the archive if it was moved out by a prior run
    if not (scen / fname).exists() and (arch / fname).exists():
        shutil.move(str(arch / fname), str(scen / fname))
    if not (scen / fname).exists():
        raise FileNotFoundError(f"target scenario {fname!r} not in {scen} or {arch}")
    moved = 0
    for f in scen.glob("*.aoe2scenario"):
        if f.name != fname:
            shutil.move(str(f), str(arch / f.name))
            moved += 1
    log(f"[stage] {fname} is the sole scenario; archived {moved} other(s) -> {arch.name}/",
        logfile)
    return fname[: -len(".aoe2scenario")]


def bring_game_to_front(logfile=None, timeout=8.0):
    """Activate AoE2:DE so the scripted clicks land on it (the launching Terminal is
    frontmost right after you press Enter), then wait until a known game screen is
    actually showing. Returns the detected state."""
    subprocess.run(["open", "-b", AOE2_BUNDLE], capture_output=True)
    t0 = time.time()
    st = "unknown"
    while time.time() - t0 < timeout:
        time.sleep(0.6)
        st = vision.detect_state(vision.grab())
        if st in ("editor", "load_dialog", "main_menu", "end_screen"):
            break
    return st

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


def find_with_retry(pattern, region, logfile, retries=6, delay=0.8):
    """Locate `pattern` (no click), retrying while the screen settles. Point or None."""
    for _ in range(retries):
        pt = vision.find_text(vision.grab(), pattern, region=region)
        if pt:
            return pt
        time.sleep(delay)
    return None


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


def _reach_load_page(state, logfile):
    """From `state` (editor / main_menu / load_dialog), get to the Load Scenario
    page. Returns True when on (or assumed on) the load page."""
    if state == "load_dialog":
        return True
    if state == "editor":
        if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
            return False
        time.sleep(0.8)
        state = "main_menu"
    if state == "main_menu":
        if not find_and_click("Load Scenario", R_DIALOG, logfile, "Load Scenario (menu)"):
            return False
        time.sleep(1.0)
        if vision.detect_state(vision.grab()) == "save_dialog":
            find_and_click("No", R_SAVE, logfile, "No (save prompt)")
            time.sleep(1.0)
        return True
    log(f"[nav] don't know how to reach load page from {state}", logfile)
    return False


def navigate_to_test_menu(start_state, scenario_name, logfile):
    """From the Load Scenario page (reached from `start_state`): the folder is staged
    to a SINGLE scenario (option B), so just click that one row -> Load -> editor ->
    Menu. NO search/typing (the Load search box keeps its previous query and has no
    select-all, so we avoid it entirely). Leaves the Main Menu open with Test visible."""
    if not _reach_load_page(start_state, logfile):
        return False
    time.sleep(1.0)                        # let the load page finish rendering
    # the list has one entry — click it directly (no search needed)
    if not find_and_click(scenario_name, R_LIST, logfile, f"row {scenario_name!r}"):
        return False
    time.sleep(0.5)
    # Load Scenario (bottom button)
    if not find_and_click("Load Scenario", R_LOAD_BTN, logfile, "Load Scenario (button)"):
        return False
    time.sleep(2.5)                        # editor loads the scenario
    # open Menu again, ready for Test
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

    # OPTION B: dedicate the scenario folder to one file so the Load list shows a
    # single entry (no search). Recover/keep the target, archive everything else.
    try:
        a.scenario = stage_single_scenario(a.scenario, logfile=a.log)
    except Exception as e:
        log(f"ERROR: could not stage scenario: {e}", a.log)
        sys.exit(1)

    # bring AoE2 to the front (the Terminal is frontmost after you press Enter)
    log("[nav] bringing AoE2:DE to the front...", a.log)
    st = bring_game_to_front(a.log)
    log(f"[nav] starting screen: {st}", a.log)
    if st not in ("editor", "main_menu", "load_dialog"):
        log(f"[nav] ERROR: unexpected starting screen {st!r}; open AoE2 in the "
            "Scenario Editor (or its Load Scenario page) and try again.", a.log)
        sys.exit(1)

    # NAVIGATE (deterministic macro) — works from the editor OR the load page
    if not navigate_to_test_menu(st, a.scenario, a.log):
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
