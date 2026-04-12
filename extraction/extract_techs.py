"""Extract technology data and compute tech ages from dat file."""

from .extract_constants import RESOURCE_TYPE_NAMES


def extract_tech_data(tech):
    """Extract relevant data from a genieutils technology object.

    Returns:
        Dict of tech data, or None if tech should be skipped.
    """
    if tech is None:
        return None

    name = getattr(tech, "name", "").strip() if hasattr(tech, "name") else ""
    if not name or name.startswith("YOURITEMHERE"):
        return None

    data = {
        "id": getattr(tech, "id", -1) if hasattr(tech, "id") else -1,
        "name": name,
        "research_time": getattr(tech, "research_time", 0),
        "civ": getattr(tech, "civ", -1),
        "effect_id": getattr(tech, "effect_id", -1),
        "required_tech": getattr(tech, "required_tech", -1),
    }

    # Required techs array (up to 6 prerequisite techs)
    if hasattr(tech, "required_techs"):
        required = [t for t in tech.required_techs if t >= 0]
        if required:
            data["required_techs"] = required

    # Research location (building ID where this tech is researched)
    if hasattr(tech, "research_locations") and tech.research_locations:
        data["research_location"] = tech.research_locations[0].location_id

    # Button ID (position in research menu)
    if hasattr(tech, "button_id") and tech.button_id >= 0:
        data["button_id"] = tech.button_id

    # Full tech mode
    if hasattr(tech, "full_tech_mode"):
        data["full_tech_mode"] = tech.full_tech_mode

    # Cost
    cost = {}
    if hasattr(tech, "resource_costs"):
        for rc in tech.resource_costs:
            if rc.amount > 0:
                res_name = RESOURCE_TYPE_NAMES.get(rc.type, None)
                if res_name:
                    cost[res_name] = int(rc.amount)
    data["cost"] = cost

    return data


def extract_technologies(df):
    """Extract all technologies from the dat file.

    Args:
        df: Parsed DatFile object.
    Returns:
        List of tech data dicts, sorted by ID.
    """
    techs = []
    if hasattr(df, "techs") and df.techs:
        for i, tech in enumerate(df.techs):
            tech_data = extract_tech_data(tech)
            if tech_data:
                if tech_data["id"] == -1:
                    tech_data["id"] = i
                techs.append(tech_data)

    techs.sort(key=lambda x: x["id"])
    return techs


def _determine_tech_age(tech_data, techs_by_id):
    """Determine the age a tech becomes available.

    Age values: 1=Dark, 2=Feudal, 3=Castle, 4=Imperial
    """
    FEUDAL_AGE = 101
    CASTLE_AGE = 102
    IMPERIAL_AGE = 103

    required_techs = tech_data.get("required_techs", [])

    if IMPERIAL_AGE in required_techs:
        return 4
    if CASTLE_AGE in required_techs:
        return 3
    if FEUDAL_AGE in required_techs:
        return 2

    max_prereq_age = 1
    for prereq_id in required_techs:
        if prereq_id in techs_by_id:
            prereq_data = techs_by_id[prereq_id]
            prereq_age = prereq_data.get("_computed_age", 1)
            max_prereq_age = max(max_prereq_age, prereq_age)

    return max_prereq_age


def generate_tech_ages(techs):
    """Generate tech age mapping for standard techs.

    Args:
        techs: List of tech data dicts (from extract_technologies).
    Returns:
        Dict with "_comment" and "techs" keys, matching tech_ages.json format.
    """
    techs_by_id = {t["id"]: t for t in techs}

    # Building ID to name mapping
    building_names = {
        103: "Blacksmith",
        101: "Stable",
        86: "Stable",
        153: "Stable",
        87: "Archery Range",
        10: "Archery Range",
        12: "Barracks",
        49: "Siege Workshop",
        209: "University",
        82: "Castle",
        104: "Monastery",
        84: "Market",
        109: "Town Center",
    }

    # Standard tech patterns - techs that are universally researchable
    standard_tech_patterns = [
        "forging",
        "iron casting",
        "blast furnace",
        "scale barding",
        "chain barding",
        "plate barding",
        "scale mail",
        "chain mail",
        "plate mail",
        "fletching",
        "bodkin",
        "bracer",
        "padded archer",
        "leather archer",
        "ring archer",
        "bloodlines",
        "husbandry",
        "thumb ring",
        "parthian",
        "squires",
        "arson",
        "supplies",
        "gambesons",
        "cavalier",
        "paladin",
        "arbalest",
        "elite skirmisher",
        "heavy cavalry archer",
        "long swordsman",
        "two-handed",
        "champion",
        "pikeman",
        "halberdier",
        "eagle warrior",
        "elite eagle",
        "light cavalry",
        "hussar",
        "heavy camel",
        "imperial camel",
        "elite battle elephant",
        "war galley",
        "galleon",
        "heavy demo",
        "heavy scorpion",
        "capped ram",
        "siege ram",
        "onager",
        "siege onager",
    ]

    tech_ages = {
        "_comment": "Tech ID to age mapping. Age: 1=Dark, 2=Feudal, 3=Castle, 4=Imperial. Auto-generated from dat file.",
        "techs": {},
    }

    # Multiple passes to resolve prerequisite chains
    for _ in range(4):
        for tech in techs:
            age = _determine_tech_age(tech, techs_by_id)
            techs_by_id[tech["id"]]["_computed_age"] = age

    # Filter to standard techs
    for tech in techs:
        tech_name = tech.get("name", "").lower()

        is_standard = any(pattern in tech_name for pattern in standard_tech_patterns)
        if not is_standard:
            continue

        # Skip civ-specific techs
        if tech.get("civ", -1) >= 0:
            continue

        tech_id = str(tech["id"])
        age = tech.get("_computed_age", 1)
        research_loc = tech.get("research_location", -1)
        building = building_names.get(research_loc, "Unknown")

        tech_ages["techs"][tech_id] = {
            "name": tech["name"],
            "age": age,
            "building": building,
        }

    return tech_ages
