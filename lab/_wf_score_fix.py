r"""_wf_score_fix.py — validation scorer for the apply_patch delta-decoder fix.

Decodes the Guecha-vs-Jaguar ground-truth dump with the CURRENT decode_state_v2
module (fresh import every run: run this script as its own process; it never
caches decoder state across runs) and scores the reconstructed side1 count curve
against the footage-OCR ground truth. Also reruns the run1 regression.

Death reconstruction (END-OF-STREAM authority, NOT last-snapshot authority —
the fight segment contains exactly ONE snapshot, at t=0, so snapshot authority
sees zero deaths by construction):
  * a seeded army unit is DEAD iff at end of the fight stream it is absent from
    entity_store OR its HP value is numeric and <= 0;
  * death_time = the time of its LAST decoded present->absent transition
    (removal op) if any, else its LAST delta HP-change time, else None (UNTIMED).
  * UNTIMED dead units never decrement pred(t) — they die at +infinity. This
    keeps the rmse honest: a decoder that loses death events scores badly.

pred(t) = 24 - #(timed side1 deaths with death_time <= t), evaluated at
(t_ocr + offset) for one rigid offset solved over [-2.0, +2.0] in 0.1 steps
(offset > 0 means decoded events run LATER than the footage clock).

Fight-segment selection: reseed on every patch > 400 KB; the fight is the
LATEST snapshot whose derived army is exactly 24 (owner 2) vs 30 (owner 3).
The segment ends at a foreign snapshot, a game-clock reset (> 2 s backwards),
or end of file — whichever comes first; authority state is frozen there.

run1 regression: subprocess redecode_hp.py on C:\dev\aoe2\aoe2record\lab\run1 and require
side1 to reach 0 at game_s in [18, 24] with 20-30 side2 survivors at the end.

Usage (cwd C:\dev\aoe2\aoe2record\lab, system python with grpcio/protobuf):
  "C:\Users\ddk22\AppData\Local\Programs\Python\Python312\python.exe" _wf_score_fix.py
  [optional argv1 = frames prefix (path without .frames.bin); defaults to the
   ground-truth dump]   [optional argv2 = "--no-run1" to skip the regression]

Progress goes to stderr; stdout carries exactly ONE final JSON line:
{"rmse":..., "offset_s":..., "pred_curve":[[t,c],...], "deaths_timed":N,
 "deaths_untimed":N, "side2_end":{"count":..,"hp":..}, "fight_end_s":...,
 "run1_ok":bool, "run1_detail":"..."}
"""
import bisect
import contextlib
import importlib
import io
import json
import math
import os
import struct
import subprocess
import sys

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
importlib.invalidate_caches()
import decode_state_v2 as D          # noqa: E402  (fresh per process run)
import cade_api_pb2 as pb            # noqa: E402

GT_PFX = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
          "\\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
PFX = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else GT_PFX
SKIP_RUN1 = "--no-run1" in sys.argv
TMP = os.path.join(D_DIR, "_wf_score_fix.reseed.bin")

F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = {9, 11, 12}
SCOUT = 448
SNAP_RESEED = 400_000
EXPECT = (24, 30)                    # ground truth: 24 Guecha (owner2) vs 30 Jaguar (owner3)
START1 = EXPECT[0]

# footage-OCR ground truth: (game_s, side1 count) — 11 samples, NEVER drop any
OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]

GAME_SPEED = 1.7  # AoE2:DE sim clock vs video clock; fr.time is game-sim ms


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def derive_army(es):
    army = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != SCOUT
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            army[e.get(F_OWNER)].add(k)
    return army


def read_frames(path):
    """Yield (game_s, patch_bytes_or_None) per frame from a .frames.bin dump."""
    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                return
            ln = struct.unpack("<I", hdr)[0]
            buf = f.read(ln)
            if len(buf) < ln:
                return
            sq = pb.FrameSequence()
            sq.ParseFromString(buf)
            for fr in sq.frame:
                yield fr.time / 1000.0, (fr.patch if fr.patch else None)


class Fight:
    """Tracking state for one candidate fight segment (latest 24v30 snapshot wins)."""

    def __init__(self, t0, doc, es, world_id, army):
        self.t0 = t0
        self.doc, self.es, self.world_id, self.army = doc, es, world_id, army
        self.removals = {}       # key -> [game_s of each present->absent transition]
        self.hp_change = {}      # key -> game_s of last delta HP write that changed HP
        self.last_sec = None
        self.readds = 0          # absent->present transitions (decoder garbage indicator)
        self.final = None        # frozen end-of-stream authority: key -> (present, hp)

    def finalize(self, why, t):
        if self.final is None:
            self.final = {}
            for k in (self.army[2] | self.army[3]):
                e = self.es.get(k)
                self.final[k] = (e is not None, None if e is None else e.get(F_HP))
            log(f"[fight] segment ended ({why}) at game_s {t:.2f}; readds={self.readds}")


def decode_fight(pfx):
    fight = None
    n_seeds = 0
    for t, p in read_frames(pfx + ".frames.bin"):
        if p is not None and len(p) > SNAP_RESEED:
            n_seeds += 1
            with open(TMP, "wb") as sf:
                sf.write(p)
            doc, es = D.Doc(), {}
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink):
                _, world_id = D.seed_from_snapshot(TMP, doc, es)
            a = derive_army(es)
            sizes = (len(a[2]), len(a[3]))
            log(f"[seed #{n_seeds}] t={t:.2f}s patch={len(p):,}B army={sizes[0]}v{sizes[1]}"
                f"  ({' / '.join(l.strip() for l in sink.getvalue().splitlines() if l.strip())})")
            if sizes == EXPECT:
                fight = Fight(t, doc, es, world_id, a)   # latest matching snapshot wins
                log(f"[fight] (re)started at game_s {t:.2f}")
            elif fight is not None:
                fight.finalize("foreign snapshot", t)
            continue
        if fight is None or fight.final is not None or p is None:
            continue
        if fight.last_sec is not None and t < fight.last_sec - 2:
            fight.finalize("clock reset", t)
            continue
        fight.last_sec = t
        allk = fight.army[2] | fight.army[3]
        pre = {k: (k in fight.es, (fight.es.get(k) or {}).get(F_HP)) for k in allk}
        D.apply_patch(fight.doc, p, fight.es, fight.world_id)
        for k in allk:
            was_present, was_hp = pre[k]
            e = fight.es.get(k)
            present = e is not None
            if was_present and not present:
                fight.removals.setdefault(k, []).append(t)
            elif present:
                if not was_present:
                    fight.readds += 1
                hp = e.get(F_HP)
                if hp != was_hp:
                    fight.hp_change[k] = t
    if fight is not None:
        fight.finalize("end of stream", fight.last_sec if fight.last_sec is not None
                       else fight.t0)
    return fight


def side1_deaths(fight):
    """Returns (sorted timed death times, untimed dead count) for side1, with
    END-OF-STREAM authority."""
    timed, untimed = [], 0
    for k in fight.army[2]:
        present, hp = fight.final[k]
        dead = (not present) or (isinstance(hp, (int, float)) and hp <= 0)
        if not dead:
            continue
        if fight.removals.get(k):
            timed.append(fight.removals[k][-1])
        elif k in fight.hp_change:
            timed.append(fight.hp_change[k])
        else:
            untimed += 1
    timed.sort()
    return timed, untimed


def solve_offset(timed):
    """Best rigid offset in [-2.0, +2.0], 0.1 steps. pred is sampled at
    (t_ocr + offset). Ties prefer the smaller |offset|."""
    def pred(t):
        return START1 - bisect.bisect_right(timed, t)
    best_rmse, best_off = None, None
    for i in range(-20, 21):
        off = i / 10.0
        se = sum((pred(t + off) - c) ** 2 for t, c in OCR_S1)
        rmse = math.sqrt(se / len(OCR_S1))
        if (best_rmse is None or rmse < best_rmse - 1e-12
                or (abs(rmse - best_rmse) <= 1e-12 and abs(off) < abs(best_off))):
            best_rmse, best_off = rmse, off
    return best_rmse, best_off


def run1_regression():
    if SKIP_RUN1:
        return False, "skipped (--no-run1)"
    try:
        cp = subprocess.run(
            [sys.executable, os.path.join(D_DIR, "redecode_hp.py"),
             os.path.join(D_DIR, "run1")],
            cwd=D_DIR, capture_output=True, text=True, timeout=570)
        if cp.returncode != 0:
            return False, f"redecode_hp.py rc={cp.returncode}: {cp.stderr.strip()[:160]}"
        rows = []
        with open(os.path.join(D_DIR, "run1.hp_log.jsonl")) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        if not rows:
            return False, "run1.hp_log.jsonl is empty"
        t_zero = next((r["game_s"] for r in rows if r["side1"]["count"] == 0), None)
        last = rows[-1]
        s2c, s2hp = last["side2"]["count"], last["side2"]["hp"]
        start = (rows[0]["side1"]["count"], rows[0]["side2"]["count"])
        ok = (t_zero is not None and 18 <= t_zero <= 24 and 20 <= s2c <= 30)
        detail = (f"start={start[0]}v{start[1]} side1_zero_at_s={t_zero} "
                  f"side2_end={s2c}u/{s2hp}hp (need zero in [18,24], side2 20-30)")
        return ok, detail
    except Exception as e:
        return False, f"run1 regression error: {type(e).__name__}: {str(e)[:140]}"


def main():
    log(f"[scorer] decoding {PFX}.frames.bin with decode_state_v2 from "
        f"{os.path.abspath(D.__file__)}")
    fight = decode_fight(PFX)
    run1_ok, run1_detail = run1_regression()
    log(f"[run1] ok={run1_ok}  {run1_detail}")

    if fight is None:
        out = {"rmse": None, "offset_s": None, "pred_curve": [],
               "deaths_timed": 0, "deaths_untimed": 0,
               "side2_end": None, "fight_end_s": None,
               "run1_ok": run1_ok, "run1_detail": run1_detail,
               "error": "no snapshot in the dump derived a 24v30 army"}
        print(json.dumps(out))
        return

    timed, untimed = side1_deaths(fight)
    # fr.time is game-sim ms at 1.7x speed; OCR timestamps are video seconds.
    timed_video = [t / GAME_SPEED for t in timed]
    rmse, off = solve_offset(timed_video)

    curve = [[round(fight.t0, 2), START1]]
    for i, t in enumerate(timed):
        curve.append([round(t, 2), START1 - i - 1])
    fight_end_s = round(timed[-1], 2) if len(timed) == START1 else None

    s2c, s2hp = 0, 0.0
    for k in fight.army[3]:
        present, hp = fight.final[k]
        if present and isinstance(hp, (int, float)) and hp > 0:
            s2c += 1
            s2hp += hp

    log(f"[score] side1 dead={len(timed) + untimed}/24 (timed={len(timed)}, "
        f"untimed={untimed})  rmse={rmse:.4f} at offset {off:+.1f}s  "
        f"fight_end_s={fight_end_s}")
    out = {"rmse": round(rmse, 4), "offset_s": round(off, 1),
           "pred_curve": curve,
           "deaths_timed": len(timed), "deaths_untimed": untimed,
           "side2_end": {"count": s2c, "hp": round(s2hp, 1)},
           "fight_end_s": fight_end_s,
           "clock_scale": GAME_SPEED,
           "fight_end_video_s": (round(timed[-1] / GAME_SPEED, 2)
                                 if len(timed) == START1 else None),
           "run1_ok": run1_ok, "run1_detail": run1_detail}
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
