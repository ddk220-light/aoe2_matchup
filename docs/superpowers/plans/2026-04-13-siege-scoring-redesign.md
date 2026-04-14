# Siege Scoring Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-castle siege scoring with 6-simulation framework (3 civs × 2 resource modes), add Tarkan to siege rankings, and update hover card with per-castle breakdown.

**Architecture:** `compute_battle_scores.py` drives all scoring changes — new `CASTLE_TARGETS` list, rewritten `compute_siege_antibuilding_scores()`, and slug-based fixed-count lookup. `unit_lines.py` gets a new standalone "tarkan" line. `rankings.js` hover card is updated with 6 sub-score keys.

**Tech Stack:** Python 3, SQLite (`webapp/aoe2_units.db`), vanilla JS (`rankings.js`)

---

## File Map

| File | Change |
|---|---|
| `webapp/compute_battle_scores.py` | Replace `SIEGE_CASTLE_TARGET` → `CASTLE_TARGETS`; rewrite `compute_siege_antibuilding_scores()`; update `SIEGE_SCORE_TYPES`; add `SIEGE_FIXED_COUNT_SLUGS`; add "tarkan" to `SIEGE_LINE_SLUGS` |
| `webapp/unit_lines.py` | Add standalone `"tarkan"` entry to `UNIT_LINES` |
| `webapp/static/js/rankings.js` | Update `SCORE_KEYS` and `SCORE_BREAKDOWN` for 6 new sub-score pairs; update siege hover card renderer |
| `webapp/aoe2_units.db` | Regenerated via `python3 compute_battle_scores.py` |
| `tests/test_siege_scoring.py` | New test file for castle stats, simulation returns, effective-TTK formula |

---

## Task 0: Verify castle stats against wiki

**Goal:** Confirm the exact HP, armor, range, arrow attack for each of the 3 castle targets before hardcoding them.

**Files:** `webapp/compute_battle_scores.py` (read only), wiki research

- [ ] **Step 1: Run the verification script**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 << 'EOF'
import json

with open('extraction/extracted_data/civ_tech_trees.json') as f:
    trees = json.load(f)
with open('extraction/extracted_data/tech_effects.json') as f:
    te = json.load(f)
with open('extraction/extracted_data/technologies.json') as f:
    techs = json.load(f)

tech_name_map = {t['id']: t['name'] for t in techs}

# Key tech IDs affecting castles
CASTLE_TECH_IDS = {
    50: ('masonry',     'hp_mult', 1.10),
    51: ('arch',        'hp_mult', 1.10),
    379:('hoardings',   'hp_mult', 1.21),
    199:('fletching',   'range+attack', 1),
    200:('bodkin',      'range+attack', 1),
    201:('bracer',      'range+attack', 1),
    47: ('chemistry',   'attack', 1),
    482:('stronghold',  'reload_mult', 0.75),
    11: ('crenellations','range', 3),
}

for civ in trees:
    if civ['name'] not in ['Persians', 'Teutons', 'Byzantines']:
        continue
    disabled = {t['id'] for t in civ.get('disabled_techs', [])}
    available = {tid: v for tid, v in CASTLE_TECH_IDS.items() if tid not in disabled}
    print(f"\n{civ['name']}: available castle techs = {[v[0] for v in available.values()]}")

# Check Teuton +2 melee armor civ bonus tech
print("\nSearching for Teuton castle melee armor civ bonus...")
for entry in te:
    tname = tech_name_map.get(entry['tech_id'], '')
    if 'teuton' not in tname.lower():
        continue
    for cmd in entry['commands']:
        if cmd.get('a') == 82 and cmd.get('c') == 8:  # unit 82, armor attribute
            print(f"  {tname}: armor class={cmd.get('d')} amount={cmd.get('d')}")

# Check Byzantine building HP civ bonus
print("\nSearching for Byzantine building HP civ bonus (class 3 HP mult)...")
for entry in te:
    tname = tech_name_map.get(entry['tech_id'], '')
    if 'byzantine' not in tname.lower():
        continue
    for cmd in entry['commands']:
        if cmd.get('b') == 3 and cmd.get('c') == 0:  # building class, HP attr
            print(f"  {tname}: HP mult={cmd.get('d')}")
EOF
```

- [ ] **Step 2: Cross-check with AoE2 wiki**

Open https://ageofempires.fandom.com/wiki/Castle_(Age_of_Empires_II) and verify:
- Persian castle HP with Masonry + Architecture + Hoardings (should be 7028)
- Teuton castle: +2 melee armor civ bonus? Crenellations range? Missing Architecture?
- Byzantine castle: building HP bonus per age? Heated Shot availability?
- Persian: any bonus attack vs siege/rams beyond base class 13?

Record confirmed values here before proceeding to Task 1. The values in `CASTLE_TARGETS` (Task 2) **must match** what the wiki and dat both confirm.

---

## Task 1: Update `_simulate_siege_vs_castle` to return `(ttk, dmg_fraction)`

**Files:**
- Modify: `webapp/compute_battle_scores.py:1422-1462`
- Test: `tests/test_siege_scoring.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_siege_scoring.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import pytest
from compute_battle_scores import _simulate_siege_vs_castle


def test_winner_returns_actual_ttk_and_full_damage():
    """Castle destroyed → (actual_ttk, 1.0)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=5, unit_hp=200, unit_dps=50,
        castle_hp=1000, castle_dps=0,
        unit_speed=1.0, unit_range=10, castle_range=8,
    )
    # 1000 hp / (5 * 50 dps) = 4.0 s
    assert dmg == 1.0
    assert abs(ttk - 4.0) < 0.2


def test_loser_returns_600_and_partial_damage():
    """Units die before castle → (600.0, partial_fraction)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=1, unit_hp=10, unit_dps=1,
        castle_hp=100_000, castle_dps=100,  # castle kills unit instantly
        unit_speed=1.0, unit_range=10, castle_range=8,
    )
    assert ttk == 600.0
    assert 0.0 <= dmg < 1.0


def test_outranges_castle_always_wins():
    """Unit outranges castle → can never die, always wins"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=5, unit_hp=100, unit_dps=20,
        castle_hp=500, castle_dps=999,  # castle fires but can't reach
        unit_speed=1.0, unit_range=15, castle_range=8,
    )
    assert dmg == 1.0
    assert ttk < 600.0


def test_outranges_castle_slow_kill_returns_loss():
    """Unit outranges but takes too long → (600.0, damage_fraction)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=1, unit_hp=100, unit_dps=0.01,
        castle_hp=100_000, castle_dps=0,
        unit_speed=1.0, unit_range=15, castle_range=8,
    )
    assert ttk == 600.0
    assert 0.0 < dmg < 1.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m pytest tests/test_siege_scoring.py -v
```

Expected: 4 failures — `_simulate_siege_vs_castle` currently returns a scalar, not a tuple.

- [ ] **Step 3: Update `_simulate_siege_vs_castle` signature and return**

In `webapp/compute_battle_scores.py`, replace lines 1422–1462:

```python
def _simulate_siege_vs_castle(n_units, unit_hp, unit_dps, castle_hp,
                               castle_dps, unit_speed, unit_range, castle_range):
    """Tick-based attrition sim: units attack a castle that fires back.

    Returns (time_seconds, damage_fraction) where:
      - time_seconds: actual TTK if castle destroyed, else 600.0
      - damage_fraction: castle HP destroyed / castle_hp (1.0 = win)
    """
    DT = 0.1
    MAX_TIME = 600.0

    remaining_hp = float(castle_hp)
    units_alive = n_units
    focused_unit_hp = float(unit_hp)
    time = 0.0

    # Fast path: unit outranges castle — castle arrows can't reach, no attrition
    if unit_range >= castle_range:
        total_dps = n_units * unit_dps
        if total_dps <= 0:
            return MAX_TIME, 0.0
        ttk = castle_hp / total_dps
        if ttk <= MAX_TIME:
            return round(ttk, 1), 1.0
        dmg = min(1.0, total_dps * MAX_TIME / castle_hp)
        return MAX_TIME, round(dmg, 4)

    # Closing time: units walk into range while castle fires
    closing_distance = castle_range - unit_range
    closing_time = closing_distance / unit_speed if unit_speed > 0 else MAX_TIME

    while time < closing_time and units_alive > 0:
        focused_unit_hp -= castle_dps * DT
        if focused_unit_hp <= 0:
            units_alive -= 1
            if units_alive > 0:
                focused_unit_hp = float(unit_hp)
        time += DT

    # Combat phase
    while remaining_hp > 0 and units_alive > 0 and time < MAX_TIME:
        focused_unit_hp -= castle_dps * DT
        if focused_unit_hp <= 0:
            units_alive -= 1
            if units_alive > 0:
                focused_unit_hp = float(unit_hp)

        remaining_hp -= units_alive * unit_dps * DT
        time += DT

    dmg_fraction = min(1.0, round((castle_hp - max(0.0, remaining_hp)) / castle_hp, 4))

    if remaining_hp <= 0:
        return round(time, 1), 1.0
    return MAX_TIME, dmg_fraction
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_siege_scoring.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_siege_scoring.py webapp/compute_battle_scores.py
git commit -m "feat: update _simulate_siege_vs_castle to return (ttk, dmg_fraction)"
```

---

## Task 2: Define `CASTLE_TARGETS` replacing `SIEGE_CASTLE_TARGET`

**Files:**
- Modify: `webapp/compute_battle_scores.py:1385-1405`
- Test: `tests/test_siege_scoring.py`

- [ ] **Step 1: Write failing tests for castle target structure**

Append to `tests/test_siege_scoring.py`:

```python
from compute_battle_scores import CASTLE_TARGETS


def test_castle_targets_has_three_entries():
    assert len(CASTLE_TARGETS) == 3
    names = {c["name"] for c in CASTLE_TARGETS}
    assert names == {"persian", "teuton", "byzantine"}


def test_castle_targets_required_keys():
    required = {"name", "hp", "armor", "arrows", "arrow_attack", "arrow_range", "reload"}
    for ct in CASTLE_TARGETS:
        assert required.issubset(ct.keys()), f"{ct['name']} missing keys"


def test_teuton_highest_range():
    """Teuton castle has Crenellations (+3 range)"""
    by_name = {c["name"]: c for c in CASTLE_TARGETS}
    assert by_name["teuton"]["arrow_range"] > by_name["persian"]["arrow_range"]
    assert by_name["teuton"]["arrow_range"] > by_name["byzantine"]["arrow_range"]


def test_persian_highest_hp():
    """Persians have Masonry + Architecture + Hoardings — highest HP"""
    by_name = {c["name"]: c for c in CASTLE_TARGETS}
    assert by_name["persian"]["hp"] >= by_name["teuton"]["hp"]
    assert by_name["persian"]["hp"] >= by_name["byzantine"]["hp"]


def test_stronghold_applied_all_castles():
    """Stronghold is universal — all castles reload in 1.5s, not 2.0s"""
    for ct in CASTLE_TARGETS:
        assert ct["reload"] == pytest.approx(1.5, abs=0.05), \
            f"{ct['name']} reload={ct['reload']}, expected 1.5"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest tests/test_siege_scoring.py::test_castle_targets_has_three_entries -v
```

Expected: `ImportError` or `AttributeError` — `CASTLE_TARGETS` doesn't exist yet.

- [ ] **Step 3: Replace `SIEGE_CASTLE_TARGET` with `CASTLE_TARGETS`**

In `webapp/compute_battle_scores.py`, replace the entire `SIEGE_CASTLE_TARGET` block (lines ~1385–1405):

```python
# ===== Siege anti-building scoring =====
#
# Three fully-upgraded Imperial castles. Values derived from:
#   - Base castle (unit 82): HP=4800, pierce=11, melee=8, std_bldg=8, range=8, reload=2.0
#   - Universal techs (all civs): Masonry(HP×1.10, armor +1/+1/+3), Architecture(same),
#     Hoardings(HP×1.21 for castles), Fletching/Bodkin/+range+1/+atk+1 each,
#     Chemistry(+1 atk), Stronghold(reload×0.75→1.5s)
#   - NOTE: std_bldg armor (class 11) base is 8 (from dat), NOT 0. Previous
#     code had this wrong (was computing 0+3+3=6 instead of 8+3+3=14).
#
# IMPORTANT: Verify these values against the AoE2 wiki before shipping.
# See spec: docs/superpowers/specs/2026-04-13-siege-scoring-redesign.md §1
CASTLE_TARGETS = [
    {
        "name": "persian",
        # Techs: Masonry(×1.10) × Architecture(×1.10) × Hoardings(×1.21) = ×1.4641
        # No Bracer (disabled for Persians). Stronghold (universal): reload×0.75.
        # TODO: verify if Persian castle has bonus attack vs siege (class 13/27)
        "hp": 7028,            # 4800 × 1.10 × 1.10 × 1.21
        "armor": {
            3:  13,            # pierce: 11 + 1(Masonry) + 1(Architecture)
            4:  10,            # melee:  8  + 1 + 1
            11: 14,            # std_building: 8 + 3(Masonry) + 3(Architecture)
            21: 0,
        },
        "arrows":      5,
        "arrow_attack": 14,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Chemistry); no Bracer
        "arrow_range":  10,   # 8  + 1(Fletching) + 1(Bodkin); no Bracer
        "reload":      1.5,   # 2.0 × 0.75 (Stronghold)
    },
    {
        "name": "teuton",
        # Techs: Masonry(×1.10) × Hoardings(×1.21); NO Architecture (disabled).
        # Civ bonus: +2 melee armor on castles.
        # Crenellations (Teuton unique, tech 11): +3 range.
        # No Bracer (disabled). Stronghold (universal).
        # TODO: verify Teuton civ bonus melee armor source (tech ID)
        "hp": 6389,            # 4800 × 1.10 × 1.21
        "armor": {
            3:  12,            # pierce: 11 + 1(Masonry); no Architecture
            4:  12,            # melee:  8  + 1(Masonry) + 2(civ bonus); no Architecture
            11: 11,            # std_building: 8 + 3(Masonry); no Architecture
            21: 0,
        },
        "arrows":      5,
        "arrow_attack": 14,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Chemistry); no Bracer
        "arrow_range":  13,   # 8 + 1(Fletching) + 1(Bodkin) + 3(Crenellations); no Bracer
        "reload":      1.5,
    },
    {
        "name": "byzantine",
        # Techs: Hoardings(×1.21) ONLY — Masonry AND Architecture both disabled.
        # Has Bracer. Heated Shot disabled in current dat (tech 380 in disabled list).
        # Stronghold (universal).
        # TODO: verify Byzantine building HP civ bonus (+10%/age) applies to castles
        #       — if confirmed, hp = round(4800 × 1.21 × 1.30) = 7550
        "hp": 5808,            # 4800 × 1.21; no Masonry, no Architecture
        "armor": {
            3:  13,            # pierce: 11 + 1(Fletching) + 1(Bodkin) + 1(Bracer)
            4:  8,             # melee:  8 base; no Masonry/Architecture
            11: 8,             # std_building: 8 base; no Masonry/Architecture
            21: 0,
        },
        "arrows":      5,
        "arrow_attack": 15,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Bracer) + 1(Chemistry)
        "arrow_range":  11,   # 8  + 1 + 1 + 1(Bracer)
        "reload":      1.5,
    },
]
```

- [ ] **Step 4: Run new tests**

```bash
python3 -m pytest tests/test_siege_scoring.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py tests/test_siege_scoring.py
git commit -m "feat: replace SIEGE_CASTLE_TARGET with 3-civ CASTLE_TARGETS"
```

---

## Task 3: Add standalone "tarkan" line to `unit_lines.py`

**Files:**
- Modify: `webapp/unit_lines.py`
- Test: `tests/test_siege_scoring.py`

**Context:** Tarkan currently lives inside the `knight` line as Huns' unique unit. It has no standalone entry. Siege scoring uses `build_line_units(line_slug, age)` which needs a UNIT_LINES key to find units. We add a minimal "tarkan" entry so siege scoring can find it — this doesn't affect the knight line's cavalry scoring.

- [ ] **Step 1: Write failing test**

Append to `tests/test_siege_scoring.py`:

```python
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
from unit_lines import UNIT_LINES
from compute_battle_scores import SIEGE_LINE_SLUGS


def test_tarkan_line_exists_in_unit_lines():
    assert "tarkan" in UNIT_LINES, "tarkan must have a standalone UNIT_LINES entry"


def test_tarkan_line_in_siege_line_slugs():
    assert "tarkan" in SIEGE_LINE_SLUGS
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest tests/test_siege_scoring.py::test_tarkan_line_exists_in_unit_lines -v
```

Expected: AssertionError.

- [ ] **Step 3: Add "tarkan" entry to `unit_lines.py`**

Find the section in `webapp/unit_lines.py` where UNIT_LINES is defined (near the end of the stable/cavalry entries). Add after the `"steppe_lancer"` entry or at the end of the stable section:

```python
    "tarkan": {
        # Standalone entry for siege anti-building scoring.
        # Tarkan (Huns unique) — replaces knight line for Huns.
        # Only Huns have this unit; no generic base slug.
        "castle_slug": "tarkan_huns",
        "imperial_slug": "elite_tarkan_huns",
        "unique_units": {},
    },
```

- [ ] **Step 4: Add "tarkan" to `SIEGE_LINE_SLUGS` in `compute_battle_scores.py`**

Find line ~636 and update:

```python
SIEGE_LINE_SLUGS = ["ram", "trebuchet", "bombard_cannon", "cannon_galleon", "tarkan"]
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/test_siege_scoring.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/unit_lines.py webapp/compute_battle_scores.py tests/test_siege_scoring.py
git commit -m "feat: add standalone tarkan line to unit_lines, add to SIEGE_LINE_SLUGS"
```

---

## Task 4: Add effective-TTK formula + fixed-count lookup

**Files:**
- Modify: `webapp/compute_battle_scores.py`
- Test: `tests/test_siege_scoring.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_siege_scoring.py`:

```python
from compute_battle_scores import _effective_ttk, _get_siege_fixed_count


def test_effective_ttk_winner():
    """Winner: effective TTK = actual TTK"""
    assert _effective_ttk(actual_ttk=150.0, dmg_fraction=1.0, max_winner_ttk=300.0) == 150.0


def test_effective_ttk_loser():
    """Loser: (max_winner + 200) / dmg_fraction"""
    result = _effective_ttk(actual_ttk=600.0, dmg_fraction=0.5, max_winner_ttk=300.0)
    assert result == pytest.approx((300.0 + 200) / 0.5)


def test_effective_ttk_zero_damage_fallback():
    """Zero damage: fallback to 600"""
    result = _effective_ttk(actual_ttk=600.0, dmg_fraction=0.0, max_winner_ttk=300.0)
    assert result == 600.0


def test_get_siege_fixed_count_default():
    assert _get_siege_fixed_count("bombard_cannon_koreans") == 5


def test_get_siege_fixed_count_fire_archer():
    assert _get_siege_fixed_count("fire_archer_wu") == 30
    assert _get_siege_fixed_count("elite_fire_archer_wu") == 30


def test_get_siege_fixed_count_tarkan():
    assert _get_siege_fixed_count("tarkan_huns") == 30
    assert _get_siege_fixed_count("elite_tarkan_huns") == 30
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest tests/test_siege_scoring.py::test_effective_ttk_winner tests/test_siege_scoring.py::test_get_siege_fixed_count_default -v
```

Expected: ImportError — functions don't exist yet.

- [ ] **Step 3: Add helper functions to `compute_battle_scores.py`**

Add just before `compute_siege_antibuilding_scores()` (after `SIEGE_SCORE_TYPES`):

```python
# Slugs (substring match) that use 30 fixed units instead of 5
_SIEGE_FIXED_30_SLUGS = ("fire_archer", "tarkan")


def _get_siege_fixed_count(unit_slug: str) -> int:
    """Return fixed unit count for a siege simulation."""
    for pattern in _SIEGE_FIXED_30_SLUGS:
        if pattern in unit_slug:
            return 30
    return 5


def _effective_ttk(actual_ttk: float, dmg_fraction: float, max_winner_ttk: float) -> float:
    """Convert a single (ttk, dmg_fraction) result into a comparable effective TTK.

    Winners (dmg_fraction == 1.0): return actual TTK.
    Losers: (max_winner_ttk + 200) / dmg_fraction, penalising failures.
    Zero damage fallback: 600.0.
    """
    if dmg_fraction >= 1.0:
        return actual_ttk
    if dmg_fraction <= 0.0:
        return 600.0
    return (max_winner_ttk + 200.0) / dmg_fraction
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_siege_scoring.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py tests/test_siege_scoring.py
git commit -m "feat: add _effective_ttk and _get_siege_fixed_count helpers"
```

---

## Task 5: Rewrite `compute_siege_antibuilding_scores` for 6-sim loop

**Files:**
- Modify: `webapp/compute_battle_scores.py:1465-1565`

This is the core change. The function runs 6 simulations per unit, stores 12 sub-score values (6 TTKs + 6 dmg fractions), computes avg effective TTK, then normalises.

- [ ] **Step 1: Update `SIEGE_SCORE_TYPES`**

Find `SIEGE_SCORE_TYPES` (~line 1402) and replace:

```python
SIEGE_SCORE_TYPES = [
    "anti_building_score",
    # Per-castle, per-mode raw TTK (seconds)
    "ab_persian_5u_ttk",   "ab_persian_5k_ttk",
    "ab_teuton_5u_ttk",    "ab_teuton_5k_ttk",
    "ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
    # Per-castle, per-mode damage fraction (0.0–1.0; 1.0 = castle destroyed)
    "ab_persian_5u_dmg",   "ab_persian_5k_dmg",
    "ab_teuton_5u_dmg",    "ab_teuton_5k_dmg",
    "ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
]
```

- [ ] **Step 2: Write the new `compute_siege_antibuilding_scores`**

Replace the entire function body (lines ~1465–1565):

```python
def compute_siege_antibuilding_scores():
    """Compute anti-building scores for all siege units (Castle + Imperial).

    Each unit runs 6 simulations: 3 castle targets × 2 resource modes.
    Mode "5u": fixed 5 units (30 for fire_archer / tarkan).
    Mode "5k": max(1, 5000 // unit_cost) units.

    Scoring:
      effective_TTK = actual_TTK if castle destroyed
                    = (max_winner_TTK + 200) / dmg_fraction  if units die first
      anti_building_score = inverse-normalised avg(6 effective_TTKs), 0-100.

    Returns dict in write_role_scores_to_db format.
    """
    # ---- Pass 1: collect raw sim results ----
    # raw[(line_slug, age)] = { sk: { "sims": [(castle_name, mode, ttk, dmg), ...],
    #                                 "_speed": float, "_cost": float } }
    raw = {}

    for age in ["castle", "imperial"]:
        is_imperial = age == "imperial"

        for line_slug in SIEGE_LINE_SLUGS:
            units = build_line_units(line_slug, age)
            if not units:
                continue

            for u in units:
                cu = u["combat_unit"]
                unit_cost = calc_weighted_cost(
                    cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
                )
                unit_cost = max(1, unit_cost)

                attacks = cu.get("attacks", {})

                sims = []
                for ct in CASTLE_TARGETS:
                    damage_per_hit = _calc_building_damage(attacks, ct["armor"])

                    # Dromon extra projectiles = independent fire bolts vs buildings
                    if "dromon" in u["unit_slug"]:
                        extra_proj = cu.get("extra_projectiles", 0) or 0
                        if extra_proj > 0:
                            damage_per_hit *= (1 + extra_proj)

                    reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0
                    unit_dps = damage_per_hit / reload_time

                    # Fire Archer Wu: Red Cliffs Tactics adds 1.0 building DPS
                    if "fire_archer_wu" in u["unit_slug"]:
                        unit_dps += 1.0

                    outranges = cu["attack_range"] > ct["arrow_range"]
                    dmg_per_arrow = max(1, ct["arrow_attack"] - cu["pierce_armor"])
                    castle_dps = ct["arrows"] * dmg_per_arrow / ct["reload"]

                    for mode in ["5u", "5k"]:
                        if mode == "5u":
                            n_units = _get_siege_fixed_count(u["unit_slug"])
                        else:
                            n_units = max(1, 5000 // unit_cost)

                        if outranges:
                            total_dps = n_units * unit_dps
                            if total_dps > 0 and ct["hp"] / total_dps <= 600.0:
                                ttk, dmg = round(ct["hp"] / total_dps, 1), 1.0
                            else:
                                dmg = min(1.0, total_dps * 600.0 / ct["hp"]) if total_dps > 0 else 0.0
                                ttk = 600.0
                        else:
                            ttk, dmg = _simulate_siege_vs_castle(
                                n_units, cu["hp"], unit_dps, ct["hp"], castle_dps,
                                cu["movement_speed"], cu["attack_range"], ct["arrow_range"],
                            )

                        sims.append((ct["name"], mode, ttk, dmg))

                sk = f"{u['civ_name']}|{u['unit_slug']}"
                raw.setdefault((line_slug, age), {})[sk] = {
                    "sims": sims,
                    "_speed": cu["movement_speed"],
                    "_cost": unit_cost,
                }

    # ---- Pass 2: compute max winner TTK per (line_slug, age, castle_name, mode) ----
    max_winner = {}  # key -> max actual TTK among units that killed the castle
    for (line_slug, age), units_data in raw.items():
        for sk, data in units_data.items():
            for castle_name, mode, ttk, dmg in data["sims"]:
                if dmg >= 1.0:
                    key = (line_slug, age, castle_name, mode)
                    max_winner[key] = max(max_winner.get(key, 0.0), ttk)

    # ---- Pass 3: effective TTK → average → store ----
    all_scores = {}
    for (line_slug, age), units_data in raw.items():
        group = {}
        for sk, data in units_data.items():
            eff_ttks = []
            sub = {}
            for castle_name, mode, ttk, dmg in data["sims"]:
                key = (line_slug, age, castle_name, mode)
                mw = max_winner.get(key, 600.0)
                eff = _effective_ttk(ttk, dmg, mw)
                eff_ttks.append(eff)
                sub[f"ab_{castle_name}_{mode}_ttk"] = round(ttk, 1)
                sub[f"ab_{castle_name}_{mode}_dmg"] = round(dmg, 4)

            sub["_avg_eff_ttk"] = sum(eff_ttks) / len(eff_ttks)
            sub["_speed"] = data["_speed"]
            group[sk] = sub
        all_scores[(line_slug, age)] = group

    # ---- Pass 4: normalise avg_eff_ttk → anti_building_score (0–100) ----
    for (line_slug, age), scores in all_scores.items():
        vals = [s["_avg_eff_ttk"] for s in scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1.0
        for s in scores.values():
            s["anti_building_score"] = round((hi - s["_avg_eff_ttk"]) / span * 100, 1)

    # ---- Pass 5: speed weighting (skip trebuchet — stationary) ----
    for (line_slug, age), scores in all_scores.items():
        if line_slug == "trebuchet":
            continue
        weighted = {}
        for sk, s in scores.items():
            weighted[sk] = s["anti_building_score"] * s["_speed"]
        vals = list(weighted.values())
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1.0
        for sk in scores:
            scores[sk]["anti_building_score"] = round(
                (weighted[sk] - lo) / span * 100, 1
            )

    # Cleanup temp keys
    for scores in all_scores.values():
        for s in scores.values():
            s.pop("_avg_eff_ttk", None)
            s.pop("_speed", None)

    result = {}
    for (line_slug, age), scores in all_scores.items():
        result[f"{line_slug}|{age}"] = scores
    return result
```

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass. Verify no regressions in other test files.

- [ ] **Step 4: Quick sanity check — run scoring and inspect output**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import sys; sys.path.insert(0, 'webapp')
from compute_battle_scores import compute_siege_antibuilding_scores
scores = compute_siege_antibuilding_scores()
# Print trebuchet imperial scores as a sanity check
key = 'trebuchet|imperial'
if key in scores:
    for sk, s in list(scores[key].items())[:3]:
        print(sk, '-> score=', s.get('anti_building_score'),
              'persian_5u_ttk=', s.get('ab_persian_5u_ttk'),
              'teuton_5u_dmg=', s.get('ab_teuton_5u_dmg'))
"
```

Expected: 3 units printed with non-null score and 12 sub-score keys each.

- [ ] **Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: rewrite compute_siege_antibuilding_scores for 3-castle 6-sim loop"
```

---

## Task 6: Regenerate battle scores database

**Files:**
- Regenerated: `webapp/aoe2_units.db`

- [ ] **Step 1: Run compute_battle_scores.py**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 compute_battle_scores.py
```

Expected output includes lines like:
```
Writing siege scores...
Done.
```

If errors appear, fix before proceeding.

- [ ] **Step 2: Verify new score keys are in DB**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_units.db')
cur = conn.cursor()
cur.execute(\"SELECT DISTINCT score_type FROM battle_scores WHERE score_type LIKE 'ab_%' LIMIT 20\")
print(cur.fetchall())
cur.execute(\"SELECT civ_name, unit_slug, score_value FROM battle_scores WHERE score_type='anti_building_score' AND line_slug='trebuchet' AND age='imperial' LIMIT 5\")
for row in cur.fetchall():
    print(row)
conn.close()
"
```

Expected: 12 distinct `ab_*` score types; 5 trebuchet rows with non-null scores.

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add webapp/aoe2_units.db
git commit -m "data: regenerate aoe2_units.db with multi-castle siege scores"
```

---

## Task 7: Update `rankings.js` hover card

**Files:**
- Modify: `webapp/static/js/rankings.js:163-226` (SCORE_BREAKDOWN, SCORE_KEYS)
- Modify: hover card renderer (search for `anti_building_score` usage in render functions)

- [ ] **Step 1: Update `SCORE_BREAKDOWN` siege entry**

In `rankings.js`, find the `anti_building_score` entry in `SCORE_BREAKDOWN` (~line 163) and replace:

```javascript
anti_building_score: {
    title: "Anti-Building Score",
    formula: "Avg of 6 simulations (Persian / Teuton / Byzantine castle × 5-unit / 5K-resource). Faster kill = higher score. Speed-weighted (non-trebuchet).",
    subs: [
        { key: "ab_persian_5u_ttk",    label: "vs Persian (5 units)" },
        { key: "ab_persian_5k_ttk",    label: "vs Persian (5K res)" },
        { key: "ab_teuton_5u_ttk",     label: "vs Teuton (5 units)" },
        { key: "ab_teuton_5k_ttk",     label: "vs Teuton (5K res)" },
        { key: "ab_byzantine_5u_ttk",  label: "vs Byzantine (5 units)" },
        { key: "ab_byzantine_5k_ttk",  label: "vs Byzantine (5K res)" },
    ],
    dmgKeys: {
        "ab_persian_5u_ttk":   "ab_persian_5u_dmg",
        "ab_persian_5k_ttk":   "ab_persian_5k_dmg",
        "ab_teuton_5u_ttk":    "ab_teuton_5u_dmg",
        "ab_teuton_5k_ttk":    "ab_teuton_5k_dmg",
        "ab_byzantine_5u_ttk": "ab_byzantine_5u_dmg",
        "ab_byzantine_5k_ttk": "ab_byzantine_5k_dmg",
    },
},
```

Also remove the now-unused `time_to_kill` entry in `SCORE_BREAKDOWN`:

```javascript
// DELETE this block:
time_to_kill: {
    title: "Time to Kill",
    formula: "...",
    subs: [],
},
```

- [ ] **Step 2: Update `SCORE_KEYS`**

Find `SCORE_KEYS` (~line 189) and update the `// Siege scores` section:

```javascript
// Siege scores
"anti_building_score",
"ab_persian_5u_ttk",   "ab_persian_5k_ttk",
"ab_teuton_5u_ttk",    "ab_teuton_5k_ttk",
"ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
"ab_persian_5u_dmg",   "ab_persian_5k_dmg",
"ab_teuton_5u_dmg",    "ab_teuton_5k_dmg",
"ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
```

Remove `"time_to_kill"` from `SCORE_KEYS`.

- [ ] **Step 3: Update hover card sub-score renderer**

Find where hover card sub-scores are rendered (search for `subs` in the hover card render function — look for `info.subs.forEach` or similar). The sub-score display needs to show `✗ XX%` for losses instead of a raw number.

Find the block that renders each sub-score value and update it to:

```javascript
// In the hover card sub-score rendering loop:
info.subs.forEach(sub => {
    const ttk = scores[sub.key];
    const dmgKey = info.dmgKeys && info.dmgKeys[sub.key];
    const dmg = dmgKey ? scores[dmgKey] : null;

    let displayVal;
    if (ttk == null) {
        displayVal = "—";
    } else if (dmg !== null && dmg < 1.0) {
        // Unit failed to kill castle — show damage % dealt
        displayVal = `✗ ${Math.round(dmg * 100)}%`;
    } else {
        displayVal = `${ttk}s`;
    }
    // ... render displayVal in the hover row ...
});
```

> **Note:** Find the actual render loop by searching for `info.subs` in rankings.js (~line 336). Adapt the above pattern to match the existing DOM structure — don't restructure the surrounding HTML.

- [ ] **Step 4: Verify hover card in browser**

Start the Flask app:
```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 app.py --port 5001
```

Open http://localhost:5001/rankings, filter to Siege, hover over a Trebuchet unit. Confirm:
- 6 sub-score rows visible (Persian/Teuton/Byzantine × 5u/5k)
- TTK shown in seconds for kills, `✗ XX%` for losses
- Score updates with civ selection

- [ ] **Step 5: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat: update rankings.js siege hover card with 3-castle sub-score breakdown"
```

---

## Task 8: Verify API passes new score keys through

**Files:**
- Verify: `webapp/app.py` — check that siege score keys are included in API responses

- [ ] **Step 1: Check what score keys the API currently returns for siege**

```bash
curl -s "http://localhost:5001/api/best-units?civ=Huns" | python3 -m json.tool | grep -A2 "anti_building\|ab_persian"
```

If `ab_persian_5u_ttk` is absent from the response, find the relevant API handler in `app.py` and check if there's a whitelist of score keys.

- [ ] **Step 2: If keys are missing, add them to the API response**

Search `app.py` for `anti_building_score` or `SIEGE_SCORE_TYPES`. If a hardcoded list of returned score keys exists, add the 12 new keys to it.

```python
# Example — if there's a SCORE_KEYS_TO_RETURN list:
SIEGE_SCORE_KEYS = [
    "anti_building_score",
    "ab_persian_5u_ttk", "ab_persian_5k_ttk",
    "ab_teuton_5u_ttk",  "ab_teuton_5k_ttk",
    "ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
    "ab_persian_5u_dmg", "ab_persian_5k_dmg",
    "ab_teuton_5u_dmg",  "ab_teuton_5k_dmg",
    "ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
]
```

If the API already passes all DB columns through (likely — check that first), no change is needed.

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit if changes were needed**

```bash
git add webapp/app.py
git commit -m "feat: expose new siege sub-score keys in API response"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] §1 Castle Targets — Task 2 defines CASTLE_TARGETS with wiki-verification TODOs
- [x] §2 Two simulation modes (5u / 5k) — Task 5 loop handles both
- [x] §2 Special counts (Fire Archer Wu + Tarkan = 30) — Task 4 `_get_siege_fixed_count`
- [x] §3 Effective TTK formula (winner / loser / zero-dmg) — Task 4 `_effective_ttk`
- [x] §3 Max winner TTK + 200 penalty — in `_effective_ttk`
- [x] §3 Edge case (no winner → fallback 600) — `max_winner.get(key, 600.0)` covers this
- [x] §4 Tarkan in Siege column — Tasks 3 + 5
- [x] §5 Hover card 6-row breakdown (TTK / ✗ dmg%) — Task 7
- [x] §5 SCORE_KEYS + SCORE_BREAKDOWN updated — Task 7
- [x] DB regeneration — Task 6

**Placeholder scan:** No TBD/TODO in code blocks except the `# TODO: verify` comments in CASTLE_TARGETS — these are intentional wiki-verification reminders, not incomplete implementations.

**Type consistency:** `_effective_ttk(actual_ttk, dmg_fraction, max_winner_ttk)` defined in Task 4 and called in Task 5 with matching argument names. `_get_siege_fixed_count(unit_slug)` defined Task 4, called Task 5. All consistent.
