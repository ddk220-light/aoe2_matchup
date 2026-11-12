# Army economics (backend data)

**Status, 2026-11-12:** offline data pipeline only. Nothing here is served by the
API or shown on the site; storage and UI integration are the next, owner-led
steps. All gathering rates are estimates (`status: estimate`); no in-game
measurement has been made.

## What the data is

For a Battle Sim pair, each army gets a **60-second army investment** in
**weighted villager-minutes**: how much villager work it takes to pay for

1. the army itself (batch-rounded purchase bill),
2. the production buildings needed to train it within 60 seconds, and
3. the net cost of the research **both** armies share (common technology IDs),

with resources weighted food 1, wood 1, gold 1.5, stone 3 and converted to work
using that civilization's post-Imperial gathering rates (simulated farms, wood,
gold and stone plus civilization bonuses). The cheaper army in villager-minutes
"wins" the comparison. Next to that headline, every army also carries its
**full** research package and the **exclusive** (unshared) part, each as cost,
weighted villager-minutes and research time.

## Where things live

| Path | What | Size |
|---|---|---:|
| `aoe2x/economy/` | importable code: `accounting` (bills, 60-s production, labor LP and its compiled dual), `compiler`, `curated` (owner decisions + cited corrections), `matchup` (evaluate a pair), `special_economy`, `policy`, `observations`, `restore`, `paths` | — |
| `tools/economy/` | offline scripts: DAT extraction (`build_{production,upgrade,economy,labor_inputs}_review.py`), gathering simulations (`farm-/wood-gathering-sim.mjs`, `gold-mining-sim.mjs`), `run_special_economy.mjs`, `impact_report.py`, `summarize_runtime.py` | — |
| `data/army_economics/army_context.db` | compiled runtime database (56 civilizations, 1,029 unit profiles) | 32 MiB |
| `data/army_economics/army_context.validation.json` | its metadata: assumptions, every curated correction, dropped rows, price corrections, scope exceptions | 0.1 MiB |
| `data/army_economics/civilization-rates.csv` | generated rate table (below) | 4 KiB |
| `data/army_economics/sources/army-context-2026-11-10/` | reviewed source snapshot `army-context.sqlite.gz` (restores to 146 MiB) + `eco-inputs.json`, `special-gather-rates.json`, `online-mechanic-evidence.json`, `pasture-online-reference.json` | 9.9 MiB + 1.5 MiB |
| `data/army_economics/sources/handoff-data-2026-11-12/` | upstream extraction inputs (`production/research/economy-review.tar.gz`) + checksum manifest | 6.4 + 11 + 13 MiB |
| `tests/test_army_economics_*.py`, `tests/economy/` | Python and JS tests (+ small gathering fixtures) | — |
| `docs/army-economics/impact-2026-11-12.csv`, `reverification/` | before/after impact of the 2026-11-12 changes; re-run of the independent review | — |

The runtime database is deliberately **not** in `data/golden/`:
`scripts/migration/prepare_release.py` ships every `data/golden/*.db` with the
backend. `aoe2x/economy/` is likewise outside the packaged `aoe2x` subpackages,
so this branch does not change the release (`apps/web/src/generated/release.json`
is identical before and after).

The compressed archives are byte-identical to the blobs on branch
`matchup-timings` (829c65bec), so they add no new objects to the repository.
Not ported (still on `matchup-timings`): the deleted page/API
(`apps/website/...`), the dated research folders
`aoe2x/js_simulation/calibration/economy/{farms,wood,gold,...}-2026-11-0*/`
(hundreds of MB of experiment JSON), the historical
`army-context-2026-11-09` database and `tools/build_army_context.py` /
`review_late_game_economy.py`, which built the snapshot from those folders and
the combat campaign.

## How it is computed (short)

- **Purchase:** `orders = ceil(units / batch)`; price from the DAT (+ curated
  engine-hook price effects), rounded half up.
- **Production:** per route, `orders per building = floor(60 / seconds per order)`,
  `buildings = ceil(orders / orders per building)`; the route with the least
  combined weighted labor wins (ties: faster queue, lower building ID). Building
  completion rebates (Wu) are netted per building.
- **Labor:** minimum villager-seconds over the civilization's activity vectors
  (food, wood, gold, stone; farm/pasture wood is a negative output; coproducts
  such as Poles gold-from-stone count once, no resale). The compiler stores the
  vertices of the LP dual, so a bill's labor is `max(bill · price vertex)` with no
  solver at runtime.
- **Research:** packages per unit (combat `military`, `production` speed, `economicSetup`);
  Imperial pricing; Spanish refunds; free techs at 0. Head-to-head, only common
  IDs enter the headline (`aoe2x.economy.matchup.evaluate_matchup` →
  `teams[i].researchSummary.{common,exclusive,full}`); every unit also stores
  `research.military.summary` (full package).

## Owner decisions applied (2026-11-12)

| # | Decision | How it is applied | Evidence / check |
|---|---|---|---|
| 1 | Headline keeps **common** research only; expose full and exclusive | `research.military.summary` per unit; `researchSummary.{common,exclusive,full}` per pair (net cost, weighted cost, villager-minutes, research seconds) | test: common + exclusive = full for every resource and time |
| 2 | Add 7 missing technologies; fail on any unreviewed "needs review" tech | `curated.ADDED_RESEARCH` (17 unit packages: Winged Hussar Poles 300F/800G and Lithuanians 600F/800G at 45.1 s; Hamask, Shield Wall, Ordo Cavalry, Coiled Serpent Array, Butalmapu, Red Cliffs Tactics); `CANDIDATE_DECISIONS` covers all 32 flagged techs, otherwise compilation fails | costs/times asserted against the DAT; aoe2techtree 188329 text; reference DB `ref_techs_applied` |
| 3 | Remove Crenellations (Teutons) and Aznauri Cavalry (Georgians) | moved to `research.excludedNonCombat` on the 7 affected units | — |
| 4 | Age-ups stay out; record discounts | `civilizations.notes.ageUp`: Byzantines, Italians, Malay, Muisca (DAT modifiers) + Dravidians, Ethiopians, Khmer (civ text) | compiler fails if a DAT age-up modifier has no note |
| 5 | Fix every review error | see next table | re-verification below |
| 6 | Wu +55 food per military building/Dock | `completionRebate` on Wu Barracks/Range/Stable/Workshop/Dock routes; `investmentCost` is net, `grossInvestmentCost` and `rebate` stay visible | DAT tech 1084 (type 4, attribute 27) read from the snapshot |
| 7 | Relics/trade/Feitoria/Caravanserai/trickle excluded; note Lithuanian 4-relic combat assumption | `metadata.excludedIncome`, civ notes, assumptions | `aoe2x/dbgen/config_constants.py` `LITHUANIAN_RELIC_COUNT = 4` |
| 8 | Drop Berber Xebec and Chinese Fire Ship | `metadata.droppedProfiles` (1,031 → 1,029 profiles); their waivers removed from `policy.py` | Dragon Ship **not** added: the combat reference DB has no Dragon Ship profile (follow-up) |
| 9 | Saxons keep −20% foot-soldier discount | labelled "assumption" in pricing and civ notes | — |
| 10 | Gathering rates stay estimates; Khitan pasture 25.2 lowest confidence | `status: scenario_estimate` / `online_reference_estimate`; Khitan note | — |

### Review fixes

| Review finding | Fix | Result |
|---|---|---|
| Danes +5% food drop-off never applied | Extractor rule fixed in `tools/economy/build_{production,economy}_review.py` (`required_tech_count 0` = no prerequisite). Re-running both extractors on the restored inputs changes **only** Danes tech 1494 (plus 22 empty "RESERVED" placeholder techs with no effect); no other bonus changes state. The compiler replays the same rule on the snapshot and fails on any other activation. Modeled like the Malian gold bonus (×1.05 food on deposit; DAT stores 5.01) | Danes food 23.53 → 24.71 /villager-min; farm wood per food 0.160 → 0.152 |
| Poles Folwark double credit | `run_special_economy.mjs` measures the unchanged Poles farm fixture over 1,800–9,000 s (3 seeds); Folwark 10%, 8 of 10 farms, deducted from the farm | 26.51 → 25.71 |
| Elite Kona missing Butalmapu −15% | `curated.PRICE_MULTIPLIERS` (engine hook 51) | 65F 40G → 55F 34G (55.25 → 55); also a price correction for army counts |
| Mapuche Elite Skirmisher/Halberdier lost Archery Range/Barracks | `curated.RESTORED_ROUTES` (Settlement kept as an alternative; route rule picks) | Archery Range/Barracks 16.54 s, 9 × 175 W instead of 14 Settlements × 125 W |
| Settlement research without Conscription | research where it is fastest (only strictly faster locations replace the snapshot choice; only Mapuche 98/197/429 change) | Elite Skirmisher 50 → 37.6 s, Pikeman 35 → 26.3 s, Halberdier 50 → 37.6 s |
| Warrior Priest at the Monastery | `curated.BUILDING_SUBSTITUTIONS` (DAT effect 941, 104 → 1806) | Fortified Church, 200 W |
| Persian Docks ×1.05 | Imperial command of DAT effect 421 (Dock 51, ×1.20) | Galleon 25.71 → 22.50 s (no headline change for 1–27 units) |
| Phantom routes | routes flagged `production_building_availability_needs_review` dropped | 55 Donjon routes removed; Sicilians keep theirs |
| Exact-half prices | round half up (values within 1e-6 of .5 count as halves) | Gurjaras Elite Elephant Archer / Shrivamsha 52 → 53 F; Koreans Halberdier/Arbalester 12 → 13 W, Elite Fire Lancer 22 → 23 W |
| Stale summary/README rate tables | table below and `civilization-rates.csv` are generated from the runtime (`summarize_runtime.py --check` guards it) | — |

Rounding rule: the in-game rule for exact halves is **not verified**; at most ±1
resource per unit.

## Re-verification (independent review scripts re-run, 2026-11-12)

The reviewers' comparison scripts (`origin/army-economics-review`,
`docs/army-economics-review/scripts/`) were adapted to read any runtime database
(`reverification/scripts/`; adaptations make previously hard-coded verdicts data
driven). Re-run on the old database they reproduce the review's counts exactly.

| Area | Review (old data) | Rebuilt data |
|---|---|---|
| Production (unit rows; the 37 static effect rows are not re-run) | 7,445 rows: 65 mismatch, 8 not verifiable, 3 version differences | 7,224 rows: **4 mismatch**, 6 not verifiable, 3 version differences; 60-s arithmetic 27,783 cases, 0 differences |
| Research | 56,076 rows: 36 mismatch, 204 not verifiable | 56,052 rows: **0 mismatch**, 197 not verifiable |
| Gathering | 379 rows: 5 mismatch | 379 rows: **0 mismatch** |

The 4 remaining production mismatches are intended: the half-up rule makes the
Korean Halberdier/Arbalester/Elite Fire Lancer and Gurjara Shrivamsha one
resource dearer than the older reference DB (`data/golden/aoe2_reference_simulation.db`).
Not verifiable (unchanged in kind): Saxon discount scope (6), age-up rows (168),
the hidden Champi Scout tech, Burgundian Vineyards / Shu / Vietnamese coproduct
rates, stone (no measurement), Folwark 8% vs 10% and extra-vs-deducted.
Rows: `reverification/remaining-non-match-rows.csv`; counts: `reverification/summary.json`.

## Impact (27 units, before → after)

`impact-2026-11-12.csv` lists all 77 changed rows (`tools/economy/impact_report.py`).
"Mirror" = the unit against itself (common research = its full package);
"army" = purchase + 60-s buildings only.

| Change | Rows | Effect |
|---|---|---|
| Missing technologies | 17 | research +30.5 to +78.2 villager-minutes (VM) per unit; mirror up to +26.8% (Wu Heavy Demo Ship nets −2.8% with the Wu rebate) |
| Crenellations / Aznauri removed | 7 | research −73.7 VM (Teutons), −39.5 VM (Georgians); mirror −4.9% to −20.7% |
| Wu rebate | 15 (all Wu rows) | food armies −14.0% to −20.5% (army); every Wu mirror −2.8% to −11.7% (research food is offset too) |
| Danes food | 18 (4 also get Hamask) | army 0 to −2.6% (food share only); research −1.8 to −7.9 VM |
| Poles steady state | 18 (1 also gets Winged Hussar) | army 0 to +1.1%; mirror +0.04% to +1.4% |
| Warrior Priest | 1 | +11.3 VM (+5.7%) |
| Mapuche routes | 2 | −6.2 VM (−4.9%); Elite Skirmisher research −12.4 s |
| Elite Kona price (+ Butalmapu research) | 1 | army −21.5 VM (−3.6%); mirror +3.7% |
| Half-up rounding | 5 | +0.3% to +0.8% |
| Persian Docks, phantom routes | — | no headline change |

Ten biggest movers (mirror headline): Lithuanians Winged Hussar 291.5 → 369.6
(+26.8%), Saxons Halberdier +21.2%, Teutons Halberdier −20.7%, Poles Winged
Hussar +20.1%, Teutons Champion −17.8%, Saxons Champion +17.5%, Khitans Hussar
+15.0%, Saxons Elite Varangian Guard +14.8%, Shu Halberdier +14.4%, Khitans
Heavy Camel Rider +13.2%. On the army-only figure the biggest movers are Wu
(Elite Skirmisher −20.5%, Hussar −20.0%, Halberdier 119.0 → 95.4 −19.8%).
Some head-to-head winners flip, e.g. Danes vs Saxons Champion and Wu vs Shu
Halberdier.

## Gathering rates used (generated)

Credited output per villager-minute; secondary outputs are extra resources from
the same work. Status: estimates (scenario simulations; Khitan food is an online
average).

<!-- rate-table:begin (generated by tools/economy/summarize_runtime.py) -->
| Civilization | Food | Wood | Gold | Stone | Farm wood per food | Secondary output | Modeled mechanics |
|---|---:|---:|---:|---:|---:|---|---|
| Armenians | 23.56 | 30.88 | 29.45 | 23.77 | 0.1600 |  |  |
| Aztecs | 23.72 | 29.13 | 27.62 | 26.00 | 0.1091 |  |  |
| Bengalis | 23.52 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Berbers | 23.66 | 28.64 | 27.36 | 25.97 | 0.1091 |  |  |
| Bohemians | 23.68 | 30.95 | 27.40 | 26.21 | 0.1600 |  |  |
| Britons | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |  |  |
| Bulgarians | 23.52 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Burgundians | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 | food->gold 1.58 | gold per active gathering minute |
| Burmese | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Byzantines | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 |  |  |
| Celts | 23.53 | 31.41 | 27.06 | 25.59 | 0.1600 |  |  |
| Chinese | 23.53 | 30.43 | 27.06 | 25.59 | 0.1455 |  |  |
| Cumans | 23.52 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Danes | 24.71 | 28.24 | 27.06 | 25.59 | 0.1524 |  | extra dropoff credit |
| Dravidians | 23.53 | 30.43 | 23.75 | 22.44 | 0.1600 |  |  |
| Ethiopians | 23.53 | 30.43 | 27.06 | 25.59 | 0.1600 |  |  |
| Franks | 23.54 | 28.24 | 27.06 | 22.44 | 0.1091 |  |  |
| Georgians | 23.72 | 30.09 | 26.13 | 27.96 | 0.1091 |  | worker work rate aura |
| Goths | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |  |  |
| Gurjaras | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Hindustanis | 23.53 | 30.43 | 29.09 | 25.59 | 0.1600 |  |  |
| Huns | 23.53 | 30.43 | 27.06 | 22.44 | 0.1600 |  |  |
| Incas | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Italians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |  |  |
| Japanese | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |  |  |
| Jurchens | 23.54 | 30.43 | 27.06 | 25.59 | 0.1091 |  |  |
| Khitans | 25.20 | 30.43 | 23.75 | 25.59 | 0.1063 |  | pasture online average |
| Khmer | 23.78 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Koreans | 23.56 | 30.43 | 27.06 | 30.14 | 0.1600 |  |  |
| Lithuanians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |  |  |
| Magyars | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Malay | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Malians | 23.54 | 28.24 | 29.76 | 25.59 | 0.1091 |  | extra dropoff credit |
| Mapuche | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Mayans | 23.44 | 31.01 | 23.78 | 25.79 | 0.0949 |  |  |
| Mongols | 23.53 | 28.24 | 27.06 | 25.59 | 0.1600 |  |  |
| Muisca | 23.54 | 30.43 | 27.07 | 25.59 | 0.1091 |  |  |
| Persians | 23.52 | 30.43 | 27.06 | 25.59 | 0.1091 |  |  |
| Poles | 25.71 | 28.24 | 23.75 | 25.59 | 0.1091 | stone->gold 8.53 | coproduct; steady state window |
| Portuguese | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |  |  |
| Romans | 24.73 | 29.44 | 28.14 | 23.72 | 0.1091 |  |  |
| Saracens | 23.53 | 30.43 | 27.06 | 22.44 | 0.1600 |  |  |
| Saxons | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Shu | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 | wood->food 2.13 | coproduct |
| Sicilians | 23.80 | 28.24 | 27.06 | 25.59 | 0.0589 |  |  |
| Slavs | 27.09 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Spanish | 23.57 | 30.43 | 23.75 | 25.59 | 0.1600 |  |  |
| Tatars | 23.54 | 28.24 | 27.06 | 22.44 | 0.1091 |  |  |
| Teutons | 23.52 | 30.43 | 23.75 | 25.59 | 0.0655 |  |  |
| Tupi | 23.56 | 30.43 | 27.06 | 22.44 | 0.1600 |  |  |
| Turks | 23.56 | 30.43 | 32.61 | 22.44 | 0.1600 |  |  |
| Varangians | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 |  |  |
| Vietnamese | 23.54 | 30.43 | 23.75 | 25.59 | 0.1091 | wood->gold 1.95 | gold per active gathering minute |
| Vikings | 23.54 | 30.43 | 27.06 | 22.44 | 0.1091 |  |  |
| Wei | 23.54 | 28.24 | 27.06 | 25.59 | 0.1091 |  |  |
| Wu | 23.56 | 30.43 | 27.06 | 25.59 | 0.1600 |  |  |
<!-- rate-table:end -->

## Assumptions and exclusions

- Post-Imperial, all available upgrades, Imperial research pricing (Chinese −15% on every tech), own civilization/team bonuses only.
- Weights food 1 / wood 1 / gold 1.5 / stone 3 are a scarcity preference, not elapsed time.
- The 60-s window starts with buildings, upgrades and resources ready; construction, rally and research queues are separate.
- Auras fully active without placement or building cost (owner 2026-11-11). Folwark covers 8 of 10 farms.
- Saxon foot soldiers: maximum −20% (four controlled Town Centers/Castles) — an assumption.
- Excluded income: relics, trade (Caravanserai, trade carts/cogs), Feitoria and other trickles, Wei Tuntian, Gurjara livestock in Mills, fishing, combat rewards, one-time grants (Cuman Mercenaries, First Crusade) and the Tupi casualty refund. Lithuanian combat stats elsewhere assume 4 relics (`LITHUANIAN_RELIC_COUNT`); no relic income is counted here.
- Age-ups are outside the headline; discounts are listed in civilization notes.
- Flemish Revolution keeps its unverified variable-cost formula (owner scope exception, 2026-11-11).
- Units slower than 60 s (Traction Trebuchet; Dromon without Shipwright) have no headline by design.

## Rebuild

```sh
pip install -r requirements-economy.txt            # SciPy (offline only)
python -m aoe2x.economy.restore                    # verify + restore army-context.sqlite (146 MiB)
python -m aoe2x.economy.compiler --require-release-ready
python tools/economy/summarize_runtime.py           # regenerate the rate table
pytest -q tests/test_army_economics_*.py && node --test tests/economy/*.test.mjs
```

After changing gathering inputs or simulations: `node tools/economy/run_special_economy.mjs`
(stale scenario hashes make the compiler fail). To re-run the DAT extraction:
`python -m aoe2x.economy.restore --include-sources`, then e.g.
`python tools/economy/build_production_review.py --raw-json data/local/army-economics/scratch/production-review/current-raw-source.json --game-trees data/local/army-economics/scratch/production-review/current-input/dat/CivTechTrees --out <dir>`
and `python tools/economy/build_economy_review.py --production <dir>/production-review.sqlite --output <dir2>`
(re-extraction changes the review DBs, not the committed snapshot). To compare
two runtimes: `python tools/economy/impact_report.py OLD.db NEW.db --csv out.csv`.

Rebuild equivalence (2026-11-12, before any fix): compiled with matchup-timings'
reference DB, the port reproduces `matchup-timings`' `army_context.db` content
exactly except the compiler file hash and the derived `contextVersion`. With this
branch's reference DB the economics are identical; only 136 mechanics hashes and
3 Elephant Archer price-audit rows differ (that DB predates the 188329 70-food price).

## Sources

- Game data: the supplied DAT, SHA-256 `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`, carrying patch 188329 balance changes (exact build unknown); decoded tables are inside the snapshot.
- Reviewed snapshot: `army-context-2026-11-10` from branch `matchup-timings` (829c65bec): `docs/army-economics.md` and `docs/matchup-timings-handoff.md` there describe its construction.
- Independent review: branch `army-economics-review` (4e3ca13de), `docs/army-economics-review/{PRODUCTION,RESEARCH,GATHERING}.md`.
- Online: aoe2techtree.net `data.json`/`strings.json` for update 188329 (fetched 2026-11-12), Age of Empires fandom wiki, community gathering tests cited in `GATHERING.md`.

## Known limits and follow-ups

- **In-game measurements (from GATHERING.md, deferred by the owner):** Danes farming; Poles Folwark (8% vs 10%, extra vs deducted); Khitan pastures with Transhumance; Burgundian Vineyards gold per minute; one generic stone-mining run. Scenario editor, fresh post-Imperial setup, 10 villagers on the `eco-inputs.json` layout, 30 minutes, log banked + carried resources and wood spent every 5 minutes, two runs each; `aoe2x/economy/observations.py` already validates such windows.
- **Chinese Dragon Ship:** needs a combat profile in the reference DB before it can get a row (production data exists: Dock, 17.55 s with Shipwright, 75W 45G).
- **Ordo Cavalry scope:** economics uses non-projectile cavalry (Hussar, Elite Steppe Lancer, Heavy Camel Rider). `data/golden/aoe2_reference_simulation.db` currently gives combat regeneration to the Khitan Heavy Cavalry Archer and Mounted Trebuchet too (matchup-timings had set those to 0) — worth reconciling in the combat data.
- Rounding of exact halves and the Saxon "foot soldier" scope (foot archers?) are not verified in game.
- Not modeled by decision: Cuman Mercenaries, First Crusade, Tupi refund; units over 60 s have no headline (a "one building per unit" fallback is an option).
- **Next owner-led steps:** decide storage for the runtime database (32 MiB, outside `data/golden/`) and integrate it into the API/UI (the deleted `matchup-timings` page is the reference design).
