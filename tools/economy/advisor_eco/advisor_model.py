"""Throwaway Python copy of apps/web/src/features/advisor/model.mjs (+ proposed rule).

``recommend_pair(rows, units, semi=None, variant="current")``:
  * variant "current": a line-by-line port of ``buildAdvisorRecommendations``;
    ``check_js_parity.py`` compares it with the real module for all 1,540 pairs.
  * variant "eco": proposed rule. A row flagged in ``semi`` (the own unit loses
    narrowly but its army is >= 33% cheaper to rebuild) is neither a loss nor a
    win: it leaves ``losses`` (so no counter is assigned) and the enemy's
    ``wins`` (so it adds nothing to that enemy's threat weight) and is listed as
    ``semi_losses`` / ``semi_wins`` caveats. A unit with no remaining losses but
    at least one semi-loss is a *strong contender*.
  * variant "eco_main": "eco" + the main unit is the best-ranked gold strong
    contender with wins when one exists (otherwise the usual rule).

Rows are the advisor API rows ``[a, b, outcome, evidence, count_a, count_b, tier, flags, evidence_id]``
from the left civilization's perspective. ``semi`` is a set of (a, b) unit-id
pairs whose cell the *loser* side is ``a`` ... see ``semi_flag``.
"""
from __future__ import annotations

from functools import cmp_to_key


def unit_weight(unit):
    return 1 if float(unit["costs"]["gold"]) > 0 else 0.5


def invert(row):
    outcome = {"a_win": "b_win", "b_win": "a_win"}.get(row[2], row[2])
    return [row[1], row[0], outcome, row[3], row[5], row[4], *row[6:]]


def _sum(values, score):
    total = 0
    for value in values:
        total += score(value)
    return total


def _compare(a, b):
    for key in (lambda e: -e["score"], lambda e: -e["win_weight"], lambda e: -unit_weight(e["unit"])):
        x, y = key(a), key(b)
        if x != y:
            return -1 if x < y else 1
    if a["unit"]["name"] != b["unit"]["name"]:
        # JS localeCompare; names are ASCII-ish, checked by the parity script.
        return -1 if a["unit"]["name"].lower() < b["unit"]["name"].lower() or (
            a["unit"]["name"].lower() == b["unit"]["name"].lower() and a["unit"]["name"] < b["unit"]["name"]) else 1
    return a["unit"]["id"] - b["unit"]["id"]


def _group(rows, units, semi):
    grouped = {}
    for row in rows:
        if row[0] not in units or row[1] not in units:
            raise ValueError("Unknown matchup unit")
        grouped.setdefault(row[0], {"unit": units[row[0]], "matches": []})["matches"].append(row)
    out = []
    for entry in grouped.values():
        m = entry["matches"]
        is_semi = (lambda row: (row[0], row[1]) in semi) if semi else (lambda row: False)
        out.append({**entry,
                    "wins": [r for r in m if r[2] == "a_win" and not is_semi(r)],
                    "semi_wins": [r for r in m if r[2] == "a_win" and is_semi(r)],
                    "losses": [r for r in m if r[2] == "b_win" and not is_semi(r)],
                    "semi_losses": [r for r in m if r[2] == "b_win" and is_semi(r)],
                    "close": [r for r in m if r[2] in ("equivalent", "close_uncertain")]})
    return out


def _recommend(own, enemy, units, variant):
    threats = {e["unit"]["id"]: unit_weight(e["unit"]) * (1 + _sum(e["wins"], lambda r: unit_weight(units[r[1]])))
               for e in enemy}
    threat = lambda row: threats[row[1]]  # noqa: E731
    ranked = [{**e, "score": _sum(e["wins"], threat), "win_weight": _sum(e["wins"], lambda r: unit_weight(units[r[1]]))}
              for e in own]
    ranked.sort(key=cmp_to_key(_compare))
    sort_threats = lambda rows: sorted(rows, key=lambda r: (-threat(r), r[1]))  # noqa: E731
    for e in ranked:
        for key in ("wins", "losses", "close", "semi_losses", "semi_wins"):
            e[key] = sort_threats(e[key])
        e["contender"] = not e["losses"] and bool(e["semi_losses"])
    main = None
    if variant == "eco_main":
        main = next((e for e in ranked if unit_weight(e["unit"]) == 1 and e["wins"] and e["contender"]), None)
    main = main or next((e for e in ranked if unit_weight(e["unit"]) == 1 and e["wins"]), None) or (ranked[0] if ranked else None)
    if main is None:
        return {"main": None, "sidekick": None, "alternatives": [], "threats": threats, "uncovered": [],
                "additions": [], "unanswered": [], "ranked": ranked}
    weaknesses = {r[1] for r in main["losses"]}
    main_wins = {r[1] for r in main["wins"]}
    candidates = []
    for e in ranked:
        if e["unit"]["id"] == main["unit"]["id"] or unit_weight(e["unit"]) != 0.5:
            continue
        covers = [r for r in e["wins"] if r[1] in weaknesses]
        holds = [r for r in e["close"] if r[1] in weaknesses]
        new = [r for r in e["wins"] if r[1] not in main_wins]
        candidates.append({**e, "covers": covers, "holds_close": holds, "new_wins": new,
                           "cover_score": _sum(covers, threat), "close_score": _sum(holds, threat),
                           "new_score": _sum(new, threat)})

    def cand_cmp(a, b):
        for key in ("cover_score", "close_score", "new_score"):
            if a[key] != b[key]:
                return -1 if a[key] > b[key] else 1
        return _compare(a, b)
    candidates.sort(key=cmp_to_key(cand_cmp))
    sidekick = candidates[0] if candidates else None
    covered = {r[1] for r in sidekick["covers"]} if sidekick else set()
    uncovered = [r for r in main["losses"] if r[1] not in covered]
    remaining = {r[1] for r in uncovered}
    additions = []
    while remaining:
        options = []
        for e in ranked:
            if e["unit"]["id"] == main["unit"]["id"] or (sidekick and e["unit"]["id"] == sidekick["unit"]["id"]):
                continue
            covers = [r for r in e["wins"] if r[1] in remaining]
            if covers:
                options.append({"entry": e, "covers": covers})
        if not options:
            break

        def opt_cmp(a, b):
            sa, sb = _sum(a["covers"], threat), _sum(b["covers"], threat)
            if sa != sb:
                return -1 if sa > sb else 1
            if len(a["covers"]) != len(b["covers"]):
                return -1 if len(a["covers"]) > len(b["covers"]) else 1
            return _compare(a["entry"], b["entry"])
        options.sort(key=cmp_to_key(opt_cmp))
        best = options[0]
        additions.append({"unit": best["entry"]["unit"], "covers": best["covers"]})
        for r in best["covers"]:
            remaining.discard(r[1])
    sid = sidekick["unit"]["id"] if sidekick else None
    alternatives = [e for e in ranked if e["unit"]["id"] != main["unit"]["id"] and e["unit"]["id"] != sid and e["wins"]][:3]
    return {"main": main, "sidekick": sidekick, "threats": threats, "uncovered": uncovered, "additions": additions,
            "unanswered": [r for r in uncovered if r[1] in remaining], "alternatives": alternatives, "ranked": ranked}


def build(rows, units, semi=None, variant="current"):
    """``semi``: set of (loser_unit_id, winner_unit_id) cells labelled narrow-loss-cheaper-rebuild."""
    flags = set()
    if semi and variant != "current":
        for loser, winner in semi:
            flags.add((loser, winner))   # row from the loser's side: b_win -> semi loss
            flags.add((winner, loser))   # row from the winner's side: a_win -> semi win
    left = _group(rows, units, flags)
    right = _group([invert(r) for r in rows], units, flags)
    return {"left": _recommend(left, right, units, variant), "right": _recommend(right, left, units, variant)}


def summary(plan):
    """Compact, comparable form of a plan (ids only)."""
    ident = lambda e: e["unit"]["id"] if e else None  # noqa: E731
    return {"main": ident(plan["main"]), "sidekick": ident(plan["sidekick"]),
            "additions": [[a["unit"]["id"], [r[1] for r in a["covers"]]] for a in plan["additions"]],
            "unanswered": [r[1] for r in plan["unanswered"]],
            "uncovered": [r[1] for r in plan["uncovered"]],
            "alternatives": [e["unit"]["id"] for e in plan["alternatives"]],
            "main_losses": [r[1] for r in plan["main"]["losses"]] if plan["main"] else [],
            "main_wins": [r[1] for r in plan["main"]["wins"]] if plan["main"] else []}
