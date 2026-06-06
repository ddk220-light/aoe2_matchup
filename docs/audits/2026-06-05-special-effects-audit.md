# Special-Effects Audit — Data + Simulation Correctness

**Date:** 2026-06-05  
**Method:** Multi-agent workflow (sonnet) — 52 special-effect mechanics, each cross-checked vs ≥2 online sources (SiegeEngineers data.json + Fandom wiki) AND against `webapp/simulation.py`. Adversarial confirm pass per flag.

**Summary:** 52 mechanics audited · data correct: 28 · sim correct: 16 · flagged: 40 · confirmed: 37

> NOTE: sonnet agents over-flag. Each item below needs human vetting; several are sim-design trade-offs (e.g. probabilistic trample, bleed-stacking simplification) rather than outright bugs.

## HIGH severity (12)

### Centurion charge attack melee recharge time (Comitatenses tech)

**Fix:** In analysis/config_combat.py lines 248-255, change all five Comitatenses entries from charge_recharge_time: 4.0 to charge_recharge_time: 20.0, and fix the comment on line 244 from '1/0.25 = 4.0 seconds' to '5/0.25 = 20.0 seconds'. The five affected units are: ('Romans','champion'), ('Romans','legionary'), ('Romans','paladin'), ('Romans','centurion'), ('Romans','elite_centurion'). After patching, rebuild: python3 -m analysis.generate_reference, python3 -m analysis.generate_main_db, then cd webapp && python3 compute_battle_scores.py.

### Battle Elephant trample damage: 25% of attack value dealt to adjacent enemies on every attack within 0.4 tile radius. Bengali civ bonus: -25% bonus damage received. Dravidian Wootz Steel: elite_elephant melee attacks ignore armor.

**Fix:** In webapp/simulation.py: remove the random.random() < TRAMPLE_HIT_CHANCE condition at lines 1532-1535 (simulate_battle) and lines 3081-3084 (simulate_mixed_battle). Trample should fire unconditionally whenever a_trample_dmg > 0 and a_trample_extra > 0. The TRAMPLE_HIT_CHANCE constant (line 22) can be deleted entirely. Corrected block at line 1531: `if a_trample_dmg > 0 and a_trample_extra > 0:` (no random gate). Same pattern at line 3080. The trample_dmg value (int(dmg * trample_percent)) and trample_extra (_splash_targets(radius)) are both already correct.

### Fire Archer (Wu) two-mode attack: anti-unit charge (charge_type=6, always available, 3 arrows/volley, range 5/6) vs anti-building regular (1 arrow, range 9/10). Recharge rate is "Infinite" meaning charge fires on every attack.

**Fix:** TWO fixes required:

FIX 1 â€” DATA (charge_projectile_attacks_json underestimates damage):
In analysis/combat_properties.py, after line 116 where charge_projectile_attacks_json is set from dat raw values, tech bonuses must be applied to the charge projectile attacks the same way they are applied to the main attacks. Since charge_type=6 Fire Archer uses the same projectile unit and the same tech upgrades (Fletching, Bodkin, Bracer, Chemistry) apply to both modes per the wiki, the simplest fix is: when building the final combat_props in generate_reference.py, copy the tech-delta from base_attacks_jsonâ†’final_attacks_json and apply it to charge_projectile_attacks_json. Alternatively, add an explicit config override in analysis/config_combat.py for fire_archer_wu and elite_fire_archer_wu: {"charge_projectile_attacks_json": '{"3":7,"21":4,"16":3,"27":2,"20":1,"17":0}'} and {"charge_projectile_attacks_json": '{"3":10,"21":4,"16":4,"27":2,"20":1,"17":0}'} respectively, then regenerate both DBs.

FIX 2 â€” SIMULATION (charge fires only once instead of every attack):
In webapp/simulation.py, the recharge block at lines 1636â€“1639 must handle recharge_time=0.0 as "instant recharge / always ready". Change the logic so that when charge_recharge_time==0.0 (or equivalently when timer is set to 0.0 after firing), the unit is immediately re-armed rather than waiting for a timer. Simplest fix: at lines 2212â€“2214, add a conditional: if t_charge_recharge == 0.0: my_charge_ready[i] = True (skip the disable/re-arm cycle entirely). Same fix needed at lines 2097â€“2098 (1v1 sim melee charge path) and lines 2264â€“2265 (melee charge path) if those paths can be hit by a charge_recharge_time=0 unit, though for Fire Archer only the ranged path matters.

### Fire Lancer charged ranged attack: 3-projectile volley every 30s, range 4, armor-ignoring pierce damage

**Fix:** Three coordinated fixes required:

FIX 1 (DATA â€” analysis/config_combat.py lines 84â€“85): Add charge_recharge_time=30.0 to both fire_lancer entries:
  "fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1, "charge_recharge_time": 30.0},
  "elite_fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1, "charge_recharge_time": 30.0},
Then rebuild both DBs: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db.

FIX 2 (SIM â€” webapp/simulation.py prepare_combat_unit, after line 164): Add:
  "charge_ignores_armor": row.get("charge_ignores_armor", 0) or 0,
Then update the charge damage pre-computation block (lines 818â€“831 and 836â€“849) to pass ignores_pierce=unit1.get("charge_ignores_armor", 0) (and ignores_melee=unit1.get("charge_ignores_armor", 0)) in the _calc_damage calls for charge projectiles, replacing the current use of unit1["ignores_pierce_armor"] / unit1["ignores_melee_armor"] for those calls. The charge volley is pure pierce (class 3), so only ignores_pierce is practically relevant.

FIX 3 (SIM â€” optional/lower priority): To model the range gate, read charge_attack_range into the unit dict in prepare_combat_unit and add a check in the use_charge_proj block (simulation.py ~line 2175) that suppresses the charge when the sim's effective distance is below that threshold. The current tick-based sim does not model positional distance, so a practical approximation is to skip the charge if the attacker is classified as melee (attack_range==0) and charge_attack_range>0 â€” this matches the in-game behavior of "does not fire when in melee combat".

### Ibirapema Warrior frontal cone AoE (trample/blast) â€” 100% damage vs stale flat-5 damage

**Fix:** Regenerate `webapp/aoe2_reference.db` from the current config by running the full pipeline: `python3 -m analysis.generate_reference` then `python3 -m analysis.generate_main_db`. This will propagate the current `UNIQUE_COMBAT_PROPERTIES` values (`trample_percent=1.0, trample_radius=0.5`, no `trample_flat_damage`) into `ref_special_effects` and the `ref_units` inline columns, replacing the stale `trample_flat_damage=5 / trample_percent=0.0` entries. After regeneration, verify: `python3 -c "import sqlite3; d=sqlite3.connect('webapp/aoe2_reference.db'); d.row_factory=sqlite3.Row; [print(dict(r)) for r in d.execute(\"SELECT property_name,property_value FROM ref_special_effects WHERE ref_unit_id IN (SELECT id FROM ref_units WHERE unit_slug LIKE '%ibirapema%')\")]"` should show `trample_percent=1.0, trample_radius=0.5` with no `trample_flat_damage` row. Then commit `webapp/aoe2_reference.db` on staging per CLAUDE.md rule 7.

### Lou Chuan dual-mode attack: anti-building trebuchet rock (1 proj + 9 secondary rocks) vs anti-unit arrow salvo (charge_type=6, charge_recharge_rate=100000 meaning instant/every-attack recharge)

**Fix:** Two fixes required:

FIX 1 â€” analysis/combat_properties.py: For charge_type=6 units, do NOT set extra_projectiles from the max_total_projectiles formula (lines 86-93). The anti-unit arrow salvo for Lou Chuan is entirely the charge projectile mechanism (charge_proj_count + charge_proj_attacks_json). Remove or gate the `if charge_type == 6` branch at line 86-93 so it does not set `extra_projectiles`, which prevents the wrong secondary_projectile_attacks profile from being attached as extra_projectile_attacks_json. After this change, Lou Chuan should have extra_projectiles=0 and extra_projectile_attacks_json=null, while charge_projectile_count=9 and charge_projectile_attacks_json={"3":5,"16":5} remain correct. Rebuild aoe2_reference.db and aoe2_units.db after this change.

FIX 2 â€” webapp/simulation.py lines 1634-1645 (_apply_tick_effects): Add a zero-recharge instant-reset path. Change the charge recharge block to:
  if charge_timer1 is not None:
      for i in alive1:
          if not charge_ready1[i]:
              if charge_recharge1 == 0:      # instant recharge (e.g. Lou Chuan, Fire Archer)
                  charge_ready1[i] = True
              elif charge_timer1[i] > 0:
                  charge_timer1[i] -= DT
                  if charge_timer1[i] <= 0:
                      charge_ready1[i] = True
(Same for charge_timer2/charge_recharge2 block.) This makes Lou Chuan (and Fire Archer) fire their charge projectiles on every attack as intended. After this fix, rerun compute_battle_scores.py to regenerate battle_scores.json and the naval role scores in pool_scores.db.

### Urumi Swordsman periodic charge attack (+12/+15 bonus damage) with AoE blast only on the charged strike; Elite additionally ignores melee armor (Wootz Steel)

**Fix:** 1. DATA FIX â€” add to UNIQUE_COMBAT_PROPERTIES in analysis/config_combat.py (after existing Coustillier/Bolas Rider entries):
   "urumi_swordsman": {"charge_attack_melee": 12, "charge_recharge_time": 20.0}
   "elite_urumi_swordsman": {"charge_attack_melee": 15, "charge_recharge_time": 13.3}
   Additionally, trample_percent/trample_radius should NOT be stored unconditionally; they should be removed from the dat-driven mapping for charge_type=3 units, or stored under a separate flag (e.g. charge_trample_percent) that the sim only applies when the charge fires.

2. SIMULATION FIX â€” in webapp/simulation.py, the trample application block (lines 1531â€“1545 in simulate_battle) needs to be conditioned on the charge being ready for units where trample is a charge-only effect. A clean approach: add a boolean field charge_trample (set True when charge_type=3 in the dat-driven mapping) and gate the trample block on `not a_charge_trample or (my_charge_ready and my_charge_ready[attacker_idx])` â€” i.e., trample fires normally for always-on trampling units (War Elephant, etc.) but only on charged strikes for the Urumi.

3. REBUILD â€” after config change: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db, then rerun compute_battle_scores.py.

### War Chariot (Shu) â€” multi-mode ranged attack with Bolt Magazine Imperial UT adding projectiles

**Fix:** PRIMARY FIX â€” Castle age extra_projectiles inflation:

In analysis/config_combat.py, CIV_COMBAT_PROPERTIES[("Shu","war_chariot")] = {"extra_projectiles": 6} must be split by age. The get_combat_properties() function (analysis/combat_properties.py line 183) currently has no age parameter. Two options:

Option A (surgical â€” add age param to get_combat_properties and call sites): Add an optional `age` parameter to get_combat_properties(). In the CIV_COMBAT_PROPERTIES lookup block (lines 264-272), if a civ_key entry contains an "imperial_only" flag or is keyed as (civ, slug, "Imperial"), apply it only when age=="Imperial". Callers in generate_reference.py must pass the age string.

Option B (simpler â€” split the CIV key into two entries with age guards, or use a separate IMPERIAL_COMBAT_PROPERTIES dict): Add a new dict entry only for Imperial, keeping Castle at the UNIQUE_COMBAT_PROPERTIES value of 4. For example: CIV_COMBAT_PROPERTIES[("Shu","war_chariot")] should remain absent for Castle (UNIQUE value of 4 applies), and only apply extra_projectiles=6 for Imperial.

The cleanest targeted fix without refactoring: in analysis/config_units.py UNIT_STAT_OVERRIDES[2150], keep reload_time=7.5. Add a new CIV_COMBAT_PROPERTIES entry keyed with age awareness. Until get_combat_properties() supports age, the workaround is to patch the DB directly: in webapp/aoe2_reference.db, update the Castle-age ref_units row for war_chariot_shu (id=1455) to set extra_projectiles=4 and re-run generate_main_db.py.

SECONDARY FIX â€” Imperial reload time:

In analysis/config_combat.py, add to CIV_COMBAT_PROPERTIES[("Shu","war_chariot")] a reload_time_override for Imperial age of 8.0s. This also requires age-awareness in get_combat_properties(). Alternatively add a UNIT_STAT_OVERRIDES entry for unit 1962 (the actual ranged War Chariot dat unit) with reload_time=8.0 for Imperial (current override is on unit 2150 with 7.5s for Castle base).

### War Elephant trample damage (blast_damage=0.5, blast_width=0.5, blast_attack_level=2) â€” AoE deals 50% of melee attack to enemies within 0.5 tile radius on every attack swing

**Fix:** In webapp/simulation.py, remove the `random.random() < TRAMPLE_HIT_CHANCE` probabilistic gate from both trample blocks. The fix at line 1531-1535 should change from `if (a_trample_dmg > 0 and a_trample_extra > 0 and random.random() < TRAMPLE_HIT_CHANCE):` to `if (a_trample_dmg > 0 and a_trample_extra > 0):`. Apply the same change at line 3080-3084 in simulate_mixed_battle(). The TRAMPLE_HIT_CHANCE constant (line 22) can then be removed entirely. This makes trample fire deterministically on every attack, matching the real game engine's blast_damage behavior.

### Xianbei Raider charge volley (charge_type=7 burst fire): fires 5 extra arrows each time charge is ready (~30s recharge), on top of the normal main projectile. The 5 charge arrows use secondary_projectile_attacks stats (pierce 1, +4 vs Spearmen, +1 vs Infantry, -3 vs Mounted Archers).

**Fix:** THREE fixes needed:

1. DATA FIX â€” analysis/combat_properties.py, get_extracted_combat_properties(): Add charge_recharge_time conversion for charge_type=7 alongside type=4. After line 149 (the existing charge_type==4 block), add:
   elif charge_type == 7 and charge_recharge and charge_recharge > 0:
       props['charge_recharge_time'] = round(1.0 / charge_recharge, 1)
   This converts charge_recharge_rate=0.0333 to charge_recharge_time=30.0s.
   Also remove lines 97-99 (the first_attack_extra_projectiles assignment for charge_type=7) â€” this mechanic must not be modelled as a first-attack burst.

2. DATA FIX â€” analysis/config_combat.py: Add entry to UNIQUE_COMBAT_PROPERTIES as a safety override:
   'xianbei_raider': {'charge_recharge_time': 30.0}
   This ensures even without pipeline rerun the value is correct.

3. SIMULATION FIX â€” webapp/simulation.py, simulate_battle(), the use_charge_proj branch (~line 2180): Change the logic from switching the main-shot damage to firing 5 extra projectiles. When use_charge_proj=True, the main shot fires normally (base = t_dmg), then loop t_charge_proj_count times firing extra projectiles at charge_proj_dmg (the charge arrow damage profile). The count value stored in t_charge_proj_count=5 must drive a loop, not just serve as a boolean. Concretely, replace the 'base = t_charge_proj_dmg' assignment with: after the main shot fires, add a loop like 'for _ in range(t_charge_proj_count): pending_damage.append(...)' using charge_proj_dmg.

After fixing (1) or (2), rerun analysis/generate_main_db.py and rebuild aoe2_reference.db/aoe2_units.db. After fixing (3), rerun compute_battle_scores.py and regenerate .golden/baseline.json.

### POLES Lechitic Legacy trample_percent (data=0.5, should=0.33); SICILIANS bonus_damage_reduction incorrectly applied to scorpion/heavy_scorpion; SHU hp_nearby max_hp regen cap mismatch (structural, no current effect)

**Fix:** 1. POLES trample_percent fix â€” in analysis/config_combat.py lines 241-242, change trample_percent from 0.5 to 0.33:
  ("Poles", "hussar"): {"trample_percent": 0.33, "trample_radius": 0.5}
  ("Poles", "winged_hussar"): {"trample_percent": 0.33, "trample_radius": 0.5}
  Also update the comment on line 240 from "50% trample" to "33% trample". Then regenerate aoe2_units.db and rerun compute_battle_scores.py.

2. SICILIANS siege fix â€” in analysis/config_combat.py, delete lines 238-239 entirely:
  ("Sicilians", "scorpion"): {"bonus_damage_reduction": 0.4},
  ("Sicilians", "heavy_scorpion"): {"bonus_damage_reduction": 0.4},
  Then regenerate aoe2_units.db and rerun compute_battle_scores.py.

3. SHU max_hp regen cap fix (optional, no urgency) â€” in webapp/simulation.py lines 608-609, after computing hp_mult, also update max_hp1/max_hp2 to reflect the boosted HP. The safest approach: move the max_hp1/max_hp2 assignment to after the hp_nearby block (lines 636-651), using the multiplied value: s.max_hp1 = float(unit1["hp"]) * hp_mult1 if pct1 > 0 else float(unit1["hp"]).

### War Hulk extra-projectile gating: extra_projectiles=2 stored correctly, but simulation.py fires only 1 melee hit per cycle because the extra-proj loop is inside `elif t_is_ranged:` (line 2168) and hulk is classified melee (range=1.0, attacks class 4, is_ranged=False)

**Fix:** webapp/simulation.py â€” in `simulate_mixed_battle` (and the equivalent block in `simulate_battle`), move the extra-projectile firing loop out of the `elif t_is_ranged:` branch so it runs for melee units too. Specifically, after line 2246 (`my_cooldown[i] = t_reload`) and after line 2269 (the melee `pending_damage.append`), add the same `if num_extra > 0:` block that currently sits inside the ranged branch (lines 2219â€“2237). Alternatively, pull the extra-proj check into a shared helper called from both the ranged and melee branches. The hulk has `attack_delay=0.0` so no committed-attack complication. Since `extra_projectile_attacks_json` is NULL for hulk, `extra_proj_dmg` already correctly falls back to `s.dmg1` (line 579) â€” the same damage value as the main hit â€” so no damage-value change is needed, only the firing-gate removal.

## MEDIUM severity (18)

### Shu arbalester Bolt Magazine extra_projectiles count (config_combat.py + ref_projectiles)

**Fix:** In analysis/config_combat.py, lines 312-315, change the Shu arbalester entry from:
  ("Shu", "arbalester"): {"extra_projectiles": 1, "extra_projectile_attacks_json": "{\"3\": 1}"}
to:
  ("Shu", "arbalester"): {"extra_projectiles": 2, "extra_projectile_attacks_json": "{\"3\": 3}"}

Apply the same correction to ("Shu", "crossbow") at lines 316-319 (also +2 projectiles per wiki/dat).

Then rebuild the pipeline: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db to repopulate webapp/aoe2_reference.db and webapp/aoe2_units.db, then rerun compute_battle_scores.py as golden data will change.

### Cataphract trample flat damage (Logistica) â€” Castle-age radius assignment

**Fix:** In D:\AI\aoe2-unit-analyzer\analysis\config_combat.py line 185, change the Castle-age entry from: `("Byzantines", "cataphract"): {"trample_flat_damage": 5, "trample_radius": 0.5}` to: `("Byzantines", "cataphract"): {"trample_flat_damage": 5, "trample_radius": 0.0}`. This makes _splash_targets(0.0) return 0, setting trample_extra=0 and has_trample=False for Castle-age sims. The Elite entry at line 186-189 is correct and should remain unchanged. After the config change, regenerate aoe2_reference.db and aoe2_units.db via the build pipeline.

### ignores_pierce_armor â€” Composite Bowman (Armenians) ignores pierce armor of non-siege land units

**Fix:** In webapp/simulation.py _calc_damage() (line 229-233), add a defender siege-category guard. The function needs a new parameter `defender_is_siege=False`. Change line 232 from: `0 if ignores_pierce else defender_armors.get(3, defender_pierce_armor)` to: `0 if (ignores_pierce and not defender_is_siege) else defender_armors.get(3, defender_pierce_armor)`. Then pass `defender_is_siege=(unit2["unit_category"] == "siege")` at all _calc_damage call sites where unit2 is the defender (lines 474-497, 573, 590, 709, 735, 762, 775, 788, 800, 827, 845, and army sim line 2469). The unit_category column is already stored in aoe2_units.db unit_stats and loaded in prepare_combat_unit() context. Buildings and ships should also be excluded if those matchups are ever simulated.

### Coustillier charge attack melee (+20 Castle / +25 Elite, recharge 40s, NOT armor-ignoring)

**Fix:** In webapp/simulation.py at lines 2094-2096 and 2261-2263, replace `hit_dmg += t_charge_melee` with `hit_dmg += max(0, t_charge_melee - target_melee_armor)` where target_melee_armor is the defender's current melee armor value (available via s.current_ma arrays or the unit dict melee_armor). Alternatively, the cleaner fix is to re-invoke _calc_damage with attacker_attack increased by t_charge_melee so the full armor subtraction is applied to (base_attack + charge_bonus) as documented: 'effective damage = base_attack + charge_bonus - target_armor'. Both code paths (committed/delayed melee at line 2096, and instant melee at line 2263) need the same fix.

### Dromon extra projectiles (5 total; Armenian civ variant should fire 6) and AoE blast radius (0.8, full damage)

**Fix:** Fix 1 (Armenian +1 projectile â€” highest priority): Add ATTR_TOTAL_PROJECTILES = 107 and ATTR_SECONDARY_PROJECTILE_COUNT = 102 to analysis/config_constants.py, then add elif branches in unit_analyzer.py _add_attribute() to increment a total_projectiles field on UnitStats. Then add total_projectiles to UnitStats, initialize it from unit_data in generate_reference.py (already done at line 541), and let the tech effect propagate it. After regenerating aoe2_reference.db and aoe2_units.db, dromon_armenians will store extra_projectiles=5, total_projectiles=6.0. Alternatively (faster surgical fix without changing the pipeline): add to analysis/config_combat.py CIV_COMBAT_PROPERTIES: {("Armenians", "dromon_armenians"): {"extra_projectiles": 5}} and set total_projectiles=6 via generate_main_db patch.

Fix 2 (AoE blast â€” naval context): Add to analysis/config_combat.py COMBAT_PROPERTIES["dromon"]: {"splash_radius": 0.8, "is_siege_projectile": 1}. The is_siege_projectile=1 flag is required because simulation.py line 534 only invokes _splash_targets() for siege projectiles (s.siege_splash1 = _splash_targets(unit1["splash_radius"]) if s.is_siege1 else 0). Byzantines' Greek Fire AoE bonus (+0.2 radius) would also need a CIV_COMBAT_PROPERTIES entry: {("Byzantines", "dromon_byzantines"): {"splash_radius": 1.0}}. After regenerating DBs, battle scores involving Dromon should be rerun via compute_battle_scores.py.

### Grenadier (Jurchens) â€” Thunderclap Bombs secondary explosions

**Fix:** Two separate fixes are needed:

1. DATA (analysis/config_combat.py line 324): Replace the wrong extra_projectiles=1 override with a representation that correctly captures the mechanic. Since the sim engine has no timed-explosion concept, the least-wrong approximation is to model the 3 secondary explosions as bleed-like AoE damage â€” OR, if the engine is extended, add a new field (e.g., timed_explosions_count=3, timed_explosion_damage=4, timed_explosion_interval=1.5, timed_explosion_radius=0.65) and remove the extra_projectiles=1 entry. For an immediate partial fix without engine changes, the extra_projectiles=1 entry should either be removed (accepting no Thunderclap Bombs bonus is modelled) or changed to use extra_projectile_attacks_json with the correct 4-melee-damage profile and count reduced to reflect actual net expected damage â€” e.g., ("Jurchens","grenadier"): {"extra_projectiles": 1, "extra_projectile_attacks_json": "{\"4\": 4}"} which at least corrects the per-shot damage magnitude (4 melee instead of full grenade pierce), even though count (1 vs 3) and timing (simultaneous vs delayed) remain wrong.

2. SIMULATION (webapp/simulation.py): The timed secondary explosion mechanic cannot be correctly modelled by the existing extra_projectiles path. A proper fix would add a new SimState field timed_explosions (count, damage, interval) and apply it in the per-tick loop N seconds after each attack event. For the death explosion, a new die_explosion field (damage, radius) would need to be applied when a unit's HP drops to 0. These are non-trivial engine extensions. Until they exist, the incorrect extra_projectiles=1 entry should be corrected in the config to at least use the right damage value (4 melee, class 4), and ideally a comment should document that the 3x count and 1.5 s delay are not simulated.

### Pirotecnia pass-through damage count (Hand Cannoneer, Italians)

**Fix:** In analysis/config_combat.py line 218, change the Italian hand_cannoneer entry from `{"pass_through_percent": 0.15}` to `{"pass_through_percent": 0.15, "pass_through_count": 3}`. Then rebuild the databases: `python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db && cd webapp && python3 compute_battle_scores.py`. No simulation.py changes needed â€” the sim logic already handles the count correctly.

### Hussite Wagon extra projectiles (5 secondary bullets per attack) and defensive protection ability (halves enemy projectile damage to units passing through its hitbox)

**Fix:** Add an override in UNIQUE_COMBAT_PROPERTIES in analysis/config_combat.py: "elite_hussite_wagon": {"extra_projectile_attacks_json": "{\"11\": 3, \"3\": 5, \"17\": 3}"}. This overrides the stale extracted value (class 3=3) with the correct post-elite-upgrade secondary pierce value (class 3=5, base 3 + tech 781 +2). Then regenerate: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db. No simulation.py changes are needed â€” the sim reads directly from the DB field and will compute correct extra-shot damage once the stored value is fixed.

### Iron Pagoda block_first_melee â€” periodic melee-attack negation shield with recharging cooldown

**Fix:** Two changes required:

1. DATA (analysis/config_combat.py, lines 93â€“94): Add charge_recharge_time to the Iron Pagoda config entries so the cooldown is stored in the DB:
   "iron_pagoda": {"block_first_melee": 1, "charge_recharge_time": 40.0}
   "elite_iron_pagoda": {"block_first_melee": 1, "charge_recharge_time": 30.0}
   Then regenerate aoe2_reference.db and aoe2_units.db via the pipeline.

2. SIMULATION (webapp/simulation.py): Add a parallel block_timer array (like shield_timer) and reset has_blocked[idx]=False once the timer expires. Concretely:
   - At setup (~line 667): add s.block_timer1=[0.0]*count1 and s.block_timer2=[0.0]*count2; read s.block_recharge1=unit1.get("charge_recharge_time",0) and s.block_recharge2=unit2.get("charge_recharge_time",0).
   - In the per-tick loop where shields are recharged (search for shield_timer logic): add analogous logic â€” if block_timer[idx] > 0: block_timer[idx] -= DT; if block_timer[idx] <= 0: has_blocked[idx] = False.
   - At block trigger lines 1037/1472: after setting t_blocked[target_idx]=True, also set t_block_timer[target_idx] = d_block_recharge (the cooldown for the defender).
   If charge_recharge_time is 0 (no recharge, block-once behavior for any future unit), the timer never resets â€” backward compatible.

### Konnik dismount-on-death: mounted Konnik respawns as Dismounted Konnik with separate HP, stats, and armor classes

**Fix:** Three fixes required in analysis/config_combat.py:

1. ARMOR FIX (highest severity, affects all unit matchups vs dismounted regular Konnik):
   In the "konnik" entry (line 59), change:
     "dismount_melee_armor": 1,
     "dismount_pierce_armor": 1,
     "dismount_armors_json": '{"1": 0, "3": 1, "4": 1, "19": 0, "31": 0}',
   to:
     "dismount_melee_armor": 2,
     "dismount_pierce_armor": 2,
     "dismount_armors_json": '{"1": 0, "3": 2, "4": 2, "19": 0, "31": 0}',
   After changing, regenerate webapp/aoe2_reference.db and webapp/aoe2_units.db per the build pipeline.

2. ATTACK DELAY FIX (affects dismount attack timing):
   In both "konnik" (line 62) and "elite_konnik" (line 74), change:
     "dismount_attack_delay": 0,
   to:
     "dismount_attack_delay": 0.76,
   (Using SiegeEngineers' authoritative AttackDelaySeconds=0.76 = FrameDelay 19 / 25fps game tick rate, not our extractor's 0.317 which uses 60fps denominator.)
   The sim at simulation.py line 2161 will then enter the commit-window path and correctly delay the attack by 0.76s.

3. ATTACKS_JSON FIX (affects building damage only):
   In both "konnik" (line 64) and "elite_konnik" (line 76), add class 21 (+4 vs Standard Buildings):
     "konnik" dismount_attacks_json: '{"4": 12, "21": 4, "1": 0, "19": 0, "31": 0}'
     "elite_konnik" dismount_attacks_json: '{"4": 13, "21": 4, "1": 0, "19": 0, "31": 0}'

### Monaspa Mountain Affinity â€” nearby ally attack bonus

**Fix:** webapp/simulation.py lines 499-510: Replace the 1:1 ratio with a floor-division by 7 to match the real-game threshold. Corrected logic:

    if nearby_bonus1 > 0:
        max_nearby1 = unit1.get("nearby_bonus_count", 4)
        qualifying_allies1 = count1 - 1  # unit itself does not count
        effective_nearby1 = min(max_nearby1, qualifying_allies1 // 7)
        s.dmg1 += nearby_bonus1 * effective_nearby1

Apply the same pattern for nearby_bonus2 (lines 506-510). This correctly yields: 0 bonus for <7 allies, +1 for 7-13, +2 for 14-20, +3 for 21-27, +4 for 28+ allies (cap). The "frozen bonus" issue (bonus not recalculated as allies die) is a lesser inaccuracy inherent to the pre-tick-loop architecture and is acceptable as a known approximation.

Also update the comment in analysis/config_combat.py line 150: change "per 7" to "groups of 8/15/22/29" to match wiki wording, and update the sim comment to reflect floor(allies/7) approximation.

### Obuch armor stripping (armor_strip_per_hit): each hit reduces target melee and pierce armor by 1, floored at 0

**Fix:** In webapp/simulation.py lines 1515â€“1520, change the floor from -99 to 0:
  t_current_ma[target_idx] = max(0, t_current_ma[target_idx] - a_armor_strip)
  t_current_pa[target_idx] = max(0, t_current_pa[target_idx] - a_armor_strip)
This caps armor stripping at 0 as the real game does. A secondary improvement would be resetting current_ma/current_pa to their original values if a unit is healed to full HP, but this has minimal impact in the 1v1 sim.

### Ratha (Melee) bonus_damage_reduction â€” Bengali civ bonus "Elephant units receive 25% less bonus damage"

**Fix:** In analysis/config_combat.py, remove lines 198-201 (the four Ratha entries under CIV_COMBAT_PROPERTIES that set bonus_damage_reduction=0.25). Then regenerate aoe2_reference.db and aoe2_units.db via the build pipeline (python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db), and rerun compute_battle_scores.py to refresh battle scores. The correct value is 0.0 (no bonus damage reduction) for all Ratha variants, matching the dat file and the game's "C-Bonus, Elephant resistance" tech effect which targets only elephant unit IDs.

### Shrivamsha Rider Dodge Shield â€” per-charge recharge timer is 5Ã—/7Ã— too long in the simulation

**Fix:** Two-line fix in webapp/simulation.py â€” replace the hardcoded dodge_recharge1/dodge_recharge2 timer resets at lines 1619 and 1629 with the per-charge value (total / max):

Line 1619: change `shield_timer1[i] = dodge_recharge1` to `shield_timer1[i] = dodge_recharge1 / dodge_max1`
Line 1629: change `shield_timer2[i] = dodge_recharge2` to `shield_timer2[i] = dodge_recharge2 / dodge_max2`

This uses the already-stored total recharge (20.0s) divided by the already-stored max charges (5 or 7) to get the correct per-charge interval: 4.0s (regular) and â‰ˆ2.857s (elite). No DB rebuild or analysis pipeline change required. After fixing, rerun compute_battle_scores.py and regenerate .golden/baseline.json.

### Sicilians civ bonus: Land military units receive 40% less bonus (counter) damage â€” siege weapons are excluded by the game's definition of this bonus.

**Fix:** Remove lines 238-239 from analysis/config_combat.py:
    ("Sicilians", "scorpion"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "heavy_scorpion"): {"bonus_damage_reduction": 0.4},
Then regenerate the pipeline: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db (and rerun compute_battle_scores.py if scorpion matchups are in scope). No simulation.py changes needed.

### attack_speed_ramp â€” Temple Guard (Muisca): each hit reduces reload time by 0.2s for 5 seconds (per-hit independent timer), stacking up to a 1.0s minimum reload

**Fix:** In webapp/simulation.py, replace the scalar ramp_reduction arrays with per-unit lists of (expiry_timestamp, reduction_amount) tuples (a rolling buffer). On each hit, append (current_time + 5.0, attack_speed_ramp) to the unit's buffer. Before computing the cooldown each tick (or when setting it after a hit), prune entries where expiry_timestamp <= current_time, then sum the remaining reductions and apply max(attack_speed_min, base_reload - active_sum). This requires: (1) adding attack_speed_ramp_duration=5.0 to UNIQUE_COMBAT_PROPERTIES in analysis/config_combat.py for both "temple_guard" and "elite_temple_guard" keys, (2) propagating the new column through generate_reference.py/generate_main_db.py schema, (3) loading it in prepare_combat_unit(), and (4) replacing the three identical ramp blocks (lines ~2109-2114, ~2239-2244, ~2270-2275) with the expiry-aware logic. The fix must track current simulation time alongside each reduction entry.

### Turtle Ship cannon (charge_type=7 burst, melee 20 dmg, 0.5 AoE) + rocket AoE (blast_width=0.3, blast_damage=1.0)

**Fix:** Three changes needed:

FILE: analysis/combat_properties.py

(A) FIX CANNON EXTRACTION â€” lines 120-128. Add a branch for `charge_type==7` when `max_proj == total_proj` (the Turtle Ship case where the burst IS the whole attack count, not a delta). The correct count is 1 cannon projectile per cycle. Override in UNIQUE_COMBAT_PROPERTIES in analysis/config_combat.py since the dat encodes no delta:
  Add to UNIQUE_COMBAT_PROPERTIES: `"turtle_ship": {"charge_projectile_count": 1, "charge_recharge_time": 6.0}` and `"elite_turtle_ship": {"charge_projectile_count": 1, "charge_recharge_time": 6.0}` (6s = full attack cycle per wiki). The `charge_projectile_attacks_json` is already extracted correctly from the dat.

(B) FIX ROCKET AOE EXTRACTION â€” lines 130-138. Add a handler for `blast_level==2 AND blast_damage==1.0 AND blast_width>0` to set `splash_on_hit_radius`. The existing trample guard (`0 < blast_damage < 1.0`) correctly excludes this case. Change:
  `elif blast_level == 11:` â†’ add a new branch:
  `elif blast_level == 2 and blast_damage >= 1.0:` â†’ `props["splash_on_hit_radius"] = round(blast_width, 2)`
  (Verify no other units have blast_level=2 + blast_damage=1.0 unintentionally hit by this â€” check extraction/extracted_data/units.json.)

FILE: analysis/config_combat.py  
Add entries to UNIQUE_COMBAT_PROPERTIES (keyed by base slug without civ suffix):
  `"turtle_ship": {"charge_projectile_count": 1, "charge_recharge_time": 6.0},`
  `"elite_turtle_ship": {"charge_projectile_count": 1, "charge_recharge_time": 6.0},`

After making these changes, regenerate webapp/aoe2_reference.db and webapp/aoe2_units.db via the build pipeline. The simulation.py cannon logic (lines 813-851) will then fire correctly once `charge_projectile_count=1` is in the DB â€” no simulation.py changes needed.

### Sicilian inherent bonus_damage_reduction â€” scorpion and heavy_scorpion incorrectly included

**Fix:** In analysis/config_combat.py, remove lines 238â€“239 entirely:
  ("Sicilians", "scorpion"): {"bonus_damage_reduction": 0.4},
  ("Sicilians", "heavy_scorpion"): {"bonus_damage_reduction": 0.4},
Then rebuild the pipeline: python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db, and rerun compute_battle_scores.py. The simulation.py logic itself requires no change.

## LOW severity (7)

### Blackwood Archer (Tupi) Curare poison / bleed-on-hit

**Fix:** The data values need no change. For the simulation, two improvements are possible if higher fidelity is desired:

1. STACKING BLEED (simulation.py lines 1084, 1581): Replace the single dict slot with an additive model. Change `t_bleed[target_idx] = (a_bleed_dps, a_bleed_dur)` to add a new entry per hit, e.g. use a list of `(dps, remaining)` tuples per target index, then sum their contributions each tick in `_apply_tick_effects` (lines 1659-1680). This would more accurately reflect the real game's per-projectile independent poison stacks.

2. MIXED BATTLE BLEED (simulation.py `simulate_mixed_battle()`): Add bleed tracking infrastructure analogous to what `simulate_battle()` uses (lines 669-670, 1659-1680). Given the docstring acknowledges this as a deliberate simplification for performance, the fix would need intentional design work.

Both are known trade-offs; the data stored in `analysis/config_combat.py` line 341 is correct and requires no change.

### Guecha Warrior ally_death_heal â€” heal-over-time triggered by ally death

**Fix:** Add an ally_death_heal_radius field to the data model (analysis/config_combat.py UNIQUE_COMBAT_PROPERTIES for guecha_warrior and elite_guecha_warrior: ally_death_heal_radius=6.0), propagate it through generate_reference.py and generate_main_db.py as a new unit_stats column, then in simulation.py lines 2291â€“2302 replace the unconditional timer-set loop with a radius-gated version: only set the heal timer on survivors whose simulated position is within 6 tiles of the dead unit. Because the sim is currently positionless, a practical interim fix is to document the gap and note that in clumped (normal) formations the approximation is accurate; full fix requires positional tracking in simulate_battle().

### Jian Swordsman HP Transform â€” three sub-claims: (1) Castle Age HP regen 15 vs wiki 20, (2) transform movement speed not applied in sim tick loop, (3) transform_attack_speed dead/ignored field

**Fix:** For the regen discrepancy: no fix needed â€” DB value of 15 HP/min Castle Age is correct per the dat; the wiki's alleged 20 HP/min cannot be verified and is likely incorrect or misread. For the transform movement speed sim gap (lines 448-449 of webapp/simulation.py): in _apply_tick_effects() (around line 1709), after the transform flag flips, update the local speed variable. The cleanest fix is to store transform_movement_speed on the sim state and apply it: after line 1716 (transformed1[idx] = True), set s.speed1_transform = transform1["movement_speed"] and use it in approach-phase speed calculations; after line 1716's revert branch, restore s.speed1. Because Jian Swordsman is melee-only and speed only governs approach time, this fix has negligible effect on 1v1 outcomes but would be correct for any future transform unit with a ranged/kiting profile. The transform_attack_speed dead field needs no immediate fix for Jian Swordsman; a comment documenting the limitation suffices.

### Longboat extra projectiles: 1 main arrow at full damage + 3 secondary arrows at 1 (minimum) damage each

**Fix:** In analysis/config_combat.py, add entries to UNIQUE_COMBAT_PROPERTIES for both longboat slugs:

  "longboat_vikings": {"extra_projectile_attacks": {"3": 1}},
  "elite_longboat_vikings": {"extra_projectile_attacks": {"3": 1}},

This mirrors the pattern used for Chu Ko Nu ("extra_projectile_attacks_json": '{"3": 3}'). After adding these overrides, rebuild the DB pipeline (analysis/generate_reference.py then analysis/generate_main_db.py) so that extra_projectile_attacks_json is populated to '{"3": 1}' in both aoe2_reference.db and aoe2_units.db. The simulation.py code path at lines 564-577 will then correctly calculate extra arrow damage against target armor â€” which for minimum-damage arrows against any target with â‰¥1 pierce armor will resolve to the game's minimum of 1 damage, matching the real mechanic. No changes to simulation.py are needed; the bug is purely a missing data override.

### Organ Gun scatter projectiles: accuracy=0% means all projectiles (primary + extras) scatter to random targets, not just the extras

**Fix:** Add `accuracy: 0` to the Organ Gun entries in `UNIQUE_COMBAT_PROPERTIES` in `analysis/config_combat.py` (around line 136): `"organ_gun": {"extra_proj_scatter": 1, "accuracy": 0}` and `"elite_organ_gun": {"extra_proj_scatter": 1, "accuracy": 0}`. Then ensure `analysis/generate_main_db.py` writes `accuracy` as a column in `unit_stats` (schema + `build_combat_dict_from_ref`), and `webapp/app.py` `api_combat_unit()` SELECTs it. Alternatively â€” and simpler since all Organ Gun projectiles scatter identically â€” treat `extra_proj_scatter=1` as implying the primary projectile also scatters: in the simulation at `webapp/simulation.py` lines 2188-2210 and 1127-1139, add a check `if t_scatter: ...route primary to random target...` before the `t_accuracy >= 1.0` branch, to handle the case where the unit has scatter-only projectiles (accuracy=0 + scatter=1 together mean all shots randomize).

### Thirisadai extra projectiles â€” secondary arrow accuracy (4 extra arrows at 85% hit chance vs 100%)

**Fix:** Two changes needed:

1. DATA (analysis/generate_reference.py): The extraction pipeline needs to read the secondary projectile unit's accuracy from the full DAT unit list. In extraction/run.py, ensure sub-projectile units (e.g. id 1779) are exported or accessible. Then in generate_reference.py, after reading base_accuracy from base_snap["accuracy"], check if unit_data has a secondary_projectile_unit with a different accuracy, and store that in a new column (e.g. extra_proj_accuracy) in ref_units. As a simpler interim fix: add thirisadai_dravidians to analysis/config_combat.py UNIQUE_COMBAT_PROPERTIES with {"extra_proj_accuracy": 85} or a workaround by overriding base_accuracy to 85 (matching the CKN pattern â€” but this would incorrectly affect primary accuracy too).

2. SIMULATION (webapp/simulation.py): Add a new unit property extra_proj_accuracy (distinct from base_accuracy) that defaults to base_accuracy if absent. In prepare_combat_unit() (~line 457), change to: s.extra_accuracy1 = (unit1.get("extra_proj_accuracy") or unit1.get("base_accuracy", 100) or 100) / 100.0. Then ensure the ref_units and unit_stats SELECT in app.py api_combat_unit() includes the new column. This allows Thirisadai to carry extra_proj_accuracy=85 independently of its primary accuracy=100.

### Projectile pass-through (Slinger / imp_slinger, Mapuche Malon UT)

**Fix:** In analysis/config_combat.py, change pass_through_count from 1 to 3 for all six Malon-affected unit entries in CIV_COMBAT_PROPERTIES (lines 326â€“334): ("Mapuche","bolas_rider"), ("Mapuche","elite_bolas_rider"), ("Mapuche","slinger"), ("Mapuche","imp_slinger"), ("Mapuche","elite_skirm"), ("Mapuche","imp_elite_skirm"). Example diff for lines 331â€“332:

  ("Mapuche", "slinger"): {"pass_through_percent": 0.30, "pass_through_count": 3},
  ("Mapuche", "imp_slinger"): {"pass_through_percent": 0.30, "pass_through_count": 3},

After editing, rerun the build pipeline (generate_reference.py â†’ generate_main_db.py â†’ compute_battle_scores.py) so aoe2_reference.db, aoe2_units.db, and battle_scores.json reflect the corrected count. No changes needed to simulation.py â€” the loop logic already supports any count value correctly.
