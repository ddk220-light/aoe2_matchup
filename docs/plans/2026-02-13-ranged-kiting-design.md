# Ranged vs Ranged Kiting Design

**Date**: 2026-02-13
**Status**: Approved

## Problem

The current ranged-vs-ranged opening volley formula (`range_diff / 2` free shots) ignores unit speed entirely. A fast Cavalry Archer and a slow Hand Cannoneer with the same range advantage get identical opening shots. In real AoE2, the longer-ranged unit retreats while firing, and speed determines how quickly the shorter-ranged unit closes the gap.

## Design

Mirror the existing ranged-vs-melee kiting model for ranged-vs-ranged matchups.

### Physics Model

Two-phase opening, same structure as ranged-vs-melee:

**Phase 1 — Closing**: The longer-ranged unit (A) retreats while firing. The shorter-ranged unit (B) advances at full speed (it can't fire yet — out of range).

- `fire_dist = range_A - max(min_range_A, range_B)`
- A's effective retreat speed: `eff_retreat_A = speed_A * (1 - delay_A / reload_A)`
- Net closing speed: `net_speed = speed_B - eff_retreat_A`
- If `net_speed > 0`: B eventually catches up. Retreat capped at `RETREAT_MAX` tiles.
  - `retreat_time = min(RETREAT_MAX / eff_retreat_A, fire_dist / net_speed)`
  - `remaining_dist = fire_dist - net_speed * retreat_time`
  - `stand_time = remaining_dist / speed_B`
  - `closing_time = retreat_time + stand_time + delay_B` (delay_B = chaser's first attack delay)
- If `net_speed <= 0`: A can kite indefinitely, retreat capped at `RETREAT_MAX`.
  - `retreat_time = RETREAT_MAX / eff_retreat_A`
  - `remaining_dist = fire_dist` (gap never closes during retreat)
  - `stand_time = remaining_dist / speed_B`
  - `closing_time = retreat_time + stand_time + delay_B`

Opening shots for A: `1 + int((closing_time - delay_A) / reload_A)` if `closing_time > delay_A`.

**Phase 2 — Extended kiting bonus** (only when A's effective retreat speed > B's speed):

- `speed_diff = eff_retreat_A - speed_B`
- `kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX`
- Extra shots: `int(kite_dist / speed_diff / reload_A)`

**Phase 3 — Engagement**: Once B is in range, normal tick-based combat. No further movement advantage.

Unit B gets 0 opening shots (out of range while closing).

### Decision Points (Resolved)

- **Fire while retreating**: Yes, same as ranged-vs-melee. Effective retreat speed accounts for attack animation pauses.
- **Spatial limits**: Same constants as ranged-vs-melee (`RETREAT_MAX=10`, `MAP_SPACE=22`).
- **Same range, different speed**: No kiting. Kiting only when range advantage exists.
- **Slower but longer range**: Gets closing shots (retreat while firing), but no extended kiting bonus.

### Code Location

Replace the `elif is_ranged1 and is_ranged2:` block in `simulate_battle()` (simulation.py lines ~1001-1007). The current 6-line block expands to ~40 lines mirroring the ranged-vs-melee pattern above it. No other files change.

Must also set `closing_time1`/`closing_time2` for post-opening cooldown initialization.

### Example: Throwing Axeman (Franks) vs Arbalester (Chinese) at 3000 resources

- TAx: range 6, speed 1.1, reload 0.5, delay 0.467 (32 units)
- Arb: range 8, speed 0.96, reload 0.588, delay 0.333 (34 units)
- Arb has +2 range, is slower. Arb retreats while firing.
- `eff_retreat_Arb = 0.96 * 0.434 = 0.417`, `net_speed = 1.1 - 0.417 = 0.683`
- `closing_time = 2.93 + 0 + 0.467 = 3.39s`
- Arb opening shots: `1 + int((3.39 - 0.333) / 0.588)` = **6** (was 1 with old formula)

### Edge Cases

- **Min range**: `fire_dist = range_A - max(min_range_A, range_B)` handles units with minimum attack range.
- **Equal range**: `range_diff = 0`, no opening shots, straight to tick loop.
- **Zero speed**: Guarded by `speed > 0` checks, no division by zero.
- **Large range differences**: Many opening shots, which is correct — a 7-range advantage should be punishing.
