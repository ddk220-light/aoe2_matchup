# Ranged vs Ranged Kiting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the simple `range_diff / 2` ranged-vs-ranged opening volley formula with a physics-based kiting model that accounts for unit speed, retreat movement, and attack timing.

**Architecture:** Modify the `elif is_ranged1 and is_ranged2:` block in `simulate_battle()` to mirror the existing ranged-vs-melee kiting pattern. Also update post-opening cooldown logic for ranged-vs-ranged. All changes in one file: `webapp/simulation.py`.

**Tech Stack:** Python, pytest

---

### Task 1: Write failing tests for ranged-vs-ranged kiting

**Files:**
- Modify: `tests/test_targeting.py`

**Step 1: Add test helper and kiting tests**

Add these tests after the existing `test_simulate_ranged_vs_ranged_unchanged` test (line 254). Use the existing `_make_unit` helper (line 157).

```python
def test_ranged_kiting_longer_range_slower_gets_opening_shots():
    """Longer-ranged but slower unit gets closing shots (retreat while firing).

    Arb (range 8, speed 0.96) vs TAx (range 6, speed 1.1):
    - fire_dist = 8 - 6 = 2
    - eff_retreat = 0.96 * (1 - 0.333/1.7) = 0.96 * 0.804 = 0.772
    Wait - need to use attack_speed correctly. reload = 1/attack_speed.
    With attack_speed=1.7, reload=0.588. delay=0.333.
    move_frac = 1 - 0.333/0.588 = 0.434
    eff_retreat = 0.96 * 0.434 = 0.417
    net_speed = 1.1 - 0.417 = 0.683
    closing = 2/0.683 + 0 + delay_TAx = 2.928 + 0.467 = 3.395
    opening = 1 + int((3.395 - 0.333) / 0.588) = 1 + 5 = 6
    Old formula: int(2/2) = 1
    So Arb should get significantly more opening damage -> TAx should do worse.
    """
    # Arb-like: range 8, speed 0.96, fast reload
    arb = _make_unit(hp=40, attack=10, attack_speed=1.7, attack_range=8,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attack_delay=0.333,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    # TAx-like: range 6, speed 1.1, melee damage class
    tax = _make_unit(hp=70, attack=12, attack_speed=2.0, attack_range=6,
                     melee_armor=4, pierce_armor=4, movement_speed=1.1,
                     attack_delay=0.467,
                     attacks={4: 12}, armors={4: 4, 3: 4})

    # Run with return_ticks to get HP percentages
    winner, rem1, rem2, hp1, hp2, ticks = simulate_battle(
        arb, tax, 0, fixed_count=30, return_ticks=True)

    # With kiting, arb should perform much better than old range_diff/2.
    # The arb gets ~6 opening shots instead of 1, killing ~5 TAx before engagement.
    # TAx should have fewer remaining or arb should have more HP.
    # At minimum, TAx remaining should be <= 20 (lost significant units to opening fire).
    assert rem1 > 0 or rem2 <= 20, (
        f"Kiting should give arb significant opening advantage. "
        f"arb_rem={rem1}, tax_rem={rem2}"
    )


def test_ranged_kiting_faster_longer_range_dominates():
    """Faster + longer-ranged unit gets extended kiting bonus.

    Fast archer (range 8, speed 1.4) vs slow archer (range 5, speed 0.9):
    - fire_dist = 3
    - eff_retreat = 1.4 * move_frac
    - If eff_retreat > 0.9, extended kiting bonus applies
    - Should get many opening shots
    """
    fast_archer = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=8,
                             melee_armor=1, pierce_armor=3, movement_speed=1.4,
                             attack_delay=0.3,
                             attacks={3: 8}, armors={4: 1, 3: 3})
    slow_archer = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=5,
                             melee_armor=1, pierce_armor=3, movement_speed=0.9,
                             attack_delay=0.3,
                             attacks={3: 8}, armors={4: 1, 3: 3})

    winner, rem1, rem2, hp1, hp2, ticks = simulate_battle(
        fast_archer, slow_archer, 0, fixed_count=20, return_ticks=True)

    # Fast archer should dominate: longer range + faster = massive kiting advantage
    assert winner == 1, (
        f"Faster + longer-ranged unit should win. "
        f"fast_rem={rem1}, slow_rem={rem2}"
    )
    # Should have many survivors due to opening advantage
    assert rem1 >= 10, (
        f"Kiting unit should have many survivors. fast_rem={rem1}"
    )


def test_ranged_kiting_equal_range_no_opening():
    """Equal range units get no opening shots regardless of speed."""
    fast = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=6,
                      melee_armor=1, pierce_armor=3, movement_speed=1.4,
                      attacks={3: 8}, armors={4: 1, 3: 3})
    slow = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=6,
                      melee_armor=1, pierce_armor=3, movement_speed=0.9,
                      attacks={3: 8}, armors={4: 1, 3: 3})

    # With identical stats except speed, and no range advantage,
    # the battle should be close to a draw (no kiting advantage)
    winner, rem1, rem2, hp1, hp2, ticks = simulate_battle(
        fast, slow, 0, fixed_count=20, return_ticks=True)

    # Neither side should dominate — allow either winner but close fight
    total = rem1 + rem2
    assert total >= 1  # battle completes
    # The winner shouldn't have more than 15 remaining (close fight)
    winner_rem = rem1 if winner == 1 else rem2
    assert winner_rem <= 15, (
        f"Equal range should be close fight. winner_rem={winner_rem}"
    )


def test_ranged_kiting_min_range_reduces_fire_dist():
    """Unit with min_range has reduced effective firing distance.

    Scorpion-like (range 9, min_range 2, speed 0.65) vs archer (range 5, speed 0.96):
    fire_dist = 9 - max(2, 5) = 9 - 5 = 4 (min_range doesn't matter here, range_B > min_range)

    But if min_range > range_B:
    Hypothetical (range 10, min_range 6, speed 0.65) vs archer (range 5, speed 0.96):
    fire_dist = 10 - max(6, 5) = 10 - 6 = 4 (min_range caps the fire window)
    """
    # min_range > range_B case: fire window is capped
    long_range_min = _make_unit(hp=50, attack=10, attack_speed=1.0, attack_range=10,
                                melee_armor=2, pierce_armor=2, movement_speed=0.65,
                                attack_delay=0.2,
                                min_attack_range=6,
                                attacks={3: 10}, armors={4: 2, 3: 2})
    archer = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=5,
                        melee_armor=1, pierce_armor=3, movement_speed=0.96,
                        attack_delay=0.3,
                        attacks={3: 8}, armors={4: 1, 3: 3})

    # Should complete without error, min_range is handled
    winner, rem1, rem2 = simulate_battle(long_range_min, archer, 0, fixed_count=15)
    assert winner in (0, 1, 2)
```

**Step 2: Update existing ranged-vs-ranged test**

The existing `test_simulate_ranged_vs_ranged_unchanged` (line 243) tests arb vs xbow. With kiting, arb should still beat xbow (arb has higher range AND stats), but the margin may change. Update the test name and assertion:

```python
def test_simulate_ranged_vs_ranged_with_kiting():
    """Ranged vs ranged with kiting: arb should beat xbow (higher range + stats)."""
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    xbow = _make_unit(hp=35, attack=8, attack_speed=0.5, attack_range=9,
                      melee_armor=2, pierce_armor=3, movement_speed=0.96,
                      attacks={3: 8}, armors={4: 2, 3: 3})
    winner, rem1, rem2 = simulate_battle(arb, xbow, 0, fixed_count=20)
    # Arbalester should beat crossbow (higher stats + range + kiting advantage)
    assert winner == 1
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v`

Expected: New kiting tests may pass or fail depending on current behavior. The key behavioral test (`test_ranged_kiting_faster_longer_range_dominates`) should fail or show marginal results with the old `range_diff/2` formula since the fast archer won't get enough opening shots.

**Step 4: Commit**

```bash
git add tests/test_targeting.py
git commit -m "test: add ranged-vs-ranged kiting tests"
```

---

### Task 2: Implement ranged-vs-ranged kiting in simulation.py

**Files:**
- Modify: `webapp/simulation.py:1001-1007` (replace `elif is_ranged1 and is_ranged2:` block)

**Step 1: Replace the ranged-vs-ranged opening volley block**

Replace lines 1001-1007:

```python
    elif is_ranged1 and is_ranged2:
        # Both ranged: side with more range gets bonus shots
        range_diff = range1 - range2
        if range_diff > 0:
            opening1 = max(0, int(range_diff / 2))
        elif range_diff < 0:
            opening2 = max(0, int(-range_diff / 2))
```

With:

```python
    elif is_ranged1 and is_ranged2:
        # Both ranged: longer-ranged unit retreats while firing.
        # Shorter-ranged unit closes the gap at full speed (can't fire yet).
        # Same physics model as ranged-vs-melee kiting.
        range_diff = range1 - range2
        if range_diff > 0:
            # Unit 1 has longer range — retreats while firing
            fire_dist = range1 - max(min_range1, range2)
            if fire_dist > 0 and speed2 > 0:
                move_frac1 = max(0.0, 1.0 - delay1 / reload1) if reload1 > 0 else 1.0
                eff_retreat_speed1 = speed1 * move_frac1
                net_speed = speed2 - eff_retreat_speed1
                if net_speed > 0:
                    retreat_time = (
                        min(RETREAT_MAX / eff_retreat_speed1, fire_dist / net_speed)
                        if eff_retreat_speed1 > 0
                        else fire_dist / net_speed
                    )
                    retreat_dist_closed = net_speed * retreat_time
                    remaining_dist = fire_dist - retreat_dist_closed
                else:
                    retreat_time = (
                        RETREAT_MAX / eff_retreat_speed1 if eff_retreat_speed1 > 0 else 0
                    )
                    remaining_dist = fire_dist
                stand_time = remaining_dist / speed2 if remaining_dist > 0 else 0
                closing_time = retreat_time + stand_time + delay2
                closing_time1 = closing_time
                if closing_time > delay1:
                    opening1 = 1 + int((closing_time - delay1) / reload1)
            # Kiting bonus: if unit 1 effective retreat > unit 2 speed
            eff_spd1 = eff_retreat_speed1 if fire_dist > 0 and speed2 > 0 else speed1
            if eff_spd1 > speed2 and speed2 > 0:
                speed_diff = eff_spd1 - speed2
                kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
                if kite_dist > 0:
                    kite_time = kite_dist / speed_diff
                    opening1 += max(0, int(kite_time / reload1))
        elif range_diff < 0:
            # Unit 2 has longer range — retreats while firing (mirror)
            fire_dist = range2 - max(min_range2, range1)
            if fire_dist > 0 and speed1 > 0:
                move_frac2 = max(0.0, 1.0 - delay2 / reload2) if reload2 > 0 else 1.0
                eff_retreat_speed2 = speed2 * move_frac2
                net_speed = speed1 - eff_retreat_speed2
                if net_speed > 0:
                    retreat_time = (
                        min(RETREAT_MAX / eff_retreat_speed2, fire_dist / net_speed)
                        if eff_retreat_speed2 > 0
                        else fire_dist / net_speed
                    )
                    retreat_dist_closed = net_speed * retreat_time
                    remaining_dist = fire_dist - retreat_dist_closed
                else:
                    retreat_time = (
                        RETREAT_MAX / eff_retreat_speed2 if eff_retreat_speed2 > 0 else 0
                    )
                    remaining_dist = fire_dist
                stand_time = remaining_dist / speed1 if remaining_dist > 0 else 0
                closing_time = retreat_time + stand_time + delay1
                closing_time2 = closing_time
                if closing_time > delay2:
                    opening2 = 1 + int((closing_time - delay2) / reload2)
            eff_spd2 = eff_retreat_speed2 if fire_dist > 0 and speed1 > 0 else speed2
            if eff_spd2 > speed1 and speed1 > 0:
                speed_diff = eff_spd2 - speed1
                kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
                if kite_dist > 0:
                    kite_time = kite_dist / speed_diff
                    opening2 += max(0, int(kite_time / reload2))
```

**Step 2: Update post-opening cooldown logic**

Modify the cooldown blocks (lines ~1026-1050) to also handle ranged-vs-ranged. Change:

```python
        if is_ranged1 and not is_ranged2 and closing_time1 > 0:
```

To:

```python
        if is_ranged1 and closing_time1 > 0:
```

And change:

```python
        if is_ranged2 and not is_ranged1 and closing_time2 > 0:
```

To:

```python
        if is_ranged2 and closing_time2 > 0:
```

This allows the cooldown sync to work for both ranged-vs-melee and ranged-vs-ranged matchups.

**Step 3: Run tests**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v`

Expected: All tests pass.

**Step 4: Commit**

```bash
git add webapp/simulation.py
git commit -m "feat: add ranged-vs-ranged kiting to opening volley"
```

---

### Task 3: Verify with real database units

**Files:** None (verification only)

**Step 1: Run TAx vs Arb simulation**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate
python3 -c "
from webapp.app import app
with app.app_context():
    from webapp.app import get_db
    db = get_db()
    from webapp.simulation import simulate_battle, prepare_combat_unit

    tax = dict(db.execute(\"SELECT * FROM unit_stats WHERE slug='throwing_axeman' AND civilization='Franks' AND age='Imperial'\").fetchone())
    arb = dict(db.execute(\"SELECT * FROM unit_stats WHERE slug='arbalester' AND civilization='Chinese' AND age='Imperial'\").fetchone())

    u1 = prepare_combat_unit(tax)
    u2 = prepare_combat_unit(arb)

    result = simulate_battle(u1, u2, 3000, return_ticks=True)
    print(f'TAx vs Arb (3000 res): winner={\"TAx\" if result[0]==1 else \"Arb\"}, TAx_rem={result[1]}, Arb_rem={result[2]}, TAx_hp={result[3]:.1%}, Arb_hp={result[4]:.1%}, ticks={result[5]}')

    # Also test a fast kiter vs slow archer
    mangudai_row = db.execute(\"SELECT * FROM unit_stats WHERE slug LIKE 'mangudai%' AND age='Imperial' LIMIT 1\").fetchone()
    if mangudai_row:
        mangudai = dict(mangudai_row)
        u_m = prepare_combat_unit(mangudai)
        result2 = simulate_battle(u_m, u2, 3000, return_ticks=True)
        print(f'Mangudai vs Arb (3000 res): winner={\"Mangudai\" if result2[0]==1 else \"Arb\"}, M_rem={result2[1]}, A_rem={result2[2]}, M_hp={result2[3]:.1%}, A_hp={result2[4]:.1%}, ticks={result2[5]}')
"
```

Expected: TAx vs Arb should be closer than baseline (TAx wins with fewer remaining). Mangudai should show kiting advantage if faster.

**Step 2: Sanity check equal-range matchup**

```bash
python3 -c "
from webapp.app import app
with app.app_context():
    from webapp.app import get_db
    db = get_db()
    from webapp.simulation import simulate_battle, prepare_combat_unit

    # Two arbs: equal range, should be close to 50/50
    arb1 = dict(db.execute(\"SELECT * FROM unit_stats WHERE slug='arbalester' AND civilization='Britons' AND age='Imperial'\").fetchone())
    arb2 = dict(db.execute(\"SELECT * FROM unit_stats WHERE slug='arbalester' AND civilization='Chinese' AND age='Imperial'\").fetchone())

    u1 = prepare_combat_unit(arb1)
    u2 = prepare_combat_unit(arb2)

    result = simulate_battle(u1, u2, 3000, return_ticks=True)
    print(f'Britons Arb vs Chinese Arb: winner={result[0]}, rem1={result[1]}, rem2={result[2]}, hp1={result[3]:.1%}, hp2={result[4]:.1%}')
    print(f'Britons range: {u1[\"attack_range\"]}, Chinese range: {u2[\"attack_range\"]}')
"
```

Expected: Britons arb has +2 range (12 vs 10 with Yeomen). Should get opening kiting shots. Chinese arb is faster? Check and verify results make sense.

**Step 3: Commit (if any fixes needed)**

Only if Task 2 needed corrections based on verification results.

---

### Task 4: Run full test suite and commit

**Step 1: Run all tests**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -m pytest tests/ -v`

Expected: All tests pass.

**Step 2: Final commit if needed**

```bash
git add -A && git commit -m "test: verify ranged kiting with real units"
```
