"""diag.py [g0|train] -- evidence & ceiling diagnostics for the id-spine solver.
Per player: candidate counts, hard pins, oracle monotone assignment accuracy
(earliest-unclaimed-slot-of-true-TYPE in id order), lag distributions.
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)
from collections import Counter, defaultdict
import eval_against_truth as E
sys.path.insert(0, WORK)
import mgz.model
import unit_classifier as uc

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
uc.production_timeline(ctx)

# truth exact token per id
truth_tok = {}
truth_cls = {}
for k, u in labels.items():
    t = E.canon_truth(u.get("type") or "")
    c = E.coarse(t)
    if c in ("villager", "military"):
        truth_tok[int(k)] = t
        truth_cls[int(k)] = c

# classifier-token truth: map truth token space back -- we compare slot TYPE via canon_pred
def slot_matches(slot_type, ttok):
    return E.canon_pred(slot_type) == ttok

for player in [p.name for p in mt.players]:
    slots = sorted(ctx.prod_full.get(player, []))
    cand = []
    for c, g in ctx.guesses.items():
        if g.player != player:
            continue
        if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
            continue
        if g.behavior.get("first_seen") is None:
            continue
        cand.append(c)
    cand.sort()
    hardV = sum(1 for c in cand if ctx.guesses[c].behavior.get("hard_build"))
    hardM = sum(1 for c in cand if ctx.guesses[c].behavior.get("hard_mil"))
    witht = sum(1 for c in cand if c in truth_tok)
    comp = Counter(u for _, u in slots)
    print(f"\n=== {key} {player}  civ={ctx.civ.get(player)} ===")
    print(f" slots M={len(slots)}  comp={dict(comp.most_common())}")
    print(f" cand N={len(cand)}  hardV={hardV} hardM={hardM}  with-truth={witht}")
    # ORACLE: id-order monotone earliest-unclaimed slot whose TYPE canon-matches truth
    claimed = [False] * len(slots)
    last = -1
    ok = tot = unassigned = 0
    lag_list = []
    mism = Counter()
    for c in cand:
        if c not in truth_tok:
            continue   # oracle only steps on truthed units (approx)
        ttok = truth_tok[c]
        tot += 1
        j = last + 1
        found = None
        while j < len(slots):
            if not claimed[j] and slot_matches(slots[j][1], ttok):
                found = j
                break
            j += 1
        if found is None:
            unassigned += 1
            mism[("NOSLOT", ttok)] += 1
            continue
        claimed[found] = True
        last = found
        ok += 1
        fs = ctx.guesses[c].behavior["first_seen"]
        lag_list.append(fs - slots[found][0])
    lag_list.sort()
    def pct(p):
        return lag_list[int(p * (len(lag_list) - 1))] if lag_list else None
    print(f" ORACLE exact-type monotone: assigned {ok}/{tot}  (noslot {unassigned}) {dict(mism)}")
    if lag_list:
        print(f" lag(fs - slot_t): min={lag_list[0]:.0f} p10={pct(.1):.0f} p50={pct(.5):.0f} p90={pct(.9):.0f} max={lag_list[-1]:.0f}  neg={sum(1 for l in lag_list if l < -4)}")
