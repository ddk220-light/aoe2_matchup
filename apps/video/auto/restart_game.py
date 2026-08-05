"""Restart AoE2:DE and get back into the Scenario Editor, unattended.

Why this exists: the game's position stream silently stops updating after a long session
(observed 2026-07-31, ~21 hours in — every unit logged its spawn tile for the whole fight
while hp and damage kept flowing). Restarting the game fixes it. But a FRESH LAUNCH does
not land where the rig expects: it opens on the main menu behind a News popup, and
"Editors" leads to a browse page, not the editor itself. The normal navigation assumes the
editor is already open, so every fixed click lands on the wrong control and
return_to_editor cannot recover — the first restart cost a hand-driven rescue.

This reproduces the sequence that worked, by OCR rather than fixed coordinates, because
the post-launch screens are the ones whose layout we trust least.

  python -m auto.restart_game          # restart and park in the editor
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto import vision, input_driver as ui, platform_io   # noqa: E402
from auto.orchestrate_matchup import (                     # noqa: E402
    _focus_game, _in_editor, STAGE_NAME, log,
)

STEAM_APP = "steam://rungameid/813780"
PROC = "AoE2DE_s"


def _running():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-Process {PROC} -ErrorAction SilentlyContinue | Measure-Object).Count"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    return out.isdigit() and int(out) > 0


def _find(img, text, region, logfile=None):
    return vision.find_text(img, text, region=region)


def restart_and_enter_editor(logfile=None, scenario=STAGE_NAME, timeout=300) -> bool:
    """Kill the game, relaunch it, dismiss the News popup, and load `scenario` in the
    Scenario Editor. Returns True once the editor tabs are visible."""
    log("[restart] stopping AoE2:DE", logfile)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Stop-Process -Name {PROC} -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    t0 = time.time()
    while _running() and time.time() - t0 < 30:
        time.sleep(2)

    log("[restart] relaunching via Steam", logfile)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process '{STEAM_APP}'"], capture_output=True)
    while not _running() and time.time() - t0 < timeout:
        time.sleep(5)
    if not _running():
        log("[restart] FAILED: game process never appeared", logfile)
        return False

    vision.warmup()
    # The menu takes a while to render; OCR returns empty until it does.
    while time.time() - t0 < timeout:
        _focus_game()
        time.sleep(2)
        img = vision.grab()
        if vision.ocr_text(img, (0.0, 0.0, 1.0, 1.0)).strip():
            break

    # News popup covers the menu. Its close button is the only X up there.
    for _ in range(3):
        img = vision.grab()
        x = _find(img, "News", (0.30, 0.08, 0.90, 0.20))
        if not x:
            break
        # the X sits at the panel's top-right; step right from the title
        ui.click((x[0] + 480, x[1]))
        log("[restart] dismissed the News popup", logfile)
        time.sleep(1.5)

    # main menu -> Editors -> pick the staged scenario -> Load Scenario
    for _ in range(6):
        _focus_game()
        img = vision.grab()
        if _in_editor(img):
            log("[restart] back in the Scenario Editor", logfile)
            return True
        row = _find(img, scenario, (0.05, 0.15, 0.75, 0.80))
        btn = _find(img, "Load Scenario", (0.0, 0.78, 1.0, 1.0))
        if row and btn:
            ui.click(row); time.sleep(1.2)
            ui.click(btn); time.sleep(9.0)
            continue
        ed = _find(img, "Editors", (0.0, 0.15, 0.40, 0.95))
        if ed:
            ui.click(ed); time.sleep(4.0)
            continue
        time.sleep(2.0)

    ok = _in_editor()
    log(f"[restart] {'in editor' if ok else 'WARNING: editor not confirmed'}", logfile)
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if restart_and_enter_editor(logfile=None) else 1)
