# Combined Anti-Cav Ranking Design

## Problem

The anti-cavalry section in civ analysis only ranks infantry units (spear + militia lines) by `anti_cav_value`. Stable units like Heavy Camels, Boyars, and Cataphracts — often a civ's best anti-cav option — are completely absent.

The challenge is that infantry `anti_cav_value` and stable `anti_cav` are computed on different scales (normalized within their own line populations), so they can't be directly compared.

## Solution: Pool + Re-rank by Shared Benchmarks

Run the same 4 anti-cav benchmark opponents against both infantry and qualifying stable units, normalize across the combined pool, and produce a single `anti_cav_combined` ranking.

### Shared Benchmarks (3K resources each)

| Key | Opponent |
|-----|----------|
| `ac_vs_paladin` | Spanish Paladin |
| `ac_vs_hussar` | Spanish Hussar |
| `ac_vs_heavy_camel` | Persian Heavy Camel |
| `ac_vs_elephant` | Vietnamese Elite War Elephant |

These are the same 4 cav-opponent benchmarks from `ANTI_CAV_BENCHMARKS` (minus the 2 frontline benchmarks: vs halb, vs arb).

### Stable Unit Filter

Only stable units with above-median `anti_cav` score (from existing stable computation) qualify. This includes camels, boyars, cataphracts, and other specialists; excludes generic paladins and hussars.

### Backend Changes

**`compute_battle_scores.py`:**
- New function `compute_combined_anti_cav_scores()` that:
  1. Reuses infantry anti-cav benchmark results (already computed by `compute_anti_cav_scores`)
  2. Runs the same 4 benchmarks against qualifying stable units
  3. Pools all results, min-max normalizes across the combined set
  4. Computes `anti_cav_combined` = average of the 4 normalized benchmark scores
  5. Writes to `battle_scores` with `score_type="anti_cav_combined"`, `line_slug="anti_cav_pool"`

**`best_units.py`:**
- Change ROLE_DEFS anti_cavalry entry from `("anti_cavalry", ["spear", "militia"], "anti_cav_value")` to `("anti_cavalry", ["anti_cav_pool"], "anti_cav_combined")`
- Remove `_compute_cross_line_rankings` call for anti-cav (no longer needed — single pool)

### No Frontend Changes

The anti-cav section in the civ analysis page just receives better-ranked data. No UI changes needed.
