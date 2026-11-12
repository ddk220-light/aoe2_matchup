# Army economics review — unit production

Reviewer dimension: training times, production buildings, production-related
civilization bonuses, unit purchase prices and the 60-second production
arithmetic. Dataset reviewed: `origin/matchup-timings` at 829c65bec
(`data/golden/army_context.db`, 56 civilizations, 1,031 profiles). Review date
2026-11-12. The dataset was not modified.

## Summary for the owner

**This part of the dataset is mostly reliable.** Base training times, nearly
all bonus multipliers, unit prices and the "how many buildings do I need in 60
seconds" arithmetic match two independent sources almost everywhere. I found
**five errors**. Three of them change a headline number, by 3.6–5.7%, and
they affect only four unit/civilization rows. One (Persian Docks) changes
displayed queue times but not the headline. One is a harmless display issue. I also found **one
civilization bonus that is not modelled** and that would move Wu results by up
to 20% if it were included.

- **Numbers compared:** 7,482 rows in `production-comparison.csv`. The
  60-second arithmetic was also recomputed for every unit at every army size
  from 1 to 27 (27,837 cases).
- **Confirmed:** 7,396 rows match, including all 27,837 arithmetic cases.
- **Wrong:** 69 rows. 55 of these are one harmless display issue (a building
  that cannot be built is listed as an unused alternative). The other 14 rows
  come from errors 1–4 listed below.
- **Uncertain or needing a decision:** 14 rows are not verifiable from data
  alone; they are policy choices, effects coded inside the game engine, or
  rows the user excluded. 3 rows
  are game-version differences, and in those the dataset is the side that is
  right for patch 188329.

The five errors, by impact:

| # | Civ / unit | Dataset | Correct | Effect on the 60-s headline (27 units) |
|---|---|---|---|---|
| 1 | Armenians Warrior Priest | Monastery, 175 W per building | Fortified Church, 200 W | +11.3 villager-minutes (+5.7%) |
| 2 | Mapuche Elite Skirmisher, Halberdier | Settlement only (22 s, 125 W) | Archery Range / Barracks also available (16.54 s, 175 W) | −6.2 VM each (−4.9%) |
| 3 | Mapuche Elite Kona | 65F 40G | 55F 34G (Butalmapu −15%) | −21.5 VM (−3.6%); also changes resource-based army counts |
| 4 | Persian ships (5 units) | Dock works ×1.05 | ×1.20 in Imperial | Training time 12.5% too slow; no change in buildings or headline for any army size |
| 5 | Spearman-line, all non-Sicilian civs (55 rows) | Donjon listed as an alternative route | Donjon is Sicilian-only | None (never selected); visible in `alternativeRoutes` |

**Not modelled, and needs your decision:** Wu military buildings and Docks give
+55 food each when built. Crediting that food would reduce Wu food-costing
armies by 14–20% (27 Halberdiers: 119.0 → 95.4 VM). The other open items are
the Cuman Mercenaries free Kipchaks, the Tupi casualty refund and the scope of
the Saxon discount.

The four "verified unit-price corrections" in the handoff (Magyar Huszar 80F,
Mapuche Bolas Rider 43W 47G, Mayan Arbalester 18W 32G, Mayan Plumed Archer 39W
39G) are all **confirmed** by the DAT and by online sources.

## Method and sources

Each dataset number was compared with values derived independently from the
following sources:

1. **Source A: decoded DAT, without the compiler.**
   `data/local/army-economics/scratch/production-review/current-raw-source.json`
   (DAT SHA-256 `d0aefd92…a337f`, format VER 8.9, contains patch-188329 changes)
   and the matching `current-input/dat/CivTechTrees/*.json`. From the raw effect
   tables I listed **every** effect command that changes a unit's training time
   (attribute 101) or a production building's work rate (attribute 13). There
   are 67 such effects. 32 belong to the 56 civilizations; the others are
   Chronicles or scenario effects. I then recomputed every route's
   seconds-per-order with my own code
   (`final = base × Π train-time multipliers / Π work-rate multipliers`). That
   code does not use the dataset's resolver. It takes technology availability
   from aoe2techtree and uses the building ID that actually exists in the
   Imperial Age.
2. **Source A′: main-repo reference DB** `data/golden/aoe2_reference_simulation.db`
   (branch `army-economics-review`, commit 00a52290b). This is a separate
   generator from an older build. It was used for unit purchase prices. Its
   train times are rounded integers, and it wrongly applies Conscription to Siege
   Workshops and Docks, so its times were used only as a sanity reference.
3. **Source B: aoe2techtree.net**, `https://aoe2techtree.net/data/data.json` and
   `https://aoe2techtree.net/data/locales/en/strings.json`, fetched 2026-11-12.
   The site's front page links the patch notes for **update 188329**, so it is
   the same patch as the DAT. I used its base train times, base unit and building
   costs, each civilization's building/unit/technology lists, and the
   civilization bonus texts.
4. **Source B′: Age of Empires fandom wiki** (MediaWiki API, fetched 2026-11-12).
   I used the pages Huskarl, Tarkan, Temple Guard, Warrior Priest, Fortified
   Church, Settlement, Mapuche, Persians, Kona, Butalmapu, Magyar Huszar,
   Kipchak, Konnik, Serjeant, Flemish Militia, Lou Chuan, Blackwood Archer and
   Conscription. Their change logs run to update 185872 and later. I used them
   for alternate-building times, Fortified Church cost, the Conscription scope
   and the Butalmapu Kona price.
5. **Liquipedia:** its API returned non-JSON to scripted requests, so it was not
   used.

The independent arithmetic for orders per building is `floor(60/s)`; buildings
required is `ceil(orders/orders per building)`; batch orders are
`ceil(n/batch)`; the route chosen is the one with minimum compiled labor, ties
broken by queue time and then building ID. This was recomputed for all 1,031
profiles and army sizes 1–27, and it agrees in every one of the 27,837 cases.

Scripts and intermediate files are in the session scratchpad:
`/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/review-production/`
(`recompute_time.py`, `recompute_prod.py`, `build_csv.py`, `impact.py`,
`prod_effects.txt`, `online/`).

### What the CSV contains

`production-comparison.csv` has one row per compared number. The columns are
civ, unit, field, dataset value, source A, source B, verdict and note. Fields
per profile:

- purchase cost per order (vs reference DB and aoe2techtree base);
- units per purchase;
- for every production route: base train seconds (vs DAT slot and
  aoe2techtree/fandom), final seconds per order (vs independent recompute and
  reference DB), building cost (vs aoe2techtree base with civ discounts) and
  availability;
- orders per building and buildings required for 27 units.

37 additional rows record each production-related civilization effect: its
magnitude and scope compared with the DAT and with the online text.

Coverage:

| Check | Rows | Match | Other |
|---|---:|---:|---|
| Base train time (all routes) | 1,090 | 1,090 | — |
| Final seconds per order (all routes) | 1,090 | 1,085 | 5 mismatch (Persian docks) |
| Building cost (all routes) | 1,090 | 1,089 | 1 mismatch (Fortified Church) |
| Purchase cost | 1,031 | 1,021 | 1 mismatch (Kona), 3 version-difference, 6 not-verifiable (Saxon policy) |
| Units per purchase | 1,031 | 1,031 | — |
| Orders/building, buildings (27 units) | 2 × 1,024 | all | 7 profiles have no route (see below) |
| Route availability / route set | 58 | — | 55 phantom Donjon, 2 Mapuche missing routes, 1 wrong building |
| Production status (no route) | 7 | 5 | 2 not-verifiable (user-excluded Xebec, Chinese Fire Ship) |
| Civilization effects | 37 | 27 | 4 mismatch, 6 not-verifiable |

## Errors found

### 1. Armenian Warrior Priest is trained at a Fortified Church, not a Monastery

- **Dataset:** route "Monastery" (ID 104), 175 wood per building, 14 buildings
  for 27 units.
- **Correct:** Armenians cannot build a Monastery. DAT effect 941
  ("C-Bonus, Fortified Church") upgrades 104 → 1806 (Fortified Church, 200
  wood). aoe2techtree's Armenian building list has 1806 but not 104. The fandom
  Warrior Priest page gives "Building = Fortified Church". The training time
  (30 s, no Conscription) is unchanged.
- **Cause:** the production resolver uses the building ID in the unit's
  training slot and does not follow building-upgrade effects.
- **Impact:** +25 W per building, so +350 W for 27 units: **+11.3
  villager-minutes (+5.7%)** on the headline.

### 2. Mapuche Skirmisher and Spearman lines lose their Archery Range / Barracks route

- **Dataset:** Elite Skirmisher and Halberdier have only a Settlement route
  (22.0 s, 125 W). The Halberdier also lists a phantom Donjon. The Settlement is
  selected: 14 Settlements, 1,750 W.
- **Correct:** aoe2techtree says "Settlements **can** train Spearman-line and
  Skirmishers". Fandom says Settlements train them "in 2.15×/1.61×/same time as
  regular production buildings". Effect 1382 sets attribute 158 ×32767; this is
  a sentinel that adds a new training slot. The resolver instead treated it as
  slot 0 and overwrote the Archery Range / Barracks. With the regular building
  restored, the cheapest route is Archery Range / Barracks at 16.54 s
  (Conscription): 9 × 175 W = 1,575 W.
- **Impact:** **−6.2 VM (−4.9%)** for each of the two units at 27 units. The
  Settlement time itself (22 s in Imperial = 22 × 2.15 × 0.75 × 0.6202) is
  correct.

### 3. Mapuche Elite Kona is missing the Butalmapu discount

- **Dataset:** 65F 40G.
- **Correct:** 55F 34G. Butalmapu is "Team Castle Unique Units and Bolas
  Riders cost −15%" (aoe2techtree), and the fandom Kona page gives 55F 34G
  with Butalmapu. In the DAT, the Bolas Rider part is an explicit ×0.85
  command, which the dataset applies (this is one of the four price
  corrections). The castle-unique-unit part is engine hook 51 (resource 33),
  which the dataset does not evaluate.
- **Impact:** −15% unit price. For 27 Elite Kona the headline is **−21.5 VM
  (−3.6%)**; the building cost is unchanged. Resource-based army counts for Kona
  are also understated. This is a fifth price correction of the same kind as the
  existing four.

### 4. Persian Docks use the Dark-Age work-rate bonus in Imperial

- **Dataset:** Dock work rate ×1.05 for Galleon, Fast Fire Ship, Heavy Demo
  Ship, Elite Cannon Galleon and Carrack (e.g. Galleon 25.71 s).
- **Correct:** ×1.20. DAT effect 421 gives Dock 45 ×1.05, 133 ×1.10, 47 ×1.15
  and 51 ×1.20, and the Imperial Age technology upgrades Dock 45 → 51.
  aoe2techtree and fandom both say Docks work "+5/10/15/20% faster in
  Dark/Feudal/Castle/Imperial Age". The dataset's own `mechanic-coverage.csv`
  records the per-age IDs, but the production route still uses unit 45.
  Correct times: 22.50 / 22.50 / 25.83 / 38.33 / 22.50 s.
- **Impact:** displayed queue times are 14% too long. Orders per building and
  buildings required are unchanged for every army size 1–27, so the headline
  is unchanged.
- **Note:** this is the only age-variant building case that matters. Every
  other production bonus (Conscription, Britons, Goths, Huns, Franks, Celts,
  Perfusion) lists all age variants with the same value.

### 5. Phantom Donjon route on every spearman-line unit

- **Dataset:** 55 Pikeman/Halberdier/Spearman profiles of civilizations other
  than the Sicilians carry a Donjon route. The route keeps its building cost
  adjustments, e.g. Incas 148.75 stone.
- **Correct:** the Donjon is Sicilian-only. It is absent from every other
  civilization's aoe2techtree building list, and the production review flags it
  `production_building_availability_needs_review`. The runtime compiler
  (`route()` in `tools/build_army_context_runtime.py`) filters only on
  `unit_not_resolved_as_trainable…`, so the flag is lost.
- **Impact:** none on numbers, because the route is never selected. It would
  be shown to users in `alternativeRoutes` / `productionRoutes`.

### Minor: rounding of exact halves

Discounted prices are rounded with Python's `round`, which rounds halves to
even: 12.5 → 12, 22.5 → 22, 52.5 → 52, but 37.5 → 38 and 17.5 → 18. This
affects about ten profiles, e.g. Korean Halberdier wood and Gurjara Elite
Elephant Archer / Shrivamsha food. The engine's rounding rule is unverified.
The effect is at most ±1 resource per unit, which is negligible.

### Confirmed version differences (dataset correct)

The Elite Elephant Archer costs 70F 80G in patch 188329 (aoe2techtree; the DAT
patch signature); the older reference DB has 60F. This affects Bengalis,
Dravidians and Gurjaras (52.5F after Kshatriyas). The reference DB is also
missing Corvinian Army, the Imperial Mayan archer step, Butalmapu Bolas and
Conscription's exclusions. Those are reference-DB defects, not dataset
defects.

## Unusual civilization mechanics

All multipliers below were checked against the DAT effect commands and against
the aoe2techtree text. Unless stated otherwise, they are correctly applied and
stack multiplicatively.

- **Conscription** (all 56 civilizations): ×1.33 work rate at Barracks,
  Archery Range, Stable, Castle, Krepost and Donjon. It does not apply to
  Siege Workshops, Docks, Monasteries or Settlements. This is correct (fandom:
  "except Siege Workshops", "does not affect Docks").
- **Perfusion + Goths team + Conscription:** Barracks work ×3.19. Goths
  Halberdier 6.89 s; Elite Huskarl via Anarchy 5.01 s (Barracks base 16 s,
  fandom-confirmed).
- **Marauders:** Tarkan at the Stable, base 24 s (fandom). With Huns team +
  Conscription this is 15.04 s. The Castle route (10.53 s) is also listed; the
  Stable is chosen because it is cheaper to build.
- **Kasbah** (team ×1.25 at Castles): applied to all Berber Castle units,
  including the Trebuchet (30.08 s).
- **Chivalry** (Stable ×1.4), Huns/Britons/Celts/Lithuanians team bonuses: all
  correct.
- **Train-time bonuses**: Aztecs (÷1.15, all military classes including siege
  and warships), Turks (gunpowder ×0.8), Magyars (cavalry archers ×0.8),
  Gurjaras (camels/elephants ×0.8), Khitans (÷1.15), Steppe Husbandry (×0.5),
  Comitatenses (×2/3), Huaracas (×2/3), Circumnavigation (×0.75), Shipwright
  (×0.65; only for civs that have it), Clerical Recruitment (×0.75): all
  correct.
- **Regional and second buildings:** Krepost (Konnik, 350 stone), Donjon
  (Elite Serjeant 12 s, fandom-confirmed), Muisca Temple Guard (Monastery 18 s /
  Barracks 24 s, fandom-confirmed), Condottiero, Imperial Skirmisher and
  Genitour team-bonus buildings: all correct. The exceptions are the Fortified
  Church (error 1) and the Mapuche Settlement (error 2).
- **Flemish Militia:** 16 s × 0.875 = 14 s from the Castle Age (fandom), then
  10.53 s with Conscription. Correct.
- **Blackwood Archer:** trained in pairs, 40W 45G per pair (fandom, update
  185872). 27 units → 14 orders, 28 units, 1 spare. Correct, and it is the only
  batch-trained unit in the roster.
- **Saxon foot-soldier discount:** the maximum −20% (four TCs/Castles) is
  applied by policy to unit classes 0, 6 and 44. The arithmetic is correct. The
  scope ("Foot Soldiers") and the four-building assumption cannot be checked
  from static data, because the discount is driven by engine hooks 38/39.
- **Production-building costs:** civilization discounts are all correct —
  Malians −15% wood, Cumans −75 wood on Archery Range/Stable, Vikings Docks
  −15%, Franks Castles −25%, Incas −15% stone, Slavs Detinets (390 stone + 260
  wood). Malay Harbor costs the same as a Dock.
- **Wu +55 food per military building/Dock** (DAT tech 1084, attribute 27):
  **not modelled**. The dataset deliberately lists it as
  `outside_baseline_or_inventory_only`. See the open questions.
- **Cuman Mercenaries** (5 free Elite Kipchaks per Castle for the whole team,
  12 s): **not modelled** (engine hook 53).
- **Tupi casualty refund** (15%; hook 27): not credited. It affects live
  replacement work only, not the 60-s headline.
- **First Crusade** (one-time Serjeant spawns): not modelled. This is
  consistent with the rule that one-time grants are not repeatable production.
- **Units slower than the window:** the Dromon is 65 s for Armenians and Huns
  (no Shipwright), and the Traction Trebuchet is 70 s for Wei, Shu and Wu. No
  complete purchase fits in 60 s, so the headline is withheld, as the
  specification says.
- **Excluded by the user:** Berber Xebec (unit 1631 is not in the Berber game
  tree at all, so it is a stale roster row) and Chinese Fire Ship (upgraded to
  the Dragon Ship, 1302, in Imperial: 75W 45G, 27 s at the Dock, 17.55 s with
  Shipwright). Neither row represents a real post-Imperial unit.
- **Cliff sensitivity:** Conscription is exactly 1.33, not 4/3. Every 20-s unit
  therefore trains in 15.04 s and fits **3** orders per minute, not 4, and
  every 40-s unit fits 1 order, not 2. This matches the DAT, but a 0.04-s gap
  changes the required building count by up to 33%. The affected units include
  Britons Elite Skirmisher, Elite Kipchak, Roman Cavalier, Huns Elite Tarkan,
  Elite Steppe Lancers, Berber Elite Camel Archer (15.04 s) and Mounted
  Crossbowmen (30.08 s).

## Open questions for the owner

1. **Fix the four headline-relevant errors?** These are the Fortified Church
   cost, the Mapuche regular routes, the Kona price and the Persian Dock rate.
   *Recommendation: yes.* All four are supported by the DAT and by two online
   sources. Kona is a fifth price correction like the existing four, so it
   would also change resource-based army counts.
2. **Remove phantom routes?** Should the compiler drop routes flagged
   `production_building_availability_needs_review`, such as the Donjon for
   non-Sicilians? *Recommendation: yes.* It changes no numbers, and users would
   otherwise see Donjon alternatives.
3. **Wu +55 food per military building/Dock:** credit it as a negative food
   cost on the building? *Recommendation: yes, as a building-cost rebate.*
   It is a permanent, unconditional civilization bonus tied directly to the
   buildings the headline already charges for. It moves Wu food armies by
   14–20%. Under the no-resale rule it does not help armies that need no food.
4. **Cuman Mercenaries:** model the 5 free Elite Kipchaks per Castle?
   *Recommendation: no for the headline, but disclose it in the UI.* It is a
   per-Castle one-time grant, like First Crusade. If you want it modelled, it
   should reduce the Kipchak purchase bill for up to 5 × Castles units.
5. **Saxon discount scope:** keep −20% for classes 0, 6 and 44, assuming four
   TCs/Castles? *Recommendation: keep it, but say in the UI that it assumes
   four controlled TCs/Castles.* Also confirm in game whether foot archers
   count as "Foot Soldiers".
6. **Sub-60-s cliffs and over-60-s units:** keep integer complete orders, with
   Traction Trebuchet and Dromon (Armenians/Huns) withheld? *Recommendation:*
   keep the integer rule, because it matches the specification. Consider a
   fallback for units over 60 s, such as one building per unit with a "queue
   exceeds window" label, so that three Chinese-DLC civilizations are not
   always missing a siege comparison.
7. **Half-unit rounding:** adopt a single rule (round half up) unless an
   in-game check shows otherwise. *Low priority: ±1 resource.*
8. **Roster rows that are not real Imperial units:** Berber Xebec and Chinese
   Fire Ship. *Recommendation:* drop them, or replace the Chinese row with the
   Dragon Ship, rather than keep them as excluded blockers.
