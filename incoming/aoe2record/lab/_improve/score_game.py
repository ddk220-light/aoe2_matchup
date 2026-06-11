"""score_game.py REPLAY LABELS GAME_END_MIN -- run the classifier on a fresh replay
and compare to gRPC ground-truth labels, on the units BOTH sides can name (exclude
flares / dataset-missing id#### / gaia). Ignores the last 5 minutes.

Patched copy of C:/dev/aoe2/aoe2record/lab/compare_game.py:
  - sys.path fixed for the moved project root (C:/dev/aoe2/aoe2record/lab)
  - if env var UC_DIR is set, it is inserted at sys.path[0] BEFORE importing
    unit_classifier, so a modified classifier copy in that dir is used.
    (NOTE: unit_classifier loads train_times.json relative to its own file --
    copy train_times.json beside any classifier copy.)
  - prints a final machine-readable line:
        SCORES coverage=<pct> overall=<pct> military=<pct>
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
_uc_dir = os.environ.get("UC_DIR")
if _uc_dir:
    sys.path.insert(0, _uc_dir)
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

if _uc_dir:
    print(f"[score_game] UC_DIR={_uc_dir} -> unit_classifier from {uc.__file__}")

REPLAY = sys.argv[1]
LABELS = sys.argv[2]
END_MIN = float(sys.argv[3])
CUT = (END_MIN - 5) * 60000

labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
tm, _ = uc.build_type_map(mt)


def known(name):
    """A truth label we can actually compare: a real unit type with a dataset name."""
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


# coverage
truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
overlap = [k for k in truth_units if k in tm]
coverage_pct = 100 * len(overlap) / max(len(truth_units), 1)
print(f"replay={REPLAY.split('/')[-1]}  end={END_MIN}min  (scoring spawn<{END_MIN-5:.1f}min)")
print(f"truth nameable mil/vil units in-window: {len(truth_units)}; "
      f"with a classifier prediction (id-linked): {len(overlap)} "
      f"({coverage_pct:.0f}% coverage)")

scores = {}
for label, milonly in (("OVERALL vil+mil", False), ("MILITARY only", True)):
    gtot = gok = 0
    per = defaultdict(lambda: [0, 0])
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
    scores[label] = 100 * gok / max(gtot, 1)
    print(f"\n-- {label}: {100*gok/max(gtot,1):.1f}% ({gok}/{gtot}) --")
    if milonly:
        conf = Counter()
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military":
                continue
            p = E.canon_pred(tm[k])
            if p != t:
                conf[(t, p)] += 1
        for t in sorted(per, key=lambda x: -per[x][1]):
            if E.coarse(t) == "military":
                errs = {p: c for (tt, p), c in conf.items() if tt == t}
                print(f"   {t:14} {per[t][0]}/{per[t][1]}  {errs if errs else ''}")

print(f"\nSCORES coverage={coverage_pct:.1f} overall={scores['OVERALL vil+mil']:.1f} "
      f"military={scores['MILITARY only']:.1f}")
