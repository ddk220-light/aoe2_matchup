"""
Best units logic: civ power units (pre-computed) + matchup recommendations (on-the-fly).
"""

import json
import os
import sqlite3

from combat_unit_loader import build_combat_dict_from_ref
from unit_lines import TREBUCHET_SLUGS, NAVAL_UNIT_LINES, CANNON_GALLEON_LINE

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")

# Civilizations that do not have access to trebuchets in-game.
CIVS_WITHOUT_TREBUCHET = {"Wu", "Wei", "Shu"}

# Siege line slugs — these only show percentile scores in match-advisor (no sims).
SIEGE_LINE_SLUGS = {"ram", "bombard_cannon", "trebuchet"}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_unit_stats(conn, civ_name, unit_slug, age="Imperial"):
    """Fetch summary stats for a unit from ref_units."""
    rc = conn.cursor()
    rc.execute(
        """SELECT unit_name, final_hp, final_attack, final_melee_armor,
                  final_pierce_armor, final_speed, final_range,
                  final_cost_food, final_cost_wood, final_cost_gold
           FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?""",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        return None, None
    stats = {
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "speed": row["final_speed"],
        "range": row["final_range"] or 0,
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
    }
    return row["unit_name"], stats


# Column definitions: (column_key, line_slugs)
COLUMN_DEFS = {
    "cavalry": ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    "ranged": ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    "infantry": ["militia", "spear", "shock_infantry"],
    "siege": ["ram", "bombard_cannon", "trebuchet", "cannon_galleon"],
}

# Per-line score type to use for ranking
LINE_SCORE_TYPE = {
    "light_cav": "stable_effectiveness",
    "knight": "stable_effectiveness",
    "camel": "stable_effectiveness",
    "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "skirmisher": "ranged_effectiveness",
    "archer": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "militia": "militia_value",
    "spear": "militia_value",
    "shock_infantry": "militia_value",
    "ram": "anti_building_score",
    "bombard_cannon": "anti_building_score",
    "trebuchet": "anti_building_score",
    # cannon_galleon intentionally absent: queried from ref_units directly,
    # not from battle_scores. The special-case in compute_civ_power_units()
    # handles it with generate_cannon_galleon_entry() and skips this dict.
}


def _classify_strength(percentile):
    """Classify a unit's strength tier based on its percentile within the role.

    Percentile is computed from rank within the unit's scoring pool:
      percentile = (total_count - rank) / (total_count - 1) * 100

    Tiers:
        signature:  top 10%  (percentile >= 90)
        strong:     65-90th  (percentile >= 65)
        average:    35-65th  (percentile >= 35)
        weak:       15-35th  (percentile >= 15)
        poor:       bottom 15%
    """
    if percentile >= 90:
        return "signature"
    if percentile >= 65:
        return "strong"
    if percentile >= 35:
        return "average"
    if percentile >= 15:
        return "weak"
    return "poor"


def _compute_line_counts(conn, age_key="imperial"):
    """Compute total unit count per (line_slug, score_type) for percentile calculation.

    Returns dict: {(line_slug, score_type): total_count}
    """
    rc = conn.cursor()
    rc.execute(
        """SELECT line_slug, score_type, COUNT(*) as cnt
           FROM battle_scores
           WHERE LOWER(age) = ?
           GROUP BY line_slug, score_type""",
        [age_key],
    )
    counts = {}
    for row in rc.fetchall():
        counts[(row["line_slug"], row["score_type"])] = row["cnt"]
    return counts


def _compute_percentile(rank, total_count):
    """Compute percentile from rank and total count.

    rank=1 is best (highest percentile), rank=total_count is worst.
    """
    if total_count <= 1:
        return 50.0
    return round((total_count - rank) / (total_count - 1) * 100, 1)


# Techs that meaningfully impact combat — used for "missing techs" tooltip
IMPACTFUL_TECHS = {
    # Blacksmith - melee
    "Forging", "Iron casting", "Blast Furnace",
    "Scale Mail Armor", "Chain Mail Armor", "Plate Mail Armor",
    # Blacksmith - ranged
    "Fletching", "Bodkin Arrow", "Bracer",
    "Padded Archer Armor", "Leather Archer Armor", "Ring Archer Armor",
    # Blacksmith - cavalry
    "Scale Barding Armor", "Chain Barding Armor", "Plate Barding Armor",
    # Stable
    "Bloodlines", "Husbandry",
    # Barracks
    "Squires", "Arson", "Gambesons",
    # Castle
    "Conscription",
    # University
    "Ballistics", "Chemistry", "Siege Engineers",
    # Archery Range
    "Thumb Ring", "Parthian Tactics",
}

# Techs to exclude from "missing" display for specific unit slugs.
# Rams share the siege_ram slug with siege elephants, but rams don't benefit
# from blacksmith attack techs (they deal siege damage) or cavalry techs.
_SLUG_TECH_EXCLUSIONS = {
    "siege_ram": {
        "Forging", "Iron casting", "Blast Furnace",
        "Bloodlines", "Husbandry",
        "Scale Barding Armor", "Chain Barding Armor", "Plate Barding Armor",
    },
}

# Special effect labels for tooltip display
_EFFECT_LABELS = {
    "trample_percent": "Trample {v:.0f}%",  # NOTE: stored as fraction, multiply by 100 before format
    "trample_flat_damage": "Trample +{v:.0f} flat damage",
    "trample_radius": "Trample ({v:.1f} radius)",
    "pass_through_count": "Pass-through x{v:.0f}",
    "ignores_melee_armor": "Ignores melee armor",
    "ignores_pierce_armor": "Ignores pierce armor",
    "bleed_dps": "Bleed {v:.0f} dps",
    "dodge_shield_max": "Dodge shield ({v:.0f} charges)",
    "block_first_melee": "Blocks first melee hit",
    "hp_regen": "+{v:.1f} HP/min regen",
    "charge_attack_melee": "Charge +{v:.0f} melee",
    "attack_bonus_per_kill": "+{v:.0f} attack per kill",
    "bonus_damage_reduction": "{v:.0f}% bonus damage reduction",
    "splash_radius": "Splash damage ({v:.1f} radius)",
    "extra_projectiles": "+{v:.0f} extra projectiles",
    "splash_on_hit_radius": "Splash on hit ({v:.1f} radius)",
    "armor_strip_per_hit": "Strips {v:.0f} armor/hit",
    "pass_through_percent": "Pass-through damage",
    "hp_per_kill": "+{v:.0f} HP per kill",
}


def _build_reference_techs(conn, age="Imperial"):
    """Build a dict: unit_slug -> set of standard tech names available to ANY civ.

    This is the 'full tech tree' reference. For each unit_slug at the given age,
    we collect all standard techs that appear in ref_techs_applied for any civ's
    version of that unit, filtered to IMPACTFUL_TECHS only.
    """
    rc = conn.cursor()
    rc.execute(
        """SELECT ru.unit_slug, rta.tech_name
           FROM ref_units ru
           JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
           WHERE ru.age = ? AND rta.tech_type IN ('standard', 'work_rate')""",
        (age,),
    )
    ref = {}
    for row in rc.fetchall():
        slug = row["unit_slug"]
        tech = row["tech_name"]
        if tech in IMPACTFUL_TECHS:
            ref.setdefault(slug, set()).add(tech)
    return ref


def _get_unit_techs_and_bonuses(conn, civ_name, unit_slug, age="Imperial"):
    """Get missing techs, bonus abilities, and special effects for a unit.

    Returns (standard_techs: list[str], bonus_abilities: list[str], special_effects: list[str])
    """
    rc = conn.cursor()

    # Get ref_unit_id
    rc.execute(
        "SELECT id FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        return [], [], []
    ref_unit_id = row["id"]

    # Get all techs applied to this unit (with tech_type for classification)
    rc.execute(
        "SELECT tech_name, tech_type FROM ref_techs_applied WHERE ref_unit_id=?",
        (ref_unit_id,),
    )
    techs_list = [(r["tech_name"], r["tech_type"]) for r in rc.fetchall()]

    # Get special effects
    rc.execute(
        "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
        (ref_unit_id,),
    )
    effects_list = [(r["property_name"], r["property_value"]) for r in rc.fetchall()]

    # Delegate to shared parser
    standard_techs, bonus_abilities, special_effects = _parse_techs_and_bonuses(techs_list, effects_list)

    return standard_techs, bonus_abilities, special_effects


def _compute_missing_techs(civ_standard_techs, reference_techs_for_slug, slug=""):
    """Compute which impactful techs this civ is missing vs the reference."""
    if not reference_techs_for_slug:
        return []
    missing = reference_techs_for_slug - set(civ_standard_techs)
    # Filter out techs that don't actually affect this unit type
    exclusions = _SLUG_TECH_EXCLUSIONS.get(slug, set())
    if exclusions:
        missing -= exclusions
    return sorted(missing)


def _batch_fetch_civ_tech_data(conn, civ_name, age="Imperial"):
    """Batch-fetch all techs and special effects for a civ in one pass.

    Returns two dicts keyed by unit_slug:
      techs_by_slug: {slug: [(tech_name, tech_type), ...]}
      effects_by_slug: {slug: [(property_name, property_value), ...]}
    """
    rc = conn.cursor()

    # All techs for this civ's units at this age (include tech_type for classification)
    rc.execute(
        """SELECT ru.unit_slug, rta.tech_name, rta.tech_type
           FROM ref_units ru
           JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
           WHERE ru.civ_name = ? AND ru.age = ?""",
        (civ_name, age),
    )
    techs_by_slug = {}
    for row in rc.fetchall():
        techs_by_slug.setdefault(row["unit_slug"], []).append(
            (row["tech_name"], row["tech_type"])
        )

    # All special effects for this civ's units at this age
    rc.execute(
        """SELECT ru.unit_slug, rse.property_name, rse.property_value
           FROM ref_units ru
           JOIN ref_special_effects rse ON rse.ref_unit_id = ru.id
           WHERE ru.civ_name = ? AND ru.age = ?""",
        (civ_name, age),
    )
    effects_by_slug = {}
    for row in rc.fetchall():
        effects_by_slug.setdefault(row["unit_slug"], []).append(
            (row["property_name"], row["property_value"])
        )

    return techs_by_slug, effects_by_slug


def _parse_techs_and_bonuses(techs_list, effects_list):
    """Parse raw tech/effect lists into (standard_techs, bonus_abilities, special_effects).

    Args:
        techs_list: list of (tech_name, tech_type) tuples from ref_techs_applied
        effects_list: list of (property_name, property_value) tuples from ref_special_effects
    """
    # Classify techs by tech_type from the database
    bonus_abilities = []
    standard_tech_names = set()
    for tech_name, tech_type in (techs_list or []):
        if tech_type == "unique_tech":
            bonus_abilities.append(tech_name)
        elif tech_type == "civ_bonus":
            # Strip "C-Bonus, " prefix if present for cleaner display
            display = tech_name[len("C-Bonus, "):] if tech_name.startswith("C-Bonus, ") else tech_name
            bonus_abilities.append(display)
        else:
            # standard, work_rate, etc. — these are standard techs
            standard_tech_names.add(tech_name)

    # Special effects
    special_effects = []
    for pname, pval in (effects_list or []):
        label = _EFFECT_LABELS.get(pname)
        if not label:
            continue
        try:
            v = float(pval)
        except (ValueError, TypeError):
            continue
        if v == 0:
            continue
        # pass_through_count of 1 is default (single target), skip it
        if pname == "pass_through_count" and v <= 1:
            continue
        # trample_percent is stored as fraction (0.25 = 25%)
        if pname == "trample_percent":
            v = v * 100
        if pname in ("ignores_melee_armor", "ignores_pierce_armor",
                      "block_first_melee", "pass_through_percent"):
            special_effects.append(label.split("{")[0].strip())
        else:
            special_effects.append(label.format(v=v))

    # Standard techs sorted for missing_techs comparison
    standard_techs = sorted(standard_tech_names)

    return standard_techs, bonus_abilities, special_effects


def _build_unit_entry(row, civ_name, conn, db_age, reference_techs, techs_by_slug, effects_by_slug, line_counts=None, score_type="", ease_by_slug=None):
    """Build a single unit entry dict with stats, techs, bonuses, and effects."""
    slug = row["unit_slug"]
    unit_name, stats = _fetch_unit_stats(conn, civ_name, slug, db_age)
    standard_techs, bonus_abilities, special_effects = _parse_techs_and_bonuses(
        techs_by_slug.get(slug, []), effects_by_slug.get(slug, [])
    )
    # Only apply tech exclusions for actual rams, not siege elephants sharing the slug
    excl_slug = slug if not (unit_name and "Elephant" in unit_name) else ""
    missing = _compute_missing_techs(standard_techs, reference_techs.get(slug, set()), excl_slug)

    # Compute percentile from rank within the scoring pool
    total_count = 1
    if line_counts and score_type:
        total_count = line_counts.get((row["line_slug"], score_type), 1)
    percentile = _compute_percentile(row["rank"], total_count)
    strength = _classify_strength(percentile)
    speed = stats["speed"] if stats else 0

    ease = None
    if ease_by_slug:
        ease = ease_by_slug.get(slug)

    return {
        "unit_slug": slug,
        "unit_name": unit_name or slug,
        "line_slug": row["line_slug"],
        "score": round(row["score_value"], 1),
        "rank": row["rank"],
        "percentile": percentile,
        "median_delta": round(row["median_delta"], 1),
        "strength": strength,
        "is_signature": strength == "signature",
        "stats": stats,
        "speed": speed,
        "missing_techs": missing,
        "bonus_abilities": bonus_abilities,
        "special_effects": special_effects,
        "ease": ease,
    }


def _strip_siege_entries(power_units):
    """Strip siege unit entries to percentile + strength only.

    Siege units (ram, bombard cannon, trebuchet) don't need full analysis
    in the match-advisor — only the percentile score matters.
    """
    siege_data = power_units.get("siege", {})
    for line_slug in SIEGE_LINE_SLUGS:
        entries = siege_data.get(line_slug)
        if not entries:
            continue
        siege_data[line_slug] = [
            {
                "unit_slug": e["unit_slug"],
                "unit_name": e["unit_name"],
                "line_slug": e["line_slug"],
                "percentile": e["percentile"],
                "strength": e["strength"],
                "is_signature": e["is_signature"],
                "ease": e.get("ease"),
            }
            for e in entries
        ]


def _generate_strategic_description(power_units, strong_columns, weak_areas, strength_profile):
    """Generate a multi-sentence strategic description for a civilization."""
    sentences = []

    # --- Part 1: Primary Playstyle ---
    combat_strong = [c for c in strong_columns if c in ("cavalry", "ranged", "infantry")]

    if len(combat_strong) >= 2:
        col_names = [c.capitalize() for c in combat_strong]
        joined = " and ".join([", ".join(col_names[:-1]), col_names[-1]] if len(col_names) > 2 else col_names)
        sentences.append(
            "This civ is versatile, with strength across " + joined
            + " -- allowing flexible strategies that adapt to any opponent."
        )
    elif len(combat_strong) == 1:
        col = combat_strong[0]
        col_data = power_units.get(col, {})
        best_entry = None
        for entries in col_data.values():
            if entries:
                top = entries[0]
                if best_entry is None or top.get("percentile", 0) > best_entry.get("percentile", 0):
                    best_entry = top
        best_name = best_entry["unit_name"] if best_entry else "their best unit"

        if col == "cavalry":
            sentences.append(
                f"This civ excels at mobile cavalry play -- able to raid,"
                f" flank, and apply pressure across the map with {best_name}."
            )
        elif col == "ranged":
            sentences.append(
                f"This civ has strong ranged options for concentrated pushes,"
                f" with {best_name} providing range advantage and sustained damage output."
            )
        elif col == "infantry":
            sentences.append(
                f"This civ has strong infantry for frontline pressure,"
                f" with {best_name} serving as the backbone of siege-backed pushes."
            )
    else:
        sentences.append(
            "This civ doesn't have a standout late-game powerhouse"
            " -- focus on early aggression and maintaining a lead."
        )

    # --- Part 2: Defensive Assessment ---
    spear_strength = strength_profile.get("spear")
    camel_strength = strength_profile.get("camel")
    skirm_strength = strength_profile.get("skirmisher")

    has_good_spear = spear_strength in ("strong", "signature")
    has_good_camel = camel_strength in ("strong", "signature")
    has_good_skirm = skirm_strength in ("strong", "signature")

    if has_good_spear and has_good_camel:
        sentences.append(
            "Excellent anti-cavalry options from both spears and camels"
            " -- very hard for cavalry-heavy opponents to find an opening."
        )
    elif has_good_camel:
        camel_entries = power_units.get("cavalry", {}).get("camel")
        camel_name = camel_entries[0]["unit_name"] if camel_entries else "camels"
        sentences.append(
            f"Can answer enemy cavalry with mobile {camel_name},"
            " allowing counter-raids and flexible responses."
        )
    elif has_good_spear:
        spear_entries = power_units.get("infantry", {}).get("spear")
        spear_name = spear_entries[0]["unit_name"] if spear_entries else "spearmen"
        sentences.append(
            f"Strong anti-cavalry defense with {spear_name} to hold"
            " positions against cavalry pushes."
        )
    else:
        sentences.append(
            "Anti-cavalry options are limited"
            " -- beware of knight-heavy opponents."
        )

    if has_good_skirm:
        sentences.append(
            "Good skirmishers help shut down archer compositions."
        )
    elif not has_good_spear and not has_good_camel:
        sentences[-1] = (
            "Limited counter options mean this civ must play aggressively"
            " and press its advantage before opponents can mass their army."
        )
    else:
        sentences.append(
            "Vulnerable to massed archers"
            " -- consider aggressive play before ranged compositions develop."
        )

    # --- Part 3: Push Strategy ---
    siege_data = power_units.get("siege", {})
    ram_entries = siege_data.get("ram")
    treb_entries = siege_data.get("trebuchet")
    bbc_entries = siege_data.get("bombard_cannon")

    has_good_ram = ram_entries and ram_entries[0]["strength"] in ("signature", "strong")
    has_good_treb = treb_entries and treb_entries[0]["strength"] in ("signature", "strong")
    has_good_bbc = bbc_entries and bbc_entries[0]["strength"] in ("signature", "strong")
    infantry_strong = "infantry" in strong_columns
    ranged_strong = "ranged" in strong_columns

    if infantry_strong and has_good_ram:
        inf_data = power_units.get("infantry", {})
        best_inf = None
        for entries in inf_data.values():
            if entries:
                top = entries[0]
                if best_inf is None or top.get("percentile", 0) > best_inf.get("percentile", 0):
                    best_inf = top
        inf_name = best_inf["unit_name"] if best_inf else "infantry"
        sentences.append(
            f"An infantry ram push is the signature play -- use {inf_name}"
            " as a meatshield to protect rams pushing into enemy bases."
        )
    elif ranged_strong and has_good_treb:
        rng_data = power_units.get("ranged", {})
        best_rng = None
        for entries in rng_data.values():
            if entries:
                top = entries[0]
                if best_rng is None or top.get("percentile", 0) > best_rng.get("percentile", 0):
                    best_rng = top
        rng_name = best_rng["unit_name"] if best_rng else "ranged units"
        sentences.append(
            f"Pushing behind trebuchets maximizes the ranged advantage"
            f" -- set up trebs and let {rng_name} protect them."
        )
    elif has_good_bbc:
        sentences.append(
            "Bombard Cannons provide long-range siege power"
            " for breaking through fortified positions."
        )
    elif "siege" in strong_columns:
        sentences.append(
            "Solid siege options give flexibility in how to close out games."
        )
    else:
        sentences.append(
            "Siege options are limited -- look to win through"
            " open-field engagements rather than pushing fortifications."
        )

    return " ".join(sentences)


def _batch_fetch_ease_data(conn, civ_name):
    """Load ease-of-creation data for all units of a civ. Returns dict keyed by unit_slug."""
    rc = conn.cursor()
    rc.execute("""
        SELECT unit_slug, ease_score, is_castle_unit, creation_time,
               total_upgrade_cost, needs_castle_ut, movement_speed,
               score_not_castle, score_creation_time, score_upgrade_cost,
               score_no_castle_ut, score_speed
        FROM unit_creation_ease
        WHERE civ_name = ?
    """, [civ_name])
    result = {}
    for row in rc.fetchall():
        result[row["unit_slug"]] = {
            "score": round(row["ease_score"], 4),
            "is_castle_unit": bool(row["is_castle_unit"]),
            "creation_time": row["creation_time"],
            "total_upgrade_cost": row["total_upgrade_cost"],
            "needs_castle_ut": bool(row["needs_castle_ut"]),
            "sub_scores": {
                "not_castle": round(row["score_not_castle"], 4),
                "creation_time": round(row["score_creation_time"], 4),
                "upgrade_cost": round(row["score_upgrade_cost"], 4),
                "no_castle_ut": round(row["score_no_castle_ut"], 4),
                "speed": round(row["score_speed"], 4),
            },
        }
    return result


def _build_naval_unit_entry(row, civ_name, conn, db_age, techs_by_slug=None, effects_by_slug=None):
    """Build an enriched entry dict for a naval unit.

    Returns the same tooltip-relevant fields that renderTooltip() expects,
    but without score/rank/percentile/median_delta (naval units have no battle sim).
    """
    slug = row["unit_slug"]
    stats = {
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "speed": row["final_speed"],
        "range": row["final_range"] or 0,
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
    }

    # Use pre-fetched batch data if provided, otherwise do a targeted DB fetch
    if techs_by_slug is not None and effects_by_slug is not None:
        techs_list = techs_by_slug.get(slug, [])
        effects_list = effects_by_slug.get(slug, [])
        standard_techs, bonus_abilities, special_effects = _parse_techs_and_bonuses(
            techs_list, effects_list
        )
    else:
        standard_techs, bonus_abilities, special_effects = _get_unit_techs_and_bonuses(
            conn, civ_name, slug, db_age
        )

    return {
        "unit_slug": slug,
        "unit_name": row["unit_name"],
        "strength": None,
        "is_signature": False,
        "stats": stats,
        "missing_techs": [],  # Naval units share no standard tech reference pool
        "bonus_abilities": bonus_abilities,
        "special_effects": special_effects,
    }


def generate_naval_column(civ_name, conn, age_key="imperial", techs_by_slug=None, effects_by_slug=None):
    """Return the navy column dict for one civ at one age.

    For each of the 4 naval lines, returns the highest-tier unit the civ can
    build, preferring unique naval units over standard ones. Returns None for a
    slot if the civ cannot build any unit in that line.

    Output structure:
        {"galleon": [enriched_entry] or None,
         "fire":    [...] or None,
         "hulk":    [...] or None,
         "demo":    [...] or None}
    """
    db_age = "Imperial" if age_key == "imperial" else "Castle"
    # Index 1 = imperial slug, index 0 = castle slug in the (castle, imperial) tuple
    unique_idx = 1 if age_key == "imperial" else 0

    rc = conn.cursor()
    col_data = {}

    for line_slug in ("galleon", "fire", "hulk", "demo"):
        line_def = NAVAL_UNIT_LINES[line_slug]
        unique_slugs = line_def["unique_slug_by_civ"].get(civ_name)

        if unique_slugs:
            query_slug = unique_slugs[unique_idx]
        else:
            query_slug = line_slug

        rc.execute(
            "SELECT * FROM ref_units "
            "WHERE civ_name=? AND unit_slug=? AND age=?",
            (civ_name, query_slug, db_age),
        )
        row = rc.fetchone()
        if row:
            col_data[line_slug] = [
                _build_naval_unit_entry(row, civ_name, conn, db_age, techs_by_slug, effects_by_slug)
            ]
        else:
            col_data[line_slug] = None

    return col_data


def generate_cannon_galleon_entry(civ_name, conn, age_key="imperial", techs_by_slug=None, effects_by_slug=None):
    """Return cannon_galleon entry for one civ at one age, or None if unavailable.

    Uses civ-specific unique replacement if defined (Dromon, Lou Chuan,
    Catapult Galleon). Falls back to standard Cannon Galleon / Elite CG.
    """
    db_age = "Imperial" if age_key == "imperial" else "Castle"
    unique_idx = 1 if age_key == "imperial" else 0

    unique_slugs = CANNON_GALLEON_LINE["unique_slug_by_civ"].get(civ_name)
    if unique_slugs:
        query_slug = unique_slugs[unique_idx]
    else:
        query_slug = "cannon_galleon"

    rc = conn.cursor()
    rc.execute(
        "SELECT * FROM ref_units "
        "WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, query_slug, db_age),
    )
    row = rc.fetchone()
    if not row:
        return None
    return _build_naval_unit_entry(row, civ_name, conn, db_age, techs_by_slug, effects_by_slug)


def compute_civ_power_units():
    """Pre-compute power units for all civs. Returns dict keyed by civ_name."""
    conn = _get_db()
    rc = conn.cursor()

    rc.execute("SELECT DISTINCT civ_name FROM battle_scores ORDER BY civ_name")
    all_civs = [row["civ_name"] for row in rc.fetchall()]

    reference_techs_by_age = {
        "imperial": _build_reference_techs(conn, "Imperial"),
        "castle": _build_reference_techs(conn, "Castle"),
    }
    line_counts_by_age = {
        "imperial": _compute_line_counts(conn, "imperial"),
        "castle": _compute_line_counts(conn, "castle"),
    }

    result = {}

    for civ in all_civs:
        civ_data = {"imperial": None, "castle": None}

        for age_key in ["imperial", "castle"]:
            db_age = "Imperial" if age_key == "imperial" else "Castle"
            reference_techs = reference_techs_by_age[age_key]
            line_counts = line_counts_by_age[age_key]
            power_units = {}

            techs_by_slug, effects_by_slug = _batch_fetch_civ_tech_data(conn, civ, db_age)
            ease_by_slug = _batch_fetch_ease_data(conn, civ)

            # Navy column: strength=null, no battle_scores lookup
            power_units["navy"] = generate_naval_column(civ, conn, age_key, techs_by_slug, effects_by_slug)

            for col_key, line_slugs in COLUMN_DEFS.items():
                col_data = {}
                for line_slug in line_slugs:
                    # cannon_galleon: skip battle_scores, query ref_units directly
                    if line_slug == "cannon_galleon":
                        entry = generate_cannon_galleon_entry(civ, conn, age_key, techs_by_slug, effects_by_slug)
                        col_data[line_slug] = [entry] if entry else None
                        continue

                    score_type = LINE_SCORE_TYPE[line_slug]
                    rc.execute(
                        """SELECT unit_slug, line_slug, score_value, rank, median_delta
                            FROM battle_scores
                            WHERE civ_name = ?
                              AND LOWER(age) = ?
                              AND score_type = ?
                              AND line_slug = ?
                            ORDER BY score_value DESC""",
                        [civ, age_key, score_type, line_slug],
                    )
                    rows = rc.fetchall()

                    # Filter trebuchets for civs that don't have them
                    if civ in CIVS_WITHOUT_TREBUCHET:
                        rows = [r for r in rows if r["unit_slug"] not in TREBUCHET_SLUGS]

                    if rows:
                        entries = []
                        for row in rows:
                            entry = _build_unit_entry(
                                row, civ, conn, db_age, reference_techs,
                                techs_by_slug, effects_by_slug, line_counts, score_type,
                                ease_by_slug,
                            )
                            entries.append(entry)
                        col_data[line_slug] = entries
                    else:
                        col_data[line_slug] = None

                power_units[col_key] = col_data

            # Build strength profile (per-line)
            strength_profile = {}
            for col_key, line_slugs in COLUMN_DEFS.items():
                for line_slug in line_slugs:
                    entries = power_units[col_key].get(line_slug)
                    strength_profile[line_slug] = entries[0]["strength"] if entries else None

            # Determine which columns have at least one strong/signature line
            strong_columns = []
            for col_key, line_slugs in COLUMN_DEFS.items():
                if any(strength_profile.get(ls) in ("strong", "signature") for ls in line_slugs):
                    strong_columns.append(col_key)

            # Build strategic summary
            all_line_slugs = [ls for slugs in COLUMN_DEFS.values() for ls in slugs]
            strong_areas = []
            weak_areas = []
            signature_areas = []
            for ls in all_line_slugs:
                s = strength_profile.get(ls)
                if s is None:
                    continue
                if s == "signature":
                    signature_areas.append(ls)
                    strong_areas.append(ls)
                elif s == "strong":
                    strong_areas.append(ls)
                elif s in ("weak", "poor"):
                    weak_areas.append(ls)

            total_strong_cols = len(strong_columns)
            if total_strong_cols >= 2:
                summary_key = "multi_flexible"
            elif total_strong_cols >= 1:
                summary_key = "one_area_strong"
            else:
                summary_key = "none_exceptional"

            primary_strength = strong_columns[0] if strong_columns else None

            strategic_summary = {
                "strong_areas": strong_areas,
                "strong_columns": strong_columns,
                "weak_areas": weak_areas,
                "signature_areas": signature_areas,
                "summary_key": summary_key,
                "primary_strength": primary_strength,
            }

            strategic_description = _generate_strategic_description(
                power_units, strong_columns, weak_areas, strength_profile
            )

            # Strip siege entries to minimal data (percentile only — no sims)
            _strip_siege_entries(power_units)

            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
                "strategic_summary": strategic_summary,
                "strategic_description": strategic_description,
            }

        result[civ] = civ_data

    conn.close()
    return result


def save_civ_power_units():
    """Compute and write civ_power_units.json."""
    data = compute_civ_power_units()
    with open(POWER_UNITS_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {POWER_UNITS_PATH} ({len(data)} civs)")
    return data


def load_civ_power_units():
    """Load pre-computed civ power units. Returns dict or None if file missing."""
    if not os.path.exists(POWER_UNITS_PATH):
        return None
    with open(POWER_UNITS_PATH, "r") as f:
        return json.load(f)


###############################################################################
# Phase B: Matchup Recommendations (on-the-fly with targeted simulation)
###############################################################################

from simulation import prepare_combat_unit, simulate_battle


def _calc_weighted_cost(food, wood, gold):
    """Resource cost with gold weighted higher."""
    cost = 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)
    return int(cost) if cost > 0 else 100


# Counter-role mapping: opponent strength -> what Civ A should query
_STABLE_LINES = ["knight", "light_cav", "camel", "steppe_lancer", "elephant"]
COUNTER_MAP = {
    "cavalry": [
        # (lines_to_search, score_type, description)
        (["spear", "militia"], "anti_cav", "anti-cavalry specialist"),
        (["camel", "knight", "light_cav", "steppe_lancer", "elephant"], "anti_cav", "camel/cavalry counter"),
    ],
    "ranged": [
        (_STABLE_LINES, "general_combat", "cavalry closes distance on ranged"),
        (["archer", "cav_archer", "scorpion", "gunpowder", "skirmisher"], "anti_archer", "anti-archer unit"),
    ],
    "infantry": [
        (["archer", "cav_archer", "scorpion", "gunpowder"], "general_combat", "ranged vs infantry"),
        (_STABLE_LINES, "general_combat", "cavalry vs infantry"),
    ],
    "siege": [
        (_STABLE_LINES, "general_combat", "cavalry snipes siege"),
    ],
}

# Trash pairing logic: gold_unit_line -> preferred trash partner
TRASH_PAIRING = {
    "knight": "skirmisher",        # cavalry + skirm (skirm handles halbs)
    "light_cav": "skirmisher",     # hussar + skirm
    "camel": "skirmisher",         # camel + skirm
    "steppe_lancer": "skirmisher", # steppe lancer + skirm
    "elephant": "skirmisher",      # elephant + skirm
    "archer": "light_cav",         # archers + hussar (hussar tanks & raids)
    "cav_archer": "light_cav",     # cav archers + hussar
    "scorpion": "spear",           # scorpion + halbs (halbs screen from cav)
    "gunpowder": "spear",          # hand cannoneers + halbs
    "militia": "light_cav",        # infantry + hussar
    "spear": "skirmisher",         # spearmen + skirm
    "shock_infantry": "light_cav", # shock infantry + hussar
    "skirmisher": "light_cav",     # skirm + hussar
    "ram": "spear",                # siege + halbs
    "bombard_cannon": "spear",     # bombard + halbs
    "trebuchet": "spear",          # trebuchet + halbs
}


def _load_combat_unit(civ_name, unit_slug, age="Imperial", conn=None):
    """Load a single combat-ready unit from ref_units."""
    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    rc = conn.cursor()
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        if own_conn:
            conn.close()
        return None

    combat_dict = build_combat_dict_from_ref(row)
    if own_conn:
        conn.close()
    cu = prepare_combat_unit(combat_dict)
    cu["cost_food"] = combat_dict["cost_food"]
    cu["cost_wood"] = combat_dict["cost_wood"]
    cu["cost_gold"] = combat_dict["cost_gold"]
    return cu


def _sim_score(unit_a, unit_b):
    """Run two battle scenarios and return composite score (-100..+100) from unit_a's perspective."""
    cost_a = _calc_weighted_cost(unit_a["cost_food"], unit_a["cost_wood"], unit_a["cost_gold"])
    cost_b = _calc_weighted_cost(unit_b["cost_food"], unit_b["cost_wood"], unit_b["cost_gold"])

    # 3K resource battle (cost efficiency)
    w1, _, _, hp1_1, hp2_1 = simulate_battle(
        unit_a, unit_b, 3000, cost1_override=cost_a, cost2_override=cost_b, return_hp=True
    )
    res_score = hp1_1 * 100 if w1 == 1 else (-hp2_1 * 100 if w1 == 2 else 0)

    # 30v30 fixed count (pop efficiency)
    w2, _, _, hp1_2, hp2_2 = simulate_battle(
        unit_a, unit_b, 0, fixed_count=30, return_hp=True
    )
    pop_score = hp1_2 * 100 if w2 == 1 else (-hp2_2 * 100 if w2 == 2 else 0)

    composite = 0.6 * res_score + 0.4 * pop_score
    return round(res_score, 1), round(pop_score, 1), round(composite, 1)


def _generate_reasoning(gold_unit, trash_unit, opponent_unit):
    """Generate human-readable reasoning for a composition recommendation."""
    reasons = []
    g_name = gold_unit.get("unit_name", gold_unit.get("slug", "Unit"))
    o_name = opponent_unit.get("unit_name", opponent_unit.get("slug", "Opponent"))
    t_name = trash_unit.get("unit_name", trash_unit.get("slug", "Support")) if trash_unit else None

    g_speed = gold_unit.get("movement_speed", 0)
    o_speed = opponent_unit.get("movement_speed", 0)
    g_range = gold_unit.get("attack_range", 0)
    o_range = opponent_unit.get("attack_range", 0)

    if g_speed > o_speed and g_range == 0:
        reasons.append(f"{g_name} closes distance on {o_name}")
    if g_range > o_range and g_range > 0:
        reasons.append(f"{g_name} outranges {o_name}")
    if g_range > 0 and o_range == 0:
        reasons.append(f"{g_name} kites melee {o_name}")
    if not reasons:
        reasons.append(f"{g_name} is strong against {o_name}")
    if t_name:
        reasons.append(f"{t_name} covers weakness")
    return "; ".join(reasons)


def get_matchup_recommendations(civ_a, civ_b, age="imperial"):
    """Get recommended units and compositions for civ_a vs civ_b.

    Returns dict with opponent_strengths, recommended_compositions, individual_counters.
    """
    power_data = load_civ_power_units()
    if not power_data:
        return {"error": "civ_power_units.json not found -- run best_units.py first"}

    civ_a_data = power_data.get(civ_a, {}).get(age)
    civ_b_data = power_data.get(civ_b, {}).get(age)
    if not civ_a_data or not civ_b_data:
        return {"error": f"No data for {civ_a} or {civ_b} in {age}"}

    # Step 1: Identify opponent's strengths (strong or signature)
    opponent_strengths = []
    for col_key in ["cavalry", "ranged", "infantry", "siege"]:
        col_data = civ_b_data["power_units"].get(col_key, {})
        # Find the best (highest percentile) entry in this column
        best_entry = None
        for line_slug, entries in col_data.items():
            if entries:
                top = entries[0]
                if top["strength"] in ("strong", "signature"):
                    if best_entry is None or top.get("median_delta", 0) > best_entry.get("median_delta", 0):
                        best_entry = top
        if best_entry:
            opponent_strengths.append({
                "role": col_key,
                "unit_slug": best_entry["unit_slug"],
                "strength": best_entry["strength"],
                "median_delta": best_entry["median_delta"],
            })

    # If opponent has no clear strengths, use their best roles anyway
    if not opponent_strengths:
        best_col = None
        best_entry = None
        for col_key in ["cavalry", "ranged", "infantry"]:
            col_data = civ_b_data["power_units"].get(col_key, {})
            for line_slug, entries in col_data.items():
                if entries:
                    top = entries[0]
                    if best_entry is None or top.get("median_delta", 0) > best_entry.get("median_delta", 0):
                        best_entry = top
                        best_col = col_key
        if best_entry:
            opponent_strengths.append({
                "role": best_col,
                "unit_slug": best_entry["unit_slug"],
                "strength": best_entry["strength"],
                "median_delta": best_entry["median_delta"],
            })

    # Step 2: Find counter candidates from battle_scores
    conn = _get_db()
    rc = conn.cursor()
    db_age = "Imperial" if age == "imperial" else "Castle"

    counter_candidates = []  # list of (unit_slug, line_slug, score, vs_role)
    seen_slugs = set()

    for opp in opponent_strengths:
        counter_defs = COUNTER_MAP.get(opp["role"], [])
        for line_slugs, score_type, desc in counter_defs:
            placeholders = ",".join("?" for _ in line_slugs)
            rc.execute(
                f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                    FROM battle_scores
                    WHERE civ_name = ?
                      AND LOWER(age) = ?
                      AND score_type = ?
                      AND line_slug IN ({placeholders})
                    ORDER BY median_delta DESC
                    LIMIT 3""",
                [civ_a, age, score_type] + line_slugs,
            )
            for row in rc.fetchall():
                slug = row["unit_slug"]
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    counter_candidates.append({
                        "unit_slug": slug,
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "median_delta": round(row["median_delta"], 1),
                        "vs_role": opp["role"],
                        "vs_unit_slug": opp["unit_slug"],
                    })

    conn.close()

    # Step 3: Simulate top candidates vs opponent power units
    individual_counters = []

    for cand in counter_candidates[:6]:  # Cap at 6 to limit sim count
        cu_a = _load_combat_unit(civ_a, cand["unit_slug"], db_age)
        cu_b = _load_combat_unit(civ_b, cand["vs_unit_slug"], db_age)
        if not cu_a or not cu_b:
            continue
        res_score, pop_score, composite = _sim_score(cu_a, cu_b)
        individual_counters.append({
            "unit_slug": cand["unit_slug"],
            "line_slug": cand["line_slug"],
            "vs_unit": cand["vs_unit_slug"],
            "resource_score": res_score,
            "pop_score": pop_score,
            "composite": composite,
        })

    # Sort by composite score descending
    individual_counters.sort(key=lambda x: x["composite"], reverse=True)

    # Step 4: Composition generation
    compositions = []

    for counter in individual_counters[:2]:  # Top 2 gold units
        gold_slug = counter["unit_slug"]
        gold_line = counter["line_slug"]

        # Determine trash partner from preferred line
        trash_line = TRASH_PAIRING.get(gold_line, "light_cav")
        # Try to find the civ's unit in the preferred trash line
        trash_slug = None
        trash_entry = None
        for col_data in civ_a_data["power_units"].values():
            entries = col_data.get(trash_line) if isinstance(col_data, dict) else None
            if entries:
                trash_entry = entries[0]
                break
        if trash_entry:
            trash_slug = trash_entry["unit_slug"]
        else:
            # Fallback: find any zero-gold unit for this civ
            tconn = _get_db()
            trc = tconn.cursor()
            trc.execute(
                """SELECT unit_slug FROM ref_units
                   WHERE civ_name=? AND age=? AND final_cost_gold=0
                   ORDER BY final_hp DESC LIMIT 1""",
                (civ_a, db_age),
            )
            trash_row = trc.fetchone()
            if trash_row:
                trash_slug = trash_row["unit_slug"]
            tconn.close()

        # Load units for reasoning
        gold_cu = _load_combat_unit(civ_a, gold_slug, db_age)
        trash_cu = _load_combat_unit(civ_a, trash_slug, db_age) if trash_slug else None
        opp_cu = _load_combat_unit(civ_b, counter["vs_unit"], db_age)

        reasoning = ""
        if gold_cu and opp_cu:
            reasoning = _generate_reasoning(gold_cu, trash_cu, opp_cu)

        compositions.append({
            "rank": len(compositions) + 1,
            "gold_unit": {
                "unit_slug": gold_slug,
                "line_slug": gold_line,
            },
            "trash_unit": {
                "unit_slug": trash_slug,
            } if trash_slug else None,
            "resource_split": {"gold_pct": 70, "trash_pct": 30},
            "scores": {
                "resource_efficiency": counter["resource_score"],
                "pop_efficiency": counter["pop_score"],
                "composite": counter["composite"],
            },
            "reasoning": reasoning,
        })

    return {
        "civ_a": civ_a,
        "civ_b": civ_b,
        "age": age,
        "opponent_strengths": opponent_strengths,
        "recommended_compositions": compositions,
        "individual_counters": individual_counters,
    }


def get_matchup_sims(civ_left, civ_right, age="imperial"):
    """Run cross-civ simulations for all power units and return win/highlight data.

    For every unit on the left side, determines which right-side units it beats
    (and vice versa) using both 30v30 and 3k-resource battles.  A win requires
    winning BOTH scenarios with >= 10% remaining HP.

    Highlighted wins are "exclusive" -- wins that no other unit in the same
    opponent line_slug can also claim, showing what makes each unit uniquely
    valuable in the matchup.

    Returns dict with 'left', 'right', and 'name_map' keys.
    """
    power_data = load_civ_power_units()
    if not power_data:
        return {"left": {}, "right": {}, "name_map": {}}

    if civ_left not in power_data or civ_right not in power_data:
        return {"error": f"Unknown civilization: {civ_left if civ_left not in power_data else civ_right}"}

    left_data = power_data.get(civ_left, {}).get(age)
    right_data = power_data.get(civ_right, {}).get(age)
    if not left_data or not right_data:
        return {"left": {}, "right": {}, "name_map": {}}

    db_age = "Imperial" if age == "imperial" else "Castle"

    # --- Collect unit entries from power_units ---------------------------------
    def _collect_units(pu_data):
        """Yield (unit_slug, unit_name, line_slug) for every unit in power_units.
        Deduplicates by unit_slug to avoid redundant simulations.
        Skips siege lines (ram/bombard/trebuchet) — percentile only."""
        seen = set()
        for col_key in ("cavalry", "ranged", "infantry"):
            col_data = pu_data.get(col_key, {})
            for line_slug, entries in col_data.items():
                if not entries:
                    continue
                for entry in entries:
                    slug = entry["unit_slug"]
                    if slug not in seen:
                        seen.add(slug)
                        yield slug, entry["unit_name"], entry["line_slug"]

    left_units = list(_collect_units(left_data["power_units"]))
    right_units = list(_collect_units(right_data["power_units"]))

    # --- Load combat units with cache -----------------------------------------
    _cu_cache = {}
    name_map = {}

    def _get_cu(civ_name, slug, uname, conn=None):
        """Load and cache a combat unit; record its display name."""
        key = (civ_name, slug)
        if key not in _cu_cache:
            _cu_cache[key] = _load_combat_unit(civ_name, slug, db_age, conn=conn)
        name_map.setdefault(slug, uname)
        return _cu_cache[key]

    # Pre-load all units using a single shared connection
    preload_conn = _get_db()
    for slug, uname, _ in left_units:
        _get_cu(civ_left, slug, uname, conn=preload_conn)
    for slug, uname, _ in right_units:
        _get_cu(civ_right, slug, uname, conn=preload_conn)
    preload_conn.close()

    # --- Battle result helper --------------------------------------------------
    def _battle_result(cu_a, cu_b, cost_a, cost_b):
        """Return (pop_win, eco_win) booleans from unit A's perspective.

        pop_win: A wins the 30v30 fixed-count battle with >= 10% HP remaining.
        eco_win: A wins the 3k-resource battle with >= 10% HP remaining.
        """
        if cu_a is None or cu_b is None:
            return False, False

        # 30v30 fixed count (pop efficiency)
        w1, _, _, hp1_1, _ = simulate_battle(
            cu_a, cu_b, 0, fixed_count=30, return_hp=True
        )
        pop_win = (w1 == 1 and hp1_1 >= 0.10)

        # 3k resource battle (eco efficiency)
        w2, _, _, hp1_2, _ = simulate_battle(
            cu_a, cu_b, 3000, cost1_override=cost_a, cost2_override=cost_b,
            return_hp=True
        )
        eco_win = (w2 == 1 and hp1_2 >= 0.10)

        return pop_win, eco_win

    # --- Run cross-matchups ---------------------------------------------------
    left_wins = {}       # {left_slug: set(right_slugs beaten)}
    left_pop_wins = {}   # {left_slug: set(right_slugs)} — won v30 only (draw overall)
    left_eco_wins = {}   # {left_slug: set(right_slugs)} — won 3k only (draw overall)
    left_losses = {}     # {left_slug: set(right_slugs)} — lost both to opponent

    right_wins = {}      # {right_slug: set(left_slugs beaten)}
    right_pop_wins = {}
    right_eco_wins = {}
    right_losses = {}

    for l_slug, _, _ in left_units:
        left_wins.setdefault(l_slug, set())
        left_pop_wins.setdefault(l_slug, set())
        left_eco_wins.setdefault(l_slug, set())
        left_losses.setdefault(l_slug, set())
    for r_slug, _, _ in right_units:
        right_wins.setdefault(r_slug, set())
        right_pop_wins.setdefault(r_slug, set())
        right_eco_wins.setdefault(r_slug, set())
        right_losses.setdefault(r_slug, set())

    # Pre-compute weighted costs to avoid redundant calculations in inner loop
    _cost_cache = {}
    for slug, _, _ in left_units:
        cu = _cu_cache.get((civ_left, slug))
        if cu:
            _cost_cache[(civ_left, slug)] = _calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"]
            )
    for slug, _, _ in right_units:
        cu = _cu_cache.get((civ_right, slug))
        if cu:
            _cost_cache[(civ_right, slug)] = _calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"]
            )

    for l_slug, _, _ in left_units:
        cu_l = _cu_cache.get((civ_left, l_slug))
        if cu_l is None:
            continue
        cost_l = _cost_cache[(civ_left, l_slug)]
        for r_slug, _, _ in right_units:
            cu_r = _cu_cache.get((civ_right, r_slug))
            if cu_r is None:
                continue
            cost_r = _cost_cache[(civ_right, r_slug)]

            # Left unit vs right unit
            l_pop, l_eco = _battle_result(cu_l, cu_r, cost_l, cost_r)
            if l_pop and l_eco:
                left_wins[l_slug].add(r_slug)
            elif l_pop:
                left_pop_wins[l_slug].add(r_slug)
            elif l_eco:
                left_eco_wins[l_slug].add(r_slug)

            # Right unit vs left unit
            r_pop, r_eco = _battle_result(cu_r, cu_l, cost_r, cost_l)
            if r_pop and r_eco:
                right_wins[r_slug].add(l_slug)
            elif r_pop:
                right_pop_wins[r_slug].add(l_slug)
            elif r_eco:
                right_eco_wins[r_slug].add(l_slug)

            # Losses: opponent wins both against me
            if r_pop and r_eco:
                left_losses[l_slug].add(r_slug)
            if l_pop and l_eco:
                right_losses[r_slug].add(l_slug)

    # --- Highlight logic (exclusive wins per opponent line) --------------------
    # Group units by line_slug for each side
    left_by_line = {}   # {line_slug: [slug, ...]}
    right_by_line = {}

    for slug, _, line_slug in left_units:
        left_by_line.setdefault(line_slug, []).append(slug)
    for slug, _, line_slug in right_units:
        right_by_line.setdefault(line_slug, []).append(slug)

    def _compute_highlights(my_wins, my_by_line, opp_wins, opp_by_line):
        """Exclusive wins: for each unit, wins that the opponent's same-line
        units cannot achieve against my side.

        E.g. Bohemian Arbalester beats Briton Champion.  Is that exclusive?
        Check whether any Briton archer-line unit also beats Bohemian Champion.
        If not, highlight it.
        """
        # Build reverse lookup: slug -> line_slug for my side
        slug_to_line = {}
        for line_slug, members in my_by_line.items():
            for s in members:
                slug_to_line[s] = line_slug

        highlights = {}
        for slug, wins in my_wins.items():
            my_line = slug_to_line.get(slug)
            if my_line is None:
                highlights[slug] = set(wins)
                continue
            # Get opponent units in the same line
            opp_same_line = opp_by_line.get(my_line, [])
            # Collect what opponents' same-line units beat on MY side
            opp_same_line_wins = set()
            for opp_slug in opp_same_line:
                opp_same_line_wins.update(opp_wins.get(opp_slug, set()))
            # Highlighted = my wins over opponent units that the opponent's
            # same-line units can NOT win against on my side
            highlights[slug] = wins - opp_same_line_wins
        return highlights

    left_highlights = _compute_highlights(
        left_wins, left_by_line, right_wins, right_by_line
    )
    right_highlights = _compute_highlights(
        right_wins, right_by_line, left_wins, left_by_line
    )

    # --- Build response -------------------------------------------------------
    def _build_side(wins_dict, highlights_dict, pop_wins_dict, eco_wins_dict, losses_dict):
        result = {}
        for slug, wins in wins_dict.items():
            result[slug] = {
                "wins": sorted(wins),
                "highlighted": sorted(highlights_dict.get(slug, set())),
                "pop_wins": sorted(pop_wins_dict.get(slug, set())),
                "eco_wins": sorted(eco_wins_dict.get(slug, set())),
                "losses": sorted(losses_dict.get(slug, set())),
            }
        return result

    return {
        "left": _build_side(left_wins, left_highlights, left_pop_wins, left_eco_wins, left_losses),
        "right": _build_side(right_wins, right_highlights, right_pop_wins, right_eco_wins, right_losses),
        "name_map": name_map,
    }


if __name__ == "__main__":
    save_civ_power_units()
