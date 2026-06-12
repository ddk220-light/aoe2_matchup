"""diag4.py [g0|train] [player] -- per-error forensics for the spine DP.
Shows, in id order, every truthed candidate: evidence, fs/U, the DP-matched slot
(idx, time, type) pre-smoothing, truth token, and marks errors. Lets us see exactly
where the alignment derails.
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
import bisect

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}
key = sys.argv[1]
sel_player = sys.argv[2] if len(sys.argv) > 2 else None
only_errs = "-e" in sys.argv
replay, labels_path, end_min = GAMES[key]
CUT = (end_min - 5) * 60
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
weight = uc.cocommand_graph(ctx)
uc.propagate_class(ctx, weight)
uc.production_timeline(ctx)
uc.form_squads(ctx, weight)

# capture DP assignment by monkey-wrapping: rerun spine_align and record
orig_apply_types = {}
matched = uc.spine_align(ctx)
# reconstruct per-unit slot: g.type holds the slot type; recover slot index by re-running
# a light version: instead, recompute assign via spine internals is messy -- just show type.

truth = {}
for k, u in labels.items():
    t = E.canon_truth(u.get("type") or "")
    if E.coarse(t) in ("villager", "military") and (u.get("created_ms") or 0) / 1000.0 < CUT:
        truth[int(k)] = (t, (u.get("created_ms") or 0) / 1000.0)

ref_ids, ref_ubs = uc._first_refs(ctx)
def ub_of(cid):
    k = bisect.bisect_left(ref_ids, cid)
    return ref_ubs[k] if k < len(ref_ids) else float("inf")

for player in [p.name for p in mt.players]:
    if sel_player and player != sel_player:
        continue
    slots = sorted(ctx.prod_full.get(player, []))
    cand = uc._spine_candidates(ctx, player)
    print(f"\n=== {key} {player}: slots={len(slots)} cands={len(cand)} ===")
    # truth slot via LCS oracle for reference
    for c in cand:
        if c not in truth:
            continue
        g = ctx.guesses[c]
        b = g.behavior
        ttok, created = truth[c]
        pred = E.canon_pred(g.type)
        err = pred != ttok
        if only_errs and not err:
            continue
        hb, hm = bool(b.get("hard_build")), bool(b.get("hard_mil"))
        ev = ("HB" if hb else "") + ("HM" if hm else "") or ("g" if b.get("gathers") else "s")
        fs = b["first_seen"]
        ubv = ub_of(c)
        mark = " <<< ERR" if err else ""
        print(f" id={c:6} {ev:3} fs={fs:7.1f} ub={ubv:7.1f} created={created:7.1f} "
          f"pred={g.type:>15}/{pred:<14} truth={ttok:<14} sq={g.squad_id}{mark}")
