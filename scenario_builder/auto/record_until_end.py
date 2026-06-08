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

from auto import vision, platform_io    # noqa: E402


def _focus_game():
    """Keep AoE2:DE frontmost so the recorder captures the fight (not another app)."""
    platform_io.activate_game()


PATROL_LEAD = 2.0   # start the clip this many seconds after the detected game-start
#   (game-start = on-screen title/readout appears; the camera pans ~2s then the armies
#    charge in — +2.0s lands on the charge, past the pan, before contact)


def detect_game_start(mov, t_from=1.0, t_to=18.0, step=0.3):
    """FRAME-ACCURATE game-start in a recording: the first frame where the on-screen
    'N vs M' title/readout appears (scenario loaded, timer running). Far more reliable
    than a wall-clock guess (load time varies run to run). Returns seconds, or None."""
    import cv2
    from PIL import Image
    cap = cv2.VideoCapture(str(mov))
    t, found = t_from, None
    while t < t_to:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            break
        if vision.read_counts(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))) is not None:
            found = t
            break
        t += step
    cap.release()
    return found


def log(msg, logfile=None):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile:
        with open(logfile, "a") as f:
            f.write(line + "\n")


def start_recorder(out_mov, cap=240, w=1920, h=1248, fps=60, logfile=None) -> subprocess.Popen:
    if not platform_io.recorder_available():
        raise FileNotFoundError(platform_io.recorder_hint())
    log(f"[rec] start (cap {cap}s, {w}x{h}@{fps}) -> {out_mov}", logfile)
    return platform_io.recorder_start(out_mov, cap=cap, fps=fps, w=w, h=h)


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


def watch_until_result(t0, cap=240, min_fight=8.0, poll=2.0, logfile=None) -> bool:
    """Poll the screen until the win trigger's '<unit> WINS!' result shows. The no-lose
    scenario holds this on screen instead of ending the game, so this is how we know the
    fight is over (no defeat banner). Returns True if detected before the cap."""
    log(f"[watch] for the result banner (min {min_fight}s, poll {poll}s)...", logfile)
    while time.time() - t0 < min_fight:
        time.sleep(0.5)
    while time.time() - t0 < cap - 2:
        try:
            _focus_game()                 # keep the fight on screen for the recorder
            if vision.detect_result(vision.grab()):
                log(f"[watch] result detected at +{time.time() - t0:.1f}s", logfile)
                return True
        except Exception as e:
            log(f"[watch] detect error: {e}", logfile)
        time.sleep(poll)
    log("[watch] cap reached without a result — stopping anyway", logfile)
    return False


def stop_recorder(rec: subprocess.Popen, out_mov, logfile=None):
    platform_io.recorder_stop(rec, out_mov)       # graceful finalize (SIGINT / ffmpeg 'q')
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
                  copy_to=None, name=None, lead_in=0.0, counts=(30, 30),
                  raw_copy_to=None, logfile=None) -> Path:
    """No-OCR compose: intro stat card (with per-side counts + resources) -> real
    fight footage (+ captured audio), capped to 30s of combat with a speed-ramp and
    ending on the in-game ~5s who-won hold. No outro card. `lead_in` trims the
    menu/load seconds off the front; `counts` = (n1, n2) units per side."""
    sys.path.insert(0, str(SB / "overlay"))
    from overlay_data import get_unit_card
    from compose import make_recap_video
    import shutil
    # Prefer a FRAME-ACCURATE clip start: detect game-start in the actual recording and
    # start on the charge (game_start + PATROL_LEAD). Falls back to the passed lead_in.
    gs = detect_game_start(out_mov)
    if gs is not None:
        lead_in = gs + PATROL_LEAD
    log(f"[compose] game_start={gs}  lead_in={lead_in:.1f}  -> intro card -> fight (capped 30s) ...",
        logfile)
    u1 = get_unit_card(civ1, slug1)
    u2 = get_unit_card(civ2, slug2)
    out = make_recap_video(u1, u2, final, battle_clip=out_mov, lead_in=lead_in,
                           counts=counts)
    log(f"[compose] -> {out} ({Path(out).stat().st_size // 1024} KB)", logfile)
    # Archive the RAW recording (so a clip can be re-composed later without re-running
    # the game) to <raw_copy_to>/raw recordings/, named like the video. Done for EVERY
    # run, independent of whether the composed clip itself is copied (e.g. join mode).
    if raw_copy_to and os.path.exists(out_mov):
        raw_dir = Path(raw_copy_to) / "raw recordings"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_dest = raw_dir / (Path(name or Path(out).name).stem + ".mov")
        try:
            shutil.copy2(out_mov, raw_dest)
            log(f"[raw] -> {raw_dest} ({Path(raw_dest).stat().st_size // 1048576} MB)", logfile)
        except Exception as e:
            log(f"[raw] copy failed: {e}", logfile)
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
    ap.add_argument("--out-mov", default=os.path.join(platform_io.TMP_DIR, "auto_fight.mov"))
    ap.add_argument("--final", default=os.path.join(platform_io.TMP_DIR, "auto_matchup_FINAL.mp4"))
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--log", default=os.path.join(platform_io.TMP_DIR, "auto_matchup.log"))
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
