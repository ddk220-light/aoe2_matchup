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

from functools import lru_cache

import numpy as np
from PIL import Image

from auto import platform_io


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def warmup() -> None:
    """Force the (lazy) rapidocr model load NOW, on a tiny dummy image, so the first real
    OCR during navigation isn't a ~15-20s cold-start. Idempotent (the model is cached)."""
    try:
        _ocr()(np.zeros((48, 96, 3), dtype=np.uint8))
    except Exception:
        pass


def grab() -> Image.Image:
    """Full-screen screenshot as a PIL RGB image (OS-specific; see platform_io)."""
    return platform_io.grab()


def ocr_text(img: Image.Image, box=(0.0, 0.0, 1.0, 1.0)) -> str:
    """OCR a fractional region (x0,y0,x1,y1); returns lowercased joined text."""
    w, h = img.size
    x0, y0, x1, y1 = box
    crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    res, _ = _ocr()(np.array(crop))
    if not res:
        return ""
    return " ".join(line[1] for line in res).lower()


SCALE = platform_io.SCALE  # screenshot pixels per click-point (Retina Mac=2, Windows~1)


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
    """Read the in-game live readout 'Unit A: N vs Unit B: M' -> (N, M) or None.

    Parsing lives in overlay.readout.parse_counts (shared with the footage OCR):
    counts are the tokens right after the colons, robust to OCR dropping the spaces
    around 'vs' and to digit-lookalike misreads like '3o' for '30'."""
    from overlay.readout import parse_counts
    if img is None:
        img = grab()
    return parse_counts(ocr_text(img, band))


def screen_luma(img: Image.Image | None = None) -> float:
    """Mean luma of the (downscaled) screen — the cheap live signal for the
    load->game transition (same constants as the footage anchor:
    editor ~32, load screen ~22, in-game arena ~120-140)."""
    if img is None:
        img = grab()
    return float(np.asarray(img.convert("L").resize((160, 90))).mean())


def detect_end(img: Image.Image | None = None) -> bool:
    """True if the end-of-game banner is showing. Our spectator (P1) is allied to
    the victor but not the declared winner, so it always reads 'You have been
    defeated!' at the real end of the fight."""
    if img is None:
        img = grab()
    txt = ocr_text(img, (0.08, 0.36, 0.92, 0.56))
    return any(k in txt for k in ("defeat", "victor", "you have been"))


def detect_result(img: Image.Image | None = None) -> bool:
    """True when the scenario's win trigger is holding '<unit> WINS!' on the center
    panel. This is how the automation knows the fight is over WITHOUT the game ending
    (the win trigger shows this instead of declare_victory, so there's no banner)."""
    if img is None:
        img = grab()
    txt = ocr_text(img, (0.10, 0.18, 0.90, 0.52))
    return "wins" in txt


class ResultWatcher:
    """Change-gated detect_result for the watch loop: the OCR (~1s of CPU per call,
    alongside the recording) only runs when the centre band has visibly CHANGED since
    the frame last OCR'd — the WINS line appearing is such a change (measured ~5 mean
    px diff vs ~1.3-2 for an idle post-battle scene; mid-combat churns at 10-27 and
    always OCRs). A force-OCR after `force_every` consecutive skips bounds the
    worst-case detection latency to (force_every+1) * poll even if a change slips
    under the threshold."""
    BAND = (0.10, 0.18, 0.90, 0.52)        # same band detect_result reads

    def __init__(self, thresh=3.0, force_every=3):
        self.thresh, self.force_every = thresh, force_every
        self._ref = None
        self._skips = 0

    def _band_gray(self, img):
        w, h = img.size
        x0, y0, x1, y1 = self.BAND
        crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        return np.asarray(crop.convert("L").resize((128, 72)), dtype=np.float32)

    def check(self, img: Image.Image | None = None) -> bool:
        if img is None:
            img = grab()
        arr = self._band_gray(img)
        if (self._ref is not None
                and float(np.abs(arr - self._ref).mean()) < self.thresh
                and self._skips < self.force_every):
            self._skips += 1
            return False                   # band unchanged since last OCR -> skip the OCR
        self._skips = 0
        self._ref = arr
        return detect_result(img)


# OCR cue -> screen name. Order matters (most specific first).
def detect_state(img: Image.Image | None = None) -> str:
    """Best-effort identification of the current screen, for navigation gating.
    Returns: main_menu | load_dialog | save_dialog | end_screen | editor |
             in_game | unknown."""
    if img is None:
        img = grab()
    if "main menu" in ocr_text(img, (0.30, 0.34, 0.70, 0.46)):
        return "main_menu"
    # the Load Scenario list: its title banner sits near the top; OCR drops the space
    # inconsistently ('loadscenario'), so compare space-insensitively.
    if "loadscenario" in ocr_text(img, (0.25, 0.06, 0.75, 0.16)).replace(" ", ""):
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
