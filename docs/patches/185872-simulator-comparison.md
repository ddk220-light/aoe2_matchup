# Patch 185872: first simulator comparison

September 23, 2026. **Local partial integration, not ranking-ready.** No website,
rankings, production databases, push, deployment or recordings were changed.

## Outcome

Five opponents each for Elite Hearth Troop, Elite Jarl and Elite Jomsviking:
**15 completed comparisons; 12 matching winners; 3 winner flips.** One seed (0)
per matchup against an existing run_001 recording. Matching winners do not prove
matching mechanics or HP. No combat values were tuned to these outcomes.

All 15 independently calculated costs, main counts and P4 counts match the plans.
Initial frame snapshots match counts, HP and first-N golden coordinate sets.
This uses the existing JavaScript V3 engine, not captured trajectories.

## Setup and sources

- Data-stage feature commit `553f8eed`; recorder policy commit
  `2cced342954cde888dc91f4bf13c13b89f2713f8`, `docs/video-production/BALANCE_POLICY.md`.
  The unrelated recorder branch was not merged.
- Installed DAT build 185872 SHA256:
  `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`.
- Local candidate `data/local/generated/patch-185872/aoe2_reference.db` now has
  1,031 runtime profiles for 1,030 reference entries, plus 1 auxiliary profile.
  Profile generation does not certify all abilities.
- Read-only captures under `E:/AoE2 Renders/{hearth-troop-saxons,jarl-varangians,jomsviking-danes}`:
  76 matchups each.
- Cost per physical unit after full applicable discounts/batch division:
  `food + 0.9*wood + 1.1*gold`. Saxon foot soldiers use the maximum 20% conditional
  discount. Bounty income is not deducted from purchase cost.
- Cheaper army: 27; dearer army: `max(1,floor(27*sqrt(cheap/dear)+0.5))`.
- Mixed only: `P4=floor(clamp(5+(rangedCount*weightedCost-1000)/1800,5,10)+0.5)`.
  First-N authored P4 slots, tenth at (7.5,5.5). Historic default 9 preserved.
- Existing golden formations, patrols, diplomacy and P4 defeat gate retained.
  P4 is Spanish master 448: 95 HP, 11 attack, 3/6 armor. Jarl is ranged with melee damage.

## Results

All featured/opponent units are elite variants except Houfnice. Counts are
featured/opponent/P4. Paired values are **game / simulation**. HP and survivors
belong to each run's winning main army, excluding P4. When the winner flips,
those values describe different units. Times are approximate **game seconds**.

| Featured | Opponent | Counts | Winner: game / sim | Winner HP | Survivors | Game seconds |
|---|---|---|---|---:|---:|---:|
| Hearth Troop | Composite Bowman |26/27/6|Composite / Composite|1111 /1209|26 /27|33.00 /29.95|
| Hearth Troop | Jaguar Warrior |27/26/0|Jaguar / Jaguar|1360 /1244|22 /20|25.99 /24.23|
| Hearth Troop | Houfnice |27/12/7|Hearth / Hearth|609.7 /1074|11 /16|65.01 /57.85|
| Hearth Troop | Cataphract |27/21/0|Cataphract / Cataphract|2523 /2283|20 /20|27.00 /26.00|
| Hearth Troop | Mangudai |27/23/6|**Hearth / Mangudai**|315 /891|5 /14|68.00 /49.10|
| Jarl | Composite Bowman |21/27/0|**Composite / Jarl**|424 /568|11 /8|42.01 /41.35|
| Jarl | Jaguar Warrior |22/27/6|Jarl / Jarl|1668 /1662|18 /19|29.00 /24.85|
| Jarl | Houfnice |27/15/0|Jarl / Jarl|1015.4 /1650|17 /17|33.00 /31.62|
| Jarl | Cataphract |27/25/6|Jarl / Jarl|1882 /2022|21 /22|41.00 /41.03|
| Jarl | Mangudai |26/27/0|**Mangudai / Jarl**|1050 /469|16 /7|41.00 /45.05|
| Jomsviking | Composite Bowman |27/27/6|Composite / Composite|1079 /1006|25 /23|31.99 /28.68|
| Jomsviking | Jaguar Warrior |27/25/0|Jaguar / Jaguar|1233 /1298|22 /22|27.00 /24.05|
| Jomsviking | Houfnice |27/11/7|Jomsviking / Jomsviking|954.4 /1443|16 /21|36.99 /44.02|
| Jomsviking | Cataphract |27/20/0|Cataphract / Cataphract|2436 /2458|20 /19|25.01 /21.78|
| Jomsviking | Mangudai |27/22/6|Mangudai / Mangudai|436 /96|8 /3|39.00 /43.90|

### Clock and endpoint

Recorder `apps/video/auto/grpc_capture.py` divides offline game seconds by game
speed and rounds to two decimals; `aoe2x/lab/live.py` copies that video-time value
to `eliminationTimeSeconds`. Archive `recording.clock` declares `video_seconds`
at 1.7 speed. Comparisons multiply by that speed before subtracting simulator
ticks/60. Integer-game-second source sampling limits precision; no trim offset
is added. The original report's unnormalized duration deltas are superseded.

Capture endpoint is defeat of P2/P3, excluding P4. Simulator golden victory
teams include the ranged side's P4. For these selected fights, the diplomacy
gate prevents melee attacks on the ranged army until P4 defeat; all mixed runs
finish with zero P4 survivors. Do not assume equivalent endpoints for other
scenario rules without checking.

## Material implementation changes

1. Setup calculator, dynamic P4 support and opt-in recording policy in the
   existing headless entry point. Older jobs keep their existing policy.
2. Candidate mechanics generated through the existing exporter; concrete
   alternate forms use candidate extraction when present, not old default data.
3. Hearth javelin: raw range modifier 6 plus Fletching/Bodkin/Bracer gives 9;
   pierce 7 plus those upgrades and available Chemistry gives 11. Bonus 4 is versus
   archers. Projectile-only upgrades are checked separately from the carrier's
   applied-tech list. Attribute 61 semantics are sourced from the
   [parser maintainer](https://ksneijders.github.io/AoE2ScenarioParser/api/AoE2ScenarioParser/datasets/trigger_lists/object_attribute.html).
4. Jomsviking torch target filtering uses building type 80 or ship trait 2 in
   combat and TTK. Eligible torch damage still fails explicitly because its
   smart-mode8 inheritance is unresolved; ordinary land attacks work normally.
5. Per-owner survivor/HP results and local preparation/comparison tools retain
   source inputs, profile hashes, frame paths, differences and limitations.

The first torch filter incorrectly treated damage class 20 as ships; it is
siege. The Houfnice spike exposed this. Object type/traits replaced that proxy,
with regression tests. Only the failed Jomsviking–Houfnice job was rerun;
14 completed runs were retained. Independent review verified old/new inputs
differ only by the added type/trait fields.

## Mechanics status after the technology follow-up

- **Shield Wall:** implemented using shipped `Effects.xs` radius7 and the owner's
  supplied AoE2 wiki rule: +1/+1 per15 OTHER living own infantry, capped at +3/+3.
  Recomputed with the existing nearby-aura update; no bonus below16 total units.
- **Hamask:** implemented from shipped `Effects.xs` function30/task160:
  +1 primary attack per complete10% of own maximum HP lost, before armor and
  minimum-one damage. Confirmed against captured Jaguar/Teutonic/War Elephant
  per-hit observations, including fractional HP. It is not target-HP execute.
- **Gothikon:** researched capacity2, range3, carrier damage inheritance, one axe
  per use, and one charge recovered per30seconds are implemented. The owner-supplied
  wiki rule resolves separate consumption/readiness. Reuses the normal weapon
  reload and special animation cycle (Varangian elite Guard inter-throw model:
  1.6seconds); that interval is not a live measurement. No Guard recordings were
  found in the named E-drive collections.
- **Jarl armor reduction:** shipped civ tip claims it, but repeated recorded hits
  do not support ordinary stacking Obuch stripping. Current
  [official description](https://www.ageofempires.com/news/varangians-civilization-deep-dive/)
  does not specify it. No speculative rule was added.
- **Jomsviking torch damage:** Smart Mode8 inherits the carrier's damage, including
  live HP-dependent modifiers; implemented. Building/ship-only restriction is
  retained. These land tests do not validate naval combat or torch flight.
- **Vendel Legacy:** researched radius/damage attributes now reach runtime;
  fixed5 radial secondary damage is implemented. The same existing shared path
  now honors exported flat-trample effects for other units, including Cataphracts.
  Zero-width unupgraded units remain inactive. No Varangian Cavalier recording
  was available for live validation.
- Regional Mounted Crossbowman/Guard profiles exist, but their behavior and all
  relevant civ effects are not covered here. Guard fighting-gold economics are
  not implemented in this stage.

Do not attribute the three flips solely to missing abilities from this sample.
In particular, do not add Jarl stripping merely to change its winners.

## Why the full archive was not run

Read-only broader input checks also found Magyar Huszar candidate 35F/45G versus
recorded 80F/0G, and Plumed Archer 43W/43G versus recorded 39W/39G. Three opponent
identities/modes do not resolve: Barrage War Chariot, Spanish Missionary and
Tatar Flaming Camel. The preparer reports these rather than substituting units.
Source reconciliation and unfinished abilities come before claiming complete
integration. No retakes, cost overrides or full 228-fight run were launched.

## Verification and artifacts

### Decisive follow-up (September23)

Owner requested decisive recordings instead of close winner flips. Default
selection now requires at least60% of the winning army's starting HP remaining;
the CLI can explicitly select50–60% secondary cases if coverage requires it.
No lower-threshold case was needed. Exact recorded job IDs are selected before
simulation; no seed or opponent was chosen after seeing a simulated winner.

Five diverse Jarl and five Jomsviking cases were run with unchanged seed0,
four workers, and the regenerated local candidate profiles. All10 setups/costs
matched recording metadata, all10 runs completed, and all10 winners matched.
This does not establish HP or timing calibration:

| Featured unit | Opponent | Recorded winner | Game winner HP% | Sim winner HP% |
|---|---|---|---:|---:|
| Jarl | Jaguar Warrior | Jarl |72.2|71.9|
| Jarl | Genitour | Jarl |67.3|78.6|
| Jarl | Cataphract | Jarl |66.4|56.2|
| Jarl | Genoese Crossbowman | Genoese |66.0|55.9|
| Jarl | Ballista Elephant | Ballista Elephant |82.9|63.9|
| Jomsviking | Jaguar Warrior | Jaguar Warrior |65.8|57.6|
| Jomsviking | Genitour | Jomsviking |75.4|76.1|
| Jomsviking | Ballista Elephant | Ballista Elephant |84.0|40.0|
| Jomsviking | War Elephant | War Elephant |75.5|61.5|
| Jomsviking | Teutonic Knight | Teutonic Knight |86.8|81.8|

All opponent variants are the elite/civilization forms recorded in the input
manifest. Individual survivors and normalized game durations are preserved in
`calibration/lab/patch185872/decisive-results.json`; exact frames paths, jobs,
starting HP and source hashes are in `decisive-jobs.json`. The largest HP delta
is44percentage points; it is not treated as a calibrated pass despite the
correct winner. No outcome correction was applied.

Focused verification passed: 31 JavaScript checks and 12 Python checks. The
independent implementation review found an existing summary path displaying
fixed trample as 0%; it now displays the fixed damage amount, with a regression
test verified failing before the correction and passing afterward. This review
accepts only the completed local subset, not full integration or publication.

Primary sources resolving the new implementation:

- Installed `resources/_common/xs/Effects.xs`, functions30/31.
- [Task160 semantics](https://ugc.aoe2.rocks/general/tasks/tasks/#160-hp-damage-modifier).
- [Official update185872: Smart Mode8](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/).
- [Official flat-blast and aura definitions](https://support.ageofempires.com/hc/en-us/articles/15607286588948-Return-of-Rome-Mod-Updates).

The owner requested online research instead of launching controlled game probes.
No game was launched, and E-drive recordings were not changed. The subsequent
staging continuation below supersedes the earlier Shield Wall/Gothikon blockers
and authorizes simulator website publication.

### Staging continuation

Owner requested the playable updated simulator in staging, with cost-efficient
default armies and manual counts retained. The same-schema serving reference
`data/golden/aoe2_reference_simulation.db` contains1030 units/1031 mechanics
profiles. Original ranking reference/derived artifacts stay unchanged: replacing
the old reference would renumber existing IDs and remove12 scored roster entries.
Simulator selectors/config/combat endpoints use the new reference; ranking
stat-chain and advisor readers retain their original data.

Default purchase weighting is F +0.9W +1.1G after maximum applicable discounts
and physical-unit batch division. Cheaper side gets27; dearer side gets rounded
`27*sqrt(cheap/dear)`. The mixed-fight buffer defaults on and uses the same
rounded5..10 fielded-ranged-cost rule as recordings. Explicit counts remain
unchanged; previous resource-budget mode remains available.

Five actual public API configurations completed through the shared engine:
Hearth Troop/Cataphract, Jarl/Paladin, Jomsviking/Teutonic Knight, Varangian
Guard/Hearth Troop, and Frankish Heavy Mounted Crossbowman/Chinese Arbalester.
Local artifacts: `public-smoke-jobs.json` and `public-smoke-results.json` beside
the comparison artifacts above. All five completed without engine errors.

Shield Wall follow-up: five decisive existing Hearth Troop recordings, seed0,
four workers. All setup counts/costs matched and all five winners matched:

| Opponent | Game winner HP% | Sim winner HP% |
|---|---:|---:|
| Composite Bowman |82.3|92.0|
| Jaguar Warrior |69.7|62.6|
| Genitour (Hearth wins) |78.4|75.0|
| Cataphract |80.1|78.6|
| Ballista Elephant |82.4|59.8|

Exact paths and source recordings are in `shield-wall-jobs.json`; outcomes in
`shield-wall-results.json`. No outcome tuning or recording writes. Together with
the previous ten decisive Jarl/Jomsviking cases this is15 matching winners,
not a claim of full survivor-HP calibration; the existing large siege deltas remain.

The ten existing approved new-unit idle images and hover animations are reused.
Missing canvas sheets were compiled into the normal horizontal WebP format
(390frames total, unchanged50ms source timing) and uploaded only to the staging
bucket. Only their manifests/native-size metadata and the reusable builder enter
Git; generated sheet media stays in ignored local output and the asset bucket.
Focused checks:31 engine JavaScript tests,17 web/API Python tests,14 exporter and
recorded-setup Python tests, and the new browser-selection default/manual-count
test passed. Independent code review found no critical or important issues.
No production deployment or
rankings run is authorized by this continuation.

### Initial spike verification (historical)

- 21 focused JavaScript and 8 Python checks passed.
- Four legacy `fire-lancer-charge.test.mjs` checks fail with expected 3 / actual 1
  damage. Independent inspection confirmed the issue exists at `553f8eed`: fixture
  lacks `ignores_armor` while existing code requires true. No unrelated fix;
  this is not a claim that the whole repository test suite passes.
- Independent review accepted a **local partial candidate**, not complete
  integration or publication readiness.
- Authoritative local result:
  `aoe2x/js_simulation/calibration/lab/patch185872/comparison-final.json`.
  Initial results, single retry, inputs and bounded frame probes remain beside
  it. Generated DBs, job payloads and results stay ignored/local-only.

Reproduce after reviewing/completing mechanics, using fresh output filenames:

```powershell
D:/miniconda3/python.exe -m aoe2x.dbgen.generate_v3_mechanics --reference-db data/local/generated/patch-185872/aoe2_reference.db --dat D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat
D:/miniconda3/python.exe aoe2x/js_simulation/tools/prepare_recorded_comparison.py --output aoe2x/js_simulation/calibration/lab/patch185872/next-jobs.json
node aoe2x/js_simulation/node/compare-recorded.mjs --input aoe2x/js_simulation/calibration/lab/patch185872/next-jobs.json --output aoe2x/js_simulation/calibration/lab/patch185872/next-results.json --workers 4
```
