"""Hand-curated, cited corrections and owner decisions applied by the compiler.

The reviewed source snapshot (army-context-2026-11-10) is never edited. Every
correction below is applied by ``aoe2x/economy/compiler.py`` at compile time,
is verified against the DAT tables inside the snapshot where the DAT can
express it, and is reported in the runtime ``metadata.curatedCorrections``.

Sources (all for game update 188329, the patch carried by the supplied DAT,
SHA-256 d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f):
  DAT     raw technologies/effects stored in the snapshot (research_raw_*, production_raw_*, eco_raw_*)
  TECHTREE aoe2techtree.net data/data.json + locales/en/strings.json (site footer "DE Update 188329"),
           fetched 2026-11-12 by the independent review; data.json SHA-256
           e21b3d22d5101257a62fc6298377314852f929c12b0c997a9e986919658fd460
  REVIEW  branch army-economics-review (commit 4e3ca13de): docs/army-economics-review/{PRODUCTION,RESEARCH,GATHERING}.md
  WIKI    ageofempires.fandom.com pages cited per entry (fetched 2026-11-12 by the review)
"""

DECISION_DATE = "2026-11-12"
TECHTREE = "aoe2techtree.net data.json (DE update 188329, fetched 2026-11-12)"
REVIEW = "army-economics-review 4e3ca13de"

# --------------------------------------------------------------------------
# Owner decision 2: technologies missing from unit research packages.
# ``units``: unit ids (runtime unitId) of the civilization's roster that the
# technology affects. ``expected``: base cost/time from TECHTREE; the compiler
# fails if the DAT row disagrees.
ADDED_RESEARCH = [
    {"techId": 786, "name": "Winged Hussar", "civs": ["Poles", "Lithuanians"], "units": [1707],
     "building": 101, "expected": {"food": 600, "gold": 800, "seconds": 60},
     "reason": "Unit-line upgrade Light Cavalry -> Winged Hussar; absent from the extracted civ tech table.",
     "evidence": [f"{TECHTREE}: unit_upgrades[1707] = tech 786, 600F 800G, 60 s",
                  "DAT tech 786 (Stable 101, 600F/800G, 60 s); DAT effect 801 (Poles) cmd 26: tech 786 food x0.5",
                  f"{REVIEW} RESEARCH.md error 1"]},
    {"techId": 1484, "name": "Hamask", "civs": ["Danes"], "units": [567, 359, 2712, 2704],
     "building": 82, "expected": {"food": 250, "gold": 450, "seconds": 35},
     "reason": "Infantry deal more damage as they lose HP (engine flag, DAT resource 33 = 30).",
     "evidence": [f"{TECHTREE}: 'Infantry deal more damage as they lose HP.'",
                  "data/golden/aoe2_reference_simulation.db ref_techs_applied: Champion, Halberdier, Elite Jomsviking, Elite Varangian Guard",
                  f"{REVIEW} RESEARCH.md error 2"]},
    {"techId": 1464, "name": "Shield Wall", "civs": ["Saxons"], "units": [567, 359, 2706, 2704],
     "building": 82, "expected": {"food": 525, "gold": 475, "seconds": 45},
     "reason": "Infantry gain additional armor when massed (engine flag, DAT resource 33 = 31).",
     "evidence": [f"{TECHTREE}: 'Infantry gain additional armor when massed.'",
                  "data/golden/aoe2_reference_simulation.db ref_techs_applied: Champion, Halberdier, Elite Hearth Troop, Elite Varangian Guard",
                  "WIKI: Shield Wall", f"{REVIEW} RESEARCH.md error 3"]},
    {"techId": 1007, "name": "Ordo Cavalry", "civs": ["Khitans"], "units": [441, 1372, 330],
     "building": 82, "expected": {"food": 600, "gold": 300, "seconds": 45},
     "reason": "Non-projectile cavalry regenerate HP in combat (engine flag, DAT resource 33 = 3). "
               "Heavy Cavalry Archer and Mounted Trebuchet are projectile units and are not included.",
     "evidence": [f"{TECHTREE}: 'Cavalry regenerates HP in combat.'",
                  "WIKI: Ordo Cavalry ('Non-projectile cavalry regenerate...')", f"{REVIEW} RESEARCH.md error 4"]},
    {"techId": 1070, "name": "Coiled Serpent Array", "civs": ["Shu"], "units": [359, 1961],
     "building": 82, "expected": {"food": 350, "gold": 300, "seconds": 40},
     "reason": "Spearman-line and White Feather Guards gain HP when near each other (engine flag, resource 33 = 6).",
     "evidence": [f"{TECHTREE}: 'Spearman-line and White Feather Guards gain additional HP when near each other.'",
                  "WIKI: Coiled Serpent Array", f"{REVIEW} RESEARCH.md error 5"]},
    {"techId": 1380, "name": "Butalmapu", "civs": ["Mapuche"], "units": [2568],
     "building": 82, "expected": {"food": 500, "gold": 450, "seconds": 45},
     "reason": "Team Castle unique units and Bolas Riders cost -15%. The Bolas Rider part is an explicit DAT "
               "price command and is already linked; the Castle-unique-unit part (Kona) is engine hook 51.",
     "evidence": [f"{TECHTREE}: 'Team Castle Unique Units and Bolas Riders cost -15%.'",
                  "WIKI: Butalmapu; Kona (55F 34G with Butalmapu)", f"{REVIEW} RESEARCH.md error 6, PRODUCTION.md error 3"]},
    {"techId": 1080, "name": "Red Cliffs Tactics", "civs": ["Wu"], "units": [528],
     "building": 82, "expected": {"food": 400, "gold": 250, "seconds": 40},
     "reason": "Demolition Ships and Fire Archers deal fire damage (already linked to the Fire Archer).",
     "evidence": [f"{TECHTREE}: 'Demolition Ships and Fire Archers deal fire damage to ships and buildings.' (400F 250G)",
                  f"{REVIEW} RESEARCH.md error 7"]},
]

# Owner decision 3: technologies with no field-combat effect, removed from the
# combat research package (listed per unit under research.excludedNonCombat).
REMOVED_RESEARCH = [
    {"techId": 11, "name": "Crenellations", "civs": ["Teutons"],
     "reason": "Castles +3 range, garrisoned infantry fire arrows: no effect in a field battle."},
    {"techId": 924, "name": "Aznauri Cavalry", "civs": ["Georgians"],
     "reason": "Mounted units take -20% population space: no combat stat."},
]

# Owner decision 2 (fail-safe): every technology the research extraction left
# flagged 'player_resource_or_special_command_scope_needs_review' must have an
# explicit decision here, or the compiler fails.
CANDIDATE_DECISIONS = {
    21: ("excluded", "Atheism (Huns): relic/wonder victory timer and Spies cost; no unit stat."),
    28: ("excluded", "Bimaristan (Saracens): Monks heal several units; no roster combat stat."),
    45: ("keep_existing_links", "Faith: conversion resistance; Monks are not in the combat roster."),
    46: ("keep_existing_links", "Devotion: conversion resistance; Monks are not in the combat roster."),
    47: ("keep_existing_links", "Chemistry: already linked where it changes projectiles or unlocks gunpowder."),
    52: ("keep_existing_links", "Rocketry (Chinese): already linked to the units it changes."),
    207: ("keep_existing_links", "Long Swordsman (Wei): already linked as a line upgrade."),
    316: ("keep_existing_links", "Redemption: Monk conversion of buildings/siege; no roster combat stat."),
    319: ("keep_existing_links", "Atonement: Monk conversion of Monks; no roster combat stat."),
    438: ("keep_existing_links", "Theocracy: Monk faith recharge; no roster combat stat."),
    439: ("keep_existing_links", "Heresy: converted units die; conversion is not simulated."),
    464: ("keep_existing_links", "Greek Fire (Byzantines): already linked to fire ships."),
    482: ("excluded", "Stronghold (Celts): Castle/tower bonuses near buildings; not a field-army stat."),
    492: ("keep_existing_links", "Supremacy (Spanish): already linked."),
    578: ("excluded", "Kasbah (Berbers): production/research speed, modeled in the production review."),
    629: ("excluded", "Paper Money (Vietnamese): villager gold, modeled in the special economy."),
    688: ("keep_existing_links", "Tatars unique technology stored under the 'Malay UT' internal name: already linked."),
    690: ("excluded", "Cuman Mercenaries: one-time free Kipchaks per Castle; one-time grants are not repeatable production."),
    754: ("excluded", "Burgundian Vineyards: villager gold, modeled in the special economy."),
    755: ("keep_existing_links", "Flemish Revolution: already linked; variable cost remains an owner scope exception."),
    756: ("excluded", "First Crusade (Sicilians): one-time Serjeant spawns; not repeatable production."),
    1007: ("added", "Ordo Cavalry: see ADDED_RESEARCH."),
    1010: ("excluded", "Dragon Ship (Chinese): automatic Fire Ship -> Dragon Ship upgrade; the Fire Ship row is dropped "
                       "and a Dragon Ship combat profile does not exist yet (follow-up)."),
    1061: ("excluded", "Tuntian (Wei): income excluded by the owner (2026-11-11)."),
    1070: ("added", "Coiled Serpent Array: see ADDED_RESEARCH."),
    1080: ("added", "Red Cliffs Tactics: see ADDED_RESEARCH (Fire Archer link kept)."),
    1380: ("added", "Butalmapu: see ADDED_RESEARCH (Bolas Rider link kept) and KONA price."),
    1393: ("keep_existing_links", "Curare (Tupi): already linked."),
    1404: ("excluded", "Circumnavigation (Portuguese): ship training speed, modeled in the production review."),
    1462: ("keep_existing_links", "Elite Hearth Troop (Saxons): already linked as a line upgrade."),
    1464: ("added", "Shield Wall: see ADDED_RESEARCH."),
    1484: ("added", "Hamask: see ADDED_RESEARCH."),
}

# --------------------------------------------------------------------------
# Owner decision 5: production and price corrections.
PROFILE_DROPS = [
    {"civ": "Berbers", "unitId": 1631, "name": "Xebec",
     "reason": "Not a post-Imperial Berber unit: unit 1631 is absent from the Berber game tree (owner decision 8)."},
    {"civ": "Chinese", "unitId": 529, "name": "Fire Ship",
     "reason": "Chinese Fire Ships upgrade automatically to the Dragon Ship (unit 1302) in the Imperial Age "
               "(owner decision 8). The Dragon Ship is not added: the combat reference DB has no Dragon Ship "
               "profile/mechanics to attach it to (follow-up)."},
]

# Building upgrade the route resolver did not follow (DAT effect 941: Armenian Monastery 104 -> Fortified Church 1806).
BUILDING_SUBSTITUTIONS = [
    {"civ": "Armenians", "from": 104, "to": 1806, "effectId": 941,
     "reason": "Armenians cannot build a Monastery; the Warrior Priest trains at the Fortified Church (200 wood).",
     "evidence": ["DAT effect 941 'C-Bonus, Fortified Church' (type 3, 104 -> 1806)",
                  f"{TECHTREE}: Armenian building list has 1806, not 104", "WIKI: Warrior Priest (Building = Fortified Church)",
                  f"{REVIEW} PRODUCTION.md error 1"]},
]

# Settlement adds a training slot (DAT effect 1382, attribute 158 x32767 sentinel); the resolver
# overwrote the regular slot instead. Restore the regular route; the cheapest/fastest route rule then chooses.
RESTORED_ROUTES = [
    {"civ": "Mapuche", "unitId": 359, "building": 12, "template": {"civ": "Mapuche", "unitId": 2554},
     "baseTrainSeconds": 22},
    {"civ": "Mapuche", "unitId": 6, "building": 87, "template": {"civ": "Mapuche", "unitId": 24},
     "baseTrainSeconds": 22},
]
RESTORED_ROUTE_EVIDENCE = [f"{TECHTREE}: Mapuche 'Settlements can train Spearman-line and Skirmishers'",
                           "WIKI: Settlement (trains them in addition to regular production buildings)",
                           f"{REVIEW} PRODUCTION.md error 2"]

# Persian 'TC and Dock work rate' (DAT effect 421): Dock 45 x1.05, 133 x1.10, 47 x1.15, 51 x1.20;
# the Imperial Age upgrades Dock 45 -> 51. Use the Imperial command.
AGE_VARIANT_WORK_RATE = [
    {"civ": "Persians", "building": 45, "effectId": 421, "imperialBuilding": 51,
     "evidence": [f"{TECHTREE}: Persians 'Docks work +5/10/15/20% faster in Dark/Feudal/Castle/Imperial Age'",
                  f"{REVIEW} PRODUCTION.md error 4"]},
]

# Engine-hook price effects the DAT cannot express (Butalmapu hook 51: Castle unique units -15%).
PRICE_MULTIPLIERS = [
    {"civ": "Mapuche", "unitId": 2568, "multiplier": 0.85, "techId": 1380,
     "reason": "Butalmapu: Team Castle unique units cost -15% (Elite Kona 65F 40G -> 55F 34G).",
     "evidence": [f"{TECHTREE}: Butalmapu text", "WIKI: Kona (55F 34G with Butalmapu)", f"{REVIEW} PRODUCTION.md error 3"]},
]

ROUNDING_RULE = ("Discounted unit prices are rounded half up (x.5 -> x+1) after all multipliers, per resource. "
                 "The previous policy used Python round() (half to even). The game's own rule is not verified in game; "
                 "the change moves at most 1 resource per unit and only affects exact halves.")

# Owner decision 6: Wu military buildings and Docks grant +55 food when built (DAT tech 1084, attribute 27).
PRODUCTION_REBATES = [
    {"civ": "Wu", "techId": 1084, "resource": "food",
     "reason": "Wu military buildings and Docks give +55 food when completed; credited as a rebate on each production building.",
     "evidence": ["DAT tech 1084 'C-Bonus, Military Buildings +55f' (type 4, attribute 27, +55)",
                  f"{REVIEW} PRODUCTION.md open question 3"]},
]

# Owner decision 1 (prerequisite rule fix): civilization bonuses that the corrected
# "required_tech_count 0 = no prerequisite" rule activates. Anything else fails compilation.
PREREQUISITE_RULE_ACTIVATIONS = {("Danes", 1494)}

# --------------------------------------------------------------------------
# Owner decisions 4, 7, 9, 10: notes carried in the data (no economics change).
AGE_UP_NOTE = ("Age-ups are not in the headline (both armies need the Imperial Age); civilization age-up "
               "discounts and grants are listed here for the UI.")
AGE_UP_TEXT = {  # TECHTREE civ help texts; DAT-backed entries are cross-checked by the compiler.
    "Byzantines": "Advancing to the Imperial Age costs -33%",
    "Dravidians": "Receive +200 wood when advancing to the next Age",
    "Ethiopians": "Receive +100 gold and +100 food when advancing to the next Age",
    "Italians": "Advancing to the next Age costs -15%",
    "Khmer": "No buildings required to advance to the next Age",
    "Malay": "Advancing to the next Age is +66% faster",
    "Muisca": "Advancing to the next Age costs -50% gold",
}
EXCLUDED_INCOME = ("Not counted as villager labor: relics, trade (Caravanserai, trade carts/cogs), Feitoria and other "
                   "trickle buildings, Wei Tuntian, Gurjara livestock in Mills, fishing/fish traps, combat rewards, "
                   "one-time grants (e.g. Cuman Mercenaries, First Crusade) and the Tupi casualty refund.")
CIV_NOTES = {
    "Lithuanians": ["Combat stats elsewhere in this project assume 4 relics held "
                    "(aoe2x/dbgen/config_constants.py LITHUANIAN_RELIC_COUNT = 4). Relics are not counted as income here."],
    "Saxons": ["Assumption: foot soldiers cost -20% (maximum discount; four controlled Town Centers/Castles)."],
    "Khitans": ["Pasture food (~25.2 food per villager-minute) is an online lifecycle average: the lowest-confidence food rate."],
    "Poles": ["Folwark: 10% instant farm food (DAT), 8 of 10 farms covered, taken out of the farm; measured over a steady-state window."],
    "Danes": ["Villagers drop off +5% food (tech 1494), modeled like the Malian gold bonus."],
    "Wu": ["Each military building and Dock refunds 55 food when built (rebate on production buildings in the headline)."],
    "Mapuche": ["Elite Kona includes the Butalmapu -15% price; Spearman-line and Skirmishers can train at the "
                "Barracks/Archery Range or the Settlement (the cheaper/faster route is used)."],
    "Portuguese": ["Feitoria income is excluded."],
}
