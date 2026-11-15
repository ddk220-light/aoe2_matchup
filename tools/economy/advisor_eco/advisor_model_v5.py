"""Matchup Advisor, Revision 5 (owner design 2026-11-15): reference plan for one civ vs one civ.

Input: the rows ``/api/advisor-matchups/<civ>`` serves for one opponent civ (own unit first,
``row[9]`` = matchup value from the own unit's side, see ``advisor_value.py``).

1. Opponent multiplier: each enemy unit's average value against our roster (its own side),
   ``m = clamp(1 + MULTIPLIER_SLOPE x average, MULTIPLIER_MIN, MULTIPLIER_MAX)``.
2. Weighted contribution of our unit i against enemy j:
   ``value x m_j`` for a win or draw, ``value x (2 - m_j)`` for a loss
   (beating a strong unit counts more; losing to a weak one hurts more).
3. Weighted score = sum of contributions. Main and support are chosen as a pair (owner
   2026-11-15): for every eligible main (never a Scorpion) its support is found (rule 4); pairs
   rank by the strength of the enemy units beaten by either unit (sum of their multipliers; a
   draw counts half), then pair score (the better of the two weighted contributions per enemy
   unit), then the main's weighted score, then id.
4. Support = a unit without gold, other than the main (owner 2026-11-15):
   - holes = enemy units the main does not beat (value <= 0), strongest first (multiplier);
   - the strongest hole some candidate does better on than the main decides: the support is
     the candidate with the best value against it (ties: improvement over all holes, raw value
     difference x enemy multiplier, then weighted score);
   - no hole, or no candidate improves any: the main's weak wins (contribution < GAP), support =
     the biggest strength-weighted improvement there;
   - otherwise the candidate with the best weighted score.
5. Enemy units neither the main nor the support beats (value <= 0): the other unit with the
   best contribution against each becomes an addition (grouped by unit) when it does better
   than both of them (it need not win); otherwise the enemy is listed as unanswered
   ("no better counter": the main and support already have the best outcome).
6. Siege fallback (owner 2026-11-15): when the own civ has Siege Onager, Onager with Siege
   Engineers or a Bombard Cannon (``data/golden/advisor_siege.json``), enemy units on the siege
   target list (slow siege, foot archers, skirmishers, foot gunpowder, elephant archers) are
   left to siege: the support ignores them, pair ranking counts them as beaten (score 0 when
   the pair itself does not beat them), and those the pair does not beat are listed as siege
   covers, before any extra unit.

Ties: higher weighted score, then lower unit id. Sums run in ascending unit id order with
plain float additions, exactly as apps/web/src/features/advisor/model.mjs (the browser twin;
tests/advisor/v5-parity.test.mjs pins them together for all 3,080 plans).
"""
from __future__ import annotations

MULTIPLIER_SLOPE = 0.7
MULTIPLIER_MIN = 0.5
MULTIPLIER_MAX = 1.5
GAP = 0.5
EXCLUDED_MAIN = ("Scorpion", "Heavy Scorpion")
SUPPORT_EXTRA = ()  # owner 2026-11-15: Scorpions only as extra units, never support

CONFIG = {"multiplierSlope": MULTIPLIER_SLOPE, "multiplierMin": MULTIPLIER_MIN, "multiplierMax": MULTIPLIER_MAX,
          "gap": GAP, "excludedMain": list(EXCLUDED_MAIN), "supportExtra": list(SUPPORT_EXTRA)}


def is_gold(unit):
    return float(unit["costs"].get("gold", 0) or 0) > 0


def siege_for(civ, siege):
    """(options, target names) for one civ from advisor_siege.json data; empty without siege."""
    if not siege or not siege["civs"].get(civ):
        return [], set()
    return list(siege["civs"][civ]), set(siege["targets"])


def plan(rows, units, siege=None):
    """``units``: advisor unit id -> unit (name, costs, civilization). Returns the plan dict."""
    value = {(r[0], r[1]): r[9] for r in rows}
    own = sorted({r[0] for r in rows})
    enemy = sorted({r[1] for r in rows})
    assert len(value) == len(own) * len(enemy), "incomplete matchup matrix"
    multiplier = {}
    for j in enemy:
        total = 0.0
        for i in own:
            total += -value[(i, j)]
        multiplier[j] = min(MULTIPLIER_MAX, max(MULTIPLIER_MIN, 1 + MULTIPLIER_SLOPE * (total / len(own))))
    contribution, score = {}, {}
    for i in own:
        total = 0.0
        for j in enemy:
            v = value[(i, j)]
            c = v * multiplier[j] if v >= 0 else v * (2 - multiplier[j])
            contribution[(i, j)] = c
            total += c
        score[i] = total

    options, targets = siege_for(units[own[0]]["civilization"], siege)
    siege_cover = {j for j in enemy if units[j]["name"] in targets}

    def best(candidates, key):
        return min(candidates, key=lambda i: (-key(i), -score[i], i)) if candidates else None

    def support_for(main):
        """(support, reason, target, holes) for one main (rule 4)."""
        candidates = [i for i in own if i != main and (not is_gold(units[i]) or units[i]["name"] in SUPPORT_EXTRA)]
        holes = sorted([j for j in enemy if value[(main, j)] <= 0 and j not in siege_cover],
                       key=lambda j: (-multiplier[j], j))

        def gain(s, targets):
            total = 0.0
            for j in targets:
                total += max(0.0, value[(s, j)] - value[(main, j)]) * multiplier[j]
            return total

        for t in holes:
            better = [s for s in candidates if value[(s, t)] > value[(main, t)]]
            if better:
                return min(better, key=lambda s: (-value[(s, t)], -gain(s, holes), -score[s], s)), "threat", t, holes
        weak = [j for j in enemy if value[(main, j)] > 0 and contribution[(main, j)] < GAP]
        helped = [s for s in candidates if gain(s, weak) > 0]
        if helped:
            return best(helped, lambda s: gain(s, weak)), "weak_wins", None, holes
        if candidates:
            return best(candidates, lambda s: score[s]), "score", None, holes
        return None, None, None, holes

    pairs = {}
    for m in [i for i in own if units[i]["name"] not in EXCLUDED_MAIN]:
        found = support_for(m)
        members = [m] + ([found[0]] if found[0] is not None else [])
        wins = draws = 0
        beaten, total = 0.0, 0.0
        for j in enemy:
            top = max(value[(i, j)] for i in members)
            if top > 0:
                wins += 1
                beaten += multiplier[j]
                total += max(contribution[(i, j)] for i in members)
            elif j in siege_cover:
                wins += 1
                beaten += multiplier[j]
            elif top == 0:
                draws += 1
                beaten += 0.5 * multiplier[j]
                total += max(contribution[(i, j)] for i in members)
            else:
                total += max(contribution[(i, j)] for i in members)
        pairs[m] = (found, beaten, total, wins + 0.5 * draws)
    main = min(pairs, key=lambda m: (-pairs[m][1], -pairs[m][2], -score[m], m))
    (support, reason, target, holes), pair_beaten, pair_score, pair_wins = pairs[main]
    pair = [main] + ([support] if support is not None else [])
    additions, unanswered, siege_covers = {}, [], []
    for j in enemy:
        if any(value[(i, j)] > 0 for i in pair):
            continue
        if j in siege_cover:
            siege_covers.append(j)
            continue
        pair_best = max(contribution[(i, j)] for i in pair)
        better = [i for i in own if i not in pair and contribution[(i, j)] > pair_best]
        counter = best(better, lambda i: contribution[(i, j)])
        if counter is None:
            unanswered.append(j)
        else:
            additions.setdefault(counter, []).append(j)
    order = sorted(additions, key=lambda i: (-len(additions[i]), -score[i], i))
    return {"main": main, "support": support, "supportReason": reason, "supportTarget": target,
            "pairWins": pair_wins, "pairBeaten": pair_beaten, "pairScore": pair_score, "holes": holes, "siege": options if siege_covers else [], "siegeCovers": siege_covers,
            "additions": [[i, additions[i]] for i in order], "unanswered": unanswered,
            "score": score, "multiplier": multiplier, "contribution": contribution}
