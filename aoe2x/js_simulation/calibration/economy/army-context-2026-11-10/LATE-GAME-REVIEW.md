# Late-game economy and technology review

Source: supplied DAT archive, SHA-256 `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`. All prices assume Imperial Age and all available upgrades. No external bonus descriptions were used.

Hunt, berries, temporary animal-food advantages, starting resources and age-up grants are excluded from the settled land economy. Research discounts, rewards and speed remain an upfront investment ledger. Free research contributes its ordinary lasting effect once; it does not add a permanent gather multiplier. Water, trade, relic, garrison, population and combat-event effects are retained as conditional systems.

## Corrections and coverage

- Every farming fixture was independently replayed from raw source commands, for both farmer sexes and the Farm. All 56 matched; no missing standard farm technology was found.
- 55 civilizations have Horse Collar and Heavy Plow; 36 have Crop Rotation. All 56 have Wheelbarrow and Hand Cart. Khitans use Domestication, Pastoralism and Transhumance instead of farms.
- Persian research now uses Imperial Town Center/Dock forms: Wheelbarrow 62.50 s, Hand Cart 45.83 s, Gillnets 25.00 s, Fishing Lines 16.67 s. Twelve research rows changed; all technology costs stayed identical.
- Portuguese berry wood, Mapuche foraging and other excluded food-source effects no longer mark ordinary land replacement calculations as unresolved. Persistent secondary-income hooks remain flagged.
- All 28 dormant/event-gated economic effects were reviewed. Wei has villager-grant hooks attached to 14 available economic technologies (the Two-Man Saw and Guilds branches are unavailable). These also require Town Center Spawn gates; event multiplicity/timing remains unvalidated and no food refund or extra farmer rate is credited.
- Existing gather-rate estimates are numerically unchanged. Khitan pasture rate and compiled-engine secondary-income formulas remain unresolved. Raw parameters are not advertised as measured income.

## Economic research advantages

| Civilization | Source-derived cost/time advantage |
|---|---|
| Bohemians | Gold Mining, Gold Shaft Mining, Stone Mining, Stone Shaft Mining: free and instant; Caravan, Guilds, Banking, Coinage: research time -44.4% |
| Burgundians | Double-Bit Axe, Bow Saw, Two-Man Saw, Gold Mining, Gold Shaft Mining, Stone Mining, Stone Shaft Mining, Horse Collar, Heavy Plow, Crop Rotation, Wheelbarrow, Hand Cart, Fishing Lines, Gillnets, Caravan, Guilds: food cost -40.0% |
| Burmese | Double-Bit Axe, Bow Saw, Two-Man Saw: free and instant |
| Chinese | Double-Bit Axe, Bow Saw, Two-Man Saw, Gold Mining, Gold Shaft Mining, Stone Mining, Stone Shaft Mining, Horse Collar, Heavy Plow, Wheelbarrow, Hand Cart, Fishing Lines, Gillnets: food cost -15.0%; wood cost -15.0%; Caravan, Banking, Coinage, Shipwright: food cost -15.0%; gold cost -15.0%; Loom: gold cost -15.0% |
| Franks | Horse Collar, Heavy Plow, Crop Rotation: free and instant |
| Goths | Loom: research time -96.0% |
| Italians | Fishing Lines, Gillnets: food cost -25.0%; wood cost -25.0%; Treadmill Crane: wood cost -25.0%; stone cost -25.0%; Shipwright: food cost -25.0%; gold cost -25.0% |
| Jurchens | Treadmill Crane: wood cost -75.0%; research time -50.0% |
| Malians | Treadmill Crane: research time -44.4% |
| Muisca | Caravan, Guilds: free and instant |
| Persians | Wheelbarrow, Hand Cart, Fishing Lines, Gillnets, Loom: research time -16.7% |
| Portuguese | Double-Bit Axe, Bow Saw, Two-Man Saw, Gold Mining, Stone Mining, Stone Shaft Mining, Horse Collar, Heavy Plow, Crop Rotation, Wheelbarrow, Hand Cart, Fishing Lines, Gillnets, Caravan, Guilds, Treadmill Crane, Banking, Coinage, Loom: research time -20.0% |
| Spanish | Double-Bit Axe, Bow Saw, Two-Man Saw, Gold Mining, Stone Mining, Stone Shaft Mining, Horse Collar, Heavy Plow, Wheelbarrow, Hand Cart, Fishing Lines, Gillnets, Caravan, Guilds, Banking, Coinage, Shipwright, Loom: +20 gold on completion |
| Vietnamese | Double-Bit Axe, Bow Saw, Two-Man Saw, Gold Mining, Stone Mining, Stone Shaft Mining, Horse Collar, Heavy Plow, Crop Rotation, Wheelbarrow, Hand Cart, Fishing Lines, Gillnets: wood cost -100.0%; research time -50.0%; Caravan, Guilds: research time -50.0% |
| Vikings | Wheelbarrow, Hand Cart: free and instant |
| Wei | Research-linked villager-grant hooks for 14 available economic technologies; spawn/count semantics unresolved, no resource refund credited |

Wei is a conditional unit-reward entry; the other listed rows are price/time/research-gold differences. Other civilizations have no special price/time advantage in the listed standard economic technologies. Enhanced technology effects, unique paid technologies and unavailable upgrades are tracked below and in separate CSV columns.

## Unique and worker-support technologies

| Civilization | Technology | Upfront cost | Research seconds | Building | Building cost | Lasting effect |
|---|---|---|---:|---|---|---|
| Bengalis | Mahayana | 800 wood, 650 gold | 45.11 | Castle | 650 stone | Villager population use becomes 0.9; population capacity, not faster work. |
| Bohemians | Sanctity | 175 food | 60.00 | Monastery | 175 wood | Bohemian hidden effect also increases villager HP; protection only. |
| Bohemians | Fervor | 140 food | 50.00 | Monastery | 175 wood | Bohemian hidden effect multiplies villager movement by 1.15; included in walking. |
| Bohemians | Hussite Reforms | 500 food, 450 gold | 33.83 | Castle | 650 stone | Monastery technologies replace their gold cost with food, including Fervor and Sanctity. |
| Burgundians | Burgundian Vineyards | 400 food, 300 gold | 33.83 | Castle | 650 stone | Farming-linked gold income; source parameter 236 and hook 14 retained. Numerical gold rate unresolved. |
| Hindustanis | Grand Trunk Road | 250 food, 200 wood | 30.08 | Castle | 650 stone | Gold-miner work ×1.10; separate trade, passive-gold and market effects also retained. |
| Italians | Silk Road | 250 food, 250 gold | 45.11 | Castle | 650 stone | Trade-unit costs ×0.50; requires a trade scenario. |
| Khitans | Domestication | 50 food, 100 wood | 20.00 | Mill | 100 wood | Pasture food parameter +115 × farm-upgrade multiplier; capacity parameter +1. |
| Khitans | Pastoralism | 100 food, 150 wood | 40.00 | Mill | 100 wood | Pasture food parameter +230 × farm-upgrade multiplier; capacity parameter +2. |
| Khitans | Transhumance | 175 food, 325 wood | 70.00 | Mill | 100 wood | Pasture food parameter +345 × farm-upgrade multiplier; capacity parameter +3. |
| Mongols | Nomads | 300 wood, 150 gold | 30.08 | Castle | 650 stone | Housing-loss protection; no harvesting-rate increase. |
| Spanish | Supremacy | 400 food, 250 gold | 45.11 | Castle | 650 stone | Villager combat/survival improvement; no harvesting-rate increase. |
| Vietnamese | Paper Money | 550 food, 200 wood | 45.11 | Castle | 650 stone | Woodcutting-linked gold income; parameter 266 starts at 1.5 and follows three researched wood-upgrade modifiers. Numerical gold rate unresolved. |
| Wei | Tuntian | 250 food, 300 wood | 30.08 | Castle | 650 stone | Persistent income parameter 287 = 3 and hook 4; scope/counting formula unresolved. |

Castle durations include generic Conscription; this is not a civilization-specific speed advantage. Each building cost is listed for review, not charged repeatedly for every technology. Fervor/Sanctity prices for Bohemians assume Hussite Reforms, whose own cost is recorded. Protection and population effects do not increase harvesting directly.

## Complete farming availability audit

HC = Horse Collar; HP = Heavy Plow; CR = Crop Rotation. All listed farm civilizations have HC and HP. Missing CR is retained as a lower-capacity farm, not counted as cheaper/faster research. Food/min is the previously modeled 10-worker scenario including reseeding. Farm food is the natural resource capacity: Mayan credited yield is 550 × 1.15 = 632.5 food.

| Civilization | Farming upgrades | Farm food | Farm wood | Farmer carry | Food/min estimate | Other missing land eco techs |
|---|---|---:|---:|---:|---:|---|
| Armenians | HC, HP | 375 | 60 | 21 | 23.56 | Two-Man Saw, Stone Shaft Mining |
| Aztecs | HC, HP, CR | 550 | 60 | 27 | 23.72 | Two-Man Saw |
| Bengalis | HC, HP, CR | 550 | 60 | 21 | 23.52 | Stone Shaft Mining |
| Berbers | HC, HP, CR | 550 | 60 | 21 | 23.66 | Two-Man Saw |
| Bohemians | HC, HP | 375 | 60 | 21 | 23.68 | — |
| Britons | HC, HP | 375 | 60 | 21 | 23.56 | Stone Shaft Mining |
| Bulgarians | HC, HP, CR | 550 | 60 | 21 | 23.52 | Two-Man Saw |
| Burgundians | HC, HP, CR | 550 | 60 | 21 | 23.54 | — |
| Burmese | HC, HP, CR | 550 | 60 | 21 | 23.54 | Stone Shaft Mining |
| Byzantines | HC, HP, CR | 550 | 60 | 21 | 23.54 | — |
| Celts | HC, HP | 375 | 60 | 21 | 23.53 | Two-Man Saw |
| Chinese | HC, HP | 412.5 | 60 | 21 | 23.53 | — |
| Cumans | HC, HP, CR | 550 | 60 | 21 | 23.52 | Stone Shaft Mining |
| Danes | HC, HP | 375 | 60 | 21 | 23.53 | Two-Man Saw |
| Dravidians | HC, HP | 375 | 60 | 21 | 23.53 | Gold Shaft Mining, Stone Shaft Mining |
| Ethiopians | HC, HP | 375 | 60 | 21 | 23.53 | — |
| Franks | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw, Stone Shaft Mining |
| Georgians | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw, Gold Shaft Mining |
| Goths | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Gurjaras | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Hindustanis | HC, HP | 375 | 60 | 21 | 23.53 | — |
| Huns | HC, HP | 375 | 60 | 21 | 23.53 | Stone Shaft Mining |
| Incas | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Italians | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Japanese | HC, HP | 375 | 60 | 21 | 23.56 | Stone Shaft Mining |
| Jurchens | HC, HP, CR | 550 | 60 | 21 | 23.54 | — |
| Khitans | Domestication, Pastoralism, Transhumance | — | — | — | unresolved | Gold Shaft Mining |
| Khmer | HC, HP, CR | 550 | 60 | 21 | 23.78 | Two-Man Saw |
| Koreans | HC, HP | 375 | 60 | 21 | 23.56 | — |
| Lithuanians | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Magyars | HC, HP, CR | 550 | 60 | 21 | 23.54 | Stone Shaft Mining |
| Malay | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Malians | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Mapuche | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Mayans | HC, HP, CR | 550 | 60 | 21 | 23.44 | Gold Shaft Mining |
| Mongols | HC, HP | 375 | 60 | 21 | 23.53 | Two-Man Saw |
| Muisca | HC, HP, CR | 550 | 60 | 21 | 23.54 | — |
| Persians | HC, HP, CR | 550 | 60 | 21 | 23.52 | — |
| Poles | HC, HP, CR | 550 | 60 | 21 | 26.51 | Two-Man Saw, Gold Shaft Mining |
| Portuguese | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Romans | HC, HP, CR | 550 | 60 | 21 | 24.73 | Two-Man Saw, Stone Shaft Mining |
| Saracens | HC, HP | 375 | 60 | 21 | 23.53 | Stone Shaft Mining |
| Saxons | HC, HP, CR | 550 | 60 | 21 | 23.54 | Stone Shaft Mining |
| Shu | HC, HP | 375 | 60 | 21 | 23.56 | Stone Shaft Mining |
| Sicilians | HC, HP, CR | 1018.75 | 60 | 21 | 23.80 | Two-Man Saw |
| Slavs | HC, HP, CR | 550 | 60 | 21 | 27.09 | Stone Shaft Mining |
| Spanish | HC, HP | 375 | 60 | 21 | 23.57 | Gold Shaft Mining |
| Tatars | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw, Stone Shaft Mining |
| Teutons | HC, HP, CR | 550 | 36 | 21 | 23.52 | Gold Shaft Mining |
| Tupi | HC, HP | 375 | 60 | 21 | 23.56 | Stone Shaft Mining |
| Turks | HC, HP | 375 | 60 | 21 | 23.56 | Stone Shaft Mining |
| Varangians | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Vietnamese | HC, HP, CR | 550 | 60 | 21 | 23.54 | Gold Shaft Mining |
| Vikings | HC, HP, CR | 550 | 60 | 21 | 23.54 | Stone Shaft Mining |
| Wei | HC, HP, CR | 550 | 60 | 21 | 23.54 | Two-Man Saw |
| Wu | HC, HP | 375 | 60 | 21 | 23.56 | — |

## Civilization-by-civilization lasting effects

| Civilization | Sustained land parameters / infrastructure | Additional land income needing a model | Other conditional systems | Excluded early food/grants |
|---|---|---|---|---|
| Armenians | Each available wood upgrade also applies work ×1.06667: approximately +28% per level instead of +20%. These enhanced effects are already modeled.; Each available gold-mining upgrade also applies work ×1.05217: approximately +21% per level instead of +15%. These enhanced effects are already modeled.; Each available stone-mining upgrade also applies work ×1.05217: approximately +21% per level instead of +15%. These enhanced effects are already modeled.; Mule Cart resource costs ×0.75 (25% cheaper).; Fortified Church base definition: costs, garrison/storage, tasks, drop sites and linked forms retained.; Mule Cart base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | — |
| Aztecs | Villager carrying capacity +3 before subsequent carry modifiers. | — | Relic-gold parameter ×1.33; requires relic count and elapsed time. | C-Bonus, +50g |
| Bengalis | — | — | Trade-food parameter 251 increases by 10; trade route and payout semantics remain to model.; Mahayana sets villager population use to 0.9; this is not faster harvesting. | C-Bonus, Free Villagers |
| Berbers | Villager movement ×1.05; later effect 626 multiplies by 1.047619 (about ×1.10 together).; Second villager movement modifier ×1.047619. | — | Fishing/trade ship movement ×1.10; trade-cog work also ×1.10. | — |
| Bohemians | Fervor-linked hidden technology gives villagers movement ×1.15. | — | — | — |
| Britons | Town Center wood cost ×0.50. | — | — | C-Bonus, +25% Shepherd |
| Bulgarians | Town Center stone cost ×0.50. | — | — | — |
| Burgundians | — | Burgundian Vineyards: resource 236 +2, engine hook 14; retain as farming-linked gold mechanic, not an assumed income rate. | Relic-food parameter 225 increases by 20; relic holdings must be specified.; Flemish Revolution triggers engine hook 55; workforce conversion is an event, not a gather bonus. | — |
| Burmese | — | — | — | — |
| Byzantines | — | — | — | — |
| Celts | Lumberjack work ×1.15; missing Two-Man Saw is recorded separately. | — | — | — |
| Chinese | Chinese own-team effect multiplies farm/pasture food and the farm-upgrade multiplier by 1.10. | — | — | C-Bonus, -200f -50w; C-Bonus, Start w/ 6 villagers |
| Cumans | Change TC constr time1; inspect exact commands and target IDs.; Change TC constr time2; inspect exact commands and target IDs. | — | — | — |
| Danes | — | — | Razing-bounty parameter 291 +250 and hook 36 with multiple player scopes; event income, not passive worker output. | — |
| Dravidians | — | — | Fishing ships and shore-fishing worker variants gain +15 carry; exact target IDs retained. | C-Bonus, +200w |
| Ethiopians | — | — | — | C-Bonus, +100f, +100g in age2; C-Bonus, +100f, +100g in age3; C-Bonus, +100f, +100g in age4 |
| Franks | — | — | — | C-Bonus, 15% faster foragers |
| Georgians | Team effect multiplies resource 271 by 0.75; retain parameter, confirm its repair-cost accounting in the engine.; Fortified Church base definition: costs, garrison/storage, tasks, drop sites and linked forms retained.; Mule Cart base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | Fortified Church area effect invokes engine hook 9. Radius, worker coverage and stacking are not encoded by this command. | — | C-Bonus, Start w/ mule cart |
| Goths | — | — | C-Bonus, +10 pop; inspect exact commands and target IDs. | C-Bonus, Hunting bonuses |
| Gurjaras | — | — | Mill garrison type/capacity are changed (capacity 10); herdable-income parameter 254 is set to 15. Herdable composition matters. | C-Bonus, Start w/ 2 bushes |
| Hindustanis | Grand Trunk Road changes gold miners, trade units, relic/passive-gold parameters and market parameters; all targets retained separately.; C-Bonus, Villager cost Age1; inspect exact commands and target IDs.; C-Bonus, Villager cost Age2; inspect exact commands and target IDs.; C-Bonus, Villager cost Age3; inspect exact commands and target IDs.; C-Bonus, Villager cost Age4; inspect exact commands and target IDs.; Caravanserai base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | — |
| Huns | — | — | Huns Tech Tree; inspect exact commands and target IDs. | C-Bonus, Start w/ Horse; C-Bonus, Disable Horse |
| Incas | C-Bonus, Building Stone cost; inspect exact commands and target IDs.; C-Bonus, TC Stone cost; inspect exact commands and target IDs.; Settlement base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | — |
| Italians | — | — | Italians Tech Tree; inspect exact commands and target IDs.; Silk Road multiplies specified trade-unit resource costs by 0.50. | — |
| Japanese | Mill, Lumber Camp and Mining Camp costs ×0.50. | — | Fishing-ship work ×1.05, followed by further age-specific modifiers; survival bonuses kept separately.; C-Bonus; inspect exact commands and target IDs. | — |
| Jurchens | — | — | — | C-Bonus, Animals don't decay |
| Khitans | Pasture base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | — |
| Khmer | Khmer Instant Farmers hook 50 plus farmer work ×0.95; cannot evaluate as a simple 5% income reduction. | — | — | — |
| Koreans | Stone-miner work ×1.20; other tree commands are retained as raw provenance. | — | — | — |
| Lithuanians | Town Center annex 890 has its dead-unit target set to hidden food object 888; completion/death chain grants the source-labelled 100 food per Town Center. | — | — | — |
| Magyars | — | — | — | — |
| Malay | — | — | Fish Trap resource cost ×0.66667.; Fish-trap food parameter 88 is set to 2130; retain exact value rather than relying on the effect label. | — |
| Malians | Building wood-cost modifiers, including exclusions/reapplications, are retained; do not apply a blanket discount to farms.; C-Bonus, TC Wood cost; inspect exact commands and target IDs. | Gold-productivity parameter 276 +10; engine accounting needs confirmation. | — | — |
| Mapuche | Settlement base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | Cavalry-gold source label invokes hook 26; eligible kills/units and amount need engine validation. | C-Bonus, Forager productivity |
| Mayans | Multiple task-output multipliers ×1.15 paired with lower worker work rates (farmer ×0.81, many other jobs ×0.87). | — | — | C-Bonus, -50f; C-Bonus, Start w/ 4 villagers |
| Mongols | — | — | — | C-Bonus, Hunters 40% faster |
| Muisca | Gold task multiplier ×1.15 paired with miner work ×0.869565; resource yield is distinct from collection speed.; Settlement cost ×0.67 and healing-related hook 28; raw settlement forms retained.; Settlement base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | — |
| Persians | Town Center/Dock work modifiers differ by age-specific unit ID: ×1.05/1.10/1.15/1.20. This affects queues, not villager harvest work.; Caravanserai base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | C-Bonus, +50f +50w |
| Poles | Folwark replaces the Mill; instant collection is 10% of current farm food, recalculated after farming upgrades. Modeled on creation/reseeding for covered farms.; Folwark base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | Stone-mining gold mechanic: resource 241 +33.3333015 and hook 13. Keep gold and stone as joint outputs. | — | — |
| Portuguese | Feitoria base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | — | C-Bonus, Foragers generate wood |
| Romans | Villager work ×1.05, farmer work additionally ×1.038095, and Farm generation ×1.05; all are modeled separately. | — | — | — |
| Saracens | — | — | Market cost reduced by 100 wood and market fee parameter changed; trades need a price/quantity scenario. | — |
| Saxons | Repairer work rate ×1.25.; Drop-site variants receive resource-storage changes labelled +35 food/+10 stone; completion event semantics retained for review. | — | — | — |
| Shu | — | Lumberjack-food parameter 502 +7 and engine hook 16; preserve wood and food together. | — | — |
| Sicilians | Farm-upgrade food multiplier ×2.25; does not multiply the initial farm food by 2.25.; C-Bonus, Fast Castle and TC; inspect exact commands and target IDs. | — | First Crusade; inspect exact commands and target IDs. | C-Bonus, +100s |
| Slavs | Farmer work ×1.23 and Farm generation ×1.15; both are modeled separately. | — | — | — |
| Spanish | Builder work ×1.30; research pricing and other tree commands remain separately recorded.; C-Bonus, TC constr time; inspect exact commands and target IDs. | — | Specified trade-unit work rate ×1.25; payout/distance logic still required. | — |
| Tatars | — | — | — | C-Bonus, Sheep +50% food |
| Teutons | Farm cost ×0.60: 36 wood for a standard 60-wood farm in this supplied DAT. | — | — | — |
| Tupi | Settlement base definition: costs, garrison/storage, tasks, drop sites and linked forms retained. | — | Unit Refund hook 27 and parameter 295 = 0.15. Eligible units, trigger and refund resource basis need engine validation. | C-Bonus, +25 each res |
| Turks | Gold-miner work rate ×1.25. | — | — | — |
| Varangians | — | — | Source-labelled gold from sheep/hunt/fishing ships: hook 34 and parameter 298 = 10.0100002.; C-Bonus, VG +33% more gold; inspect exact commands and target IDs.; Caravan-linked extra trade movement and work ×1.0835; do not turn both modifiers into a guessed income percentage. | — |
| Vietnamese | — | Paper Money: gold parameter 266 +1.5 and hook 15; additional hidden modifiers follow researched wood upgrades.; Paper Money parameter ×1.20 conditional on Double-Bit Axe.; Paper Money parameter ×1.20 conditional on Bow Saw.; Paper Money parameter ×1.10 conditional on Two-Man Saw. | — | — |
| Vikings | — | — | Dock costs ×0.85. | — |
| Wei | — | Tuntian: parameter 287 +3 and hook 4; income source/counting semantics remain unresolved. | — | — |
| Wu | Military-building food reward is stored through resource-storage attribute 27, including Docks. | — | — | — |

## Database

The joined `army-context.sqlite` includes `late_farming_audit`, `late_eco_technology_ledger`, `late_unique_eco_technologies`, `late_effect_scopes`, `late_civilization_review`, `late_research_corrections`, and `late_conditional_event_review`. `eco_technology_advantages` exposes the technology exceptions. The canonical current economic research ledger is `late_eco_technology_ledger`; `eco_` source-copy tables retain historical input records for provenance, including their earlier research times. Every current ledger retains IDs, modifier evidence, costs by resource, rewards, research locations and construction costs. The original 2026-11-09 snapshot is preserved.

## Reproduce in this worktree

```bash
python tools/build_upgrade_review.py --output /workspace/scratch/research-review/late-game-2026-11-10
export ARMY_CONTEXT_OUT=/workspace/aoe2_matchup-advisor/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10
export ARMY_RESEARCH_DB=/workspace/scratch/research-review/late-game-2026-11-10/unit-upgrades.sqlite
python tools/export_army_economy.py
node tools/run_army_economy.mjs
python tools/build_army_context.py
python tools/review_late_game_economy.py
python tools/validate_army_context.py
```

Unchanged physical scenarios reuse cached runs only when the fixture and engine hashes match. The source databases and prior fixture files referenced by the tools remain required inputs.
