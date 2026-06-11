"""Fast scorer: load pickled Match objects once, run the WORKSPACE classifier copy,
print the same numbers as _improve/score_game.py plus military confusion rows.

Usage: python fast_score.py [g0|train|both]
"""
import sys, types, json, pickle, time
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\final"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
import unit_classifier as uc
import eval_against_truth as E
assert uc.__file__.startswith(WORK), uc.__file__

GAMES = {
    "g0": (r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger\match_cache_g0.pkl", r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger\match_cache_train.pkl", r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def score(game, verbose=True):
    PKL, LABELS, END_MIN = GAMES[game]
    CUT = (END_MIN - 5) * 60000
    labels = json.load(open(LABELS))
    with open(PKL, "rb") as f:
        mt = pickle.load(f)
    tm, _ = uc.build_type_map(mt)
    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    cov = 100 * len(overlap) / max(len(truth_units), 1)
    out = {"coverage": cov}
    for label, milonly in (("overall", False), ("military", True)):
        gtot = gok = 0
        conf = Counter()
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if milonly and E.coarse(t) != "military":
                continue
            p = E.canon_pred(tm[k])
            gtot += 1
            if p == t:
                gok += 1
            else:
                conf[(t, p)] += 1
        out[label] = 100 * gok / max(gtot, 1)
        out[label + "_n"] = (gok, gtot)
        if milonly and verbose:
            print(f"  {game} military errors:")
            for (t, p), c in conf.most_common():
                print(f"    {t}->{p} x{c}")
    print(f"  {game}: coverage={cov:.1f} overall={out['overall']:.1f} "
          f"({out['overall_n'][0]}/{out['overall_n'][1]}) "
          f"military={out['military']:.1f} ({out['military_n'][0]}/{out['military_n'][1]})")
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    t0 = time.time()
    if which == "both":
        for g in ("g0", "train"):
            score(g)
    else:
        score(which)
    print(f"[{time.time()-t0:.1f}s]")
