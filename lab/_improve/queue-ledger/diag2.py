"""Per-type pred vs truth counts per player + unqueue accounting."""
import sys, types, json, pickle, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger"
UCDIR = os.environ.get("UCDIR", WS)
sys.path[:0] = [UCDIR, "C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
if UCDIR != WS:
    sys.path.insert(1, WS)  # still need cache; uc comes from UCDIR
from collections import Counter, defaultdict
import unit_classifier as uc
import eval_against_truth as E

key = sys.argv[1] if len(sys.argv) > 1 else "g0"
GAMES = {
    "g0": dict(labels=r"C:\dev\aoe2\aoe2record\lab\labels.json"),
    "train": dict(labels=r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"),
}
mt = pickle.load(open(os.path.join(WS, f"match_cache_{key}.pkl"), "rb"))
labels = json.load(open(GAMES[key]["labels"]))
ctx = uc._run(mt)

for p in mt.players:
    pname = p.name
    tr = Counter()
    for k, u in labels.items():
        if u.get("owner") != p.number:
            continue
        nm = u.get("type") or ""
        if not nm or nm.lower() == "flare" or nm.startswith("id"):
            continue
        tok = E.canon_truth(nm)
        if E.coarse(tok) != "military":
            continue
        tr[tok] += 1
    pr = Counter(E.canon_pred(u) for _, u in ctx.prod_mil.get(pname, []))
    print(f"\n== {pname} (civ={ctx.civ.get(pname)}) truth={sum(tr.values())} pred={sum(pr.values())}")
    for tok in sorted(set(tr) | set(pr)):
        d = pr[tok] - tr[tok]
        print(f"   {tok:18} truth={tr[tok]:3} pred={pr[tok]:3}  {'+' if d>0 else ''}{d}")

# unqueue accounting
print("\n-- unqueues per building owner --")
uq = Counter()
for b, lst in ctx.unqueues.items():
    uq[ctx.owner.get(b)] += len(lst)
print(dict(uq))
print("resign:", dict(ctx.resign), "end_t:", ctx.end_t)
