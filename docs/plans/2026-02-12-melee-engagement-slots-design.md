# Melee Engagement Slot System

## Problem

The current simulation allows all melee units to attack simultaneously when they reach melee range. In a 30 Champion vs 30 Arbalester fight, all 30 champions attack 30 different archers in the same tick. This is unrealistic: in actual AoE2, melee units form a semi-circle and only a fraction can physically reach the enemy at once, with surplus units pathing around looking for openings.

## Solution

Add an engagement slot system that limits how many melee units can attack ranged targets simultaneously.

## Rules

### Melee vs Ranged

1. **50% engageable cap**: At most `max(1, alive_ranged // 2)` ranged units are targetable by melee each tick.
2. **1:1 strict**: Each engageable ranged unit gets exactly 1 melee attacker.
3. **Surplus idles**: Melee units without an engagement slot skip their attack that tick.
4. **Rotation**: The engageable set rotates each tick (`tick % len(alive_ranged)` offset) so the same archers aren't always targeted.

### Melee vs Melee

Soft cap of 2 attackers per target: `max_per_target = max(2, melee_alive // max(1, enemy_alive))`. Prevents overkill concentration while allowing natural spread.

## Constants

```python
MELEE_ENGAGE_RATIO = 0.5   # fraction of ranged units engageable by melee
MELEE_MAX_PER_TARGET = 1   # max melee attackers per ranged target
MELEE_VS_MELEE_MAX = 2     # soft cap for melee-vs-melee targeting
```

## New Functions

### `_assign_targets_melee_capped(my_alive, enemy_alive, tick)`

- Calculates `engageable_count = max(1, len(enemy_alive) // 2)`
- Selects `engageable_count` targets from `enemy_alive` using rotating offset: `start = tick % len(enemy_alive)`
- Assigns 1 melee attacker per engageable target
- Returns dict mapping attacker_idx -> target_idx (surplus melee get no entry)

### `_assign_targets_spread_capped(my_alive, enemy_alive)`

- Same as `_assign_targets_spread()` but caps at `MELEE_VS_MELEE_MAX` attackers per target
- Surplus attackers wrap to next target

## Integration

### `simulate_battle()` (lines 966-973)

Target assignment logic changes from:

```python
if is_ranged1:
    targets1 = _assign_targets_focus(...)
else:
    targets1 = _assign_targets_spread(...)
```

To:

```python
if is_ranged1:
    targets1 = _assign_targets_focus(...)
elif is_ranged2:  # melee attacking ranged
    targets1 = _assign_targets_melee_capped(alive1, alive2, tick)
else:  # melee attacking melee
    targets1 = _assign_targets_spread_capped(alive1, alive2)
```

Mirror logic for team 2.

### Idle handling

Units with no assigned target hit the existing `if target_idx < 0: continue` check (line 1093) and naturally skip. No changes to attack logic needed.

### Opening volley

No changes. Opening volleys model the ranged-vs-melee closing phase where melee isn't attacking yet. Engagement slots only apply during Phase 2 tick loop.

### `simulate_mixed_battle()`

Same capped targeting logic applied for melee units attacking ranged enemies.

## Expected Impact

| Matchup | Before | Expected After |
|---------|--------|----------------|
| 30 Champ vs 30 Arb | Champ barely wins (0.7 HP) | Arb likely wins or much closer |
| 30 Knight vs 30 Xbow | Knight wins easily | Knight wins but takes more losses |
| 10 Hussar vs 30 Arb | Hussar loses | Hussar loses harder |
| 30 Champ vs 30 Paladin | Paladin wins | Similar (2:1 cap minimal effect at equal numbers) |
| 5v5 small battles | Various | Nearly unchanged (small numbers, all can engage) |

All battle scores for melee-vs-ranged matchups will shift. `compute_battle_scores.py` must be re-run.

## Testing

1. Verify `_assign_targets_melee_capped()` returns exactly `min(melee_alive, engageable_count)` assignments
2. Verify rotation: different archers targeted across consecutive ticks
3. Integration: 30 champ vs 30 arb shows improved arb performance
4. Sanity: 5v5 battles behave similarly to before
5. Re-run battle scores and spot-check rankings

## Files Changed

- `webapp/simulation.py` -- new targeting functions, updated target assignment
- `webapp/compute_battle_scores.py` -- re-run only (no code changes)
