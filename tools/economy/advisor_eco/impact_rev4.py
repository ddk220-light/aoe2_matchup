"""Revision 4 impact: run advisor_model_rev4 on all 1,540 civ pairs (3,080 plans) for the three
weight sets, compare with the live advisor (advisor_model "current") and Revision 3
(advisor_model "eco_lite_main" with the Revision 3 eco-win cells), run the sensitivity
checks and write the per-plan output.

Writes $ADVISOR_ECO_OUT/impact_rev4.json, $ADVISOR_ECO_OUT/changes_rev4.md and
docs/army-economics/advisor-plans-rev4.json(.gz).
Usage: ADVISOR_ECO_OUT=... python tools/economy/advisor_eco/impact_rev4.py
"""
from __future__ import annotations

import collections
import gzip
import itertools
import json

import advisor_model as old
import advisor_model_rev4 as m4
from classify import ECO, HP_LIMIT, classify, load_bundle, motion
from common import OUT, REPO, advisor_units, civ_documents, connect, read_cells
from impact_rev2 import eco_win_set

SLOW_SIEGE = {"War Chariot", "Elite Ballista Elephant", "Mounted Trebuchet", "Elite Organ Gun", "Elite Hussite Wagon"}
SCORPIONS = set(m4.CONFIG["excluded_main"])
FOCUS = [("Goths", "Tupi"), ("Romans", "Berbers")]


def pct(x):
    return None if x is None else round(100 * x)


def main():
    db = connect()
    units = advisor_units(db)
    documents = civ_documents(db, units)
    variants = load_bundle()
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    cells_list = list(read_cells())
    idx = m4.cell_index(cells_list, mo, classify)
    semi = eco_win_set(cells_list, mo, HP_LIMIT, ECO)
    pairs = list(itertools.combinations(sorted(documents), 2))
    name = lambda uid: units[uid]["name"] if uid is not None else None  # noqa: E731

    # ---------------------------------------------------------------- old plans
    old_plans = {}
    for left, right in pairs:
        rows = documents[left][right]
        live, rev3 = old.build(rows, units), old.build(rows, units, semi, "eco_lite_main")
        for side, civ, enemy in (("left", left, right), ("right", right, left)):
            old_plans[(civ, enemy)] = {"live": old.summary(live[side]), "rev3": old.summary(rev3[side])}

    def run(weights="default", cfg=None, keep=False):
        plans = {}
        for left, right in pairs:
            res = m4.build(documents[left][right], units, idx, weights, cfg)
            for side, civ, enemy in (("left", left, right), ("right", right, left)):
                p = res[side]
                plans[(civ, enemy)] = p if keep else m4.summary(p)
        return plans

    def stats(plans, keep):
        s = collections.Counter()
        dist = collections.Counter()
        for key, p in plans.items():
            sm = m4.summary(p) if keep else p
            o = old_plans[key]
            for ref in ("live", "rev3"):
                r = o[ref]
                s[f"main changed vs {ref}"] += sm["main"] != r["main"]
                s[f"support changed vs {ref} sidekick"] += sm["support"] != r["sidekick"]
                s[f"additions changed vs {ref}"] += sorted(a[0] for a in sm["additions"]) != sorted(a[0] for a in r["additions"])
                s[f"any of main/support/additions changed vs {ref}"] += (
                    sm["main"] != r["main"] or sm["support"] != r["sidekick"]
                    or sorted(a[0] for a in sm["additions"]) != sorted(a[0] for a in r["additions"]))
            s["additions total"] += len(sm["additions"])
            s["unanswered total"] += len(sm["unanswered"])
            s["plans with no support"] += sm["support"] is None
            if sm["support"] is not None:
                s["support is Scorpion line" if name(sm["support"]) in SCORPIONS else "support is trash"] += 1
            dist[name(sm["main"])] += 1
            if name(sm["main"]) in SLOW_SIEGE:
                s[f"main is slow siege: {name(sm['main'])}"] += 1
            if keep:
                s["main has no loss"] += not any(i["cat"] in m4.LOSS_CATS for i in p["main"]["vs"].values())
                s["main has no real loss (eco wins allowed)"] += not any(
                    i["cat"] in m4.LOSS_CATS and i["cat"] != "eco_win" for i in p["main"]["vs"].values())
                s["top eligible unit is trash (gold preference applied)"] += p["main"] is not p["top_eligible"]
                s["top overall unit is a Scorpion (exclusion applied)"] += p["top_overall"]["unit"]["name"] in SCORPIONS
                s["support targets total"] += len(p["targets"])
                s["targets that are losses"] += sum(1 for t in p["targets"] if t[1] == "loss")
                s["targets that are struggles"] += sum(1 for t in p["targets"] if t[1] == "struggle")
                s["plans with no targets"] += not p["targets"]
                s["struggle targets that are power wins with main HP >= 75%"] += sum(
                    1 for t, k in p["targets"] if k == "struggle" and p["main"]["vs"][t]["cat"] == "power_win"
                    and (p["main"]["vs"][t]["hp_own"] or 0) >= 0.75)
                s["struggle targets that are power wins"] += sum(
                    1 for t, k in p["targets"] if k == "struggle" and p["main"]["vs"][t]["cat"] == "power_win")
                s["struggle targets that are close"] += sum(1 for t, k in p["targets"] if p["main"]["vs"][t]["cat"] == "close")
                if p["support"]:
                    s["support helps resting on a pending (inferred) cell"] += sum(
                        1 for h in p["support"]["helps"] if p["support"]["entry"]["vs"][h["opp"]].get("pending")
                        or p["main"]["vs"][h["opp"]].get("pending"))
                    s["support helps total"] += len(p["support"]["helps"])
                    for h in p["support"]["helps"]:
                        s[f"help reason {h['why']}"] += 1
                        s[f"help on {h['kind']}"] += 1
        s["additions total live"] = sum(len(o["live"]["additions"]) for o in old_plans.values())
        s["additions total rev3"] = sum(len(o["rev3"]["additions"]) for o in old_plans.values())
        s["unanswered total live"] = sum(len(o["live"]["unanswered"]) for o in old_plans.values())
        return dict(sorted(s.items())), dist

    out = {"plans": 2 * len(pairs), "weights": m4.WEIGHT_SETS, "config": m4.CONFIG}
    dist_live = collections.Counter(name(o["live"]["main"]) for o in old_plans.values())
    dist_rev3 = collections.Counter(name(o["rev3"]["main"]) for o in old_plans.values())
    out["scorpionMains"] = {"live": sum(dist_live[n] for n in SCORPIONS), "rev3": sum(dist_rev3[n] for n in SCORPIONS)}
    out["slowSiegeMains"] = {"live": {n: dist_live[n] for n in SLOW_SIEGE if dist_live[n]},
                             "rev3": {n: dist_rev3[n] for n in SLOW_SIEGE if dist_rev3[n]}}
    out["sidekickScorpionLive"] = sum(1 for o in old_plans.values() if name(o["live"]["sidekick"]) in SCORPIONS)
    out["noSidekickLive"] = sum(1 for o in old_plans.values() if o["live"]["sidekick"] is None)
    out["mainDistribution"] = {"live": dist_live.most_common(20), "rev3": dist_rev3.most_common(20)}
    full = {}
    out["sets"] = {}
    for ws in m4.WEIGHT_SETS:
        plans = run(ws, keep=True)
        full[ws] = plans
        st, dist = stats(plans, True)
        out["sets"][ws] = {"stats": st, "mainDistribution": dist.most_common(20)}
        print(ws, json.dumps(st, indent=0))
    # pairwise between weight sets
    d = full["default"]
    for ws in ("eco", "combat"):
        out["sets"][ws]["vsDefault"] = {
            "main changed": sum(1 for k in d if d[k]["main"] is not full[ws][k]["main"] and d[k]["main"]["unit"]["id"] != full[ws][k]["main"]["unit"]["id"]),
            "support changed": sum(1 for k in d if m4.summary(d[k])["support"] != m4.summary(full[ws][k])["support"])}

    # ---------------------------------------------------------------- sensitivity (default weights)
    base_sum = {k: m4.summary(p) for k, p in d.items()}
    variants_cfg = {
        "strength rank [0.5,1.5]": {"strength": "rank"},
        "strength min-max [0.75,1.25]": {"lo": 0.75, "hi": 1.25},
        "strength min-max [0.25,1.75]": {"lo": 0.25, "hi": 1.75},
        "no strength (advantage = base)": {"strength": "none"},
        "no gold-main preference": {"gold_main": False},
        "struggle HP < 33%": {"struggle_hp": 0.33},
        "struggle HP < 66%": {"struggle_hp": 0.66},
        "power win is not a struggle": {"struggle_power": False},
        "close is not a struggle": {"struggle_close": False},
        "help HP margin 25 pts": {"help_hp_margin": 0.25},
        "help eco 33%": {"help_eco": 0.33},
        "no same-result help (tie bonus 0)": {"help_tie_bonus": 0.0},
        "also exclude War Chariot, Ballista Elephant, Mounted Trebuchet from main":
            {"excluded_main": ("Scorpion", "Heavy Scorpion", "War Chariot", "Elite Ballista Elephant", "Mounted Trebuchet")},
    }
    out["sensitivity"] = {}
    for wname, wpatch in (("power win weight 0.8", {"power_win": 0.8}), ("power win weight 1.0 (= plain win)", {"power_win": 1.0}),
                          ("eco win weight 0 (= close)", {"eco_win": 0.0}), ("losses x2", {k: 2 * v for k, v in m4.WEIGHT_SETS["default"].items() if v < 0})):
        variants_cfg[wname] = ({**m4.WEIGHT_SETS["default"], **wpatch}, {})
    for label, cfg in variants_cfg.items():
        plans = run(*cfg) if isinstance(cfg, tuple) else run("default", cfg)
        st = collections.Counter()
        for k, sm in plans.items():
            b = base_sum[k]
            st["main changed"] += sm["main"] != b["main"]
            st["support changed"] += sm["support"] != b["support"]
            st["additions changed"] += sorted(a[0] for a in sm["additions"]) != sorted(a[0] for a in b["additions"])
            st["no support"] += sm["support"] is None
            st["main changed vs live"] += sm["main"] != old_plans[k]["live"]["main"]
            st["mains that are trash"] += not m4.is_gold(units[sm["main"]])
            if name(sm["main"]) in SLOW_SIEGE:
                st["slow-siege mains"] += 1
        out["sensitivity"][label] = dict(st)
        print(label, dict(st))

    # ---------------------------------------------------------------- per-plan output
    def info_text(i, hp=True):
        t = m4.LABEL[i["cat"]] + (" [pending re-sim]" if i.get("pending") else "")
        if hp and i["cat"] in m4.WIN_CATS and i.get("hp_own") is not None:
            t += f", keeps {pct(i['hp_own'])}% HP"
        if hp and i["cat"] in m4.LOSS_CATS and i.get("hp_winner") is not None:
            t += f", winner keeps {pct(i['hp_winner'])}% HP"
        if i.get("vm_own") is not None:
            t += f", army {round(i['vm_own'])} vs {round(i['vm_opp'])} VM"
        return t

    def help_text(p, h):
        s, mn = p["support"]["entry"], p["main"]
        si, mi = s["vs"][h["opp"]], mn["vs"][h["opp"]]
        verb = {"better": "does better", "more_hp": "wins with more HP", "cheaper": "wins with a cheaper army"}[h["why"]]
        return (f"{name(h['opp'])} (strength {p['strength'][h['opp']]:.2f}, main {h['kind']}): {s['unit']['name']} {verb}"
                f" — {s['unit']['name']}: {info_text(si)}; {mn['unit']['name']}: {info_text(mi)}")

    def entry_brief(e, p):
        cats = collections.Counter(i["cat"] for i in e["vs"].values())
        return {"unit": e["unit"]["name"], "id": e["unit"]["id"], "gold": m4.is_gold(e["unit"]),
                "base": round(e["base"], 3), "advantage": round(e["adv"], 3),
                "categories": {m4.LABEL[c]: cats[c] for c in m4.CATS if cats[c]},
                "pending": sum(1 for i in e["vs"].values() if i.get("pending"))}

    def old_brief(o):
        return {"main": name(o["main"]), "sidekick": name(o["sidekick"]),
                "additions": [[name(a), [name(x) for x in cov]] for a, cov in o["additions"]],
                "unanswered": [name(x) for x in o["unanswered"]]}

    records = []
    for (civ, enemy), p in sorted(d.items()):
        o = old_plans[(civ, enemy)]
        byid = {e["unit"]["id"]: e for e in p["ranked"]}
        rec = {"civ": civ, "enemy": enemy,
               "live": old_brief(o["live"]) | {"mainScoresRev4": entry_brief(byid[o["live"]["main"]], p) if o["live"]["main"] in byid else None},
               "rev3": old_brief(o["rev3"]),
               "rev4": {"main": entry_brief(p["main"], p),
                        "mainVs": {name(opp): info_text(i) for opp, i in sorted(p["main"]["vs"].items(), key=lambda t: (-p["strength"][t[0]], t[0]))},
                        "enemyStrength": {name(k): round(v, 3) for k, v in sorted(p["strength"].items(), key=lambda t: (-t[1], t[0]))},
                        "targets": [[name(t), k] for t, k in p["targets"]],
                        "support": None if not p["support"] else {
                            "unit": p["support"]["entry"]["unit"]["name"],
                            "kind": "scorpion" if p["support"]["entry"]["unit"]["name"] in SCORPIONS else "trash",
                            "score": round(p["support"]["score"], 3),
                            "helps": [help_text(p, h) for h in p["support"]["helps"]]},
                        "additions": [[a["entry"]["unit"]["name"], [name(x) for x in a["covers"]]] for a in p["additions"]],
                        "unanswered": [name(x) for x in p["unanswered"]],
                        "alternatives": [entry_brief(e, p) for e in p["alternatives"]],
                        "ranking": [[e["unit"]["name"], round(e["adv"], 2), round(e["base"], 2)] for e in p["ranked"]]},
               "eco": {"main": full["eco"][(civ, enemy)]["main"]["unit"]["name"],
                       "support": (full["eco"][(civ, enemy)]["support"] or {}).get("entry", {}).get("unit", {}).get("name")},
               "combat": {"main": full["combat"][(civ, enemy)]["main"]["unit"]["name"],
                          "support": (full["combat"][(civ, enemy)]["support"] or {}).get("entry", {}).get("unit", {}).get("name")}}
        records.append(rec)
    payload = json.dumps({"description": "Revision 4 advisor plans (scratch model tools/economy/advisor_eco/advisor_model_rev4.py, "
                                         "default weights) with live and Revision 3 plans and the eco/combat weight-set mains.",
                          "weights": m4.WEIGHT_SETS, "config": m4.CONFIG, "plans": records}, indent=0, ensure_ascii=False)
    dst = REPO / "docs" / "army-economics" / "advisor-plans-rev4.json"
    if len(payload) > 2_000_000:
        with gzip.open(str(dst) + ".gz", "wt", compresslevel=9) as fh:
            fh.write(payload)
        dst = str(dst) + ".gz"
    else:
        dst.write_text(payload)
    out["perPlanFile"] = str(dst)
    print("wrote", dst, len(payload))

    # ---------------------------------------------------------------- change list
    changed = []
    for rec in records:
        if rec["live"]["main"] == rec["rev4"]["main"]["unit"]:
            continue
        old_adv = rec["live"]["mainScoresRev4"]["advantage"]
        changed.append((rec["rev4"]["main"]["advantage"] - old_adv, rec))
    reasons = collections.Counter()
    for _, r in changed:
        lm = r["live"]["mainScoresRev4"]["categories"]
        wins = sum(lm.get(m4.LABEL[c], 0) for c in m4.WIN_CATS)
        losses = sum(lm.get(m4.LABEL[c], 0) for c in m4.LOSS_CATS)
        nl = sum(r["rev4"]["main"]["categories"].get(m4.LABEL[c], 0) for c in m4.LOSS_CATS)
        if r["live"]["main"] in SCORPIONS:
            reasons["live main is a Scorpion (excluded)"] += 1
        elif wins and lm.get("Power win", 0) >= wins / 2:
            reasons["live main wins mostly as Power wins (dearer army, usually Castles)"] += 1
        elif nl < losses:
            reasons["new main has fewer losses"] += 1
        else:
            reasons["other (category mix / opponent strength)"] += 1
    out["mainChangeReasons"] = dict(reasons.most_common())
    print(out["mainChangeReasons"])
    changed.sort(key=lambda t: (-t[0], t[1]["civ"], t[1]["enemy"]))
    out["mainChangePairs"] = collections.Counter(
        f"{r['live']['main']} -> {r['rev4']['main']['unit']}" for _, r in changed).most_common(30)
    picks, seen_pairs = [], set()
    for _, r in changed:  # biggest advantage gain, at most one plan per (old main -> new main) pair
        key = (r["live"]["main"], r["rev4"]["main"]["unit"])
        if key in seen_pairs or (r["civ"], r["enemy"]) in FOCUS or r["live"]["main"] in SCORPIONS:
            continue
        seen_pairs.add(key)
        picks.append(r)
        if len(picks) == 21:
            break
    scorp = sorted((r for _, r in changed if r["live"]["main"] in SCORPIONS),
                   key=lambda r: (-r["live"]["mainScoresRev4"]["advantage"], r["civ"], r["enemy"]))
    picks += scorp[:2]
    for civ, enemy in FOCUS:
        r = next(x for x in records if x["civ"] == civ and x["enemy"] == enemy)
        if r not in picks:
            picks.append(r)
    lines = []
    for r in picks:
        lv, n4 = r["live"], r["rev4"]
        lm = lv["mainScoresRev4"]
        sup = n4["support"]
        lines.append(f"### {r['civ']} vs {r['enemy']}\n")
        lines.append(f"- Main: {lv['main']} (base {lm['base']}, adv {lm['advantage']}) → **{n4['main']['unit']}** "
                     f"(base {n4['main']['base']}, adv {n4['main']['advantage']}); Rev 3: {r['rev3']['main']}; "
                     f"eco set: {r['eco']['main']}; combat set: {r['combat']['main']}")
        lines.append(f"- Old main {lv['main']}: {lm['categories']}; new main: {n4['main']['categories']}")
        lines.append(f"- Support: {lv['sidekick']} → **{sup['unit'] if sup else 'none'}**"
                     + (f" ({sup['kind']}, score {sup['score']})" if sup else ""))
        for h in (sup["helps"] if sup else [])[:4]:
            lines.append(f"  - {h}")
        lines.append(f"- Additions: {[a[0] for a in lv['additions']]} → {[a[0] for a in n4['additions']]}; "
                     f"unanswered {n4['unanswered']}\n")
    (OUT / "changes_rev4.md").write_text("\n".join(lines))
    table = ["| Civ vs enemy | Main live → Rev 4 (adv) | Rev 3 | eco / combat set | Support live → Rev 4 | Support helps against |",
             "|---|---|---|---|---|---|"]
    for r in picks:
        lv, n4 = r["live"], r["rev4"]
        sup = n4["support"]
        helped = "; ".join(h.split(" (strength")[0] + " (" + h.split("main ")[1].split(")")[0] + ")" for h in (sup["helps"] if sup else []))
        table.append(f"| {r['civ']} vs {r['enemy']} | {lv['main']} ({lv['mainScoresRev4']['advantage']:.1f}) → **{n4['main']['unit']}** "
                     f"({n4['main']['advantage']:.1f}) | {r['rev3']['main']} | {r['eco']['main']} / {r['combat']['main']} | "
                     f"{lv['sidekick']} → {sup['unit'] if sup else '—'} | {helped or '—'} |")
    (OUT / "changes_rev4_table.md").write_text("\n".join(table) + "\n")
    out["noSupportPlans"] = [[r["civ"], r["enemy"], r["rev4"]["main"]["unit"], r["rev4"]["targets"]]
                             for r in records if r["rev4"]["support"] is None]
    out["changeListPlans"] = [[r["civ"], r["enemy"]] for r in picks]
    (OUT / "impact_rev4.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("scorpionMains", "slowSiegeMains", "sidekickScorpionLive", "noSidekickLive")}, indent=1))


if __name__ == "__main__":
    main()
