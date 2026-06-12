"""compare_order.py REPLAY LABELS END_MIN -- accuracy of the reconstructed unit-CREATION
ORDER (.aoe2record FIFO+multiqueue+train-time+unqueue) vs the gRPC true created_ms order,
per player. Reports count accuracy, order accuracy (LCS), spawn-time accuracy, and a
timeseries cross-check, and localises WHERE the model diverges."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter, defaultdict
import bisect
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY, LABELS, END_MIN = sys.argv[1], sys.argv[2], float(sys.argv[3])
labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
ctx = uc._run(mt)

# owner number -> player name (majority vote via classifier attribution)
name_owner = defaultdict(Counter)
for cid, g in ctx.guesses.items():
    if g.player and str(cid) in labels:
        name_owner[g.player][labels[str(cid)].get("owner")] += 1
owner_player = {}
for nm, cnt in name_owner.items():
    owner_player[cnt.most_common(1)[0][0]] = nm


def tok(name_or_token, is_truth):
    """Map to the shared canonical military token; villager collapsed; '' if not a real unit."""
    if is_truth:
        if not name_or_token or name_or_token.startswith("id") or name_or_token.lower() == "flare":
            return ""
        c = E.canon_truth(name_or_token)
    else:
        c = E.canon_pred(name_or_token)
    return c if c in ("villager",) or E.coarse(c) == "military" else ""


def lcs_len(a, b):
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        ai = a[i - 1]
        for j in range(1, m + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else (prev[j] if prev[j] >= cur[j - 1] else cur[j - 1])
        prev = cur
    return prev[m]


def analyze(owner, military_only):
    nm = owner_player.get(owner, f"owner{owner}")
    # TRUE creation order from gRPC (created_ms), real produced units only (exclude start=0)
    true = []
    for k, u in labels.items():
        if u.get("owner") != owner or u.get("model_type") == 14:
            continue
        if not u.get("created_ms"):
            continue
        t = tok(u.get("type"), True)
        if not t or (military_only and t == "villager"):
            continue
        true.append((u["created_ms"] / 1000.0, t))
    true.sort()
    # RECONSTRUCTED order from .aoe2record FIFO
    src = ctx.prod_mil if military_only else ctx.prod_full
    fifo = []
    for ti, ty in sorted(src.get(nm, [])):
        t = tok(ty, False)
        if not t or (military_only and t == "villager"):
            continue
        fifo.append((ti, t))
    return nm, true, fifo


def report(owner, military_only, cut_min):
    nm, true, fifo = analyze(owner, military_only)
    cut = cut_min * 60
    trueW = [(t, ty) for t, ty in true if t < cut]
    fifoW = [(t, ty) for t, ty in fifo if t < cut]
    T = [ty for _, ty in trueW]
    F = [ty for _, ty in fifoW]
    kind = "MILITARY" if military_only else "ALL (vil+mil)"
    print(f"\n=== {nm}  [{kind}]  (spawned < {cut_min:.1f}m) ===")
    print(f"  count: FIFO {len(F)} vs TRUE {len(T)}  (diff {len(F)-len(T):+d})")
    tc, fc = Counter(T), Counter(F)
    rows = sorted(set(tc) | set(fc), key=lambda x: -tc.get(x, 0))
    print(f"  {'type':14}{'TRUE':>6}{'FIFO':>6}{'  diff':>7}")
    for r in rows:
        d = fc.get(r, 0) - tc.get(r, 0)
        print(f"  {r:14}{tc.get(r,0):6}{fc.get(r,0):6}{('  '+f'{d:+d}') if d else '   ok':>7}")
    l = lcs_len(F, T)
    print(f"  ORDER accuracy (LCS of FIFO-order vs TRUE-order): {l}/{len(T)} = {100*l/max(len(T),1):.1f}%")
    # spawn-time accuracy: align each true unit to the nearest unclaimed same-type FIFO slot
    used = [False] * len(fifoW)
    diffs = []
    fbytype = defaultdict(list)
    for idx, (t, ty) in enumerate(fifoW):
        fbytype[ty].append(idx)
    for tt, ty in trueW:
        best = None; bd = 1e18
        for idx in fbytype.get(ty, []):
            if used[idx]:
                continue
            d = abs(fifoW[idx][0] - tt)
            if d < bd:
                bd = d; best = idx
        if best is not None:
            used[best] = True
            diffs.append(fifoW[best][0] - tt)
    if diffs:
        ad = sorted(abs(x) for x in diffs)
        print(f"  spawn-time error (same-type matched, n={len(diffs)}): "
              f"median {ad[len(ad)//2]:.0f}s, 90th {ad[int(len(ad)*0.9)]:.0f}s")
    return nm, len(T), len(F), l


print(f"REPLAY {REPLAY.split('/')[-1]}  vs  {LABELS}")
for owner in sorted(owner_player):
    report(owner, True, END_MIN - 5)
    report(owner, False, END_MIN - 5)

# timeseries cross-check (player object-count trajectory vs FIFO cumulative production)
print("\n--- timeseries cross-check (player total_objects increments vs FIFO production) ---")
for owner, nm in owner_player.items():
    ts = ctx.timeseries.get(nm) or []
    inc = 0
    prev = None
    for _, toto in ts:
        if prev is not None and toto > prev:
            inc += toto - prev
        prev = toto if prev is None else max(prev, toto)
    fifo_n = len(ctx.prod_full.get(nm, []))
    finalo = ts[-1][1] if ts else 0
    print(f"  {nm:24} timeseries: peak/last objects~{finalo}, total positive increments {inc}; "
          f"FIFO produced (vil+mil) {fifo_n}")
