# Data Model Review — how stage 1–3 stores and derives, and the target architecture

*Last verified: 2026-06-11 · game build 177723 · branch `staging`*

A deep critique of the extraction/analysis data model: what is stored, what is derived,
where the model is right, and where curation has crept in that should be derivation.
Written against verified evidence (every load-bearing claim below was checked in the
DBs/JSONs on 2026-06-10; one major agent claim was refuted during verification and is
recorded in §6 so it doesn't resurface).

**The owner's design principle, which this review adopts as the yardstick:**
*store underlying facts + functions that derive everything else; cache derived artifacts
only with provenance; keep one-off curation to what the dat genuinely cannot express.*

The litmus test used throughout: **"when a new patch/DLC lands, which files must a human
hand-edit?"** Every hand-edit point is a drift risk. Three incidents this quarter came
from exactly this: the phantom-unit purge (776 wrong rows), its Cumans/Dravidians
collateral (fixed 2026-06-10), and the 21 orphan config keys.

---

## 1. What is stored today (the factual map)

Per `(civ × unit_slug)` — 972 Imperial-only rows in `ref_units` (the
2026-06-11 Imperial-only purge deleted the 871 Castle rows, the 4 militia
ghost rows and the 4 phantom 3K siege rows; ages below Imperial exist only
as tech-staging inside the Imperial chain):

| Group | Storage | Origin |
|---|---|---|
| Base scalar stats (hp, attack, armors, speed, range, reload, accuracy, LOS) | `base_*` columns | dat `units.json` |
| Final scalar stats | `final_*` columns | derived: base + effect chain |
| Per-class attacks/armors | `attacks_json` / `armors_json` (dicts keyed by armor-class id, 40 classes) | dat + per-class effect commands |
| Costs (food/wood/gold), train time | `final_cost_*` columns | dat + cost effect commands (discounts DO flow — §6) |
| 52 special-ability properties | flat columns on `ref_units` + audit rows in `ref_special_effects` | 19 dat-derived, 33 hardcoded in `config_combat.py` |
| Multi-form blocks (dismount/transform) | 9 flattened columns each | derived per civ at generation time (`derived:form_tech_chain`, since `bcdbcbc`); config keeps only the form unit ids + Jian threshold |
| Audit trail | `ref_techs_applied`, `ref_stat_chain` (per-step stat snapshot), `ref_special_effects` (source-tagged), `ref_projectiles` | generated |

The derivation functions (the "interpreters" the owner asked about):

| Function | Role |
|---|---|
| `unit_analyzer.get_base_stats()` | dat unit dict → mutable `UnitStats` (scalars + per-class dicts) |
| `unit_analyzer.apply_effect_command()` | dispatches effect command types 0/4/5 (set/add/multiply); decodes the `class*256+amount` per-class encoding; covers HP/attack/armor/speed/range/reload/accuracy/LOS/train-time/costs/regen |
| `unit_analyzer.calculate_unit_stats_for_civ()` | the full chain: base → standard techs → civ bonuses → team bonuses (partial, §4) → unique techs → work rate; records every step |
| `combat_properties.get_extracted_combat_properties()` | decodes dat ability fields: `blast_attack_level`/`blast_width` (trample, splash, pass-through), `charge_type` 4/6/7 (dodge shield, extra projectiles, burst), `total_projectiles`, `bonus_damage_resistance`, attr-109 regen |
| `combat_properties.get_combat_properties()` | 4-layer merge: extracted → `COMBAT_PROPERTIES` (30) → `UNIQUE_COMBAT_PROPERTIES` (52) → `CIV_COMBAT_PROPERTIES` (89); later wins |
| `combat_unit_loader.build_combat_dict_from_ref()` | ref row → ~100-key combat dict (the single serving contract) |
| `simulation.prepare_combat_unit()` | combat dict → engine-ready (~73 keys, JSON parsed, defaults) |
| `weighted_cost()` | food + 0.7·wood + 1.5·gold (canonical in `simulation_real.py`) |

## 2. What the model already gets right — do not churn these

1. **Per-class attacks/armors as class-keyed dicts** is exactly the game's own model
   (40 armor classes; bonus damage = attack entry vs armor entry, missing armor entry
   defaults to 0 — verified matching game semantics in `_calc_damage`).
2. **Store-final-with-replayable-provenance.** `ref_stat_chain` records the stat state
   after *every* tech application. This is the correct reading of "store underlying data
   and derive": the underlying facts (dat + effects) are kept, the derivation is a pure
   function, and the cached result carries its own proof. Serving recomputes nothing.
3. **The 4-layer override semantics** (dat → standard → unique → civ-conditional, later
   wins) are clear and consistently applied.
4. **Costs and discounts flow correctly** through multiply/add commands on cost
   attributes — verified: Berbers paladin 48f/60g (−20%), Goths champion 35f/14g (−30%),
   Berbers hussar 64f (−20%). Equal-resources sims price discounts correctly.

## 3. The five structural problems

### 3.1 Availability: four mechanisms, none of them the game's

> **Census re-pinned 2026-06-11 (Imperial-only purge): 163 mismatches over
> 1,325 Imperial cells (1,162 agree) — ref DB side CLEAN, swap still NOT
> performed.** The site's data model went Imperial-only: Castle rows were
> deleted from `ref_units` (and `aoe2_units.db`), and `generate_reference`
> stopped emitting them (tech staging through Castle untouched). Both
> ref-DB-side mismatch classes the 2026-06-10 report exposed are now fixed
> derivationally: the 4 militia ghost rows (Incas/Mapuche/Muisca/Tupi
> `champion`) die via the new
> `AvailabilityResolver.tech_tree_disabled_unit_closure()` gate that
> `generate_reference` consults (type-2 tech-tree unit disables expanded
> through type-3 upgrade edges — kills the bug class for future DLCs), and
> the suspect 3K siege rows were confirmed phantom against the game's
> CivTechTrees JSON (Trebuchet NotAvailable for Shu/Wei/Wu — they field the
> Traction Trebuchet; Scorpion/Heavy Scorpion NotAvailable for Shu) and
> pruned via the existing `availability_tech` mechanism (trebuchet → tech
> 256, heavy_scorpion → tech 94; both tree-disabled for exactly those
> civs). Every remaining mismatch is a categorized RESOLVER-side limitation
> pinned in `tests/test_availability_resolver.py`: 56 `regional_grant`
> missing + 1 tier (CivTechTrees-external grants incl. the Hei-Kuang /
> Rocket Cart / Siege Elephant alternates and Vietnamese Imp Skirm), 104
> `team_bonus_leak` phantoms (condottiero + elite_genitour, no in-dat
> per-civ gate), 1 `enable_mechanism` (Flemish Revolution unit-spawn), 1
> `mode_gating` (Wei Paphos Champion, Chronicles). ~~Known leftover: a few
> phantom-derived rows linger in `derived_data.db`/`pool_scores.db`
> (Shu heavy_scorpion, 3K trebuchet battle/pool scores) — out of scope this
> pass, cleaned by the next derive run.~~ **Resolved 2026-06-11**: phantom
> rows purged from `battle_scores` (116 rows, both builds), `pool_scores`
> (6), `patch_matchup_changes` (2); ranks renumbered; full 177723 re-derive
> from the baseline (which was verified already phantom-free — trebuchet is
> never enumerated for matchups, and the baseline's 516 (civ,slug) pairs
> exactly match the purged ref DB). Naval rows + golden byte-identical.
>
> *(Historical, 2026-06-10 report against the then Castle+Imperial DB:)*
> **Resolver report 2026-06-10 (Phase B core): 282 mismatches — swap NOT
> performed.** `analysis/availability_resolver.py` implements the full
> fixed-point resolution (per-tech civ binding, `required_tech_count`,
> dynamic type-102 disables from fired techs, type-2 enables / type-3
> upgrade-edge walking, age-phase staging, `full_tech_mode == -1` as the
> Full-Tech-Tree-only marker, default-enabled seed {74 Militia, 545
> Transport Ship} probed from the per-civ unit tables). Against the
> committed ref DB standard rosters it scores **2,050 / 2,332 agree** and
> the Phase B gate required exactly 0 mismatches, so generate_reference
> still uses the blocklist + `_AVAILABILITY_OVERRIDES`.
> `tests/test_availability_resolver.py` pins the full 282-row census (and
> keeps the 2,050-row agreement green; the gate itself is an xfail).
>
> **The "New evidence" paragraph below is REFUTED for the 17 allowlist
> lines** — written before `required_tech_count` semantics were checked
> against the dat. Tech 235's prereqs `[102, 858]` with `count=1` mean
> "Castle Age OR the Gurjaras early-camel slot": it fires for **every**
> civ, there is no "one slot per enabling civ". The actual in-dat regional
> mechanism is the reverse: tech **79 "Disable Regionals"** (civ −1, no
> prereqs) fires for every civ at game start and 102-disables every
> regional make-avail/upgrade tech (camels, battle/armored elephants,
> eagles, steppe lancers, slingers, fire lancers, elephant archers, rocket
> carts, hei-kuang, champi, traction treb, dromon…); the only counter is
> tech 78 "[FTT] Enable Regionals" with `full_tech_mode = -1` (fires only
> in Full-Tech-Tree games). **The per-civ regional grants are not in the
> dat at all** — they ship in the game's per-civ
> `resources/_common/dat/CivTechTrees/<CIV>.json` (verified locally:
> Berbers' file carries node 329 Camel Rider `RegionalUnit /
> ResearchedCompleted`), and aoe2techtree.net's generator reads exactly
> those files rather than resolving the dat. So the curated lists are
> irreducible **until the pipeline extracts CivTechTrees JSON**, which is
> the real Phase B successor task.
>
> What the resolver derives correctly today (all pinned green): every
> default-roster line and tier for all 53 civs, Burgundians Castle-age
> Cavalier, Winged Hussar via the 786 OR-slots (788/789 civ-bound), the
> 655/656 Imperial Skirmisher interlock, and four genuine early-tier civ
> bonuses the config age-gating cannot express (Cumans Capped Ram @Castle,
> Khitans Heavy Cav Archer @Castle, Armenians Halberdier + Champion
> @Castle). It also exposed four likely **phantom ref rows**: the
> Incas/Muisca/Mapuche/Tupi militia lines (their tech trees type-2-disable
> unit 74; Incas' CivTechTrees JSON confirms Militia/M@A/Champion
> NotAvailable) plus suspect 3K trebuchet/scorpion rows — worth a
> follow-up pass against SiegeEngineers data.

Today a unit's per-civ existence is decided by **four cooperating mechanisms**:
`disabled_techs` blocklist + per-line `availability_tech` + `civ_only` /
`_AVAILABILITY_OVERRIDES` allowlists (17 lines, hand-synced from SiegeEngineers) +
a stage-4 `CIV_MISSING_UNITS` exclusion set in `webapp/unit_lines.py`. The blocklist
alone produced 776 phantom rows; the allowlist fix then silently dropped Cumans Camel
Rider and Dravidians Battle Elephant at Imperial.

**New evidence (verified 2026-06-10): the dat encodes availability fully — we just
don't extract enough to resolve it.** The camel chain: shadow tech 235 "Make Camels
Available" requires `[102 (Feudal Age), 858]`; tech 858 "Camel Scout (make avail)" is
**civ-bound** (`civ: 42` in the extracted record — the per-tech civ field IS captured).
Genie resolves these via `required_tech_count` ("fire when ≥N of the prereq slots are
satisfied"), with one slot per enabling civ — **and our extraction drops
`required_tech_count` entirely** (`extract_techs.py` doesn't read it). Without it, no
resolver can work, which is why curation grew instead. This is the same fixed-point
resolution aoe2techtree.net performs on the dat.

**Target:** a tech-tree **resolver** in extraction — iterate to fixed point: a shadow
tech auto-fires when (its civ field matches or is −1) ∧ (not in the civ's
disabled_techs) ∧ (≥ required_tech_count prereqs fired); apply type-2 enable/disable-unit
and type-102/103 commands; emit `availability.json` (civ → enabled unit ids per age).
Then:
- `_AVAILABILITY_OVERRIDES` becomes a **test** asserting resolver output ==
  SiegeEngineers data.json (curation → assertion; mismatches become a tiny documented
  exception table, expected size ~0).
- `CIV_MISSING_UNITS` becomes generated or asserted from the same source.
- Next DLC's availability is automatic, and the Cumans bug class dies.

### 3.2 Special abilities: 52 flat columns, a 6-file chain, no schema

> **Status: Phase A landed 2026-06-10; Phase B (registry-driven generation)
> landed 2026-06-10 in the same window** — the §7 Phase A resolver/line-graph
> items are separate and still open.
> **Phase A:** `analysis/ability_registry.py` (36 abilities / 77 params across
> 11 families, every pipeline property declared with type, default, ref
> column, source, engine coverage, audit description and quirks) +
> `tests/test_ability_registry.py` (orphan-key allowlist vs the committed ref
> DB, registry↔config↔schema↔loader↔engine parity, defaults vs
> `prepare_combat_unit`). The orphan audit lives as a strict-equality test: 20
> allowlisted dead keys (15 `COMBAT_PROPERTIES` exact-match misses — Feudal-only
> stages + civ-suffixed uniques; `elite_xianbei_raider`; Sicilians
> `hand_cannoneer`/`heavy_camel`, Poles `winged_hussar`, Romans `legionary`);
> any NEW orphan fails the suite. (`Dravidians/elite_elephant` left the orphan
> list with the 2026-06-10 restore — verified.)
>
> **Phase B (columns stay — `abilities_json` storage was NOT adopted, optional
> / not planned):** the registry now *generates* (a) the ability-column DDL
> fragment, the ref_units UPDATE writer and the `ref_special_effects` audit
> list in `analysis/generate_reference.py` (legacy column/audit order pinned
> there for schema byte-stability; new params append automatically), (b) the
> ability-key mapping of `combat_unit_loader.build_combat_dict_from_ref`, and
> (c) `simulation.prepare_combat_unit`'s ability defaults
> (`combat_dict_defaults()`; the abstract engine's consumed-key subset stays
> pinned in `_PREPARE_SCALAR_KEYS`). Output-identity gates, all zero-diff:
> scratch regen vs pre-refactor scratch regen byte-identical across all 7
> tables (vs the committed DB: only the 4 known Mayan-cost rows + a 2-row
> Konnik audit-order artifact of the old surgical patch, sets equal); 1,851-row
> type-aware dict comparison for the loader, prepared units, and the
> `generate_main_db` sibling. `sim_version` untouched
> (`e221c8a3a0437bd8`). `generate_main_db.build_combat_dict_from_ref`
> deliberately keeps its bespoke special-effects/projectiles-table merge
> (an import-swap would change `aoe2_units.db`: 231 dict-level disagreements
> in 6 keys, measured) — instead the registry pins its key set and a full-row
> agreement test documents the two exception classes
> (`tests/test_ability_registry.py::test_maindb_dict_agrees_with_webapp_loader`).
> Adding an ability is now registry entry + config value + handler per engine
> (runbooks §3); a JS manifest for `simulate.js` remains open (engine-parity
> stays presence-only).

**The family taxonomy** (shared core vs per-unit quirks; full detail in the registry):

| Family | Abilities (params) | Shared core / notable quirks |
|---|---|---|
| projectile_volley | extra_projectiles(2), first_attack_burst(1), charge_projectile_volley(3), extra_proj_scatter(1) | extras roll `base_accuracy` (TR primary-only; `EXTRA_PROJ_ACCURACY=0.85` is a dead fallback); CKN/Kipchak extras carry weaker {3:3} profiles, Organ Gun's is NULL (reuses primary) + dat accuracy 0/0; burst is Xianbei-only; abstract collapses charge salvo to 1 replacing shot |
| area_damage | siege_splash(2), splash_on_hit(2), trample(3), pass_through(2) | Centurion is a CHARGE, not splash; Logistica/Druzhina both flat-5 on disjoint rosters (no stacking path); Urumi trample gated to charged strike (position/js) vs 25%-chance ungated (abstract); miss-graze is a global position-engine mechanic |
| charge | melee_charge(2), ranged_charge_mods(2), charge_slow(2) | recharge = dat MaxCharge/RechargeRate; `charge_recharge_time` shared with the ranged salvo; abstract adds charge flat (no armor subtract) and ignores range/armor-ignore mods |
| damage_over_time | bleed(2) | one refreshing slot per target (multi-shooter Curare undermodeled) |
| on_kill | attack_per_kill(1), hp_per_kill(2), resources_per_kill(3) | stored attack value = CAP not increment; eco trio position-only; food/wood unset (gold=Mapuche) |
| armor_interaction | ignore_armor(2), armor_strip(1), bonus_damage_reduction(1), damage_reflect(1) | ignore zeroes base armor only; reduction applies to bonus damage only |
| defensive | dodge_shield(2), block_first_melee(1) | shield absorbs ranged hits then recharges; block is once-ever (Iron Pagoda) |
| aura | attack_aura(2), hp_aura(2), ally_death_heal(2) | abstract pre-computes from army size at setup (no decay); position/js live-update |
| form_change | dismount_on_death(10), hp_transform(11), paired_forms(1) | stat blocks `derived:form_tech_chain` since bcdbcbc (the dead config copies were deleted 2026-06-10); dismount in ALL THREE engines since the 2026-06-10 port (was abstract-only); Ratha two-row pattern is the target model |
| tempo | attack_speed_ramp(2), execute(2) | ramp resets out-of-combat in position engine only |
| misc | min_attack_range, miss_damage, pop_space, hp_regen, hp_regen_in_combat, projectile_speed, unit_category (1 each) | `min_range` column ≠ dict key; Ordo regen position-only; projectile_speed unused in abstract (no flight); unit_category never reaches `ref_units` |

The census (verified): 52 properties; 19 derived from dat fields, 33 hardcoded;
stored twice (flat `ref_units` columns for speed + `ref_special_effects` rows for
audit); 21 config keys are orphans matching no roster unit (silent no-ops — the same
mechanism that hid the Dravidians gap). Adding one ability today touches **6 files**
(config → generate_reference schema+writer → combat_unit_loader → both Python engines →
simulate.js), with no test asserting the chain is complete, and parity across the three
engines is maintained by hand (test coverage 13 / 7 / 0 per engine).

**Target: a single `ABILITY_REGISTRY`** (one Python module, the only place an ability
is *declared*):

```python
ABILITIES = {
  "bleed": Ability(
      params={"dps": Param(float, 0.0), "duration": Param(float, 0.0)},
      source="curated",            # vs "dat:<field>" for extracted ones
      engines=("abstract", "position", "js"),
      description="Damage over time applied on hit (Liao Dao, Curare)"),
  ...
}
```

Generated/validated **from** the registry: (a) storage — either the column set or,
better, one `abilities_json` column holding `[{type, params}]` validated against the
registry at generate time (keep the ~8 hottest scalars as real columns if SQL needs
them); (b) the loader mapping in `build_combat_dict_from_ref` (iterate registry, stop
hand-listing keys); (c) `prepare_combat_unit` defaults; (d) a JSON manifest consumed by
`simulate.js` so the frontend knows the expected params; (e) **parity tests**: each
Python engine exposes a `HANDLERS` table keyed by ability name and a unit test asserts
every registry entry with that engine listed has a handler (the JS side asserts against
the manifest). Adding an ability becomes: 1 registry entry + 1 handler per engine —
everything else is generated or fails a test. The orphan-keys problem becomes a
registry-vs-roster assertion instead of a one-off audit.

`ref_special_effects` stays as-is — source-tagged audit is exactly right.

### 3.3 Multi-form units: hand-copied stat blocks that techs never touch — **confirmed accuracy bug**

> **Status: fixed at generation time 2026-06-10.** `unit_analyzer.calculate_form_stats()`
> runs the form's dat unit (1252/1253 dismount, 1976 transform) through the full tech
> chain and `generate_reference.py` overrides the config-supplied `dismount_*`/`transform_*`
> values with the derived block (source-tagged `derived:form_tech_chain` in
> `ref_special_effects`). Verified: Bulgarians Elite Konnik dismount now 17 atk / 5/6
> armor (smith deltas equal to the mounted form's; Bagains and Stirrups correctly do
> not apply — they target militia unit ids / cavalry classes), Wu Jian transform
> unchanged in value but now derivation-backed (the dat's C-Bonus 1076 targets unit
> 1976 explicitly and is picked up). The derivation also corrected two latent issues
> the config carried: `dismount_attack_speed` was stored as reload-seconds (2.4) where
> every engine consumes attacks/sec (now 0.4167), and the base Konnik dismount armor
> was stale vs. the current dat (1/1 vs. 2/2). The stat values in
> `UNIQUE_COMBAT_PROPERTIES` (`config_combat.py` konnik/elite_konnik/jian_swordsman
> entries) became dead inputs at that point and were **deleted in the 2026-06-10
> bundled re-sim window**; only `dismount_unit_id`, `transform_unit_id`, and
> `hp_transform_threshold` remain in config (scratch-regen diff vs the committed
> DB: zero row differences beyond the known Mayan-cost rows).
>
> **Port complete (same window):** dismount-on-death now runs in all THREE
> engines. The position engine (`simulation_real.py`) and `simulate.js` replace
> a dying Konnik in place with its derived dismounted form at end of tick —
> verified by a 12-matchup byte-identity neutrality harness (non-dismount
> outcomes unchanged; Konnik outcomes change) plus
> `tests/test_position_sim_abilities.py::test_konnik_dismounts_on_death_and_fights_on`.
> The edit rotated `sim_version` `f6ab0051d5cd4fff` → `e221c8a3a0437bd8`, so
> every matchup row is stale pending the next full batch re-sim.

Konnik dismount and Jian transform are stored as 9 hand-copied columns each in
`UNIQUE_COMBAT_PROPERTIES`. **Verified consequence:** Bulgarians Elite Konnik's
dismounted form is stored with attack 13 / armor 2/2 — byte-equal to the raw dat base
of unit 1253 — while the mounted form correctly carries final 18 / 5/6. In the real
game the dismounted Konnik benefits from infantry blacksmith + Bagains (~17 attack,
~+5 MA). **The sim's Konnik second life is far weaker than the game's**, because the
form block is data, not a derivation.

**Target:** forms as references. `dismount_unit_id` (1252/1253) already exists and the
dismounted units ARE dat units — run the same `calculate_unit_stats_for_civ()` on the
form's dat id with the same civ (the infantry tech set applies itself correctly), and
store the result as a generated nested block (or a linked `ref_units` row with
`form='dismounted'`). The hand-copied values in config get deleted; the curated part
shrinks to what is genuinely not in the dat (the transform *threshold* for Jian, the
fact that dismount triggers on death). Ratha's two forms already do this right —
they are two real rows, each fully pipelined; that is the pattern to generalize.

⚠ Fixing this changes sim inputs → unit fingerprints change → the affected matchup
groups re-sim automatically via the `rebuild_matchup_baseline` `groups_done` resume
(the proven 8.5-minute playbook; blast radius ≈ Konnik/Jian rosters).

### 3.4 Upgrade lines: hand-curated though fully present in the dat

Line chains (knight→cavalier→paladin) are curated in `config_units.py`
(`upgrades`/`civ_upgrades` lists) and again in `webapp/unit_lines.py` (+ a JS copy).
The dat encodes them completely as type-3 UPGRADE_UNIT commands (verified: tech 209
Cavalier 38→283, tech 265 Paladin 38→569 + 283→569); age ordering comes from
`tech_ages.json`. **Target:** derive `lines.json` in extraction (graph walk over type-3
commands), keep curation only for presentation (line labels, slug names), and add tests
asserting `config_units` chains and `UNIT_LINES` (py *and* js) match the derived graph.

### 3.5 Validation is the missing glue layer

Every incident this quarter was a curated table drifting from its upstream with no
assertion to catch it. The principle to adopt: **every curated table must have an
automated assertion against the thing it summarizes.** Concretely (all cheap):
- config_combat keys ↔ ref-DB roster (the designed-but-unimplemented
  `test_config_combat_keys.py`, with the documented allowlist for roster-conditional keys)
- availability resolver ↔ SiegeEngineers data.json (replaces `_AVAILABILITY_OVERRIDES`)
- `UNIT_LINES` (py) ↔ rankings.js copy ↔ derived lines.json
- ABILITY_REGISTRY ↔ engine HANDLERS tables ↔ JS manifest
- `config_units` upgrade chains ↔ dat type-3 graph

## 4. Smaller findings

- **Team bonuses are extracted but unapplied** except 2 hardcoded entries
  (`CIV_TEAM_BONUS_ATTACK`: Persians, Saracens). `team_bonus_effect_id` is captured per
  civ; the generic application path doesn't exist. Inventory what the dat's team-bonus
  effects contain and either run them through the same effect machinery or document the
  exclusion per entry (many are eco-only and rightly ignored — make that explicit).
- **The attribute skip-list is implicit.** `apply_effect_command` silently ignores
  attributes it doesn't model (garrison, work rate, carry capacity, dispersion…). Make
  it an explicit `SKIPPED_ATTRIBUTES = {id: reason}` dict so silence is a decision.
- **The irreducible curated core is real and fine.** Verified genuinely absent from the
  dat: armor-ignore (Leitis/Wootz), bleed, block-first-melee, kill-stacking, auras
  (Monaspa/Shu), damage reflect, transform thresholds, in-combat-only regen gating.
  These are exactly what `UNIQUE/CIV_COMBAT_PROPERTIES` should shrink to — abilities the
  game implements in engine code, not data. The dat-derived 19 (charge, dodge shield,
  extra/burst projectiles, trample/splash via blast fields, bonus-damage resistance,
  regen) are already being extracted properly — credit where due.

## 5. Target architecture

```
empires2_x2_p1.dat
   │ extraction (+ required_tech_count, per-tech civ binding already captured)
   ▼
units.json · technologies.json · effects/tech_effects.json · civ_tech_trees.json
   │
   ├── RESOLVER (new, pure function) ──► availability.json   ◄── asserted vs SiegeEngineers
   ├── LINE GRAPH (new, type-3 walk) ──► lines.json          ◄── asserted vs config/UNIT_LINES
   ▼
analysis: base stats → effect chain (0/4/5 + explicit skip-list) → forms derived by
re-running the chain on form unit ids → ABILITY_REGISTRY-validated curated layer
   ▼
aoe2_reference.db: core stat columns + abilities_json (registry-validated)
                   + audit tables (unchanged)
   ▼
loaders GENERATED from the registry → engines with per-ability HANDLERS tables
   ▼
validation suite asserting every junction above
```

Human-edit surface after migration: the ability registry (semantics of genuinely
hardcoded abilities), presentation labels, and `config_combat` *values* — everything
else regenerates from the dat.

## 6. Claims checked and refuted (do not re-raise)

| Claim | Verdict | Evidence |
|---|---|---|
| "Civ cost discounts are skipped (type-1 commands unhandled) — costs never discounted" | **REFUTED** | `ref_units` finals: Berbers paladin 48/60 vs Franks 60/75 (−20% exact); Goths champion −30%; Berbers hussar −20%. The type-1 tech the reviewer found was not the operative mechanism; discounts arrive via multiply commands on cost attributes. The Mayan surgical patch fixes one special case, not systemic breakage. |
| "Availability is irreducibly non-derivable for the 17 allowlist lines" | **CONFIRMED** *(the 2026-06-10 "half-refutation" was itself wrong — resolver built and run, §3.1 status)* | Tech 79 "Disable Regionals" locks all regional lines for every civ in normal games (counter tech 78 is `full_tech_mode=-1`, FTT-only); the per-civ grants live in the game's `CivTechTrees/<CIV>.json`, not in `empires2_x2_p1.dat`. No dat-only resolver can derive them — extraction of CivTechTrees JSON is the path. |
| "Konnik dismount stats are just stored config" | **Confirmed, and it's a bug** *(fixed 2026-06-10 — see §3.3 status)* | Stored dismount attack 13 / armor 2/2 == dat base of unit 1253; mounted final 18 / 5/6; in-game blacksmith applies to both forms (§3.3). |

## 7. Migration plan (re-sim-aware)

| Phase | Work | Regen/re-sim impact |
|---|---|---|
| **A — additive, zero risk** | `ABILITY_REGISTRY` module + parity/orphan-key tests (**done 2026-06-10**, §3.2 status); lines/availability tests in *report mode*; extract `required_tech_count` (**done**, cb979b1); build resolver + line graph alongside current code and **diff their output against current rosters** (resolver **done 2026-06-10**: 282 mismatches, NOT the expected exact match — §3.1 status) | none |
| **B — swap sources, stat-neutral** | ~~availability from resolver~~ **blocked 2026-06-10** (282-mismatch report, §3.1: the dat cannot express regional availability; prerequisite is a CivTechTrees JSON extractor, then re-run the gate); ~~generated loaders~~ **done 2026-06-10** (§3.2 status: registry generates schema/writer/audit/loader/defaults; columns kept, `abilities_json` not adopted; zero-diff identity gates, no re-sim); delete `_AVAILABILITY_OVERRIDES`/`CIV_MISSING_UNITS` as data (keep as assertions) — still open | ref regen with scratch-diff neutrality gate (the proven procedure); **no re-sim** if neutral |
| **C — accuracy fixes (stat-changing)** | derive multi-form stats through the tech chain (Konnik/Jian); apply any missing team bonuses | fingerprint-driven scoped re-sim via `rebuild_matchup_baseline` resume (~minutes, not hours); golden regen; re-derive |

## 8. What NOT to do

- Don't normalize the serving layer into a deep relational schema — the flat combat
  dict is the hot path and the right shape; this review changes how it's *produced*.
- Don't move final stats out of the DB into request-time derivation — provenance-cached
  finals are the correct trade.
- Don't drop `ref_special_effects` — source-tagged audit rows are the model to extend.
- Don't byte-touch `simulation_real.py`/`config_combat.py` outside a bundled re-sim
  window (sim_version hash).

## Update triggers

| If this changes | Update |
|---|---|
| CivTechTrees JSON extractor lands (re-run the resolver gate) | §3.1 status, §5 diagram, §6 row 2, test pin in `tests/test_availability_resolver.py` |
| New dat build (regenerate extraction) | re-run `python -m analysis.availability_resolver`; re-probe `DEFAULT_ENABLED_UNIT_IDS`; update the 163-row pin (Imperial-only universe) |
| Ability registry generation changes (new generated artifact, or abilities_json adopted after all) | §3.2 status, §7 phase B, runbooks §3 |
| Multi-form derivation lands | §3.3 (close the bug), improvements.md ledger |
| New ability families appear in DE dats | §4 irreducible-core list |
