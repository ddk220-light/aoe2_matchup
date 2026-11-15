"""Matchup Advisor, Revision 5 (owner design 2026-11-15): reference plan for one civ vs one civ.

Input: the rows ``/api/advisor-matchups/<civ>`` serves for one opponent civ (own unit first,
``row[9]`` = matchup value from the own unit's side, see ``advisor_value.py``).

1. Opponent multiplier: each enemy unit's average value against our roster (its own side),
   ``m = clamp(1 + MULTIPLIER_SLOPE x average, MULTIPLIER_MIN, MULTIPLIER_MAX)``.
2. Weighted contribution of our unit i against enemy j:
   ``value x m_j`` for a win or draw, ``value x (2 - m_j)`` for a loss
   (beating a strong unit counts more; losing to a weak one hurts more).
3. Weighted score = sum of contributions. Main = highest weighted score, never a Scorpion.
4. Support = a unit without gold, or a Scorpion, other than the main, covering the most of the
   main's gaps: enemies where the main's contribution is below GAP; gain = sum of
   max(0, support contribution - main contribution) there. No gain anywhere -> the candidate
   with the best weighted score.
5. Enemy units neither the main nor the support beats (value <= 0): the other unit with the
   best winning contribution against each becomes an addition (grouped by unit); when no unit
   beats it, it is listed as unanswered ("no better counter").

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
SUPPORT_EXTRA = ("Scorpion", "Heavy Scorpion")

CONFIG = {"multiplierSlope": MULTIPLIER_SLOPE, "multiplierMin": MULTIPLIER_MIN, "multiplierMax": MULTIPLIER_MAX,
          "gap": GAP, "excludedMain": list(EXCLUDED_MAIN), "supportExtra": list(SUPPORT_EXTRA)}


def is_gold(unit):
    return float(unit["costs"].get("gold", 0) or 0) > 0


def plan(rows, units):
    """``units``: advisor unit id -> unit (name, costs). Returns the plan dict."""
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

    def best(candidates, key):
        return min(candidates, key=lambda i: (-key(i), -score[i], i)) if candidates else None

    main = best([i for i in own if units[i]["name"] not in EXCLUDED_MAIN], lambda i: score[i])
    gaps = [j for j in enemy if contribution[(main, j)] < GAP]
    candidates = [i for i in own if i != main and (not is_gold(units[i]) or units[i]["name"] in SUPPORT_EXTRA)]
    gains = {}
    for s in candidates:
        total = 0.0
        for j in gaps:
            total += max(0.0, contribution[(s, j)] - contribution[(main, j)])
        gains[s] = total
    support = best([s for s in candidates if gains[s] > 0], lambda s: gains[s]) or best(candidates, lambda s: score[s])
    pair = [main] + ([support] if support is not None else [])
    additions, unanswered = {}, []
    for j in enemy:
        if any(value[(i, j)] > 0 for i in pair):
            continue
        winners = [i for i in own if i not in pair and value[(i, j)] > 0]
        counter = best(winners, lambda i: contribution[(i, j)])
        if counter is None:
            unanswered.append(j)
        else:
            additions.setdefault(counter, []).append(j)
    order = sorted(additions, key=lambda i: (-len(additions[i]), -score[i], i))
    return {"main": main, "support": support, "supportGain": gains.get(support, 0.0) if support is not None else None,
            "gaps": gaps, "additions": [[i, additions[i]] for i in order], "unanswered": unanswered,
            "score": score, "multiplier": multiplier, "contribution": contribution}
