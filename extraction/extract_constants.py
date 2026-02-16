"""Shared constants for data extraction from empires2_x2_p1.dat."""

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
    38: "Skirmishers",
    39: "Mounted Archers",
}

# Civilization names (order matters - matches civ IDs in dat file)
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
    "Turks",  # 10
    "Vikings",
    "Mongols",
    "Celts",
    "Spanish",
    "Aztecs",
    "Mayans",
    "Huns",
    "Koreans",
    "Italians",
    "Hindustanis",  # 20 (formerly Indians, renamed in 2022)
    "Incas",
    "Magyars",
    "Slavs",
    "Portuguese",
    "Ethiopians",
    "Malians",
    "Berbers",
    "Khmer",
    "Malay",
    "Burmese",  # 30
    "Vietnamese",
    "Bulgarians",
    "Tatars",
    "Cumans",
    "Lithuanians",
    "Burgundians",
    "Sicilians",
    "Poles",
    "Bohemians",
    "Dravidians",  # 40
    "Bengalis",
    "Gurjaras",
    "Romans",
    "Armenians",
    "Georgians",  # 45
    # Chronicles DLC - Age of Antiquity (not in ranked play)
    None,  # 46 Achaemenids - skip
    None,  # 47 Athenians - skip
    None,  # 48 Spartans - skip
    # Three Kingdoms DLC (in ranked play)
    "Shu",  # 49
    "Wu",  # 50
    "Wei",  # 51
    "Jurchens",  # 52
    "Khitans",  # 53
    # Chronicles DLC - Alexander (not in ranked play)
    None,  # 54 Macedonians - skip
    None,  # 55 Thracians - skip
    None,  # 56 Puru - skip
]
