"""eval_against_truth.py — score the .aoe2record-only unit classifier against the
gRPC ground-truth labels. Reports coarse + fine accuracy and every error, so we
can drive the classifier toward 99% on the units we have truth for.
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier

VILLAGER_KW = ("villager", "farmer", "lumberjack", "miner", "builder", "forager",
               "fisher", "shepherd", "repairer", "hunter", "gatherer", "berry")
BUILDING_KW = ("town center", "house", "farm", "mill", "camp", "barracks", "range",
               "stable", "blacksmith", "castle", "tower", "wall", "gate", "market",
               "monastery", "university", "dock", "wonder", "outpost", "workshop",
               "krepost", "kreposts", "palisade", "wonder")
GAIA_KW = ("tree", "bush", "mine", "forage", "grass", "plant", "stump", "sheep",
           "boar", "deer", "cow", "llama", "relic", "rock", "flower", "wolf",
           "turkey", "flare", "dead ", "fish", "goat", "pig")
# map specific military names -> a canonical military token (same space the
# classifier emits, which is _norm(DE_QUEUE unit name)).
MIL = {
    "elite skirmisher": "skirmisher", "skirmisher": "skirmisher",
    "arbalester": "archer", "crossbowman": "archer", "archer": "archer",
    "slinger": "slinger",
    "halberdier": "spearman", "pikeman": "spearman", "spearman": "spearman",
    "hussite wagon": "hussitewagon",
    "champi scout": "champiscout", "champi": "champiscout",
    "paladin": "knight", "cavalier": "knight", "knight": "knight",
    "two-handed swordsman": "militia", "long swordsman": "militia",
    "man-at-arms": "militia", "champion": "militia", "militia": "militia",
    "trebuchet": "trebuchet", "monk": "monk", "missionary": "monk",
    "warrior priest": "monk",
    "light cavalry": "scoutcavalry", "hussar": "scoutcavalry",
    "scout cavalry": "scoutcavalry", "scout": "scoutcavalry",
    "mangonel": "mangonel", "onager": "mangonel",
    "scorpion": "scorpion",
    # post-v33315 DLC uniques the old name table lacked (caught Jaguar/Composite as
    # generic 'unit', hiding correct predictions and conflating cross-line errors)
    "jaguar warrior": "jaguarwarrior",
    "composite bowman": "compositebowman",
    "monastery": None,  # avoid 'monk' substring false hit handled below
}


def canon_mil(name):
    """Map a unit name OR a classifier token (which is space-less) to a token."""
    n = name.lower().replace("_", " ")
    nns = n.replace(" ", "")
    for k, tok in MIL.items():
        if tok and (k in n or k.replace(" ", "") in nns):
            return tok
    return None


def canon_truth(name):
    n = name.lower()
    if any(k in n for k in VILLAGER_KW):
        return "villager"
    if any(k in n for k in BUILDING_KW):
        return "building"
    if any(k in n for k in GAIA_KW) or name.startswith("id"):
        return "gaia"
    tok = canon_mil(name)
    if tok:
        return tok
    return "unit"     # unknown military -> generic


def canon_pred(token):
    """Map a classifier output token to the canonical token space."""
    if token == "villager":
        return "villager"
    if token in ("unit", "military"):
        return "unit"
    return canon_mil(token) or "unit"


def coarse(tok):
    if tok == "villager":
        return "villager"
    if tok in ("building", "gaia"):
        return tok
    return "military"


def main():
    labels = json.load(open("labels.json"))
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    tm, _ = unit_classifier.build_type_map(mt)

    both = [i for i in tm if str(i) in labels]
    print(f"overlap: {len(both)} of {len(tm)} classifier-typed ids have ground truth\n")

    # build comparison records
    recs = []
    for i in both:
        pred = str(tm[i])
        truth = canon_truth(labels[str(i)]["type"])
        recs.append((i, pred, truth, labels[str(i)]["type"], labels[str(i)].get("owner")))

    # ---- coarse (villager / military / building / gaia) ----
    cc = sum(coarse(p) == coarse(t) for _, p, t, _, _ in recs)
    print(f"COARSE (villager/military/building/gaia): {cc}/{len(recs)} = {100*cc/len(recs):.1f}%")
    conf = Counter((coarse(p), coarse(t)) for _, p, t, _, _ in recs)
    for (p, t), c in conf.most_common():
        flag = "" if p == t else "   <-- error"
        print(f"    pred={p:9} truth={t:9} {c}{flag}")

    # ---- fine (EXACT type in canonical token space) ----
    def fine_ok(p, t):
        return canon_pred(p) == t              # strict exact match
    def fine_or_generic(p, t):
        return canon_pred(p) == t or (canon_pred(p) == "unit" and coarse(t) == "military")
    fc = sum(fine_ok(p, t) for _, p, t, _, _ in recs)
    fg = sum(fine_or_generic(p, t) for _, p, t, _, _ in recs)
    print(f"\nFINE exact: {fc}/{len(recs)} = {100*fc/len(recs):.1f}%  "
          f"(+generic-military-ok: {100*fg/len(recs):.1f}%)")

    # ---- restricted to the classifier's actual job: TRUE villagers + military ----
    job = [r for r in recs if coarse(r[2]) in ("villager", "military")]
    jc_coarse = sum(coarse(p) == coarse(t) for _, p, t, _, _ in job)
    jc_fine = sum(fine_ok(p, t) for _, p, t, _, _ in job)
    print(f"\nON TRUE UNITS ONLY ({len(job)} villagers+military):")
    print(f"    villager-vs-military: {jc_coarse}/{len(job)} = {100*jc_coarse/len(job):.1f}%")
    print(f"    exact type:           {jc_fine}/{len(job)} = {100*jc_fine/len(job):.1f}%")

    # ---- error breakdown ----
    print("\nERROR PATTERNS (pred -> truth_token : count):")
    errs = Counter((p, t) for _, p, t, _, _ in recs if not fine_ok(p, t))
    for (p, t), c in errs.most_common(20):
        print(f"    {p:14} -> {t:12} {c}")

    print("\nSAMPLE ERRORS (id, pred, truth_name, owner):")
    n = 0
    for i, p, t, tn, o in recs:
        if not fine_ok(p, t):
            print(f"    id={i:6} pred={p:13} truth={tn:18} owner={o}")
            n += 1
            if n >= 25:
                break


if __name__ == "__main__":
    main()
