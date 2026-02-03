#!/usr/bin/env python3
"""
AoE2:DE Data Extractor
Extracts unit, technology, and civilization data from empires2_x2_p1.dat
"""

import json
from pathlib import Path
from genieutils.datfile import DatFile

# Known armor/attack class names
ARMOR_CLASSES = {
    0: "Unused",
    1: "Infantry",
    2: "Turtle Ships",
    3: "Base Pierce",
    4: "Base Melee",
    5: "War Elephants",
    6: "Unused",
    7: "Unused",
    8: "Cavalry",
    9: "Unused",
    10: "Unused",
    11: "All Buildings",
    12: "Unused",
    13: "Stone Defense",
    14: "Predator Animals",
    15: "Archers",
    16: "Ships & Saboteurs",
    17: "Rams",
    18: "Trees",
    19: "Unique Units",
    20: "Siege Weapons",
    21: "Standard Buildings",
    22: "Walls & Gates",
    23: "Gunpowder Units",
    24: "Boars",
    25: "Monks",
    26: "Castles",
    27: "Spearmen",
    28: "Cavalry Archers",
    29: "Eagle Warriors",
    30: "Camels",
    31: "Leitis",
    32: "Condottieri",
    33: "Fishing Ships",
    34: "Mamelukes",
    35: "Heroes & Kings",
    36: "Hussite Wagons",
    37: "Unused",
    38: "Elephants",
    39: "Mounted Archers",
}

# Unit class names (from class_ attribute)
UNIT_CLASSES = {
    0: "Archer",
    1: "Artifact",
    2: "Trade Boat",
    3: "Building",
    4: "Civilian",
    5: "Ocean Fish",
    6: "Infantry",
    7: "Berry Bush",
    8: "Stone Mine",
    9: "Prey Animal",
    10: "Predator Animal",
    11: "Miscellaneous",
    12: "Cavalry",
    13: "Siege Weapon",
    14: "Terrain",
    15: "Tree",
    16: "Tree Stump",
    17: "Healer",
    18: "Monk",
    19: "Trade Cart",
    20: "Transport Boat",
    21: "Fishing Boat",
    22: "Warship",
    23: "Conquistador",
    24: "War Elephant",
    25: "Hero",
    26: "Elephant Archer",
    27: "Wall",
    28: "Phalanx",
    29: "Domestic Animal",
    30: "Flag",
    31: "Deep Sea Fish",
    32: "Gold Mine",
    33: "Shore Fish",
    34: "Cliff",
    35: "Petard",
    36: "Cavalry Archer",
    37: "Doppelganger",
    38: "Bird",
    39: "Gate",
    40: "Salvage Pile",
    41: "Resource Pile",
    42: "Relic",
    43: "Monk with Relic",
    44: "Hand Cannoneer",
    45: "Two-Handed Swordsman",
    46: "Pikeman",
    47: "Scout",
    48: "Ore Mine",
    49: "Farm",
    50: "Spearman",
    51: "Packed Unit",
    52: "Tower",
    53: "Boarding Boat",
    54: "Unpacked Siege Unit",
    55: "Ballista",
    56: "Raider",
    57: "Cavalry Raider",
    58: "Livestock",
    59: "King",
    60: "Miscellaneous",
    61: "Controlled Animal",
}

# Civilization names (order matters - matches civ IDs)
CIV_NAMES = [
    "Gaia",  # 0
    "Britons",
    "Franks",
    "Goths",
    "Teutons",
    "Japanese",
    "Chinese",
    "Byzantines",
    "Persians",
    "Saracens",
    "Turks",
    "Vikings",
    "Mongols",
    "Celts",
    "Spanish",
    "Aztecs",
    "Mayans",
    "Huns",
    "Koreans",
    "Italians",
    "Indians",
    "Incas",
    "Magyars",
    "Slavs",
    "Portuguese",
    "Ethiopians",
    "Malians",
    "Berbers",
    "Khmer",
    "Malay",
    "Burmese",
    "Vietnamese",
    "Bulgarians",
    "Tatars",
    "Cumans",
    "Lithuanians",
    "Burgundians",
    "Sicilians",
    "Poles",
    "Bohemians",
    "Dravidians",
    "Bengalis",
    "Gurjaras",
    "Romans",
    "Armenians",
    "Georgians",
]

# Comprehensive unit ID to display name mappings
UNIT_NAMES = {
    # ===== Core Infantry =====
    74: "Spearman",
    75: "Man-at-Arms",
    76: "Long Swordsman",
    77: "Militia",
    93: "Pikeman",
    358: "Pikeman",
    359: "Halberdier",
    360: "Champion",
    567: "Two-Handed Swordsman",
    751: "Eagle Scout",
    753: "Eagle Warrior",
    752: "Elite Eagle Warrior",
    1: "Legionary (AoE1)",

    # ===== Core Archers =====
    4: "Archer",
    24: "Crossbowman",
    492: "Arbalester",
    7: "Skirmisher",
    6: "Elite Skirmisher",
    1155: "Imperial Skirmisher",
    5: "Hand Cannoneer",
    185: "Slinger",
    39: "Cavalry Archer",
    474: "Heavy Cavalry Archer",
    569: "Paladin",

    # ===== Core Cavalry =====
    448: "Scout Cavalry",
    546: "Light Cavalry",
    530: "Hussar",
    1658: "Winged Hussar",
    38: "Knight",
    283: "Cavalier",
    529: "Paladin",
    329: "Camel Rider",
    207: "Camel Rider",
    330: "Heavy Camel Rider",
    441: "Imperial Camel Rider",
    1252: "Battle Elephant",
    1254: "Elite Battle Elephant",
    1258: "Steppe Lancer",
    1259: "Elite Steppe Lancer",

    # ===== Siege Weapons =====
    35: "Battering Ram",
    493: "Capped Ram",
    527: "Siege Ram",
    1733: "Armored Elephant",
    1735: "Siege Elephant",
    280: "Mangonel",
    550: "Onager",
    588: "Siege Onager",
    279: "Scorpion",
    281: "Heavy Scorpion",
    36: "Bombard Cannon",
    1660: "Houfnice",
    42: "Trebuchet",
    331: "Trebuchet (Packed)",
    188: "Siege Tower",

    # ===== Monks =====
    125: "Monk",
    286: "Monk with Relic",
    759: "Missionary",
    1749: "Warrior Priest",
    1751: "Elite Warrior Priest",

    # ===== Ships =====
    13: "Fishing Ship",
    17: "Trade Cog",
    21: "Galley",
    420: "War Galley",
    442: "Galleon",
    539: "Transport Ship",
    1103: "Fire Galley",
    885: "Fire Ship",
    532: "Fast Fire Ship",
    875: "Demolition Raft",
    886: "Demolition Ship",
    1104: "Heavy Demolition Ship",
    869: "Cannon Galleon",
    873: "Elite Cannon Galleon",
    1743: "Dromon",
    1702: "Thirisadai",
    250: "Longboat",
    533: "Elite Longboat",

    # ===== Unique Units - Britons =====
    8: "Longbowman",
    545: "Elite Longbowman",

    # ===== Unique Units - Franks =====
    1001: "Throwing Axeman",
    1003: "Elite Throwing Axeman",

    # ===== Unique Units - Goths =====
    41: "Huskarl",
    554: "Elite Huskarl",

    # ===== Unique Units - Teutons =====
    25: "Teutonic Knight",
    556: "Elite Teutonic Knight",

    # ===== Unique Units - Japanese =====
    291: "Samurai",
    560: "Elite Samurai",

    # ===== Unique Units - Chinese =====
    73: "Chu Ko Nu",
    559: "Elite Chu Ko Nu",

    # ===== Unique Units - Byzantines =====
    40: "Cataphract",
    553: "Elite Cataphract",

    # ===== Unique Units - Persians =====
    422: "War Elephant",
    555: "Elite War Elephant",

    # ===== Unique Units - Saracens =====
    832: "Mameluke",
    831: "Elite Mameluke",

    # ===== Unique Units - Turks =====
    46: "Janissary",
    557: "Elite Janissary",

    # ===== Unique Units - Vikings =====
    866: "Berserk",
    775: "Elite Berserk",
    94: "Berserk",

    # ===== Unique Units - Mongols =====
    11: "Mangudai",
    561: "Elite Mangudai",

    # ===== Unique Units - Celts =====
    232: "Woad Raider",
    548: "Elite Woad Raider",

    # ===== Unique Units - Spanish =====
    771: "Conquistador",
    773: "Elite Conquistador",

    # ===== Unique Units - Aztecs =====
    765: "Jaguar Warrior",
    764: "Elite Jaguar Warrior",

    # ===== Unique Units - Mayans =====
    763: "Plumed Archer",
    756: "Elite Plumed Archer",

    # ===== Unique Units - Huns =====
    755: "Tarkan",
    757: "Elite Tarkan",

    # ===== Unique Units - Koreans =====
    827: "War Wagon",
    829: "Elite War Wagon",
    828: "Turtle Ship",
    830: "Elite Turtle Ship",

    # ===== Unique Units - Italians =====
    1004: "Genoese Crossbowman",
    1006: "Elite Genoese Crossbowman",
    866: "Condottiero",

    # ===== Unique Units - Indians/Hindustanis =====
    1010: "Elephant Archer",
    1012: "Elite Elephant Archer",
    1747: "Ghulam",
    1749: "Elite Ghulam",

    # ===== Unique Units - Incas =====
    1016: "Kamayuk",
    1018: "Elite Kamayuk",

    # ===== Unique Units - Magyars =====
    1007: "Magyar Huszar",
    1009: "Elite Magyar Huszar",

    # ===== Unique Units - Slavs =====
    1013: "Boyar",
    1015: "Elite Boyar",

    # ===== Unique Units - Portuguese =====
    1120: "Organ Gun",
    1122: "Elite Organ Gun",
    1123: "Caravel",
    1125: "Elite Caravel",

    # ===== Unique Units - Ethiopians =====
    1132: "Shotel Warrior",
    1134: "Elite Shotel Warrior",

    # ===== Unique Units - Malians =====
    1129: "Gbeto",
    1131: "Elite Gbeto",

    # ===== Unique Units - Berbers =====
    1123: "Camel Archer",
    1125: "Elite Camel Archer",
    1126: "Genitour",
    1128: "Elite Genitour",

    # ===== Unique Units - Khmer =====
    1225: "Ballista Elephant",
    1227: "Elite Ballista Elephant",

    # ===== Unique Units - Malay =====
    1228: "Karambit Warrior",
    1230: "Elite Karambit Warrior",

    # ===== Unique Units - Burmese =====
    1231: "Arambai",
    1233: "Elite Arambai",

    # ===== Unique Units - Vietnamese =====
    1234: "Rattan Archer",
    1236: "Elite Rattan Archer",

    # ===== Unique Units - Bulgarians =====
    1263: "Konnik",
    1265: "Elite Konnik",
    1275: "Konnik (Dismounted)",
    1277: "Elite Konnik (Dismounted)",

    # ===== Unique Units - Tatars =====
    1268: "Keshik",
    1270: "Elite Keshik",

    # ===== Unique Units - Cumans =====
    1271: "Kipchak",
    1273: "Elite Kipchak",

    # ===== Unique Units - Lithuanians =====
    1274: "Leitis",
    1276: "Elite Leitis",

    # ===== Unique Units - Burgundians =====
    1370: "Coustillier",
    1372: "Elite Coustillier",
    1374: "Flemish Militia",

    # ===== Unique Units - Sicilians =====
    1575: "Serjeant",
    1577: "Elite Serjeant",

    # ===== Unique Units - Poles =====
    1655: "Obuch",
    1657: "Elite Obuch",

    # ===== Unique Units - Bohemians =====
    1596: "Hussite Wagon",
    1598: "Elite Hussite Wagon",

    # ===== Unique Units - Dravidians =====
    1699: "Urumi Swordsman",
    1701: "Elite Urumi Swordsman",

    # ===== Unique Units - Bengalis =====
    1709: "Ratha",
    1707: "Elite Ratha",

    # ===== Unique Units - Gurjaras =====
    1705: "Chakram Thrower",
    1704: "Elite Chakram Thrower",
    1714: "Shrivamsha Rider",
    1713: "Elite Shrivamsha Rider",

    # ===== Unique Units - Romans =====
    1737: "Centurion",
    1739: "Elite Centurion",
    1741: "Legionary",

    # ===== Unique Units - Armenians =====
    1746: "Composite Bowman",
    1748: "Elite Composite Bowman",

    # ===== Unique Units - Georgians =====
    1752: "Monaspa",
    1754: "Elite Monaspa",

    # ===== Three Kingdoms DLC Units =====
    1949: "Tiger Cavalry",
    1951: "Elite Tiger Cavalry",
    1952: "Xianbei Raider",
    1959: "White Feather Crossbowman",
    1961: "Elite White Feather Crossbowman",
    1962: "War Chariot (3K)",
    1968: "Fire Archer",
    1970: "Elite Fire Archer",
    1974: "Jian Swordsman",
    1976: "Jian Swordsman (Unique)",
    1980: "War Chariot (3K)",

    # ===== Three Kingdoms Heroes =====
    1954: "Cao Cao",
    1966: "Liu Bei",
    1978: "Sun Jian",
    2032: "Lu Bu",
    2034: "Guan Yu",
    2036: "Zhuge Liang",
    2038: "Zhang Fei",
    2040: "Sun Ce",
    2042: "Sun Quan",
    2044: "Zhou Yu",
    2045: "Dong Zhuo",
    2046: "Yuan Shao",
    2047: "Yu Ji",
    2048: "White Tiger Yan",
    2049: "Liu Biao",
    2050: "Zhang Jue",
    2051: "Zhao Yun",
    2052: "Cao Cao (Hero)",
    2053: "Liu Bei (Hero)",
    2054: "Sun Jian (Hero)",

    # ===== Antiquity Mode Units =====
    2101: "Immortal",
    2102: "Elite Immortal",
    2104: "Strategos",
    2105: "Elite Strategos",
    2107: "Hippeus",
    2108: "Elite Hippeus",
    2110: "Hoplite",
    2111: "Elite Hoplite",
    2150: "War Chariot",
    2151: "Elite War Chariot",
    2174: "Immortal (Ranged)",
    2175: "Elite Immortal (Ranged)",
    2187: "Hoplite with Xyphos",
    2188: "Elite Hoplite with Xyphos",
    2227: "Strategos with Taxiarchs",
    2228: "Elite Strategos with Taxiarchs",
    2320: "Rhodian Slinger",
    2321: "Mercenary Hoplite",
    2322: "Elite Greek Cavalry",
    2323: "Elite Persian Cavalry",
    2324: "Elite Persian Archer",
    2325: "Ekdromos",
    2326: "Cretan Archer",
    2327: "Camel Raider",
    2328: "Tarantine Cavalry",
    2329: "Sparabara",
    2330: "Takabara",
    2331: "Sickle Warrior",
    2332: "Thracian Peltast",
    2349: "Elite Hoplite",
    2382: "Companion Cavalry",
    2383: "Elite Companion Cavalry",
    2384: "Phalangite",
    2385: "Elite Phalangite",
    2386: "Rhomphaia Warrior",
    2387: "Elite Rhomphaia Warrior",
    2388: "Pattiyodha Longbowman",
    2389: "Elite Pattiyodha Longbowman",
    2390: "Sannahya",
    2391: "Elite Sannahya",
    2419: "Pattiyodha Longbowman",
    2420: "Elite Pattiyodha Longbowman",
    2485: "Scythian Horse Archer",
    2486: "Elite Scythian Horse Archer",
    2487: "Sacred Band",

    # ===== Antiquity Ships =====
    2123: "Lembos",
    2124: "War Lembos",
    2125: "Heavy Lembos",
    2126: "Elite Lembos",
    2127: "Monoreme",
    2128: "Bireme",
    2129: "Trireme",
    2130: "Galley (Antiquity)",
    2131: "War Galley (Antiquity)",
    2132: "Elite Galley (Antiquity)",
    2133: "Incendiary Raft",
    2134: "Incendiary Ship",
    2135: "Heavy Incendiary Ship",
    2138: "Catapult Ship",
    2139: "Onager Ship",
    2140: "Leviathan",
    2147: "Fishing Ship (Antiquity)",
    2148: "Transport Ship (Antiquity)",
    2149: "Merchant Ship",
    2171: "Oystering Ship",
    2356: "Fishing Ship (Antiquity)",

    # ===== Antiquity Heroes =====
    2308: "Artaphernes",
    2309: "Datis",
    2310: "Aristagoras",
    2311: "Dionysus",
    2312: "Artemisia",
    2313: "Aristides",
    2314: "Miltiades",
    2315: "Themistocles",
    2316: "Leonidas",
    2317: "Brasidas",
    2318: "Lysander",
    2319: "The Aeginetan",
    2339: "Themistocles (Warship)",
    2346: "Cleon",
    2347: "Darius",
    2397: "Alexander (Dismounted)",
    2398: "Alexander",
    2399: "Philip II",
    2400: "Parmenion",
    2401: "Cleitus",
    2402: "Hephaistion",
    2403: "Perdiccas",
    2404: "Nearchos",
    2436: "Porus",
    2449: "Indian Tribesman",
    2451: "Thracian Chieftain",
    2453: "Hill Tribesman",
    2525: "Bucephalus",

    # ===== Polemarch Units =====
    2162: "Polemarch I",
    2164: "Polemarch II",
    2165: "Polemarch III",
    2166: "Polemarch IV",
    2167: "Polemarch III (Ephorate)",
    2168: "Hippeus",
    2169: "Elite Hippeus",
    2270: "Polemarch IV (Ephorate)",
    2271: "Polemarch III (Morai)",
    2272: "Polemarch IV (Morai)",

    # ===== Alexander Campaign Units =====
    2459: "Alexander's Rhomphaia Warrior",
    2460: "Alexander's Peltast",
    2461: "Alexander's Ekdromos",
    2462: "Alexander's Strategos",
    2463: "Alexander's Slinger",
    2464: "Alexander's Mercenary Archer",
    2465: "Alexander's Axe Cavalry",
    2466: "Alexander's Axeman",
    2467: "Alexander's Immortal",
    2468: "Alexander's Immortal (Ranged)",
    2469: "Alexander's War Chariot",
    2470: "Alexander's Skirmisher Cavalry",
    2471: "Alexander's Heavy Cavalry",
    2472: "Alexander's Sannahya",
    2473: "Alexander's Longbowman",
    2474: "Alexander's Eastern Archer",
    2475: "Alexander's Sickle Warrior",

    # ===== Villagers =====
    83: "Villager (Male)",
    293: "Villager (Female)",
    56: "Villager (Male Fisher)",
    57: "Villager (Female Fisher)",
    118: "Villager (Male Builder)",
    212: "Villager (Female Builder)",
    120: "Villager (Male Forager)",
    214: "Villager (Female Farmer)",
    122: "Villager (Male Hunter)",
    216: "Villager (Female Hunter)",
    123: "Villager (Male Lumberjack)",
    218: "Villager (Female Lumberjack)",
    124: "Villager (Male Miner)",
    220: "Villager (Female Miner)",
    156: "Villager (Male Repairer)",
    222: "Villager (Female Repairer)",
    259: "Villager (Male Farmer)",
    206: "Villager (Male)",
    2333: "Villager (Male Gold Miner)",
    2334: "Villager (Female Gold Miner)",

    # ===== Trade Units =====
    128: "Trade Cart",
    204: "Trade Cart (Full)",

    # ===== Petard =====
    755: "Petard",

    # ===== King =====
    434: "King",

    # ===== Wild Animals =====
    48: "Wild Boar",
    810: "Javelina",
    126: "Wolf",
    202: "Dire Wolf",
    89: "Dire Wolf",
    65: "Deer",
    822: "Ibex",
    1026: "Ostrich",
    2340: "Mouflon",
    1955: "Red Fox",
    1958: "Arctic Fox",
    1965: "Arctic Wolf",
    2089: "Black Bear",
    2090: "Polar Bear",
    2091: "Arctic Wolf",

    # ===== Livestock =====
    594: "Sheep",
    705: "Cow",
    1243: "Water Buffalo",
    1142: "Goat",
    1963: "Llama",
    2381: "Goat (Antiquity)",

    # ===== Birds =====
    96: "Hawk",
    2490: "Owl",
    2537: "Peacock",

    # ===== Campaign Heroes =====
    106: "Harald Hardraade",
    114: "Erik the Red",
    138: "Spy",
    159: "Artifact",
    160: "Richard the Lionheart",
    161: "The Black Prince",
    163: "Friar Tuck",
    164: "Sheriff of Nottingham",
    165: "Charlemagne",
    166: "Roland",
    167: "Belisarius",
    168: "Theodoric",
    169: "Aethelfrid",
    170: "Siegfried",
    171: "Erik the Red",
    172: "Tamerlane",
    173: "Karthage",
    174: "Lancelot",
    175: "Gawain",
    176: "Mordred",
    177: "Archbishop",
    193: "Vlad Dracula",
    195: "Kitabatake",
    196: "Minamoto",
    197: "William Wallace",
    198: "El Cid",
    200: "Robin Hood",
    203: "Vasco da Gama",
    223: "Alaric",
    230: "Bela IV",
    275: "Centurion (AoE1)",
    282: "Dervish",

    # ===== Miscellaneous =====
    184: "Condottiero (Placeholder)",
    239: "Siege Tower (Packed)",
    2026: "Crane",
    2067: "Kongming Lantern",
    2444: "Siege Tower",
    1988: "Emperor's Litter",
    1973: "Nessie",
    748: "Cobra Car",
    1222: "Sharkatzor",
}

# Additional unit ID mappings for heroes and special units
UNIT_NAMES.update({
    299: "Infiltrator",
    307: "Cuauhtémoc",
    309: "Monk with Relic",
    354: "Villager (Female Forager)",
    418: "Henry the Lion",
    424: "Charles Martel",
    425: "Ornlu the Wolf",
    426: "Harun al-Rashid",
    427: "Gonzalo Pizarro",
    428: "Harald Hardrada",
    429: "Barbarossa",
    430: "Joan of Arc",
    432: "William the Conqueror",
    436: "Demolition Ship",
    437: "Prithviraj",
    438: "Bombard Ship",
    439: "Sforza",
    440: "Petard",
    453: "Ataulf",
    473: "Two-Handed Swordsman (Hero)",
    486: "Brown Bear",
    528: "Caravel",
    531: "Throwing Axeman (Unique)",
    534: "Woad Raider (Unique)",
    535: "Boarding Galley",
    536: "Boarding Galley",
    542: "Ballista",
    544: "Flying Dog",
    558: "Siege Tower (Hero)",
    571: "Raiding Archer",
    573: "Raiding Swordsman",
    575: "Raiding Cavalry",
    577: "Raiding Cavalry Archer",
    583: "Genitour",
    590: "Villager (Female Shepherd)",
    592: "Villager (Male Shepherd)",
    596: "Elite Genitour",
    629: "Joker",
    632: "Forester",
    634: "Metz",
    636: "Bertrand",
    638: "Alencon",
    639: "Penguin",
    640: "Hireling",
    642: "Gravedigger",
    646: "Richard",
    648: "Josselin",
    652: "Falstaff",
    678: "Rey",
    680: "Mot",
    686: "Composite Archer",
    691: "Cannon Boat",
    692: "Berserk (Light)",
    694: "Berserk (Unique Light)",
    698: "Subotai",
    700: "Hunting Wolf",
    702: "Furious the Monkey Boy",
    704: "Stormy Dog",
    748: "Cobra Car",
    758: "Elite Tarkan",
    776: "Jarl",
    807: "Ornlu the Wolf",
    836: "Genghis Khan",
    838: "Hunting Wolf",
    844: "Elite Huskarl (Hero)",
    1027: "Crocodile",
    1029: "Komodo Dragon",
    1031: "Lion",
    1033: "Elephant",
    1035: "Rhinoceros",
    1048: "Box Turtles",
    1060: "Alfred the Alpaca",
    1137: "Tiger",
    1222: "Sharkatzor",
    1988: "Emperor's Litter",
    1973: "Nessie",
})

# Internal name to display name fallback mapping
INTERNAL_NAME_MAP = {
    "ARCHR": "Archer",
    "HCANR": "Hand Cannoneer",
    "HXBOW": "Elite Skirmisher",
    "XBOWM": "Skirmisher",
    "LNGBW": "Longbowman",
    "FSHSP": "Fishing Ship",
    "COGXX": "Trade Cog",
    "GALLY": "Galley",
    "CARCH": "Crossbowman",
    "TKNIT": "Teutonic Knight",
    "BTRAM": "Battering Ram",
    "BCANN": "Bombard Cannon",
    "LANCE": "Lancer",
    "KNGHT": "Knight",
    "CVRCH": "Cavalry Archer",
    "CATAP": "Cataphract",
    "GBRSK": "Huskarl",
    "JANNI": "Janissary",
    "CHUKN": "Chu Ko Nu",
    "SPRMN": "Spearman",
    "SWDMN": "Man-at-Arms",
    "HVSWD": "Long Swordsman",
    "THSWD": "Two-Handed Swordsman",
    "MONKX": "Monk",
    "TCART": "Trade Cart",
    "PKEMN": "Pikeman",
    "BRSRK": "Berserk",
    "SCBAL": "Scorpion",
    "MANGO": "Mangonel",
    "TAXEM": "Throwing Axeman",
    "DERVI": "Dervish",
    "ONAGR": "Onager",
    "SNAGR": "Siege Onager",
    "TREBU": "Trebuchet",
    "PTREB": "Trebuchet (Packed)",
    "WBRSK": "Woad Raider",
    "CENTU": "Centurion",
    "SHCLRY": "Camel Rider",
    "MPCAV": "Siege Tower",
    "ORGAN": "Organ Gun",
    "EORGAN": "Elite Organ Gun",
    "SIEGTWR": "Siege Tower",
    "FIREARCHER": "Fire Archer",
    "EFIREARCHER": "Elite Fire Archer",
    "TIGERCAV": "Tiger Cavalry",
    "ETIGERCAV": "Elite Tiger Cavalry",
    "XIANBEI": "Xianbei Raider",
    "WHTFTHRG": "White Feather Crossbowman",
    "EWHTFTHRG": "Elite White Feather Crossbowman",
    "WARCHAR": "War Chariot",
    "JIANSWDS": "Jian Swordsman",
    "JIANSWDUS": "Jian Swordsman (Unique)",
    "HOUFNICE": "Houfnice",
    "MOSUN": "Mangudai",
    "JUNKX": "Junk",
    "DEERX": "Deer",
    "BOARX": "Wild Boar",
    "WOLFX": "Wolf",
    "DWOLF": "Dire Wolf",
    "VMBAS": "Villager (Male)",
    "VMFIS": "Villager (Male Fisher)",
    "VFFIS": "Villager (Female Fisher)",
    "VMBLD": "Villager (Male Builder)",
    "VMFOR": "Villager (Male Forager)",
    "VMHUN": "Villager (Male Hunter)",
    "VMLUM": "Villager (Male Lumberjack)",
    "VMMIN": "Villager (Male Miner)",
    "VMREP": "Villager (Male Repairer)",
    "VMFAR": "Villager (Male Farmer)",
    "VFBLD": "Villager (Female Builder)",
    "VFFAR": "Villager (Female Farmer)",
    "VFHUN": "Villager (Female Hunter)",
    "VFLUM": "Villager (Female Lumberjack)",
    "VFMIN": "Villager (Female Miner)",
    "VFREP": "Villager (Female Repairer)",
    "VMDL": "Villager (Male)",
    "VMGLD": "Villager (Male Gold Miner)",
    "VFGLD": "Villager (Female Gold Miner)",
    "OUTLW": "Outlaw",
    "ARTCT": "Artifact",
    "HAWKX": "Hawk",
    "XPORT": "Transport Ship",
    "HLBDM": "Halberdier",
    "DHLBDM": "Halberdier",
    "FLPKM": "Flemish Pikeman",
    "DISPKM": "Pikeman (Dismounted)",
    "SGTWR": "Fire Ship",
    "HLORR": "Heavy Scorpion",
    "HBURE": "Houfnice",
    "COBRA": "Cobra Car",
    "SHARKATZOR": "Sharkatzor",
    "RCKTCRT": "Rocket Cart",
    "HRCKTCRT": "Heavy Rocket Cart",
    "TRTREB": "Traction Trebuchet",
    "LNGBT": "Longboat",
    "RJANI": "Janissary (Ranged)",
    "HSTOER": "Harald Hardraade",
    "HLEIF": "Leif Erikson",
    "HRLION": "Richard the Lionheart",
    "HBLACK": "The Black Prince",
    "HFRIAR": "Friar Tuck",
    "HSHERN": "Sheriff of Nottingham",
    "HCHARL": "Charlemagne",
    "HROLAN": "Roland",
    "HBELIS": "Belisarius",
    "HTHEOD": "Theodoric",
    "HAETH": "Aethelfrid",
    "HSIEG": "Siegfried",
    "HERIK": "Erik the Red",
    "HTAME": "Tamerlane",
    "HKARTH": "Karthage",
    "HLANCE": "Lancelot",
    "HGAWA": "Gawain",
    "HMORD": "Mordred",
    "HARCH": "Archbishop",
    "HVLAD": "Vlad Dracula",
    "HKITA": "Kitabatake",
    "HMINA": "Minamoto",
    "HWILL": "William Wallace",
    "HELCID": "El Cid",
    "HROBN": "Robin Hood",
    "HVASCO": "Vasco da Gama",
    "HALARIC": "Alaric",
    "HBELA": "Bela IV",
    "CONDOPLACEHOLDER": "Condottiero",
    "WOLF2": "Wolf",
    "TCARTF": "Trade Cart (Full)",
    "HSUMANGURU": "Sumanguru",
    "FMANGRO": "Mango Tree",
    "SUMANGURU_D": "Sumanguru",
    "PROJMTREB_D": "Trebuchet Projectile",
    "PASTURE_MANGROVE": "Pasture (Mangrove)",
    "PASTURE_D (MANGROVE)": "Pasture (Mangrove)",
    "IHXBOW": "Imperial Skirmisher",
    "INFIL": "Infiltrator",
    "SGULL": "Seagull",
    "LLAMAA": "Llama",
    "HCUAUT": "Cuauhtemoc",
    "RMNK0": "Monk with Relic",
    "VFFOR": "Villager (Female Forager)",
    "HHLION": "Henry the Lion",
    "HCMAR": "Charles Martel",
    "HFORE": "Ornlu the Wolf",
    "HHAHA": "Harun al-Rashid",
    "HGPIZ": "Gonzalo Pizarro",
    "HHRTG": "Harald Hardrada",
    "HBARBA": "Barbarossa",
    "HJODA": "Joan of Arc",
    "HWIWA": "William the Conqueror",
    "OMTBO": "Demolition Ship",
    "HPRITH": "Prithviraj",
    "STRBO": "Bombard Ship",
    "HSFORZA": "Sforza",
    "PETARD": "Petard",
    "HATAULF": "Ataulf",
    "HTHSW": "Two-Handed Swordsman (Hero)",
    "BROWNBEAR": "Brown Bear",
    "CRMSH": "Caravel",
    "UTAXE": "Throwing Axeman (Unique)",
    "UWBRS": "Woad Raider (Unique)",
    "BDGAL": "Boarding Galley",
    "ABGAL": "Boarding Galley",
    "HWBAL": "Ballista",
    "FLDOG": "Flying Dog",
    "UMPCAV": "Siege Tower (Hero)",
    "RFARC": "Raiding Archer",
    "RFSWD": "Raiding Swordsman",
    "RCSWD": "Raiding Cavalry",
    "RCARC": "Raiding Cavalry Archer",
    "GENIT": "Genitour",
    "VFSHE": "Villager (Female Shepherd)",
    "VMSHE": "Villager (Male Shepherd)",
    "GENITX": "Elite Genitour",
    "HJOKT": "Joker",
    "HEROF": "Forester",
    "HMETZ": "Metz",
    "HBERT": "Bertrand",
    "HALEN": "Alencon",
    "PENGUI": "Penguin",
    "HHIRE": "Hireling",
    "HGRAV": "Gravedigger",
    "HRICH": "Richard",
    "HJOSS": "Josselin",
    "HFALS": "Falstaff",
    "HREY": "Rey",
    "HMOT": "Mot",
    "HAOE": "Composite Archer",
    "CNGAU": "Cannon Boat",
    "VBRSK": "Berserk (Light)",
    "UVBRK": "Berserk (Unique Light)",
    "HSUBO": "Subotai",
    "HWOLF": "Hunting Wolf",
    "HFURI": "Furious the Monkey Boy",
    "STORM": "Stormy Dog",
    "HJARL": "Jarl",
    "ORNLU": "Ornlu the Wolf",
    "HGENG": "Genghis Khan",
    "HUNTW": "Hunting Wolf",
    "HGHUS": "Elite Huskarl (Hero)",
    "CROCR": "Crocodile",
    "KOMO": "Komodo Dragon",
    "LIONX": "Lion",
    "ELEPH": "Elephant",
    "RHINO": "Rhinoceros",
    "BOXTU": "Box Turtles",
    "ALFRE": "Alfred the Alpaca",
    "TIGER": "Tiger",
    "EMPLT": "Emperor's Litter",
    "NESSIE": "Nessie",
    "HCANN": "Cannon Galleon",
    "HCANE": "Elite Cannon Galleon",
    "DEMOR": "Demolition Raft",
    "DEMOS": "Demolition Ship",
    "HDEMO": "Heavy Demolition Ship",
    "FIREB": "Fire Galley",
    "FIRES": "Fire Ship",
    "FFIRS": "Fast Fire Ship",
    "TRANS": "Transport Ship",
    "GALLN": "Galleon",
    "WGALL": "War Galley",
    "LGBTV": "Longboat",
    "ELGBT": "Elite Longboat",
    "DROMN": "Dromon",
    "THIRI": "Thirisadai",
    "CARAV": "Caravel",
    "ECARA": "Elite Caravel",
    "TURTL": "Turtle Ship",
    "ETURT": "Elite Turtle Ship",
    "WAGN": "War Wagon",
    "EWAGN": "Elite War Wagon",
    "JUNK": "Junk",
    "SAMUR": "Samurai",
    "ESAMR": "Elite Samurai",
    "MAMLK": "Mameluke",
    "EMAML": "Elite Mameluke",
    "HMGDX": "Mangudai",
    "EMGDX": "Elite Mangudai",
    "TARKAN": "Tarkan",
    "ETARK": "Elite Tarkan",
    "HUSK": "Huskarl",
    "EHUSK": "Elite Huskarl",
    "WAREL": "War Elephant",
    "EWARE": "Elite War Elephant",
    "CONQU": "Conquistador",
    "ECONQ": "Elite Conquistador",
    "JAGAR": "Jaguar Warrior",
    "EJAGA": "Elite Jaguar Warrior",
    "PLUMA": "Plumed Archer",
    "EPLUM": "Elite Plumed Archer",
    "MISSY": "Missionary",
    "EAGSC": "Eagle Scout",
    "EAGWA": "Eagle Warrior",
    "EEAGW": "Elite Eagle Warrior",
    "CAMEL": "Camel Rider",
    "HCAML": "Heavy Camel Rider",
    "ICAML": "Imperial Camel Rider",
    "SCAVY": "Scout Cavalry",
    "LCAVY": "Light Cavalry",
    "HUSSR": "Hussar",
    "WHUSS": "Winged Hussar",
    "CAVLR": "Cavalier",
    "PALAD": "Paladin",
    "CAPRA": "Capped Ram",
    "SGRAM": "Siege Ram",
    "HSCOR": "Heavy Scorpion",
    "ARBAL": "Arbalester",
    "HALBD": "Halberdier",
    "CHAMP": "Champion",
    "STEPLN": "Steppe Lancer",
    "ESTEP": "Elite Steppe Lancer",
    "BATEL": "Battle Elephant",
    "EBATE": "Elite Battle Elephant",
    "ARMEL": "Armored Elephant",
    "SIGEL": "Siege Elephant",
    "GENXB": "Genoese Crossbowman",
    "EGENX": "Elite Genoese Crossbowman",
    "ELPHA": "Elephant Archer",
    "EELPH": "Elite Elephant Archer",
    "KAMAY": "Kamayuk",
    "EKAMA": "Elite Kamayuk",
    "MAGHZ": "Magyar Huszar",
    "EMAGH": "Elite Magyar Huszar",
    "BOYAR": "Boyar",
    "EBOYA": "Elite Boyar",
    "ORGNG": "Organ Gun",
    "EORGN": "Elite Organ Gun",
    "SHOTE": "Shotel Warrior",
    "ESHOT": "Elite Shotel Warrior",
    "GBETO": "Gbeto",
    "EGBET": "Elite Gbeto",
    "CMLAR": "Camel Archer",
    "ECMLA": "Elite Camel Archer",
    "BALLE": "Ballista Elephant",
    "EBALL": "Elite Ballista Elephant",
    "KARAM": "Karambit Warrior",
    "EKARA": "Elite Karambit Warrior",
    "ARAMB": "Arambai",
    "EARAM": "Elite Arambai",
    "RATTA": "Rattan Archer",
    "ERATT": "Elite Rattan Archer",
    "KONNI": "Konnik",
    "EKONN": "Elite Konnik",
    "DKONN": "Konnik (Dismounted)",
    "EDKON": "Elite Konnik (Dismounted)",
    "KESHI": "Keshik",
    "EKESH": "Elite Keshik",
    "KIPCH": "Kipchak",
    "EKIPC": "Elite Kipchak",
    "LEITI": "Leitis",
    "ELEIT": "Elite Leitis",
    "COUST": "Coustillier",
    "ECOUS": "Elite Coustillier",
    "FLEMM": "Flemish Militia",
    "SERJT": "Serjeant",
    "ESERJ": "Elite Serjeant",
    "OBUCH": "Obuch",
    "EOBUC": "Elite Obuch",
    "HUSWA": "Hussite Wagon",
    "EHUSW": "Elite Hussite Wagon",
    "URUMI": "Urumi Swordsman",
    "EURUM": "Elite Urumi Swordsman",
    "RATHA": "Ratha",
    "ERATH": "Elite Ratha",
    "CHAKR": "Chakram Thrower",
    "ECHAK": "Elite Chakram Thrower",
    "SHRIV": "Shrivamsha Rider",
    "ESHRI": "Elite Shrivamsha Rider",
    "CENTM": "Centurion",
    "ECENT": "Elite Centurion",
    "LEGNY": "Legionary",
    "COMPB": "Composite Bowman",
    "ECOMP": "Elite Composite Bowman",
    "WARPR": "Warrior Priest",
    "EWARP": "Elite Warrior Priest",
    "MONAS": "Monaspa",
    "EMONA": "Elite Monaspa",
    "FLEMISHPIKEMAN": "Flemish Pikeman",
    "FLEMISHPIKEMANF": "Flemish Pikeman (Female)",
    "FLEMISHPIKEMAN2": "Flemish Pikeman",
    "CRUSADERKNIGHT": "Crusader Knight",
}


def get_display_name(unit_id, internal_name):
    """Get the display name for a unit, using ID mapping first, then internal name fallback."""
    # First check ID mapping
    if unit_id in UNIT_NAMES:
        return UNIT_NAMES[unit_id]

    # Then check internal name mapping
    internal_upper = internal_name.upper().strip()
    if internal_upper in INTERNAL_NAME_MAP:
        return INTERNAL_NAME_MAP[internal_upper]

    # If name already looks readable (has spaces or mixed case), use it
    if ' ' in internal_name or (internal_name and not internal_name.isupper()):
        return internal_name

    # Otherwise return internal name as-is
    return internal_name


def extract_unit_data(unit):
    """Extract relevant data from a unit object."""
    if unit is None:
        return None

    # Only extract combat units (type 70 = Combatant, type 80 = Building)
    if not hasattr(unit, 'type') or unit.type not in [70, 80]:
        return None

    # Skip units with no HP (usually decorative/dead units)
    if not hasattr(unit, 'hit_points') or unit.hit_points <= 0:
        return None

    # Get the unit class from class_ attribute
    unit_class = getattr(unit, 'class_', -1)

    # Get display name from our mapping, fallback to internal name
    internal_name = getattr(unit, 'name', '').strip()
    display_name = get_display_name(unit.id, internal_name)

    data = {
        "id": unit.id,
        "name": display_name,
        "internal_name": internal_name,
        "type": unit.type,
        "class": unit_class,
        "class_name": UNIT_CLASSES.get(unit_class, "Unknown"),
        "hit_points": int(getattr(unit, 'hit_points', 0)),
        "speed": round(getattr(unit, 'speed', 0), 3),
        "line_of_sight": round(getattr(unit, 'line_of_sight', 0), 1),
        "garrison_capacity": getattr(unit, 'garrison_capacity', 0),
    }

    # Cost from creatable
    if hasattr(unit, 'creatable') and unit.creatable:
        c = unit.creatable
        # Get train time from train_locations
        if hasattr(c, 'train_locations') and c.train_locations:
            data["train_time"] = c.train_locations[0].train_time
        else:
            data["train_time"] = 0

        cost = {}
        if hasattr(c, 'resource_costs'):
            for rc in c.resource_costs:
                if rc.amount > 0:
                    resource_names = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
                    res_name = resource_names.get(rc.type, None)
                    if res_name:
                        cost[res_name] = int(rc.amount)
        data["cost"] = cost

    # Combat stats from type_50
    if hasattr(unit, 'type_50') and unit.type_50:
        t = unit.type_50
        data["range"] = round(getattr(t, 'max_range', 0), 2)
        data["min_range"] = round(getattr(t, 'min_range', 0), 2)
        data["reload_time"] = round(getattr(t, 'reload_time', 0), 3)
        data["accuracy"] = getattr(t, 'accuracy_percent', 100)
        data["blast_width"] = round(getattr(t, 'blast_width', 0), 2)
        data["displayed_attack"] = getattr(t, 'displayed_attack', 0)
        data["displayed_melee_armor"] = getattr(t, 'displayed_melee_armour', 0)
        data["displayed_pierce_armor"] = getattr(unit.creatable, 'displayed_pierce_armour', 0) if hasattr(unit, 'creatable') and unit.creatable else 0

        # Attacks
        attacks = []
        if hasattr(t, 'attacks'):
            for atk in t.attacks:
                attacks.append({
                    "class": atk.class_,
                    "class_name": ARMOR_CLASSES.get(atk.class_, f"Class_{atk.class_}"),
                    "amount": atk.amount
                })
        data["attacks"] = sorted(attacks, key=lambda x: x["amount"], reverse=True)

        # Armors
        armors = []
        if hasattr(t, 'armours'):
            for arm in t.armours:
                armors.append({
                    "class": arm.class_,
                    "class_name": ARMOR_CLASSES.get(arm.class_, f"Class_{arm.class_}"),
                    "amount": arm.amount
                })
        data["armors"] = armors

    return data


def extract_tech_data(tech):
    """Extract relevant data from a technology object."""
    if tech is None:
        return None

    # Skip invalid techs
    name = getattr(tech, 'name', '').strip() if hasattr(tech, 'name') else ''
    if not name or name.startswith('YOURITEMHERE'):
        return None

    data = {
        "id": getattr(tech, 'id', -1) if hasattr(tech, 'id') else -1,
        "name": name,
        "research_time": getattr(tech, 'research_time', 0),
        "civ": getattr(tech, 'civ', -1),  # -1 means all civs, otherwise civ-specific
        "effect_id": getattr(tech, 'effect_id', -1),
        "required_tech": getattr(tech, 'required_tech', -1),
    }

    # Required techs array (up to 6 prerequisite techs)
    if hasattr(tech, 'required_techs'):
        required = [t for t in tech.required_techs if t >= 0]
        if required:
            data["required_techs"] = required

    # Research location (building ID where this tech is researched)
    if hasattr(tech, 'research_location') and tech.research_location >= 0:
        data["research_location"] = tech.research_location

    # Button ID (position in research menu)
    if hasattr(tech, 'button_id') and tech.button_id >= 0:
        data["button_id"] = tech.button_id

    # Full tech mode - if 1, tech is always available once building exists
    if hasattr(tech, 'full_tech_mode'):
        data["full_tech_mode"] = tech.full_tech_mode

    # Cost
    cost = {}
    if hasattr(tech, 'resource_costs'):
        for rc in tech.resource_costs:
            if rc.amount > 0:
                resource_names = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
                res_name = resource_names.get(rc.type, None)
                if res_name:
                    cost[res_name] = int(rc.amount)
    data["cost"] = cost

    return data


def main():
    dat_path = Path(__file__).parent / "empires2_x2_p1.dat"
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"Loading {dat_path}...")
    df = DatFile.parse(dat_path)
    print(f"Loaded successfully!")

    # Extract units from first civ (base units - Gaia has all units)
    print("\nExtracting units...")
    units = []
    if df.civs and len(df.civs) > 0:
        base_civ = df.civs[0]  # Gaia has all base units
        for unit in base_civ.units:
            unit_data = extract_unit_data(unit)
            if unit_data:
                units.append(unit_data)

    # Sort by ID
    units.sort(key=lambda x: x["id"])
    print(f"  Extracted {len(units)} units")

    # Save units
    with open(output_dir / "units.json", "w") as f:
        json.dump(units, f, indent=2)
    print(f"  Saved to output/units.json")

    # Extract technologies
    print("\nExtracting technologies...")
    techs = []
    if hasattr(df, 'techs') and df.techs:
        for i, tech in enumerate(df.techs):
            tech_data = extract_tech_data(tech)
            if tech_data:
                if tech_data["id"] == -1:
                    tech_data["id"] = i
                techs.append(tech_data)

    techs.sort(key=lambda x: x["id"])
    print(f"  Extracted {len(techs)} technologies")

    with open(output_dir / "technologies.json", "w") as f:
        json.dump(techs, f, indent=2)
    print(f"  Saved to output/technologies.json")

    # Extract civilizations
    print("\nExtracting civilizations...")
    civs = []
    for i, civ in enumerate(df.civs):
        if i == 0:
            continue  # Skip Gaia
        if i >= len(CIV_NAMES):
            break

        civ_data = {
            "id": i,
            "name": CIV_NAMES[i] if i < len(CIV_NAMES) else f"Civ_{i}",
        }

        # Count available units
        available_units = []
        for unit in civ.units:
            if unit is not None and hasattr(unit, 'hit_points') and unit.hit_points > 0:
                if hasattr(unit, 'type') and unit.type in [70, 80]:
                    available_units.append(unit.id)
        civ_data["unit_count"] = len(available_units)

        civs.append(civ_data)

    print(f"  Extracted {len(civs)} civilizations")

    with open(output_dir / "civilizations.json", "w") as f:
        json.dump(civs, f, indent=2)
    print(f"  Saved to output/civilizations.json")

    # Save armor classes
    print("\nSaving armor classes...")
    armor_classes = [{"id": k, "name": v} for k, v in sorted(ARMOR_CLASSES.items())]
    with open(output_dir / "armor_classes.json", "w") as f:
        json.dump(armor_classes, f, indent=2)
    print(f"  Saved to output/armor_classes.json")

    # Print sample data
    print("\n" + "="*60)
    print("SAMPLE DATA")
    print("="*60)

    # Find some interesting units by ID
    sample_ids = [4, 38, 77, 93, 125, 280, 550, 1968, 2110, 2398]
    units_by_id = {u["id"]: u for u in units}

    print("\nSample Units:")
    for uid in sample_ids:
        if uid in units_by_id:
            u = units_by_id[uid]
            print(f"\n  {u['name']} (ID: {u['id']}, Class: {u['class_name']}):")
            print(f"    HP: {u['hit_points']}, Speed: {u['speed']}")
            if u.get("cost"):
                cost_str = ", ".join(f"{v} {k}" for k, v in u["cost"].items())
                print(f"    Cost: {cost_str}")
            if u.get("attacks"):
                main_atk = u["attacks"][0] if u["attacks"] else None
                if main_atk:
                    print(f"    Attack: {main_atk['amount']} ({main_atk['class_name']})")
            if u.get("range", 0) > 0:
                print(f"    Range: {u['range']}")
            if u.get("armors"):
                melee = next((a for a in u["armors"] if a["class"] == 4), None)
                pierce = next((a for a in u["armors"] if a["class"] == 3), None)
                if melee or pierce:
                    m_val = melee["amount"] if melee else 0
                    p_val = pierce["amount"] if pierce else 0
                    print(f"    Armor: {m_val}/{p_val} (melee/pierce)")

    print("\n" + "="*60)
    print("EXTRACTION COMPLETE!")
    print("="*60)
    print(f"\nFiles created in {output_dir}/:")
    print("  - units.json       ({} units)".format(len(units)))
    print("  - technologies.json ({} techs)".format(len(techs)))
    print("  - civilizations.json ({} civs)".format(len(civs)))
    print("  - armor_classes.json")


if __name__ == "__main__":
    main()
