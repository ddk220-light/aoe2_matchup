"""Readable examples and per-category breakdowns from classification.csv.gz (classify.py).

Prints Markdown: per category the most frequent unit pairs, the purchase-vs-headline
check for eco wins, and the curated examples listed in EXAMPLES (civ, unit, civ, unit).
Writes $ADVISOR_ECO_OUT/examples_rev2.md.
Usage: python tools/economy/advisor_eco/examples_rev2.py
"""
from __future__ import annotations

import collections
import csv
import gzip

from common import OUT

# (civ, unit, civ, unit) in either order; chosen after browsing the CSV (see the design doc).
EXAMPLES = [
    ("Aztecs", "Champion", "Spanish", "Elite Conquistador"),            # kite: owner's example
    ("Saracens", "Elite Mameluke", "Aztecs", "Champion"),               # kite, odd: range-3 Mameluke
    ("Shu", "War Chariot", "Bengalis", "Champion"),                     # kite, odd: siege-class chariot
    ("Burmese", "Champion", "Mapuche", "Heavy Scorpion"),               # eco win, cheaper on purchase too
    ("Dravidians", "Elite Elephant Archer", "Italians", "Elite Genoese Crossbowman"),  # eco win, Castle-driven
    ("Slavs", "Champion", "Lithuanians", "Elite Leitis"),               # eco win in the new 40-50% band, 1 seed
    ("Bengalis", "Heavy Scorpion", "Armenians", "Halberdier"),          # power win / cheap loss
    ("Armenians", "Elite Composite Bowman", "Danes", "Knight"),         # power win, Castle-driven
    ("Armenians", "Halberdier", "Georgians", "Cavalier"),               # dominance
    ("Armenians", "Champion", "Gurjaras", "Elite Chakram Thrower"),     # dominance, odd: winner keeps 2.5%
    ("Vikings", "Champion", "Spanish", "Elite Conquistador"),           # odd: Champion wins the no-kite sim
    ("Armenians", "Halberdier", "Berbers", "Elite Genitour"),           # odd: kite-capable ranged loses
]


def load():
    with gzip.open(OUT / "classification.csv.gz", "rt", newline="") as handle:
        return list(csv.DictReader(handle))


def side(r, x):
    return {"civ": r["civ_" + x], "unit": r["unit_" + x], "n": int(r["count_" + x]), "vm": float(r["vm_" + x]),
            "army": float(r["army_vm_" + x]), "cat": r["category_" + x], "speed": float(r["speed_" + x]),
            "kite": r["kite_speed_" + x], "cls": r["class_" + x], "badge": r["badge_cheaper_upgrade_" + x] == "1",
            "full": r["full_upgrade_vm_" + x]}


def line(r):
    w = r["winner"]; l = "b" if w == "a" else "a"
    W, L = side(r, w), side(r, l)
    hp = (f"keeps {r['hp_avg_pct']}% HP ({r['seeds']} seed{'s' if r['seeds'] != '1' else ''}"
          + (f", {r['hp_min_pct']}-{r['hp_max_pct']}%" if r['seeds'] != '1' else "") + ")") if r["hp_avg_pct"] else "HP not recorded"
    kite = ""
    if W["kite"] or L["kite"]:
        kite = "; speeds " + ", ".join(f"{s['unit']} {'kite ' + s['kite'] if s['kite'] else 'move ' + format(s['speed'], '.3f')}" for s in (W, L))
    badge = "".join(f"; badge: {s['unit']} cheaper to fully upgrade ({s['full']} vs {o['full']} VM)" for s, o in ((W, L), (L, W)) if s["badge"])
    return (f"{W['civ']} {W['n']} {W['unit']} beat {L['civ']} {L['n']} {L['unit']}, {hp}. "
            f"Villager-minutes {W['vm']:.0f} (winner) vs {L['vm']:.0f} (loser), army purchase only {W['army']:.0f} vs {L['army']:.0f}{kite}{badge}. "
            f"**{W['cat']} / {L['cat']}**")


def main():
    rows = load()
    md = []
    by_cat = collections.defaultdict(list)
    for r in rows:
        w = r["winner"]; l = "b" if w == "a" else "a"
        by_cat[(r["category_" + w], r["category_" + l])].append(r)
    for (cw, cl), rs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        pairs = collections.Counter((r["winner_unit"], r["unit_b" if r["winner"] == "a" else "unit_a"]) for r in rs)
        md.append(f"\n### {cw} / {cl}: {len(rs)} cells\n")
        md.append("Top winner / loser unit pairs: " + "; ".join(f"{w} > {l} ({n})" for (w, l), n in pairs.most_common(8)))
        losers = collections.Counter(r["unit_b" if r["winner"] == "a" else "unit_a"] for r in rs)
        winners = collections.Counter(r["winner_unit"] for r in rs)
        md.append("\nTop winners: " + ", ".join(f"{u} {n}" for u, n in winners.most_common(6)))
        md.append("\nTop losers: " + ", ".join(f"{u} {n}" for u, n in losers.most_common(6)))
        if cl == "Eco win":
            dearer = [r for r in rs if float(r["army_vm_" + ("b" if r["winner"] == "a" else "a")]) >= float(r["army_vm_" + r["winner"]])]
            md.append(f"\nEco wins where the loser's army purchase alone is NOT cheaper (production buildings make the gap): {len(dearer)}")
            band = collections.Counter("<33%" if float(r["hp_avg_pct"]) < 33 else "33-40%" if float(r["hp_avg_pct"]) < 40 else "40-50%" for r in rs)
            md.append(f"\nWinner HP bands: {dict(band)}")
            single = sum(1 for r in rs if r["seeds"] == "1")
            md.append(f"\nSingle-seed eco wins: {single}; with a seed above 50% HP: {sum(1 for r in rs if float(r['hp_max_pct']) >= 50)}")
    md.append("\n## Odd-case counts\n")
    L = lambda r: "b" if r["winner"] == "a" else "a"  # noqa: E731
    hp = lambda r: float(r["hp_avg_pct"]) if r["hp_avg_pct"] else None  # noqa: E731
    dom = [r for r in rows if r["category_" + r["winner"]] == "Complete dominance"]
    for limit in (50, 33, 10):
        md.append(f"- Complete dominance with winner HP < {limit}%: {sum(1 for r in dom if hp(r) is not None and hp(r) < limit)} of {len(dom)}")
    power = [r for r in rows if r["category_" + r["winner"]] == "Power win"]
    md.append(f"- Power wins whose winner's army purchase is cheaper than or equal to the loser's (gap = buildings/research): "
              f"{sum(1 for r in power if float(r['army_vm_' + r['winner']]) <= float(r['army_vm_' + L(r)]))} of {len(power)}")
    eco = [r for r in rows if r["category_" + L(r)] == "Eco win"]
    md.append(f"- Eco wins with mean HP in [49.5, 50): {sum(1 for r in eco if hp(r) >= 49.5)}; with one seed >= 50%: "
              f"{sum(1 for r in eco if float(r['hp_max_pct']) >= 50)}; single seed: {sum(1 for r in eco if r['seeds'] == '1')}")
    md.append(f"- Kite clear wins whose winner keeps >= 50% HP: {sum(1 for r in rows if r['category_' + r['winner']] == 'Clear win (kite)' and hp(r) >= 50)}")
    md.append("\n## Curated examples\n")
    index = {}
    for r in rows:
        index[(r["civ_a"], r["unit_a"], r["civ_b"], r["unit_b"])] = r
        index[(r["civ_b"], r["unit_b"], r["civ_a"], r["unit_a"])] = r
    for i, key in enumerate(EXAMPLES, 1):
        r = index.get(key)
        md.append(f"{i}. " + (line(r) if r else f"{key}: not a decided cell"))
    text = "\n".join(md) + "\n"
    (OUT / "examples_rev2.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
