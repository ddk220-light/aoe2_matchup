"""Pure classification rules for unit-analysis-video storyboards.

No I/O, no sim — operates on plain dicts. Reference implementation +
calibration history:
  docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py
  docs/superpowers/specs/2026-07-05-etg-dbsource-dryrun.py  (DB-backed golden)

Constants are calibrated / user-approved; change them only with a re-run of
the Temple Guard validation. The dry-run behaviour is authoritative on any
conflict with the plan doc.
"""
import json
import math

WIN_T = 15.0          # |S| <= WIN_T  -> "even"
E_T = 0.15            # clearly-negative prior threshold
B_T = 0.2             # meaningful bonus threshold
B_STRONG = 0.45       # dedicated-counter bonus threshold
OUTLIER_MARGIN = 15.0  # generic staple must beat next unique by this much |S|
WEIGHTS = {"bonus": 0.5, "rps": 0.3, "cost": 0.2}

GUNPOWDER_KEYS = ("janissary", "conquistador", "organ_gun", "hand_cannoneer",
                  "hussite", "ribauldequin", "fire_thrower", "grenadier")

# expected_counter pick rule (user 2026-07-05): a MIX, not 3 identical wipes --
# 1 gunpowder shock + 2 iconic archer counters (the classic "archers shred
# infantry" story). Curated trio by slug; falls back to margin sort if absent.
COUNTER_MIX = ("grenadier_jurchens", "elite_chakram_thrower_gurjaras",
               "elite_chu_ko_nu_chinese")

# Folk-knowledge matrix, subject-row perspective (+ = row favored). Sparse;
# missing pair -> antisymmetric lookup -> 0. Verbatim from the prototype/dry run.
RPS = {
    "eagle": {"archer": .5, "skirm": .4, "cav_archer": .4, "siege": .6,
              "gunpowder": .4, "infantry": -.5, "spear": .2, "cavalry": -.3,
              "light_cav": .0, "camel": .0, "elephant": -.2},
    "infantry": {"spear": .4, "eagle": .5, "siege": .5, "elephant": .2,
                 "archer": -.4, "cav_archer": -.4, "cavalry": -.2,
                 "gunpowder": -.3, "skirm": .3},
    "spear": {"cavalry": .7, "light_cav": .6, "camel": .5, "elephant": .7,
              "archer": -.6, "skirm": -.5, "cav_archer": -.6,
              "gunpowder": -.5, "siege": .2},
    "archer": {"infantry": .4, "spear": .6, "elephant": .3, "siege": .2,
               "cavalry": -.4, "light_cav": -.3, "camel": -.3, "skirm": -.5},
    "skirm": {"archer": .5, "cav_archer": .4, "spear": .5,
              "cavalry": -.5, "light_cav": -.4, "gunpowder": .2},
    "cav_archer": {"infantry": .5, "spear": .6, "siege": .3, "elephant": .2,
                   "cavalry": -.2, "camel": -.2},
    "cavalry": {"archer": .4, "skirm": .5, "siege": .6, "gunpowder": .5,
                "cav_archer": .2, "light_cav": .3, "camel": -.5},
    "light_cav": {"siege": .6, "archer": .3, "skirm": .4, "gunpowder": .4,
                  "camel": -.4},
    "camel": {"elephant": .3, "cav_archer": .3, "infantry": -.3, "archer": -.3},
    "elephant": {"siege": .4, "gunpowder": .2},
    "siege": {"gunpowder": .2},
    "gunpowder": {},
}


def categorize(slug, unit_class_name, is_ranged, speed=1.0):
    """Map a unit onto one of the folk-knowledge categories.

    `speed` is used only for the eagle->infantry override (an eagle-armored
    unit that moves at infantry speed, e.g. the Temple Guard, plays like
    infantry). Callers that already resolved the override may pass any speed.
    """
    s = slug.lower()
    if any(k in s for k in GUNPOWDER_KEYS):
        return "gunpowder"
    if "ballista_elephant" in s:
        return "siege"
    if "camel" in s:
        return "camel"
    if "elephant" in s:
        return "elephant"
    cat = None
    if any(k in s for k in ("eagle", "fire_lancer", "temple_guard")):
        cat = "eagle"
    elif any(k in s for k in ("halberdier", "pikeman", "spearman", "kamayuk")):
        cat = "spear"
    elif "skirm" in s or "genitour" in s:
        cat = "skirm"
    elif (s in ("hussar", "winged_hussar") or "huszar" in s
          or "shrivamsha" in s or s == "elite_steppe" or "steppe_lancer" in s):
        cat = "light_cav"
    if cat is None:
        uc = (unit_class_name or "").lower()
        if uc == "siege" or s in ("siege_onager", "heavy_scorpion",
                                  "mounted_trebuchet_khitans"):
            cat = "siege"
        elif "cavalry" in uc:
            cat = "cav_archer" if is_ranged else "cavalry"
        elif uc == "archer":
            cat = "archer"
        elif uc == "infantry" and is_ranged:
            cat = "archer"       # thrown-weapon infantry (gbeto, axeman, chakram)
        else:
            cat = "infantry"
    if cat == "eagle" and speed < 1.2:
        cat = "infantry"         # eagle-classed but infantry-speed (Temple Guard)
    return cat


def rps(a, b):
    if a == b:
        return 0.0
    if b in RPS.get(a, {}):
        return RPS[a][b]
    if a in RPS.get(b, {}):
        return -RPS[b][a]
    return 0.0


def bonus_gain(attacks_json, base_atk, opp_armors_json, attacker_ranged):
    """Relative extra damage from class bonuses vs this opponent."""
    atts = {int(k): v for k, v in json.loads(attacks_json or "{}").items()}
    arms = {int(k): v for k, v in json.loads(opp_armors_json or "{}").items()}
    base_armor = arms.get(3, 0) if attacker_ranged else arms.get(4, 0)
    base_eff = max((base_atk or 0) - base_armor, 1.0)
    gain = 0.0
    for cls, amt in atts.items():
        if cls in (3, 4):        # base pierce / base melee
            continue
        if cls in arms:
            eff = amt - arms[cls]
            if eff > 0:
                gain += eff
    return gain / base_eff


def bonus_component(gain_subject, gain_opponent):
    """B = tanh(subject bonus-gain - opponent bonus-gain), in (-1, 1)."""
    return math.tanh(gain_subject - gain_opponent)


def cost_component(subject_cost, opponent_cost):
    """C = clamp(log_3(subject_cost / opponent_cost), -1, 1)."""
    return max(-1.0, min(1.0,
               math.log(subject_cost / max(opponent_cost, 1)) / math.log(3)))


def expectation_from_components(B, R, C):
    """Blend the three priors into E in [-1, 1]."""
    E = WEIGHTS["bonus"] * B + WEIGHTS["rps"] * R + WEIGHTS["cost"] * C
    return max(-1.0, min(1.0, E))


def expectation(subj, opp):
    """(E, factors) exactly as the dry run computes them from packed dicts.

    `subj`/`opp` are packed dicts with keys: attacks, atk, armors, ranged,
    cost, cat. Returns (E, {"bonus","rps","cost"}) with factors rounded to 2dp.
    """
    gs = bonus_gain(subj["attacks"], subj["atk"], opp["armors"], subj["ranged"])
    go = bonus_gain(opp["attacks"], opp["atk"], subj["armors"], opp["ranged"])
    B = bonus_component(gs, go)
    R = rps(subj["cat"], opp["cat"])
    C = cost_component(subj["cost"], opp["cost"])
    E = expectation_from_components(B, R, C)
    return E, {"bonus": round(B, 2), "rps": round(R, 2), "cost": round(C, 2)}


def classify(r):
    """Assign a result row to exactly one of the five categories.

    Verbatim from the prototype/dry run. `r` needs S, E, kited, ranged and
    factors["bonus"].
    """
    B = r["factors"]["bonus"]
    if abs(r["S"]) <= WIN_T:
        return "even"
    if r["S"] > WIN_T:
        if B >= B_T:
            return "expected_win"
        if B <= -B_T:
            return "unexpected_win"
        return "expected_win" if r["E"] >= 0 else "unexpected_win"
    if B <= -B_STRONG or r["kited"] or r["E"] < -E_T:
        return "expected_counter"
    if not r["ranged"]:
        return "unexpected_counter"
    return "expected_counter"


SORTS = {
    "expected_win":       lambda r: -r["S"],
    "unexpected_win":     lambda r: (r["factors"]["bonus"], r["S"]),
    "expected_counter":   lambda r: (r["S"], r["factors"]["bonus"]),
    "unexpected_counter": lambda r: -r["S"],
    "even":               lambda r: -r["S"],
}

# Top-3 pick eligibility (stricter than list membership): mirrors the dry run's
# `buckets` filters so the filmed fights match the caption categories.
PICK_FILTERS = {
    "expected_win":       lambda r: r["factors"]["bonus"] >= B_T and r["gold"] > 0,
    "unexpected_win":     lambda r: r["factors"]["bonus"] <= -B_T,
    "expected_counter":   lambda r: (r["factors"]["bonus"] <= -B_STRONG
                                     or r["E"] < -E_T or r["kited"]),
    "unexpected_counter": lambda r: (r["factors"]["bonus"] > -B_STRONG
                                     and not r["ranged"] and r["E"] >= -E_T),
}


def dedupe_line(items):
    """Collapse split forms of the same unit line (e.g. ratha melee/ranged)."""
    seen, out = set(), []
    for r in items:
        key = r["slug"].split("_(")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def prefer_uniques(items, margin=OUTLIER_MARGIN):
    """Top-3 favoring uniques; a generic takes a slot only when it outclasses
    the next unique by >= margin points of |S|."""
    picks, rest = [], list(items)
    while rest and len(picks) < 3:
        head = rest.pop(0)
        if head["is_unique"]:
            picks.append(head)
            continue
        next_uni = next((r for r in rest if r["is_unique"]), None)
        if next_uni is None or abs(head["S"]) - abs(next_uni["S"]) >= margin:
            picks.append(head)
    return picks


def pick_counter_mix(items):
    """expected_counter pick rule (user 2026-07-05): the curated gunpowder +
    archer MIX by slug; falls back to margin sort (prefer_uniques on the
    deduped list) when the curated trio is not all present."""
    by_slug = {r["slug"]: r for r in items}
    curated = [by_slug[s] for s in COUNTER_MIX if s in by_slug]
    return curated if len(curated) == 3 else prefer_uniques(dedupe_line(items))
