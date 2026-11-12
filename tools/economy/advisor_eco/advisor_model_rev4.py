"""Revision 4 scratch advisor model (owner request 2026-11-12): category-weighted scoring
with an opponent-strength multiplier, no Scorpion mains, trash-or-Scorpion support.

Not site code. Python only (no JS twin yet). See docs/army-economics/ADVISOR_ECO_DESIGN.md,
"Revision 4". Everything tunable lives in WEIGHT_SETS and CONFIG.

Per plan (own civ X vs enemy civ Y), every own-unit x enemy-unit row gets one category
from the own unit's side (classify.py, Revision 3 rules; inferred cells = "pending",
scored as plain win / plain loss and flagged; identity and close cells = close):

  1. base(u)      = sum over Y's units j of  W[cat(u, j)]
  2. strength(j)  = base(j) of Y's unit j (scored against X's roster), normalised across
                    Y's roster to [lo, hi] (default min-max to [0.5, 1.5])
  3. advantage(u) = sum over j of  W[cat] * strength(j)            if W[cat] >= 0
                                   W[cat] * (lo + hi - strength(j)) if W[cat] <  0
     (credit grows with the opponent's strength, blame grows with its weakness)
  4. main = best advantage among eligible units (not Scorpion / Heavy Scorpion) that cost
     gold and have at least one win; fallback: best eligible unit.
  5. targets  = main's losses (any loss category, eco win included) + main's struggles
                (close, power win, or a win where the main keeps < struggle_hp of its HP)
     support  = a no-gold unit or a Scorpion / Heavy Scorpion, not the main, that helps
                against the most valuable targets:
                help(s, j) = W[cat(s, j)] - W[cat(main, j)] if positive; or, same weight and
                both win, a tie bonus when s keeps >= help_hp_margin more HP or its army is
                >= help_eco cheaper. support score = sum strength(j) * help(s, j).
  6. additions = greedy counters (any unit except main and support, wins only) for the
     main's real losses (not eco wins) that the support does not beat; weighted by strength.

Deterministic tie-breaks everywhere (score, then name, then id).
"""
from __future__ import annotations

CATS = ["dominance", "kite", "plain_win", "power_win", "eco_win", "close",
        "cheap_loss", "plain_loss", "kited_loss", "outclassed_loss"]
WIN_CATS = {"dominance", "kite", "plain_win", "power_win"}
LOSS_CATS = {"eco_win", "cheap_loss", "plain_loss", "kited_loss", "outclassed_loss"}
LABEL = {"dominance": "Complete dominance", "kite": "Clear win (kite)", "plain_win": "Plain win",
         "power_win": "Power win", "eco_win": "Eco win", "close": "Close", "cheap_loss": "Cheap loss",
         "plain_loss": "Plain loss", "kited_loss": "Kited loss", "outclassed_loss": "Outclassed loss"}

WEIGHT_SETS = {
    # Proposed default: a plain win is the unit; cost-efficiency moves a result by about half a unit.
    "default": {"dominance": 1.5, "kite": 1.5, "plain_win": 1.0, "power_win": 0.6, "eco_win": 0.25,
                "close": 0.0, "cheap_loss": -0.25, "plain_loss": -0.5, "kited_loss": -0.75,
                "outclassed_loss": -0.75},
    # Rewards economy: dominance and eco wins count more, expensive wins less, cheap losses are free.
    "eco": {"dominance": 2.0, "kite": 1.5, "plain_win": 1.0, "power_win": 0.3, "eco_win": 0.6,
            "close": 0.0, "cheap_loss": 0.0, "plain_loss": -0.5, "kited_loss": -0.75,
            "outclassed_loss": -1.0},
    # Raw combat: only the battle result counts (any win +1, any loss -0.5), cost ignored.
    "combat": {"dominance": 1.0, "kite": 1.0, "plain_win": 1.0, "power_win": 1.0, "eco_win": -0.5,
               "close": 0.0, "cheap_loss": -0.5, "plain_loss": -0.5, "kited_loss": -0.5,
               "outclassed_loss": -0.5},
}

CONFIG = {
    "strength": "minmax",     # minmax | rank | none
    "lo": 0.5, "hi": 1.5,     # strength range
    "gold_main": True,        # prefer a gold main with at least one win
    "struggle_hp": 0.50,      # a win where the main keeps < this share of HP is a struggle
    "struggle_power": True,   # a power win (main's army >= 25% dearer) is a struggle
    "struggle_close": True,   # a close result is a struggle
    "help_hp_margin": 0.15,   # same result: support keeps >= 15 HP points more
    "help_eco": 0.25,         # same result: support army >= 25% cheaper (60-s investment)
    "help_tie_bonus": 0.25,   # help value of a same-result-but-better help
    "excluded_main": ("Scorpion", "Heavy Scorpion"),
    "support_extra": ("Scorpion", "Heavy Scorpion"),  # gold units allowed as support
}


def is_gold(unit):
    return float(unit["costs"]["gold"]) > 0


# --------------------------------------------------------------------------- categories
WIN_KEY = {"kite": "kite", "dominance": "dominance", "power": "power_win", "plain": "plain_win"}
LOSS_KEY = {"kite": "kited_loss", "dominance": "outclassed_loss", "eco": "eco_win", "cheap": "cheap_loss",
            "nohp": "cheap_loss", "plain": "plain_loss"}


def cell_index(cells, mo, classify):
    """(own, opp) -> info for every observed decided cell, from both sides."""
    idx = {}
    for c in cells:
        if c["outcome"] not in ("a_win", "b_win") or c["vm_a"] is None or c["vm_b"] is None:
            continue
        wk, lk, w = classify(c, mo)
        l = "b" if w == "a" else "a"
        hp = c["hp_avg"]
        for own, opp, cat, won in ((w, l, WIN_KEY[wk], True), (l, w, LOSS_KEY[lk], False)):
            idx[(c[own], c[opp])] = {"cat": cat, "won": won, "hp_winner": hp, "hp_own": (hp if won else 0.0),
                                     "vm_own": c["vm_" + own], "vm_opp": c["vm_" + opp], "seeds": c["seeds"],
                                     "n_own": c["count_" + own], "n_opp": c["count_" + opp], "pending": False,
                                     "nohp": lk == "nohp"}
    return idx


def row_info(row, idx):
    """Category info for an advisor row [a, b, outcome, evidence_type, ...] seen from a."""
    a, b, outcome, evidence = row[0], row[1], row[2], row[3]
    if outcome in ("equivalent", "close_uncertain") or evidence == "identity":
        return {"cat": "close", "won": False, "pending": False, "hp_own": None, "hp_winner": None,
                "vm_own": None, "vm_opp": None}
    if evidence == "inferred":
        won = outcome == "a_win"
        return {"cat": "plain_win" if won else "plain_loss", "won": won, "pending": True, "hp_own": None,
                "hp_winner": None, "vm_own": None, "vm_opp": None}
    info = idx.get((a, b))
    if info is None:  # observed and decided but no economics (none today)
        won = outcome == "a_win"
        return {"cat": "plain_win" if won else "plain_loss", "won": won, "pending": False, "hp_own": None,
                "hp_winner": None, "vm_own": None, "vm_opp": None}
    return info


def invert(row):
    outcome = {"a_win": "b_win", "b_win": "a_win"}.get(row[2], row[2])
    return [row[1], row[0], outcome, row[3], row[5], row[4], *row[6:]]


# --------------------------------------------------------------------------- scoring
def normalise(scores, cfg):
    lo, hi = cfg["lo"], cfg["hi"]
    if cfg["strength"] == "none" or not scores:
        return {k: 1.0 for k in scores}
    if cfg["strength"] == "rank":
        order = sorted(scores, key=lambda k: (scores[k], k))
        n = len(order)
        if n == 1:
            return {order[0]: 1.0}
        ranks = {}
        i = 0
        while i < n:  # average rank for ties
            j = i
            while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
                j += 1
            for k in order[i:j + 1]:
                ranks[k] = (i + j) / 2
            i = j + 1
        return {k: lo + (hi - lo) * ranks[k] / (n - 1) for k in scores}
    mn, mx = min(scores.values()), max(scores.values())
    if mx == mn:
        return {k: (lo + hi) / 2 for k in scores}
    return {k: lo + (hi - lo) * (v - mn) / (mx - mn) for k, v in scores.items()}


def _entries(rows, units, idx):
    out = {}
    for row in rows:
        e = out.setdefault(row[0], {"unit": units[row[0]], "vs": {}})
        e["vs"][row[1]] = row_info(row, idx)
    return out


def _base(entries, w):
    for e in entries.values():
        e["base"] = sum(w[i["cat"]] for i in e["vs"].values())


def _advantage(entries, w, strength, cfg):
    s = cfg["lo"] + cfg["hi"]
    for e in entries.values():
        total = 0.0
        for opp, i in e["vs"].items():
            wt = w[i["cat"]]
            total += wt * (strength[opp] if wt >= 0 else s - strength[opp])
        e["adv"] = total
        e["n_wins"] = sum(1 for i in e["vs"].values() if i["cat"] in WIN_CATS)


def _rank_key(e):
    return (-round(e["adv"], 9), -round(e["base"], 9), not is_gold(e["unit"]), e["unit"]["name"], e["unit"]["id"])


def struggles(info, cfg):
    cat = info["cat"]
    if cat == "close":
        return cfg["struggle_close"]
    if cat not in WIN_CATS:
        return False
    if cat == "power_win" and cfg["struggle_power"]:
        return True
    return info["hp_own"] is not None and info["hp_own"] < cfg["struggle_hp"]


def help_value(si, mi, w, cfg):
    """(value, reason) of support row si against the main's row mi for the same target."""
    gain = w[si["cat"]] - w[mi["cat"]]
    if gain > 1e-12:
        return gain, "better"
    if abs(gain) <= 1e-12 and si["cat"] in WIN_CATS and mi["cat"] in WIN_CATS:
        if si["hp_own"] is not None and mi["hp_own"] is not None and si["hp_own"] >= mi["hp_own"] + cfg["help_hp_margin"]:
            return cfg["help_tie_bonus"], "more_hp"
        if si["vm_own"] is not None and mi["vm_own"] is not None and si["vm_own"] <= (1 - cfg["help_eco"]) * mi["vm_own"]:
            return cfg["help_tie_bonus"], "cheaper"
    return 0.0, None


def _recommend(own, enemy, strength, w, cfg):
    ranked = sorted(own.values(), key=_rank_key)
    excluded = set(cfg["excluded_main"])
    eligible = [e for e in ranked if e["unit"]["name"] not in excluded]
    main = None
    if cfg["gold_main"]:
        main = next((e for e in eligible if is_gold(e["unit"]) and e["n_wins"]), None)
    main = main or (eligible[0] if eligible else None)
    top = eligible[0] if eligible else None
    result = {"ranked": ranked, "main": main, "top_eligible": top, "top_overall": ranked[0] if ranked else None,
              "support": None, "targets": [], "additions": [], "unanswered": [], "alternatives": []}
    if main is None:
        return result
    targets = []
    for opp, mi in main["vs"].items():
        if mi["cat"] in LOSS_CATS:
            targets.append((opp, "loss"))
        elif struggles(mi, cfg):
            targets.append((opp, "struggle"))
    targets.sort(key=lambda t: (-strength[t[0]], t[0]))
    result["targets"] = targets
    extra = set(cfg["support_extra"])
    cands = []
    for e in ranked:
        if e is main or not (not is_gold(e["unit"]) or e["unit"]["name"] in extra):
            continue
        helps = []
        for opp, kind in targets:
            v, why = help_value(e["vs"][opp], main["vs"][opp], w, cfg)
            if v > 0:
                helps.append({"opp": opp, "kind": kind, "value": v, "why": why, "credit": strength[opp] * v})
        score = sum(h["credit"] for h in helps)
        converts = sum(1 for h in helps if e["vs"][h["opp"]]["cat"] in WIN_CATS and h["kind"] == "loss")
        cands.append({"entry": e, "helps": helps, "score": score, "converts": converts})
    cands.sort(key=lambda c: (-round(c["score"], 9), -c["converts"]) + _rank_key(c["entry"]))
    support = cands[0] if cands and cands[0]["score"] > 0 else None
    result["support"] = support
    result["support_candidates"] = cands
    beaten = {opp for opp, i in support["entry"]["vs"].items() if i["cat"] in WIN_CATS} if support else set()
    real_losses = [opp for opp, i in main["vs"].items() if i["cat"] in LOSS_CATS and i["cat"] != "eco_win"]
    remaining = {opp for opp in real_losses if opp not in beaten}
    result["uncovered"] = sorted(remaining, key=lambda o: (-strength[o], o))
    taken = {main["unit"]["id"]} | ({support["entry"]["unit"]["id"]} if support else set())
    while remaining:
        options = []
        for e in ranked:
            if e["unit"]["id"] in taken:
                continue
            covers = [o for o in remaining if e["vs"][o]["cat"] in WIN_CATS]
            if covers:
                options.append((-round(sum(strength[o] for o in covers), 9), -len(covers)) + _rank_key(e) + (e, covers))
        if not options:
            break
        options.sort(key=lambda t: t[:-2])
        e, covers = options[0][-2], options[0][-1]
        result["additions"].append({"entry": e, "covers": sorted(covers, key=lambda o: (-strength[o], o))})
        taken.add(e["unit"]["id"])
        remaining -= set(covers)
    result["unanswered"] = sorted(remaining, key=lambda o: (-strength[o], o))
    result["alternatives"] = [e for e in eligible if e["unit"]["id"] not in taken and e["n_wins"]][:3]
    return result


def build(rows, units, idx, weights="default", cfg=None):
    """Both plans for one civ pair. rows: advisor API rows from the left civ's side."""
    cfg = {**CONFIG, **(cfg or {})}
    w = WEIGHT_SETS[weights] if isinstance(weights, str) else weights
    left = _entries(rows, units, idx)
    right = _entries([invert(r) for r in rows], units, idx)
    _base(left, w)
    _base(right, w)
    s_left = normalise({k: e["base"] for k, e in left.items()}, cfg)
    s_right = normalise({k: e["base"] for k, e in right.items()}, cfg)
    for e in left.values():
        e["strength"] = s_left[e["unit"]["id"]]
    for e in right.values():
        e["strength"] = s_right[e["unit"]["id"]]
    _advantage(left, w, s_right, cfg)
    _advantage(right, w, s_left, cfg)
    return {"left": _recommend(left, right, s_right, w, cfg) | {"strength": s_right, "enemy": right},
            "right": _recommend(right, left, s_left, w, cfg) | {"strength": s_left, "enemy": left}}


def summary(plan):
    ident = lambda e: e["unit"]["id"] if e else None  # noqa: E731
    return {"main": ident(plan["main"]), "support": ident(plan["support"]["entry"]) if plan["support"] else None,
            "additions": [[a["entry"]["unit"]["id"], a["covers"]] for a in plan["additions"]],
            "unanswered": plan["unanswered"]}
