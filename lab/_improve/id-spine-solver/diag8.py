"""diag8.py [g0|train] -- for every FIFO-snap candidate (refine_military stage-3
logic), compute excess = PT[k] - ub(cid) and whether the snap type matches truth.
Gives the separation curve for UB_SNAP_TOL.
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)
from collections import Counter
import unit_classifier as uc
assert uc.__file__.startswith(WORK)
import eval_against_truth as E
import mgz.model
import bisect

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}
key = sys.argv[1] if len(sys.argv) > 1 else "g0"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
weight = uc.cocommand_graph(ctx)
uc.propagate_class(ctx, weight)
uc.production_timeline(ctx)
squads = uc.form_squads(ctx, weight)
matched = uc.align_production(ctx)

truth_tok = {}
for k, u in labels.items():
    t = E.canon_truth(u.get("type") or "")
    if E.coarse(t) in ("villager", "military"):
        truth_tok[int(k)] = t

ubf = uc._ub_fn(ctx)
TOL = 4.0
rows = []
players = set(ctx.guesses[c].player for c in matched)
for player in players:
    pm = sorted(ctx.prod_mil.get(player, []))
    PT = [t for t, _ in pm]
    PU = [u for _, u in pm]
    if not PT:
        continue
    iso = [min((abs(PT[x] - PT[k]) for x in range(len(PT)) if PU[x] != PU[k]),
               default=float("inf")) for k in range(len(PT))]
    for c in matched:
        if ctx.guesses[c].player != player or c not in truth_tok:
            continue
        fs = ctx.guesses[c].behavior.get("first_seen")
        if fs is None:
            continue
        k = bisect.bisect_right(PT, fs + TOL) - 1
        if 0 <= k < len(PU) and iso[k] >= 14.0:
            excess = PT[k] - ubf(c)
            ok = E.canon_pred(PU[k]) == truth_tok[c]
            rows.append((excess, ok, c, PU[k], truth_tok[c]))

rows.sort()
n_ok = sum(1 for r in rows if r[1])
n_bad = len(rows) - n_ok
print(f"[{key}] snap candidates with truth: {len(rows)}  ok={n_ok} bad={n_bad}")
print(" excess(PT[k]-ub) distribution:")
for excess, ok, c, pu, tt in rows:
    if excess > 0:
        print(f"   excess={excess:7.1f} {'OK ' if ok else 'BAD'} id={c:6} snap={pu:15} truth={tt}")
# cumulative: if gate at X, how many ok lost vs bad killed
print("\n gate sweep (reject snap when excess > X):")
for X in (5, 10, 15, 20, 25, 30, 40, 60, 90, 150, 1e9):
    ok_lost = sum(1 for e, ok, *_ in rows if ok and e > X)
    bad_kill = sum(1 for e, ok, *_ in rows if not ok and e > X)
    print(f"   X={X:6}: ok_lost={ok_lost:3} bad_killed={bad_kill:3}")
