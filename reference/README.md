# AoE2 Reference Corpus

Generated: 2026-04-12

This directory contains markdown reference files for all AoE2 civilizations, units, and armor classes.
Each file includes a **DB Comparison** table showing whether our local database matches the authoritative
external sources (Fandom wiki + SiegeEngineers/aoe2techtree).

## Structure

```
reference/
  armor-classes.md       — All armor classes
  civs/                  — One file per civilization (53 total)
  units/generic/         — Generic unit lines (Arbalester, Paladin, etc.)
  units/unique/          — Unique units per civ
```

## How to Regenerate

From the project root (activate venv first: `source venv/bin/activate`):

```bash
# Regenerate all files (skip existing)
python3 scripts/build_reference_docs.py

# Force regenerate all files
python3 scripts/build_reference_docs.py --force

# Regenerate a single civ
python3 scripts/build_reference_docs.py --civ Muisca

# Regenerate a single unit
python3 scripts/build_reference_docs.py --unit "Temple Guard"

# Dry run — report what would be written
python3 scripts/build_reference_docs.py --dry-run
```

## Reading the DB Comparison Tables

| Symbol | Meaning |
|--------|---------|
| ✅ | Values match within tolerance (±0.01 for floats) |
| ❌ | Values differ — needs investigation |
| ⚠️ | External data not available for this field |
| ❌ NOT IN DB | Field missing from our database |

## When to Regenerate

Regenerate the corpus after:
- A new dat file update (new patch with balance changes)
- Adding new civilizations
- Adding new combat mechanics to the simulator

## Sources

- **Stats:** [SiegeEngineers/aoe2techtree](https://github.com/SiegeEngineers/aoe2techtree)
- **Civ bonuses + unique techs:** [Fandom Wiki](https://ageofempires.fandom.com/wiki/Age_of_Empires_II)
- **DB:** `webapp/aoe2_reference.db` (local SQLite, queried directly)
