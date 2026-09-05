"""Published ranking projection shared by JSON and server-rendered pages."""
from aoe2x.sim.unit_lines import UNIT_LINES, CIV_MISSING_UNITS
from aoe2x.advisor.best_units import _compute_missing_techs as compute_missing_techs, _parse_techs_and_bonuses as parse_techs_and_bonuses

INFANTRY_LINE_SLUGS = {"militia", "spear", "shock_infantry"}
ARCHERY_LINE_SLUGS = {"archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"}
STABLE_LINE_SLUGS = {"knight", "light_cav", "camel", "steppe_lancer", "elephant"}
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon", "cannon_galleon"}
NAVAL_LINE_SLUGS = {"galleon", "fire", "hulk", "naval"}

FINAL_SCORE_TYPE_BY_LINE = {
    "militia": "militia_value",
    "spear": "militia_value",
    "shock_infantry": "militia_value",
    "archer": "ranged_effectiveness",
    "skirmisher": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "knight": "stable_effectiveness",
    "light_cav": "stable_effectiveness",
    "camel": "stable_effectiveness",
    "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "ram": "anti_building_score",
    "trebuchet": "anti_building_score",
    "bombard_cannon": "anti_building_score",
    "cannon_galleon": "anti_building_score",
    "galleon": "naval_effectiveness",
    "fire": "naval_effectiveness",
    "hulk": "naval_effectiveness",
}

_V3_FINAL_SCORE_TYPES = {
    "militia_value",
    "ranged_effectiveness",
    "stable_effectiveness",
}

_V3_BREAKDOWN_YARDSTICKS = (
    ("champion", "Champion", "gc_v3_27_vs_champ"),
    ("paladin", "Paladin", "gc_v3_27_vs_paladin"),
    ("arbalester", "Arbalester", "gc_v3_27_vs_arb"),
    ("halberdier", "Halberdier", "at_v3_27_vs_halb"),
    ("elite_skirmisher", "Elite Skirmisher", "at_v3_27_vs_elite_skirm"),
    ("hussar", "Hussar", "at_v3_27_vs_hussar"),
)

def get_unit_line_data(line_slug, *, get_ref_db, get_rankings_derived_db, current_build):
    """Return comparison data for a unit line across all civs as a plain dict.

    Returns None if line_slug is not a known unit line.
    Used by api_ref_unit_line and server-side rendering tasks.
    """
    if line_slug not in UNIT_LINES:
        return None

    line = UNIT_LINES[line_slug]
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    stat_cols = """id, civ_name, unit_name, unit_slug, unit_type, age,
        final_hp, final_attack, final_melee_armor, final_pierce_armor,
        final_speed, final_range, final_reload_time,
        final_cost_food, final_cost_wood, final_cost_gold,
        upgrade_cost_food, upgrade_cost_wood, upgrade_cost_gold,
        applied_bonuses_summary"""

    # Determine which sub-lines to fetch (virtual "infantry" or single line)
    sub_lines = line.get("sub_lines", [line_slug])

    result = {
        "line_name": line["name"],
        "building": line["building"],
        "imperial": [],
    }

    # Load role scores from DB (keyed by "age|civ_name|unit_slug")
    _db_role_scores = {}
    scored_lines = (
        INFANTRY_LINE_SLUGS
        | ARCHERY_LINE_SLUGS
        | STABLE_LINE_SLUGS
        | SIEGE_LINE_SLUGS
        | NAVAL_LINE_SLUGS
    )
    _score_line_slugs = [s for s in sub_lines if s in scored_lines]
    if _score_line_slugs:
        derived_conn = get_rankings_derived_db()
        placeholders = ",".join("?" for _ in _score_line_slugs)
        _bld = current_build()
        if _bld:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value, rank, median_delta "
                f"FROM battle_scores WHERE line_slug IN ({placeholders}) "
                f"AND build_number = ?",
                _score_line_slugs + [_bld],
            ).fetchall()
        else:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value, rank, median_delta "
                f"FROM battle_scores WHERE line_slug IN ({placeholders})",
                _score_line_slugs,
            ).fetchall()
        derived_conn.close()

        for bs_row in derived_rows:
            uk = f"{bs_row['age'].lower()}|{bs_row['civ_name']}|{bs_row['unit_slug']}"
            _db_role_scores.setdefault(uk, {})[bs_row["score_type"]] = {
                "score_value": bs_row["score_value"],
                "rank": bs_row["rank"],
                "median_delta": bs_row["median_delta"],
            }

    def _attach_scores(entry, age_key, sub_slug):
        """Attach role scores from derived_data.db (battle_scores table).

        Scores are only loaded for the infantry/archery/stable/siege/naval
        sub-lines, so other lines simply get no score keys — rankings.js
        treats missing keys as "no score" (same as the old -999 sentinels).
        """
        unit_key = f"{age_key}|{entry['civ_name']}|{entry['unit_slug']}"
        score_rows = _db_role_scores.get(unit_key, {})
        for score_type, score_row in score_rows.items():
            entry[score_type] = score_row["score_value"]

        final_type = FINAL_SCORE_TYPE_BY_LINE.get(sub_slug)
        final_row = score_rows.get(final_type) if final_type else None
        if final_row:
            entry["ranking_score_type"] = final_type
            entry["ranking_score"] = final_row["score_value"]
            entry["ranking_rank"] = final_row["rank"]
            entry["ranking_median_delta"] = final_row["median_delta"]

        if final_type in _V3_FINAL_SCORE_TYPES:
            roles = {
                label: entry.get(score_type)
                for label, score_type in (
                    ("GC", "general_combat"),
                    ("AC", "anti_cav"),
                    ("AT", "anti_trash"),
                    ("AA", "anti_archer"),
                )
                if entry.get(score_type) is not None
            }
            yardsticks = [
                {"key": key, "label": label, "score": entry.get(score_type)}
                for key, label, score_type in _V3_BREAKDOWN_YARDSTICKS
                if entry.get(score_type) is not None
            ]
            if roles or yardsticks:
                entry["ranking_breakdown"] = {
                    "roles": roles,
                    "yardsticks": yardsticks,
                }

    _ABILITY_LABELS = {
        "ignores_melee_armor": "Ignores melee armor",
        "ignores_pierce_armor": "Ignores pierce armor",
        "trample_percent": "Trample {v:.0%}",
        "trample_flat_damage": "Trample +{v:.0f} dmg",
        "trample_radius": None,
        "bonus_damage_reduction": "{v:.0%} bonus dmg reduction",
        "damage_reflect_percent": "Reflects {v:.0%} melee dmg",
        "hp_regen": "{v:.0f} HP/min regen",
        "attack_bonus_per_kill": "+{v:.0f} atk per kill",
        "pop_space": "{v} pop space",
        "armor_strip_per_hit": "Strips {v:.0f} armor/hit",
        "bleed_dps": "Bleed {v:.0f} dps",
        "bleed_duration": None,
        "pass_through_percent": "Pass-through dmg",
        "pass_through_count": None,
        "extra_proj_scatter": "Projectiles scatter",
        "miss_damage_percent": "Missed shots deal {v:.0%} dmg",
        "hp_per_kill": "+{v:.0f} HP per kill",
        "hp_per_kill_max": None,
        "charge_attack_melee": "Charge +{v:.0f} melee",
        "charge_recharge_time": None,
        "block_first_melee": "Blocks first melee hit",
        "hp_transform_threshold": "Transforms at {v:.0%} HP",
        "dodge_shield_max": "Dodge shield ({v:.0f} charges)",
        "dodge_shield_recharge": None,
    }

    # Build reference tech sets per unit_slug across all civs in scope.
    # For each slug, the set of standard techs that ≥2 civs have applied.
    # Used for missing-techs computation — a civ "missing" a tech is one in
    # this reference set that they don't have applied.
    #
    # The ≥2 civ filter drops civ-locked work_rate / standard techs that only
    # one civ ever has (e.g. Goths' "Gothic Perfusion" has tech_type='work_rate'
    # and only Goths get it — without this filter every other civ's militia
    # line would falsely show "Missing: Gothic Perfusion").
    _per_slug_civ_techs: dict[tuple[str, str], list[tuple[str, str]]] = {}
    rc.execute("""
        SELECT ru.civ_name, ru.unit_slug, rta.tech_name, rta.tech_type
          FROM ref_units ru
          JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
    """)
    for r in rc.fetchall():
        _per_slug_civ_techs.setdefault((r["civ_name"], r["unit_slug"]), []).append(
            (r["tech_name"], r["tech_type"])
        )
    # Count, per (slug, tech), how many civs apply it.
    _slug_tech_civ_counts: dict[tuple[str, str], int] = {}
    for (civ, slug), techs in _per_slug_civ_techs.items():
        standard_techs, _bonus, _eff = parse_techs_and_bonuses(techs, [])
        for tech in standard_techs:
            _slug_tech_civ_counts[(slug, tech)] = _slug_tech_civ_counts.get((slug, tech), 0) + 1
    # Reference set per slug = standard techs applied by ≥2 civs.
    _reference_techs_by_slug: dict[str, set[str]] = {}
    for (slug, tech), count in _slug_tech_civ_counts.items():
        if count >= 2:
            _reference_techs_by_slug.setdefault(slug, set()).add(tech)

    def _attach_special(entry):
        rc.execute(
            "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
            (entry["id"],),
        )
        parts = []
        for pname, pval in rc.fetchall():
            label = _ABILITY_LABELS.get(pname)
            if label is None:
                continue
            try:
                v = float(pval)
            except (ValueError, TypeError):
                continue
            if v == 0:
                continue
            parts.append(label.format(v=v))
        entry["special_abilities"] = "; ".join(parts) if parts else ""

        # Missing techs: this civ's standard techs vs the per-slug reference.
        civ_techs = _per_slug_civ_techs.get((entry["civ_name"], entry["unit_slug"]), [])
        standard_techs, bonus_abilities, _eff = parse_techs_and_bonuses(civ_techs, [])
        reference = _reference_techs_by_slug.get(entry["unit_slug"], set())
        entry["missing_techs"] = compute_missing_techs(standard_techs, reference, entry["unit_slug"])

        # Civ bonuses + unique techs as a separate display field. These are stat
        # boosts (e.g. "+15 HP" via "Skirm Spear +5 HP × 3 ages") and named effects
        # (e.g. "Garland Wars", "Druzhina") that don't fit ref_special_effects but
        # belong in the Special cell as the third info line.
        # De-dupe and drop blatantly internal-looking names (containing 'attr_').
        seen = set()
        cleaned = []
        for name in bonus_abilities:
            if "attr_" in name:
                continue
            if name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        entry["civ_bonus_techs"] = cleaned

    # Fetch units for each sub-line
    for sub_slug in sub_lines:
        sub_line = UNIT_LINES[sub_slug]

        # Standard units (Imperial only)
        for age_key, slug_key, slugs_key, db_age in [
            ("imperial", "imperial_slug", "imperial_slugs", "Imperial"),
        ]:
            slugs = sub_line.get(
                slugs_key, [sub_line.get(slug_key)] if sub_line.get(slug_key) else []
            )
            for slug in slugs:
                rc.execute(
                    f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                    (slug, db_age),
                )
                for row in rc.fetchall():
                    if (row["civ_name"], slug) in CIV_MISSING_UNITS:
                        continue
                    entry = dict(row)
                    entry["is_unique"] = False
                    entry["line_slug"] = sub_slug
                    _attach_scores(entry, age_key, sub_slug)
                    _attach_special(entry)
                    result[age_key].append(entry)

        # Extra standard units
        for extra_slug in sub_line.get("extra_imperial_slugs", []):
            rc.execute(
                f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                (extra_slug, "Imperial"),
            )
            for row in rc.fetchall():
                if (row["civ_name"], extra_slug) in CIV_MISSING_UNITS:
                    continue
                entry = dict(row)
                entry["is_unique"] = False
                entry["line_slug"] = sub_slug
                _attach_scores(entry, "imperial", sub_slug)
                _attach_special(entry)
                result["imperial"].append(entry)

        # Unique units (value may be a single (castle, imperial) tuple or a list
        # of such tuples — only the imperial slug is served)
        for civ_name, entries in sub_line.get("unique_units", {}).items():
            entries = entries if isinstance(entries, list) else [entries]
            for _castle_uu, imperial_uu in entries:
                for uu_slug, age_key, db_age in [
                    (imperial_uu, "imperial", "Imperial"),
                ]:
                    if not uu_slug:
                        continue
                    rc.execute(
                        f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND civ_name=? AND age=?",
                        (uu_slug, civ_name, db_age),
                    )
                    row = rc.fetchone()
                    if row:
                        entry = dict(row)
                        entry["is_unique"] = True
                        entry["line_slug"] = sub_slug
                        _attach_scores(entry, age_key, sub_slug)
                        _attach_special(entry)
                        result[age_key].append(entry)

    # Exclude Elephant Archers from stable (ranged, already in archery rankings)
    if line_slug == "stable":
        result["imperial"] = [u for u in result["imperial"] if "ele_archer" not in u["unit_slug"]]

    ref_conn.close()
    return result
