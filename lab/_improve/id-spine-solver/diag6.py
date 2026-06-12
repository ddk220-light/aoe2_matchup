"""diag6.py [g0|train] -- list every HYBRID error with both branches' predictions,
baseline tier, behavior evidence, squad id, and timing. Guides the next fix.
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)
from collections import Counter, defaultdict
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
CUT = (end_min - 5) * 60000
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
weight = uc.cocommand_graph(ctx)
uc.propagate_class(ctx, weight)
uc.production_timeline(ctx)
squads = uc.form_squads(ctx, weight)
pre = {cid: (g.type, g.type_conf, g.cls, g.cls_conf) for cid, g in ctx.guesses.items()}
uc.assign_types(ctx, squads)
uc.refine_military(ctx)
base = {cid: (g.type, g.type_conf, g.cls, g.cls_conf) for cid, g in ctx.guesses.items()}
for cid, (t, tc, c, cc) in pre.items():
    g = ctx.guesses[cid]
    g.type, g.type_conf, g.cls, g.cls_conf = t, tc, c, cc
matched = uc.spine_align(ctx)
uc.spine_post(ctx, matched)
spine = {cid: (g.type, g.type_conf, g.cls, g.cls_conf) for cid, g in ctx.guesses.items()}
for cid, (t, tc, c, cc) in base.items():
    if t not in uc.GENERIC_TYPES and tc >= uc.CONF["squad_type"]:
        g = ctx.guesses[cid]
        g.type, g.type_conf, g.cls, g.cls_conf = t, tc, c, cc
uc.finalize(ctx)

def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")

truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}

ref_ids, ref_ubs = uc._first_refs(ctx)
def ub_of(cid):
    k = bisect.bisect_left(ref_ids, cid)
    return ref_ubs[k] if k < len(ref_ids) else float("inf")

print(f"=== {key}: hybrid errors (mil + vil) ===")
nerr = 0
for k in sorted(truth_units):
    g = ctx.guesses.get(k)
    if g is None or k in ctx.building_ids or k in ctx.gaia_all:
        continue
    t = E.canon_truth(truth_units[k]["type"])
    pf = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
    p = E.canon_pred(pf)
    if p == t:
        continue
    nerr += 1
    bt, btc, _, _ = base[k]
    sp, spc, _, _ = spine[k]
    b = g.behavior
    hb, hm = bool(b.get("hard_build")), bool(b.get("hard_mil"))
    ev = ("HB" if hb else "") + ("HM" if hm else "")
    if not ev:
        ev = "g" if b.get("gathers") else "-"
    fs = b.get("first_seen")
    src = "BASE" if (bt not in uc.GENERIC_TYPES and btc >= uc.CONF["squad_type"]) else "SPINE"
    created = (truth_units[k].get("created_ms") or 0) / 1000.0
    print(f" id={k:6} P{truth_units[k].get('owner')} truth={t:15} pred={p:15} src={src:5} "
          f"base={bt}/{btc:.2f} spine={sp}/{spc:.2f} ev={ev:2} fs={fs if fs is None else round(fs,1)} "
          f"ub={round(ub_of(k),1)} created={created:.1f} sq={g.squad_id}")
print(f"total errors: {nerr}")
