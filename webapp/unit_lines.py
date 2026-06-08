"""
Single source of truth for the UNIT_LINES configuration dict.

This module was created to eliminate the drift between app.py (21 entries, including
4 aggregate sub_lines keys) and compute_battle_scores.py (17 entries, unit lines only).
A programmatic diff confirmed the 17 individual unit-line entries were byte-identical
between both files; the 4-entry difference was the sub_lines aggregate keys
(archery, infantry, stable, siege) that existed only in app.py to power the
/api/ref/unit-line/<slug> rankings UI.

The unified dict has all 21 keys. compute_battle_scores.py iteration sites guard
against the aggregate entries with:
    if not std_slug and not multi_slugs and not has_unique: continue
so no behavior change and no DB regeneration is needed.

TODO: The supplementary _LINE_SLUGS sets (INFANTRY_LINE_SLUGS, ARCHERY_LINE_SLUGS,
STABLE_LINE_SLUGS, SIEGE_LINE_SLUGS, HIDDEN_LINE_SLUGS) have semantic drift between
app.py and compute_battle_scores.py — specifically, mangonel is in SIEGE_LINE_SLUGS
in app.py but in HIDDEN_LINE_SLUGS in compute_battle_scores.py. Both sets are left
in their respective files for now; they should be reconciled and extracted here in
a future task to avoid unintended behavior changes to role-scoring logic.
"""

# Civ-specific unit exclusions: (civ_name, unit_slug) pairs that should be
# filtered out of rankings and battle-score computation. The extraction
# pipeline emits these rows regardless of tech-tree availability, so we gate
# them declaratively here based on the authoritative Fandom tech trees.
CIV_MISSING_UNITS = {
    # Incas / Mapuche / Muisca / Tupi: entire Militia line disabled
    # (|Militia=0 in Barracks Tech Tree template). Champi Warrior is their
    # only Barracks "infantry line" unit.
    ("Incas", "swordsmen"), ("Incas", "champion"),
    ("Mapuche", "swordsmen"), ("Mapuche", "champion"),
    ("Muisca", "swordsmen"), ("Muisca", "champion"),
    ("Tupi", "swordsmen"), ("Tupi", "champion"),
    # Muisca additionally lacks Halberdier (|Halberdier=0); Pikeman only.
    ("Muisca", "halberdier"),
    # Mapuche lacks Arbalester (and Bracer) — archer line caps at Crossbowman.
    # Source: SiegeEngineers data.json civs.Mapuche.Unit (Arbalester id 492 absent).
    ("Mapuche", "arbalester"),
    # All four Andean/Amazonian civs lack Imperial Skirmisher (cap at Elite Skirm).
    # Source: SiegeEngineers data.json civs.{Civ}.Unit (Imperial Skirm id 1155 absent).
    ("Incas", "imp_elite_skirm"),
    ("Mapuche", "imp_elite_skirm"),
    ("Muisca", "imp_elite_skirm"),
    ("Tupi", "imp_elite_skirm"),
}


UNIT_LINES = {
    "militia": {
        "name": "Militia Line",
        "building": "Barracks",
        "castle_slug": "swordsmen",
        "imperial_slug": "champion",
        "unique_units": {
            "Goths": ("huskarl_goths", "elite_huskarl_goths"),
            "Celts": ("woad_raider_celts", "elite_woad_raider_celts"),
            "Vikings": ("berserk_vikings", "elite_berserk_vikings"),
            "Japanese": ("samurai_japanese", "elite_samurai_japanese"),
            "Teutons": ("teutonic_knight_teutons", "elite_teutonic_knight_teutons"),
            "Aztecs": ("jaguar_warrior_aztecs", "elite_jaguar_warrior_aztecs"),
            "Italians": (None, "condottiero"),
            "Ethiopians": (
                "shotel_warrior_ethiopians",
                "elite_shotel_warrior_ethiopians",
            ),
            "Burgundians": (None, "flemish_militia"),
            "Sicilians": ("serjeant_sicilians", "elite_serjeant_sicilians"),
            "Poles": ("obuch_poles", "elite_obuch_poles"),
            "Dravidians": (
                "urumi_swordsman_dravidians",
                "elite_urumi_swordsman_dravidians",
            ),
            "Hindustanis": ("ghulam_hindustanis", "elite_ghulam_hindustanis"),
            "Malay": ("karambit_warrior_malay", "elite_karambit_warrior_malay"),
            "Armenians": ("warrior_priest_armenians", "warrior_priest_armenians"),
            "Khitans": ("liao_dao_khitans", "elite_liao_dao_khitans"),
            "Shu": (
                "white_feather_guard_shu",
                "elite_white_feather_guard_shu",
            ),
            "Incas": [
                ("kamayuk_incas", "elite_kamayuk_incas"),
                ("champi_warrior", "elite_champi_warrior"),
            ],
            "Muisca": ("champi_warrior", "elite_champi_warrior"),
            "Mapuche": ("champi_warrior", "elite_champi_warrior"),
            "Tupi": [
                ("ibirapema_warrior_tupi", "elite_ibirapema_warrior_tupi"),
                ("champi_warrior", "elite_champi_warrior"),
            ],
        },
    },
    "spear": {
        "name": "Spear Line",
        "building": "Barracks",
        "castle_slug": "pikeman",
        "imperial_slug": "halberdier",
        "unique_units": {},
    },
    "shock_infantry": {
        # Units in the Eagle Warriors armor class (id=29 in armor_classes).
        # This is the in-game "shock infantry" armor class — units with
        # "+X vs Eagle Warriors" bonus damage hit everything here.
        "name": "Shock Infantry",
        "building": "Barracks",
        "castle_slug": "fire_lancer",
        "imperial_slug": "elite_fire_lancer",
        "unique_units": {
            "Aztecs": ("eagle_warrior", "elite_eagle"),
            "Mayans": ("eagle_warrior", "elite_eagle"),
            "Wu": ("jian_swordsman_wu", "jian_swordsman_wu"),
            "Muisca": ("temple_guard_muisca", "elite_temple_guard_muisca"),
        },
    },
    "archer": {
        "name": "Archers & Gunpowder",
        "building": "Archery Range",
        "castle_slug": "crossbow",
        "imperial_slug": "arbalester",
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Vietnamese": (
                "rattan_archer_vietnamese",
                "elite_rattan_archer_vietnamese",
            ),
            "Armenians": (
                "composite_bowman_armenians",
                "elite_composite_bowman_armenians",
            ),
            "Wu": ("fire_archer_wu", "elite_fire_archer_wu"),
            "Muisca": ("guecha_warrior_muisca", "elite_guecha_warrior_muisca"),
            "Tupi": ("blackwood_archer_tupi", "elite_blackwood_archer_tupi"),
        },
    },
    "skirmisher": {
        "name": "Skirmisher Line",
        "building": "Archery Range",
        "castle_slug": "elite_skirm",
        "imperial_slug": "imp_elite_skirm",
        "unique_units": {
            "Berbers": ("genitour", "elite_genitour"),
        },
    },
    "cav_archer": {
        "name": "Cavalry Archer Line",
        "building": "Archery Range",
        "castle_slug": "cav_archer",
        "imperial_slug": "heavy_cav_archer",
        "extra_castle_slugs": ["elephant_archer"],
        "extra_imperial_slugs": ["elite_ele_archer"],
        "unique_units": {
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Berbers": ("camel_archer_berbers", "elite_camel_archer_berbers"),
            "Burmese": ("arambai_burmese", "elite_arambai_burmese"),
            "Cumans": ("kipchak_cumans", "elite_kipchak_cumans"),
            "Bengalis": (
                "ratha_(ranged)_bengalis",
                "elite_ratha_(ranged)_bengalis",
            ),
            "Wei": ("xianbei_raider_wei", "xianbei_raider_wei"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
            "Mapuche": ("bolas_rider_mapuche", "elite_bolas_rider_mapuche"),
        },
    },
    "knight": {
        "name": "Knight Line",
        "building": "Stable",
        "castle_slug": "knight",
        "imperial_slug": "paladin",
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
            "Bulgarians": ("konnik_bulgarians", "elite_konnik_bulgarians"),
            "Lithuanians": ("leitis_lithuanians", "elite_leitis_lithuanians"),
            "Tatars": ("keshik_tatars", "elite_keshik_tatars"),
            "Burgundians": ("coustillier_burgundians", "elite_coustillier_burgundians"),
            "Bengalis": (
                "ratha_(melee)_bengalis",
                "elite_ratha_(melee)_bengalis",
            ),
            "Gurjaras": (
                "shrivamsha_rider_gurjaras",
                "elite_shrivamsha_rider_gurjaras",
            ),
            "Romans": ("centurion_romans", "elite_centurion_romans"),
            "Georgians": ("monaspa_georgians", "elite_monaspa_georgians"),
            "Jurchens": ("iron_pagoda_jurchens", "elite_iron_pagoda_jurchens"),
            "Wei": ("tiger_cavalry_wei", "elite_tiger_cavalry_wei"),
            "Mapuche": ("kona_mapuche", "elite_kona_mapuche"),
        },
    },
    "light_cav": {
        "name": "Light Cavalry Line",
        "building": "Stable",
        "castle_slug": "light_cav",
        "imperial_slug": "hussar",
        "unique_units": {
            "Magyars": ("magyar_huszar_magyars", "elite_magyar_huszar_magyars"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
        },
    },
    "camel": {
        "name": "Camel Line",
        "building": "Stable",
        "castle_slug": "camel",
        "imperial_slug": "heavy_camel",
        "unique_units": {},
    },
    "steppe_lancer": {
        "name": "Steppe Lancer",
        "building": "Stable",
        "castle_slug": "steppe_lancer",
        "imperial_slug": "elite_steppe",
        "unique_units": {},
    },
    "elephant": {
        "name": "Elephant Line",
        "building": "Stable",
        "castle_slug": "elephant",
        "imperial_slug": "elite_elephant",
        # elephant_archer / elite_ele_archer also live in cav_archer (Archery
        # Range). They appear here too so callers that walk the elephant line's
        # extra slugs (e.g. legacy compute_battle_scores aggregations) still
        # find them. derive_unit_rankings.build_slug_to_line uses first-write-
        # wins, so the slug→line mapping resolves to cav_archer (which is
        # defined first in this dict) and the units get scored as ranged.
        "extra_castle_slugs": ["elephant_archer"],
        "extra_imperial_slugs": ["elite_ele_archer"],
        "unique_units": {
            "Persians": ("war_elephant_persians", "elite_war_elephant_persians"),
        },
    },
    "ram": {
        "name": "Ram Line",
        "building": "Siege Workshop",
        "castle_slug": "ram",
        "imperial_slug": "siege_ram",
        "unique_units": {},
    },
    "mangonel": {
        "name": "Mangonel Line",
        "building": "Siege Workshop",
        "castle_slug": "mangonel",
        "imperial_slug": "siege_onager",
        "unique_units": {},
    },
    "gunpowder": {
        "name": "Gunpowder",
        "building": "Archery Range",
        "castle_slug": None,
        "imperial_slug": "hand_cannoneer",
        "unique_units": {
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Portuguese": ("organ_gun_portuguese", "elite_organ_gun_portuguese"),
            "Jurchens": ("grenadier_jurchens", "grenadier_jurchens"),
            # Slinger is a regional Archery Range unit shared by all four
            # South American civs. No upgrade exists — imp_slinger here is
            # a synthetic Imperial-age tech-applied entry (same unit, finals
            # diff via age techs).
            "Incas":   ("slinger", "imp_slinger"),
            "Mapuche": ("slinger", "imp_slinger"),
            "Muisca":  ("slinger", "imp_slinger"),
            "Tupi":    ("slinger", "imp_slinger"),
            "Bohemians": ("hussite_wagon_bohemians", "elite_hussite_wagon_bohemians"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Malians": ("gbeto_malians", "elite_gbeto_malians"),
            "Gurjaras": (
                "chakram_thrower_gurjaras",
                "elite_chakram_thrower_gurjaras",
            ),
        },
    },
    "scorpion": {
        "name": "Scorpion Line",
        "building": "Siege Workshop",
        "castle_slug": "scorpion",
        "imperial_slug": "heavy_scorpion",
        "unique_units": {
            "Khmer": ("ballista_elephant_khmer", "elite_ballista_elephant_khmer"),
            "Shu": ("war_chariot_shu", "war_chariot_shu"),
            "Khitans": ("mounted_trebuchet_khitans", "mounted_trebuchet_khitans"),
        },
    },
    "trebuchet": {
        "name": "Trebuchet",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "trebuchet",
        "unique_units": {},
    },
    "bombard_cannon": {
        "name": "Bombard Cannon",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "bombard_cannon",
        "extra_imperial_slugs": ["traction_trebuchet"],
        "unique_units": {},
    },
    "galleon": {
        "name": "Galleon Line",
        "building": "Dock",
        "castle_slug": "galleon",
        "imperial_slug": "galleon",
        # Berbers/Xebec intentionally excluded from rankings (no confirmed icon/data).
        # See NAVAL_UNIT_LINES for the civ-overview mapping which still references it.
        # NOTE: the Wu Lou Chuan is NOT a warship — its stat profile is a Cannon
        # Galleon (230 building damage, range 13 / min-range 3) and Wu has no
        # regular Cannon Galleon, so it's Wu's cannon-galleon replacement. It is
        # mapped in the cannon_galleon line below (matching Chinese/Jurchens/Shu/
        # Wei), NOT here — otherwise it would be (mis)scored in the naval ranking
        # and excluded from Anti-Building Effectiveness.
        "unique_units": {
            "Vikings": ("longboat_vikings", "elite_longboat_vikings"),
            "Portuguese": ("caravel_portuguese", "elite_caravel_portuguese"),
            "Dravidians": ("thirisadai_dravidians", "thirisadai_dravidians"),
        },
    },
    "fire": {
        "name": "Fire Ship Line",
        "building": "Dock",
        "castle_slug": "fire",
        "imperial_slug": "fire",
        "unique_units": {},
    },
    "hulk": {
        "name": "Hulk Line",
        "building": "Dock",
        "castle_slug": "hulk",
        "imperial_slug": "hulk",
        "unique_units": {
            "Koreans": ("turtle_ship_koreans", "elite_turtle_ship_koreans"),
        },
    },
    "cannon_galleon": {
        "name": "Cannon Galleon",
        "building": "Dock",
        "castle_slug": None,
        "imperial_slug": "cannon_galleon",
        "unique_units": {
            # Dromon: Byzantines + Romans/Armenians/Goths/Huns (tech 886 enabled)
            "Byzantines": (None, "dromon_byzantines"),
            "Romans":     (None, "dromon_romans"),
            "Armenians":  (None, "dromon_armenians"),
            "Goths":      (None, "dromon_goths"),
            "Huns":       (None, "dromon_huns"),
            # Catapult Galleon: South American civs (Mapuche, Tupi, Muisca)
            "Mapuche":    (None, "catapult_galleon_mapuche"),
            "Tupi":       (None, "catapult_galleon_tupi"),
            "Muisca":     (None, "catapult_galleon_muisca"),
            # Lou Chuan: Chinese, Jurchens + Three Kingdoms civs (tech 1034 enabled)
            "Chinese":    (None, "lou_chuan_chinese"),
            "Jurchens":   (None, "lou_chuan_jurchens"),
            "Wu":         (None, "lou_chuan_wu"),
            "Shu":        (None, "lou_chuan_shu"),
            "Wei":        (None, "lou_chuan_wei"),
        },
    },
    "archery": {
        "name": "Ranged Effectiveness",
        "building": "Archery Range",
        "sub_lines": ["archer", "cav_archer", "skirmisher", "scorpion", "gunpowder"],
    },
    "infantry": {
        "name": "Infantry Effectiveness",
        "building": "Barracks",
        "sub_lines": ["militia", "spear", "shock_infantry"],
    },
    "stable": {
        "name": "Stable Units",
        "building": "Stable",
        "sub_lines": ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
    },
    "siege": {
        "name": "Anti-Building Effectiveness",
        "building": "Siege Workshop",
        "sub_lines": ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"],
    },
    "naval": {
        "name": "Naval Effectiveness",
        "building": "Dock",
        "sub_lines": ["galleon", "fire", "hulk"],
    },
}

# Trebuchet unit slugs — excluded from matchup sim results (siege-only, no direct combat).
TREBUCHET_SLUGS = {"trebuchet"}

# =============================================================================
# NAVAL UNIT LINES
# =============================================================================
# Maps line_slug → unique_slug_by_civ → (castle_slug, imperial_slug).
# The castle_slug is the ref_units slug to query for Castle-age display,
# imperial_slug for Imperial-age display. When a civ has a unique, its unique
# slug is used instead of the standard line slug.
NAVAL_UNIT_LINES = {
    "galleon": {
        "name": "Galleon Line",
        "unique_slug_by_civ": {
            "Vikings":    ("longboat_vikings",    "elite_longboat_vikings"),
            "Portuguese": ("caravel_portuguese",  "elite_caravel_portuguese"),
            "Dravidians": ("thirisadai_dravidians","thirisadai_dravidians"),  # no elite
            "Berbers":    ("xebec_berbers",       "xebec_berbers"),          # no elite
        },
    },
    "fire": {
        "name": "Fire Ship Line",
        "unique_slug_by_civ": {},
    },
    "hulk": {
        "name": "Hulk Line",
        "unique_slug_by_civ": {
            "Koreans": ("turtle_ship_koreans", "elite_turtle_ship_koreans"),
        },
    },
    "demo": {
        "name": "Demo Ship Line",
        "unique_slug_by_civ": {},
    },
}

# Cannon Galleon is part of the Siege column, not Navy.
# Unique replacements: Dromon (Byzantines), Lou Chuan (Wu/Shu/Wei),
# Catapult Galleon (Mapuche).
CANNON_GALLEON_LINE = {
    "name": "Cannon Galleon",
    "unique_slug_by_civ": {
        # Dromon (1795): Byzantines, Romans, Armenians, Goths, Huns
        "Byzantines": ("dromon_byzantines",         "dromon_byzantines"),
        "Romans":     ("dromon_romans",             "dromon_romans"),
        "Armenians":  ("dromon_armenians",          "dromon_armenians"),
        "Goths":      ("dromon_goths",              "dromon_goths"),
        "Huns":       ("dromon_huns",               "dromon_huns"),
        # Catapult Galleon (2633): South American civs
        "Mapuche":    ("catapult_galleon_mapuche",  "catapult_galleon_mapuche"),
        "Tupi":       ("catapult_galleon_tupi",     "catapult_galleon_tupi"),
        "Muisca":     ("catapult_galleon_muisca",   "catapult_galleon_muisca"),
        # Lou Chuan (1948): Chinese, Jurchens, Wu, Shu, Wei
        "Chinese":    ("lou_chuan_chinese",         "lou_chuan_chinese"),
        "Jurchens":   ("lou_chuan_jurchens",        "lou_chuan_jurchens"),
        "Wu":         ("lou_chuan_wu",              "lou_chuan_wu"),
        "Shu":        ("lou_chuan_shu",             "lou_chuan_shu"),
        "Wei":        ("lou_chuan_wei",             "lou_chuan_wei"),
    },
}
