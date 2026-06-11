"""Ablate the PRIORS mechanisms over g0 + train; print a score matrix."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WS]
import mgz.model
sys.path.insert(0, WS)
import unit_classifier as uc
import eval_against_truth as E
assert uc.__file__.lower().startswith(WS.lower())

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
matches = {n: mgz.model.parse_match(open(rp, "rb")) for n, (rp, lb, em) in GAMES.items()}
labels = {n: json.load(open(lb)) for n, (rp, lb, em) in GAMES.items()}


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def score(game):
    rp, lb, end_min = GAMES[game]
    cut = (end_min - 5) * 60000
    ctx = uc._run(matches[game])
    tm = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else (
            "villager" if g.cls == "villager" else "unit")
    truth_units = {int(k): u for k, u in labels[game].items()
                   if (u.get("created_ms") or 0) < cut and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    res = {}
    for label, milonly in (("ov", False), ("mil", True)):
        gtot = gok = 0
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            gtot += 1
            if E.canon_pred(tm[k]) == t:
                gok += 1
        res[label] = 100 * gok / max(gtot, 1)
    return res


ALL = ["blocks", "lb_blocks", "upgrades", "eagle_age", "line_speed", "speed_techs",
       "coprod_lines", "avail_veto"]
TCB = ["blocks", "lb_blocks", "tc"]
CONFIGS = [
    ("all-off", []),
    ("tcb", TCB),
    ("tcb+coprod", TCB + ["coprod_lines"]),
    ("tcb+veto", TCB + ["avail_veto"]),
    ("tcb+cp+veto", TCB + ["coprod_lines", "avail_veto"]),
    ("coprod-only", ["coprod_lines"]),
]
if len(sys.argv) > 1:
    # custom: ablate.py name=k1,k2 ...   ('tc' pseudo-key = blocks_scope tc)
    CONFIGS = []
    for arg in sys.argv[1:]:
        nm, ks = arg.split("=")
        CONFIGS.append((nm, [k for k in ks.split(",") if k]))

print(f"{'config':14} {'g0 mil':>7} {'g0 ov':>7} {'tr mil':>7} {'tr ov':>7}")
for name, keys in CONFIGS:
    for k in ALL:
        uc.PRIORS[k] = k in keys
    uc.PRIORS["blocks_scope"] = "tc" if "tc" in keys else "all"
    r0 = score("g0")
    r1 = score("train")
    print(f"{name:14} {r0['mil']:7.1f} {r0['ov']:7.1f} {r1['mil']:7.1f} {r1['ov']:7.1f}",
          flush=True)
