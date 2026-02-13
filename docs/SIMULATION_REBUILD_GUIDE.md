# Simulation Rebuild Guide (Backend + Frontend)

This focuses on combat logic quality and data nuances, not current architecture.

## 1. Core model to preserve

Combat is currently deterministic per tick with precomputed per-unit stats and mechanics.

Common model assumptions:
- Tick size: `0.1s`
- Damage-only backend sim does not use XY physics
- Frontend sim is XY/animation-oriented and not 1:1 deterministic with backend
- All mechanics should be read from data fields, not slug hardcoding in combat loop

## 2. Backend simulation mechanics currently represented

Backend (`webapp/simulation.py`) models:
- armor/bonus class damage (`attacks` vs `armors`)
- min range and ranged/melee behavior
- opening volley + kiting advantage
- focus fire vs spread targeting
- attack delay, reload, retarget delay
- accuracy + stray hits
- siege splash
- splash-on-hit
- pass-through
- extra and first-burst projectiles
- trample
- dodge shield + recharge
- bleed DOT
- HP regen
- block first melee
- attack bonus per kill
- hp-threshold transform
- dismount-on-death
- charge melee bonus + recharge
- armor stripping
- melee damage reflection
- nearby ally attack bonus
- nearby ally HP bonus
- pop-space scaling
- mixed-army simulation (simplified mechanic set)

## 3. Frontend simulation mechanics currently represented

Frontend (`templates/simulate.html`) includes:
- real-time movement/collision/kiting
- projectile travel
- attack/armor class damage and bonus breakdown
- extra projectiles and first-attack burst
- charge projectile attack
- splash, splash-on-hit, pass-through
- trample
- dodge shield
- bleed
- hp regen
- block first melee
- kill-based attack bonus

Not fully aligned with backend for several mechanics.

## 4. Known alignment risks between backend and frontend

If rebuilding, treat these as mandatory fix points:

1. Transform logic mismatch
- Backend switches to transform stat block.
- Frontend currently treats transform more like a buff trigger.

2. Missing/partial mechanics in frontend
- No true dismount state machine.
- No armor stripping model.
- No damage reflection model.
- Nearby HP/attack bonuses are not fully mirrored as backend precombat logic.

3. Mixed battle simplifications
- `simulate_mixed_battle` intentionally omits some mechanics.
- Ranking/matchup conclusions can drift from 1v1 full simulation expectations.

4. Randomness without seed control
- Accuracy/scatter randomness can produce unstable comparisons.
- Reproducibility is limited.

## 5. If starting over: better simulation design

### A. One combat rules engine, two adapters

Implement a shared combat core with:
- same hit resolution rules
- same mechanic modules
- same damage function

Then expose:
- backend fast mode (no XY)
- frontend visual mode (XY)

Visual mode should call the same damage resolution primitives, only differing in target acquisition and timing from movement.

### B. Data schema for mechanics should be explicit and typed

Instead of loosely optional numeric columns everywhere, define a typed mechanic payload per unit:
- `projectile`
- `trample`
- `splash`
- `shield`
- `bleed`
- `transform`
- `dismount`
- `charge`
- `reflect`
- `armor_strip`

All mechanics should have explicit defaults and validation.

### C. Determinism controls

Add seeded RNG support to all random branches:
- projectile miss/scatter
- trample proc chance
- target tie-breakers

Expose seed in API for reproducible tests and ranking jobs.

### D. Test by mechanic, not only by battle outcome

Build unit tests for:
- damage decomposition per class
- each special mechanic activation rule
- ordering rules (simultaneous damage, cooldown behavior)
- edge conditions (min-range siege, zero-cost units, pop-space < 1)

### E. Keep a parity test suite

Have a fixed set of matchup fixtures. For each fixture assert:
- winner
- remaining counts
- hp percentages
- ticks/time band

Run parity checks for:
- backend full sim
- backend mixed sim (expected drift documented)
- frontend headless sim (if possible)

## 6. Practical mechanic priorities for improved realism

If time is limited, implement in this order:
1. Deterministic damage core with class bonus correctness
2. projectile/extra/burst + splash rules
3. transform+dismount correctness
4. armor strip + reflect
5. movement-aware target geometry (frontend)
6. mixed-army consistency with full model

## 7. Performance guidance for reranking all unit lines

- Pre-parse combat units once (`prepare_combat_unit` equivalent cache)
- Memoize pair outcomes by full combat signature, not object identity
- Batch simulations and store deterministic seed
- Separate expensive visual simulation from ranking simulation
