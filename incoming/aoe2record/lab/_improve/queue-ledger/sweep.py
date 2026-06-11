"""Sweep ledger feature flags: reload unit_classifier under each combo, score both games."""
import sys, types, json, pickle, os, importlib
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger"
sys.path[:0] = [WS, "C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter
import unit_classifier as _uc_first   # MUST precede eval_against_truth (which
assert _uc_first.__file__.startswith(WS), _uc_first.__file__  # prepends prod dir)
import eval_against_truth as E
# E prepends the PRODUCTION visualizer dir; importlib.reload re-resolves the spec
# by name through sys.path, so WS must be back at the front or reload silently
# switches to the production copy.
while WS in sys.path:
    sys.path.remove(WS)
sys.path.insert(0, WS)

GAMES = {
    "g0": dict(labels=r"C:\dev\aoe2\aoe2record\lab\labels.json", end_min=42.6),
    "train": dict(labels=r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", end_min=44.5),
}
MT = {k: pickle.load(open(os.path.join(WS, f"match_cache_{k}.pkl"), "rb")) for k in GAMES}
LB = {k: json.load(open(GAMES[k]["labels"])) for k in GAMES}


def score(uc, key):
    cfg = GAMES[key]
    labels = LB[key]
    CUT = (cfg["end_min"] - 5) * 60000
    tm, _ = uc.build_type_map(MT[key])

    def known(name):
        if not name or name.lower() == "flare" or name.startswith("id"):
            return False
        return E.coarse(E.canon_truth(name)) in ("villager", "military")

    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    res = {}
    for label, milonly in (("overall", False), ("military", True)):
        gtot = gok = 0
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            p = E.canon_pred(tm[k])
            gtot += 1
            gok += p == t
        res[label] = 100 * gok / max(gtot, 1)
    return res


FLAGS = ["QL_RESEARCH_BLOCK", "QL_UPGRADE_TIMES", "QL_AGE_TIMES", "QL_CONSC", "QL_ENDT", "QL_CAP"]
OFF = {f: "0" for f in FLAGS}
P = {**OFF, "QL_ALLOC": "prod"}
COMBOS = [
    ("prod+line-both", {**P, "QL_LINE": "both"}),
    ("prod+line-both+endt", {**P, "QL_LINE": "both", "QL_ENDT": "1"}),
    ("prod+line-cb+endt", {**P, "QL_LINE": "cb", "QL_ENDT": "1"}),
    ("prod+line-castle+endt", {**P, "QL_LINE": "castle", "QL_ENDT": "1"}),
]

if len(sys.argv) > 1:
    names = set(sys.argv[1].split(","))
    COMBOS = [c for c in COMBOS if c[0] in names]

for name, env in COMBOS:
    for f in FLAGS + ["QL_ALLOC", "QL_RB", "QL_LINE"]:
        os.environ.pop(f, None)
    os.environ.update(env)
    if "unit_classifier" in sys.modules:
        uc = importlib.reload(sys.modules["unit_classifier"])
    else:
        import unit_classifier as uc
    if os.environ.get("QL_DEBUG"):
        print("  uc:", uc.__file__, "flags:", uc.FLAG_RESEARCH_BLOCK, uc.FLAG_UPGRADE_TIMES,
              uc.FLAG_AGE_TIMES, uc.FLAG_CONSC, uc.FLAG_ENDT, uc.FLAG_CAP, uc.ALLOC_MODE)
        ctx = uc._run(MT["g0"])
        print("  ddk220 pred_mil:", len(ctx.prod_mil.get("ddk220", [])))
    parts = []
    for key in GAMES:
        r = score(uc, key)
        parts.append(f"{key}: mil={r['military']:.1f} ov={r['overall']:.1f}")
    print(f"{name:24} {'  '.join(parts)}")
