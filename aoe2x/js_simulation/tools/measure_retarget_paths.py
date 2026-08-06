"""Does a unit retarget when the PATH to its target gets too long?

Hypothesis: units continuously evaluate the route to their target, routing
around allies and enemies. When that route becomes long relative to the direct
line -- which is what happens as a melee gets dense -- the unit gives up and
picks a target it can actually reach. That would explain both the density
dependence (2-4 unit fights never retarget) and why 60% of switches go to a
target that is FARTHER in a straight line.

Test: at each voluntary switch, run a real grid A* over the occupied cells and
compare the OLD target's path against the NEW target's path.
"""
import collections
import glob
import heapq
import json
import math
import statistics

CH, PA = 567, 569
HALF = {CH: 0.20, PA: 0.25}
CELL = 0.25
PAD = 3.0
SQRT2 = math.sqrt(2)


def build_grid(frame, mover_id, exclude_ids):
    xs = [u["x"] for u in frame.values()]
    ys = [u["y"] for u in frame.values()]
    x0, x1 = min(xs) - PAD, max(xs) + PAD
    y0, y1 = min(ys) - PAD, max(ys) + PAD
    w = int((x1 - x0) / CELL) + 1
    h = int((y1 - y0) / CELL) + 1
    blocked = bytearray(w * h)
    for uid, u in frame.items():
        if uid == mover_id or uid in exclude_ids:
            continue
        if (u.get("hp") or 0) <= 0:
            continue
        r = HALF[u["master"]]
        ci0 = max(0, int((u["x"] - r - x0) / CELL))
        ci1 = min(w - 1, int((u["x"] + r - x0) / CELL))
        cj0 = max(0, int((u["y"] - r - y0) / CELL))
        cj1 = min(h - 1, int((u["y"] + r - y0) / CELL))
        for j in range(cj0, cj1 + 1):
            base = j * w
            for i in range(ci0, ci1 + 1):
                blocked[base + i] = 1
    return blocked, w, h, x0, y0


def cell_of(x, y, x0, y0, w, h):
    return (min(w - 1, max(0, int((x - x0) / CELL))),
            min(h - 1, max(0, int((y - y0) / CELL))))


def astar(blocked, w, h, start, goal):
    if start == goal:
        return 0.0
    sx, sy = start
    gx, gy = goal
    dist = {start: 0.0}
    pq = [(0.0, start)]
    NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2)]
    seen = set()
    while pq:
        f, cur = heapq.heappop(pq)
        if cur in seen:
            continue
        seen.add(cur)
        if cur == goal:
            return dist[cur] * CELL
        cx, cy = cur
        g = dist[cur]
        for dx, dy, cost in NB:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            nxt = (nx, ny)
            if nxt in seen:
                continue
            if blocked[ny * w + nx] and nxt != goal:
                continue
            ng = g + cost
            if ng < dist.get(nxt, 1e18):
                dist[nxt] = ng
                heapq.heappush(pq, (ng + math.hypot(gx - nx, gy - ny), nxt))
    return None


def main():
    rows = []
    for d in ["cvc", "pvp", "cvp92"]:
        for path in sorted(glob.glob(f"{d}/*.tape_trace.jsonl")):
            by = collections.defaultdict(list)
            frames = collections.defaultdict(dict)
            with open(path) as fh:
                for line in fh:
                    r = json.loads(line)
                    if r.get("master") in (CH, PA):
                        by[r["id"]].append(r)
                        frames[r["t_ms"]][r["id"]] = r
            for s in by.values():
                s.sort(key=lambda r: r["t_ms"])
            death = {}
            for uid, s in by.items():
                for r in s:
                    if r.get("hp") is not None and r["hp"] <= 0:
                        death[uid] = r["t_ms"]
                        break
            times = sorted(frames)
            tidx = {t: i for i, t in enumerate(times)}
            for uid, s in by.items():
                cur = None
                for r in s:
                    if r.get("hp") is not None and r["hp"] <= 0:
                        break
                    t = r.get("target_id")
                    if t in (None, -1, 0):
                        t = None
                    if t is not None and t != cur:
                        if cur is not None:
                            dd = death.get(cur)
                            if dd is None or r["t_ms"] < dd - 100:
                                i = tidx.get(r["t_ms"], 0)
                                F = frames[times[max(0, i - 1)]]
                                me, old, new = F.get(uid), F.get(cur), F.get(t)
                                if me and old and new:
                                    g, w, h, x0, y0 = build_grid(F, uid, {cur, t})
                                    c = cell_of(me["x"], me["y"], x0, y0, w, h)
                                    po = astar(g, w, h, c,
                                               cell_of(old["x"], old["y"], x0, y0, w, h))
                                    pn = astar(g, w, h, c,
                                               cell_of(new["x"], new["y"], x0, y0, w, h))
                                    eo = math.hypot(old["x"] - me["x"], old["y"] - me["y"])
                                    en = math.hypot(new["x"] - me["x"], new["y"] - me["y"])
                                    rows.append((po, pn, eo, en))
                        cur = t
    ok = [r for r in rows if r[0] is not None and r[1] is not None]
    print(f"{len(rows)} voluntary switches, {len(ok)} with a path to both targets\n")

    unreach_old = sum(1 for r in rows if r[0] is None)
    print(f"  OLD target unreachable at the switch : {unreach_old}/{len(rows)}"
          f"  ({unreach_old / len(rows) * 100:.0f}%)")
    print(f"  NEW target unreachable               : "
          f"{sum(1 for r in rows if r[1] is None)}/{len(rows)}\n")

    closer_line = sum(1 for r in ok if r[3] < r[2])
    closer_path = sum(1 for r in ok if r[1] < r[0])
    print(f"  new target closer in a STRAIGHT LINE : {closer_line}/{len(ok)}"
          f"  ({closer_line / len(ok) * 100:.0f}%)")
    print(f"  new target closer by PATH            : {closer_path}/{len(ok)}"
          f"  ({closer_path / len(ok) * 100:.0f}%)")

    flip = [r for r in ok if r[3] >= r[2] and r[1] < r[0]]
    print(f"\n  farther in a line BUT closer by path : {len(flip)}"
          f"  ({len(flip) / len(ok) * 100:.0f}% of all switches)")

    det_old = [r[0] / r[2] for r in ok if r[2] > 0.3]
    det_new = [r[1] / r[3] for r in ok if r[3] > 0.3]
    print(f"\n  detour factor (path / straight line)")
    print(f"     OLD target at the switch : median {statistics.median(det_old):.2f}")
    print(f"     NEW target chosen        : median {statistics.median(det_new):.2f}")


if __name__ == "__main__":
    main()
