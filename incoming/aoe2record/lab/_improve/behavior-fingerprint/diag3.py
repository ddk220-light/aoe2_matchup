"""Speed-estimate separability test: commanded-position displacement rates."""
import math
from collections import defaultdict

u = reload_uc()


def speed_est(track):
    """Median of per-segment implied speeds for long, slow segments."""
    vs = []
    for (t1, x1, y1), (t2, x2, y2) in zip(track, track[1:]):
        dt = t2 - t1
        d = math.hypot(x2 - x1, y2 - y1)
        if dt >= 8 and d >= 8:
            vs.append(d / dt)
    if not vs:
        return None, 0
    vs.sort()
    return vs[len(vs) // 2], len(vs)


for game in ("g0", "train"):
    ctx = u._run(MTS[game])
    tn = {int(k): v.get("type") for k, v in LBL[game].items()}
    rows = defaultdict(list)
    for cid, g in ctx.guesses.items():
        tr = g.behavior.get("move_track") or []
        v, n = speed_est(tr)
        t = tn.get(cid)
        if v is not None and t:
            rows[t].append((round(v, 2), n))
    print(f"=== {game}: median implied speed by truth type ===")
    for t in sorted(rows):
        vs = sorted(v for v, n in rows[t])
        med = vs[len(vs) // 2]
        print(f"  {t:18} n={len(vs):3} med={med:.2f} all={vs[:14]}")
