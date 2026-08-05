"""golden_roster.py — the Phase-1 standard-unit roster for the simulation-calibration
golden set, and the full round-robin matchup list generated from it.

CIV CHOICE RULE: each unit is fielded by a civ that (a) actually has the top unit and
every upgrade tech that touches its stats, and (b) has no civ bonus altering it — so a
sim/game disagreement can never be blamed on a civ bonus.

Availability truth is aoe2techtree (SiegeEngineers), NOT the reference DB: the ref DB
over-reports (it lists Siege Onager for all 53 civs and gives Chinese a Paladin they do
not have). Verified 2026-07-29 against tech-tree data + the ref DB's final stat vectors.

Deliberate exceptions, both user calls:
  * Elite Battle Elephant — NO generic civ exists. Bengalis get faster attack (Paiks,
    reload 1.67 vs 2.00), Khmer +3 attack and speed, Malay/Vietnamese miss blacksmith
    techs. Burmese is generic-plus-Howdah (+2/+2 armour), a flat armour delta the ref DB
    models correctly, which is the least behaviourally distorting option.
  * Elite Steppe Lancer — Cumans lack Husbandry but carry a cavalry speed bonus, netting
    1.68 speed vs the fully-upgraded generic 1.60 (Jurchens/Tatars are the only fully
    upgraded civs). Chosen over Jurchens for DLC availability.

  python golden_roster.py            # print the roster + matchup counts
  python golden_roster.py --json OUT # write the matchup list for record_golden.py --list
"""
import itertools
import json
import sys
from pathlib import Path

# (civ, ref-DB slug, display label)
ROSTER = [
    ("Chinese",  "champion",          "Champion"),
    ("Chinese",  "halberdier",        "Halberdier"),
    ("Chinese",  "arbalester",        "Arbalester"),
    ("Chinese",  "imp_elite_skirm",   "Elite Skirmisher"),      # slug name is legacy;
    ("Chinese",  "elite_fire_lancer", "Elite Fire Lancer"),     # maps to ELITE_SKIRMISHER
    ("Saracens", "heavy_cav_archer",  "Heavy Cav Archer"),      # Chinese lack Parthian Tactics
    ("Japanese", "hand_cannoneer",    "Hand Cannoneer"),        # Persians lack Bracer
    ("Japanese", "heavy_scorpion",    "Heavy Scorpion"),
    ("Aztecs",   "siege_onager",      "Siege Onager"),          # Japanese have no Siege Onager
    ("Spanish",  "paladin",           "Paladin"),               # Chinese have no Paladin
    ("Persians", "hussar",            "Hussar"),
    ("Persians", "heavy_camel",       "Heavy Camel"),
    ("Cumans",   "elite_steppe",      "Elite Steppe Lancer"),
    ("Burmese",  "elite_elephant",    "Elite Battle Elephant"),
]

MIRRORS = False          # user call 2026-07-29: everything-vs-everything, no mirrors
UNIT_CAP = 21            # per side; equal resources, budget 3000, gold weight 1.5


def matchups():
    pairs = itertools.combinations(ROSTER, 2)
    out = [{"civ1": a[0], "slug1": a[1], "label1": a[2],
            "civ2": b[0], "slug2": b[1], "label2": b[2]} for a, b in pairs]
    if MIRRORS:
        out += [{"civ1": u[0], "slug1": u[1], "label1": u[2],
                 "civ2": u[0], "slug2": u[1], "label2": u[2]} for u in ROSTER]
    return out


def main(argv):
    ms = matchups()
    if "--json" in argv:
        dest = Path(argv[argv.index("--json") + 1])
        dest.write_text(json.dumps(ms, indent=2))
        print(f"{len(ms)} matchups -> {dest}")
        return 0
    print(f"{len(ROSTER)} units, {len(ms)} matchups (mirrors={MIRRORS}), cap={UNIT_CAP}")
    for civ, slug, label in ROSTER:
        print(f"  {label:24s} {civ}/{slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
