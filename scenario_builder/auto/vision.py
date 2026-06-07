"""vision.py — screenshot processing for the AoE2 matchup automation.

Grabs the screen with `screencapture` (uses the Screen Recording grant — no input
injection, so this works from any host) and OCRs fractional regions with rapidocr
to identify which screen the game is on and whether a fight has ended.

This is the "check the stage through screenshot processing" layer: callers gate
their next action on detect_state() / detect_end() instead of a human eyeballing.

Coordinates everywhere are FRACTIONAL (0..1 of width/height) so they're resolution
independent. Pixel<->point scale (Retina 2x here) only matters for input injection,
handled in input_driver.py.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from functools import lru_cache

import numpy as np
from PIL import Image


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def grab() -> Image.Image:
    """Full-screen screenshot as a PIL RGB image (needs Screen Recording perm)."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        subprocess.run(["screencapture", "-x", "-t", "png", path],
                       check=True, capture_output=True)
        return Image.open(path).convert("RGB")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def ocr_text(img: Image.Image, box=(0.0, 0.0, 1.0, 1.0)) -> str:
    """OCR a fractional region (x0,y0,x1,y1); returns lowercased joined text."""
    w, h = img.size
    x0, y0, x1, y1 = box
    crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    res, _ = _ocr()(np.array(crop))
    if not res:
        return ""
    return " ".join(line[1] for line in res).lower()


SCALE = 2.0  # screencapture pixels per logical point (Retina 2x); point = pixel / SCALE


def find_text(img: Image.Image, pattern: str, region=(0.0, 0.0, 1.0, 1.0)):
    """Locate a UI label by text; return its center as a LOGICAL POINT (x, y) for
    input injection (cliclick), or None. `pattern` is matched case-insensitively as
    a substring of each OCR line (spaces ignored). `region` narrows the search."""
    w, h = img.size
    x0, y0, x1, y1 = region
    ox, oy = int(x0 * w), int(y0 * h)
    crop = img.crop((ox, oy, int(x1 * w), int(y1 * h)))
    res, _ = _ocr()(np.array(crop))
    if not res:
        return None
    want = pattern.lower().replace(" ", "")
    for box, text, _conf in res:
        if want in text.lower().replace(" ", ""):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            cx = (ox + sum(xs) / len(xs)) / SCALE
            cy = (oy + sum(ys) / len(ys)) / SCALE
            return (cx, cy)
    return None


def read_counts(img: Image.Image | None = None, band=(0.28, 0.12, 0.74, 0.22)):
    """Read the in-game live readout 'Unit A: N vs Unit B: M' -> (N, M) or None."""
    if img is None:
        img = grab()
    txt = ocr_text(img, band)
    parts = re.split(r"\bvs\b", txt, maxsplit=1)
    if len(parts) != 2:
        return None
    a = re.findall(r"\d+", parts[0])
    b = re.findall(r"\d+", parts[1])
    if not a or not b:
        return None
    return int(a[0]), int(b[0])


def detect_end(img: Image.Image | None = None) -> bool:
    """True if the end-of-game banner is showing. Our spectator (P1) is allied to
    the victor but not the declared winner, so it always reads 'You have been
    defeated!' at the real end of the fight."""
    if img is None:
        img = grab()
    txt = ocr_text(img, (0.08, 0.36, 0.92, 0.56))
    return any(k in txt for k in ("defeat", "victor", "you have been"))


# OCR cue -> screen name. Order matters (most specific first).
def detect_state(img: Image.Image | None = None) -> str:
    """Best-effort identification of the current screen, for navigation gating.
    Returns: main_menu | load_dialog | save_dialog | end_screen | editor |
             in_game | unknown."""
    if img is None:
        img = grab()
    if "main menu" in ocr_text(img, (0.30, 0.34, 0.70, 0.46)):
        return "main_menu"
    if "load scenario" in ocr_text(img, (0.30, 0.15, 0.70, 0.24)):
        return "load_dialog"
    if "save your changes" in ocr_text(img, (0.28, 0.40, 0.72, 0.54)):
        return "save_dialog"
    if detect_end(img):
        return "end_screen"
    tabs = ocr_text(img, (0.0, 0.02, 0.55, 0.09))
    if any(k in tabs for k in ("terrain", "diplomacy", "triggers", "cinematics")):
        return "editor"
    if read_counts(img) is not None:
        return "in_game"
    return "unknown"


if __name__ == "__main__":
    # quick live probe: prints detected state + the key OCR bands for calibration
    import json
    img = grab()
    print("size px:", img.size)
    print("state:", detect_state(img))
    bands = {
        "menu_title(.30,.34,.70,.46)": (0.30, 0.34, 0.70, 0.46),
        "load_hdr(.30,.15,.70,.24)": (0.30, 0.15, 0.70, 0.24),
        "tabs(0,.02,.55,.09)": (0.0, 0.02, 0.55, 0.09),
        "readout(.28,.12,.74,.22)": (0.28, 0.12, 0.74, 0.22),
        "banner(.08,.36,.92,.56)": (0.08, 0.36, 0.92, 0.56),
    }
    for name, box in bands.items():
        print(f"  {name}: {ocr_text(img, box)!r}")
    print("counts:", read_counts(img))
