"""Pure categorization + showcase-selection rules for the V2 unit-analysis flow.

This is the user-approved scheme finalized 2026-07-06 (ETG pilot). It supersedes
the earlier E-prior/RPS prototype in ``story_rules.py`` for the position-aware V2
sim source (``apps/video/sim_v2``). No I/O, no sim — plain dicts in, plain dicts
out — so it is importable and testable. The driver
``apps/video/sim_v2/build_v2_categorization.py`` assembles the inputs (subject +
opponent combat stats + V2 sim results) and calls into here.

The scheme, verbatim from the locked decisions:

Outcome (winner must keep army HP; the coin-flip band absorbs the middle):
  win  = subject win-rate >= 0.80 AND subject keeps > 5% army HP
  loss = subject win-rate <= 0.20 AND opponent keeps > 5% army HP
  else = coin-flip  (contested win-rate, or the winner too thin)

Normal-counter triangle (broad class X counters Y):
  infantry -> {cavalry, infantry}
  ranged   -> {infantry, ranged}
  cavalry  -> {ranged, cavalry}

Expected vs unexpected — who is FAVORED decides, by this cascade:
  1. only the subject has a usable damage bonus  -> subject favored
  2. only the opponent has a bonus vs the subject -> opponent favored
  3. BOTH have a usable bonus                     -> "both" (always unexpected)
  4. neither has a bonus                          -> the normal-counter class decides
Then: win + subject/neither-favored = expected win; win + opp/both = unexpected win;
loss + opp/neither-favored = expected loss; loss + subject/both = unexpected loss.

Two quirks baked in:
  * Melee gating — a melee subject's damage bonus only counts against opponents it
    can catch. Against a ranged/kiting opponent the "on paper" bonus (e.g. anti-cav
    vs a cav-archer's cavalry armor) never connects, so it is dropped and the
    counter class decides instead. (Disable with melee_only=False.)
  * Skirmisher/spearman override — skirmishers (anti-archer) and spearmen (anti-cav)
    are weak vs infantry: infantry counters them and they do NOT counter infantry.
    But a MOUNTED skirmisher faster than the subject kites and behaves like a normal
    ranged unit, so the override is speed-gated.

Bonus threshold: an attack bonus must be > 1 to count (a +1 class bonus is noise).
"""

import json

# --- thresholds (calibrated / user-approved; change only with a re-validation) ---
WIN_RATE = 0.80          # subject win-rate at/above this (+ HP) -> win
LOSS_RATE = 0.20         # subject win-rate at/below this (+ opp HP) -> loss
WIN_HP_MIN = 5.0         # the winner must keep more than this % army HP
BONUS_MIN = 1            # an attack bonus must be strictly > this to count
BASE_ATTACK_CLASSES = {"3", "4"}   # base pierce / base melee — never a "bonus"

# Normal-counter graph (broad class X counters the classes in its set).
COUNTERS = {
    "infantry": {"cavalry", "infantry"},
    "ranged":   {"infantry", "ranged"},
    "cavalry":  {"ranged", "cavalry"},
}

# Narrative order + which categories are losses (showcase picks cheapest for these).
CATEGORY_ORDER = ("expected_win", "unexpected_win", "coin_flip",
                  "unexpected_loss", "expected_loss")
LOSS_CATEGORIES = {"expected_loss", "unexpected_loss"}


def _as_dict(j):
    """attacks/armors may arrive as a JSON string or an already-parsed dict."""
    if isinstance(j, str):
        return json.loads(j or "{}")
    return j or {}


def bonus_classes(attacks):
    """Attack classes that are a real damage bonus: not base melee/pierce and
    with a value strictly greater than BONUS_MIN."""
    return {k for k, v in _as_dict(attacks).items()
            if k not in BASE_ATTACK_CLASSES and v and v > BONUS_MIN}


def armor_classes(armors):
    """The set of armor classes a unit carries (keys of its armor dict)."""
    return set(_as_dict(armors).keys())


def broad_class(cat, is_ranged):
    """Collapse a fine unit category into the counter-triangle's broad class."""
    if is_ranged:
        return "ranged"
    if cat in ("cavalry", "camel", "light_cav", "elephant"):
        return "cavalry"
    return "infantry"          # infantry, spear, eagle


def outcome(subject_winrate, subject_hp, opp_hp):
    """win / loss / coinflip from the V2 win-rate + surviving-army-HP bands."""
    if subject_winrate >= WIN_RATE and subject_hp > WIN_HP_MIN:
        return "win"
    if subject_winrate <= LOSS_RATE and opp_hp > WIN_HP_MIN:
        return "loss"
    return "coinflip"


def favored(subject_bonus, opp_bonus, subject_counter, opp_counter):
    """Who the fight favors, by the bonus-first cascade. -> subject / opponent /
    both / neither."""
    if subject_bonus and opp_bonus:
        return "both"
    if subject_bonus:
        return "subject"
    if opp_bonus:
        return "opponent"
    if subject_counter and opp_counter:
        return "neither"       # mutual counter (e.g. inf vs inf) — a fair fight
    if subject_counter:
        return "subject"
    if opp_counter:
        return "opponent"
    return "neither"


def category_for(out, fav):
    """Map (outcome, favored) onto exactly one of the five categories."""
    if out == "coinflip":
        return "coin_flip"
    if fav == "both":
        return "unexpected_win" if out == "win" else "unexpected_loss"
    if out == "win":
        return "expected_win" if fav in ("subject", "neither") else "unexpected_win"
    return "expected_loss" if fav in ("opponent", "neither") else "unexpected_loss"


def make_subject(cat, is_ranged, speed, attacks, armors):
    """Precompute the subject's derived fields once (bonus set, armor set, class)."""
    return {
        "cat": cat, "ranged": bool(is_ranged), "speed": speed,
        "broad": broad_class(cat, is_ranged),
        "bonus": bonus_classes(attacks),
        "armor": armor_classes(armors),
    }


def classify(subject, *, cat, ranged, speed, attacks, armors,
             subject_winrate, subject_hp, opp_hp,
             ingame_outcome=None, melee_only=True):
    """Classify one opponent against a make_subject() descriptor.

    Returns a dict with the resolved class / outcome / favored / category and the
    four advantage flags (subject_bonus, subject_counter, opp_bonus, opp_counter).
    ``ingame_outcome`` (one of "win"/"loss"/"coinflip") overrides the V2-derived
    outcome for matchups the V2 model is known to get wrong (validated in-game).
    """
    ocls = broad_class(cat, ranged)
    subject_counter = ocls in COUNTERS[subject["broad"]]
    opp_counter = subject["broad"] in COUNTERS[ocls]
    # Skirmisher/spearman override, speed-gated: a non-kiting skirm/spear is weak
    # vs infantry (countered by it, does not counter it); a mounted skirmisher
    # faster than the subject kites and behaves like a normal ranged unit.
    kites = ranged and speed > subject["speed"]
    if cat in ("skirm", "spear") and not kites:
        subject_counter, opp_counter = True, False
    # Damage bonuses (> 1). Melee gating: a melee subject's bonus is ignored vs a
    # ranged opponent it can never catch.
    subject_bonus_raw = bool(subject["bonus"] & armor_classes(armors))
    opp_bonus = bool(bonus_classes(attacks) & subject["armor"])
    if melee_only and not subject["ranged"] and ranged:
        subject_bonus = False
    else:
        subject_bonus = subject_bonus_raw
    out = ingame_outcome or outcome(subject_winrate, subject_hp, opp_hp)
    fav = favored(subject_bonus, opp_bonus, subject_counter, opp_counter)
    return {
        "class": ocls, "outcome": out, "favored": fav,
        "category": category_for(out, fav),
        "subject_bonus": subject_bonus, "subject_counter": subject_counter,
        "opp_bonus": opp_bonus, "opp_counter": opp_counter,
    }


def _cost_key(category, cost):
    """Sort key that puts the showcase-preferred unit first: losses -> cheapest
    (ascending cost); wins/coin-flips -> most expensive (descending cost)."""
    return cost if category in LOSS_CATEGORIES else -cost


def sort_rows(rows):
    """Full-table order: by narrative category, then the per-category cost key."""
    return sorted(rows, key=lambda r: (CATEGORY_ORDER.index(r["category"]),
                                       _cost_key(r["category"], r["cost"])))


def pick_showcase(rows, *, max_per_cat=5, exclude=()):
    """Choose up to ``max_per_cat`` showcase opponents per category.

    Wins & (unused) coin-flips -> the most expensive opponents; losses -> the
    cheapest the subject loses to. Coin-flips get NO showcase (listed with odds
    instead). ``exclude`` is a set of (civ, slug) to never showcase.
    Each row needs: category, cost, civ, slug.
    """
    exclude = {tuple(e) for e in exclude}
    out = {}
    for cat in CATEGORY_ORDER:
        if cat == "coin_flip":
            out[cat] = []
            continue
        cands = [r for r in rows
                 if r["category"] == cat and (r["civ"], r["slug"]) not in exclude]
        cands.sort(key=lambda r: _cost_key(cat, r["cost"]))
        out[cat] = cands[:max_per_cat]
    return out
