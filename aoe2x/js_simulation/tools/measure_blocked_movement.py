"""Step 1 (corrected): does a screened attacker detour, slow down, or stall?

Reference direction is the unit's live combat target, which is what a melee
unit actually steers at. For each moving frame we ask whether the straight
line to that target is obstructed by another body, and what the unit does.
"""
import collections
import json
import math
import statistics

SP = "C:/Users/ddk22/AppData/Local/Temp/claude/D--AI-aoe2-matchup/" \
     "1bb1b353-ae0a-4383-b95f-37a4f05b5e52/scratchpad/"
UNITS = {
    "PALADIN": dict(dir=SP + "pal_trace/", master=569, half=0.25, speed=1.4850000321865082),
    "CHAMPION": dict(dir=SP, master=567, half=0.20, speed=1.0560000228881836),
}
TAGS = [t for r in ["2v3", "5v3", "6v3"] for t in (r, f"{r}_r2", f"{r}_r3")]
ST_MOVE = 4


def load(path, master):
    by = collections.defaultdict(list)
    try:
        fh = open(path)
    except FileNotFoundError:
        return None, None
    for line in fh:
        r = json.loads(line)
        if r.get("master") not in (None, master):
            continue
        by[r["id"]].append(r)
    frames = collections.defaultdict(list)
    for s in by.values():
        s.sort(key=lambda r: r["t_ms"])
        for r in s:
            frames[r["t_ms"]].append(r)
    return by, dict(sorted(frames.items()))


def blocks_segment(px, py, tx, ty, bx, by_, pad):
    """Does an axis-aligned box of half-extent `pad` at (bx,by_) straddle the
    segment p->t, between the endpoints?"""
    dx, dy = tx - px, ty - py
    seg = math.hypot(dx, dy)
    if seg < 1e-9:
        return False
    t = ((bx - px) * dx + (by_ - py) * dy) / (seg * seg)
    if t <= 0.05 or t >= 0.95:
        return False
    cx, cy = px + t * dx, py + t * dy
    return abs(bx - cx) <= pad and abs(by_ - cy) <= pad


def analyse(label, cfg):
    half = cfg["half"]
    rows = {"clear": [], "screened": []}
    stall = {"clear": [0, 0], "screened": [0, 0]}
    for tag in TAGS:
        by, frames = load(f"{cfg['dir']}{tag}.tape_trace.jsonl", cfg["master"])
        if not by:
            continue
        for uid, s in by.items():
            for i in range(1, len(s)):
                a, b = s[i - 1], s[i]
                if (b.get("hp") or 0) <= 0 or b.get("action_state") != ST_MOVE:
                    continue
                tgt = b.get("target_id")
                if tgt in (None, -1):
                    continue
                peers = [p for p in frames[b["t_ms"]]
                         if p["id"] != uid and (p.get("hp") or 0) > 0]
                target = next((p for p in peers if p["id"] == tgt), None)
                if target is None:
                    continue
                gap = max(abs(b["x"] - target["x"]), abs(b["y"] - target["y"]))
                if gap < 2 * half + 0.25:      # already at the target
                    continue
                blockers = [p for p in peers if p["id"] != tgt and blocks_segment(
                    b["x"], b["y"], target["x"], target["y"], p["x"], p["y"], 2 * half)]
                kind = "screened" if blockers else "clear"
                dt = (b["t_ms"] - a["t_ms"]) / 1000
                if dt <= 0:
                    continue
                vx, vy = b["x"] - a["x"], b["y"] - a["y"]
                speed = math.hypot(vx, vy) / dt
                stall[kind][1] += 1
                if speed < 0.05:
                    stall[kind][0] += 1
                    continue
                dgx, dgy = target["x"] - b["x"], target["y"] - b["y"]
                dev = math.degrees(abs(math.atan2(
                    vx * dgy - vy * dgx, vx * dgx + vy * dgy)))
                rows[kind].append((speed / cfg["speed"], dev))

    print(f"\n===== {label} =====")
    for kind in ("clear", "screened"):
        v = rows[kind]
        stalled, total = stall[kind]
        if not v:
            print(f"  {kind:9}: no samples")
            continue
        sp = [x[0] for x in v]
        dv = [x[1] for x in v]
        big = sum(1 for d in dv if d > 30)
        print(f"  {kind:9}: moving frames={total:5d}  stalled={stalled:5d} "
              f"({100*stalled/total:4.1f}%)")
        print(f"             speed/top  median={statistics.median(sp):.3f} "
              f"mean={statistics.mean(sp):.3f}")
        print(f"             heading deviation from target: "
              f"median={statistics.median(dv):5.1f} deg  "
              f">30 deg in {100*big/len(dv):4.1f}% of frames")


for label, cfg in UNITS.items():
    analyse(label, cfg)
