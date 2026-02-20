# Speed-Weighted Score Normalization

**Date:** 2026-02-20
**Status:** Approved

## Goal

Incorporate movement speed as a multiplier on unit ranking scores. Faster units should rank higher, slower units lower. This reflects the real-game importance of mobility for engagement control, raiding, and map presence.

## Algorithm

For each composite score:

1. Compute the composite score as usual (0-100)
2. Multiply by the unit's movement speed: `weighted = score * speed`
3. Re-normalize back to 0-100 within the same scope as the original normalization

```python
for each unit:
    speed_weighted = score * movement_speed
lo, hi = min(all_speed_weighted), max(all_speed_weighted)
final = (speed_weighted - lo) / (hi - lo) * 100
```

## Affected Scores & Scopes

| Score Type | Function | Norm Scope |
|---|---|---|
| `general_combat` (infantry) | `compute_infantry_role_scores` | All infantry |
| `anti_cav` (infantry) | `compute_infantry_role_scores` | All infantry |
| `militia_value` | `compute_infantry_role_scores` | All infantry |
| `raid_building` | `compute_raiding_scores` | All infantry |
| `anti_cav_value` | `compute_anti_cav_scores` | All infantry |
| `general_combat` (archery) | `compute_archery_role_scores` | Per line |
| `anti_archer` | `compute_archery_role_scores` | Per line |
| `ranged_effectiveness` | `compute_archery_role_scores` | Per line |
| `general_combat` (stable) | `compute_stable_role_scores` | All stable |
| `anti_cav` (stable) | `compute_stable_role_scores` | All stable |
| `stable_effectiveness` | `compute_stable_role_scores` | All stable |
| `anti_building_score` (ram) | `compute_siege_antibuilding_scores` | Per line |
| `anti_building_score` (BBC) | `compute_siege_antibuilding_scores` | Per line |
| `anti_building_score` (treb) | `compute_siege_antibuilding_scores` | **EXEMPT** |
| `anti_cav_combined` | `compute_combined_anti_cav_scores` | Combined pool |

## Exemptions

- **Trebuchet line**: Exempted from speed multiplication (speed=0, deployed siege)

## What Does NOT Change

- Scoring formula weights (50/30/20, 70/30, etc.)
- Benchmark definitions and opponents
- Raw simulation battle results
- Database schema
- Frontend display logic
