# Archery Line Redesign — Design

## Goal

Replace the round-robin/PES/RES scoring for archery lines with a role-based **Ranged Power Ranking** using the same UI pattern as infantry (stats table, hover cards, simulate links). Combine archer + cav_archer + skirmisher into one unified "archery" virtual line.

## Scoring Formula

**Ranged Power** = `0.7 × DPS Score + 0.3 × Survivability Score`

### DPS Score (avg of 3 matchups, all 3K resources)

| Matchup | Rationale |
|---|---|
| vs Chinese Champion | Anti-infantry effectiveness |
| vs Spanish Paladin | Anti-cavalry effectiveness |
| vs Chinese Arbalester | Mirror ranged effectiveness |

### Survivability Score (avg of 2 matchups, all 3K resources)

| Matchup | Rationale |
|---|---|
| vs Spanish Elite Skirmisher | Survives anti-archer counter |
| vs Chinese Heavy Cav Archer | Survives mobile ranged pressure |

Each matchup score = HP% remaining on archery unit (win → positive) or HP% remaining on enemy (loss → negative). Range: -100 to +100.

## Data Source

All scores stored in `aoe2_reference.db` → `battle_scores` table (same as infantry). No `battle_scores.json` dependency.

Score types stored: `vs_champ_dps`, `vs_paladin_dps`, `vs_arb_dps`, `vs_skirm_surv`, `vs_cav_archer_surv`, `dps_score`, `survivability_score`, `ranged_power`.

## Table Columns

Civ | Unit | Line | Score | DPS Score | Survivability | DPS | HP | Atk | M.Arm | P.Arm | Speed | Range | Cost | Upg Cost | Special

- **Line** column distinguishes archer / cav_archer / skirmisher
- Default sort: ranged_power descending
- Color coding: green above median, red below (median from non-unique units only)

## Hover Cards

Score columns show formula breakdown + individual matchup values + "Run in Battle Sim →" links. Stat columns reuse existing tech-chain hover cards.

## What Gets Removed

1. Round-robin computation for archer/cav_archer/skirmisher
2. PES and RES score columns
3. 30v30, 3K, 5K+Upg, 30vChp, 30vPal, 30vArb columns for archery
4. The `all_ranged` virtual line entry (replaced by `archery`)
5. Related `battle_scores.json` reads and SCORE_BREAKDOWN entries

## Files Modified

| File | Change |
|---|---|
| `webapp/compute_battle_scores.py` | Add `ARCHERY_ROLE_BENCHMARKS` + `compute_archery_scores()`, store in `battle_scores` DB table |
| `webapp/app.py` | Add `"archery"` virtual line with `sub_lines`, serve scores from DB, remove JSON reads for archery |
| `webapp/templates/index.html` | Add `archeryColumns`, `ARCHERY_SCORE_BREAKDOWN` hover cards, wire into `renderTable()` |
