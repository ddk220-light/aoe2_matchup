"""record_until_end.py — autonomously record an in-game fight until it ENDS,
then OCR + compose the titled matchup video and copy it out. Logs every step.

The pieces are exposed as functions so orchestrate_matchup.py can reuse them
(start recorder -> click Test -> watch -> stop -> compose). Run as a module to do
the record+compose half on its own (caller clicks Test):

  python -m auto.record_until_end <civ1> <slug1> <civ2> <slug2> \
      [--final PATH] [--cap 240] [--copy-to DIR] [--name FILE.mp4] [--log FILE]

Needs only the Screen Recording grant (screencapture + SCK) — no input injection.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent                       # scenario_builder/
sys.path.insert(0, str(SB / "overlay"))
sys.path.insert(0, str(SB))

from auto import vision                 # noqa: E402

RECORDER = SB / "recorder" / "sck_record"


def log(msg, logfile=None):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile:
        with open(logfile, "a") as f:
            f.write(line + "\n")


def start_recorder(out_mov, cap=240, w=1920, h=1248, fps=60, logfile=None) -> subprocess.Popen:
    if not RECORDER.exists():
        raise FileNotFoundError(f"recorder not built at {RECORDER} (run recorder/build.sh)")
    log(f"[rec] start (cap {cap}s, {w}x{h}@{fps}) -> {out_mov}", logfile)
    return subprocess.Popen(
        [str(RECORDER), out_mov, str(cap), str(fps), str(w), str(h)],
        stderr=subprocess.DEVNULL)


def watch_until_end(t0, cap=240, min_fight=8.0, poll=3.0, logfile=None) -> bool:
    """Poll the screen until the end-of-game banner shows. Returns True if detected."""
    log(f"[watch] for game-end banner (min {min_fight}s, poll {poll}s)...", logfile)
    while time.time() - t0 < min_fight:
        time.sleep(0.5)
    last = None
    while time.time() - t0 < cap - 2:
        try:
            img = vision.grab()
            if vision.detect_end(img):
                log(f"[watch] game-end detected at +{time.time() - t0:.1f}s", logfile)
                return True
            c = vision.read_counts(img)
            if c and c != last:
                last = c
                log(f"[watch] +{time.time() - t0:4.0f}s  readout {c[0]} vs {c[1]}", logfile)
        except Exception as e:
            log(f"[watch] detect error: {e}", logfile)
        time.sleep(poll)
    log("[watch] cap reached without a banner — stopping anyway", logfile)
    return False


def stop_recorder(rec: subprocess.Popen, out_mov, logfile=None):
    if rec.poll() is None:
        rec.send_signal(signal.SIGINT)        # graceful: finalize the .mov
        try:
            rec.wait(timeout=20)
        except subprocess.TimeoutExpired:
            log("[rec] slow to finalize; killing", logfile)
            rec.kill()
    sz = os.path.getsize(out_mov) // 1024 if os.path.exists(out_mov) else 0
    log(f"[rec] stopped; {sz} KB captured", logfile)


def ocr_and_compose(civ1, slug1, civ2, slug2, out_mov, final,
                    copy_to=None, name=None, logfile=None) -> Path:
    from video_extract import extract_video_results
    from make_real_video import make_real_matchup_video
    import shutil
    log("[ocr] extracting survivor timeline + fight window...", logfile)
    result = extract_video_results(out_mov, civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2)
    names = {1: slug1, 2: slug2, 0: "draw"}
    log(f"[ocr] {result.start1}v{result.start2} -> {result.survivors1}-{result.survivors2}  "
        f"winner={names[result.winner]}  window {result.fight_start_s:.1f}-{result.fight_end_s:.1f}s  "
        f"({len(result.timeline)} samples)", logfile)
    log("[compose] intro card -> fight + live HUD + audio -> outro card...", logfile)
    out = make_real_matchup_video(out_mov, civ1, slug1, civ2, slug2, final, result=result)
    log(f"[compose] -> {out} ({Path(out).stat().st_size // 1024} KB)", logfile)
    if copy_to:
        Path(copy_to).mkdir(parents=True, exist_ok=True)
        dest = Path(copy_to) / (name or Path(out).name)
        shutil.copy2(out, dest)
        log(f"[copy] -> {dest}", logfile)
        return Path(dest)
    return Path(out)


def compose_recap(civ1, slug1, civ2, slug2, out_mov, final,
                  copy_to=None, name=None, lead_in=0.0, logfile=None) -> Path:
    """No-OCR compose: intro stat card -> real fight footage (+ captured audio) ->
    recap card. No survivor counts are extracted (see build_run.py / the 'matchup
    recap' design). `lead_in` trims the menu/load seconds off the front of the clip."""
    sys.path.insert(0, str(SB / "overlay"))
    from overlay_data import get_unit_card
    from compose import make_recap_video
    import shutil
    log("[compose] intro card -> real fight (+audio) -> recap card (no OCR)...", logfile)
    u1 = get_unit_card(civ1, slug1)
    u2 = get_unit_card(civ2, slug2)
    out = make_recap_video(u1, u2, final, battle_clip=out_mov, lead_in=lead_in)
    log(f"[compose] -> {out} ({Path(out).stat().st_size // 1024} KB)", logfile)
    if copy_to:
        Path(copy_to).mkdir(parents=True, exist_ok=True)
        dest = Path(copy_to) / (name or Path(out).name)
        shutil.copy2(out, dest)
        log(f"[copy] -> {dest}", logfile)
        return Path(dest)
    return Path(out)


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
    ap.add_argument("--min-fight", type=float, default=8.0)
    ap.add_argument("--poll", type=float, default=3.0)
    a = ap.parse_args()
    open(a.log, "w").close()
    rec = start_recorder(a.out_mov, a.cap, logfile=a.log)
    t0 = time.time()
    watch_until_end(t0, a.cap, a.min_fight, a.poll, a.log)
    stop_recorder(rec, a.out_mov, a.log)
    ocr_and_compose(a.civ1, a.slug1, a.civ2, a.slug2, a.out_mov, a.final,
                    a.copy_to, a.name, a.log)
    log("DONE", a.log)


if __name__ == "__main__":
    main()
