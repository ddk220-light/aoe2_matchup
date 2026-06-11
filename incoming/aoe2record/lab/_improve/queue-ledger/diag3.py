"""Histogram truth spawns vs predicted completions per type for one player."""
import sys, types, json, pickle, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger"
sys.path[:0] = [WS, "C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter, defaultdict
import unit_classifier as uc
import eval_against_truth as E

key = sys.argv[1] if len(sys.argv) > 1 else "g0"
pname = sys.argv[2] if len(sys.argv) > 2 else "ddk220"
GAMES = {"g0": r"C:\dev\aoe2\aoe2record\lab\labels.json",
         "train": r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"}
mt = pickle.load(open(os.path.join(WS, f"match_cache_{key}.pkl"), "rb"))
labels = json.load(open(GAMES[key]))
ctx = uc._run(mt)
pnum = {p.name: p.number for p in mt.players}[pname]

tr = defaultdict(list)
for k, u in labels.items():
    if u.get("owner") != pnum:
        continue
    nm = u.get("type") or ""
    if not nm or nm.lower() == "flare" or nm.startswith("id"):
        continue
    tok = E.canon_truth(nm)
    if E.coarse(tok) != "military":
        continue
    tr[tok].append((u.get("created_ms") or 0) / 1000)
pr = defaultdict(list)
for t, u in ctx.prod_mil.get(pname, []):
    pr[E.canon_pred(u)].append(t)

BIN = 200
for tok in sorted(set(tr) | set(pr)):
    a, b = sorted(tr[tok]), sorted(pr[tok])
    print(f"\n{tok}: truth={len(a)} pred={len(b)}")
    hi = int(max(a[-1] if a else 0, b[-1] if b else 0) // BIN) + 1
    for i in range(hi):
        na = sum(1 for x in a if i * BIN <= x < (i + 1) * BIN)
        nb = sum(1 for x in b if i * BIN <= x < (i + 1) * BIN)
        if na or nb:
            print(f"  {i*BIN:5}-{(i+1)*BIN:5}s truth={na:3} pred={nb:3} {'<<<' if abs(na-nb)>=3 else ''}")
