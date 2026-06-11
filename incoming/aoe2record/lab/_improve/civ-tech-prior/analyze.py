"""analyze.py [g0|train] -- deep error dump: per-error unit details + civ/research context."""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
game = sys.argv[1] if len(sys.argv) > 1 else "g0"
REPLAY, LABELS, END_MIN = GAMES[game]
CUT = (END_MIN - 5) * 60000

labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))

print("=== PLAYERS / CIVS ===")
for p in mt.players:
    print(f"  {p.name}: civ={getattr(p,'civilization',None)}")

print("\n=== RESEARCH actions (first 60) ===")
n = 0
for a in mt.actions:
    if a.player and str(a.type).replace("Action.", "") == "RESEARCH":
        pl = a.payload or {}
        t = a.timestamp.total_seconds()
        print(f"  t={t/60:6.2f}min  {a.player.name:12} {pl.get('technology')!r}  payload_keys={sorted(pl.keys())}")
        n += 1
        if n >= 60:
            break

ctx = uc._run(mt)
tm = {}
for cid, g in ctx.guesses.items():
    if cid in ctx.building_ids or cid in ctx.gaia_all:
        continue
    t = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
    tm[cid] = t


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
overlap = [k for k in truth_units if k in tm]

print("\n=== ERRORS (all, vil+mil) ===")
errs = []
for k in sorted(overlap):
    t = E.canon_truth(truth_units[k]["type"])
    p = E.canon_pred(tm[k])
    if p != t:
        errs.append(k)
        g = ctx.guesses[k]
        cms = truth_units[k].get("created_ms", 0) / 60000
        print(f" id={k:6} truth={truth_units[k]['type']:>18}({t:>14}) pred={tm[k]:>14}({p:>12}) "
              f"own={truth_units[k].get('owner')} ply={g.player} cls={g.cls}/{g.cls_conf:.2f} "
              f"tconf={g.type_conf:.2f} sig={','.join(g.signals)} created={cms:5.2f}m "
              f"fs={ (g.behavior.get('first_seen') or 0)/60:5.2f}m beh={ {k2:v for k2,v in g.behavior.items() if k2!='first_seen'} }")

print(f"\ntotal errors: {len(errs)}")

# production stream summary per player
print("\n=== PRODUCTION (mil FIFO per player, first 50 each) ===")
for pl, comp in ctx.prod_mil.items():
    cc = Counter(u for _, u in comp)
    print(f"  {pl}: {dict(cc)}")
