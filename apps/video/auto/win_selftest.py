"""win_selftest.py — prove the automation primitives work on THIS machine.

Exercises the three capabilities the matchup automation needs and prints a
PASS / WARN / FAIL report:

  CAPTURE   screenshot (grab) + the screen recorder (ffmpeg ddagrab/nvenc or gdigrab)
  ACTIONS   input injection (move the cursor + read it back) + window focus
  SAVES     OCR of a screenshot (rapidocr) + the scenario folder (list saves)

It is SAFE to run anytime: the only input action is a tiny cursor move that it
restores. Artifacts (a screenshot PNG + a ~3s test recording) go to %TEMP%.

  scenario_builder\\.venv\\Scripts\\python.exe -m auto.win_selftest
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import platform_io, vision, input_driver as ui   # noqa: E402

TMP = Path(platform_io.TMP_DIR)
_results: list[tuple[str, str, str]] = []   # (status, name, detail)


def _record(status, name, detail=""):
    _results.append((status, name, detail))
    icon = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[status]
    print(f"{icon} {name}" + (f"  —  {detail}" if detail else ""), flush=True)


def check(name, critical=True):
    """Decorator-ish wrapper: run fn, capture PASS/FAIL (or WARN if non-critical)."""
    def deco(fn):
        try:
            ok, detail = fn()
            _record("PASS" if ok else ("FAIL" if critical else "WARN"), name, detail)
        except Exception as e:
            _record("FAIL" if critical else "WARN", name,
                    f"{type(e).__name__}: {e}")
            if os.environ.get("SELFTEST_TRACE"):
                traceback.print_exc()
        return fn
    return deco


def main():
    print("=" * 70)
    print("  AoE2 matchup automation — Windows self-test")
    print("=" * 70)

    # ---- config / backend -------------------------------------------------
    @check("backend selected")
    def _():
        be = "windows" if platform_io.IS_WINDOWS else "mac"
        return platform_io.IS_WINDOWS, (
            f"OS={be}  SCALE={platform_io.SCALE}  "
            f"canvas={platform_io.OUT_W}x{platform_io.OUT_H}  TMP={platform_io.TMP_DIR}")

    # ---- CAPTURE: screenshot ---------------------------------------------
    shot = {"img": None}

    @check("CAPTURE  screenshot (grab)")
    def _():
        img = platform_io.grab()
        shot["img"] = img
        out = TMP / "selftest_screenshot.png"
        img.save(out)
        return (img.width > 100 and img.height > 100,
                f"{img.width}x{img.height}px -> {out.name}")

    # ---- CAPTURE: recorder ------------------------------------------------
    @check("CAPTURE  screen recorder (ffmpeg ddagrab/nvenc, gdigrab fallback)")
    def _():
        if not platform_io.recorder_available():
            return False, platform_io.recorder_hint()
        out = TMP / "selftest_recording.mov"
        if out.exists():
            out.unlink()
        proc = platform_io.recorder_start(str(out), cap=3, fps=30,
                                           w=platform_io.OUT_W, h=platform_io.OUT_H)
        time.sleep(4.0)                       # cap=3 -> ffmpeg self-stops; give it a beat
        platform_io.recorder_stop(proc, str(out))
        if not out.exists():
            return False, "no output file produced"
        sz = out.stat().st_size
        dims = ""
        try:
            import cv2
            cap = cv2.VideoCapture(str(out))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            dims = f"{w}x{h}, ~{n} frames, "
        except Exception:
            pass
        return sz > 50_000, f"{dims}{sz // 1024} KB -> {out.name}"

    # ---- ACTIONS: input injection ----------------------------------------
    @check("ACTIONS  input injection (cursor move + read-back)")
    def _():
        if not ui.accessibility_ok():
            return False, "input_available() is False"
        import ctypes
        from ctypes import wintypes
        get = ctypes.windll.user32.GetCursorPos
        pt = wintypes.POINT()
        get(ctypes.byref(pt))
        orig = (pt.x, pt.y)
        target = (max(50, platform_io.OUT_W // 4), max(50, platform_io.OUT_H // 4))
        ui.move(target)
        time.sleep(0.25)
        get(ctypes.byref(pt))
        landed = (pt.x, pt.y)
        ui.move(orig)                          # put the cursor back
        err = abs(landed[0] - target[0]) + abs(landed[1] - target[1])
        return err <= 4, f"target={target} landed={landed} err={err}px (restored to {orig})"

    # ---- ACTIONS: window focus -------------------------------------------
    @check("ACTIONS  window enumeration / focus", critical=False)
    def _():
        import pygetwindow as gw
        titles = [t for t in gw.getAllTitles() if t and t.strip()]
        aoe = [t for t in titles if "age of empires" in t.lower()]
        detail = f"{len(titles)} windows visible"
        if aoe:
            detail += f"; AoE2 window FOUND: {aoe[0]!r}"
        else:
            detail += f"; AoE2 not running (looked for {platform_io.AOE2_WIN_TITLE!r})"
        return len(titles) > 0, detail

    # ---- SAVES: OCR -------------------------------------------------------
    @check("SAVES    OCR engine (rapidocr)")
    def _():
        img = shot["img"] or platform_io.grab()
        txt = vision.ocr_text(img, (0.0, 0.0, 1.0, 1.0))
        words = len(txt.split())
        state = vision.detect_state(img)
        return True, f"OCR ran; ~{words} words on screen; detect_state()={state!r}"

    # ---- SAVES: scenario folder ------------------------------------------
    @check("SAVES    scenario folder (view the saves)")
    def _():
        d = platform_io.scenario_dir()
        exists = d.is_dir()
        saves = sorted(p.name for p in d.glob("*.aoe2scenario")) if exists else []
        listing = (("; saves: " + ", ".join(saves)) if saves else
                   ("; (folder empty)" if exists else "; FOLDER MISSING — set AOE2_SCENARIO_DIR"))
        return exists, f"{d}{listing}"

    # ---- summary ----------------------------------------------------------
    print("-" * 70)
    n_fail = sum(1 for s, *_ in _results if s == "FAIL")
    n_warn = sum(1 for s, *_ in _results if s == "WARN")
    n_pass = sum(1 for s, *_ in _results if s == "PASS")
    print(f"  {n_pass} passed, {n_warn} warning(s), {n_fail} failed")
    if n_fail == 0:
        print("  ALL CRITICAL CHECKS PASSED — capture / actions / saves are working.")
    print("=" * 70)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
