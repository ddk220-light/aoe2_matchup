"""input_driver.py — scripted mouse/keyboard via the platform_io backend (cliclick on
macOS, pydirectinput on Windows).

Coordinates are click-points (what vision.find_text returns). Clicks use the game-safe
pattern AoE2:DE needs: move -> settle -> discrete down/up (a warp+click is dropped by
the in-game engine on both platforms).
"""
from __future__ import annotations

import time

from auto import platform_io


def accessibility_ok() -> bool:
    """True if we can inject input (macOS: Accessibility granted; Windows: always)."""
    return platform_io.input_available()


def move(pt):
    platform_io.move(pt[0], pt[1])


def click(pt, settle=0.45, hold=0.12):
    """Game-safe click at a click-point: move -> settle -> down -> hold -> up."""
    x, y = int(pt[0]), int(pt[1])
    platform_io.move(x, y)
    time.sleep(settle)
    platform_io.mouse_down(x, y)
    time.sleep(hold)
    platform_io.mouse_up(x, y)


def double_click(pt, gap=0.45):
    """Two game-safe clicks (some buttons/menus need a second press)."""
    click(pt)
    time.sleep(gap)
    click(pt)


def type_text(text, settle=0.3):
    """Type into the focused field."""
    time.sleep(settle)
    platform_io.type_text(text)
