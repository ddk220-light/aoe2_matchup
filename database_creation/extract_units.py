"""Extract unit data from dat file into units.json."""

from .extract_constants import ARMOR_CLASSES

# Unit class names (combat-relevant classes only)
UNIT_CLASSES = {
    0: "Archer",
    3: "Building",
    6: "Infantry",
    12: "Cavalry",
    13: "Siege Weapon",
    17: "Healer",
    18: "Monk",
    23: "Conquistador",
    24: "War Elephant",
    25: "Hero",
    26: "Elephant Archer",
    35: "Petard",
    36: "Cavalry Archer",
    44: "Hand Cannoneer",
    45: "Two-Handed Swordsman",
    46: "Pikeman",
    47: "Scout",
    50: "Spearman",
    51: "Packed Unit",
    52: "Tower",
    54: "Unpacked Siege Unit",
    55: "Ballista",
    56: "Raider",
    57: "Cavalry Raider",
    59: "King",
    60: "Miscellaneous",
}

# Unit IDs to extract and their display names
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
    473: "Two-Handed Swordsman",
    567: "Two-Handed Swordsman",
    751: "Eagle Scout",
    753: "Eagle Warrior",
    752: "Elite Eagle Warrior",
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
    1813: "Savar",
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
    1744: "Armored Elephant",
    280: "Mangonel",
    550: "Onager",
    588: "Siege Onager",
    279: "Scorpion",
    281: "Heavy Scorpion",
    542: "Heavy Scorpion",
    36: "Bombard Cannon",
    1660: "Houfnice",
    42: "Trebuchet",
    331: "Trebuchet (Packed)",
    188: "Siege Tower",
    1749: "Warrior Priest",
    1751: "Elite Warrior Priest",
    # ===== Elephant Units (Regional) =====
    1132: "Battle Elephant",
    1134: "Elite Battle Elephant",
    873: "Elephant Archer",
    875: "Elite Elephant Archer",
    # ===== Unique Units - Britons =====
    8: "Longbowman",
    545: "Elite Longbowman",
    # ===== Unique Units - Franks =====
    531: "Elite Throwing Axeman",
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
    239: "War Elephant",
    422: "War Elephant",
    555: "Elite War Elephant",
    558: "Elite War Elephant",
    # ===== Unique Units - Saracens =====
    282: "Mameluke",
    556: "Elite Mameluke",
    832: "Mameluke",
    831: "Elite Mameluke",
    # ===== Unique Units - Turks =====
    46: "Janissary",
    557: "Elite Janissary",
    # ===== Unique Units - Vikings =====
    692: "Berserk",
    694: "Elite Berserk",
    866: "Berserk",
    775: "Elite Berserk",
    94: "Berserk",
    # ===== Unique Units - Mongols =====
    11: "Mangudai",
    561: "Elite Mangudai",
    # ===== Unique Units - Celts =====
    232: "Woad Raider",
    534: "Elite Woad Raider",
    548: "Elite Woad Raider",
    # ===== Unique Units - Spanish =====
    771: "Conquistador",
    773: "Elite Conquistador",
    # ===== Unique Units - Aztecs =====
    725: "Jaguar Warrior",
    726: "Elite Jaguar Warrior",
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
    868: "Elite Genoese Crossbowman",
    1004: "Genoese Crossbowman",
    1006: "Elite Genoese Crossbowman",
    866: "Condottiero",
    # ===== Unique Units - Indians/Hindustanis =====
    1747: "Ghulam",
    1749: "Elite Ghulam",
    # ===== Unique Units - Incas =====
    879: "Kamayuk",
    881: "Elite Kamayuk",
    # ===== Unique Units - Ethiopians =====
    1016: "Shotel Warrior",
    1018: "Elite Shotel Warrior",
    # ===== Unique Units - Magyars =====
    869: "Magyar Huszar",
    871: "Elite Magyar Huszar",
    1007: "Magyar Huszar",
    1009: "Elite Magyar Huszar",
    # ===== Unique Units - Slavs =====
    876: "Boyar",
    878: "Elite Boyar",
    # ===== Unique Units - Portuguese =====
    1120: "Organ Gun",
    1122: "Elite Organ Gun",
    # ===== Unique Units - Malians =====
    1013: "Gbeto",
    1015: "Elite Gbeto",
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
    1129: "Rattan Archer",
    1131: "Elite Rattan Archer",
    1234: "Rattan Archer",
    1236: "Elite Rattan Archer",
    # ===== Unique Units - Bulgarians =====
    1263: "Konnik",
    1265: "Elite Konnik",
    1253: "Elite Konnik (Dismounted)",
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
    1659: "Elite Serjeant",
    # ===== Unique Units - Poles =====
    1655: "Obuch",
    1657: "Elite Obuch",
    1703: "Elite Obuch",
    # ===== Unique Units - Bohemians =====
    1596: "Hussite Wagon",
    1598: "Elite Hussite Wagon",
    1706: "Elite Hussite Wagon",
    # ===== Unique Units - Dravidians =====
    1699: "Urumi Swordsman",
    1701: "Elite Urumi Swordsman",
    # ===== Unique Units - Bengalis =====
    1709: "Ratha",
    1707: "Elite Ratha",
    1738: "Ratha (Melee)",
    1740: "Elite Ratha (Melee)",
    1759: "Ratha (Ranged)",
    1761: "Elite Ratha (Ranged)",
    # ===== Unique Units - Gurjaras =====
    1705: "Chakram Thrower",
    1704: "Elite Chakram Thrower",
    1743: "Elite Chakram Thrower",
    1714: "Shrivamsha Rider",
    1713: "Elite Shrivamsha Rider",
    1753: "Elite Shrivamsha Rider",
    # ===== Unique Units - Romans =====
    1737: "Centurion",
    1739: "Elite Centurion",
    1741: "Legionary",
    1790: "Centurion",
    1792: "Elite Centurion",
    # ===== Unique Units - Armenians =====
    1746: "Composite Bowman",
    1748: "Elite Composite Bowman",
    1800: "Composite Bowman",
    1802: "Elite Composite Bowman",
    1811: "Warrior Priest",
    # ===== Unique Units - Georgians =====
    1752: "Monaspa",
    1754: "Elite Monaspa",
    1803: "Monaspa",
    1805: "Elite Monaspa",
    # ===== Three Kingdoms DLC Units =====
    1901: "Fire Lancer",
    1903: "Elite Fire Lancer",
    1908: "Iron Pagoda",
    1910: "Elite Iron Pagoda",
    1911: "Grenadier",
    1920: "Liao Dao",
    1922: "Elite Liao Dao",
    1923: "Siege Camel",
    1944: "Hei-Kuang Cavalry",
    1946: "Heavy Hei-Kuang Cavalry",
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
    2150: "War Chariot",
    2151: "Elite War Chariot",
}


def get_display_name(unit_id):
    """Get the display name for a unit by ID."""
    return UNIT_NAMES.get(unit_id)


def extract_unit_data(unit, all_units=None):
    """Extract relevant data from a genieutils unit object.

    Args:
        unit: The genieutils unit object.
        all_units: Dict of id->unit for all units (including type 60 projectiles),
                   used to look up secondary projectile attack data.
    Returns:
        Dict of unit data, or None if unit should be skipped.
    """
    if unit is None:
        return None

    # Only extract units in our list
    display_name = get_display_name(unit.id)
    if display_name is None:
        return None

    unit_class = getattr(unit, "class_", -1)
    internal_name = getattr(unit, "name", "").strip()

    data = {
        "id": unit.id,
        "name": display_name,
        "internal_name": internal_name,
        "type": unit.type,
        "class": unit_class,
        "class_name": UNIT_CLASSES.get(unit_class, "Unknown"),
        "hit_points": int(getattr(unit, "hit_points", 0)),
        "speed": round(getattr(unit, "speed", 0), 3),
        "line_of_sight": round(getattr(unit, "line_of_sight", 0), 1),
        "garrison_capacity": getattr(unit, "garrison_capacity", 0),
    }

    # Cost from creatable
    if hasattr(unit, "creatable") and unit.creatable:
        c = unit.creatable
        if hasattr(c, "train_locations") and c.train_locations:
            data["train_time"] = c.train_locations[0].train_time
        else:
            data["train_time"] = 0

        cost = {}
        if hasattr(c, "resource_costs"):
            for rc in c.resource_costs:
                if rc.amount > 0:
                    resource_names = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
                    res_name = resource_names.get(rc.type, None)
                    if res_name:
                        cost[res_name] = int(rc.amount)
        data["cost"] = cost

        # Projectile counts (extra projectiles for Chu Ko Nu, etc.)
        data["total_projectiles"] = round(getattr(c, "total_projectiles", 1), 1)
        data["max_total_projectiles"] = getattr(c, "max_total_projectiles", 1)
        data["secondary_projectile_unit"] = getattr(c, "secondary_projectile_unit", -1)

        # Charge attack (Coustillier, Urumi, Shrivamsha dodge, etc.)
        max_charge = getattr(c, "max_charge", 0)
        recharge_rate = getattr(c, "recharge_rate", 0)
        charge_event = getattr(c, "charge_event", 0)
        charge_type = getattr(c, "charge_type", 0)
        if max_charge > 0:
            data["charge_attack"] = round(max_charge, 1)
            data["charge_recharge_rate"] = round(recharge_rate, 4)
            data["charge_event"] = charge_event
            data["charge_type"] = charge_type

        # Charge projectile unit (Fire Lancer, Fire Archer, Xianbei Raider, etc.)
        charge_proj_id = getattr(c, "charge_projectile_unit", -1)
        if charge_proj_id and charge_proj_id > 0:
            data["charge_projectile_unit"] = charge_proj_id

        # HP regeneration rate (attribute 109, stored as rear_attack_modifier in dat)
        hp_regen = getattr(c, "rear_attack_modifier", 0)
        if hp_regen and hp_regen > 0:
            data["hp_regen"] = round(hp_regen, 1)

    # Combat stats from type_50
    if hasattr(unit, "type_50") and unit.type_50:
        t = unit.type_50
        data["range"] = round(getattr(t, "max_range", 0), 2)
        data["min_range"] = round(getattr(t, "min_range", 0), 2)
        data["reload_time"] = round(getattr(t, "reload_time", 0), 3)
        frame_delay = getattr(t, "frame_delay", 0)
        data["attack_delay"] = round(frame_delay / 60.0, 3)
        data["accuracy"] = getattr(t, "accuracy_percent", 100)
        data["blast_width"] = round(getattr(t, "blast_width", 0), 2)
        data["blast_attack_level"] = getattr(t, "blast_attack_level", 0)
        data["blast_damage"] = round(getattr(t, "blast_damage", 0), 4)
        data["bonus_damage_resistance"] = round(
            getattr(t, "bonus_damage_resistance", 0), 4
        )
        data["projectile_unit_id"] = getattr(t, "projectile_unit_id", -1)
        data["displayed_attack"] = getattr(t, "displayed_attack", 0)
        data["displayed_melee_armor"] = getattr(t, "displayed_melee_armour", 0)
        data["displayed_pierce_armor"] = (
            getattr(unit.creatable, "displayed_pierce_armour", 0)
            if hasattr(unit, "creatable") and unit.creatable
            else 0
        )

        # Attacks
        attacks = []
        if hasattr(t, "attacks"):
            for atk in t.attacks:
                attacks.append(
                    {
                        "class": atk.class_,
                        "class_name": ARMOR_CLASSES.get(
                            atk.class_, f"Class_{atk.class_}"
                        ),
                        "amount": atk.amount,
                    }
                )
        data["attacks"] = sorted(attacks, key=lambda x: x["amount"], reverse=True)

        # Armors
        armors = []
        if hasattr(t, "armours"):
            for arm in t.armours:
                armors.append(
                    {
                        "class": arm.class_,
                        "class_name": ARMOR_CLASSES.get(
                            arm.class_, f"Class_{arm.class_}"
                        ),
                        "amount": arm.amount,
                    }
                )
        data["armors"] = armors

    # Extract projectile speed from the projectile unit (type 60)
    proj_id = data.get("projectile_unit_id", -1)
    if all_units and proj_id and proj_id > 0 and proj_id in all_units:
        proj_unit = all_units[proj_id]
        proj_speed = getattr(proj_unit, "speed", 0)
        if proj_speed and proj_speed > 0:
            data["projectile_speed"] = round(proj_speed, 2)

    # Extract secondary projectile attack data (for multi-projectile units)
    sec_proj_id = data.get("secondary_projectile_unit", -1)
    if all_units and sec_proj_id and sec_proj_id > 0 and sec_proj_id in all_units:
        proj_unit = all_units[sec_proj_id]
        if hasattr(proj_unit, "type_50") and proj_unit.type_50:
            proj_t = proj_unit.type_50
            proj_attacks = []
            if hasattr(proj_t, "attacks"):
                for atk in proj_t.attacks:
                    if atk.amount != 0:
                        proj_attacks.append(
                            {
                                "class": atk.class_,
                                "class_name": ARMOR_CLASSES.get(
                                    atk.class_, f"Class_{atk.class_}"
                                ),
                                "amount": atk.amount,
                            }
                        )
            if proj_attacks:
                data["secondary_projectile_attacks"] = sorted(
                    proj_attacks, key=lambda x: x["amount"], reverse=True
                )

    # Extract charge projectile attack data (Fire Lancer, Fire Archer, etc.)
    charge_proj_id = data.get("charge_projectile_unit", -1)
    if (
        all_units
        and charge_proj_id
        and charge_proj_id > 0
        and charge_proj_id in all_units
    ):
        proj_unit = all_units[charge_proj_id]
        proj_speed = getattr(proj_unit, "speed", 0)
        if proj_speed and proj_speed > 0:
            data["charge_projectile_speed"] = round(proj_speed, 2)
        if hasattr(proj_unit, "type_50") and proj_unit.type_50:
            proj_t = proj_unit.type_50
            proj_attacks = []
            if hasattr(proj_t, "attacks"):
                for atk in proj_t.attacks:
                    proj_attacks.append(
                        {
                            "class": atk.class_,
                            "class_name": ARMOR_CLASSES.get(
                                atk.class_, f"Class_{atk.class_}"
                            ),
                            "amount": atk.amount,
                        }
                    )
            if proj_attacks:
                data["charge_projectile_attacks"] = sorted(
                    proj_attacks, key=lambda x: x["amount"], reverse=True
                )

    return data


def extract_units(df):
    """Extract all combat units from the dat file.

    Args:
        df: Parsed DatFile object.
    Returns:
        List of unit data dicts, sorted by ID.
    """
    units = []
    if df.civs and len(df.civs) > 0:
        base_civ = df.civs[0]  # Gaia has all base units
        # Build lookup of ALL units (including type 60 projectiles)
        all_units_by_id = {}
        for unit in base_civ.units:
            if unit is not None and hasattr(unit, "id"):
                all_units_by_id[unit.id] = unit
        for unit in base_civ.units:
            unit_data = extract_unit_data(unit, all_units=all_units_by_id)
            if unit_data:
                units.append(unit_data)

    units.sort(key=lambda x: x["id"])
    return units
