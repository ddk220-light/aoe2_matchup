"""diag5.py [g0|train] -- run BASELINE pipeline and SPINE pipeline on the same match;
compare per-unit correctness vs truth, bucketed by baseline confidence tier.
Tells us the optimal (tier-based) merge rule for a hybrid.
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
CUT = (end_min - 5) * 60000
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

def run_baseline(match):
    ctx = uc.build_context(match)
    uc.behavioral_labels(ctx)
    weight = uc.cocommand_graph(ctx)
    uc.propagate_class(ctx, weight)
    uc.production_timeline(ctx)
    squads = uc.form_squads(ctx, weight)
    uc.assign_types(ctx, squads)
    uc.refine_military(ctx)
    uc.finalize(ctx)
    return ctx

def run_spine(match):
    ctx = uc.build_context(match)
    uc.behavioral_labels(ctx)
    weight = uc.cocommand_graph(ctx)
    uc.propagate_class(ctx, weight)
    uc.production_timeline(ctx)
    uc.form_squads(ctx, weight)
    matched = uc.spine_align(ctx)
    uc.spine_post(ctx, matched)
    uc.finalize(ctx)
    return ctx

ctxA = run_baseline(mt)
ctxB = run_spine(mt)

def flat(ctx):
    out = {}
    conf = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        t = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
        out[cid] = t
        conf[cid] = g.type_conf if g.type not in uc.GENERIC_TYPES else 0.0
    return out, conf

tmA, confA = flat(ctxA)
tmB, confB = flat(ctxB)

def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")

truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}

TIERS = [(0.95, "hard"), (0.90, "cocmd"), (0.80, "squad"), (0.55, "idrank"), (0.30, "fallback"), (-1, "none")]
def tier(c):
    for thr, name in TIERS:
        if c >= thr:
            return name
    return "none"

# per tier: counts of (A ok, B ok) cross
agg = defaultdict(Counter)   # tier -> Counter of (Aok,Bok)
agg_mil = defaultdict(Counter)
examples = defaultdict(list)
for k, u in truth_units.items():
    if k not in tmA:
        continue
    t = E.canon_truth(u["type"])
    pa = E.canon_pred(tmA[k])
    pb = E.canon_pred(tmB.get(k, "unit"))
    ta = tier(confA.get(k, 0))
    cell = (pa == t, pb == t)
    agg[ta][cell] += 1
    if E.coarse(t) == "military":
        agg_mil[ta][cell] += 1
    if cell == (False, True) or cell == (True, False):
        examples[(ta, cell)].append((k, t, pa, pb))

print(f"=== {key}: per-baseline-tier  (Aok=baseline correct, Bok=spine correct) ===")
for _, name in TIERS:
    if not agg[name]:
        continue
    c = agg[name]
    n = sum(c.values())
    print(f" tier {name:9} n={n:4}  bothOK={c[(True,True)]:4} onlyA={c[(True,False)]:3} onlyB={c[(False,True)]:3} bothBAD={c[(False,False)]:3}"
          f"   [mil: {dict(agg_mil[name])}]")

print("\n--- units where exactly one side is right (tier, who) ---")
for (ta, cell), exs in sorted(examples.items()):
    who = "B(spine) wins" if cell == (False, True) else "A(base) wins"
    print(f" tier={ta:9} {who}: {len(exs)}")
    for k, t, pa, pb in exs[:12]:
        print(f"    id={k:6} truth={t:16} base={pa:16} spine={pb}")
