# Siege Scoring Redesign — Multi-Castle, Multi-Mode

**Date:** 2026-04-13
**Status:** Approved

## Overview

Replace the single-castle, single-resource-budget siege scoring with a 6-simulation framework: 3 civ-specific castle targets × 2 resource modes (fixed count vs 5k resources). Add Tarkan to siege rankings. Update hover card to show per-castle breakdown.

## Motivation

The current scoring benchmarks against one generic "Spanish castle" and uses a single 1000-resource budget. This misses:
- Civ-specific defensive differences (Teuton Crenellations, Byzantine low HP, Persian full tech tree)
- How siege performs at both small-squad and large-army scale
- Units that die before killing the castle (treated as TTK=600s with no nuance)

---

## 1. Castle Targets

Replace `SIEGE_CASTLE_TARGET` with a `CASTLE_TARGETS` list of three dicts. Each represents a fully-upgraded Imperial-age castle for a specific civ, with all available techs researched.

```python
CASTLE_TARGETS = [
    {
        "name": "persian",
        # Techs: Masonry(×1.10) × Architecture(×1.10) × Hoardings(×1.21) = ×1.4641
        # No Bracer (disabled). Stronghold (universal tech): reload ×0.75.
        # Source: dat file tech_effects, verified against wiki.
        "hp": 7028,           # 4800 × 1.10 × 1.10 × 1.21
        "armor": {
            3:  13,           # pierce: 11 + 1(Masonry) + 1(Architecture)
            4:  10,           # melee: 8 + 1 + 1
            11: 14,           # std_building: 8 + 3(Masonry) + 3(Architecture)
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 14,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Chemistry); no Bracer
        "arrow_range": 10,    # 8 + 1 + 1; no Bracer
        "reload": 1.5,        # 2.0 × 0.75 (Stronghold, universal)
        # NOTE: Verify Persian attack-vs-siege bonus (class 13/27) and any
        # Heated Shot availability against wiki before finalising.
    },
    {
        "name": "teuton",
        # Techs: Masonry(×1.10) × Hoardings(×1.21) = ×1.331; NO Architecture (disabled).
        # Civ bonus: +2 melee armor on castles.
        # Crenellations (Teuton unique tech): +3 range.
        # No Bracer (disabled). Stronghold (universal).
        # Source: dat file tech_effects + disabled_techs list.
        "hp": 6389,           # 4800 × 1.10 × 1.21
        "armor": {
            3:  12,           # pierce: 11 + 1(Masonry); no Architecture
            4:  12,           # melee: 8 + 1(Masonry) + 1(civ bonus top +2) — verify exact
            11: 11,           # std_building: 8 + 3(Masonry); no Architecture
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 14,   # 11 + 1 + 1 + 1(Chemistry); no Bracer
        "arrow_range": 13,    # 8 + 1(Fletching) + 1(Bodkin) + 3(Crenellations); no Bracer
        "reload": 1.5,
        # NOTE: Confirm exact Teuton castle +2 melee armor tech source and
        # whether Crenellations also grants garrison-unit attacks.
    },
    {
        "name": "byzantine",
        # Techs: Hoardings(×1.21) only — Masonry AND Architecture both disabled.
        # Has Bracer. No Heated Shot (disabled in dat). Stronghold (universal).
        # Source: dat file disabled_techs list. Byzantine building HP civ bonus
        # needs wiki cross-check — may add extra HP multiplier.
        "hp": 5808,           # 4800 × 1.21; no Masonry, no Architecture
        "armor": {
            3:  13,           # pierce: 11 + 1(Fletching) + 1(Bodkin) + 1(Bracer) — no Masonry
            4:  8,            # melee: 8 base; no Masonry/Architecture
            11: 8,            # std_building: 8 base; no Masonry/Architecture
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 15,   # 11 + 1 + 1 + 1(Bracer) + 1(Chemistry)
        "arrow_range": 11,    # 8 + 1 + 1 + 1(Bracer)
        "reload": 1.5,
        # NOTE: Byzantine building HP bonus (+10% per age) may raise HP
        # to ~7550 if it applies to castles — verify against wiki.
        # Also verify whether Heated Shot is truly absent in current patch.
    },
]
```

### Implementation note — wiki verification checklist

Before finalising these constants, the implementer must cross-check:

1. **Persian castle attack-vs-siege** (class 13/27): does Mahouts or any civ bonus give the Persian castle extra attack vs rams/siege?
2. **Teuton +2 melee armor on castle**: which tech ID delivers this bonus?
3. **Byzantine building HP civ bonus**: does the "buildings +10% HP per age" apply to Castles? If yes, HP ≈ 7550.
4. **Byzantine Heated Shot**: the dat shows tech 380 disabled for Byzantines — confirm in latest patch.
5. **Stronghold (482) as universal tech**: confirm it applies to all civs (dat shows not disabled for any civ).

---

## 2. Simulation Modes

Each unit runs **6 simulations**: 3 castle targets × 2 resource modes.

### Fixed-count mode
| Unit | Fixed count |
|---|---|
| All siege units | 5 |
| Fire Archer Wu (`fire_archer_wu`) | 30 |
| Tarkan (all variants) | 30 |

### 5k-resource mode
```python
n_units = max(1, 5000 // unit_cost)
```
`unit_cost` uses the existing `calc_weighted_cost()` function (0.8×wood + 1×food + 1.5×gold).

Both modes use the existing `_simulate_siege_vs_castle()` function unchanged.

---

## 3. Scoring Formula

### Per-simulation: effective TTK

```
# Winner (castle hp reaches 0):
effective_TTK = actual_TTK

# Loser (all units die before castle is destroyed):
effective_TTK = (max_winner_TTK_in_group + 200) / damage_fraction
    where damage_fraction = total_damage_dealt / castle_hp
          max_winner_TTK_in_group = slowest actual_TTK among winning units
                                    in the same (line_slug, age, castle, mode) group

# Edge case (no unit in the group kills the castle):
effective_TTK = 600  # fallback cap
```

The `+200` penalty ensures losers score significantly worse than the slowest winner even at high damage fractions.

### Per-unit: average effective TTK

```
avg_effective_TTK = mean of all 6 effective_TTK values
```

### Normalization (per line_slug + age group)

```
lo = min(avg_effective_TTK across group)
hi = max(avg_effective_TTK across group)
span = hi - lo  (if 0, span = 1)
anti_building_score = round((hi - avg_effective_TTK) / span × 100, 1)
```

Lower average TTK → higher score (0–100). Speed weighting applied after normalization for non-trebuchet lines (same as current logic).

### Sub-score storage

The 6 individual effective TTKs are stored as:
- `ab_persian_5u`, `ab_persian_5k`
- `ab_teuton_5u`, `ab_teuton_5k`
- `ab_byzantine_5u`, `ab_byzantine_5k`

Plus a boolean/fraction per sub-score indicating whether the unit won or lost (for hover card rendering).

---

## 4. Tarkan in Siege Rankings

Add `"tarkan"` to `SIEGE_LINE_SLUGS` in `compute_battle_scores.py`.

`build_line_units("tarkan", age)` already works via the existing unit_lines infrastructure — Tarkan appears in `UNIT_LINES` under the stable line. If Tarkan is not currently in a siege-appropriate line, it must be added to `SIEGE_LINE_SLUGS` directly and `build_line_units` called with the correct slug.

Only Huns have Tarkan (castle age: Tarkan, imperial age: Elite Tarkan). Fixed count = 30.

No UI change needed — Tarkan rows appear in the Siege rankings column automatically.

---

## 5. Hover Card — Frontend Changes

### New DB score keys (add to `SIEGE_SCORE_TYPES`)

```python
SIEGE_SCORE_TYPES = [
    "anti_building_score",
    # Sub-score TTKs (effective TTK in seconds, stored for hover card)
    "ab_persian_5u_ttk",   "ab_persian_5k_ttk",
    "ab_teuton_5u_ttk",    "ab_teuton_5k_ttk",
    "ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
    # Damage fraction (0.0–1.0; 1.0 = castle destroyed, <1.0 = unit died first)
    "ab_persian_5u_dmg",   "ab_persian_5k_dmg",
    "ab_teuton_5u_dmg",    "ab_teuton_5k_dmg",
    "ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
]
```

Hover card logic: if `dmg == 1.0` → show TTK in seconds. If `dmg < 1.0` → show `✗ XX%`.

### Hover card layout

```
┌─ Anti-Building Breakdown ────────────────────┐
│                  5 units     5k resources     │
│  vs Persian       142s          89s           │
│  vs Teuton      ✗ 62%          115s           │
│  vs Byzantine     98s           61s           │
└──────────────────────────────────────────────┘
```

- Winning runs: display actual TTK in seconds (e.g. `142s`)
- Losing runs: display `✗ XX%` — the percentage of castle HP dealt
- Replaces current `time_to_kill` field in the siege hover card
- `SCORE_KEYS` and `SCORE_BREAKDOWN` in `rankings.js` must include the 6 sub-score keys

---

## 6. Files Changed

| File | Change |
|---|---|
| `webapp/compute_battle_scores.py` | Replace `SIEGE_CASTLE_TARGET` with `CASTLE_TARGETS` list; update `compute_siege_antibuilding_scores()` for 6-sim loop; add tarkan to `SIEGE_LINE_SLUGS`; add `SIEGE_SCORE_TYPES` entries |
| `webapp/aoe2_units.db` | Regenerated after score recomputation |
| `webapp/static/js/rankings.js` | Add 6 sub-score keys to `SCORE_KEYS`/`SCORE_BREAKDOWN`; update siege hover card renderer |
| `webapp/app.py` | Ensure new score keys pass through `api_siege` or `api_best_units` response |

### Files NOT changed
- `webapp/simulation.py` — `_simulate_siege_vs_castle()` is reused as-is
- `webapp/unit_lines.py` — Tarkan already exists; no line change needed (only `SIEGE_LINE_SLUGS`)
- Scoring formulas for infantry, archery, cavalry, naval — untouched

---

## 7. Out of Scope

- Changing castle arrow count for garrisoned units (stay with base 5 arrows)
- Making castle targets dynamic / DB-driven
- Adding more than 3 castle targets
- Changing the speed-weighting logic
