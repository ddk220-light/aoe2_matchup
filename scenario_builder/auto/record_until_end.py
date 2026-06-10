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
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent                       # scenario_builder/
sys.path.insert(0, str(SB))

from auto import vision, platform_io    # noqa: E402


def _focus_game():
    """Keep AoE2:DE frontmost so the recorder captures the fight (not another app)."""
    platform_io.activate_game()


PATROL_LEAD = 1.3   # start the clip this many seconds after game-time ZERO (V0)
#   V0 = the first in-game frame (the load->game pixel transition; frame-accurate).
#   On this template the armies break formation and start advancing ~1.3s after V0 —
#   calibrated to match the proven old framing (the readout became OCR-readable ~0.3s
#   after V0, and the old readout-based lead was +1.0 from there).


def detect_game_start(mov, t_from=1.0, t_to=25.0, coarse=1.0, fine=0.2):
    """Game-time ZERO (the first in-game frame) in a recording.

    PRIMARY: the load->game luma transition (video_extract.find_game_start) —
    frame-accurate pixel statistics, NO OCR; every recording shares the same
    deterministic structure (editor -> click flash -> dark load screen -> bright
    arena). FALLBACK: the old two-pass OCR scan for the on-screen readout appearing
    (the readout renders within ~0.5s of V0, so the fallback is only slightly late).
    Returns seconds, or None."""
    from overlay.video_extract import find_game_start
    v0 = find_game_start(mov, t_from=t_from, t_to=max(t_to, 25.0))
    if v0 is not None:
        return v0

    import cv2
    from PIL import Image
    cap = cv2.VideoCapture(str(mov))

    def _has_readout(t):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            return None
        return vision.read_counts(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))) is not None

    hit, t = None, t_from
    while t < t_to:
        r = _has_readout(t)
        if r is None:
            break
        if r:
            hit = t
            break
        t += coarse
    found = hit
    if hit is not None and hit > t_from:          # refine within the prior coarse step
        s = max(t_from, hit - coarse + fine)
        while s < hit:
            if _has_readout(s):
                found = s
                break
            s += fine
    cap.release()
    return found


def log(msg, logfile=None):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile:
        with open(logfile, "a") as f:
            f.write(line + "\n")


def start_recorder(out_mov, cap=240, w=platform_io.OUT_W, h=platform_io.OUT_H,
                   fps=60, logfile=None) -> subprocess.Popen:
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


def watch_until_result(t0, cap=240, min_fight=8.0, poll=2.0, logfile=None,
                       end_flag=None) -> bool:
    """Poll until the fight is over. PRIMARY signal: the gRPC live tailer's `end_flag`
    file (<grpc-prefix>.END), written by the stream recorder the moment one army's
    alive count hits 0 — exact, no OCR. FALLBACK: the win trigger's '<unit> WINS!'
    banner via the change-gated screen watcher (vision.ResultWatcher), which also
    covers runs where the live decode disabled itself. Returns True if either fires
    before the cap."""
    log(f"[watch] for fight end (gRPC .END + banner fallback, min {min_fight}s, "
        f"poll {poll}s)...", logfile)
    watcher = vision.ResultWatcher()
    while time.time() - t0 < min_fight:
        time.sleep(0.5)
    while time.time() - t0 < cap - 2:
        try:
            if end_flag and os.path.exists(end_flag):
                log(f"[watch] gRPC live tailer reports fight end at "
                    f"+{time.time() - t0:.1f}s", logfile)
                return True
            _focus_game()                 # keep the fight on screen for the recorder
            if watcher.check(vision.grab()):
                log(f"[watch] result banner detected at +{time.time() - t0:.1f}s", logfile)
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
    from overlay.video_extract import extract_video_results
    from overlay.make_real_video import make_real_matchup_video
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


def archive_raw(out_mov, raw_copy_to, name, logfile=None):
    """Archive the RAW recording (so a clip can be re-composed later without re-running
    the game) to <raw_copy_to>/raw recordings/<name>.mov. Done for EVERY run, independent
    of whether a composed clip is copied (e.g. join mode). Returns the dest Path or None."""
    if not (raw_copy_to and out_mov and os.path.exists(out_mov)):
        return None
    raw_dir = Path(raw_copy_to) / "raw recordings"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_dest = raw_dir / (Path(name).stem + ".mov")
    try:
        import shutil
        shutil.copy2(out_mov, raw_dest)
        log(f"[raw] -> {raw_dest} ({raw_dest.stat().st_size // 1048576} MB)", logfile)
        return raw_dest
    except Exception as e:
        log(f"[raw] copy failed: {e}", logfile)
        return None


def copy_out(out, copy_to, name, logfile=None) -> Path:
    """Copy the finished video to the delivery folder (if any); returns the final path."""
    if not copy_to:
        return Path(out)
    import shutil
    Path(copy_to).mkdir(parents=True, exist_ok=True)
    dest = Path(copy_to) / (name or Path(out).name)
    shutil.copy2(out, dest)
    log(f"[copy] -> {dest}", logfile)
    return dest


def compose_recap(civ1, slug1, civ2, slug2, out_mov, final,
                  copy_to=None, name=None, lead_in=0.0, counts=(30, 30),
                  raw_copy_to=None, sidecar=None, logfile=None) -> Path:
    """No-OCR compose: intro stat card (with per-side counts + resources) -> real
    fight footage (+ captured audio), capped to 30s of combat with a speed-ramp and
    ending on the in-game ~5s who-won hold. No outro card. `lead_in` trims the
    menu/load seconds off the front; `counts` = (n1, n2) units per side."""
    from overlay.overlay_data import get_unit_card
    from overlay.compose import make_recap_video
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
                           counts=counts, size=(platform_io.OUT_W, platform_io.OUT_H),
                           sidecar=sidecar)
    log(f"[compose] -> {out} ({Path(out).stat().st_size // 1024} KB)", logfile)
    archive_raw(out_mov, raw_copy_to, name or Path(out).name, logfile)
    dest = copy_out(out, copy_to, name, logfile)
    if sidecar and Path(sidecar).exists():            # ship the overlay's sidecar with it
        try:
            import shutil
            shutil.copy2(sidecar, str(Path(dest).with_suffix("")) + ".hp.json")
        except Exception as e:
            log(f"[compose] sidecar copy failed: {e}", logfile)
    return dest


def build_ocr_sidecar(out_mov, civ1, slug1, civ2, slug2, counts, gs, sidecar_path,
                      logfile=None):
    """OCR the scenario's on-screen unit-count readout straight from the RAW footage into
    an overlay sidecar. This is the GAME'S OWN live count, so the bar/counts match the units
    dying frame-for-frame (no gRPC lag/offset). Bounded to the fight window for speed. The
    bar fraction uses the count itself (hp == count), so it drains exactly with the deaths.

    The sidecar clock is anchored on `gs` (= V0, pixel-detected game-time zero) so
    `game_s` is REAL game-seconds and video time = video_game_start_s + game_s exactly.
    Returns the sidecar path, or None on failure."""
    import json
    try:
        from overlay.video_extract import extract_video_results
        res = extract_video_results(
            out_mov, civ1=civ1, slug1=slug1, civ2=civ2, slug2=slug2,
            start1=counts[0], start2=counts[1], sample_hz=1.0,
            t_from=max(0.0, (gs or 1.0) - 0.5))
    except Exception as e:
        log(f"[ocr] readout sidecar failed: {type(e).__name__}: {e}", logfile)
        return None
    if not res.timeline:
        return None
    base = gs if gs is not None else res.fight_start_s
    off = round(res.fight_start_s - base, 2)        # first readable readout, game-secs
    rows = [{"game_s": round(r["t"] + off, 2),
             "side1": {"count": r["s1"], "hp": r["s1"]},
             "side2": {"count": r["s2"], "hp": r["s2"]}} for r in res.timeline]
    _zero_loser_from_banner(rows, out_mov, (res.fight_end_s + 2.0, res.fight_end_s + 5.0),
                            civ1, slug1, civ2, slug2, logfile)
    sidecar = {"video_game_start_s": round(base, 3), "rows": rows,
               "source": "ocr_readout"}
    with open(sidecar_path, "w") as f:
        json.dump(sidecar, f)
    log(f"[ocr] readout sidecar -> {sidecar_path}  (game start +{base:.2f}s, "
        f"{len(rows)} rows, end {res.survivors1}-{res.survivors2})", logfile)
    return sidecar_path


def _zero_loser_from_banner(rows, out_mov, banner_ts, civ1, slug1, civ2, slug2,
                            logfile=None) -> bool:
    """A timeline can end with both sides above zero (a lone-unit chase outliving the
    recording's hold, the last '0' frame unreadable, or decode lag) even though the
    game declared a winner. The WINS hold is the game's OWN verdict — read it from the
    footage (`banner_ts` = candidate video times), match the winner's name and append a
    row zeroing the loser, so the bar and the end card show the wipe. Returns True if
    a correction was applied."""
    if not rows or min(rows[-1]["side1"]["count"], rows[-1]["side2"]["count"]) <= 0:
        return False
    try:
        import re
        from overlay.video_extract import read_winner_text
        from overlay.overlay_data import get_unit_card
        txt = read_winner_text(out_mov, banner_ts)
        if not txt:
            return False
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
        wn = norm(txt.split("wins")[0])
        n1 = norm(get_unit_card(civ1, slug1)["name"])
        n2 = norm(get_unit_card(civ2, slug2)["name"])
        win = 1 if n1 in wn and n2 not in wn else 2 if n2 in wn and n1 not in wn else 0
        if not win:
            return False
        loser, keep = ("side2", "side1") if win == 1 else ("side1", "side2")
        last = rows[-1]
        rows.append({"game_s": round(last["game_s"] + 1.0, 2),
                     keep: dict(last[keep]), loser: {"count": 0, "hp": 0}})
        log(f"[sidecar] WINS banner says side {win} won — zeroed the loser's count "
            f"(was {last[loser]['count']})", logfile)
        return True
    except Exception as e:
        log(f"[sidecar] banner correction skipped: {type(e).__name__}: {e}", logfile)
        return False


def select_sidecar(out_mov, gs, grpc_sidecar, civ1, slug1, civ2, slug2, counts,
                   ocr_path, final, reuse_ocr=False, logfile=None):
    """Choose the overlay timeline. Returns (sidecar_path, source_tag).

    DEFAULT: the gRPC redecode sidecar — exact game data, zero OCR cost — when it
    passes hp_merge.grpc_sane's structural gate, anchored on the pixel-detected V0.
    FALLBACK (or AOE2_GRPC_PRIMARY=0): the OCR readout sidecar, upgraded with gRPC
    true HP via the correlation merge when the two series agree.
    History: a live cross-check (Guecha vs Jaguar, 2026-06) caught the redecoded curve
    "stretched ~1.9x" — that was TWO stacked faults, both fixed 2026-06-10: the 178524
    delta decoder lost/oversat on deaths (apply_patch now re-anchors instead of
    byte-stepping; 24/24 deaths timed, was 23 untimed), and the stream clock is
    GAME-SIM time at game speed 1.7x (write_sidecar now converts to video seconds —
    the clock="video" stamp below guards against pre-fix sidecars). Validated vs
    footage: offline rmse 0.43 (was 2.47), then a fresh live run merged at rmse 0.41 /
    offset +0.10s with the loser's end count agreeing exactly (0-25)."""
    import json
    if (grpc_sidecar and Path(grpc_sidecar).exists()
            and os.environ.get("AOE2_GRPC_PRIMARY", "1").lower() not in ("0", "false", "no")):
        try:
            from overlay.hp_merge import grpc_sane
            with open(grpc_sidecar) as f:
                d = json.load(f)
            if d.get("clock") != "video":
                log("[sidecar] gRPC sidecar predates the clock fix (game-sim seconds) "
                    "— OCR fallback", logfile)
            elif grpc_sane(d, counts):
                if gs is not None:
                    d["video_game_start_s"] = round(gs, 3)     # V0 anchors the game clock
                d["source"] = "grpc_redecode"
                # the game's WINS verdict still rules the END state (decode/chase can
                # leave the loser hanging above zero)
                prev, last_chg = None, d["rows"][0]["game_s"]
                for r in d["rows"]:
                    cur = (r["side1"]["count"], r["side2"]["count"])
                    if prev is not None and cur != prev:
                        last_chg = r["game_s"]
                    prev = cur
                vs = d.get("video_game_start_s") or 0.0
                _zero_loser_from_banner(d["rows"], out_mov,
                                        (vs + last_chg + 2.0, vs + last_chg + 5.0),
                                        civ1, slug1, civ2, slug2, logfile)
                out = str(Path(final).with_suffix("")) + ".grpc.hp.json"
                with open(out, "w") as f:
                    json.dump(d, f)
                log("[sidecar] gRPC redecode is SANE — overlay uses exact game data, "
                    "OCR pass skipped", logfile)
                return out, "grpc"
            else:
                log("[sidecar] gRPC sidecar failed the sanity gate — OCR fallback", logfile)
        except Exception as e:
            log(f"[sidecar] gRPC check failed ({type(e).__name__}: {e}) — OCR fallback",
                logfile)
    if reuse_ocr and Path(ocr_path).exists():
        ocr_sidecar = str(ocr_path)
    else:
        ocr_sidecar = build_ocr_sidecar(out_mov, civ1, slug1, civ2, slug2, counts, gs,
                                        str(ocr_path), logfile)
    if not ocr_sidecar:
        if grpc_sidecar and Path(grpc_sidecar).exists():
            return str(grpc_sidecar), "grpc-unverified"        # last resort
        return None, None
    use, src = ocr_sidecar, "ocr"
    if grpc_sidecar and Path(grpc_sidecar).exists():
        try:
            from overlay.hp_merge import merge_sidecars
            merged = merge_sidecars(ocr_sidecar, grpc_sidecar,
                                    str(Path(final).with_suffix("")) + ".merged.hp.json",
                                    logfn=lambda m: log(m, logfile))
            if merged:
                use, src = merged, "ocr+grpc"
        except Exception as e:
            log(f"[hp-merge] skipped: {type(e).__name__}: {e}", logfile)
    return use, src


def compose_live_overlay(civ1, slug1, civ2, slug2, out_mov, final,
                         copy_to=None, name=None, lead_in=0.0, counts=(30, 30),
                         raw_copy_to=None, sidecar=None, logfile=None) -> Path:
    """NEW single-clip compose (no separate intro/outro card screens): the unit DETAIL
    cards are overlaid LIVE over the opening of the real fight footage, with a TOP draining
    army-HP bar throughout, ramped to ~20s (10s @1x + 5s fast + 5s @1x). Archives the RAW
    recording and copies the result + sidecar out, exactly like compose_recap."""
    from overlay.overlay_data import get_unit_card
    from overlay.compose import make_live_overlay_video
    gs = detect_game_start(out_mov)
    if gs is not None:
        lead_in = gs + PATROL_LEAD
    # sidecar preference: sane gRPC redecode (exact, no OCR) > OCR readout (+HP merge)
    use_sidecar, src = select_sidecar(
        out_mov, gs, sidecar, civ1, slug1, civ2, slug2, counts,
        str(Path(final).with_suffix("")) + ".ocr.hp.json", final, logfile=logfile)
    log(f"[compose-live] game_start={gs}  lead_in={lead_in:.1f}  sidecar={src}"
        f"  -> live detail-card overlay + top HP bar ...", logfile)
    u1 = get_unit_card(civ1, slug1)
    u2 = get_unit_card(civ2, slug2)
    out = make_live_overlay_video(u1, u2, final, out_mov, use_sidecar, lead_in=lead_in,
                                  counts=counts, size=(platform_io.OUT_W, platform_io.OUT_H))
    log(f"[compose-live] -> {out} ({Path(out).stat().st_size // 1024} KB)", logfile)
    archive_raw(out_mov, raw_copy_to, name or Path(out).name, logfile)
    dest = copy_out(out, copy_to, name, logfile)
    # ship the sidecar that actually drove the overlay next to the delivered video
    if use_sidecar:
        try:
            import shutil
            sc_dest = str(Path(dest).with_suffix("")) + ".hp.json"
            shutil.copy2(use_sidecar, sc_dest)
            log(f"[compose-live] sidecar ({src}) -> {sc_dest}", logfile)
        except Exception as e:
            log(f"[compose-live] sidecar copy failed: {e}", logfile)
    return dest


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
