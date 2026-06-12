"""diag3.py [g0|train] -- evidence distribution per truth class for spine candidates:
how separable are soft villagers vs soft military? Also command-delay (fs - created)
distribution per class, and behavior profiles of current spine errors.
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

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}
key = sys.argv[1] if len(sys.argv) > 1 else "g0"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
weight = uc.cocommand_graph(ctx)
uc.propagate_class(ctx, weight)
uc.production_timeline(ctx)

truth = {}
for k, u in labels.items():
    t = E.canon_truth(u.get("type") or "")
    if E.coarse(t) in ("villager", "military"):
        truth[int(k)] = (t, (u.get("created_ms") or 0) / 1000.0)

for player in [p.name for p in mt.players]:
    cand = uc._spine_candidates(ctx, player)
    prof = defaultdict(Counter)
    delay = defaultdict(list)
    for c in cand:
        if c not in truth:
            continue
        g = ctx.guesses[c]
        b = g.behavior
        tok, created = truth[c]
        cls = "vil" if tok == "villager" else "mil"
        hb, hm = bool(b.get("hard_build")), bool(b.get("hard_mil"))
        if hb and hm:
            ev = "conflict"
        elif hb:
            ev = "hardV"
        elif hm:
            ev = "hardM"
        elif g.cls == "villager" and g.cls_conf >= uc.CONF["cocmd_class"]:
            ev = "cocmdV"
        elif g.cls == "military" and g.cls_conf >= uc.CONF["cocmd_class"]:
            ev = "cocmdM"
        elif b.get("gathers"):
            ev = "gather"
        else:
            ev = "soft"
        prof[ev][cls] += 1
        delay[cls].append(b["first_seen"] - created)
        if ev == "soft":
            prof["soft_detail"][f"{cls}:mv{min(b.get('moves',0),9)}ab{min(b.get('attacks_building',0),5)}"] += 1
    print(f"\n=== {key} {player} ===")
    for ev in ("hardV", "hardM", "cocmdV", "cocmdM", "gather", "soft", "conflict"):
        if prof[ev]:
            print(f"  {ev:8} {dict(prof[ev])}")
    if prof["soft_detail"]:
        print(f"  soft detail: {dict(prof['soft_detail'].most_common(14))}")
    for cls in ("vil", "mil"):
        d = sorted(delay[cls])
        if d:
            def pct(p): return d[int(p * (len(d) - 1))]
            print(f"  cmd-delay {cls}: p10={pct(.1):.0f} p50={pct(.5):.0f} p90={pct(.9):.0f} max={d[-1]:.0f}")
