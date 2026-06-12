"""order_misses.py REPLAY LABELS END_MIN -- list the EXACT units missed in the
creation-order alignment (true units not in the LCS of FIFO-order vs true-order)."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import defaultdict, Counter
import mgz.model, unit_classifier as uc, eval_against_truth as E

REPLAY, LABELS, END_MIN = sys.argv[1], sys.argv[2], float(sys.argv[3])
CUT = (END_MIN - 5) * 60
labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
ctx = uc._run(mt)
no = defaultdict(Counter)
for cid, g in ctx.guesses.items():
    if g.player and str(cid) in labels:
        no[g.player][labels[str(cid)].get("owner")] += 1
op = {c.most_common(1)[0][0]: nm for nm, c in no.items()}


def milt(t, truth, milonly):
    c = E.canon_truth(t) if truth else E.canon_pred(t)
    if E.coarse(c) == "military":
        return c
    if not milonly and c == "villager":
        return "villager"
    return None


def lcs_backtrack(F, T):
    n, m = len(F), len(T)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if F[i - 1] == T[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    matchedT = set()
    i, j = n, m
    while i > 0 and j > 0:
        if F[i - 1] == T[j - 1] and dp[i][j] == dp[i - 1][j - 1] + 1:
            matchedT.add(j - 1); i -= 1; j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return matchedT


def run(owner, milonly):
    nm = op[owner]
    true = sorted((u["created_ms"] / 1000.0, milt(u.get("type"), True, milonly), u.get("type"))
                  for u in labels.values()
                  if u.get("owner") == owner and u.get("created_ms") and u.get("model_type") != 14
                  and u["created_ms"] / 1000 < CUT and milt(u.get("type"), True, milonly))
    fifo = [(t, milt(ty, False, milonly)) for t, ty in sorted(ctx.prod_mil.get(nm, []) if milonly else ctx.prod_full.get(nm, []))
            if t < CUT and milt(ty, False, milonly)]
    T = [x[1] for x in true]
    F = [x[1] for x in fifo]
    matched = lcs_backtrack(F, T)
    misses = [(true[j][0], true[j][1], true[j][2]) for j in range(len(T)) if j not in matched]
    kind = "MILITARY" if milonly else "ALL"
    print(f"\n=== {nm} [{kind}] — {len(misses)} of {len(T)} units missed in order ===")
    for tm_, ttok, tname in misses:
        # what the FIFO had around that spawn time
        near = [ty for t, ty in fifo if abs(t - tm_) <= 12]
        print(f"   {tm_/60:5.1f}m  TRUE={tname:18}({ttok})   FIFO nearby: {near}")


for owner in sorted(op):
    run(owner, True)
for owner in sorted(op):
    run(owner, False)
