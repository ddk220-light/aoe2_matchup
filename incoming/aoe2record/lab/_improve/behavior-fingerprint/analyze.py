"""Deep-dive error analysis: for every military/villager error unit, dump its full
command trail (action types, times, targets, positions) so we can find fingerprints.

Usage: python analyze.py [g0|train]
"""
import sys, types, json
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"]
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
ctx = uc._run(mt)
tm = {}
for cid, g in ctx.guesses.items():
    if cid in ctx.building_ids or cid in ctx.gaia_all:
        continue
    tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
overlap = [k for k in truth_units if k in tm]

# gaia name lookup
gaia_name = {}
for g in (mt.gaia or []):
    iid = getattr(g, "instance_id", None)
    if iid is not None:
        gaia_name[iid] = (getattr(g, "name", "") or "")

# truth name lookup for ALL labels (even out of window)
truth_name = {int(k): u.get("type") for k, u in labels.items()}

# command trail per canonical id
trail = defaultdict(list)
for a in mt.actions:
    if not a.player:
        continue
    at = uc._at(a)
    payload = a.payload or {}
    t = a.timestamp.total_seconds()
    pos = getattr(a, "position", None)
    pos_s = f"({pos.x:.0f},{pos.y:.0f})" if pos and pos.x is not None else ""
    tgt = payload.get("target_id")
    tgt_s = ""
    if isinstance(tgt, int) and tgt > 0:
        tn = gaia_name.get(tgt) or truth_name.get(tgt) or ""
        own = ctx.owner.get(ctx.canon(tgt), "")
        tgt_s = f"->#{tgt}{(':' + tn) if tn else ''}{('@' + own) if own else ''}"
    extra = ""
    if at == "SPECIAL":
        extra = f" order={payload.get('order_id')}/{payload.get('order')}"
    if at in ("STANCE", "FORMATION"):
        extra = f" {payload.get('stance') or payload.get('formation')}"
    ids = [ctx.canon(o) for o in payload.get("object_ids", [])]
    nids = len(ids)
    for cid in ids:
        trail[cid].append(f"{t:7.1f} {at}{extra} n={nids} {pos_s}{tgt_s}")

errs = []
for k in overlap:
    t = E.canon_truth(truth_units[k]["type"])
    p = E.canon_pred(tm[k])
    if p != t:
        errs.append((t, p, k))
errs.sort()
print(f"=== {game}: {len(errs)} errors ===")
for t, p, k in errs:
    g = ctx.guesses.get(k)
    sq = g.squad_id if g else None
    print(f"\n--- id={k} truth={truth_units[k]['type']}({t}) pred={tm[k]}({p}) owner=P{truth_units[k].get('owner')} "
          f"created={truth_units[k].get('created_ms',0)/1000:.0f}s cls={g.cls if g else '?'} conf={g.type_conf if g else 0} "
          f"squad={sq} signals={g.signals if g else []}")
    for line in trail.get(k, [])[:14]:
        print("   ", line)
    if len(trail.get(k, [])) > 14:
        print(f"    ... +{len(trail[k])-14} more")
