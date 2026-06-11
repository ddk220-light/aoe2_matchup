"""compare_per_player.py REPLAY LABELS END_MIN -- per-player military accuracy of the
classifier vs gRPC ground truth (scores units BOTH sides can name, ignores last 5 min)."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY, LABELS, END_MIN = sys.argv[1], sys.argv[2], float(sys.argv[3])
CUT = (END_MIN - 5) * 60000
labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
tm, _ = uc.build_type_map(mt)
ctx = uc._run(mt)

# owner number -> player name/civ (assume gRPC owner == classifier player via majority)
owner_name = {}
pl_by_name = {p.name: p for p in mt.players}
name_owner = defaultdict(Counter)
for cid, g in ctx.guesses.items():
    if g.player and str(cid) in labels:
        name_owner[g.player][labels[str(cid)].get("owner")] += 1
for nm, cnt in name_owner.items():
    o = cnt.most_common(1)[0][0]
    p = pl_by_name.get(nm)
    civ = (getattr(p, "civilization", "?") if p else "?")
    owner_name[o] = f"{nm}/{civ}".encode("ascii", "replace").decode()


def known(n):
    return n and n.lower() != "flare" and not n.startswith("id") and \
        E.coarse(E.canon_truth(n)) in ("villager", "military")


print(f"{REPLAY.split('/')[-1]}  (military exact-type, spawn<{END_MIN-5:.1f}min)\n")
by_owner = defaultdict(lambda: [0, 0, 0, 0])   # owner -> [mil_ok, mil_tot, all_ok, all_tot]
conf = defaultdict(Counter)
for k, u in labels.items():
    if (u.get("created_ms") or 0) >= CUT or not known(u.get("type")) or int(k) not in tm:
        continue
    o = u.get("owner")
    t = E.canon_truth(u["type"])
    p = E.canon_pred(tm[int(k)])
    by_owner[o][3] += 1
    if p == t:
        by_owner[o][2] += 1
    if E.coarse(t) == "military":
        by_owner[o][1] += 1
        if p == t:
            by_owner[o][0] += 1
        elif p != t:
            conf[o][(t, p)] += 1

for o in sorted(by_owner):
    mo, mt_, ao, at = by_owner[o]
    nm = owner_name.get(o, f"owner{o}")
    mil = f"{100*mo/mt_:.0f}% ({mo}/{mt_})" if mt_ else "n/a"
    print(f"  owner {o} {nm:28} military {mil:14} overall {100*ao/at:.0f}% ({ao}/{at})")
    top = conf[o].most_common(4)
    if top:
        print(f"        top errors: {', '.join(f'{t}->{p} x{c}' for (t,p),c in top)}")
