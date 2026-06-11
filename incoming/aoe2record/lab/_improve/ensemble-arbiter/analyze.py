"""analyze.py [g0|train] -- per-error evidence dump + produced-vs-assigned quota check."""
import sys, types, json, os, pickle, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\ensemble-arbiter"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
from collections import Counter, defaultdict
import unit_classifier as uc
import eval_against_truth as E
from iterate import GAMES, get_match, known

key = sys.argv[1] if len(sys.argv) > 1 else "g0"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = get_match(key)
ctx = uc._run(mt)

CUT = (end_min - 5) * 60000
truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}

tm = {}
for cid, g in ctx.guesses.items():
    if cid in ctx.building_ids or cid in ctx.gaia_all:
        continue
    tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")

# squad membership + majority
sq_members = defaultdict(list)
for c, g in ctx.guesses.items():
    if g.squad_id is not None:
        sq_members[g.squad_id].append(c)

# per-player produced vs assigned military multisets
print("=== produced vs ASSIGNED military type multisets (quota violations flagged) ===")
for player in sorted(set(g.player for g in ctx.guesses.values() if g.player)):
    prod = Counter(u for _, u in ctx.prod_mil.get(player, []))
    assigned = Counter(g.type for c, g in ctx.guesses.items()
                       if g.player == player and g.cls == "military"
                       and c not in ctx.building_ids and c not in ctx.gaia_all
                       and c not in ctx.start_ids and g.type not in uc.GENERIC_TYPES)
    if not prod and not assigned:
        continue
    print(f"-- {player}")
    for t in sorted(set(prod) | set(assigned)):
        flag = "  <-- OVER-QUOTA" if assigned[t] > prod[t] else ""
        print(f"     {t:<18} prod={prod[t]:<4} assigned={assigned[t]:<4}{flag}")

# error dump with full evidence
print("\n=== ERROR EVIDENCE (military errors + villager->mil flips) ===")
for k in sorted(truth_units):
    if k not in tm:
        continue
    t = E.canon_truth(truth_units[k]["type"])
    p = E.canon_pred(tm[k])
    if p == t:
        continue
    g = ctx.guesses[k]
    if E.coarse(t) != "military" and p == "villager":
        continue
    fs = g.behavior.get("first_seen")
    player = g.player
    pm = sorted(ctx.prod_mil.get(player, []))
    PT = [x for x, _ in pm]; PU = [u for _, u in pm]
    iso_info = ""
    if fs is not None and PT:
        kk = bisect.bisect_right(PT, fs + 4.0) - 1
        if 0 <= kk < len(PU):
            isov = min((abs(PT[x] - PT[kk]) for x in range(len(PT)) if PU[x] != PU[kk]),
                       default=float("inf"))
            iso_info = f"iso_slot={PU[kk]}@{PT[kk]:.0f}s iso={isov:.0f} lag={fs-PT[kk]:.0f}"
    sq = ""
    if g.squad_id is not None:
        mem = sq_members[g.squad_id]
        votes = Counter(ctx.guesses[m].type for m in mem if ctx.guesses[m].cls == "military")
        sq = f"squad#{g.squad_id}(n={len(mem)}) milvotes={dict(votes.most_common(4))}"
    print(f"id={k:6} truth={truth_units[k]['type']:<18} pred={tm[k]:<16} src={g.type_src:<13} "
          f"fs={fs if fs is None else round(fs)} hist={g.type_hist}")
    print(f"        behav={ {kk: vv for kk, vv in g.behavior.items() if kk != 'first_seen'} } {iso_info} {sq}")
