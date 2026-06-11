"""flipdiff.py cfgA cfgB [game] -- show per-unit prediction flips between two PRIORS
configs (comma-joined key lists, 'none' = all off). Shows which truth units got
better/worse, with behavior context."""
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
cfgA = [] if sys.argv[1] == "none" else sys.argv[1].split(",")
cfgB = [] if sys.argv[2] == "none" else sys.argv[2].split(",")
games = [sys.argv[3]] if len(sys.argv) > 3 else list(GAMES)


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def run(game, keys, mt):
    for k in ALL:
        uc.PRIORS[k] = k in keys
    ctx = uc._run(mt)
    tm = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else (
            "villager" if g.cls == "villager" else "unit")
    return tm, ctx


for game in games:
    rp, lb, end_min = GAMES[game]
    cut = (end_min - 5) * 60000
    labels = json.load(open(lb))
    mt = mgz.model.parse_match(open(rp, "rb"))
    tmA, ctxA = run(game, cfgA, mt)
    tmB, ctxB = run(game, cfgB, mt)
    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < cut and known(u.get("type"))}
    print(f"=== {game}: A={cfgA or 'none'} vs B={cfgB or 'none'} ===")
    fixed = broken = 0
    for k in sorted(truth_units):
        if k not in tmA or k not in tmB:
            continue
        t = E.canon_truth(truth_units[k]["type"])
        pA, pB = E.canon_pred(tmA[k]), E.canon_pred(tmB[k])
        if pA == pB:
            continue
        okA, okB = pA == t, pB == t
        tag = "FIXED " if (not okA and okB) else ("BROKE " if (okA and not okB) else "moved ")
        if not okA and okB:
            fixed += 1
        elif okA and not okB:
            broken += 1
        g = ctxB.guesses[k]
        cms = (truth_units[k].get("created_ms") or 0) / 60000
        print(f" {tag} id={k:6} truth={truth_units[k]['type']:>18}({t}) A={pA} B={pB} "
              f"ply={g.player} created={cms:5.2f}m sig={','.join(g.signals)}")
    print(f" net: +{fixed} fixed, -{broken} broken\n")
