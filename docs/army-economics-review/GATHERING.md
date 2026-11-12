# Army economics review: villager gathering (economy)

Reviewer scope: how fast each of the 56 civilizations' villagers gather food, wood, gold and stone after the Imperial Age, with every economic upgrade and every civ-specific gathering mechanic. Review only. Nothing in the dataset was changed.

Reviewed: branch `origin/matchup-timings` at commit 829c65bec. Read-only copy under the session scratchpad (`.../scratchpad/mt`). Runtime numbers come from `data/golden/army_context.db`. Every compared number is in [`gathering-comparison.csv`](gathering-comparison.csv): 379 rows, 326 match, 32 within tolerance, 14 not verifiable, 2 version differences and 5 mismatches. The 5 mismatch rows come from 3 distinct problems.

---

## 1. Summary for the owner

**Are the gathering numbers trustworthy as estimates?** Yes, with two fixes. For 54 of 56 civilizations, all four rates are good estimates. They are as close to the community measurements as those measurements are to each other, which is about 1–4%.

- **The generic numbers agree with the best measurements available.**
  - **Food:** the model gives about 23.5 food per villager-minute. In AoE2 DE a farm can only release about 0.4 food per second, a hard cap of 24 per minute, and players have measured 23.5–24.4.
  - **Wood:** the model gives 30.4 per minute. Tests found 30.4–31.6.
  - **Gold:** the model gives 27.1 per minute. A single uncrowded miner measures 29.3, and the model reproduces that exactly (29.24). The lower headline value comes from deliberately crowding 10 miners onto one mine.
  - **Stone:** no published measurement exists. Stone uses the same engine as gold, with the game's slower stone work rate.
- **Which upgrades each civ has is correct for all 56 civs.** For example, which civs lack Two-Man Saw, Gold Shaft Mining, Stone Shaft Mining or Crop Rotation. I checked every civ against the public tech-tree site (aoe2techtree), which was updated for the same patch (188329) on 2026-10-27. All 56 match.
- **Civ bonuses are mostly right.**
  - Slavs +15%, Romans +5%, Turks +25% gold work, Koreans +20% stone, Celts +15% wood, Malians +10% gold, Hindustani Grand Trunk Road, Armenian +40% Mule Cart technologies and the Georgian church aura all match the game text and the game file.
  - Teuton and Sicilian farm savings, the Chinese team bonus (+10% farm food), the Mayan "lasts longer", Poles' gold from stone, Shu food from wood and Vietnamese Paper Money all match too.
  - The differences between civs are the right size, given how the game works.
  - One counter-intuitive point is correct: Romans and Slavs get their full food bonus, but Khmer, Aztec, Georgian and Mayan farmers barely gain. Farms, not villagers, are the bottleneck. The game data raises the farm cap only for Slavs and Romans.

**What is wrong**

1. **Danes: a real civilization bonus is missing (data-extraction bug).** The game file contains "Villagers and Fishing Ships drop off +5% food" (tech 1494). The official civ text and the official Danes deep dive both describe it. The extractor never switches it on: it misreads that tech's prerequisite fields as "requires tech 0".
   - Danes food is 23.53 per villager-minute; it should be about 24.7.
   - Farm wood per food is 0.160; it should be about 0.152.
   - Effect: Danish food costs about **5% too many villager-minutes**. Any Danish army that costs food is overstated by up to about 5% of its food share.
2. **Poles: food is overstated by about 3%.** The Folwark bonus is real, and it is modeled in the conservative way. But the 30-minute simulation window credits each covered farm's instant 10% twice: once at time zero and once at its only reseed. Run the same model to steady state and Poles get **25.7, not 26.5** food per villager-minute. Polish food labor is **understated by about 2.8%**. Separately, the fan wiki now says the Folwark takes 8% (formerly 10%), while the game file says 10%. You need to decide which patch is the truth.
3. **Documentation is stale.** The rate table in the review README, plus `summary.json` and `civilization-rates.csv`, predate the latest model changes. That is where "Khitans unresolved", "farm wood 0.3429" and "223/224 rows modeled" come from.
   - The runtime database actually used by the page has all 224 rows.
   - It has Khitan pastures at 25.2 food with 0.106 wood per food.
   - It has Malians at 29.76 gold, Georgians with the church aura, and the Burgundian, Poles, Shu and Vietnamese coproducts.
   - The README table differs from the runtime for 7 civs. Anyone reading the README will see the wrong numbers.

**Biggest remaining uncertainties.** These are estimates, not errors:

- Khitan pastures rest on one forum test of a slightly earlier upgrade level.
- The timed-gold rates (Burgundian Vineyards, Paper Money) have no published measurement.
- Stone has no measurement at all.
- The ±5% sensitivity band is used only in the offline "attrition reversal" screen. The live page shows a plain percentage difference.

---

## 2. Generic gathering: dataset compared with the best available measurements

| Resource | Dataset (villager-min) | Best online/independent value | Source (version, conditions) | Difference | Verdict |
|---|---:|---:|---|---:|---|
| Food, full upgrades | 23.54 | 24 hard cap (0.4 food/s farm regeneration, 15-food buffer) | AoE2 fandom *Farm (AoE2)* (current DE); [reddit 1ipzw3v](https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/) (Feb 2025, multiplayer) | −1.9% | within tolerance |
| Food, HC + Heavy Plow | 23.54 | 23.62 | [AoE forums, how-to-nerf-khitans #183](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183) (Jun 2025, after update 147949, layout unspecified) | −0.3% | match |
| Food, HC + HP, near/outer TC farm | 23.99 / 23.35 (model in that geometry) | 24.01 / 23.54 | [reddit 18l91t2](https://www.reddit.com/r/aoe2/comments/18l91t2/did_some_farm_testing_wheelbarrow_math/) (Dec 2023, scenario editor) | −0.1% / −0.8% | match |
| Food, full, 8 farms on a TC | 23.54 | 24.40 | [Steam guide 1932327114](https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114) (2019/20 DE, forced final deposit) | −3.5% | within tolerance (older patch, different geometry) |
| Food, Folwark-ring geometry, 175-food farms | 20.86 / 19.91 | 20.69 / 19.35 | [vixark Folwark analysis](https://vixark.com/age-of-empires-ii/folwark) (286 observations, build unknown) | +0.8% / +2.9% | within tolerance |
| Wood, full | 30.43 | 31.60 | [reddit 1ilig6h](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/) (Feb 2025; 12 lumberjacks, 3 camps, 14 min) | −3.7% | within tolerance (−0.5% in a matched one-tile-gap layout) |
| Wood, full (analytical) | 30.43 | 30.42 | [reddit fes2fb](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/) | 0.0% | match |
| Wood, no Two-Man Saw | 28.24 | 28.32 | same | −0.3% | match |
| Gold, full | 27.06 (10 miners, one 4-tile mine) | 29.27 (one miner, one tile, no bumping) | [Forgotten Empires gold guide](https://www.forgottenempires.net/strategy/age-of-empires-ii-strategy-center/gold-relics) (patch unstated) | −7.5% (single uncrowded miner in the model: −0.1%) | version/condition difference |
| Stone, full | 25.59 | none found | — | — | not verifiable |

DAT parameters check out against published DE values:

- **Farms:** 175 + 75 + 125 + 175 = 550 food, 60 wood, 0.40/s cap.
- **Work rates:** wood 0.39 with +20/+20/+10%; gold 0.38 and stone 0.36 with +15/+15%.
- **Villager speed:** 0.8 × 1.1 × 1.1.

The integer carry rounding (21 for farmers, 20 otherwise) is an assumption with no online confirmation.

**Assessment.** The generic model is within about 1–4% of every comparable published test. That is the same spread the tests show among themselves, since none of them match the model's layout. Stone is the weakest point (no data) and also the most heavily weighted (×3).

---

## 3. Civilization-specific mechanics

"Δ" is the model's change against the generic rate for the same upgrade set. Online text means the in-game civ description at aoe2techtree commit `e56728e` ("Implement DE Update 188329", 2026-10-27). That is the same patch the DAT carries: its patch-signature units, 873/875/2569, match that commit's diff.

| Civ | Mechanic (game text) | How the model handles it | Model result | Verdict |
|---|---|---|---|---|
| Armenians | Mule Cart technology effects +40% | DAT multipliers: wood ×1.0667 and gold/stone ×1.0522 per tech level (= +40% of each upgrade). Mule Cart footprint used as the drop site | wood +9.4%, gold +8.8%, stone +5.9% | correct |
| Aztecs | Villagers carry +3 | carry +3 before the Wheelbarrow and Hand Cart multipliers | food +0.8% (farm cap), wood +3.2%, gold +2.1%, stone +1.6% | correct |
| Berbers | Villagers move +10% | speed ×1.05 × 1.0476 | +0.5 to +1.5% | correct |
| Bohemians | Fervor affects villagers; mining techs free | speed ×1.15; free techs go to the research ledger | +0.6 to +2.4% | correct |
| Burgundians | Vineyards: farmers slowly generate gold | 2 gold per *active* farming minute (DAT resource 236); coproduct | +1.58 gold per food villager-minute | plausible; no measurement online (old forum arithmetic suggests ~1/min) |
| Celts | Lumberjacks +15% | work ×1.15; no Two-Man Saw | wood 31.41 (+11.2%) | correct |
| Chinese | Team: farms +10% food; no Crop Rotation | farm 412.5 food | farm wood/food 0.1455 | correct |
| **Danes** | **Villagers and Fishing Ships drop off +5% food** | **not modeled**: tech 1494 is never activated | food 23.53 (should be ≈24.71); wood/food 0.160 (should be ≈0.152) | **error** |
| Franks | Mill techs free | research ledger only | no rate change | correct |
| Georgians | Fortified Church: +10% work rate within 9 tiles | ×1.1 work, full coverage, no church cost (owner assumption) | food +0.8%, wood +6.6%, gold +10.0%, stone +9.3% | correct under the stated assumption |
| Gurjaras | Livestock garrisoned in Mills produce food | excluded (needs livestock) | — | consistent exclusion |
| Hindustanis | Grand Trunk Road: all gold income +10% | gold-miner work ×1.10; trade and relic parts excluded | gold +7.5% | correct |
| Khitans | Pastures replace Farms (2 herders, 9 animals × 115 food, 110 wood) | online lifecycle proxy of 25.20 food/min with immediate credit; 110 wood per 1035 food | food 25.20, wood/food 0.1063 | acceptable proxy (see §5) |
| Khmer | Farmers need no drop site | auto-deposit, plus a DAT farmer work ×0.95 that the help text does not mention | food +1.0% | correct (the farm cap makes the ×0.95 irrelevant) |
| Koreans | Stone miners +20% | work ×1.20 | stone 30.14 (+17.8%) | correct |
| Malians | Villagers drop off +10% gold | ×1.10 credit on deposit | gold 29.76 | correct (README table is stale at 27.06) |
| Mayans | Resources last 15% longer | yield ×1.15 with lower work rates in the DAT; collection speed unchanged; farm 632.5 credited food | food −0.4%, wood +1.9%, farm wood/food 0.0949 | correct |
| Muisca | Team: gold lasts 15% longer | same as Mayans, gold only | +0.0% | correct |
| **Poles** | Folwark replaces Mill (instant 10% of new farm food); stone miners also make gold | instant food taken *from* the farm, 8 of 10 farms covered; 33.3% gold coproduct on stone | food 26.51; gold 8.53 per stone villager-minute | gold correct; **food +3.1% too high** (window artifact); 8% vs 10% open |
| Portuguese | Feitoria (Imperial trickle building) | excluded | — | consistent exclusion, but not listed in the README limits |
| Romans | Villagers gather, build and repair +5% | work ×1.05; DAT also raises farm generation ×1.05 | food +5.0%, wood +4.2%, gold +4.0%, stone +5.7% | correct |
| Shu | Lumberjacks generate food | 7 food per 100 wood (DAT 502) | +2.13 food per wood villager-minute | plausible; the official text gives no number |
| Sicilians | Farm upgrades +125% food | upgrade food ×2.25: farm 1018.75 | food +1.1%, wood/food 0.0589 | correct |
| Slavs | Farmers +15% | DAT farmer ×1.23 and farm generation ×1.15 (the cap rises) | food 27.09 (+15.1%) | correct |
| Teutons | Farms −40% | 36-wood farm | wood/food 0.0655 | correct |
| Turks | Gold miners +25% | work ×1.25 | gold 32.61 (+20.5%) | correct |
| Vietnamese | Paper Money: lumberjacks slowly generate gold | 2.376 gold per active wood minute | +1.95 gold per wood villager-minute | plausible; no current measurement |
| Vikings | Wheelbarrow and Hand Cart free | research ledger only | — | correct |
| Wei | Free villager per eco tech; Tuntian | one-off grants excluded; Tuntian excluded by owner | — | consistent |
| Others (Bengalis, Britons, Bulgarians, Burmese, Byzantines, Cumans, Dravidians, Ethiopians, Goths, Huns, Incas, Italians, Japanese, Jurchens, Lithuanians, Magyars, Malay, Mapuche, Mongols, Persians, Saracens, Saxons, Spanish, Tatars, Tupi, Varangians, Wu) | No post-Imperial land gathering-rate bonus (only shepherd/hunter/forager/fishing, one-off grants, trade, relics, refunds or research discounts) | generic rates for their upgrade set | all within ±1% of their class baseline | correct |

Pastures belong to the Khitans only. Mongols, Cumans and Tatars use farms in this patch, as the dataset does.

---

## 4. Errors in detail

### E1. Danes +5% food drop-off missing (extraction bug)

- **Evidence.** In `labor-inputs.sqlite` `raw_technologies`, tech 1494 is "C-Bonus, Villagers & Fishing Ships +10% food" (civ 62 = Danes). Its `required_techs` is `[0,-1,-1,-1,-1,-1]` and its `required_tech_count` is `0`. Its effect 1494 sets resource 299 to +5.01 and engine hook 35. That is the same pattern as the Malian gold bonus (resource 276 +10, hook 11), which *is* modeled. The tech does not appear in `active_effect_commands`, `conditional-event-review.csv`, `effect-scopes.csv` or the Danish rows of any review table.
- **Cause.** `tools/build_production_review.py` (around line 146) and `tools/build_economy_review.py` (line 75) treat `required_count == 0` as "all listed prerequisites required", and the list contains tech 0. In the game, a count of 0 means no prerequisite. The tech's name says +10% but the value is 5.01. The official text says +5%.
- **Online confirmation.** The aoe2techtree civ text (188329) says "Fishing Ships and Villagers drop off +5% food". The official [Danes deep dive](https://www.ageofempires.com/news/danes-civilization-deep-dive/) says villagers drop off extra food.
- **Impact.** Danes food should be ≈24.71 per villager-minute (+5%), with farm wood per food ≈0.152. In the labor program, the cost of one food falls from 0.0482 to 0.0459 villager-minutes (−4.8%). Every Danish army with a food cost is overstated by up to about 5% of its food share. Wood, gold and stone are unaffected. I found no other civilization tech hidden by this pattern: I scanned all civ-owned automatic techs that are not active, and the rest are correctly inactive (missing prerequisites, age grants, relic events, or empty effects).

### E2. Poles food overstated about 3% (simulation-window artifact)

- **Evidence.** `tools/farm-gathering-sim.mjs` credits `instant_food` at t = 0 (`harvested: instantFor(f)`) and again at every reseed. The army run is 1,800 s with each farm reseeded about once. Covered farms therefore get 2 × 55 instant food in 30 minutes instead of the steady-state 55 per ~21-minute cycle. I re-ran the unchanged model fixture (`eco-inputs.json`), seed 0, out to 9,000 s:

  | Civ | 0–1800 s (dataset) | 1800–9000 s (steady state) |
  |---|---:|---:|
  | Poles | 26.54 | 25.71 |
  | Byzantines (generic) | 23.54 | 23.52 |
  | Slavs | 27.08 | 26.91 |
  | Sicilians | 23.80 | 23.66 |

  The generic farm layout and the Folwark layout give the same rate without the bonus (23.58 vs 23.54), so layout is not the cause.
- **Impact.** Polish food labor is understated by about 2.8% (0.0416 vs 0.0428 villager-minutes per food). Other civs move by less than 0.7%. With the 8% Folwark figure from the wiki, the windowed model would give 25.92, and steady state would be lower again (about 25.2).

### E3. Stale documentation (no runtime effect)

The rate table in `army-context-2026-11-10/README.md`, plus `civilization-rates.csv`, `summary.json` (`modeled_resource_rows 223`) and `civilization-review.csv`, predate the special-economy and pasture models. They differ from `army_context.db` for:

- **Khitans:** unresolved and 0.3429 in the docs, against 25.20 and 0.1063 in the runtime.
- **Malians:** 27.06 against 29.76 gold.
- **Georgians:** pre-aura values in the docs.
- **Burgundians, Poles, Shu and Vietnamese:** the docs omit their coproducts.

The "223/224" is Khitans food. The runtime has 224/224. `docs/army-economics.md` is current.

### Minor observations (no change recommended without owner input)

- **Drop sites for Armenians and Georgians.** These two use the Mule Cart footprint as their lumber/mining drop site. That costs about 0.8% against an ordinary camp. Both civs can also build normal camps.
- **Khmer farmer work ×0.95.** This comes from the DAT. The help text omits it, and an older patch note mentions −3%. It has no effect because of the farm cap.

---

## 5. Notes on the striking values the owner asked about

| Value | Why it is what it is | Right? |
|---|---|---|
| Poles food 26.51 | Folwark instant food plus window artifact | real bonus, but ~25.7 at steady state (E2) |
| Slavs food 27.09 | the only civ whose farms regenerate faster (+15%) | yes |
| Romans food 24.73 | +5% applies to farmers *and* the farm regeneration rate | yes |
| Turks gold 32.61 | +25% miner work, diluted by walking to +20.5% | yes |
| Hindustanis gold 29.09 | Grand Trunk Road +10% miner work → +7.5% | yes |
| Armenians gold 29.45 | +40% Mule Cart tech effects: gold upgrades +21% instead of +15% each | yes |
| Koreans stone 30.14 | +20% stone work → +17.8% | yes |
| Celts wood 31.41 | +15% lumberjacks, but no Two-Man Saw | yes |
| Khitans food "unresolved", farm wood 0.3429 | stale README; runtime has 25.20 and 0.1063 | runtime correct |
| Sicilians farm wood 0.0589 | 60 / 1018.75 (farm upgrades +125%) | yes |
| Teutons farm wood 0.0655 | 36 / 550 (farms −40%) | yes |
| Mayans farm wood 0.0949 | 60 / 632.5 (resources last 15% longer) | yes |

The relative ordering between civs is right. Every civ without a gathering bonus is within ±1% of the generic rate for its upgrade set. Every bonus has the right sign and a magnitude consistent with the game text once walking and the farm cap are accounted for.

---

## 6. Best available online estimates (citations)

- **Farm cap:** 0.4 food/s per farm, up to a 15-food invisible buffer, so about 24 food/min. Aztecs and Khmer hit the cap; Slavs get around it because their farm growth rate is raised. Sources: AoE2 fandom *Farm (Age of Empires II)*; [reddit 1ipzw3v](https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/).
- **Pastures:**
  - [Update 147949 notes](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-147949/) removed the Khitan +10% shepherd/herder bonus, increased herder walking distance, and cut the herder edge over un-upgraded farmers from about +12% to about +7%.
  - A balance patch summarized on the forums set Pasture to 110 wood and animals to 115 food.
  - Lifecycle test: [AoE forums #183](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183) and its method in [#191](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/191) (Jun 2025), 25.20 food/min.
  - A separate single test reported 23.24 food/min against 19.27 for Britons farms, early-game conditions.
- **Wood:** 30.4–31.6 per villager-minute fully upgraded ([reddit 1ilig6h](https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/), [reddit fes2fb](https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/)).
- **Gold:** 29.27 per villager-minute for an uncrowded miner one tile from the camp ([Forgotten Empires](https://www.forgottenempires.net/strategy/age-of-empires-ii-strategy-center/gold-relics)).
- **Poles:**
  - Stone-to-gold was reduced from 50% to 33% in Dynasties of India (AoE2 fandom *Poles/Strategy*).
  - The Folwark is described as 8% (formerly 10%) of a new adjacent farm's food (AoE2 fandom *Folwark*). The DAT says 10%.
- **Civ texts and tech trees:** [SiegeEngineers/aoe2techtree @ e56728e](https://github.com/SiegeEngineers/aoe2techtree/commit/e56728e76b7d08301fba7b18d5f16bc8554c109a) (DE update 188329). All 56 tech trees match the dataset's missing-upgrade lists.
- **Danes:** [official Danes deep dive](https://www.ageofempires.com/news/danes-civilization-deep-dive/).

Access limits: in this session the AoE forums and the fandom wiki could only be read through search-engine summaries, not fetched directly. Values quoted from those sites come from summaries and the repository's earlier captures. The aoe2techtree data was downloaded and parsed directly.

---

## 7. Open questions for the owner

1. **Which patch is the truth for the Folwark (10% in the DAT or 8% on the wiki)?** *Recommendation:* keep the supplied DAT (patch 188329 balance) as the single truth. It matches aoe2techtree's 188329 data everywhere else I checked. Note the wiki figure as a possible newer or older value.
2. **Is Folwark food extra, or taken out of the farm?** The model takes it out of the farm, which is conservative. Nothing online settles it. *Recommendation:* keep it as is until measured. Either way, fix the start-up double credit (E2) by measuring a steady-state window, for example 1,800–5,400 s, or by not crediting instant food for the initial farms.
3. **Fix the Danes bonus?** *Recommendation:* yes. Treat `required_tech_count == 0` as "no prerequisite" in both review builders. Model it like the Malian credit (×1.05 food on deposit), then regenerate. Expect Danes food at about 24.7.
4. **Pastures:** keep the 25.2 online proxy? *Recommendation:* yes for now. It agrees with the developers' own "+7% over farmers". It probably slightly under-states Imperial pastures, because Transhumance means fewer rebuilds. Label it the lowest-confidence food number.
5. **Trickle, relic, trade and Feitoria income:** include or not? *Recommendation:* keep them excluded, because they are not villager labor and depend on map and game state. Add one sentence listing Feitoria, Caravanserai, relics, trade, Tuntian, Gurjara livestock and fishing/fish traps as excluded. Keep Vineyards, Paper Money, Shu food and Poles gold, which are tied to villagers working.
6. **One-off grants that offset the investment in the headline:** for example Wu (+55 food per military building) and Saxons (+35 food/+10 stone per camp). Should they reduce the production-building cost? *Recommendation:* yes for Wu military buildings, because the headline already charges for those buildings. This is for the production reviewer to confirm.
7. **Show the ±5% band on the live page?** *Recommendation:* label any live difference under about 5–10% as "too close to call". The offline screen already requires surviving ±5%, and the generic model's real-world error is about 2–4% per resource.
8. **Is an in-game measurement worth it?** *Recommendation:* yes, but only a small, targeted set.
   - **Which civs and resources:** Danes farming, Poles Folwark (8 vs 10%, extra vs deducted), Khitan pastures with Transhumance, Burgundian Vineyards gold per minute, and one generic stone-mining run (stone carries the ×3 weight).
   - **How:** in the scenario editor, use a fresh post-Imperial setup with 10 villagers on a 10-farm or 4-tile layout matching `eco-inputs.json`.
   - **What to record:** run 30 game minutes and log banked resources, villagers' carried amounts and wood spent at 5-minute marks. Two runs per case is enough.
   - The validator in `docs/army-economics.md` already accepts these windows.
9. **Should the stale README rate table be regenerated from the runtime?** *Recommendation:* yes, so reviewers stop seeing "Khitans unresolved" and the pre-aura and pre-coproduct values.
