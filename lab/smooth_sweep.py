"""Sweep the co-command smoothing threshold across all games/players to test whether
smoothing is helping or *causing* the within-military swallow (minorities snapped to the
squad-dominant type), now that the creation-queue order is ~100%."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

G = "C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/"
GAMES = [
    ("ORIGINAL", "C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "labels.json", 42.6),
    ("GAME2", G + "AgeIIDE_Replay_482723861.aoe2record", "labels_g2.json", 44.5),
]
THRESHOLDS = [0.6, 0.7, 0.8, 0.9, 2.0]   # 2.0 == smoothing effectively OFF


def run(mt, th):
    ctx = uc.build_context(mt)
    uc.behavioral_labels(ctx)
    w = uc.cocommand_graph(ctx)
    uc.propagate_class(ctx, w)
    uc.production_timeline(ctx)
    sq = uc.form_squads(ctx, w)
    uc.assign_types(ctx, sq)
    uc.refine_military(ctx, smooth_thresh=th)
    uc.finalize(ctx)
    return {c: (g.type if g.type not in uc.GENERIC_TYPES
               else ("villager" if g.cls == "villager" else "unit"))
            for c, g in ctx.guesses.items()
            if c not in ctx.building_ids and c not in ctx.gaia_all}, ctx


for name, replay, labelsf, endmin in GAMES:
    labels = json.load(open(labelsf))
    CUT = (endmin - 5) * 60000
    mt = mgz.model.parse_match(open(replay, "rb"))
    # owner -> player
    _, ctx0 = run(mt, 0.6)
    no = defaultdict(Counter)
    for cid, g in ctx0.guesses.items():
        if g.player and str(cid) in labels:
            no[g.player][labels[str(cid)].get("owner")] += 1
    owner_player = {c.most_common(1)[0][0]: nm for nm, c in no.items()}
    civ = {p.name: str(p.civilization) for p in mt.players}
    print(f"\n######## {name} ########")
    header = "  " + " ".join(f"th={t}".rjust(9) for t in THRESHOLDS)
    print("  player".ljust(26) + header)
    for owner in sorted(owner_player):
        player = owner_player[owner]
        mil = [(int(k), E.canon_truth(u["type"])) for k, u in labels.items()
               if u.get("owner") == owner and E.coarse(E.canon_truth(u["type"])) == "military"
               and (u.get("created_ms") or 0) < CUT]
        if len(mil) < 6:
            continue
        cells = []
        for th in THRESHOLDS:
            tm, _ = run(mt, th)
            ok = sum(1 for k, t in mil if k in tm and E.canon_pred(tm[k]) == t)
            n = sum(1 for k, _ in mil if k in tm)
            cells.append(f"{100*ok/max(n,1):.0f}%".rjust(9))
        nm = f"{player}/{civ[player]}".encode("ascii", "replace").decode()[:24]
        print(f"  {nm:24}" + " ".join(cells))
