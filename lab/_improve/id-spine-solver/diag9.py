"""diag9.py [g0|train] -- list ALL truthed units where base(conf>=0.8) and spine
DISAGREE, with truth, to mine arbitration rules. Also disagreements where base<0.8
(spine currently wins) for completeness.
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

def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")

truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}

print(f"=== {key}: base>=0.8 vs spine disagreements ===")
stat = Counter()
for k in sorted(truth_units):
    if k not in base or k in ctx.building_ids or k in ctx.gaia_all:
        continue
    bt, btc, bc, _ = base[k]
    sp, spc, sc, _ = spine[k]
    if bt in uc.GENERIC_TYPES or btc < uc.CONF["squad_type"]:
        continue
    pb = E.canon_pred(bt)
    ps = E.canon_pred(sp if sp not in uc.GENERIC_TYPES else ("villager" if sc == "villager" else "unit"))
    if pb == ps:
        continue
    t = E.canon_truth(truth_units[k]["type"])
    who = "BASE" if pb == t else ("SPINE" if ps == t else "NONE")
    stat[who] += 1
    b = ctx.guesses[k].behavior
    ev = ("HB" if b.get("hard_build") else "") + ("HM" if b.get("hard_mil") else "")
    if not ev:
        ev = "g" if b.get("gathers") else "-"
    print(f" id={k:6} base={bt:16}/{btc:.2f} spine={sp:16} truth={t:16} right={who:5} ev={ev}")
print(f"summary: {dict(stat)}")
