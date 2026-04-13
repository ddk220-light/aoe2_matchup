# AoE2 Reference Corpus — Design Spec

**Date:** 2026-04-12  
**Status:** Approved

---

## Overview

A static markdown corpus documenting every civilization, unit, and armor class in AoE2, generated from external authoritative sources (Fandom wiki + SiegeEngineers/aoe2techtree). Each file includes a DB comparison table that flags mismatches against our local `aoe2_reference.db`. The corpus serves as both human-readable documentation and a validation tool.

---

## Goals

1. **Documentation** — Human-readable reference for all 53 civs, ~180 units, 40 armor classes.
2. **Validation** — Each file embeds a DB comparison table so discrepancies between external data and our DB are immediately visible.
3. **Agent support** — The `aoe2onlinereference` skill + `--civ`/`--unit` CLI flags let agents regenerate a single file on-demand when they need to verify a specific unit or civ.

---

## File Structure

```
reference/
  README.md                    ← index + regeneration instructions
  armor-classes.md             ← all 40 armor classes
  civs/
    Armenians.md
    Aztecs.md
    ... (53 files, one per civ)
  units/
    generic/
      Archer.md
      Crossbowman.md
      Arbalester.md
      Paladin.md
      ... (~60 files, one per unit tier in each generic line)
    unique/
      Cataphract.md
      Leitis.md
      Temple_Guard.md
      ... (~130 files, one per unique unit including elite variants as sections)
scripts/
  build_reference_docs.py      ← the generator script
```

**Unit file naming:** Use the exact unit name with spaces replaced by underscores. Elite variants are sections within the same file (e.g., `Temple_Guard.md` covers both Regular and Elite).

---

## Data Sources

| Content | Primary Source | Fallback |
|---------|---------------|---------|
| Unit base stats | SiegeEngineers/aoe2techtree `data.json` | Fandom wiki infobox |
| Civ bonuses, team bonus | Fandom wiki | aoe2techtree civ entry |
| Unique tech costs + effects | Fandom wiki | aoe2techtree techs |
| Tech tree gaps | SiegeEngineers/aoe2techtree civ tree JSON | — |
| Armor class names + IDs | Local `aoe2_reference.db` `armor_classes` table | — |
| Special abilities text | Fandom wiki | — |

**New civ handling (Muisca, Mapuche, Tupi, Shu, Wei, Wu, Jurchens, Khitans):** These may be absent or incomplete in aoe2techtree. Use Fandom wiki as primary for these civs. If wiki also has no page, write partial file with a `⚠️ External data not found` note and still write DB values.

**Do NOT use** our Railway API (`aoe2.up.railway.app`) as a data source — it only reflects our current DB state, making comparison circular.

---

## Script: `scripts/build_reference_docs.py`

### CLI Interface

```bash
# Full build — skip existing files
python3 scripts/build_reference_docs.py

# Full rebuild — regenerate all files
python3 scripts/build_reference_docs.py --force

# Single civ (for agent on-demand use)
python3 scripts/build_reference_docs.py --civ Muisca

# Single unit (for agent on-demand use)
python3 scripts/build_reference_docs.py --unit "Temple Guard"

# Dry run — report what would be written + mismatches, write nothing
python3 scripts/build_reference_docs.py --dry-run
```

### Execution Order

1. **Startup**: Fetch `SiegeEngineers/aoe2techtree` `data.json` once, cache in memory. Open local `aoe2_reference.db` connection.
2. **Generate `reference/armor-classes.md`** from DB `armor_classes` table.
3. **Generate civ files** — iterate all 53 civs:
   - Skip if file exists and `--force` not set
   - Fetch Fandom wiki page (with 0.5s delay between requests)
   - Query local DB for units, techs, special effects
   - Cross-reference aoe2techtree
   - Write file
4. **Generate unit files** — iterate all generic + unique units:
   - Same skip logic
   - Pull from aoe2techtree (primary) or wiki (fallback)
   - Query local DB
   - Write file
5. **Print summary** to stdout: files written, files skipped, total ❌ mismatches found.

### Rate Limiting

Sleep 0.5s between Fandom wiki API calls. aoe2techtree is fetched once (large JSON), not per-unit.

### Error Handling

- Fandom wiki 404 or missing page → log `⚠️ WARNING: Wiki page not found for {name}`, write partial file with available data.
- aoe2techtree missing unit → log warning, use wiki values only, mark DB comparison fields as `N/A (external)`.
- DB missing unit → mark DB comparison fields as `❌ NOT IN DB`.
- Network timeout → retry once, then skip with warning.

---

## Markdown File Formats

### Civ File (`reference/civs/{CivName}.md`)

```markdown
# {CivName}

**Focus:** {type, e.g. "Archer & Monk"}  
**Sources:** Fandom wiki, SiegeEngineers/aoe2techtree  
**Generated:** {YYYY-MM-DD}

## Civilization Bonuses
- Bonus 1
- Bonus 2

## Team Bonus
{text}

## Unique Technologies
| Tech | Age | Cost | Effect |
|------|-----|------|--------|
| {castle UT} | Castle | {cost} | {effect} |
| {imperial UT} | Imperial | {cost} | {effect} |

## Unique Units
### {Unit Name}
| Stat | Regular | Elite |
|------|---------|-------|
| HP | X | Y |
| Attack | X | Y |
| Melee Armor | X | Y |
| Pierce Armor | X | Y |
| Speed | X | Y |
| Range | X | Y |
| Reload Time | X | Y |
| Cost | XF XW XG | XF XW XG |
| Train Time | Xs | Xs |
| Pop Space | X | X |

**Special Ability:** {free text}

**Attack Bonuses:**
| vs | Regular | Elite |
|----|---------|-------|
| {armor class} | +X | +X |

## Tech Tree Gaps
- No {unit/tech}
- No {unit/tech}

## DB Comparison
| Field | External | Our DB | Match |
|-------|----------|--------|-------|
| {Unit} HP (regular) | X | X | ✅/❌ |
| {Unit} HP (elite) | X | X | ✅/❌ |
| {Unit} speed | X | X | ✅/❌ |
| {Castle UT} cost | X | X | ✅/❌ |
| {Imperial UT} cost | X | X | ✅/❌ |
| {Unit} special effect | X | X | ✅/❌ |
```

### Unit File (`reference/units/{generic|unique}/{UnitName}.md`)

```markdown
# {Unit Name}

**Type:** {Infantry/Cavalry/Archer/Siege}  
**Available to:** {All civs / specific civs}  
**Building:** {Barracks/Stable/etc.}  
**Sources:** SiegeEngineers/aoe2techtree, Fandom wiki  
**Generated:** {YYYY-MM-DD}

## Stats
| Stat | {Age/Regular} | {Age+1/Elite} |
|------|--------------|----------------|
| HP | X | Y |
| Attack | X | Y |
| Melee Armor | X | Y |
| Pierce Armor | X | Y |
| Speed | X | Y |
| Range | X | Y |
| Reload Time | X | Y |
| Cost | XF XW XG | XF XW XG |
| Train Time | Xs | Xs |
| Pop Space | X | X |

## Bonus Damage
| vs Armor Class | Amount |
|----------------|--------|
| {class} | +X |

## Armor Classes (unit belongs to)
- {class name}
- {class name}

## Special Effects
{free text, or "None"}

## DB Comparison
| Field | External | Our DB (Castle) | Our DB (Imperial) | Match |
|-------|----------|----------------|-------------------|-------|
| HP | X | X | X | ✅/❌ |
| attack | X | X | X | ✅/❌ |
| melee_armor | X | X | X | ✅/❌ |
| pierce_armor | X | X | X | ✅/❌ |
| speed | X | X | X | ✅/❌ |
| range | X | X | X | ✅/❌ |
| reload_time | X | X | X | ✅/❌ |
| cost_food | X | X | X | ✅/❌ |
| cost_wood | X | X | X | ✅/❌ |
| cost_gold | X | X | X | ✅/❌ |
| {special effect field} | X | X | X | ✅/❌ |
```

### Armor Classes File (`reference/armor-classes.md`)

```markdown
# AoE2 Armor Classes

| ID | Name | Key Units That Belong | Key Units With Bonus vs This |
|----|------|-----------------------|------------------------------|
| 0 | Infantry | Militia line, Eagle Warriors | Jaguar Warrior, Samurai |
| 1 | Turtle Ships | Turtle Ships | — |
...
```

---

## DB Comparison Logic

### Fields Compared for Units

All comparisons use `ref_units` table, columns:
`base_hp`, `base_attack`, `base_melee_armor`, `base_pierce_armor`, `base_speed`, `base_range`, `base_reload_time`, `base_cost_food`, `base_cost_wood`, `base_cost_gold`

Special effect fields (from `ref_special_effects` join):
`bleed_dps`, `bleed_duration`, `trample_percent`, `trample_flat_damage`, `trample_radius`, `pass_through_percent`, `pass_through_count`, `attack_bonus_per_kill`, `charge_attack_melee`, `dodge_shield_max`, `pop_space`, `attack_speed_ramp`, `attack_speed_min`, `execute_damage_per_step`, `ally_death_heal`

### Mismatch Tolerance

- **Floats:** Consider equal if `abs(external - db) <= 0.01` (handles rounding like 0.96 vs 0.9600)
- **Strings:** Exact match after `.strip().lower()`
- **Costs:** Exact integer match

### Match Symbol Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Values match within tolerance |
| ❌ | Values differ — needs investigation |
| ⚠️ | External data not available for this field |
| — | Field not applicable for this unit type |

---

## `reference/README.md` Content

Explains:
- What the corpus is and how to use it
- How to regenerate all files: `python3 scripts/build_reference_docs.py`
- How to regenerate a single civ/unit: `--civ` / `--unit` flags
- How to interpret the DB Comparison tables
- When to regenerate (after a new patch dat file update)

---

## Out of Scope

- Ship units (not in the simulator)
- Building stats
- Campaign-only units (War Dog)
- Full tech tree (only unique techs per civ, not every researchable tech)
- Automatic regeneration on push (manual only)
