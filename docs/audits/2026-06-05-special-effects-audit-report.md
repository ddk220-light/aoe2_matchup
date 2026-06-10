# Special-Effects Audit Report — AoE2 Unit Analyzer
**Date:** 2026-06-05  
**Scope:** 13 special-effect mechanics across 25 unit variants  
**Sources:** AoE2 Fandom wiki (API wikitext fetches), SiegeEngineers se_data.json, extraction/extracted_data/*.json, local DB inspection

---

## 1. Summary

| Metric | Count |
|---|---|
| Mechanics audited | 13 |
| Data correct | 7 |
| Data wrong | 6 |
| Sim correct | 5 |
| Sim correct (partial / known gap) | 3 |
| Sim wrong | 5 |

**Confirmed issues by severity**

| Severity | Count |
|---|---|
| HIGH | 3 |
| MEDIUM | 7 |
| LOW | 3 |
| None / verified-correct | 4 |

> Adversarial review reversed two prior findings: Ballista Elephant pass-through (0.6667/0.6 is correct per dat) and Bolas Rider pass-through scope (applies to every shot, not charge-only). Those are listed under Verified-correct.

---

## 2. Confirmed Issues

### 2a. Issue Table (sorted by severity)

| Mechanic | Units | Data | Sim | What is wrong | Fix |
|---|---|---|---|---|---|
| **Centurion charge recharge time (Comitatenses)** | centurion_romans, elite_centurion_romans (also champion, legionary, paladin) | WRONG | WRONG | config stores 4.0 s (formula 1/rate); correct formula is charge_attack/rate = 5/0.25 = 20 s — charge fires 5× too often | `analysis/config_combat.py` lines 248–255: change all five entries to `charge_recharge_time: 20.0`; update comment line 244 |
| **Fire Lancer charge recharge + armor-ignore** | fire_lancer, elite_fire_lancer (5 civs) | WRONG | WRONG | (a) charge_recharge_time=0.0 in all rows; sim treats 0 as "never re-arm" so charge fires once then dies permanently. Should be 30.0 s. (b) charge_ignores_armor=1 stored but never read by simulation.py prepare_combat_unit; charge _calc_damage uses ignores_pierce=0 instead | (a) `analysis/config_combat.py` lines 84–85: add `charge_recharge_time: 30.0` to fire_lancer and elite_fire_lancer UNIQUE_COMBAT_PROPERTIES entries. (b) `webapp/simulation.py` prepare_combat_unit (~line 164): add `charge_ignores_armor` read; pass it into _calc_damage at lines 827–828 for charge projectile damage |
| **Fire Archer charge-always-ready + un-upgraded charge damage** | fire_archer_wu, elite_fire_archer_wu | WRONG | WRONG | (a) charge_recharge_time=0.0; wiki/dat say charge is permanently active (recharge_rate≈3.2e18 = infinite); sim fires charge once then disables it forever. (b) charge_projectile_attacks_json stores un-upgraded pierce (3:5 Castle, 3:5 Elite) instead of post-tech values (3:7 Castle / 3:10 Elite) | (a) `webapp/simulation.py`: treat charge_recharge_time=0 as "always ready" — skip the disable/re-arm cycle when recharge_time==0. (b) In generate_reference.py or generate_main_db.py: when writing charge_projectile_attacks for charge_type=6 units that share the primary projectile unit, apply the same tech deltas used for final_attacks_json |
| **Cataphract trample radius — Castle-age (pre-Logistica)** | cataphract_byzantines | WRONG | WRONG (via data) | `analysis/config_combat.py` line 185 assigns trample_radius=0.5 to the Castle-age entry. Logistica adds only the blast radius — Castle-age Cataphract has trample_flat_damage=5 but radius=0 (Logistica not yet researched). With radius=0, `_splash_targets(0)=0` → trample never fires; current 0.5 makes it fire | `analysis/config_combat.py` line 185: change `("Byzantines", "cataphract")` entry to `{"trample_flat_damage": 5, "trample_radius": 0.0}`. Elite entry (line 186–189) is correct; leave unchanged |
| **Coustillier charge bonus is effectively armor-ignoring in sim** | coustillier_burgundians, elite_coustillier_burgundians | CORRECT | WRONG | charge_ignores_armor=0 stored correctly, but sim adds t_charge_melee after _calc_damage output (post-armor value), making +20/+25 bypass all melee armor. Column charge_ignores_armor has zero occurrences in simulation.py | `webapp/simulation.py` lines 2096 and 2263: replace `hit_dmg += t_charge_melee` with `hit_dmg += max(0, t_charge_melee - defender_melee_armor)`. Also wire up charge_ignores_armor so armor-ignoring charge units (future) can use the flat-add path |
| **Shu arbalester Bolt Magazine — wrong count and damage** | arbalester (Shu civ) | WRONG | WRONG (via data) | `analysis/config_combat.py` lines 312–315: `extra_projectiles: 1` and `extra_projectile_attacks_json: '{"3": 1}'`. Dat tech_id=1069 adds +2 projectiles; Fandom wiki states "+2 projectiles"; secondary arrow deals 3 pierce. Same error at lines 316–319 for (Shu, crossbow) | `analysis/config_combat.py` lines 312–315: change to `extra_projectiles: 2, extra_projectile_attacks_json: '{"3": 3}'`. Apply same fix to lines 316–319 for Shu crossbow. Rebuild pipeline |
| **Battle Elephant trample trigger probability (TRAMPLE_HIT_CHANCE)** | all Battle Elephants | CORRECT | WRONG | `simulation.py` line 22: `TRAMPLE_HIT_CHANCE=0.25`; lines 1535/3084 gate trample on `random.random() < 0.25`. Wiki states 25% is the damage fraction, not a trigger probability — trample fires on every attack. Net effect: sim produces 6.25% trample DPS vs correct 25% (4× underestimate) | `webapp/simulation.py` lines 1532–1535 and 3081–3084: remove the `random.random() < TRAMPLE_HIT_CHANCE` condition. Trample fires whenever `a_trample_dmg > 0 and a_trample_extra > 0`. Delete `TRAMPLE_HIT_CHANCE` constant (line 22) |
| **Composite Bowman ignores_pierce_armor — no siege/building guard** | composite_bowman_armenians, elite_composite_bowman_armenians | CORRECT | PARTIAL | `_calc_damage()` line 232 zeroes target pierce armor unconditionally when ignores_pierce=True. Wiki: restriction applies only to "non-siege land units." Against a Trebuchet (pierce armor=150), sim gives ~8 dmg/shot vs correct 1 (min-cap) — 8× overestimate. Trebuchet is a selectable UNIT_LINES opponent | `webapp/simulation.py` _calc_damage() (~line 232): add `defender_is_siege` parameter; bypass armor only when `ignores_pierce and not defender_is_siege`. Pass `defender_is_siege=(unit2["unit_category"]=="siege")` at all call sites |
| **Grenadier (Jurchens) Thunderclap Bombs — wrong mechanic type** | grenadier_jurchens | WRONG | WRONG | `analysis/config_combat.py` line 324: `("Jurchens","grenadier"): {"extra_projectiles": 1}` — models Thunderclap Bombs as 1 simultaneous extra projectile at full grenade damage (~12+ pierce). Actual mechanic: 3 timed secondary explosions, 4 damage each at r=0.65, one every 1.5 s; plus a 15-dmg death explosion | Remove `("Jurchens","grenadier"): {"extra_projectiles": 1}` from CIV_COMBAT_PROPERTIES. Model as new `delayed_explosion_count=3, delayed_explosion_damage=4` properties with corresponding sim support, or approximate as AoE bonus DPS. Death explosion (~15 dmg, r=0.75) is out-of-scope for 1v1 sim but relevant for army sim |
| **Armenian Dromon fires 5 projectiles instead of 6** | dromon_armenians | WRONG | WRONG (via data) | Tech 959 (+1 projectile, attr_107/102 for unit 1795) is applied in ref_techs_applied but `_add_attribute()` in unit_analyzer.py has no branch for attr 107 or 102 — stat is silently dropped. extra_projectiles stays at 4 (total 5) for Armenians; should be 5 (total 6) — a 20% DPS underestimate | Add `elif attr == 107 or attr == 102` branches in `analysis/unit_analyzer.py _add_attribute()` to propagate total_projectiles, OR add `("Armenians", "dromon"): {"extra_projectiles": 5}` to CIV_COMBAT_PROPERTIES in `analysis/config_combat.py` |
| **Tupi bleed stacking — single-slot overwrite** | elite_blackwood_archer_tupi, arbalester (Tupi) | CORRECT | PARTIAL | `simulation.py` lines 1084, 1581: `t_bleed[target_idx] = (dps, dur)` overwrites existing bleed instead of stacking. In multi-archer army fights, target receives only one bleed stack regardless of arrows that hit. Known limitation documented at `analysis/config_combat.py` lines 338–339 | Change bleed storage to a list of `(dps, remaining)` tuples per target index; sum contributions each tick in `_apply_tick_effects` (lines 1659–1680). Also add bleed support to `simulate_mixed_battle()` (currently excluded, line 2314 docstring) |
| **Guecha Warrior heal — 6-tile radius not enforced** | guecha_warrior_muisca, elite_guecha_warrior_muisca | CORRECT | PARTIAL | Wiki: heal triggers only for Guecha Warriors within 6-tile radius of the dead unit. Sim has no positional model; applies heal to all surviving same-team units unconditionally. No ally_death_heal_radius column in DB or schema | Add comment in config_combat.py and simulation.py noting the 6-tile radius restriction is not enforced (sim assumes all units within radius). If positional model added later, store `ally_death_heal_radius=6.0` |
| **Arambai stale aoe2_units.db** | arambai_burmese, elite_arambai_burmese | CORRECT (ref DB) | CORRECT | aoe2_units.db has miss_damage_percent=0.0 (stale); aoe2_reference.db correctly has 1.0. Sim reads from reference DB so no gameplay impact. Semantic note: value is used as stray-hit probability, not damage fraction | Re-run generate_main_db.py and commit updated aoe2_units.db. Add code comment in simulation.py clarifying miss_damage_percent=1.0 means 100% probability of stray hit, not 100% damage scaling |

---

### 2b. Detailed fix descriptions for HIGH and MEDIUM severity

#### HIGH — Centurion charge recharge time (`analysis/config_combat.py` lines 248–255)

The comment on line 244 uses the formula `1 / charge_recharge_rate = 1 / 0.25 = 4.0 s`, which is wrong. The correct formula (validated by every other charge unit in the dat file) is `charge_attack / charge_recharge_rate`. For Comitatenses: `5 / 0.25 = 20.0 s`. The Fandom wiki wikitext for Centurion_(Age_of_Empires_II) explicitly reads "+5 charge attack over 20 seconds." All five affected units — `("Romans","champion")`, `("Romans","legionary")`, `("Romans","paladin")`, `("Romans","centurion")`, `("Romans","elite_centurion")` — must be updated from `charge_recharge_time: 4.0` to `charge_recharge_time: 20.0`. The simulation logic at lines 2094–2098 and 2261–2265 is structurally correct and needs no changes. After patching config, run: `python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db && cd webapp && python3 compute_battle_scores.py`.

#### HIGH — Fire Lancer charge recharge + armor-ignore (`analysis/config_combat.py` lines 84–85; `webapp/simulation.py` ~lines 156, 164, 827–828)

Two separate bugs share a severity rating. Bug 1 (data): `charge_recharge_time=0.0` for all five civ variants because `combat_properties.py` only converts `charge_recharge_rate` for `charge_type=4` (dodge shield, line 147) but not for `charge_type=6`. Add `charge_recharge_time: 30.0` to both the `fire_lancer` and `elite_fire_lancer` UNIQUE_COMBAT_PROPERTIES entries in `analysis/config_combat.py`. With timer=0 the sim sets `charge_ready=False` at line 2212 and the recharge tick at lines 1636–1639 is guarded by `charge_timer[i] > 0` — so charge permanently dies after its first shot. Bug 2 (sim): `prepare_combat_unit()` (~line 100–199) never reads `charge_ignores_armor` into the unit dict. The charge damage `_calc_damage()` call at lines 827–828 falls through to `ignores_pierce=unit1['ignores_pierce_armor']` which is 0 for Fire Lancer. Add `charge_ignores_armor = int(row.get("charge_ignores_armor", 0))` in prepare_combat_unit and wire it to the charge-projectile _calc_damage calls. Rebuild DBs after fixing the config.

#### HIGH — Fire Archer charge-always-ready + un-upgraded charge damage (`webapp/simulation.py`; `analysis/generate_reference.py` or `generate_main_db.py`)

The dat encodes `charge_recharge_rate ≈ 3.2×10¹⁸` (effectively infinite) for Fire Archer, meaning the anti-unit charge mode is permanently active. The pipeline does not convert this to a finite `charge_recharge_time`; the value lands as 0.0. Fix part 1 — simulation.py: when `t_charge_recharge == 0`, skip the `charge_ready[i] = False` assignment at line 2212 (and the symmetric path in the 1v1 loop), leaving charge permanently ready. Fix part 2 — data pipeline: `charge_projectile_attacks_json` stores the un-upgraded base attack vector (`{3:5}` for both Castle and Elite) rather than the post-tech fully-upgraded vector (`{3:7}` Castle, `{3:10}` Elite). Since Fire Archer's charge uses the same projectile unit as its regular attack, the same Fletching/Bodkin/Bracer/Chemistry tech deltas must be applied to `charge_projectile_attacks_json`. The generation step that writes `ref_projectiles` for charge-type entries must incorporate attack deltas. The anti-building attack mode (range 9/10, 1 arrow) and the minor AOE (`blast_attack_level=6`, 0.25 radius, 1 flat damage) are acceptable omissions for 1v1 unit sim scope.

#### MEDIUM — Cataphract trample radius for Castle-age (`analysis/config_combat.py` line 185)

Single value change: `("Byzantines", "cataphract"): {"trample_flat_damage": 5, "trample_radius": 0.5}` → `{"trample_flat_damage": 5, "trample_radius": 0.0}`. With radius=0, `_splash_targets(0.0)` returns 0 (line 258 in simulation.py: `max(1, int(0.0 / 0.75)) = 0` — actually `int(0/0.75)=0`, so the guard `if a_trample_extra > 0` is False and trample never fires). The Elite entry at line 186 is correct and unchanged. Rebuild both DBs after the config change. Note: the Fandom wiki wikitext for the Cataphract infobox shows `|AOE = 0 [pure 5 damage]` as a base stat, and Logistica's table entry adds `+0.5 tiles blast radius` — confirming the Castle-age unit has the damage but not the radius.

#### MEDIUM — Coustillier charge bonus bypasses armor (`webapp/simulation.py` lines 2096, 2263)

The charge bonus `t_charge_melee` is added to `hit_dmg` after `_calc_damage()` has already subtracted armor, making the charge effectively armor-ignoring despite `charge_ignores_armor=0`. For a target with M melee armor, the sim over-deals M extra damage on each charged hit. Fix at lines 2096 and 2263: replace `hit_dmg += t_charge_melee` with a version that subtracts the defender's melee armor from the charge bonus, e.g. `hit_dmg += max(0, t_charge_melee - s.current_ma[enemy_team][target_idx])`. The cleanest equivalent is to re-invoke `_calc_damage` with `attacker_attacks` overridden to include `charge_attack_melee` in the base attack key, so the full `base_attack + charge_bonus - target_armor` arithmetic is done in one place. Also read `charge_ignores_armor` in prepare_combat_unit and use it to gate between the two code paths, so that future units with genuinely armor-ignoring charges (if any) work correctly.

#### MEDIUM — Shu arbalester/crossbow Bolt Magazine (`analysis/config_combat.py` lines 312–319)

Dat tech_id=1069 (Bolt Magazine) issues `ADD_ATTRIBUTE +2.0` to attr_102 and attr_107 on unit 492 (arbalester). The Fandom wiki states "+2 projectiles" for Archer line. Config currently stores `extra_projectiles: 1` and `extra_projectile_attacks_json: '{"3": 1}'`. Both values are wrong — correct is `extra_projectiles: 2` and `extra_projectile_attacks_json: '{"3": 3}'` (secondary arrow deals 3 pierce, same as standard CKN secondary). The same correction applies to the `("Shu", "crossbow")` entry at lines 316–319. Rebuild the full pipeline after patching.

#### MEDIUM — Battle Elephant trample trigger probability (`webapp/simulation.py` lines 1532–1535, 3081–3084, line 22)

Remove `TRAMPLE_HIT_CHANCE = 0.25` (line 22). In simulate_battle (lines ~1532–1535): change `if a_trample_dmg > 0 and a_trample_extra > 0 and random.random() < TRAMPLE_HIT_CHANCE:` to `if a_trample_dmg > 0 and a_trample_extra > 0:`. Apply identical change at simulate_mixed_battle (lines ~3081–3084). The 25% in `trample_percent` is a damage fraction (already captured in `trample_dmg = int(dmg * 0.25)`), not a trigger probability. Removing the random gate changes effective trample DPS from 6.25% → 25% of attack, a 4× increase matching documented game behavior. Bengali bonus_damage_reduction=0.25 and Dravidian elite_elephant ignores_melee_armor=1 are correctly stored and correctly simulated; no changes needed there.

#### MEDIUM — Grenadier Thunderclap Bombs mechanic type (`analysis/config_combat.py` line 324)

Remove `("Jurchens", "grenadier"): {"extra_projectiles": 1}` from CIV_COMBAT_PROPERTIES. The current entry fires 1 simultaneous extra hit at full grenade damage (~12 pierce vs infantry), whereas the real mechanic fires 3 delayed secondary explosions of 4 damage each (r=0.65) at 1.5 s intervals. The sim's extra_projectile DPS is ~3–4× too high per secondary hit, and count is wrong (1 vs 3). Introduce new properties `delayed_explosion_count` and `delayed_explosion_damage` to model the timed sub-blasts, with corresponding sim logic in `_apply_tick_effects`. The death explosion (15 dmg, r=0.75) can be noted as out-of-scope for 1v1 sim. The base `splash_on_hit_radius=0.65` is correctly sourced from extracted_data and must be retained.

#### MEDIUM — Armenian Dromon projectile count (`analysis/unit_analyzer.py`; `analysis/config_combat.py`)

Tech 959 (`+1 projectile, C-Bonus Navy`) is recorded in ref_techs_applied for dromon_armenians but silently dropped because `_add_attribute()` in unit_analyzer.py has no `elif` branch for attr 107 (max_total_projectiles) or attr 102 (secondary_projectile_count). The surgical fix is to add to `analysis/config_combat.py` CIV_COMBAT_PROPERTIES: `("Armenians", "dromon"): {"extra_projectiles": 5}` (total=6). The pipeline fix is to add attr 107/102 handling in unit_analyzer.py and propagate total_projectiles through to ref_units. After fixing, the Armenian Dromon correctly fires 6 projectiles, a 20% DPS increase. The Dromon AoE blast (blast_width=0.8, blast_damage=1.0 in dat) is absent from the data layer (splash_radius=0.0 for all variants) and absent from the sim — noted as a naval-context omission in Section 4.

---

## 3. Verified-Correct Mechanics

| Mechanic | Data | Sim | Note |
|---|---|---|---|
| **Arambai miss_damage_percent=1.0** | ✓ | ✓ | ref DB has 1.0 for Castle and Elite; sim reads from aoe2_reference.db (not stale aoe2_units.db) and applies it as stray-hit probability=100% on every missed dart. Wiki: "Missed projectiles deal 100% damage too" (post-patch 44725). se_data.json AccuracyPercent=20/30 confirmed. |
| **Ballista Elephant pass_through_percent (0.6667 Castle / 0.6 Elite)** | ✓ | ✓ | Adversarial review overturned prior finding. Values are correctly derived from dat secondary_pierce / primary_pierce (6/9, 6/10). The wiki says "same pass-through mechanic as Scorpion," not "same 50% fraction." The Scorpion's 0.4545 is also a dat-derived ratio (5/11), not exactly 0.5. Stored values match the dat; changing to 0.5 would be less accurate. |
| **Bolas Rider Malon pass_through=0.3 applies to every shot** | ✓ | ✓ | Adversarial review overturned prior "charge-shot only" finding. Malon wiki states all Bolas Rider, Slinger, and Skirmisher shots gain 30% pass-through. Wiki phrase "pass-through charged attack" describes a combined interaction, not a restriction. Sister units (Mapuche Skirmisher) have no charge mechanic at all yet are documented as receiving Malon's pass-through on every shot. Sim uniform _apply_tick_damage treatment is correct. charge_slow is correctly restricted to charge shots only. |
| **Bolas Rider charge_slow_percent=0.15, charge_slow_duration=10.0, charge_recharge_time=30.0** | ✓ | ✓ | All three values match SiegeEngineers data.json (unit ID 2569/2571: RechargeDuration=30.000028 s, ChargeType=6). Charge slow correctly gated to charge shots at simulation.py lines 2216–2217. |
| **Chakram Thrower pass_through_percent=1.0, pass_through_count=3** | ✓ | ✓ | Dat blast_damage=1.0 (100% pass-through fraction) confirmed. Wiki updated to 100% after patch 73855. Count=3 (3 additional targets beyond primary = 4 total) is consistent with Scorpion/Ballista Elephant editorial convention; no public source documents an exact cap. 1v1 sim correctly never triggers the pass-through loop (no secondary alive targets). |
| **Chu Ko Nu extra_projectiles=2/4, secondary damage {3:3}, base accuracy for extras** | ✓ | ✓ | Dat unit IDs 73/559 with secondary_projectile_unit=510 confirmed. Extra arrows deal 3-pierce-only with no anti-spearman bonus. simulation.py line 457 comment explicitly documents: "extra arrows use base_accuracy not final_accuracy" (Thumb Ring does not help extras). Counts 3/5 total confirmed. |
| **Blackwood Archer (Tupi) Curare — bleed_dps=0.133, bleed_duration=15.0, Castle has no bleed** | ✓ | Partial | Data correct: 2 dmg / 15 s = 0.1333 DPS; stored as 0.133 (negligible rounding). Castle-age unit correctly has no bleed (Curare is Imperial UT). Confirmed by Fandom Curare wiki. Sim limitation: single-slot overwrite on multi-hit (acknowledged known gap — see confirmed issues). |
| **Fire Archer (Wu) — extra_projectiles=2 (3 total per attack)** | ✓ | Partial | Dat max_total_projectiles=3 / total_projectiles=1 correctly yields extra_projectiles=2. Charge mechanic bugs are listed separately under HIGH issues (charge_recharge_time=0, un-upgraded charge damage). |
| **Jian Swordsman — standard unit stats and armor classes** | ✓ | ✓ | No special-effect mechanics flagged. Unit stats sourced from extracted dat without special-effect overrides. |
| **Tiger Cavalry — standard unit stats** | ✓ | ✓ | No special-effect mechanics flagged. Standard melee unit with no special-effect properties in config_combat.py. |
| **Kona (unit) — unit stats and armor classes** | ✓ | ✓ | No special-effect mechanics flagged. Standard stats sourced from dat extraction. |
| **Ibirapema — bleed/poison on hit** | ✓ | Partial | bleed_dps and bleed_duration correctly stored and applied in 1v1 sim. Single-slot stacking limitation applies (same as Tupi arbalester) — see confirmed issues. |
| **General bleed/poison mechanic (all units)** | ✓ | Partial | bleed_dps, bleed_duration values are correct against wiki sources across all audited units. Shared sim limitation: single-slot overwrite (not stacking) and simulate_mixed_battle() excludes bleed entirely (documented in source comment at line 2314). |
| **Sicilians bonus_damage_reduction=0.4 (arbalester, crossbow, all land military)** | ✓ | ✓ | 0.4 matches current post-update-153015 wiki value (was 0.33 before update 153015, 0.5 before 66692). simulation.py:248–249 applies reduction to bonus_damage component only (not base damage). Propagated correctly to extra-projectile, charge, transform, and army sim damage paths. |
| **Guecha Warrior ally_death_heal=5, duration=3s, refresh-not-stack behavior** | ✓ | Partial | heal magnitude (5 HP / 3 s) and timer-refresh behavior (overwrites, does not accumulate — correct per wiki) are right. Only gap: 6-tile radius not enforced (position-less sim). |

---

## 4. Not Simulated (Naval / Siege Out of 1v1 Scope)

These mechanics are documented or known but intentionally outside the 1v1 unit simulation scope:

- **Dromon AoE blast** — `blast_width=0.8, blast_damage=1.0` in dat; `splash_radius=0.0` stored. Naval unit; 1v1 land sim does not exercise it. Byzantine Greek Fire (+0.2 radius) is also absent.
- **Dromon anti-building attack profile** — secondary projectile range 9/10 vs buildings. Naval/building context.
- **Fire Archer anti-building mode** — long-range single-arrow mode (range 9/10), activates automatically vs buildings and ships. Not relevant for unit 1v1.
- **Fire Archer blast_attack_level=6 AoE** — 0.25-radius, 1 flat damage splash per arrow (combat_properties.py has no branch for blast_level=6). Negligible impact in 1v1; out-of-scope for the sim's architecture.
- **Grenadier Thunderclap Bombs death explosion** — 15 dmg, r=0.75, triggers on unit death. No die-and-explode mechanic in simulation.py. Matters for army-vs-army; not 1v1.
- **Scorpion / Heavy Scorpion pass-through simulations vs buildings/ships** — pass-through logic is structurally correct; building/ship matchups are not in UNIT_LINES for 1v1 sim.
- **Trebuchet, Mangonel, Onager (general siege splash)** — is_siege_projectile=1 path exists in the sim for single-target siege, but multi-target AoE on static structures is not modeled.

---

## 5. Low-Confidence / Needs Human Review

| Item | Question | Confidence |
|---|---|---|
| Fire Archer charge_projectile_attacks_json post-tech values | The pipeline must apply the same Fletching/Bodkin/Bracer/Chemistry deltas to charge_projectile_attacks as it does to final_attacks. Verify the correct method in generate_reference.py to propagate tech attack deltas to the charge projectile sub-row. | Medium |
| Grenadier Thunderclap Bombs delayed explosion timing | Wiki says "one every 1.5 s"; whether the interval is exactly 1.5 s or varies needs verification in the dat's secondary_missile_unit sub-unit data (unit 1916). The sim would need a new per-unit delayed-explosion queue. | Medium |
| pass_through_percent derivation formula (all bolt units) | `secondary_pierce / primary_pierce` is used for Scorpion, Heavy Scorpion, Ballista Elephant. For Scorpion this gives 0.4545 vs the commonly cited "50%". The adversarial review concluded dat values are authoritative and should not be rounded to 0.5; a human should confirm whether the wiki's simplification or the dat ratio is the intended design value. | Medium |
| Composite Bowman ignores_pierce_armor vs buildings | The wiki says "non-siege land units only." Ships and buildings are excluded but no sim test exercises these matchups. If buildings/ships are ever added to the matchup pool, the guard must be extended beyond the siege check. | Low |
| Bolas Rider charge_slow interaction with Malon pass-through | In multi-target army scenarios, does Malon's pass-through on the charge shot apply the slow to secondary (pass-through hit) targets? The wiki is ambiguous. Only the primary target's slow is currently tracked in the sim (charge_hit_target). | Low |
