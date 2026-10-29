# V3 unit model: audit, repairs and remaining plan

Updated 2026-10-29 with the owner-approved combat scope and selected patch 188329 stats.

The reference-to-runtime audit passes for all **1,030 civilization/unit entries,
1,031 weapon-mode profiles, 56 civilizations and one auxiliary scenario profile**.
This is a consistency result, not certification that every value matches the game.
The original patch 185872 DAT, extracted JSON and resolved civilization tech trees
are unavailable in this cloud checkout. The owner confirmed those inputs are not
available right now. Raw extraction and upgrade eligibility therefore remain open.

The complete roster review table is [2026-10-28-v3-unit-model.csv](2026-10-28-v3-unit-model.csv).
Every row includes stats, researched technology IDs, ability families, runtime
effect parameters, consistency errors, source caveats and outstanding work.

## Plan and acceptance gates

1. **Pin the source — partially complete.** All stored profiles name the same DAT
   SHA256, `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`,
   documented as build 185872. When the DAT/extraction/trees are available,
   regenerate into a scratch database and compare every unit, upgrade decision,
   armor/attack class, projectile and alternate form. Matching stored hashes alone
   does not prove that the extractor applied the game rules correctly.
2. **Validate data transfer — complete for the available artifacts.** Check every
   profile's identity, source build, schema/hash, HP, attack/armor maps, range,
   speed, reload, accuracy, projectile speed, LOS, population and cost against
   the reference and final upgrade-chain step. Require exactly one default mode
   per unit. Class/form exceptions must be explicit, not silently ignored.
3. **Audit ability definitions — implemented with open source questions.** Map
   every active registry parameter to a V3 consumer, compare reference-backed
   effects with runtime JSON, and inventory behavior missing beyond that registry.
   The audit covers 33 active registry ability families. Its consumer inventory
   does not by itself prove correct behavior. Six profiles have explicit
   follow-ups, detailed below and in the CSV.
4. **Verify unit behavior — focused checks pass.** Exercise current database
   profiles with controlled targets/positions and independently specified expected
   values. Do not calibrate damage, HP or timings to a desired matchup winner.
   Repeat the audit and unit tests in CI. Resolve the source questions before
   treating this stage as fully signed off.
5. **Then review interactions.** Movement, targeting, projectile interception,
   mixed armies, pending death replacements, draws, scenario parity and live
   battle comparisons follow this unit-level stage. Ranking runs remain later.

## How the data reaches the web simulation

`UnitAnalyzer` starts from extracted game units and selects the configured
Imperial tier and available technologies for each civilization. The generator
records fully researched stats in `ref_units`, selected upgrades in
`ref_techs_applied`, and intermediate changes in `ref_stat_chain`. Conditional
abilities are separate from the full-health base attack/armor columns.

`export_unit_mechanics.py` combines those upgraded values with DAT geometry,
animation timing, weapon/projectile data and concrete alternate bodies. It uses
the exact chain speed instead of the rounded display speed. Attack delay comes
from the attack graphic and its hit frame, not the reference table's old delay
column. Spanish gunpowder reload has a documented DAT tech-tree multiplier
outside the reference stat chain. Concrete War Chariot forms also have explicit
speed/accuracy differences. Nine HP entries involve rounding fractional chain
values; their exact in-game rounding needs raw-source verification.

`generate_v3_mechanics.py` stores canonical, hashed JSON in `ref_unit_mechanics`.
The website validates and serves that JSON; its worker and the Node runner both
pass it into V3. The old ranking database is a separate artifact.

## Repairs in this stage

| Mechanic | Change |
|---|---|
| Shrivamsha shield | Export seven charges and full-pool recharge time; consume one charge per projectile, recharge fractionally, require a whole charge to block, suppress on-hit effects on blocked hits. |
| Iron Pagoda defense | Owner scope: block the ordinary direct melee component, retain the elite 30-second recharge and 50% friendly-fire reduction. Charge damage lands and consumes the attacker's charge; trample and explosions bypass the block. |
| Bonus resistance | Export Sicilian/Bengali resistance and apply it to matching bonus-class damage, preserving ordinary attack damage. |
| Khitan reflection | Apply direct melee/trample reflection without recursive reflection loops. |
| Monaspa | Count seven other own Knights/Monaspas per attack tier, within 15 tiles, maximum four tiers. Unrelated allies do not qualify. |
| Guecha | Require a nearby allied Guecha death, use six tiles, refresh rather than stack the three-second heal, and expire unused healing at full health. |
| Tiger Cavalry | Each of the first four kills increases maximum HP and heals by ten, as well as increasing attack. |
| Armor calculations | Preserve native negative armor; apply kill/group attack bonuses before armor and the minimum-one rule. Restrict Leitis, Composite Bowman and Rocket Cart armor bypass to their documented target categories. |
| Liao Dao/bleed | Exclude mechanical siege, ships and buildings from Liao Dao bleeding while retaining organic targets. Apply every scheduled damage-over-time tick, avoiding one lost tick per stack. |
| Resource effects | Export military-kill income, including posthumous projectile kills, and record Tupi death refunds at 15% of per-physical-unit cost. Earnings are recorded once in immutable unit state. This does not change ranking scores or add a general economy model. |

## Owner-approved corrections, 2026-10-29

- **Ordo:** melee cavalry only; current stationary attack/reload ticks against a
  live reachable enemy receive regeneration. No five/ten-second grace period.
  Healing uses 150% of current maximum HP per minute, preserving fractions.
  Heavy Cavalry Archer and Mounted Trebuchet no longer receive it; Hussar's
  reference rate is 112.5 HP/min rather than rounded 113.
- **Centurion:** non-stacking, same-owner militia-line aura. Elite radius 12,
  movement multiplier 1.15, attack-rate multiplier 1.2 (reload divided by 1.2).
  Entering/leaving the aura preserves elapsed reload progress. Source: official
  [83607](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-83607/)
  radius/speed and [95810](https://www.ageofempires.com/news/preview-age-of-empires-ii-definitive-edition-update-95810/)
  attack-rate reduction to 20%, corroborated by the current Centurion wiki.
- **Gothikon:** owner-specified independent slots, each returning 30 seconds
  after its axe is released. Both can recharge concurrently. Retain the current
  1.6-second fully upgraded weapon cycle, close to the owner's approximate two
  seconds; exact live cadence remains unverified. This is a scoped mechanic
  choice, not a claim that DAT's shared recharge scalar proves independent slots.
- **Fighting gold:** generic per-animation-second income, separate from kill
  rewards. Keshik uses task work rate 0.01 × resource 50 = 0.5 gold per animation
  second (about 0.368 gold/sec over its 1.4s animation / 1.9s cycle). All five
  civilizations' Elite Varangian Guards use stored task151 work rate
  0.015908999368548393 × resource 50; Varangians additionally apply stored
  tech1488's 1.333299994468689 multiplier. The resulting work rates are about
  0.79545 and 1.06057 gold per animation second, respectively. Reload-only gaps,
  movement, dead targets and buildings earn nothing. Income remains unit-state
  bookkeeping and does not change ranking cost/scoring policy.
  Direct task/capture analyses: [Keshik](https://www.reddit.com/r/aoe2/comments/gq309z/how_does_keshik_gold_generation_ability_work_an/)
  and [Varangian Guard](https://www.reddit.com/r/aoe2/comments/1wpq9yi/reasoning_for_the_weird_numbers_behind_the/).
  These support the task model; exact live resource timing is still uncalibrated.
- **Konnik:** pending dismounted replacements keep their victory team in the
  battle. The existing spawn delay and full foot-form profile are retained.

The earlier 71-profile effect refresh was followed by this stage's ability
refresh (64 profiles) and three Elephant Archer stat updates. Some profiles
appear in both refreshes; these are operation counts, not distinct-unit totals.
The Ordo correction also updates three reference scalar rows. Raw attack,
armor, geometry, animation and projectile extraction is otherwise preserved.

## Selected patch 188329 stats

Source: official [October 27 patch notes](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-188329/).
The owner requested these balance changes only; the DAT source hash remains
185872. A separate `balance_overrides` field records 188329 provenance on the
changed runtime profiles. This is not a full 188329 data rebuild.

| Unit | Base change | Current fully upgraded result |
|---|---|---|
| Elephant Archer / Elite | HP 230→220 / 280→270; food 60→70, gold stays 80 | Elite: Bengalis 290 HP/70F, Dravidians 270 HP/70F, Gurjaras 290 HP/52F |
| Bolas Rider | Non-elite speed 1.5→1.45 | Current roster is Elite: stays 1.5 |

Bloodlines and Kshatriyas are preserved in every upgrade-chain step. Gurjaras'
raw discounted cost is 52.5 food; the existing generator's integer rounding
stores 52. Both reference databases, their runtime profiles/hashes, and the
flat website stats are updated transactionally. Ranking databases are unchanged.
Future base-stat generation applies the same patch before civilization upgrades;
non-elite Bolas is covered there without adding a unit to the Imperial roster.

## Remaining validation and deliberate scope exclusions

Six profiles retain follow-ups: Keshik and five civilizations' Varangian Guards
need live gold timing validation; the Varangian civilization's Guard also needs
exact throw-cadence validation. Missing raw DAT/extraction/tech-tree verification
continues to apply to the full roster.

The owner explicitly excluded Barrage, Hussite Wagon projectile shielding,
Fire Archer building/ship mode, and Warrior Priest healing from this stage.
Focus Fire and Fire Archer's anti-unit mode remain the selected use cases.
These exclusions are source notes in the CSV, not unresolved implementation bugs.
The Barrage profile is retained for compatibility but is outside this audit's
behavioral acceptance scope. No new UI, roster or simulation mode was added.

Correction, 2026-10-28: **Jarl has no armor-stripping ability.** The earlier gap
entry incorrectly carried forward an old tooltip claim. The owner corrected it,
and the later comparison report already found no support for adding stripping.
The runtime profile has no armor-strip effect; the item is closed and removed
from the generated follow-up list. The October 29 scope decisions supersede the earlier fourteen-profile follow-up count. Keshik's unit
gap concerns fighting gold; terrain/elevation belongs to the general interaction
review, rather than being a Keshik-specific missing ability.

This list is a review of the available registry, unit documents and patch notes;
new raw game tasks/effects may reveal additional omissions when the source inputs
become available. A blank follow-up cell means no additional issue was identified
in this audit, not independently verified game fidelity.

## Repeatable checks

```bash
python -m aoe2x.dbgen.audit_v3_units data/golden/aoe2_reference_simulation.db \
  --output /tmp/v3-unit-audit.json --csv /tmp/v3-unit-audit.csv
python -m aoe2x.dbgen.refresh_v3_effects data/golden/aoe2_reference_simulation.db
python -m pytest -q tests/test_v3_unit_model.py
node aoe2x/js_simulation/tests/unit-model.test.mjs
```

The refresh command above is a dry run; add `--write` to apply a reviewed effect
refresh. Current results including the selected patch-stat tests: 38 focused Python checks pass, 12 tests requiring
unavailable source inputs skip; all 11 selected V3 test files pass. The new Node
unit-model file contains 20 passing behavioral/contract checks. API checks verify
that the web endpoint serves the same shield, block and resistance profiles.

The older world-tick file retains the same 10 failures observed before this
change (22 pass). The superseded legacy ability-registry suite also retains its
five baseline failures and is already excluded from the active CI gate. Neither
is presented as a clean overall simulator test result. No ranking rebuild,
publication or deployment was performed.

The stat overlay is repeatable with
`python -m aoe2x.dbgen.patch188329_stats data/golden`; a second run changes no rows.
Its dedicated tests verify both tiers, unchanged Elite Bolas, all three civ
upgrade results, API delivery, idempotence and rollback across all three databases.

## Combat follow-up, October 29

The owner approved three combat changes after the unit audit:

- Battle completion waits for pending damage that can affect a survivor,
  including already-fired projectiles, delayed explosions, hostile ground
  hazards and poison/bleed. Pending dismounts remain part of survival. Harmless
  allied effects and target-only shots at dead enemies do not extend a fight.
  Mutual elimination returns `outcome: "draw"`; reaching the tick ceiling returns
  `outcome: "timeout"`. Both have a null winner. These outcomes pass through the
  shared fight function, Node jobs and comparison adapters; unresolved timeouts
  are not scored as draws or assigned an elimination time.
- Melee attacks ready on the same tick use a seeded Fisher–Yates shuffle after
  canonical sorting. Earlier damage ticks retain precedence. The scenario's
  `openingSeed` now also determines combat arbitration, using a separate stream
  from projectile accuracy. The same seed and inputs reproduce the same fight;
  lower reference IDs no longer automatically win a lethal melee tie.
- Charged projectiles store their release position, fixed aim and physical
  speed. Each tick sweeps the flight segment against the target's collision
  body, so approaching targets can be struck early and targets that leave the
  path are missed. The shot expires at its aim point and survives its shooter's
  death. Charge cost, independent recharge, volley counts, armor bypass and
  on-impact Bolas slow retain their existing rules.

The charged-projectile correction fixes the guaranteed-hit behavior; it does
not establish exact game fidelity for spread, projectile width, interception
or Ballistics on every charge weapon. Existing charge profiles omit that
metadata. They currently use target-only point flight toward the release-time
position and retain the existing accuracy-roll handling. Fire Lancer spread
remains an acknowledged approximation, without an invented hit-rate adjustment.

Browser scenario parity is deferred by the owner. Tupi poison on stray hits,
specialized Onager AI, and acceleration/turning simplifications remain as accepted.
No ranking rebuild or deployment is part of this change.

`combat-resolution.test.mjs` adds 20 synthetic behavioral checks using the
committed runtime profiles, including real Node jobs ending in a draw and a
timeout, plus a 256-seed lethal-melee sample. It is included in CI. All 11
previously selected mechanics files and five additional integration/CI files
pass. The legacy world-tick file now has 23 passing checks and nine pre-existing
failures: its obsolete lower-ID-wins test was replaced by a seeded cancellation
check, and its timeout/draw contracts were updated. This is not a claim that
the entire historical simulator suite is clean or that live-game validation
has been completed.
