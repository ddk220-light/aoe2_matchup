"""record_navigation.py — screen-record the FULL pre-fight navigation for one matchup so
we can SEE where the per-run overhead goes (menu transitions, dialog waits, load time) and
find places to speed it up. Records from before bring-to-front through to game-start, stops,
compresses to a viewable mp4, and prints a per-phase timing breakdown.

  python -m auto.record_navigation                 # next civ (Berbers) vs Guecha
  python -m auto.record_navigation --civ Berbers --slug elite_camel_archer_berbers
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))

from auto import platform_io, vision                            # noqa: E402
from auto.orchestrate_matchup import (                          # noqa: E402
    resolve_side, equal_resource_counts, stage_generated, bring_game_to_front,
    navigate_to_test_menu, find_and_click, _park_cursor, wait_for_game_start,
    return_to_editor, RUN_DIR, STAGE_NAME, R_DIALOG)
from auto.record_until_end import start_recorder, stop_recorder, log   # noqa: E402
from build_run import build_run                                 # noqa: E402

from auto.config import GUECHA_OUT as OUT_DIR                   # noqa: E402

GUECHA = ("Muisca", "elite_guecha_warrior_muisca")


def _compress(src_mov, dst_mp4):
    """Transcode the full-res capture to a smaller 1080p mp4 (no audio) for easy review."""
    from overlay.compose import _ffmpeg, _run
    _run([_ffmpeg(), "-y", "-i", str(src_mov),
          "-vf", "scale=1920:-2", "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "26", "-an", "-movflags", "+faststart", str(dst_mp4)])
    return dst_mp4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--civ", default="Berbers")
    ap.add_argument("--slug", default="elite_camel_archer_berbers")
    ap.add_argument("--out", default=str(OUT_DIR / "_navigation_capture.mp4"))
    ap.add_argument("--cap", type=int, default=120)
    ap.add_argument("--no-record", action="store_true",
                    help="don't film the nav (representative timing: nav before recorder)")
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logf = str(OUT_DIR / "_nav_capture.log")
    open(logf, "w").close()
    marks = []                                       # (phase, seconds)

    def phase(label, fn):
        t = time.time(); r = fn(); dt = time.time() - t
        marks.append((label, dt)); log(f"[nav-time] {label}: {dt:.1f}s", logf)
        return r

    # 0. build + stage the run scenario (NOT part of the on-screen navigation timing)
    side1, side2 = resolve_side(*GUECHA), resolve_side(a.civ, a.slug)
    counts = equal_resource_counts(*GUECHA, a.civ, a.slug, 30)
    run_path = RUN_DIR / f"{side1[1]}_vs_{side2[1]}.aoe2scenario"
    build_run(side1, side2, run_path, counts=counts)
    stage_generated(run_path, logfile=logf)
    vision.warmup()                                  # warm OCR once (as the sweep would)
    log(f"[nav] recording navigation for Guecha vs {side2[2]} ({a.civ})", logf)

    nav_mov = os.path.join(platform_io.TMP_DIR, "nav_capture.mov")
    # --no-record: time the cycle the way the REAL sweep runs it (navigation BEFORE any
    # recorder, so vision.grab() doesn't contend with the recorder's Desktop-Duplication
    # capture). This is the representative per-matchup timing; recording inflates the
    # OCR-gated phases. With --record we also film the nav for review.
    rec = None if a.no_record else start_recorder(nav_mov, a.cap, logfile=logf)
    t0 = time.time()
    try:
        st = phase("bring_game_to_front", lambda: bring_game_to_front(logf))
        if st in ("end_screen", "in_game", "unknown"):
            return_to_editor(logf); st = bring_game_to_front(logf)
        phase("navigate_to_test_menu", lambda: navigate_to_test_menu(st, STAGE_NAME, logf))
        phase("click_Test", lambda: find_and_click("Test", R_DIALOG, logf, "Test"))
        _park_cursor(logf)
        phase("Test->game_start(load)", lambda: wait_for_game_start(time.time(), logfile=logf))
        time.sleep(2.0)                              # a moment of the fight, then we're done
    finally:
        total = time.time() - t0
        if rec is not None:
            stop_recorder(rec, nav_mov, logf)
        phase("return_to_editor(cleanup)", lambda: return_to_editor(logf))

    if rec is not None:
        log(f"[nav] compressing capture -> {a.out}", logf)
        _compress(nav_mov, a.out)
    sz = Path(a.out).stat().st_size // 1024 if (rec is not None and Path(a.out).exists()) else 0
    print("\n=== NAVIGATION TIMING BREAKDOWN ===")
    for label, dt in marks:
        print(f"  {label:28} {dt:6.1f}s")
    print(f"  {'(front->game start total)':28} {total:6.1f}s")
    if rec is not None:
        print(f"\nvideo -> {a.out} ({sz} KB)")
    print(f"step-by-step log -> {logf}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
