"""avail.py -- count errors where the PREDICTED type is impossible for that player:
the player never produced that token (not in their own queue stream) and it is not a
starting-unit type. These are civ/production-availability violations a prior can veto."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WS]
import mgz.model
sys.path.insert(0, WS)
import unit_classifier as uc
import eval_against_truth as E

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
ALL = ["blocks", "lb_blocks", "upgrades", "eagle_age", "line_speed", "speed_techs"]
keys = [] if sys.argv[1] == "none" else sys.argv[1].split(",")
for k in ALL:
    uc.PRIORS[k] = k in keys
uc.PRIORS["blocks_scope"] = "tc" if "tc" in keys else "all"


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


for game, (rp, lb, end_min) in GAMES.items():
    cut = (end_min - 5) * 60000
    labels = json.load(open(lb))
    mt = mgz.model.parse_match(open(rp, "rb"))
    ctx = uc._run(mt)
    # per-player produced tokens + starting unit types
    prod = {}
    for b, q in ctx.queues.items():
        pl = ctx.owner.get(b)
        prod.setdefault(pl, set()).update(u for _, u in q)
    start_types = {}
    for p in mt.players:
        st = set()
        for o in (p.objects or []):
            nm = uc._norm(getattr(o, "name", None))
            if nm:
                st.add(nm)
        start_types[p.name] = st
    tm = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else (
            "villager" if g.cls == "villager" else "unit")
    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < cut and known(u.get("type"))}
    nviol_err = nviol_ok = 0
    print(f"=== {game} ===")
    for k in sorted(truth_units):
        if k not in tm:
            continue
        g = ctx.guesses[k]
        pred_tok = g.type
        if pred_tok in uc.GENERIC_TYPES or pred_tok == "villager":
            continue
        pl = g.player
        ok_avail = (pred_tok in prod.get(pl, set())
                    or pred_tok in start_types.get(pl, set()))
        if ok_avail:
            continue
        t = E.canon_truth(truth_units[k]["type"])
        p = E.canon_pred(tm[k])
        good = p == t
        if good:
            nviol_ok += 1
        else:
            nviol_err += 1
        cms = (truth_units[k].get("created_ms") or 0) / 60000
        print(f"  {'OK ' if good else 'ERR'} id={k:6} pred_tok={pred_tok:16} canon={p:14} "
              f"truth={truth_units[k]['type']:>18}({t}) ply={pl} created={cms:5.2f}m "
              f"sig={','.join(g.signals)}")
    print(f"  violations: {nviol_err} on errors, {nviol_ok} on correct predictions\n")
