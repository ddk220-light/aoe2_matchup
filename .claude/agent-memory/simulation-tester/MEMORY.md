# Simulation Tester Agent Memory

## Key Findings

### Damage Formula Direction
- `_calc_damage` iterates over **defender armor classes**, checking if attacker has matching attack class
- Bonus damage only applies if defender HAS the armor class (e.g., Champion's anti-spearman bonus won't apply to Paladin because Paladin has no Spearman armor class)
- This matches AoE2 game mechanics: bonus damage targets armor classes, not unit types

### Unit Slug Lookups
- Elite Skirmisher slug: `elite_skirm` (NOT `elite_skirmisher`)
- `unit_stats` table has no `age` column; use `units.age_id` via JOIN if needed
- Units table uses `display_name` (not `name`)

### Khitans Lamellar Armor (damage_reflect_percent=0.25)
- Applies to ALL Khitans units (champion, halberdier, elite_skirm, etc.)
- Only triggers on melee attacks (ranged attacks don't cause reflect)
- Formula: `reflect_dmg = max(1, int(damage_dealt * 0.25))` -- always at least 1
- Reflect is applied in the damage application phase, after the main hit
- Khitans lack Blast Furnace (-2 base attack), which significantly reduces halberdier anti-cav bonus
- For halbs: the -10 anti-cavalry bonus damage loss far outweighs the 25% reflect gain

### Simulation API
- `simulate_battle(unit1, unit2, resources=0, fixed_count=30, return_hp=True, return_ticks=True)`
- Returns 6-tuple: `(winner, rem1, rem2, hp_pct1, hp_pct2, elapsed_ticks)`
- `attack_speed` field = attacks per second (NOT reload time). Reload = 1.0/attack_speed
- Deterministic for melee-vs-melee (no RNG except trample hit chance)
- Use `random.seed(42)` for reproducibility

### Scorpion Line Mechanics
- Pass-through: hits up to `pass_through_count` additional targets for `pass_through_percent` of damage
- Scorpion/Heavy Scorp: pass_through_count=3 (hits 3 extra targets, NOT just 1)
- Scorpion PT%: ~45.5% (base/heavy vary slightly: heavy=42.9% for Chinese due to Rocketry scaling)
- Ballista Elephant: pass_through_count=3, PT%=66.7% (elite=60%)
- `min_attack_range >= 2.0` triggers `cant_attack_melee=True`: scorpions CANNOT fire in melee phase
- Entire scorpion-vs-melee matchup decided by opening volley; melee phase is one-sided cleanup
- Mounted Trebuchet (Khitans): `is_siege_projectile=0`, `splash_radius=0.0` -- NO area damage in sim (potential data gap)
- Mounted Treb does melee damage at range (class 4=31, no pierce class): targets melee armor not pierce
- Chinese Rocketry adds +4 pierce to scorpions, transforming Heavy Scorp from 7->10 dmg vs 5 PA targets (43% boost)
- Khitans Siege Engineers gives +1 range to Heavy Scorp (8 vs 7) but same # opening shots in most matchups

### New Mechanics (pass_through_count, extra_proj_scatter)
- `pass_through_count`: DB column, defaults to 1 in `prepare_combat_unit` via `row.get()`
- `extra_proj_scatter`: DB column, defaults to 0. When 1, extra projectiles target random alive enemies
- **API gap**: `/api/combat-unit` does NOT return `pass_through_count` or `extra_proj_scatter` in response JSON
- For simulation, use direct DB query + `prepare_combat_unit(dict(row))` to get all fields
- Must convert `sqlite3.Row` to `dict()` before passing to `prepare_combat_unit` (no `.get()` on Row)

### War Chariot (Shu)
- Slug: `war_chariot_shu`, has Castle (age_id=3) and Imperial (age_id=4) entries
- Imperial stats: HP=65, Atk=9(8P), Range=6, Min Range=1, RoF=0.133 (7.52s), MA=3/PA=9
- pass_through: 50% to 3 targets; extra_projectiles=6 (no scatter, focused on primary)
- Shu Bolt Magazine (Imp UT) adds +6 extra projectiles via CIV_COMBAT_PROPERTIES
- IS ranged (range=6 >= 1.0, pierce damage) -- gets opening volley
- NOT cant_attack_melee (min_range=1 < 2.0) -- can fire in melee phase
- Very slow reload (7.52s) but extra projectiles compensate

### Organ Gun (Portuguese)
- Elite: HP=70, Atk=8(8P), Range=8, Min Range=1, RoF=0.29 (3.45s), MA=2/PA=6
- extra_projectiles=5 (elite), scatter=1 -- extra projs hit random alive targets
- No pass-through, no separate extra_projectile_attacks (extra projs same dmg as main)
- Low individual projectile damage (3 vs 5 PA champion) but spread across many targets

### DB Query Patterns
- `unit_stats` has no `age` column; use `units.age_id` via JOIN
- `unit_stats` has no `accuracy` column; `prepare_combat_unit` defaults to 100
- Mounted Trebuchet has 2 entries (age_id=3 Castle, age_id=4 Imperial) with same slug; use `ORDER BY u.age_id DESC LIMIT 1` or explicit age_id filter
- Combat-unit API: `/api/combat-unit/<civ_name>/<unit_slug>` (path params, NOT query params)
- API `fetchone()` may return wrong age for multi-age slugs; prefer direct DB access for precision

### Elite Janissary (Turks) Key Findings
- Slug: `elite_janissary_turks` (Imperial), `janissary_turks` (Castle)
- Classified under `gunpowder` line (not archer)
- **Accuracy: 65%** -- one of the lowest-accuracy ranged units
- Turk civ bonus: +25% HP to gunpowder units (40 -> 50 HP)
- Stray hit mechanic significantly boosts effective accuracy: 65% nominal -> ~80% effective vs 20 targets
- Ranking: #14/31 ranged_effectiveness overall, but #4 anti-archer, #4 vs paladin (30v30)
- Dead last (#31) in general_combat and vs_champion scores
- 20v20 vs Japanese Champions: wins 10/10, avg 19.1 survivors at 86% HP

### Accuracy Stray Hit Mechanic
- When a shot misses (1 - accuracy chance), there's a stray hit chance
- Stray chance = `min(0.5, len(alive_enemies) * 0.05)`
- 20 enemies: 50% stray chance. 10 enemies: 50%. 5 enemies: 25%. 1 enemy: 5%
- Stray target is random.choice(alive_enemies)
- `miss_damage_percent` field overrides the generic stray formula if set
- This means even 50% accuracy units have ~62-75% effective hit rate vs groups

### Reference DB vs Main DB
- Reference DB (`aoe2_reference.db`) has `ref_units` table with fully computed stats (final_*)
- Reference DB has `battle_scores` table with pre-computed ranking scores
- Combat unit API uses ref DB: `/api/ref/combat-unit/<civ>/<slug>?age=Imperial`
- ORIGINAL_13_CIVS list has ~50 civs (misleading name)

### Environment
- Must `cd webapp` or `os.chdir('webapp')` before imports (relative paths in app.py)
- DB path (linux): `/home/user/aoe2-unit-analyzer/webapp/aoe2_units.db`
- Import path: `sys.path.insert(0, 'webapp')` then `os.chdir('webapp')`
- EXTRA_PROJ_ACCURACY (0.5) can be imported: `from simulation import EXTRA_PROJ_ACCURACY`... actually it's a local var in simulate_battle, not exported
