"""input_driver.py — scripted mouse/keyboard via cliclick.

Coordinates are LOGICAL POINTS (what vision.find_text returns). Requires the
launching app to have macOS Accessibility permission (System Settings ->
Privacy & Security -> Accessibility). The Screen Recording grant is NOT enough
for input injection — that's a separate permission.

Clicks use the game-safe pattern learned for AoE2:DE: move -> settle -> discrete
down/up (no re-warp), which the engine accepts (a warp+click is dropped).
"""
from __future__ import annotations

import subprocess
import time

CLICLICK = "/opt/homebrew/bin/cliclick"


def accessibility_ok() -> bool:
    """True if cliclick can inject events (Accessibility granted)."""
    out = subprocess.run([CLICLICK, "-V"], capture_output=True, text=True)
    blob = (out.stdout + out.stderr).lower()
    return "accessibility privileges not enabled" not in blob


def _run(*args):
    subprocess.run([CLICLICK, *args], check=True, capture_output=True)


def move(pt):
    _run(f"m:{int(pt[0])},{int(pt[1])}")


def click(pt, settle=0.45, hold=0.12):
    """Game-safe click at a logical point: move -> settle -> down -> up."""
    x, y = int(pt[0]), int(pt[1])
    _run(f"m:{x},{y}")
    time.sleep(settle)
    _run(f"dd:{x},{y}")
    time.sleep(hold)
    _run(f"du:{x},{y}")


def double_click(pt, gap=0.45):
    """Two game-safe clicks (some buttons/menus need a second press)."""
    click(pt)
    time.sleep(gap)
    click(pt)


def clear_field(backspaces=50):
    """Clear a focused text field. The AoE2 Load dialog keeps the PREVIOUS search
    text, so we must wipe it before typing or the new name appends. Select-all +
    delete handles it; a run of backspaces is a backup for fields that ignore Cmd+A."""
    _run("kd:cmd", "t:a", "ku:cmd")          # Cmd+A (select all)
    time.sleep(0.1)
    _run(*(["kp:delete"] * backspaces))      # backspaces, in one invocation


def type_text(text, settle=0.3):
    """Type into the focused field."""
    time.sleep(settle)
    _run(f"t:{text}")
