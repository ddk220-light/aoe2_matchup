"""Revision 2 (owner decisions 2026-11-12): classify every advisor cell from both sides.

Reads ``$ADVISOR_ECO_OUT/cells.csv.gz`` (``extract_cells.py``: seed HP + 60-s army
investment per simulated cell), the advisor DB (identity / inferred / close cells)
and the frozen 2026 mechanics bundle (``matchup-runs`` branch) for the kite rule.

Categories (winner side <-> loser side), checked in this order:
  kite        Clear win (kite)       <-> Kited loss          ranged winner, melee loser, ranged
                                                             effective kite speed > melee movement speed
  dominance   Complete dominance     <-> Outclassed loss     winner's army >= ECO cheaper
  power/eco   Power win              <-> Eco win             loser's army >= ECO cheaper, winner HP < HP_LIMIT
  power/cheap Power win              <-> Cheap loss          loser's army >= ECO cheaper, winner HP >= HP_LIMIT
  power/nohp  Power win              <-> Cheap loss (HP unknown)  no seed HP record in git
  plain       Plain win              <-> Plain loss          eco within +-ECO
  close       Close                  <-> Close               close_uncertain / equivalent, identity
  pending     Pending re-simulation  <-> same                inferred (never simulated)
"Cheaper by x" means ``1 - cheaper_vm / dearer_vm >= x`` (headline 60-s army investment
including production buildings and common research, owner decision 1).

Kite speed: ``speed_tiles_per_second * (1 - attack_delay_seconds / reload_seconds)``
(= ``simulation_real.BattleUnit.effective_kite_speed``, base reload = 1/attack_speed =
reload_seconds). Ranged = behavior_class mobile_ranged / siege_ranged (the campaign's
``isRangedClass``; identical to attack_range_tiles > 1 for all 555 variants).

Badge "cheaper to fully upgrade": own full research package <= BADGE_RATIO x the opponent's.

Writes $ADVISOR_ECO_OUT/classification.csv.gz (decided cells), classification_summary.json,
classification_report.md, eco_wins.json (loser/winner advisor ids, for impact_rev2.py).
Usage: python tools/economy/advisor_eco/classify.py [--csv-out PATH] [--hp 0.5] [--eco 0.25]
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import subprocess

from common import OUT, REPO, advisor_units, connect, evidence_decoder, read_cells

BUNDLE_REF = "matchup-runs"
BUNDLE_PATH = "aoe2x/matchups/bundles/campaign-2026-185872-188329.json.gz"
BUNDLE_HASH = "201cec0cdfac7ad218748051451350070e6a353f833d52d97094f74ddb23b813"
HP_LIMIT = 0.50
ECO = 0.25
BADGE_RATIO = 0.50
RANGED = {"mobile_ranged", "siege_ranged"}

WIN = {"kite": "Clear win (kite)", "dominance": "Complete dominance", "power": "Power win", "plain": "Plain win"}
LOSS = {"kite": "Kited loss", "dominance": "Outclassed loss", "eco": "Eco win", "cheap": "Cheap loss",
        "nohp": "Cheap loss (HP unknown)", "plain": "Plain loss"}


def load_bundle(ref=BUNDLE_REF):
    raw = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{BUNDLE_PATH}"], capture_output=True, check=True).stdout
    bundle = json.loads(gzip.decompress(raw))
    if bundle["bundleHash"] != BUNDLE_HASH:
        raise SystemExit(f"bundle hash {bundle['bundleHash']} != {BUNDLE_HASH}")
    return {v["key"]: v for v in bundle["variants"]}


def motion(variant):
    m = variant["mechanics"]
    speed = float(m["speed_tiles_per_second"])
    reload_s = float(m["reload_seconds"] or 0) or 2.0
    delay = float(m["attack_delay_seconds"] or 0)
    ranged = m["behavior_class"] in RANGED
    return {"ranged": ranged, "speed": speed, "delay": delay, "reload": reload_s,
            "kite": speed * max(0.0, 1 - delay / reload_s), "range": m["attack_range_tiles"],
            "behavior": m["behavior_class"]}


def classify(c, mo, hp_limit=HP_LIMIT, eco=ECO):
    """Return (winner_key, loser_key, winner_side 'a'/'b') for a decided cell."""
    w = "a" if c["outcome"] == "a_win" else "b"
    l = "b" if w == "a" else "a"
    mw, ml = mo[c[w]], mo[c[l]]
    if mw["ranged"] and not ml["ranged"] and mw["kite"] > ml["speed"]:
        return "kite", "kite", w
    vw, vl = c["vm_" + w], c["vm_" + l]
    if vw <= (1 - eco) * vl:
        return "dominance", "dominance", w
    if vl <= (1 - eco) * vw:
        if c["hp_avg"] is None:
            return "power", "nohp", w
        return "power", ("eco" if c["hp_avg"] < hp_limit else "cheap"), w
    return "plain", "plain", w


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hp", type=float, default=HP_LIMIT)
    parser.add_argument("--eco", type=float, default=ECO)
    parser.add_argument("--csv-out", default=str(OUT / "classification.csv.gz"))
    args = parser.parse_args()
    db = connect()
    units = advisor_units(db)
    variants = load_bundle()
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    assert all(variants[u["key"]]["profileHash"] == u["profileHash"] for u in units.values())
    decode = evidence_decoder(db)
    family = {}
    cells = [c for c in read_cells()]
    for eid in sorted({c["evidence_id"] for c in cells}):
        family[eid] = decode(db.execute("SELECT data FROM evidence WHERE id=?", (eid,)).fetchone()[0])["context"]
    checks = collections.Counter()
    for c in cells:  # campaign family (context order) must agree with the bundle classes
        ctx = family[c["evidence_id"]]
        ia = ctx["profiles"].index(units[c["a"]]["profileHash"])
        ra, rb = mo[c["a"]]["ranged"], mo[c["b"]]["ranged"]
        r0, r1 = (ra, rb) if ia == 0 else (rb, ra)
        expect = {(False, False): "melee_vs_melee", (True, True): "ranged_vs_ranged",
                  (True, False): "ranged_vs_melee", (False, True): "melee_vs_ranged"}[(r0, r1)]
        checks["family agrees with bundle class" if expect == ctx["family"] else "family DISAGREES"] += 1
        c["family"] = ctx["family"]
        c["policy_kiting_disabled"] = "disableKiting" in ctx["policy"]
    checks["contexts with disableKiting"] = sum("disableKiting" in f["policy"] for f in family.values())
    checks["contexts"] = len(family)

    full = {}
    for c in cells:
        for x in "ab":
            if c["full_vm_" + x] is not None:
                full[c[x]] = c["full_vm_" + x]

    def badge(own, opp):
        return own in full and opp in full and full[own] <= BADGE_RATIO * full[opp]

    all_cells = db.execute("SELECT a, b, outcome, evidence_type FROM cells").fetchall()
    summary = {"thresholds": {"hpBelow": args.hp, "ecoCheaperBy": args.eco, "badgeRatio": BADGE_RATIO},
               "bundle": {"ref": BUNDLE_REF, "path": BUNDLE_PATH, "hash": BUNDLE_HASH,
                          "fields": ["mechanics.behavior_class", "mechanics.speed_tiles_per_second",
                                     "mechanics.attack_delay_seconds", "mechanics.reload_seconds",
                                     "mechanics.attack_range_tiles", "group"]},
               "checks": dict(checks)}
    etype = collections.Counter(r[3] for r in all_cells)
    observed_close = sum(1 for c in cells if c["outcome"] not in ("a_win", "b_win"))
    decided = [c for c in cells if c["outcome"] in ("a_win", "b_win") and c["vm_a"] is not None and c["vm_b"] is not None]
    summary["coverage"] = {"all": len(all_cells), "identity": etype["identity"], "inferred_pending": etype["inferred"],
                           "observed": len(cells), "observed_close": observed_close, "decided": len(decided),
                           "decided_no_seed_hp": sum(1 for c in decided if c["hp_avg"] is None),
                           "decided_eco_unavailable": sum(1 for c in cells if c["outcome"] in ("a_win", "b_win")) - len(decided)}

    # Main classification + sensitivity grid.
    pair_key = lambda c: (units[c["a"]]["name"], units[c["b"]]["name"]) if units[c["a"]]["name"] <= units[c["b"]]["name"] \
        else (units[c["b"]]["name"], units[c["a"]]["name"])  # noqa: E731
    combos = collections.Counter(); ctx_sets = collections.defaultdict(set); name_sets = collections.defaultdict(set)
    grid = {}
    for hp in (0.33, 0.40, 0.50):
        for eco in (0.25, 0.33):
            k = collections.Counter()
            for c in decided:
                wk, lk, _ = classify(c, mo, hp, eco)
                k[f"{WIN[wk]} / {LOSS[lk]}"] += 1
            grid[f"hp<{hp:.2f} eco>={eco:.2f}"] = dict(k)
    summary["sensitivity"] = grid

    # Kite-rule impact: what the cell would be without the kite rule.
    nokite = lambda c: classify(c, {**mo, c["a"]: {**mo[c["a"]], "ranged": False}, c["b"]: {**mo[c["b"]], "ranged": False}}, args.hp, args.eco)  # noqa: E731
    kite_stats = collections.Counter(); kite_pairs = collections.Counter(); kite_flip_pairs = collections.Counter()
    kite_melee = collections.Counter(); ranged_loses_but_can_kite = collections.Counter()
    eco_wins = []
    rows_out = []
    fields = ["civ_a", "unit_a", "civ_b", "unit_b", "count_a", "count_b", "winner", "winner_unit", "family",
              "hp_avg_pct", "hp_min_pct", "hp_max_pct", "seeds", "vm_a", "vm_b", "army_vm_a", "army_vm_b",
              "loser_to_winner_vm_ratio", "class_a", "class_b", "speed_a", "speed_b", "kite_speed_a", "kite_speed_b",
              "category_a", "category_b", "category_without_kite_rule_a", "category_without_kite_rule_b",
              "full_upgrade_vm_a", "full_upgrade_vm_b", "badge_cheaper_upgrade_a", "badge_cheaper_upgrade_b",
              "a_id", "b_id", "evidence_id"]
    for c in decided:
        wk, lk, w = classify(c, mo, args.hp, args.eco)
        l = "b" if w == "a" else "a"
        cat = {w: WIN[wk], l: LOSS[lk]}
        combos[(wk, lk)] += 1
        ctx_sets[(wk, lk)].add(c["evidence_id"]); name_sets[(wk, lk)].add(pair_key(c))
        nwk, nlk, _ = nokite(c)
        ncat = {w: WIN[nwk], l: LOSS[nlk]}
        mw, ml = mo[c[w]], mo[c[l]]
        if mw["ranged"] and not ml["ranged"]:
            kite_stats["ranged beats melee"] += 1
            if wk == "kite":
                kite_stats["kite rule applies"] += 1
                kite_melee[units[c[l]]["group"]] += 1
                kite_pairs[(units[c[w]]["name"], units[c[l]]["name"])] += 1
                kite_stats[f"without rule would be: {WIN[nwk]} / {LOSS[nlk]}"] += 1
                if (nwk, nlk) != ("plain", "plain"):
                    kite_stats["category changed vs no-kite rule (not plain)"] += 1
                if nlk == "eco":
                    kite_stats["eco-win label removed by kite rule"] += 1
                    kite_flip_pairs[(units[c[w]]["name"], units[c[l]]["name"])] += 1
            else:
                kite_stats["ranged beats melee, too slow to kite"] += 1
        if ml["ranged"] and not mw["ranged"]:
            kite_stats["melee beats ranged"] += 1
            if ml["kite"] > mw["speed"]:
                kite_stats["melee beats ranged that could out-kite it (odd)"] += 1
                kite_stats[f"  ... melee winner group {units[c[w]]['group']}"] += 1
                ranged_loses_but_can_kite[(units[c[l]]["name"], units[c[w]]["name"])] += 1
        if lk == "eco":
            eco_wins.append([c[l], c[w]])
        ratio = c["vm_" + l] / c["vm_" + w]
        rows_out.append({
            "civ_a": c["civ_a"], "unit_a": c["name_a"], "civ_b": c["civ_b"], "unit_b": c["name_b"],
            "count_a": c["count_a"], "count_b": c["count_b"], "winner": w, "winner_unit": c["name_" + w],
            "family": c["family"],
            "hp_avg_pct": "" if c["hp_avg"] is None else f"{100 * c['hp_avg']:.1f}",
            "hp_min_pct": "" if c["hp_min"] is None else f"{100 * c['hp_min']:.1f}",
            "hp_max_pct": "" if c["hp_max"] is None else f"{100 * c['hp_max']:.1f}",
            "seeds": c["seeds"], "vm_a": f"{c['vm_a']:.1f}", "vm_b": f"{c['vm_b']:.1f}",
            "army_vm_a": f"{c['army_vm_a']:.1f}", "army_vm_b": f"{c['army_vm_b']:.1f}",
            "loser_to_winner_vm_ratio": f"{ratio:.3f}",
            "class_a": ("ranged" if mo[c["a"]]["ranged"] else "melee-" + units[c["a"]]["group"].lower()),
            "class_b": ("ranged" if mo[c["b"]]["ranged"] else "melee-" + units[c["b"]]["group"].lower()),
            "speed_a": f"{mo[c['a']]['speed']:.3f}", "speed_b": f"{mo[c['b']]['speed']:.3f}",
            "kite_speed_a": f"{mo[c['a']]['kite']:.3f}" if mo[c["a"]]["ranged"] else "",
            "kite_speed_b": f"{mo[c['b']]['kite']:.3f}" if mo[c["b"]]["ranged"] else "",
            "category_a": cat["a"], "category_b": cat["b"],
            "category_without_kite_rule_a": ncat["a"], "category_without_kite_rule_b": ncat["b"],
            "full_upgrade_vm_a": f"{full[c['a']]:.1f}" if c["a"] in full else "",
            "full_upgrade_vm_b": f"{full[c['b']]:.1f}" if c["b"] in full else "",
            "badge_cheaper_upgrade_a": int(badge(c["a"], c["b"])), "badge_cheaper_upgrade_b": int(badge(c["b"], c["a"])),
            "a_id": c["a"], "b_id": c["b"], "evidence_id": c["evidence_id"]})
    with gzip.open(args.csv_out, "wt", newline="", compresslevel=9) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows_out)

    for c in cells:  # close cells where a ranged side could out-kite the melee side
        if c["outcome"] in ("a_win", "b_win"):
            continue
        for x, y in (("a", "b"), ("b", "a")):
            if mo[c[x]]["ranged"] and not mo[c[y]]["ranged"] and mo[c[x]]["kite"] > mo[c[y]]["speed"]:
                kite_stats["close cells where the ranged side could out-kite the melee side"] += 1
    summary["categories"] = [{"winner": WIN[wk], "loser": LOSS[lk], "cells": n, "contexts": len(ctx_sets[(wk, lk)]),
                              "unitNamePairs": len(name_sets[(wk, lk)])} for (wk, lk), n in combos.most_common()]
    summary["kite"] = {"stats": dict(kite_stats), "meleeLoserGroup": dict(kite_melee),
                       "topPairs": [[w, l, n] for (w, l), n in kite_pairs.most_common(15)],
                       "ecoWinRemovedPairs": [[w, l, n] for (w, l), n in kite_flip_pairs.most_common(15)],
                       "oddRangedLosesButCanKite": [[r, m, n] for (r, m), n in ranged_loses_but_can_kite.most_common(15)],
                       "oddRangedLosesButCanKiteCells": sum(ranged_loses_but_can_kite.values())}
    # Badge frequency: all non-identity cells, and decided cells.
    nonid = [(a, b) for a, b, o, e in all_cells if e != "identity"]
    summary["badge"] = {
        "unitsWithFullCost": len(full), "unitsWithout": [units[u]["key"] for u in units if u not in full],
        "allNonIdentityCells": len(nonid),
        "cellsWithBadgeEitherSide": sum(1 for a, b in nonid if badge(a, b) or badge(b, a)),
        "decidedCells": len(rows_out),
        "decidedWithBadgeEitherSide": sum(1 for r in rows_out if r["badge_cheaper_upgrade_a"] or r["badge_cheaper_upgrade_b"]),
        "decidedBadgeOnWinner": sum(1 for r in rows_out if r["badge_cheaper_upgrade_" + r["winner"]]),
        "decidedBadgeOnLoser": sum(1 for r in rows_out if r["badge_cheaper_upgrade_" + ("b" if r["winner"] == "a" else "a")]),
    }
    for ratio in (0.4, 0.5, 0.67):
        summary["badge"][f"allCellsRatio<={ratio}"] = sum(
            1 for a, b in nonid if a in full and b in full and (full[a] <= ratio * full[b] or full[b] <= ratio * full[a]))
    (OUT / "eco_wins.json").write_text(json.dumps({"thresholds": summary["thresholds"], "ecoWins": eco_wins}) + "\n")
    (OUT / "classification_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
