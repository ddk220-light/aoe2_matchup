"""Across all labelled games, split each current-classifier military error into
CLASS-floor (truth military, predicted villager/unit -- mostly the signal-less floor)
vs WITHIN-MILITARY (right class, wrong type -- the per-line binding bucket), and show
which dominant type is swallowing the minorities."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

G = "C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/"
GAMES = [
    ("ORIGINAL", "C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "labels.json", 42.6),
    ("GAME1-4v4", G + "AgeIIDE_Replay_482721813.aoe2record", "labels_g1.json", 15.75),
    ("GAME2-Aztec", G + "AgeIIDE_Replay_482723861.aoe2record", "labels_g2.json", 44.5),
]
for name, replay, labelsf, endmin in GAMES:
    labels = json.load(open(labelsf))
    CUT = (endmin - 5) * 60000
    mt = mgz.model.parse_match(open(replay, "rb"))
    tm, _ = uc.build_type_map(mt)
    ctx = uc._run(mt)
    owner_player = {}
    from collections import defaultdict
    no = defaultdict(Counter)
    for cid, g in ctx.guesses.items():
        if g.player and str(cid) in labels:
            no[g.player][labels[str(cid)].get("owner")] += 1
    for nm, c in no.items():
        owner_player[c.most_common(1)[0][0]] = nm
    print(f"\n######## {name} ########")
    for owner in sorted(owner_player):
        player = owner_player[owner]
        mil = ok = classerr = typeerr = 0
        swallow = Counter()
        for k, u in labels.items():
            if u.get("owner") != owner or (u.get("created_ms") or 0) >= CUT:
                continue
            t = E.canon_truth(u["type"])
            if E.coarse(t) != "military" or int(k) not in tm:
                continue
            mil += 1
            p = E.canon_pred(tm[int(k)])
            if p == t:
                ok += 1
                continue
            if tm[int(k)] in ("villager", "unit", "military"):
                classerr += 1
            else:
                typeerr += 1
                swallow[p] += 1
        if mil >= 6:
            civ = str(dict((p.name, p.civilization) for p in mt.players).get(player, "?"))
            nm = f"{player}/{civ}".encode("ascii", "replace").decode()
            print(f"  {nm:24} mil {100*ok/mil:.0f}% ({ok}/{mil})  errors: CLASS-floor {classerr}, "
                  f"WITHIN-mil {typeerr}  swallowed-by={dict(swallow.most_common(3))}")
