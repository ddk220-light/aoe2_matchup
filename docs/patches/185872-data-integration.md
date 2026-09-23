# Build 185872: local data integration

Prepared September 23, 2026. **Data candidate only: no simulations, ranking rebuild, website changes or publication.**

## Inputs and outputs

The installed `empires2_x2_p1.dat` has SHA256
`4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`.
It matches the file used for the earlier civilization-page work. This run uses
the normal extraction/analyzer/database pipeline, including the installed
`CivTechTrees` for regional grants and upgrade restrictions.

Baseline: the checked-in reference at `e9b07348`, 972 Imperial entries for 53
civilizations. The candidate has **1,030 entries for 56 civilizations**:
**73 added, 15 removed, 200 changed**. These counts compare database entries,
not unique game units or simulated matchups.

All generated files are local-only under `data/local/generated/patch-185872/`:

- `aoe2_reference.db`: fully upgraded stats, technology/stat chains, projectile
  data and 112 additional source-evidence records in the existing special-effects table.
- `aoe2_units.db`: normal flat stats schema, 1,030 available-unit entries.
- `extracted/`: game-unit, technology, effect and civilization JSON, plus source provenance.
- `reports/reference-diff.md`: every changed field, added entry and removed entry.
- `reports/reference-diff.json`: the complete comparison and both technology audits.
- `reports/mechanics-evidence.json`: 34 sourced technology/team-effect definitions,
  new-unit tasks, charge/projectile fields, raw research costs/times and unresolved semantics.
- `manifest.json`: source/output hashes, integrity result and explicit stage flags.

The checked-in golden databases, existing V3 mechanics, rankings and production
data have **not** been overwritten. The candidate is not ready for deployment
or ranking simulations until the new runtime behavior is implemented and validated.

## New roster

- Danes, Saxons and Varangians each contribute 18 fully upgraded Imperial entries.
- Mounted Crossbowman line: 15 civilizations. Heavy tier: Britons, Celts, Danes,
  Franks, Poles, Saxons, Sicilians, Spanish, Teutons and Varangians. Bohemians,
  Burgundians, Italians, Portuguese and Vikings retain the base tier with their
  available Imperial technologies.
- Elite Varangian Guard: Byzantines, Danes, Saxons, Varangians and Vikings.
- Elite Hearth Troop (Saxons), Elite Jarl (Varangians), Elite Jomsviking (Danes).
- Regional Longships and Catapult Galleons are registered through the existing
  naval configs. Vikings retain their existing `elite_longboat_vikings` identity
  while the display name becomes Elite Longship.
- Cavalry Archer replacements are removed for the 11 previously represented
  European owners. Bohemians gain Mounted Crossbowmen without an old CA row to remove.
- Vikings lose Cannon Galleon and gain Catapult Galleon. Three pre-existing
  phantom Demo Raft entries (Koreans, Portuguese, Vikings) are removed because
  the installed trees explicitly exclude them. This is a data correction,
  not a claim that those three losses were introduced by this patch.

### Fully upgraded new unique units

These are initial, full-health stats. Conditional effects are recorded separately.
Costs are per-unit resource totals; no variable Saxon building discount is selected.

| Civilization / unit | HP | Main attack | Melee / pierce armor | Range | Cost |
|---|---:|---:|---:|---:|---|
| Saxons / Elite Hearth Troop | 85 | 14 melee | 4 / 8 | melee | 80 wood, 35 gold |
| Varangians / Elite Jarl | 105 | 14 melee | 5 / 5 | 5 | 75 food, 55 gold |
| Danes / Elite Jomsviking | 75 | 13 melee | 5 / 6 | melee | 65 food, 15 gold |

The separate javelin/torch attacks and armor reduction are not summed into the
ordinary attack column. Guard HP varies from 80 to Viking 96; Varangian Guards'
reload is 1.6 seconds instead of 2.0, while Danish Guards receive the speed bonus.

## Important changes versus the checked-in reference

The complete field-by-field report is authoritative for this comparison. The
following summarizes the main gameplay-facing changes without presenting
pre-existing pipeline corrections as patch balance changes.

| Unit / civilization | Old reference -> candidate |
|---|---|
| Grenadier / Jurchens | 35F 65G -> 55F 50G |
| Elite Bolas Rider / Mapuche | 45W 50G -> 50W 55G |
| Elite Blackwood Archer / Tupi | 35W 45G -> 40W 45G |
| Elite Conquistador / Spanish | 70F 60G -> 75F 60G |
| Xianbei Raider / Wei | 65W 25G -> 65W 35G |
| Elite Hussite Wagon / Bohemians | 110W 70G -> 110W 80G; speed .92 -> .88 |
| Bohemian gunpowder speed | Hand Cannoneer 1.10 -> 1.06; Houfnice .80 -> .77; Elite Cannon Galleon 1.33 -> 1.27 |
| Flemish Militia / Burgundians | 30F 25G -> 35F 25G; raw training 14 -> 16 seconds |
| Onager | Fully upgraded main attack 51 -> 56; pierce armor 7 -> 8 |
| Chinese cavalry archers | Heavy tier -> ordinary Cavalry Archer; HP80 ->70, attack11 ->10, melee armor4 ->3 |
| Vietnamese Elite Rattan Archer | HP45 ->48 |
| Vietnamese Heavy Cavalry Archer | HP96 ->80 |
| Vietnamese Elite Fire Lancer | HP102 ->85 |
| Korean / Viking Champion | Pierce armor6 ->5 after losing Gambesons |
| Korean Elite Fire Lancer | Pierce armor6 ->5 |
| War Hulk, owners without Carrack | HP115 ->110; melee armor5 ->4 |
| Xebec / Berbers | Range14 ->15 |

Additional attack-class changes, armor tags, line of sight and research-cost
changes are all retained in the full report. For example the swordsman line's
anti-shock-infantry attack changes are represented in the attack-class maps,
not added to its ordinary melee attack.

### Changed implementation, unchanged final result

- **Elite Teutonic Knight:** base melee armor10 ->8; the widened Teuton Castle
  and Imperial bonuses now provide +1 and +1. With +3 blacksmith armor the
  final total remains **13**. Techs334/335, effects333/334 are in the audit chain.
- **Elite Cataphract:** innate infantry bonus12 ->18, while Logistica stops
  adding its former +6. The final anti-infantry bonus remains **18**; trample remains.
- **Elite Throwing Axeman:** innate range4 ->6 and the removed Bearded Axe no
  longer adds +2. Final range remains **6**. Without excluding retired tech83,
  the old selector would incorrectly produce8.

### Pipeline corrections exposed during this update

- War Chariot's old configuration used unrelated DAT master2150 with fabricated
  overrides. It now uses playable Shu master1962; the stable slug and existing
  Focus Fire/Barrage definitions are preserved. The patch cost is75F90G and raw
  training time32 seconds. The broader range/reload/speed differences in the
  report include this identity correction and must not all be called patch buffs.
- A melee-only upgrade could incorrectly increase the displayed attack of a
  pierce-only weapon. This is corrected; e.g. Elite Ballista Elephant's displayed
  attack15 ->11 reflects removal of phantom melee upgrades, not a new damage nerf.
  The existing attack-class map already carried its pierce damage.
- Encoded attack/armor multipliers use an unsigned percentage byte. Northmen's
  Fury's140% was otherwise read as−116%, producing negative attacks.
- Resolved regional replacement/tier gates now reach the normal analyzer.
  Four Heavy Rocket Cart replacements remain present despite their unavailable
  Mangonel roots. New self-team stats include Danish siege LOS+2 and Varangian
  knight-line infantry attack+1, exactly once.
- Technology research time is read from the actual research-location record,
  instead of defaulting to0 from a nonexistent top-level field.
- Hamask and Shield Wall are included in researched-tech/cost audits despite
  using resource-selected rules rather than immediate unit-stat modifiers.

## New effects: what is known versus what must be validated

All six new civilization unique technologies and the new unit/civ/team effects
are recorded with source IDs. Internal development labels are retained as raw
evidence, but their prose is not treated as a numeric specification.

| Effect | Data-stage treatment / next validation |
|---|---|
| Varangian Bloodlines,1489 | Actual extra+10HP after ordinary+20; total+30, despite internal '+65%' label |
| Danish upgrade gold,1492 | Raw multiplier.34 on specified research gold costs, not the internal label's 'no gold' |
| Cranequins,1452 | Applicable range/LOS+1 and infantry attack+2, with per-civ availability |
| Hamask,1484 | Full-health baseline; own-missing-HP scaling selector recorded. Formula still needs engine/frame validation |
| Shield Wall,1464 | Initial armor excludes formation bonus; nearby-infantry selector recorded. Radius/thresholds still need validation |
| Saxon foot-soldier discount,1469 | 5% per controlled TC/Castle capped20%; no count chosen and no hypothetical discount applied |
| Vendel Legacy,1473 | Knight-line radius+.5 and flat5 trample encoding recorded; runtime ability application is next-stage work |
| Gothikon,1474 | Capacity2, recharge/event/target and inherited projectile semantics retained; not approximated as one simple charge |
| Hearth Troop | Source javelin profile retained once; launch/recharge timing and target mask need validation |
| Jomsviking | Torch target mask320 limits it to buildings/ships; generic unrestricted charge is not an acceptable implementation |
| Jarl | Ranged melee and armor reduction identified; amount, duration and reset behavior must be measured, not copied from Obuch |
| Guard fighting gold | Tasks/resource evidence retained; not modeled as gold per kill |

**Unresolved source discrepancy:** Varangian tech1488 multiplies resource297 by
1.3333 from a base50, while the shipped tooltip says+50% gold. Both are recorded.
No runtime gold rate has been invented to reconcile them.

Other economy/repair/fortification bonuses remain in the evidence bundle even
where the military-unit database has no applicable row. No economic return is
subtracted from the food/wood/gold purchase cost.

## Verification and remaining limits

- 27 focused tests passed before final review; both real candidate databases
  were generated successfully. Reference SQLite integrity check: `ok`.
- Candidate and flat database available-unit counts agree. Golden baseline hash
  is unchanged. Independent review found no new Critical/Important defect.
- Existing `upgrade_cost_*` totals sum researched stat/ability technologies,
  not the unit-tier upgrades themselves. This inherited aggregate definition
  is unchanged; raw elite/regional upgrade costs and IDs are captured separately.
  It does not change fully upgraded stats or the per-unit purchase costs.
- The old extraction name lookup misses `INDIANS.json` and `MAGYAR.json` aliases;
  review found no additional exclusion or wrong resulting row from those two
  files for this patch. Alias cleanup is deferred, not silently included.
- The inherited flat writer warns on textual `hp_transform_reversible=True`;
  it has no corresponding numeric output column. No runtime mechanics were
  rebuilt or certified by this data-stage run.
- E-drive evidence exists: **76 frame files and76 videos for each** of Hearth
  Troop, Jarl and Jomsviking (228 battles total). Recordings were neither modified
  nor rerun. Their battle conditions and outcomes have not yet been validated.

Next: implement/validate the new conditional and secondary-attack behavior
against those recordings, then integrate the validated V3 profiles into the
battle system and run the authorized ranking subset. This document does not
authorize a simulation batch, golden-data replacement, push or deployment.

## Reproduction

From the isolated feature checkout, using the existing Python environment:

```powershell
& 'D:\miniconda3\python.exe' -m aoe2x.dbgen.prepare_patch185872 `
  --dat 'D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat' `
  --output-dir data/local/generated/patch-185872
```

Use `--reuse-extracted` for later reference-only rebuilds **only when the
extraction code has not changed**. It checks that the DAT/tree provenance still
matches. Source updates to extraction require a fresh extraction.

Patch intent was cross-checked against the [official185872 notes](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/).
Numeric comparisons above come from the local DAT and the saved database diff.
