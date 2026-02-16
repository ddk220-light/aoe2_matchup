# AoE2 `.dat` Extraction Restart Guide

This document is for rebuilding data generation from scratch while keeping the current webapp behavior.

## 1. Source of truth and outputs

Use `extraction/ and analysis/empires2_x2_p1.dat` as source of truth.

Target intermediate outputs (JSON):
- `extraction/ and analysis/extracted_data/units.json`
- `extraction/ and analysis/extracted_data/technologies.json`
- `extraction/ and analysis/extracted_data/tech_ages.json`
- `extraction/ and analysis/extracted_data/civilizations.json`
- `extraction/ and analysis/extracted_data/armor_classes.json`
- `extraction/ and analysis/extracted_data/effects.json`
- `extraction/ and analysis/extracted_data/civ_tech_trees.json`
- `extraction/ and analysis/extracted_data/tech_effects.json`

Target DB outputs:
- `webapp/aoe2_reference.db` (audit + stat chain + projectile/special effects)
- `webapp/aoe2_units.db` (main webapp/simulation DB)

## 2. ID systems you must preserve

There are three separate ID namespaces that must stay consistent:

1. Game Unit ID (`units.json[].id`)
- Raw AoE2 engine ID (ex: `38` Knight, `1923` Mounted Trebuchet).

2. Technology ID (`technologies.json[].id`)
- Used for availability techs, upgrades, civ bonus commands.

3. Webapp Unit Slug (`ref_units.unit_slug`, `units.slug`)
- Canonical identifier used by frontend and API routes.
- Standard line examples: `halberdier`, `arbalester`, `siege_onager`.
- Unique unit slug format: `<unit_base_slug>_<civ_lowercase>` (ex: `longbowman_britons`, `elite_huskarl_goths`).

If you break slug generation, `/api/ref/combat-unit/<civ>/<unit_slug>` and simulator selection will break.

## 3. Unit name and code nuances (important)

Do not trust one naming field.

- `name` in the dat can be scrambled/misleading for some units.
- Preserve `internal_name` and raw numeric ID in extracted JSON for debugging.
- Prefer ID-first matching for deterministic extraction.
- Maintain a controlled unit inclusion list (`UNIT_NAMES` style) for stable coverage.

Known pitfalls already encoded in config/comments:
- Some base IDs look surprising by name but are correct by stats/effects.
- Same logical line can appear under multiple game IDs across expansions.
- Some unique units have no elite tech; they must still appear in Imperial context.

## 4. What to extract for units (minimum contract)

From creatable/type50/projectile data, you need:

Core stats:
- `hit_points`, `speed`, `line_of_sight`, `train_time`, costs
- `displayed_attack`, `displayed_melee_armor`, `displayed_pierce_armor`
- `range`, `min_range`, `reload_time`, `attack_delay`, `accuracy`
- `attacks[]`, `armors[]`

Projectile/mechanic raw fields:
- `projectile_unit_id` -> resolve `projectile_speed` from projectile unit (often type 60)
- `total_projectiles`, `max_total_projectiles`
- `secondary_projectile_unit` -> resolve `secondary_projectile_attacks`
- `charge_projectile_unit` -> resolve `charge_projectile_speed` and attacks
- `blast_width`, `blast_attack_level`, `blast_damage`
- `bonus_damage_resistance`
- charge-related: `charge_type`, `charge_attack`, `charge_recharge_rate`
- HP regen source: `rear_attack_modifier` (not corpse-decay fields)

## 5. How unit availability should be determined

Availability is not inferred from one place only.

Use all of:
- Configured unit line definitions with `availability_tech`
- Civ tech tree disables (`effect cmd type 102/103`)
- Tech civ restriction (`tech.civ != -1` means civ-locked)
- Upgrade path techs gated by age and disabled techs
- Civ-specific replacement chains (`civ_upgrades`)
- Alternate unit path logic (ex: civs that replace ram line)

Practical rule:
A unit is available for civ C at age A iff
- Base availability tech is not disabled for C
- Availability tech civ restriction matches C (or is global)
- Highest valid upgrade tech at/under age A is available
- If main line blocked and alternate line exists + valid, switch to alternate

## 6. Tech/effect extraction nuances

### Command types you must handle for stat application
- `0` set attribute
- `4` add attribute
- `5` multiply attribute
- `2` enable/disable unit
- `3` upgrade unit
- `101` tech cost set/override
- `102` disable tech
- `103` disable unit

### Armor/attack delta encoding
For `ADD_ATTRIBUTE` on attack/armor, value packs class and amount into one number. Decode exactly (class from high byte, amount signed low byte behavior). This affects correct bonus class math.

### Tech age determination
Use:
- direct age tech prereqs (101/102/103 = Feudal/Castle/Imperial)
- recursive prerequisite age propagation
- guard against cycles

## 7. Projectile and special-mechanic derivation rules

These are currently derived from raw unit fields and must remain deterministic:

- `min_range` -> `min_attack_range`
- projectile unit speed -> `projectile_speed`
- siege splash detection:
  - class 13 + blast_width>0 + blast_damage>=1 + range>=1 => siege projectile + `splash_radius`
- extra projectiles:
  - `total_projectiles > 1` (except siege splash cases)
- burst/first attack projectiles from `max_total_projectiles` + specific `charge_type`
- trample percent from fractional blast damage patterns
- splash-on-hit radius from blast attack level markers
- dodge shield from `charge_type` and charge fields
- pass-through from secondary projectile profile patterns
- bonus damage reduction from resistance field

## 8. What must remain configurable/hardcoded

Not every gameplay mechanic is fully represented in dat fields. Keep a controlled override layer (same concept as current `UNIQUE_COMBAT_PROPERTIES` and `CIV_COMBAT_PROPERTIES`) for:
- dismount form stats
- transform form stats
- armor-ignore flags where dat signal is ambiguous
- civ-conditional mechanics from unique tech design intent
- paired unit relations (ex: melee/ranged modes)

Do not bury these in random code branches; keep one explicit override registry.

## 9. Recommended rebuild sequence

1. Parse dat once and write all extracted JSON.
2. Build `UnitAnalyzer`-style stat computation over JSON.
3. Generate `aoe2_reference.db` with:
- base/final stats
- stat chain
- applied tech rows
- special effects
- projectile rows
4. Generate `aoe2_units.db` from reference DB with complete `unit_stats` simulation columns.
5. Validate API payload compatibility (`/api/ref/civ/*`, `/api/ref/combat-unit/*`).

## 10. Regression checklist (must pass)

- Unique units are addressable by expected slug with civ suffix.
- Non-elite unique units still appear in Imperial data paths.
- Projectile fields are populated for Chu Ko Nu/Kipchak/Organ Gun/Fire Archer/Fire Lancer/Xianbei class cases.
- `attacks_json`/`armors_json` contain numeric class keys encoded as JSON object keys.
- `unit_stats` special columns are non-null/default-safe for simulator reads.
- Civ tech disables correctly remove unavailable units/upgrades.
