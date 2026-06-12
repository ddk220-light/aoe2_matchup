"""driver.py [g0|train|both] -- parse-once (pickle-cached) scorer for the
id-spine-solver classifier copy. Mirrors _improve/score_game.py scoring exactly,
plus per-player diagnostics. Usage:
    python _improve/id-spine-solver/driver.py both
"""
import sys, types, json, os, pickle, time
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)   # my classifier copy wins
from collections import Counter, defaultdict
import unit_classifier      # resolve MY copy first (E would import the production one)
assert unit_classifier.__file__.startswith(WORK), unit_classifier.__file__
import eval_against_truth as E

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}


def get_match(key):
    import mgz.model
    replay = GAMES[key][0]
    t0 = time.time()
    mt = mgz.model.parse_match(open(replay, "rb"))
    print(f"[driver] parsed {key} in {time.time()-t0:.1f}s", file=sys.stderr)
    return mt


def score(key, mt, uc, verbose=True):
    _, labels_path, end_min = GAMES[key]
    labels = json.load(open(labels_path))
    CUT = (end_min - 5) * 60000
    tm, _ = uc.build_type_map(mt)

    def known(name):
        if not name or name.lower() == "flare" or name.startswith("id"):
            return False
        return E.coarse(E.canon_truth(name)) in ("villager", "military")

    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    coverage = 100 * len(overlap) / max(len(truth_units), 1)
    out = {}
    for label, milonly in (("overall", False), ("military", True)):
        gtot = gok = 0
        per = defaultdict(lambda: [0, 0])
        conf = Counter()
        errs_by_id = []
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            p = E.canon_pred(tm[k])
            gtot += 1
            per[t][1] += 1
            if p == t:
                gok += 1
                per[t][0] += 1
            else:
                conf[(t, p)] += 1
                errs_by_id.append((k, t, p, truth_units[k]["type"], truth_units[k].get("owner")))
        out[label] = 100 * gok / max(gtot, 1)
        if milonly and verbose:
            print(f"[{key}] MILITARY {out[label]:.1f}% ({gok}/{gtot})")
            for t in sorted(per, key=lambda x: -per[x][1]):
                errs = {p: c for (tt, p), c in conf.items() if tt == t}
                print(f"   {t:16} {per[t][0]}/{per[t][1]}  {errs if errs else ''}")
            out["mil_errs"] = errs_by_id
        elif verbose:
            print(f"[{key}] OVERALL  {out[label]:.1f}% ({gok}/{gtot})  coverage {coverage:.1f}%")
            ve = {(t, p): c for (t, p), c in conf.items() if t == "villager" or p == "villager"}
            if ve:
                print(f"   vil-confusions: {ve}")
            out["all_errs"] = errs_by_id
    out["coverage"] = coverage
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    keys = ["g0", "train"] if which == "both" else [which]
    import unit_classifier as uc
    print(f"[driver] unit_classifier from {uc.__file__}", file=sys.stderr)
    res = {}
    for key in keys:
        mt = get_match(key)
        res[key] = score(key, mt, uc)
    line = "  |  ".join(f"{k}: mil={res[k]['military']:.1f} overall={res[k]['overall']:.1f} cov={res[k]['coverage']:.1f}"
                        for k in keys)
    print("RESULT " + line)
    if len(keys) == 2:
        print(f"RESULT avgmil={ (res['g0']['military']+res['train']['military'])/2 :.2f}")


if __name__ == "__main__":
    main()
