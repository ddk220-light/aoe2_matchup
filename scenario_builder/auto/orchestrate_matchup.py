"""orchestrate_matchup.py — one-command MACRO for a matchup video.

Template-based, no-OCR pipeline. Given two `civ slug` pairs it:

  1. build_run     generate the run scenario from the golden jungle template
                   (swap units + civs, retarget triggers, add force-engage,
                   NO tech research) -> /tmp/aoe2_matchup_runs/
  2. stage         clear the game's scenario folder and drop in that ONE file
                   (named "Matchup Run") so the Load list has a single entry
  3. navigate      Load -> click the one row -> Load -> editor -> Menu (no search)
  4. record        SCK recorder: video + system audio, 1920x1248@60
  5. Test          fight begins; recorder captures from the countdown
  6. watch         poll the screen; the end-of-game banner = the fight is over
  7. stop          SIGINT -> the .mov finalizes at the end
  8. compose       intro stat card -> real fight (+audio) -> recap card  (NO OCR,
                   no survivor counts — see build_run.py / the recap design)
  9. copy          drop the finished mp4 in --copy-to

The scenario folder is DEDICATED to these runs: it holds exactly the staged file
(so no search is needed). The golden template lives in the git repo
(templates/template_landscape_jungle.aoe2scenario); generated runs live in /tmp.

PREREQUISITES (one-time): run from a Terminal that has BOTH Screen Recording and
Accessibility (System Settings -> Privacy & Security). Leave AoE2:DE open in the
Scenario Editor (or its Load page), frontmost.

  python -m auto.orchestrate_matchup Muisca elite_temple_guard_muisca \
      Aztecs elite_jaguar_warrior_aztecs \
      --name "Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs).mp4" \
      --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos"
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AOE2_BUNDLE = "com.feralinteractive.ageofempires2"

# The AoE2:DE scenario folder, DEDICATED to these runs. The macro keeps exactly the
# staged run scenario here so the Load list has a single entry (no search/typing).
SCEN_DIR = Path(
    "/Users/deepak/Library/Application Support/Feral Interactive/Age Of Empires II/"
    "VFS/User/Games/Age of Empires 2 DE/76561198053842894/resources/_common/scenario"
)
RUN_DIR = Path("/tmp/aoe2_matchup_runs")        # generated scenarios (pre-stage)
STAGE_NAME = "Matchup Run"                       # fixed name shown in the Load list
LEAD_PAD = 3.0                                    # extra trim past Test-click (load+countdown)

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto import vision, input_driver as ui          # noqa: E402
from auto.record_until_end import (                   # noqa: E402
    start_recorder, watch_until_end, stop_recorder, compose_recap, log)
from build_run import build_run                       # noqa: E402

# search regions (fractional) to disambiguate repeated labels
R_MENU_BTN = (0.85, 0.0, 1.0, 0.10)      # top-right "Menu"
R_DIALOG = (0.33, 0.38, 0.67, 0.78)      # menu-dialog buttons (Load/Test/...)
R_SAVE = (0.30, 0.50, 0.70, 0.66)        # "No" on the save prompt
R_LIST = (0.12, 0.33, 0.60, 0.76)        # scenario list rows
R_LOAD_BTN = (0.38, 0.78, 0.62, 0.90)    # bottom "Load Scenario" button
R_CONTINUE = (0.30, 0.56, 0.70, 0.76)    # "Continue" on the end-of-game banner


def resolve_side(civ: str, slug: str):
    """(civ, slug) -> (civ, unit_key, display_label) for build_run.

    The scenario unit key is the slug minus its civ suffix (unique-unit slugs carry
    one, e.g. 'elite_temple_guard_muisca' -> 'elite_temple_guard'); the label is the
    unit's display name from the reference DB."""
    from overlay_data import get_unit_card
    suffix = "_" + civ.lower()
    key = slug[: -len(suffix)] if slug.endswith(suffix) else slug
    label = get_unit_card(civ, slug)["name"]
    return (civ, key, label)


def stage_generated(src, scen_dir=SCEN_DIR, stage_name=STAGE_NAME, logfile=None) -> str:
    """Clear the game's scenario folder and copy `src` in as the SOLE entry (named
    `stage_name`), so the Load list shows one row. Returns the display name."""
    scen = Path(scen_dir)
    scen.mkdir(parents=True, exist_ok=True)
    for f in scen.glob("*.aoe2scenario"):
        f.unlink()
    dest = scen / f"{stage_name}.aoe2scenario"
    shutil.copy2(str(src), str(dest))
    log(f"[stage] '{stage_name}' is the sole scenario in the game folder", logfile)
    return stage_name


def bring_game_to_front(logfile=None, timeout=8.0) -> str:
    """Activate AoE2:DE and wait until a known game screen shows. Returns the state."""
    subprocess.run(["open", "-b", AOE2_BUNDLE], capture_output=True)
    t0 = time.time()
    st = "unknown"
    while time.time() - t0 < timeout:
        time.sleep(0.6)
        st = vision.detect_state(vision.grab())
        if st in ("editor", "load_dialog", "main_menu", "end_screen"):
            break
    return st


def find_and_click(pattern, region, logfile, label=None, retries=4, dbl=False) -> bool:
    """Locate `pattern` in `region` and click it; retry briefly while the screen settles."""
    for _ in range(retries):
        pt = vision.find_text(vision.grab(), pattern, region=region)
        if pt:
            (ui.double_click if dbl else ui.click)(pt)
            log(f"[nav] clicked {label or pattern!r} at {int(pt[0])},{int(pt[1])}", logfile)
            return True
        time.sleep(0.8)
    log(f"[nav] FAILED to find {label or pattern!r} in {region}", logfile)
    return False


def _reach_load_page(state, logfile) -> bool:
    """From editor / main_menu / load_dialog, get to the Load Scenario page."""
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


def navigate_to_test_menu(start_state, scenario_name, logfile) -> bool:
    """Load page -> click the ONE list row -> Load -> editor -> Menu. No search."""
    if not _reach_load_page(start_state, logfile):
        return False
    time.sleep(1.0)
    if not find_and_click(scenario_name, R_LIST, logfile, f"row {scenario_name!r}"):
        # the staged file is named "Matchup Run" — try the first word as a fallback
        if not find_and_click(scenario_name.split()[0], R_LIST, logfile, "row (first word)"):
            return False
    time.sleep(0.5)
    if not find_and_click("Load Scenario", R_LOAD_BTN, logfile, "Load Scenario (button)"):
        return False
    time.sleep(2.5)
    if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
        return False
    time.sleep(0.8)
    return True


def return_to_editor(logfile, retries=8) -> bool:
    """After a fight ends, dismiss the end-of-game banner back to the Scenario
    Editor so the game is clean for the NEXT run. The 'You have been defeated!'
    screen has a single 'Continue' button -> clicking it returns DIRECTLY to the
    editor (no intermediate stats screen). Idempotent: returns True once the editor
    tabs are visible."""
    for _ in range(retries):
        img = vision.grab()
        if vision.detect_state(img) == "editor":
            log("[end] back in the Scenario Editor — clean for the next run", logfile)
            return True
        pt = vision.find_text(img, "Continue", region=R_CONTINUE)
        if pt:
            ui.click(pt)
            log(f"[end] clicked Continue at {int(pt[0])},{int(pt[1])}", logfile)
            time.sleep(2.5)
        else:
            time.sleep(1.0)
    ok = vision.detect_state(vision.grab()) == "editor"
    log(f"[end] {'in editor' if ok else 'WARNING: editor not confirmed'}", logfile)
    return ok


def run_matchup(civ1, slug1, civ2, slug2, *, name=None, copy_to=None, cap=240,
                out_mov="/tmp/auto_fight.mov", final="/tmp/auto_matchup_FINAL.mp4",
                dismiss_after=True, logfile=None) -> Path:
    """One full matchup: build from template -> stage -> navigate -> record -> Test
    -> watch for end -> stop -> (dismiss to editor) -> compose recap -> copy.
    Returns the final video Path. Designed to be called repeatedly for a batch."""
    # 1. BUILD the run scenario from the golden template (swap units/civs, no tech)
    side1 = resolve_side(civ1, slug1)
    side2 = resolve_side(civ2, slug2)
    run_path = RUN_DIR / f"{side1[1]}_vs_{side2[1]}.aoe2scenario"
    build_run(side1, side2, run_path)
    log(f"[build] {side1[2]} ({civ1}) vs {side2[2]} ({civ2}) -> {run_path}", logfile)

    # 2. STAGE it as the sole scenario in the game folder
    scen_name = stage_generated(run_path, logfile=logfile)

    # 3. bring AoE2 to the front; if a previous fight left an end banner up, clear it
    log("[nav] bringing AoE2:DE to the front...", logfile)
    st = bring_game_to_front(logfile)
    if st == "end_screen":
        return_to_editor(logfile)
        st = bring_game_to_front(logfile)
    log(f"[nav] starting screen: {st}", logfile)
    if st not in ("editor", "main_menu", "load_dialog"):
        raise RuntimeError(f"unexpected starting screen {st!r}")
    if not navigate_to_test_menu(st, scen_name, logfile):
        raise RuntimeError("navigation failed")

    # 4-7. RECORD -> Test -> watch for the end banner. Whatever happens, ALWAYS stop
    # the recorder and (try to) dismiss back to the editor, so one bad run can't leave
    # a recorder orphaned or the game stuck for the next matchup.
    rec = start_recorder(out_mov, cap, logfile=logfile)
    t_rec = time.time()
    t_test = None
    try:
        if not find_and_click("Test", R_DIALOG, logfile, "Test"):
            raise RuntimeError("could not click Test")
        t_test = time.time()
        watch_until_end(t_test, cap, logfile=logfile)
    finally:
        stop_recorder(rec, out_mov, logfile)
        if dismiss_after:
            return_to_editor(logfile)

    # recording sanity: an empty/tiny .mov means the capture failed (Screen Recording
    # grant missing, or the recorder never started) — fail loudly, don't compose black.
    sz = os.path.getsize(out_mov) if os.path.exists(out_mov) else 0
    if sz < 1_000_000:
        raise RuntimeError(f"recording looks empty ({sz} bytes) — is Screen Recording "
                           "granted to this terminal, and the recorder built?")

    # 8-9. COMPOSE (recap, no OCR) -> COPY. Trim the menu/load lead-in off the front.
    lead_in = max(0.0, (t_test - t_rec) + LEAD_PAD)
    return compose_recap(civ1, slug1, civ2, slug2, out_mov, final,
                         copy_to, name, lead_in=lead_in, logfile=logfile)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("civ1"); ap.add_argument("slug1")
    ap.add_argument("civ2"); ap.add_argument("slug2")
    ap.add_argument("--out-mov", default="/tmp/auto_fight.mov")
    ap.add_argument("--final", default="/tmp/auto_matchup_FINAL.mp4")
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--log", default="/tmp/auto_matchup.log")
    a = ap.parse_args()
    open(a.log, "w").close()
    log(f"=== orchestrate {a.slug1} vs {a.slug2} (template-based, no OCR) ===", a.log)

    if not ui.accessibility_ok():
        log("ERROR: Accessibility not granted to this terminal — scripted clicks will "
            "fail. System Settings -> Privacy & Security -> Accessibility.", a.log)
        sys.exit(2)
    try:
        final = run_matchup(a.civ1, a.slug1, a.civ2, a.slug2, name=a.name,
                            copy_to=a.copy_to, cap=a.cap, out_mov=a.out_mov,
                            final=a.final, logfile=a.log)
    except Exception as e:
        log(f"ERROR: {e}", a.log)
        sys.exit(1)
    log(f"DONE -> {final}", a.log)


if __name__ == "__main__":
    main()
