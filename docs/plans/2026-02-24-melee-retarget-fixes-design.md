# Melee Combat Simulation Fixes Design

## Problems

Three melee combat behaviors were unrealistic:

1. **Retarget delay after kills**: When a melee unit kills its target, it paid a full walk delay (`RETARGET_DIST / speed` ~1.4s) even when another enemy was already hitting it in melee range. In AoE2, units immediately switch to nearby attackers.

2. **Instant full engagement**: `_assign_targets_spread_capped` allowed `MELEE_VS_MELEE_MAX` (2) attackers per target from tick 0. In reality, melee groups form a front line — initially ~1 attacker per target, with surplus units pathing around to engage after ~2s.

3. **Kill bonus was wrong**: `attack_bonus_per_kill = 4` was treated as "+4 attack per kill, unlimited stacking". The correct AoE2 mechanic is "+1 attack per kill, capped at +4 total" (applies to Jaguar Warriors and Tiger Cavalry).

4. **Infantry vs cavalry stacking**: Infantry units can stack around larger cavalry hitboxes faster. The sim treated all melee-vs-melee the same.

## Fix 1: Skip retarget delay when being attacked

Each tick after target assignment, build reverse lookup maps showing which enemy targets each unit. When a melee unit needs to retarget, check if any alive enemy is already targeting it. If yes, switch to that attacker instantly (no walk delay). Applied to both `simulate_battle` and `simulate_mixed_battle`.

## Fix 2: Melee engagement ramp (1 → 2 after ~2s)

`_assign_targets_spread_capped` now takes `tick`, `initial_cap`, and `max_cap` params. For the first `MELEE_VS_MELEE_RAMP_TICKS` (20 ticks = 2.0s), cap at `initial_cap`. After that, allow `max_cap`. Equal-sized armies are unaffected (cap=1 still assigns all when n_attackers <= n_targets).

## Fix 3: Corrected kill bonus mechanic

`attack_bonus_per_kill` is now treated as the **max cap**. Each kill adds +1 attack, capped at the value. So `attack_bonus_per_kill = 4` means +1/+2/+3/+4 over 4 kills.

## Fix 4: Infantry vs cavalry stacking caps

New constants: `INF_VS_CAV_INITIAL_CAP = 2`, `INF_VS_CAV_MAX_CAP = 3`. When infantry (armor class 1) attacks cavalry (armor class 8), uses higher caps. Detection via armor classes in unit dicts.

## Results (28 EJW vs 37 Armenian Champion, 3k eco)

| Metric | Before all fixes | After all fixes |
|--------|-----------------|-----------------|
| Eco winner | Armenian Champion (6 survive) | E. Jaguar Warrior (10 survive, 11% HP) |
| Pop winner | EJW (30.7% HP) | EJW (30.7% HP) |
| Matchup advisor | Pop win only | Full win (both) |
