# Unit Database Audit — Wrong `unit_class` & Stat Divergence

**Date:** 2026-06-05
**Method:** Multi-agent workflow (`.scratch/unit_audit_workflow.js` + `.scratch/audit_lib.py`).
Four deterministic finders swept all **108 config entries + 1,851 reference-DB rows + 134
reference docs** across four dimensions (unit-class, tech-application, armor/attack class
sets, stats-vs-docs); 18 candidates were adversarially verified against the `.dat` effect
targeting + `analysis/config_units.py` + `reference/units/**/*.md`. Findings independently
re-confirmed in the main session via `audit_lib` class-divergence analysis.

This audit was triggered after fixing the **Conquistador/Arambai** wrong-`unit_class` bug
(class 36 Cavalry-Archer instead of true dat class 23). Goal: find any other instance of
the same bug class — a wrong `unit_class` in `analysis/config_units.py` driving incorrect
per-class tech filtering in `analysis/generate_reference.py`.

## 1. Summary

| Metric | Count |
|---|---|
| Candidates checked | 18 |
| **Confirmed bugs (2 unit lines)** | **2 fixes** (8 raw finder rows) |
| — High severity | Centurion (Romans) |
| — Medium severity | Ratha (Melee) (Bengalis) |
| Cleared / intentional | 9 |
| Doc-only error (no DB defect) | 1 |

Two real defects, both the same root cause as Conquistador/Arambai — a wrong `unit_class`
in `analysis/config_units.py`. Each is a **single-line edit**.

## 2. Confirmed bugs

| # | Unit (ids) | Civ | Configured | True dat class | Effect |
|---|---|---|---|---|---|
| 1 | **Centurion / Elite** (1790/1792) | Romans | Infantry (6) | **Cavalry (12)** | Wrongly gets Scale/Chain/Plate **Mail** Armor + Squires + Arson (+ Roman Double-Mail bonus); wrongly **drops** Bloodlines (+20 HP), Husbandry, Scale/Chain/Plate **Barding** Armor |
| 2 | **Ratha (Melee) / Elite** (1738/1740) | Bengalis | Cavalry Archer (36) | **Cavalry (12)** | Wrongly gets Chemistry + Thumb Ring (inert on melee); wrongly **drops** Forging/Iron Casting/Blast Furnace → melee attack frozen at base |

Independently confirmed via `audit_lib` (config class vs true dat class, tech divergence):

- **Centurion** (class 6 vs 12): ADD `Scale/Chain/Plate Mail Armor, Squires, Arson, Tracking`; DROP `Bloodlines, Husbandry, Scale/Chain/Plate Barding Armor`.
- **Ratha (Melee)** (class 36 vs 12): ADD `Chemistry, Thumb Ring, archer-armor C-bonuses`; DROP `Forging, Iron Casting, Blast Furnace`. The Fletching/Bodkin/Bracer + Padded/Leather/Ring Archer Armor it has are **dat id-targeted (1738/1740)** and correctly remain (inert on the 0-range melee strike).

## 3. Exact fixes & expected deltas

### HIGH — Romans Centurion (1790/1792)
`analysis/config_units.py`: change the Centurion entry `"unit_class": 6` → `"unit_class": 12`.
- **GAIN:** Bloodlines (+20 HP), Husbandry (×1.10 speed), Scale/Chain/Plate **Barding** Armor.
- **LOSE:** Scale/Chain/Plate **Mail** Armor, Squires, Arson, and the infantry Double-Mail civ bonus (becomes Barding).
- **HP:** Castle 110 → **130**; Imperial 155 → **175**. Imperial pierce armor +1 (Plate Barding +2 PA vs Plate Mail +1 PA). Speed net unchanged (Squires ×1.1 ≈ Husbandry ×1.1). Attack unchanged (Forging line targets both class 6 and 12).
- Ground truth: `reference/units/unique/Centurion.md` Technologies (Bloodlines, Husbandry, Barding; no Mail/Squires/Arson).

### MEDIUM — Bengalis Ratha (Melee) (1738/1740)
`analysis/config_units.py`: change the **"Ratha (Melee)"** entry `"unit_class": 36` → `"unit_class": 12`.
**Do NOT touch the "Ratha (Ranged)" entry (1759/1761)** — it is correctly class 36.
- **GAIN:** Forging, Iron Casting, Blast Furnace on Base Melee → **+4 attack**.
- **Melee attack:** Castle 10 → **14**; Imperial 12 → **16**.
- **LOSE:** Thumb Ring, Chemistry (both inert on a 0-range melee strike).
- **KEEP:** Fletching/Bodkin/Bracer + Padded/Leather/Ring Archer Armor (dat id-targeted), Barding, Bloodlines, Husbandry.
- Ground truth: `reference/units/unique/Ratha_(Melee).md` (Range 0, no ranged blacksmith techs).

## 4. Cleared / intentional (verified, no change)

| Unit / item | Civ | Why cleared |
|---|---|---|
| Ballista Elephant (`extra_unit_classes=[12]`) | Khmer | Intentional documented dual-class (`unit_analyzer.py:576`); cavalry extra class correct, no leakage |
| Warrior Priest (class 6 + extra [18] Monk) | Armenians | Intentional Infantry+Monk hybrid; the two wrong monk techs (Block Printing, Illumination) are already suppressed via `excluded_tech_ids` (audit metric ignores that list) |
| Hussite Wagon (class 13 vs dat 55) | Bohemians | Tech-inert: classes 13 and 55 are equivalent for every effect Bohemians can reach; cosmetic label only |
| Light Cavalry / Hussar (class 12 vs dat 47 Scout) | all | Intentional Scout-as-Cavalry override; classes 12 and 47 tech-equivalent in the dat |
| Fire Archer range 5/6 | Wu | Intentional `config_units.py` override modeling the anti-unit charge mode for the 1v1 sim |
| Elite Skirmisher HP 35 | all | Finder compared the wrong doc (base Skirmisher HP 30); DB 35 matches dat ids 6/1155 |
| Turtle Ship attack/reload | Koreans | DB stores the regular rocket attack (dat 831/832); the doc's 20/25@6.0 is the separate charge cannonball; naval (not in 1v1 sim DB) |
| Caravel HP 130/150 | Portuguese | DB base matches dat; doc's 143/165 = base ×1.10 Portuguese ship-HP civ bonus, applied separately |

## 5. Doc-only error (no DB defect)

- **Battle Elephant** — `reference/units/generic/Battle_Elephant.md` top Stats table (HP 230/250, Attack 6/12, Range 4) is mistranscribed; the DB (HP 250/300, Attack 12/14, Range 0) matches the dat and the doc's own "DB Comparison / External" column. Optional: fix that doc's Stats table. No code/DB change.

## 6. Applying the fixes
Both are `unit_class` edits in `analysis/config_units.py`. Neither Romans nor Bengalis is in
the `.golden` matchup set, so the golden baseline is **not** affected. Because the committed
DBs are stale vs the current pipeline (a full regen rewrites combat-prop columns on all
rows — see the Conquistador fix), prefer the **surgical patch**: edit config, regenerate
into a scratch DB, transplant only the affected Centurion (Romans) and Ratha-Melee
(Bengalis) rows into `webapp/aoe2_reference.db`, verify blast radius, commit, promote.
