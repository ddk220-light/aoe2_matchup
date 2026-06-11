# Data Pipeline — Stages 1–3 (`extraction/`, `analysis/`)

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document covers the first three stages of the four-stage pipeline: parsing the game's binary `.dat` file into JSON, computing fully-upgraded per-civ stats into `webapp/aoe2_reference.db`, and flattening that into `webapp/aoe2_units.db`. Stage 4 (the Flask app and simulators) is documented in [webapp.md](webapp.md) and [simulation-engines.md](simulation-engines.md); offline derived artifacts (battle scores, pool scores) are in [derived-data.md](derived-data.md).

```
empires2_x2_p1.dat
  └─ python3 -m extraction.run            → extraction/extracted_data/*.json   (8 files)
       └─ python3 -m analysis.generate_reference → webapp/aoe2_reference.db   (audit DB)
            └─ python3 -m analysis.generate_main_db → webapp/aoe2_units.db    (flat unit_stats)
```

The `.dat` file lives at `extraction/empires2_x2_p1.dat` and is **not** committed; copy it from a local AoE2:DE install. Parsing requires `genieutils-py` (`from genieutils.datfile import DatFile`), which is in neither `requirements.txt` nor `webapp/requirements.txt` — install it manually before rebuilding, and note no version is pinned anywhere.

## Stage 1 — Extraction (`extraction/`)

`extraction/run.py` calls `DatFile.parse()` once, then delegates to three modules and writes 8 JSON files into `extraction/extracted_data/`. Counts below are from the committed build-177723 output.

| File | Entries | Producer | Contents |
|---|---|---|---|
| `units.json` | 256 | `extract_units.py` | One dict per whitelisted combat unit: hp, speed, LOS, cost, train time, range, reload, attack delay, accuracy, blast fields, per-class `attacks`/`armors` lists, charge fields, projectile data. Read from **Gaia** (`df.civs[0]`), which holds base stats for all units. |
| `technologies.json` | 1366 | `extract_techs.py` | Every named tech: cost, research time, `civ` (owner civ id, −1 = generic), `effect_id`, `required_techs`, `research_location`. |
| `tech_ages.json` | 69 | `extract_techs.py` | Age (1=Dark … 4=Imperial) and building for ~69 pattern-matched standard techs (Blacksmith lines, unit upgrades, etc.), resolved through prerequisite chains. |
| `civilizations.json` | 53 | `run.py` inline | Per-civ id, name, and a unit count (sanity data only). |
| `armor_classes.json` | 40 | `extract_constants.py` | The 40 armor/attack class ids 0–39 with names (several marked "Unused"). |
| `effects.json` | 1121 | `extract_effects.py` | Every dat effect that has commands, with each command decoded (`type`, `a`, `b`, `c`, `d` plus derived fields and a description). |
| `civ_tech_trees.json` | 53 | `extract_effects.py` | Per civ: `disabled_techs` and `disabled_units` (decoded from type-102/103 commands in the civ's tech-tree effect), plus the raw `team_bonus` effect. |
| `tech_effects.json` | 1013 | `extract_effects.py` | tech_id → decoded effect commands; this is the file the analyzer actually applies. |

`extract_units.py` extracts only the 256 unit ids in its `UNIT_NAMES` whitelist (militia line through The Last Chieftains uniques). For ranged units it follows `projectile_unit_id`, `secondary_projectile_unit`, and `charge_projectile_unit` into the full (projectile-inclusive) unit table to capture projectile speed and per-projectile attack lists. HP regen comes from the dat field `rear_attack_modifier` (attribute 109).

### The 53-civ mapping

`extract_constants.CIV_NAMES` is a 60-slot list matching dat civ ids. Skipped slots: index 0 (Gaia) and the six `None` slots — 46–48 (Achaemenids, Athenians, Spartans; Chronicles: Age of Antiquity) and 54–56 (Macedonians, Thracians, Puru; Chronicles: Alexander). That leaves **53 playable civs**, which is the count everywhere downstream (`civilizations.json`, `ORIGINAL_13_CIVS`, the `civilizations` table). The pipeline's civ list constant is `ORIGINAL_13_CIVS` in `analysis/config_constants.py` — the name is historical; it is now **derived** from `CIV_NAMES` (`sorted(c for c in CIV_NAMES[1:] if c)`), so a new civ added at its dat slot flows through automatically. (The old duplicate copy in `webapp/app.py` was deleted.)

## Stage 2 — Reference DB (`analysis/generate_reference.py`)

`generate_reference.py` instantiates `analysis/unit_analyzer.py::UnitAnalyzer` (which loads all 8 JSONs), deletes and recreates `webapp/aoe2_reference.db`, and for each of the 53 civs processes every unit roster entry with a full audit trail. Current DB contents: 972 `ref_units` rows, age `Imperial` **only** (the Imperial-only purge, 2026-06-11 — Castle rows are no longer emitted; Castle-age *techs* still apply inside the Imperial stat chain).

### How armor and attack values are derived

**The armor-class system.** Damage in AoE2 is per-class: a unit carries a list of *attacks* (class → amount) and a list of *armors* (class → amount), over the 40 classes in `armor_classes.json`. Class 4 is Base Melee, class 3 is Base Pierce; everything else is a bonus-damage class (27 Spearmen, 15 Archers, 8 Cavalry, …). `UnitAnalyzer.get_base_stats()` copies these lists into `UnitStats.attacks` / `UnitStats.armors` dicts (keeping the first entry per class), and also tracks scalar `attack`, `melee_armor`, `pierce_armor` from the dat's displayed values; the scalars are kept in sync with classes 4 and 3 as effects apply.

**Effect command types.** A tech's effect is a list of commands; the analyzer applies three of them (`unit_analyzer.apply_effect_command`):

| Type | Name | Semantics |
|---|---|---|
| 0 | SET_ATTRIBUTE | `stats.attr = d` (hp, speed, range, reload, accuracy, hp_regen) |
| 4 | ADD_ATTRIBUTE | `stats.attr += d`; for attack (attr 9) / armor (attr 8), `d` is **encoded as `class*256 + amount`** with amount a signed byte (e.g. Forging's `d=1025` = class 4, +1; Plate Barding's `d=770` = class 3, +2) |
| 5 | MULTIPLY_ATTRIBUTE | `stats.attr *= d`; for attack/armor, `d` encodes `class*256 + percent` (e.g. 120 = ×1.2) |

Targeting: command field `a` is a unit id (or −1) and `b` is a unit class; `effect_applies_to_unit()` matches either, and dual-class units (e.g. Ballista Elephant, Warrior Priest via `extra_unit_classes`) match on a tuple of classes.

**Order of application** (`process_unit_audited` in `generate_reference.py`, mirroring `calculate_unit_stats_for_civ` in `unit_analyzer.py`):

1. **Base stats** from `units.json`, then `UNIT_STAT_OVERRIDES` patches (see below).
2. **Standard techs** — generic techs (`civ == -1`), researchable (`research_location != -1` unless in `ALLOWED_SHADOW_TECHS`), age-gated, applied in tech-id order. Additive first matters: Bloodlines' +20 HP lands before multiplicative civ bonuses.
3. **Civ bonus techs** — free techs with `civ >= 0` (named `C-Bonus, …`), with special handling: Lithuanian relic bonuses capped by `LITHUANIAN_RELIC_COUNT = 4`, conditional "`+ BL`" variants preferred when Bloodlines is available, and unit-specific armor commands that exactly cancel a class-wide bonus in the same effect are skipped (`_is_class_cancellation_cmd`).
4. **Team bonus attack** — from the hardcoded `CIV_TEAM_BONUS_ATTACK` dict in `analysis/config_units.py` (currently Persians knight-line +2 vs Archers, Saracens foot archers +3 vs Standard Buildings). Note the dat team-bonus effect is extracted into `civ_tech_trees.json` but is **not** generically applied; only these hardcoded entries and `CIV_TEAM_BONUS_WORK_RATE` are.
5. **Unique techs** — civ-specific techs that have a research cost (e.g. Garland Wars).
6. **Building work rate** — divides train time only, via `BUILDING_WORK_RATE_TECHS` (Conscription, Perfusion, Chivalry) and `CIV_TEAM_BONUS_WORK_RATE`.

Every applied step writes one `ref_techs_applied` row (tech name, type, building, age, human-readable effect description, cost) and one `ref_stat_chain` row — a **full snapshot of all stats after that step**, with step 0 being base stats. This is the audit trail.

**Worked example — Frankish Paladin, Imperial Age** (`ref_units.unit_slug = 'paladin'`, civ `Franks`; reproduce with `SELECT * FROM ref_stat_chain WHERE ref_unit_id = (SELECT id FROM ref_units WHERE civ_name='Franks' AND unit_slug='paladin')`):

| Step | Tech (type) | HP | Attack (cls 4) | Melee armor (cls 4) | Pierce armor (cls 3) |
|---|---|---|---|---|---|
| 0 | Base Stats | 160 | 14 | 2 | 3 |
| 2–4 | Forging / Iron Casting / Blast Furnace (standard) | 160 | 15 / 16 / 18 | 2 | 3 |
| 5–7 | Plate / Scale / Chain Barding Armor (standard) | 160 | 18 | 3 / 4 / 5 | 5 / 6 / 7 |
| 8 | C-Bonus, Cavalry +20% HP (civ_bonus, type-5 ×1.2) | 192 | 18 | 5 | 7 |
| 9 | Building Work Rate (Conscription, Franks UT Chivalry) | train time only | | | |

Melee armor 2→5 is exactly three +1 class-4 ADDs from the barding line (Plate Barding's command `d=1025`); pierce 3→7 is +1, +1, +2 on class 3 (`d=770` for the +2). Bloodlines does not appear because tech 435 is in Franks' `disabled_techs`. The HP multiply runs after all adds, so the chain order is load-bearing.

### Which unit is available for which civ

Availability is a **blocklist with allowlist patches**, resolved per (civ, line) in `calculate_unit_stats_for_civ`:

- **Blocklist (dat-driven):** a civ lacks a line if its config's `availability_tech` (e.g. 166 "Knight (make avail)") appears in that civ's `disabled_techs` from `civ_tech_trees.json`; upgrade tiers (`upgrades` list of `(tech_id, unit_id, name)`) are likewise skipped when their tech is disabled or above the target age. Disabled-unit ids (type 103) are also extracted but the tech check is what gates lines.
- **Allowlist patch (`_AVAILABILITY_OVERRIDES`, `analysis/config_units.py` line 1730):** 17 slugs (eagle line, camels, battle elephants, elephant archers, slinger, champi warrior, steppe lancer, fire lancer, paladin) are auto-enabled in the dat via tech-tree resolution the pipeline does not replicate, so they are pinned to explicit civ lists (sourced from SiegeEngineers data.json) by injecting `civ_only` into `CASTLE_UNITS`/`IMPERIAL_UNITS`. Without this, ~776 phantom rows appear.
- **Alternates:** a config's `alternate` block swaps the line when the main unit is disabled but the alternate's tech is not (Battering Ram → Armored Elephant, tech 162 vs 837; similar for capped/siege ram tiers). **`civ_upgrades`** grants civ-specific tiers outside the age gate (Burgundian Castle-age Cavalier; Rocket Cart replacing Mangonel for Chinese/Koreans/Jurchens/Khitans).
- **Unique units:** `UNIQUE_UNITS` in `analysis/config_units.py` maps each of the 53 civs to its unique-unit configs (64 total) with `base_id`/`elite_id`; `NAVAL_UNIQUE_UNITS` adds 18 naval uniques. Unique slugs get a civ suffix (`huskarl_goths`).
- `CIV_MISSING_UNITS` in `webapp/unit_lines.py` is a **stage-4** declarative filter on top of this (rows the pipeline still emits); see [webapp.md](webapp.md).

**Ages.** Only Imperial (4) ROWS are generated (Imperial-only purge, 2026-06-11): the roster is `IMPERIAL_UNITS` (25 lines) plus `NAVAL_LINE_CONFIGS` (5 lines) and the unique units (elite form, or the base unit with Imperial techs when no elite exists). Age constants below Imperial still matter for **tech staging** — `calculate_unit_stats_for_civ(…, IMPERIAL_AGE)` applies Feudal/Castle-age techs on the way up — and `CASTLE_UNITS`/`FEUDAL_UNITS` still exist in config (`_PREVIOUS_AGE_NAMES`, the availability-resolver override comparison) but are never emitted as rows. Two derivational availability gates were added with the purge: (1) `AvailabilityResolver.tech_tree_disabled_unit_closure(civ)` — a line whose `base_id` is type-2-disabled by the civ's tech-tree effect (expanded through the dat's type-3 upgrade edges) never emits, which is what kills the Incas/Mapuche/Muisca/Tupi militia-line ghosts and the bug class for future DLCs; (2) `availability_tech` was set on `trebuchet` (tech 256) and `heavy_scorpion` (tech 94), pruning the phantom Shu/Wei/Wu Trebuchet and Shu Scorpion rows (CivTechTrees-verified). (Do not confuse the `imp_`-prefixed line slugs `imp_elite_skirm`/`imp_slinger` with anything age-related — they are real Imperial upgrade tiers. The dead `NO_ELITE_UNITS` dict that described a never-implemented `_imp`-suffix scheme was deleted from `generate_main_db.py`.)

### Config patch registries (`analysis/config_constants.py`, `analysis/config_units.py`)

| Registry | Entries | Purpose |
|---|---|---|
| `UNIT_STAT_OVERRIDES` | 4 unit ids | Base-stat patches for dat errors: 534 Elite Woad Raider speed 1.2174; 2150 War Chariot full ranged stat block (dat extracts it as melee); 1968/1970 Fire Archer range 5/6 (dat exposes the anti-building attack's range). Applied right after `get_base_stats()`. |
| `ALLOWED_SHADOW_TECHS` | 3 tech ids | Shadow techs (`research_location == -1`) that must bypass the shadow filter: 774/797 Flemish Militia age upgrades, 1025 Traction Trebuchet enable. |
| `REMOVED_TECHS` | 1 tech id | Techs still in the dat but removed from the live game: 9 (Saracen Zealotry). Skipped during civ-bonus and unique-tech application. |
| `LITHUANIAN_RELIC_COUNT` | scalar = 4 | How many relic attack bonuses to assume for Lithuanian cavalry. |

### Combat-property override chain

Stats the dat cannot express (or expresses obscurely) are layered by `analysis/combat_properties.py::get_combat_properties()`, later wins:

```
defaults (zeros) → extracted dat data → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES
```

| Layer | Where | Entries | What lives there |
|---|---|---|---|
| Extracted (`get_extracted_combat_properties`) | `analysis/combat_properties.py` | data-driven | min range, projectile speed, siege splash (class 13 + blast fields), extra projectiles (`total_projectiles`, charge types 6/7), trample percent/radius (blast level 2), Grenadier splash (level 11), Shrivamsha dodge shield (charge type 4), scorpion pass-through ratio, bonus-damage resistance, HP regen. |
| `COMBAT_PROPERTIES` | `analysis/config_combat.py` | 30 slugs | Mostly `unit_category` tags (`siege`/`trash`/`infantry`) plus scorpion `pass_through_count`. Keyed by standard-unit slug. |
| `UNIQUE_COMBAT_PROPERTIES` | `analysis/config_combat.py` | 52 base slugs | Ability flags not in the dat: Konnik dismount stat block, Leitis/Composite Bowman armor-ignore, charge recharge times, Liao Dao bleed, Obuch armor strip, Monaspa nearby bonus, pop-space 0.5 units, etc. Matched after stripping the civ suffix. |
| `CIV_COMBAT_PROPERTIES` | `analysis/config_combat.py` | 89 (civ, slug) keys | Civ-conditional effects of unique techs and civ bonuses: Logistica trample, Wootz Steel armor-ignore, Sicilian 40% bonus-damage reduction, Khitan Ordo regen / Lamellar reflect, Tupi Curare bleed, etc. |

The merged result is written three ways into the reference DB: as inline columns on `ref_units`, as rows in `ref_special_effects` (with a `source` column recording which layer supplied each value), and as `ref_projectiles` rows.

### `aoe2_reference.db` schema

| Table | Rows | Cols | Contents |
|---|---|---|---|
| `ref_units` | 972 | 121 | One row per civ × slug (age = `Imperial` for every row since the 2026-06-11 purge): identity (civ_name, unit_slug, unit_type ∈ standard/naval/unique, age, class), `base_*` and `final_*` stat sets (15 each, incl. `*_attacks_json`/`*_armors_json` per-class dicts), upgrade costs, and ~70 inline combat-property columns (incl. 9 `dismount_*` and 9 `transform_*`). |
| `ref_techs_applied` | 6,791 | 11 | Per unit: every applied tech with type (`standard`/`civ_bonus`/`unique_tech`/`work_rate`), building, age, effect description, cost. |
| `ref_stat_chain` | 7,749 | 20 | Step-ordered full stat snapshots; step 0 = base. The audit trail behind every final number. |
| `ref_special_effects` | 1,278 | 6 | property_name/value pairs with `source` (extracted_data / UNIQUE_COMBAT_PROPERTIES / CIV_COMBAT_PROPERTIES) and description. |
| `ref_projectiles` | 1,001 | 8 | `primary`/`extra`/`charge` projectile rows: count, speed, attacks_json, blast radius, siege flag. |
| `armor_classes` | 40 | 2 | Copied from `armor_classes.json`. |
| `battle_scores` | 0 at generation | 9 | Created empty; only the retired `compute_battle_scores.py` `main()` writes it (0 rows today — see [derived-data.md](derived-data.md) §5). |

## Stage 3 — Main DB (`analysis/generate_main_db.py`)

`generate_main_db.py` reads **only** the reference DB (plus `armor_classes.json` and `COMBAT_PROPERTIES`/`PAIRED_UNITS` for category and pairing tags), preserves any user rows from `comments`/`simulation_comments`/`unit_verifications`, deletes `webapp/aoe2_units.db`, and rebuilds it:

| Table | Rows | Notes |
|---|---|---|
| `civilizations` | 53 | Alphabetical; ids are local autoincrements, not dat ids. |
| `ages` | 3 | 2=Feudal, 3=Castle, 4=Imperial — but only Imperial (4) `unit_stats` rows exist since the Imperial-only purge. |
| `units` | 112 | Distinct (slug, age): all Imperial. Unique units carry `civ_id`. |
| `unit_stats` | 5,936 | **112 definitions × all 53 civs.** `has_unit=1` where a ref row exists (final stats copied in, 972 rows), `has_unit=0` stub otherwise — so "does civ X have unit Y" is answered by this flag, and webapp queries never need an outer join. |
| `armor_classes` | 40 | Same as reference DB. |
| `combat_results`, `comments`, `simulation_comments`, `unit_verifications` | user/runtime data | Created empty; preserved rows restored. |

`unit_stats` has exactly **100 columns**, in these groups: identity (3: `civ_id`, `unit_id`, `unit_name`) · core final stats (8: hp, attack, attack_range — NULL for melee, attack_speed = 1/reload, attack_delay, melee/pierce armor, movement_speed) · cost/economy (5: food/wood/gold, creation_time, upgrade_cost) · metadata (2: `civ_bonuses` summary string, `has_unit`) · per-class JSON (2: `attacks_json`, `armors_json`) · legacy combat counters (4, always 0) · combat properties (57: everything from the override chain, `unit_category`, `paired_unit_slug`) · `transform_*` (9) · `dismount_*` (9), plus `id`. `build_combat_dict_from_ref()` (line 78) is the function that maps `ref_special_effects` + `ref_projectiles` + inline `ref_units` columns into these fields; it deliberately mirrors the webapp-side canonical mapping, `build_combat_dict_from_ref()` in `webapp/combat_unit_loader.py`, so the two must stay in sync when columns are added. The script ends with hard-coded sanity checks (Byzantine Knight stats, Eagle Warrior availability, Cataphract trample, Chu Ko Nu projectiles, Fire Lancer charge, Berserk regen).

## Update triggers

| If this changes… | …update these sections |
|---|---|
| New game build / `.dat` patch | All counts (JSON entries, ref/main DB rows), 53-civ mapping if a DLC adds civs, worked example values |
| `extraction/extract_units.py` `UNIT_NAMES` or new extracted fields | Stage 1 table, units.json count |
| `extract_constants.CIV_NAMES` slots | "The 53-civ mapping" |
| `analysis/config_combat.py` dict entries | Override-chain table entry counts |
| `analysis/config_constants.py` (`UNIT_STAT_OVERRIDES` is in `config_units.py`, `ALLOWED_SHADOW_TECHS`/`REMOVED_TECHS` here) | "Config patch registries" table |
| `_AVAILABILITY_OVERRIDES`, `CASTLE_UNITS`/`IMPERIAL_UNITS`/`UNIQUE_UNITS` rosters | "Which unit is available for which civ", roster counts |
| `ref_units` / `unit_stats` schema (new combat property) | Both schema tables, the 100-column breakdown, and the 5-file sync chain in [webapp.md](webapp.md) |
| Effect application order in `unit_analyzer.py` / `generate_reference.py` | "Order of application", worked example |
