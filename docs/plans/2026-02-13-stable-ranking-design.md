# Stable Units Ranking Table Design

## Overview

Replace all 6 existing cavalry tables (knight, light_cav, camel, steppe_lancer, elephant, all_cavalry) with a single "Stable Units" ranking table. The new table uses a benchmark-based composite score instead of round-robin pairwise scoring.

## Scoring Formula

```
stable_power = 0.6 * attack_power + 0.2 * movement_speed + 0.2 * survivability
```

All components normalized to 0-100. Final score range: 0-100.

### Attack Power

Average of 6 benchmark simulations (shifted from -100..+100 to 0..100):

| Key | Opponent | Mode |
|-----|----------|------|
| `atk_30v30_vs_paladin` | Spanish Paladin | 30v30 fixed count, HP% |
| `atk_30v30_vs_arb` | Chinese Arbalester | 30v30 fixed count, HP% |
| `atk_30v30_vs_champ` | Chinese Champion | 30v30 fixed count, HP% |
| `atk_3k_vs_paladin` | Spanish Paladin | 3K resource, HP% |
| `atk_3k_vs_arb` | Chinese Arbalester | 3K resource, HP% |
| `atk_3k_vs_champ` | Chinese Champion | 3K resource, HP% |

Shift formula: `(sim_score + 100) / 2`

### Survivability

Average of 6 benchmark simulations (same shift):

| Key | Opponent | Mode |
|-----|----------|------|
| `surv_30v30_vs_halb` | Chinese Halberdier | 30v30 fixed count, HP% |
| `surv_30v30_vs_camel` | Turks Heavy Camel | 30v30 fixed count, HP% |
| `surv_30v30_vs_ca` | Berbers Camel Archer | 30v30 fixed count, HP% |
| `surv_3k_vs_halb` | Chinese Halberdier | 3K resource, HP% |
| `surv_3k_vs_camel` | Turks Heavy Camel | 3K resource, HP% |
| `surv_3k_vs_ca` | Berbers Camel Archer | 3K resource, HP% |

### Movement Speed

Min-max normalization within the table's unit pool:

```
movement_speed = (unit_speed - min_speed) / (max_speed - min_speed) * 100
```

## Units Included

Imperial age only. Every stable-trained unit each civ has access to gets its own row.

**Generic lines:**
- Paladin (or Cavalier if civ lacks Paladin)
- Hussar
- Heavy Camel
- Elite Steppe Lancer
- Elite Battle Elephant

**Unique stable units (elite versions):**
- Cataphract (Byzantines), Tarkan (Huns), Boyar (Slavs), War Elephant (Persians)
- Konnik (Bulgarians), Leitis (Lithuanians), Keshik (Tatars), Coustillier (Burgundians)
- Ratha/Melee (Bengalis), Shrivamsha Rider (Gurjaras), Centurion (Romans)
- Monaspa (Georgians), Iron Pagoda (Jurchens), Tiger Cavalry (Wei)
- Magyar Huszar (Magyars)

Multiple rows per civ. E.g., Byzantines: Paladin, Cataphract, Hussar, Heavy Camel.

## Backend Changes

### compute_battle_scores.py

1. **Remove** 6 line entries from `UNIT_LINES`: `knight`, `light_cav`, `camel`, `steppe_lancer`, `elephant`, `all_cavalry`
2. **Add** `STABLE_LINE_SLUGS = ["knight", "light_cav", "camel", "steppe_lancer", "elephant"]` (source lines for unit collection)
3. **Add** `STABLE_BENCHMARKS` list with 12 benchmark tuples
4. **Add** `STABLE_SCORE_TYPES` list with all score keys
5. **Add** `compute_stable_role_scores()` function:
   - Collects all Imperial stable units from the 5 source lines via `build_line_units()`
   - Runs each unit against 12 benchmarks using existing sim modes (`fixed_hp` for 30v30, `res` for 3K)
   - Computes `attack_power` = avg of 6 attack benchmark scores (shifted 0-100)
   - Computes `survivability` = avg of 6 survivability benchmark scores (shifted 0-100)
   - Collects movement speeds, does min-max normalization to 0-100
   - Computes `stable_power = 0.6 * attack_power + 0.2 * movement_speed + 0.2 * survivability`
   - Stores all scores under virtual line slug `"stable"`
6. **Update** `main()` to call `compute_stable_role_scores()` and skip old cavalry round-robin
7. **Update** `write_role_scores_to_db()` call to include stable scores

### app.py

1. **Remove** individual cavalry line entries from any line-config dicts
2. **Add** `"stable"` to the set of role-scored lines (alongside infantry, archery)
3. Ensure `/api/ref/unit-line/stable` returns the correct data with new score types

## Frontend Changes

### index.html

1. **Remove** 6 LINE_CONFIG entries: `knight`, `light_cav`, `camel`, `steppe_lancer`, `elephant`, `all_cavalry`
2. **Add** single entry:
   ```js
   stable: {
       name: "Stable Units",
       building: "Stable",
       castle: null,
       imperial: "Paladin",
       hasUnique: true,
   }
   ```
3. No Castle/Imperial age toggle (Imperial only)
4. **Primary sort**: `stable_power` (composite score)
5. **Table columns**: Civ, Unit, Stable Power, Attack Power, Speed Score, Survivability, HP, Atk, Armor, Cost
6. **Score breakdown config**:
   - `attack_power`: 6 sub-scores with benchmark details
   - `survivability`: 6 sub-scores with benchmark details
   - `movement_speed`: raw speed + normalized score

## Score Display

| Column | Description | Range |
|--------|-------------|-------|
| Stable Power | Composite score (primary sort) | 0-100 |
| Attack Power | Avg of 6 attack benchmarks | 0-100 |
| Speed | Min-max normalized movement speed | 0-100 |
| Survivability | Avg of 6 survivability benchmarks | 0-100 |
