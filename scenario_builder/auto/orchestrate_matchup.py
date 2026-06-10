"""orchestrate_matchup.py — one-command MACRO for a matchup video (Windows).

Template-based pipeline. Given two `civ slug` pairs it:

  1. build_run     generate the run scenario from the golden template
                   (templates/new_template.aoe2scenario: swap units + civs,
                   retarget triggers, NO tech research) -> %TEMP%/aoe2_matchup_runs/
  2. stage         copy it into the game's scenario folder as "Matchup Run"
                   (non-destructive; freshly written, so it tops the Load list)
  3. navigate      fixed-coordinate fast path with cheap OCR gates (OCR fallback):
                   editor -> Menu -> Load -> row -> Load -> editor -> Menu
  4. record        ffmpeg ddagrab + h264_nvenc at native res (gdigrab/libx264
                   fallback), game audio via the dshow loopback device
  5. Test          fight begins; recorder captures from the countdown
  6. watch         change-gated OCR poll for the win trigger's "<unit> WINS!" hold
  7. stop          'q' to ffmpeg -> the recording finalizes
  8. compose       single-pass live overlay: top army-HP bar + unit detail cards
                   over the real fight (+audio), speed-ramped, ends after the win
                   (or --record-only style: run_matchup(compose=False) archives the
                   raw + sidecars for a later parallel recompose_from_raws)
  9. copy          drop the finished mp4 (+ .hp.json sidecar) in --copy-to

The gRPC HP logger runs alongside the fight for the overlay's true-HP timeline; the
clip itself is cut from the frame-accurate game-start detected in the footage.

PREREQUISITES: AoE2:DE open in the Scenario Editor (or its Load page), frontmost,
fullscreen on the primary display. See README_WINDOWS.md for setup + env vars.

  python -m auto.orchestrate_matchup Muisca elite_temple_guard_muisca \
      Aztecs elite_jaguar_warrior_aztecs \
      --name "Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs).mp4" \
      --copy-to "%USERPROFILE%/Videos/aoe2_matchups"
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import vision, input_driver as ui, platform_io, grpc_capture   # noqa: E402
from auto.record_until_end import (                   # noqa: E402
    start_recorder, watch_until_result, stop_recorder, compose_recap,
    compose_live_overlay, archive_raw, log)
from build_run import build_run                       # noqa: E402

# The AoE2:DE scenario folder, DEDICATED to these runs (OS-specific; see platform_io).
# The macro keeps exactly the staged run scenario here so the Load list has one entry.
SCEN_DIR = platform_io.scenario_dir()
TMP = platform_io.TMP_DIR                         # /tmp on mac, %TEMP% on windows
RUN_DIR = Path(TMP) / "aoe2_matchup_runs"        # generated scenarios (pre-stage)
STAGE_NAME = "Matchup Run"                       # fixed name shown in the Load list

RESULT_HOLD = 5.0                                      # seconds to hold the result on screen
PATROL_LEAD_WALLCLOCK = 3.5    # FALLBACK clip-start offset after the WALL-CLOCK game-start
#   Used only when the composer can't frame-accurately detect game-start in the footage
#   (record_until_end.detect_game_start, whose own PATROL_LEAD=1.0 then applies instead —
#   the two offsets differ because their reference points differ: the wall-clock game-start
#   is detected by a slow OCR poll that lags the real start by a few seconds, while the
#   footage scan pins the exact frame). At game-start the camera spends ~2s panning to the
#   arena; the armies patrol in at game-time ~4s; 3.5s after the (late) OCR-detected start
#   lands on the charge.

# search regions (fractional) to disambiguate repeated labels
R_MENU_BTN = (0.85, 0.0, 1.0, 0.10)      # top-right "Menu"
R_DIALOG = (0.33, 0.38, 0.67, 0.78)      # menu-dialog buttons (Load/Test/...)
R_SAVE = (0.30, 0.50, 0.70, 0.66)        # "No" on the save prompt
R_LIST = (0.12, 0.33, 0.60, 0.76)        # scenario list rows
R_LOAD_BTN = (0.38, 0.78, 0.62, 0.90)    # bottom "Load Scenario" button
R_CONTINUE = (0.30, 0.56, 0.70, 0.76)    # "Continue" on the (legacy) defeat banner
R_GAME_MENU = (0.28, 0.24, 0.72, 0.74)   # quit/return option in the in-game F10 menu
R_CONFIRM = (0.28, 0.48, 0.72, 0.62)     # Yes/No confirm dialog

# Fixed click points (fraction of screen). The editor/menu UI is DETERMINISTIC at a given
# resolution, so the fast nav clicks these directly and only falls back to OCR if a cheap
# checkpoint says the expected screen didn't appear. Captured at 2560x1440 (the logged
# click coords are identical every run): Menu 2447,28 · Load(menu) 1280,715 · row 503,544
# · Load(btn) 1270,1235 · Test 1281,829.
FP_MENU = (0.9559, 0.0195)               # top-right "Menu" (editor & in-game share it)
FP_LOAD_MENU = (0.5000, 0.4965)          # "Load Scenario" row in the menu dialog
FP_TEST = (0.5004, 0.5757)               # "Test" row in the menu dialog
FP_ROW1 = (0.1965, 0.3778)               # the single staged scenario row on the Load page
FP_LOAD_BTN = (0.4961, 0.8576)           # "Load Scenario" button on the Load page
FP_SAVE_NO = (0.5731, 0.5542)            # "No" on the 'save your changes?' prompt (1467,798)


def resolve_side(civ: str, slug: str):
    """(civ, slug) -> (civ, unit_key, display_label) for build_run.

    The scenario unit key is the slug minus its civ suffix (unique-unit slugs carry
    one, e.g. 'elite_temple_guard_muisca' -> 'elite_temple_guard'); the label is the
    unit's display name from the reference DB."""
    from overlay.overlay_data import get_unit_card
    suffix = "_" + civ.lower()
    key = slug[: -len(suffix)] if slug.endswith(suffix) else slug
    label = get_unit_card(civ, slug)["name"]
    return (civ, key, label)


RES_BUDGET = 3000.0   # the cheaper side's total WEIGHTED cost must stay <= this


def equal_resource_counts(civ1, slug1, civ2, slug2, unit_cap=30):
    """Counts for an equal-RESOURCE fight. Per-unit costs come from the unit card,
    which already folds in civ cost bonuses (e.g. Mayan -30% archers), train
    batches (Blackwood Archers come 2 per train), and the website's resource
    weights (food 1.0 / wood 0.7 / gold 1.5 — webapp/simulation_real.py). The
    cheaper unit takes `unit_cap`, shrunk so its army never exceeds RES_BUDGET;
    the pricier unit's count is the largest that fits the same spend.
    Returns (n1, n2)."""
    from overlay.overlay_data import get_unit_card
    c1 = get_unit_card(civ1, slug1)["cost"]["weighted"] or 1
    c2 = get_unit_card(civ2, slug2)["cost"]["weighted"] or 1
    if c1 <= c2:                                   # side 1 cheaper -> it gets the cap
        n1 = max(1, min(unit_cap, int(RES_BUDGET // c1)))
        return n1, max(1, int(n1 * c1 // c2))
    n2 = max(1, min(unit_cap, int(RES_BUDGET // c2)))
    return max(1, int(n2 * c2 // c1)), n2


def stage_generated(src, scen_dir=SCEN_DIR, stage_name=STAGE_NAME, logfile=None) -> str:
    """Copy `src` into the game's scenario folder as `stage_name`. Freshly written, so it
    sorts to the TOP of the Load list by modified-time (navigation finds the row by name).
    NON-destructive: the user's own scenarios in the folder are left untouched. Returns
    the display name."""
    scen = Path(scen_dir)
    scen.mkdir(parents=True, exist_ok=True)
    dest = scen / f"{stage_name}.aoe2scenario"
    shutil.copy2(str(src), str(dest))
    log(f"[stage] '{stage_name}' written to the game folder (top of the Load list)", logfile)
    return stage_name


def bring_game_to_front(logfile=None, timeout=8.0) -> str:
    """Activate AoE2:DE and wait until a known game screen shows. Returns the state.

    Editor is the overwhelmingly common state between matchups, so we check it FIRST with a
    single cheap tabs-band OCR and return immediately — avoiding the full detect_state
    (~5 OCR calls, ~20s on CPU rapidocr). Only non-editor screens pay the full detect_state."""
    platform_io.bring_to_front()
    t0 = time.time()
    st = "unknown"
    while time.time() - t0 < timeout:
        time.sleep(0.4)
        img = vision.grab()
        if _in_editor(img):                  # fast path: one small-region OCR
            return "editor"
        st = vision.detect_state(img)
        if st in ("load_dialog", "main_menu", "end_screen", "in_game"):
            break
    return st


def _focus_game():
    """Re-assert AoE2:DE as the frontmost app so screenshots capture it and clicks land
    on it — even if another app (Terminal, Claude, a notification) grabbed focus."""
    platform_io.activate_game()
    time.sleep(0.4)


def _park_cursor(logfile=None):
    """Nudge the cursor off the (centered) battle but WELL INSIDE the screen. Parking it at
    a screen edge/corner triggers AoE2 edge-scrolling, which pans the camera off the fight —
    so aim for a lower-right INTERIOR point, away from the armies and nowhere near an edge."""
    img = vision.grab()
    x = int(0.85 * img.width / vision.SCALE)
    y = int(0.80 * img.height / vision.SCALE)
    platform_io.move(x, y)
    log("[nav] parked cursor off the battle (interior, no edge-scroll)", logfile)


def _click_frac(fx, fy, logfile=None, label="", dbl=False, settle=0.0):
    """Click a FIXED fractional screen point (the deterministic-UI fast path). No OCR."""
    _focus_game()
    img = vision.grab()
    pt = (fx * img.width / vision.SCALE, fy * img.height / vision.SCALE)
    (ui.double_click if dbl else ui.click)(pt)
    if label:
        log(f"[nav] fixed-click {label} @ {int(pt[0])},{int(pt[1])}", logfile)
    if settle:
        time.sleep(settle)
    return pt


def _wait_text(pattern, region, tries=4, delay=0.5) -> bool:
    """Cheap checkpoint: is `pattern` visible in `region`? One OCR per try."""
    for _ in range(tries):
        if vision.find_text(vision.grab(), pattern, region=region):
            return True
        time.sleep(delay)
    return False


def _wait_editor(tries=8, delay=0.6) -> bool:
    """Cheap checkpoint for the Scenario Editor (one tabs-band OCR per try, not the full
    6-band detect_state)."""
    for _ in range(tries):
        tabs = vision.ocr_text(vision.grab(), (0.0, 0.02, 0.55, 0.09))
        if any(k in tabs for k in ("terrain", "diplomacy", "triggers", "cinematics")):
            return True
        time.sleep(delay)
    return False


def find_and_click(pattern, region, logfile, label=None, retries=4, dbl=False) -> bool:
    """Locate `pattern` in `region` and click it; retry briefly while the screen settles."""
    for _ in range(retries):
        _focus_game()
        pt = vision.find_text(vision.grab(), pattern, region=region)
        if pt:
            (ui.double_click if dbl else ui.click)(pt)
            log(f"[nav] clicked {label or pattern!r} at {int(pt[0])},{int(pt[1])}", logfile)
            return True
        time.sleep(0.8)
    log(f"[nav] FAILED to find {label or pattern!r} in {region}", logfile)
    return False


def _dismiss_save_prompt(logfile, timeout=4.0) -> bool:
    """Loading a scenario over an edited one pops 'Do you want to save your changes?'.
    It FADES IN (can take >1s, so a single check misses it) — poll for it and click 'No'
    (discard) to proceed. Returns True if a prompt was found and dismissed."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        _focus_game()
        img = vision.grab()
        txt = vision.ocr_text(img, (0.20, 0.30, 0.80, 0.62)).replace(" ", "")
        if "saveyourchanges" in txt or "savechanges" in txt:
            pt = vision.find_text(img, "No", region=R_SAVE)
            if pt:
                ui.click(pt)
                log(f"[nav] save prompt -> No (discard changes) @ {int(pt[0])},{int(pt[1])}",
                    logfile)
                time.sleep(1.0)
                return True
        time.sleep(0.3)
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
        # a 'save changes?' prompt fades in over the load — poll for it and discard
        _dismiss_save_prompt(logfile)
        time.sleep(0.8)
        return True
    log(f"[nav] don't know how to reach load page from {state}", logfile)
    return False


def navigate_to_test_menu(start_state, scenario_name, logfile, fast=True) -> bool:
    """Reach the editor's Menu dialog (where 'Test' lives), staged scenario loaded.

    fast=True clicks the deterministic UI at FIXED coordinates with cheap single-OCR
    checkpoints between steps, falling back to the OCR path the moment a checkpoint says
    the expected screen didn't show. ~4x fewer OCR passes than the all-OCR path."""
    if fast:
        try:
            if _navigate_fast(start_state, scenario_name, logfile):
                return True
            log("[nav] fast path didn't confirm — retrying via OCR", logfile)
        except Exception as e:
            log(f"[nav] fast path error ({e}) — falling back to OCR", logfile)
    return _navigate_ocr(start_state, scenario_name, logfile)


def _navigate_fast(start_state, scenario_name, logfile) -> bool:
    """Fixed-coordinate navigation: editor -> Menu -> Load Scenario -> (save? No) -> row
    -> Load -> (save? No) -> editor -> Menu. OCR only as cheap per-gate verification."""
    st = start_state
    if st == "editor":
        _click_frac(*FP_MENU, logfile=logfile, label="Menu", dbl=True, settle=0.9)
        st = "main_menu"
    if st == "main_menu":
        _click_frac(*FP_LOAD_MENU, logfile=logfile, label="Load Scenario", settle=0.5)
        # the 'save your changes?' prompt ALWAYS appears here (leaving the edited scenario)
        # and fades in over ~2-3s. OCR-polling for it is slow (the big region is ~5s/poll,
        # so it samples only ~1x and often misses, stalling GATE A ~15s). Instead BLIND-CLICK
        # 'No' at its fixed coord after the fade — deterministic + instant. If it ever misses
        # (slow fade), GATE A below still detects the stuck dialog and OCR-recovers.
        time.sleep(2.3)
        _click_frac(*FP_SAVE_NO, logfile=logfile, label="save:No (discard)", settle=0.6)
    elif st != "load_dialog":
        return False                                     # unknown start -> let OCR handle it
    # GATE A: the Load page must be up (its bottom 'Load Scenario' button is visible)
    if not _wait_text("Load Scenario", R_LOAD_BTN, tries=3):
        log("[nav] load page not confirmed — OCR recover", logfile)
        _dismiss_save_prompt(logfile, timeout=6.0)       # blind No may have missed a slow fade
        if not _reach_load_page(start_state, logfile):
            return False
    _click_frac(*FP_ROW1, logfile=logfile, label="row", settle=0.4)
    _click_frac(*FP_LOAD_BTN, logfile=logfile, label="Load Scenario (button)", settle=0.3)
    # loading the file doesn't re-prompt (we already discarded), so no second save-poll.
    # the small scenario loads in ~2s; a fixed wait beats an OCR poll here (each editor
    # check is a ~5s OCR). GATE C below catches the rare case where it wasn't ready.
    time.sleep(2.5)
    _click_frac(*FP_MENU, logfile=logfile, label="Menu", dbl=True, settle=0.7)
    # GATE C: the menu dialog (with 'Test') must be up; else OCR-find Menu (self-correcting)
    if not _wait_text("Test", R_DIALOG, tries=3):
        if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
            return False
        time.sleep(0.6)
    return True


def _navigate_ocr(start_state, scenario_name, logfile) -> bool:
    """All-OCR navigation (the robust fallback): Load page -> click the ONE list row ->
    Load -> editor -> Menu. No search."""
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
    _dismiss_save_prompt(logfile)          # loading over the open scenario can re-prompt
    time.sleep(2.5)
    if not find_and_click("Menu", R_MENU_BTN, logfile, "Menu", dbl=True):
        return False
    time.sleep(0.8)
    return True


def wait_for_game_start(t0, timeout=20.0, logfile=None) -> float:
    """After clicking Test, wait until the scenario actually starts. PRIMARY signal:
    the dark-load-screen -> bright-arena luma jump (the same deterministic transition
    the footage anchor uses) — no OCR, ~instant, and it works even when the on-screen
    readout triggers are removed (AOE2_NO_READOUT). Returns the wall timestamp, or a
    fixed fallback offset if no transition shows."""
    seen_dark = False
    while time.time() - t0 < timeout:
        _focus_game()
        lum = vision.screen_luma()
        if lum < 50:
            seen_dark = True               # the load screen (or the dark editor UI)
        elif lum >= 90 and seen_dark:
            t = time.time()
            log(f"[watch] game started at +{t - t0:.1f}s (luma {lum:.0f})", logfile)
            return t
        time.sleep(0.25)
    log("[watch] game-start not detected — using fallback offset", logfile)
    return t0 + 5.0


def _in_editor(img=None) -> bool:
    """Cheap editor check: one tabs-band OCR (not the full 6-band detect_state)."""
    tabs = vision.ocr_text(img if img is not None else vision.grab(), (0.0, 0.02, 0.55, 0.09))
    return any(k in tabs for k in ("terrain", "diplomacy", "triggers", "cinematics"))


def return_to_editor(logfile, retries=10) -> bool:
    """Quit the running test back to the Scenario Editor so the game is clean for the
    NEXT run. The no-lose scenario holds the result on screen WITHOUT ending the game
    (no banner), so the path is: open the in-game Menu (F10) -> 'Quit Current Game' ->
    'Yes'. A leftover defeat banner ('Continue') is handled too, for safety. Idempotent:
    returns True once the editor tabs are visible. Uses the cheap editor check + warm OCR
    + tightened waits; Quit is tried before the (legacy) banner to save an OCR/iter."""
    for _ in range(retries):
        _focus_game()
        img = vision.grab()
        if _in_editor(img):
            log("[end] back in the Scenario Editor — clean for the next run", logfile)
            return True
        # in-game menu open -> quit back to the editor -> Yes
        q = (vision.find_text(img, "Quit Current Game", region=R_GAME_MENU)
             or vision.find_text(img, "Quit", region=R_GAME_MENU))
        if q:
            ui.click(q)
            time.sleep(1.0)
            y = vision.find_text(vision.grab(), "Yes", region=R_CONFIRM)
            if y:
                ui.click(y)
            log("[end] Quit -> Yes", logfile)
            time.sleep(2.0)
            continue
        # legacy defeat banner (shouldn't occur with no-lose triggers)
        if vision.detect_end(img):
            pt = vision.find_text(img, "Continue", region=R_CONTINUE)
            if pt:
                ui.click(pt); time.sleep(2.0); continue
        # otherwise open the in-game menu via the F10 hotkey (bound in-game on Windows)
        platform_io.key("f10")
        log("[end] opened in-game menu (F10)", logfile)
        time.sleep(1.0)
    ok = _in_editor()
    log(f"[end] {'in editor' if ok else 'WARNING: editor not confirmed'}", logfile)
    return ok


def _flag_no_result(final_path, got_result: bool, logfile=None):
    """The watch loop hit the cap without seeing the 'WINS' banner — the recording is
    probably truncated mid-battle. Don't fail the run (the footage may still be usable);
    flag it loudly with a marker file next to the output so a sweep can't silently ship
    a clip that ends before the fight does."""
    if got_result:
        return
    try:
        marker = Path(str(Path(final_path).with_suffix("")) + ".NO_RESULT.txt")
        marker.write_text(
            "The watch loop hit the recording cap without detecting the WINS result\n"
            "banner — this clip may end mid-battle. Re-run with a higher --cap, or\n"
            "verify the clip manually and delete this marker.\n")
        log(f"[watch] WARNING: no result before cap — flagged {marker.name}", logfile)
    except OSError as e:
        log(f"[watch] WARNING: no result before cap (marker write failed: {e})", logfile)


def run_matchup(civ1, slug1, civ2, slug2, *, name=None, copy_to=None, raw_copy_to=None,
                cap=240, mode="count", unit_cap=30, live_overlay=True, compose=True,
                out_mov=os.path.join(TMP, "auto_fight.mov"),
                final=os.path.join(TMP, "auto_matchup_FINAL.mp4"),
                dismiss_after=True, logfile=None) -> Path:
    """One full matchup: build from template -> stage -> navigate -> record -> Test
    -> watch for end -> stop -> (dismiss to editor) -> compose recap -> copy.

    mode="count"     -> unit_cap vs unit_cap (equal-count, default 30v30)
    mode="resources" -> equal total resources, cheaper unit capped at unit_cap
    compose=False    -> RECORD-ONLY: archive the raw + sidecar and skip the (CPU-bound)
                        compose entirely; re-render later with auto.recompose_from_raws
                        (parallel, no game needed). Returns the archived raw Path.

    Returns the final video Path. Designed to be called repeatedly for a batch."""
    vision.warmup()                          # load the OCR model now (cached for the batch)
    # 1. BUILD the run scenario from the golden template (swap units/civs, no tech)
    side1 = resolve_side(civ1, slug1)
    side2 = resolve_side(civ2, slug2)
    if mode == "resources":
        counts = equal_resource_counts(civ1, slug1, civ2, slug2, unit_cap)
    else:
        counts = (unit_cap, unit_cap)
    run_path = RUN_DIR / f"{side1[1]}_vs_{side2[1]}.aoe2scenario"
    from overlay.overlay_data import get_unit_card
    ranged = (bool(get_unit_card(civ1, slug1).get("is_ranged")),
              bool(get_unit_card(civ2, slug2).get("is_ranged")))
    build_run(side1, side2, run_path, counts=counts, ranged=ranged)
    log(f"[build] {side1[2]} x{counts[0]} ({civ1}) vs {side2[2]} x{counts[1]} ({civ2}) "
        f"[{mode}] ranged={ranged} -> {run_path}", logfile)

    # 2. STAGE it as the sole scenario in the game folder
    scen_name = stage_generated(run_path, logfile=logfile)

    # 3. bring AoE2 to the front; if a previous fight left an end banner up, clear it
    log("[nav] bringing AoE2:DE to the front...", logfile)
    st = bring_game_to_front(logfile)
    if st in ("end_screen", "in_game", "unknown"):   # leftover test/banner -> editor first
        return_to_editor(logfile)
        st = bring_game_to_front(logfile)
    log(f"[nav] starting screen: {st}", logfile)
    if st not in ("editor", "main_menu", "load_dialog"):
        raise RuntimeError(f"unexpected starting screen {st!r}")
    if not navigate_to_test_menu(st, scen_name, logfile):
        raise RuntimeError("navigation failed")

    # 4-7. start the gRPC HP logger (separate process), RECORD -> Test -> wait for the
    # EXACT battle-end (gRPC army-count -> 0, OCR fallback). Whatever happens, ALWAYS stop
    # the logger + recorder and dismiss back to the editor, so one bad run can't orphan them.
    grpc_prefix = os.path.join(TMP, "grpc_" + Path(out_mov).stem)
    grpc_proc = grpc_capture.start_logger(grpc_prefix, dur=cap + 30, logfile=logfile)
    rec = start_recorder(out_mov, cap, logfile=logfile)
    t_rec = time.time()
    t_gs = None
    got_result = False
    try:
        if not find_and_click("Test", R_DIALOG, logfile, "Test"):
            raise RuntimeError("could not click Test")
        t_test = time.time()
        _park_cursor(logfile)                                 # cursor out of the captured frame
        t_gs = wait_for_game_start(t_test, logfile=logfile)   # when the fight actually begins
        # End-detection: the in-game "WINS" banner is the GAME'S OWN verdict, so OCR reads
        # it correctly every run. The gRPC recorder's LIVE TAILER (fixed decoder) writes
        # <prefix>.END the moment one army hits 0 — the exact battle end; the WINS-banner
        # screen watcher remains the fallback when the tailer disabled itself.
        got_result = watch_until_result(
            t_test, cap, logfile=logfile,
            end_flag=(grpc_prefix + ".END") if grpc_proc else None)
        time.sleep(RESULT_HOLD)            # keep recording the on-screen result hold
    finally:
        stop_recorder(rec, out_mov, logfile)
        grpc_capture.stop_logger(grpc_proc, logfile=logfile)
        if dismiss_after:
            return_to_editor(logfile)

    # recording sanity: an empty/tiny .mov means the capture failed (Screen Recording
    # grant missing, or the recorder never started) — fail loudly, don't compose black.
    sz = os.path.getsize(out_mov) if os.path.exists(out_mov) else 0
    if sz < 1_000_000:
        raise RuntimeError(
            f"recording looks empty ({sz} bytes) — check the recorder log "
            f"({out_mov}.ffmpeg.log)")

    # build the gRPC HP sidecar (overlay data + video-sync offset) BEFORE compose, so the
    # live HP-bar HUD can be composited onto the fight footage.
    hp_sidecar = grpc_capture.write_sidecar(grpc_prefix, t_rec, logfile=logfile)

    # RECORD-ONLY mode: archive the raw + its gRPC sidecar and stop here; the (CPU-bound)
    # compose runs later via auto.recompose_from_raws — in parallel, with no game needed.
    if not compose:
        raw_dest = archive_raw(out_mov, raw_copy_to or copy_to,
                               name or Path(final).name, logfile)
        if raw_dest is None:
            raise RuntimeError("record-only: raw archive failed (pass copy_to/raw_copy_to)")
        grpc_capture.copy_sidecar(hp_sidecar, raw_dest, logfile=logfile)
        grpc_capture.archive_stream(grpc_prefix, raw_dest, logfile=logfile)
        _flag_no_result(raw_dest, got_result, logfile)
        log(f"[record-only] raw archived; compose deferred -> {raw_dest}", logfile)
        return raw_dest

    # 8-9. COMPOSE (recap, no OCR) -> COPY. Start the clip when the armies patrol in
    # (measured from the detected game-start), and the compose drops the idle tail.
    # This wall-clock lead_in is only the FALLBACK — the composer overrides it with the
    # frame-accurate game-start it detects in the footage itself.
    base = t_gs if t_gs is not None else t_rec
    lead_in = max(0.0, (base - t_rec) + PATROL_LEAD_WALLCLOCK)
    composer = compose_live_overlay if live_overlay else compose_recap
    final_path = composer(civ1, slug1, civ2, slug2, out_mov, final,
                          copy_to, name, lead_in=lead_in, counts=counts,
                          raw_copy_to=raw_copy_to, sidecar=hp_sidecar, logfile=logfile)
    # archive the gRPC sidecar AND the raw stream dump NEXT TO the raw too, so a later
    # recompose of the raw can use (or redecode) the exact game data instead of OCR
    if raw_copy_to:
        raw_dest = (Path(raw_copy_to) / "raw recordings"
                    / (Path(name or Path(final_path).name).stem + ".mov"))
        if raw_dest.exists():
            grpc_capture.copy_sidecar(hp_sidecar, raw_dest, logfile=logfile)
            grpc_capture.archive_stream(grpc_prefix, raw_dest, logfile=logfile)
    _flag_no_result(final_path, got_result, logfile)
    return final_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("civ1"); ap.add_argument("slug1")
    ap.add_argument("civ2"); ap.add_argument("slug2")
    ap.add_argument("--out-mov", default=os.path.join(TMP, "auto_fight.mov"))
    ap.add_argument("--final", default=os.path.join(TMP, "auto_matchup_FINAL.mp4"))
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--resources", action="store_true",
                    help="equal-resource counts (cheaper unit capped at --unit-cap)")
    ap.add_argument("--unit-cap", type=int, default=30)
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--log", default=os.path.join(TMP, "auto_matchup.log"))
    a = ap.parse_args()
    open(a.log, "w").close()
    log(f"=== orchestrate {a.slug1} vs {a.slug2} (template-based, no OCR) ===", a.log)

    if not ui.accessibility_ok():
        log("ERROR: Accessibility not granted to this terminal — scripted clicks will "
            "fail. System Settings -> Privacy & Security -> Accessibility.", a.log)
        sys.exit(2)
    try:
        final = run_matchup(a.civ1, a.slug1, a.civ2, a.slug2, name=a.name,
                            mode=("resources" if a.resources else "count"),
                            unit_cap=a.unit_cap,
                            copy_to=a.copy_to, raw_copy_to=a.copy_to, cap=a.cap,
                            out_mov=a.out_mov, final=a.final, logfile=a.log)
    except Exception as e:
        log(f"ERROR: {e}", a.log)
        sys.exit(1)
    log(f"DONE -> {final}", a.log)


if __name__ == "__main__":
    main()
