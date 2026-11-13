# Matchup Advisor × army economics: "narrow loss, cheaper to rebuild"

## Revision 4 — scoring model (owner request 2026-11-12)

**Status (2026-11-13): wired into the site on branch `advisor-eco`** (not yet on `staging`).
The live advisor page now runs Revision 4 with the default weights:

- Data: `data/golden/advisor_cell_metrics.json.gz` (1.3 MB; built by
  `tools/economy/advisor_eco/build_advisor_metrics.py` from `cells.csv.gz` + the campaign
  bundle) holds every observed cell's two categories, winner HP and both 60-s investments,
  and every unit's full research package. `/api/advisor-matchups/<civ>` rows carry
  `category_a, category_b, winner_hp, vm_a, vm_b` (advisor component schema 3); inferred
  cells are `pending`, identity/close cells `close`. Rebuild after a re-simulation:
  `docs/architecture/runbooks.md` §9.
- Browser: `apps/web/src/features/advisor/model.mjs` is the JS port (weights and settings in
  `WEIGHTS` / `CONFIG`); `tests/advisor/rev4-parity.test.mjs` checks all 3,080 plans against
  this Python model (main, support, targets, helps, additions, scores, enemy strength:
  0 differences). The page shows each matchup's category, the support's helps with their
  reason, a "cheaper to fully upgrade" mark and badge, a legend and pending marks.
- Rounding: the published winner HP has 4 decimals and investments 2; the Python model on
  those rounded values gives exactly the plans in `advisor-plans-rev4.json.gz`.

Model: `tools/economy/advisor_eco/advisor_model_rev4.py` (the reference). Runner: `impact_rev4.py` (≈ 1 min,
single process). Per-plan output for all 3,080 plans:
`docs/army-economics/advisor-plans-rev4.json.gz` (default weights in full, plus the live
plan, the Revision 3 plan and the main/support under the eco and combat weight sets).
Summary numbers: `advisor-plans-rev4-summary.json`. Categories are the Revision 3 ones
(`classify.py`: HP < 50%, eco ≥ 25%, kite eligibility, dominance needs ≥ 50% HP).

### The scoring in plain language

1. **Category per matchup.** For a plan "civ X against civ Y", every X unit against every Y
   unit gets one category from X's side: Complete dominance, Clear win (kite), Plain win,
   Power win, Eco win (narrow loss but ≥ 25% cheaper), Close, Cheap loss, Plain loss,
   Kited loss, Outclassed loss. Inferred (pending re-simulation) cells count as Plain
   win / Plain loss and are flagged in the output; identity and close cells are Close;
   "Cheap loss (HP unknown)" counts as Cheap loss.
2. **Base score** of a unit = sum of the category weights over the opponent civ's roster.
3. **Opponent strength.** Each Y unit's base score (computed the same way against X's
   roster) is mapped onto 0.5–1.5 across Y's roster: weakest unit 0.5, strongest 1.5,
   linear in between (min-max). All units equal → 1.0.
4. **Advantage score** = sum over the opponent's units of weight × multiplier. For a positive
   weight (wins, eco win) the multiplier is the opponent's strength: beating the strongest
   enemy unit counts 1.5×, beating the weakest 0.5×. For a negative weight (losses) it is
   the mirror, 2 − strength: losing to the enemy's strongest unit counts 0.5×, losing to
   its weakest 1.5× ("credit grows with the opponent's strength, blame with its weakness").
5. **Main unit** = highest advantage score among eligible units, ties broken by base score,
   gold first, name, id. Not eligible: **Scorpion** (16 civ entries: Aztecs, Burgundians,
   Byzantines, Cumans, Hindustanis, Huns, Italians, Khitans, Koreans, Lithuanians, Malians,
   Poles, Portuguese, Saracens, Spanish, Vietnamese) and **Heavy Scorpion** (39 civ entries)
   — 55 advisor units, matched by name. The "prefer a gold main with at least one win" rule
   is kept (see below).
6. **Support targets** = every enemy unit the main loses to (any loss category, eco win
   included) plus every enemy unit the main **struggles** against: a Close result, a
   Power win (main's army ≥ 25% dearer), or any win where the main keeps < 50% HP.
7. **Support candidates** = no-gold units and Scorpion / Heavy Scorpion (never the main).
   A candidate **helps** against a target if
   - its category weight against the target is higher than the main's (e.g. it wins where
     the main loses, dominates where the main only wins, or loses only cheaply where the
     main is outclassed) — help = the weight difference; or
   - both win with the same category weight and the candidate keeps ≥ 15 HP points more,
     or its army is ≥ 25% cheaper (60-s investment) — help = 0.25 (tie bonus).
   Support score = sum over helped targets of opponent strength × help. Highest score wins
   (ties: number of losses turned into wins, then the ranking order). No candidate with a
   positive score → no support.
8. **Additions** (kept): greedy counters, any unit except the main and the support, for the
   main's *real* losses (eco wins need no counter, as in Revision 2) that the support does
   not beat; an addition must win its matchup; ranked by the summed strength of what it
   covers. Struggles get a support but never an addition.

**Gold / no-gold weighting.** Dropped for scoring. The old threat weight
(`weight(b) × (1 + our units b beats)`) is replaced by opponent strength, which already
measures how much an enemy unit hurts our roster, whether it costs gold or not (a
Halberdier that beats our cavalry is a strong enemy). The gold distinction survives in
two places: the main must cost gold (when a gold unit has a win) and the support must be
trash or a Scorpion.

**Gold-main preference: kept.** Without it 40 of 3,080 plans (default weights) would get a
trash main (89 with the eco set): Halberdiers, Elite Skirmishers and Hussars often score
higher because their wins against dearer armies are dominance wins. It is not redundant.

### Weights (one config dict, `WEIGHT_SETS`)

| Category | Default | Eco | Combat | Rationale (default) |
|---|---:|---:|---:|---|
| Complete dominance | +1.5 | +2.0 | +1.0 | win, ≥ 25% cheaper army and ≥ 50% HP left: the best trade |
| Clear win (kite) | +1.5 | +1.5 | +1.0 | the melee unit can never catch it: as good as dominance |
| Plain win | +1.0 | +1.0 | +1.0 | the reference unit: a win at similar cost |
| Power win | +0.6 | +0.3 | +1.0 | a win, but the army cost ≥ 25% more (often Castles): worth less than a plain win |
| Eco win (narrow loss, cheaper) | +0.25 | +0.6 | −0.5 | lost, but traded efficiently: slightly positive |
| Close | 0 | 0 | 0 | coin flip |
| Cheap loss | −0.25 | 0 | −0.5 | lost clearly, but little was spent |
| Plain loss | −0.5 | −0.5 | −0.5 | losses count half a win: a unit is judged mainly by what it beats |
| Kited loss | −0.75 | −0.75 | −0.5 | cannot engage at all |
| Outclassed loss | −0.75 | −1.0 | −0.5 | lost to a cheaper army that kept ≥ 50% HP: the worst trade |

Other settings (`CONFIG`): strength min-max to [0.5, 1.5]; struggle = close, power win, or
win with < 50% HP; help margins 15 HP points / 25% cheaper army, tie bonus 0.25.

### Results (all 1,540 pairs, 3,080 plans)

| | Default | Eco | Combat |
|---|---:|---:|---:|
| main changed vs live / vs Revision 3 | 1,298 / 1,280 | 1,574 / 1,548 | 442 / 490 |
| support changed vs live sidekick / Rev 3 | 1,475 / 1,468 | 1,530 / 1,525 | 1,616 / 1,637 |
| additions changed vs live / Rev 3 | 929 / 836 | 1,170 / 1,081 | 566 / 502 |
| any of main / support / additions changed vs live | 2,081 | 2,293 | 1,777 |
| additions in total (live 968, Rev 3 848) | 951 | 1,201 | 732 |
| unanswered losses in total (live 944) | 769 | 772 | 805 |
| support is trash / Scorpion line / none | 2,187 / 851 / 42 | 2,316 / 721 / 43 | 1,660 / 1,391 / 29 |
| plans with no support target at all | 3 | 3 | 3 |
| main has no loss / no real loss (eco wins allowed) | 517 / 649 | 440 / 578 | 750 / 818 |
| best eligible unit was trash (gold preference applied) | 40 | 89 | 10 |
| best unit overall was a Scorpion (exclusion applied) | 302 | 229 | 313 |
| single-civ (unique) unit as main (live 1,148, Rev 3 1,143) | 532 | 368 | 1,274 |
| main changed vs default weights | — | 361 | 1,113 |

- **Scorpion mains:** 285 plans in the live advisor (296 in Revision 3) had a Heavy Scorpion
  main; all now get another main (Heavy Scorpion → Champion 65, → Paladin 41, → Cavalier 37,
  → Elite Champi Warrior 29, → Legionary 24 …). The live sidekick was never a Scorpion (it
  had to be no-gold); now a Scorpion is the support in 851 plans (28%).
- **Why so many mains change (default):** 753 of the 1,298 changes are live mains whose wins
  are mostly *Power wins* — their 60-second army costs ≥ 25% more, almost always because
  of the Castles needed to train unique units — so they score 0.6 per win instead of 1.0;
  285 are the Scorpion exclusion; 53 are mains with fewer losses; 207 other (category mix,
  opponent strength). The combat set, which ignores cost, changes only 442 mains (285 of
  them Scorpions).
- **Other slow siege as main** (not excluded; question for the owner): Elite Hussite Wagon
  31 plans (live 50), War Chariot 24 (live 22), Elite Organ Gun 2 (live 14), Elite Ballista
  Elephant 0 (live 37), Mounted Trebuchet 0. With the combat set: Hussite Wagon 54,
  Ballista Elephant 39, War Chariot 23, Organ Gun 17. No Mangonel / Onager / Bombard Cannon
  is in the advisor catalog. The catalog's own `line: scorpion` also contains War Chariot,
  Elite Ballista Elephant and Mounted Trebuchet; excluding those too changes 24 more mains.

Main units, top 20:

| # | Live | Revision 3 | Rev 4 default | Rev 4 eco | Rev 4 combat |
|---:|---|---|---|---|---|
| 1 | Cavalier 436 | Cavalier 417 | Champion 466 | Champion 653 | Cavalier 452 |
| 2 | Heavy Scorpion 285 | Heavy Scorpion 296 | Cavalier 465 | Cavalier 415 | Paladin 300 |
| 3 | Paladin 258 | Paladin 251 | Paladin 446 | Paladin 414 | Champion 221 |
| 4 | Elite Battle Elephant 222 | Elite Battle Elephant 223 | Elite Battle Elephant 261 | Elite Battle Elephant 260 | Elite Battle Elephant 220 |
| 5 | Champion 176 | Champion 197 | Elite Steppe Lancer 141 | Elite Steppe Lancer 150 | Elite Elephant Archer 98 |
| 6 | Heavy Camel Rider 121 | Heavy Camel Rider 121 | Heavy Camel Rider 135 | Elite Champi Warrior 138 | Heavy Camel Rider 94 |
| 7 | Elite Elephant Archer 93 | Elite Elephant Archer 95 | Elite Champi Warrior 107 | Heavy Camel Rider 134 | Elite Steppe Lancer 80 |
| 8 | Elite Steppe Lancer 73 | Elite Steppe Lancer 71 | Heavy Hei-Kuang Cavalry 104 | Elite Fire Lancer 98 | Heavy Hei-Kuang Cavalry 69 |
| 9 | Heavy Hei-Kuang Cavalry 66 | Heavy Hei-Kuang Cavalry 66 | Elite Elephant Archer 103 | Elite Elephant Archer 98 | Elite Eagle Warrior 55 |
| 10 | Elite War Elephant 55 | Elite War Elephant 55 | Elite Fire Lancer 81 | Heavy Hei-Kuang Cavalry 93 | Elite War Elephant 55 |
| 11 | Elite Konnik 51 | Elite Konnik 52 | Heavy Cavalry Archer 65 | Heavy Cavalry Archer 77 | Elite Hussite Wagon 54 |
| 12 | Elite Leitis 51 | Elite Leitis 51 | Elite Eagle Warrior 60 | Elite Eagle Warrior 60 | Elite Konnik 52 |
| 13 | Elite Hussite Wagon 50 | Elite Hussite Wagon 50 | Elite Temple Guard 53 | Elite Temple Guard 53 | Elite Leitis 52 |
| 14 | Elite Coustillier 50 | Imperial Camel Rider 50 | Imperial Camel Rider 51 | Savar 52 | Elite Temple Guard 52 |
| 15 | Imperial Camel Rider 50 | Elite Coustillier 49 | Savar 51 | Imperial Camel Rider 50 | Elite Kamayuk 51 |
| 16 | Elite Eagle Warrior 49 | Elite Temple Guard 48 | Grenadier 38 | Legionary 48 | Elite Champi Warrior 51 |
| 17 | Elite Temple Guard 48 | Elite Eagle Warrior 47 | Legionary 38 | Grenadier 39 | Elite Coustillier 50 |
| 18 | Elite Mameluke 47 | Elite Kamayuk 46 | Elite Varangian Guard 35 | Arbalester 32 | Imperial Camel Rider 50 |
| 19 | Elite Kamayuk 45 | Elite Mameluke 46 | Elite Hussite Wagon 31 | Hand Cannoneer 28 | Elite Mameluke 48 |
| 20 | Elite War Wagon 45 | Elite War Wagon 45 | Elite Kamayuk 27 | Elite Varangian Guard 26 | Elite Cataphract 47 |

### Sensitivity (default weights; plans whose main / support change vs the default run)

| Variant | Main | Support | No support | Unique-unit mains |
|---|---:|---:|---:|---:|
| default (min-max 0.5–1.5) | — | — | 42 | 532 |
| strength rank-based 0.5–1.5 | 57 | 88 | 42 | 523 |
| strength min-max 0.75–1.25 | 77 | 134 | 42 | 520 |
| strength min-max 0.25–1.75 | 82 | 138 | 42 | 552 |
| no strength (advantage = base) | 172 | 352 | 43 | 490 |
| no gold-main preference | 40 | 21 | 43 | 526 |
| struggle at HP < 33% / < 66% | 0 | 172 / 113 | 90 / 23 | 532 |
| power win is not a struggle | 0 | 203 | 79 | 532 |
| power win is a struggle only below 75% HP | 0 | 162 | 63 | 532 |
| close is not a struggle | 0 | 117 | 64 | 532 |
| help margin 25 HP points / eco 33% | 0 | 63 / 49 | 53 / 51 | 532 |
| no same-result help (tie bonus 0) | 0 | 366 | 238 | 532 |
| power win weight 0.8 | 373 | 360 | 40 | 809 |
| power win weight 1.0 (= plain win) | 825 | 846 | 22 | 1,148 |
| eco win weight 0 | 79 | 124 | 42 | 535 |
| losses × 2 | 172 | 186 | 42 | 601 |
| categories on army purchase price only (no Castles) | 1,113 | 1,032 | 7 | 1,302 |
| also exclude War Chariot, Ballista Elephant, Mounted Trebuchet | 24 | 7 | 42 | 512 |

Strength normalisation is a second-order choice (rank vs min-max: 57 mains); the
power-win weight and the cost basis are first-order (hundreds of mains).

### Biggest changes vs the live advisor (default weights)

Selection: largest advantage gain of the new main over the old main (both scored with the
default weights), at most one plan per old → new main pair, plus the two largest Scorpion
exclusions and the two earlier questionable cases. "adv" = advantage score. Full text of
every help ("why"), all scores and every main matchup are in `advisor-plans-rev4.json.gz`.

| Civ vs enemy | Main live → Rev 4 (adv) | Rev 3 | eco / combat set | Support live → Rev 4 | Support helps against |
|---|---|---|---|---|---|
| Burgundians vs Italians | Elite Coustillier (6.1) → **Paladin** (10.9) | Paladin | Paladin / Elite Coustillier | Halberdier → Halberdier | Cavalier (struggle) |
| Jurchens vs Vikings | Elite Iron Pagoda (6.8) → **Grenadier** (11.4) | Elite Iron Pagoda | Grenadier / Elite Iron Pagoda | Hussar → Hussar | Heavy Scorpion (struggle); Arbalester (struggle) |
| Khmer vs Turks | Elite Ballista Elephant (7.6) → **Elite Battle Elephant** (12.1) | Elite Ballista Elephant | Elite Battle Elephant / Elite Ballista Elephant | Halberdier → Hussar | Heavy Scorpion (struggle); Skirmisher (struggle) |
| Mayans vs Portuguese | Elite Plumed Archer (2.9) → **Elite Eagle Warrior** (7.3) | Elite Plumed Archer | Elite Eagle Warrior / Elite Eagle Warrior | Halberdier → Halberdier | Cavalier (loss) |
| Khitans vs Italians | Elite Liao Dao (6.1) → **Elite Steppe Lancer** (10.4) | Elite Liao Dao | Elite Steppe Lancer / Elite Steppe Lancer | Elite Skirmisher → Elite Skirmisher | Elite Genoese Crossbowman (loss); Pikeman (struggle) |
| Saracens vs Shu | Elite Mameluke (5.5) → **Champion** (9.8) | Champion | Champion / Elite Mameluke | Elite Skirmisher → Hussar | Arbalester (struggle) |
| Goths vs Shu | Cavalier (5.2) → **Elite Huskarl** (9.4) | Elite Huskarl | Elite Huskarl / Cavalier | Halberdier → Halberdier | Heavy Hei-Kuang Cavalry (loss) |
| Lithuanians vs Mongols | Elite Leitis (6.4) → **Paladin** (10.6) | Elite Leitis | Paladin / Elite Leitis | Halberdier → Halberdier | Heavy Camel Rider (loss); Pikeman (struggle) |
| Portuguese vs Khitans | Elite Organ Gun (3.9) → **Champion** (8.0) | Elite Organ Gun | Champion / Elite Organ Gun | Halberdier → Halberdier | Elite Steppe Lancer (loss); Hussar (struggle); Mounted Trebuchet (struggle) |
| Tatars vs Italians | Elite Keshik (5.7) → **Elite Steppe Lancer** (9.7) | Elite Keshik | Elite Steppe Lancer / Elite Keshik | Elite Skirmisher → Heavy Scorpion | Elite Genoese Crossbowman (loss) |
| Persians vs Vikings | Elite War Elephant (7.2) → **Savar** (11.2) | Elite War Elephant | Savar / Elite War Elephant | Hussar → Heavy Scorpion | Elite Berserk (struggle) |
| Saracens vs Mapuche | Elite Mameluke (4.4) → **Heavy Camel Rider** (8.4) | Elite Mameluke | Heavy Camel Rider / Elite Mameluke | Elite Skirmisher → Elite Skirmisher | Halberdier (loss) |
| Wei vs Saxons | Elite Tiger Cavalry (6.1) → **Heavy Hei-Kuang Cavalry** (9.8) | Elite Tiger Cavalry | Heavy Hei-Kuang Cavalry / Elite Tiger Cavalry | Elite Skirmisher → Elite Skirmisher | Heavy Mounted Crossbowman (struggle); Halberdier (loss) |
| Magyars vs Ethiopians | Elite Magyar Huszar (4.0) → **Heavy Cavalry Archer** (7.7) | Elite Magyar Huszar | Heavy Cavalry Archer / Elite Magyar Huszar | Halberdier → Heavy Scorpion | Heavy Camel Rider (loss); Elite Shotel Warrior (loss) |
| Italians vs Malians | Elite Genoese Crossbowman (4.3) → **Condottiero** (8.0) | Elite Genoese Crossbowman | Condottiero / Elite Genoese Crossbowman | Elite Skirmisher → Hussar | Scorpion (struggle) |
| Mongols vs Georgians | Elite Mangudai (5.9) → **Elite Steppe Lancer** (9.3) | Elite Mangudai | Elite Steppe Lancer / Elite Mangudai | Hussar → Pikeman | Cavalier (struggle) |
| Jurchens vs Britons | Elite Iron Pagoda (6.5) → **Elite Steppe Lancer** (9.9) | Elite Iron Pagoda | Elite Steppe Lancer / Elite Iron Pagoda | Hussar → Elite Skirmisher | Halberdier (struggle) |
| Aztecs vs Byzantines | Elite Jaguar Warrior (6.3) → **Champion** (9.8) | Elite Jaguar Warrior | Champion / Elite Jaguar Warrior | Elite Skirmisher → Elite Skirmisher | Hand Cannoneer (loss) |
| Portuguese vs Saracens | Elite Organ Gun (5.4) → **Cavalier** (8.8) | Elite Organ Gun | Cavalier / Elite Organ Gun | Halberdier → Halberdier | Heavy Camel Rider (loss); Elite Mameluke (loss); Pikeman (struggle) |
| Burmese vs Saracens | Elite Arambai (3.7) → **Elite Battle Elephant** (7.1) | Elite Arambai | Elite Battle Elephant / Elite Arambai | Halberdier → Halberdier | Heavy Camel Rider (loss); Elite Mameluke (loss); Pikeman (struggle) |
| Poles vs Italians | Elite Obuch (5.7) → **Cavalier** (9.0) | Elite Obuch | Cavalier / Elite Obuch | Winged Hussar → Winged Hussar | Cavalier (loss) |
| Celts vs Saracens | Heavy Scorpion (12.7) → **Paladin** (9.6) | Heavy Scorpion | Paladin / Paladin | Halberdier → Heavy Scorpion | Heavy Cavalry Archer (struggle); Elite Mameluke (loss); Heavy Camel Rider (loss); Knight (struggle) |
| Romans vs Danes | Heavy Scorpion (12.6) → **Legionary** (10.3) | Heavy Scorpion | Legionary / Legionary | Light Cavalry → Heavy Scorpion | Elite Varangian Guard (struggle); Champion (struggle); Elite Jomsviking (struggle); Heavy Scorpion (loss); Heavy Mounted Crossbowman (loss); Knight (struggle) |
| Goths vs Tupi | Cavalier (6.4) → **Elite Huskarl** (7.4) | Champion | Elite Huskarl / Cavalier | Elite Skirmisher → Heavy Scorpion | Elite Ibirapema Warrior (loss) |
| Romans vs Berbers | Elite Centurion (6.0) → **Cavalier** (8.1) | Legionary | Legionary / Elite Centurion | Halberdier → Halberdier | Cavalier (loss); Heavy Camel Rider (loss); Elite Camel Archer (struggle); Pikeman (struggle) |

**The two earlier questionable cases**

- **Goths vs Tupi.** Live: Cavalier (+ Elite Skirmisher); Revision 3: Champion (4 wins and
  3 eco-win caveats). Revision 4: **Elite Huskarl** (adv 7.4: 2 dominance, 5 plain wins, 1
  plain loss to Elite Ibirapema Warrior); Cavalier 6.4 second, Champion only 4.75. The
  support is **Heavy Scorpion**: it beats the Ibirapema Warrior (61% HP left) where the
  Huskarl loses. The combat set keeps Cavalier. Revision 4 removes the weak Champion
  pick of Revision 3: a unit with few wins can no longer win just by having no "real" loss.
- **Romans vs Berbers.** Live: Elite Centurion (1 plain win, 10 power wins — its Castles —
  and 1 outclassed loss); Revision 3: Legionary. Revision 4: **Cavalier** (10 plain wins,
  plain losses to Berber Cavalier and Heavy Camel Rider), Legionary close second (7.7 vs
  8.1), Elite Centurion 6.0. Heavy Scorpion would rank first (9.2) but is excluded. The
  support Halberdier covers both losses (Heavy Camel Rider simulated; Cavalier pending
  re-simulation) and two struggles. The eco set picks Legionary, the combat set keeps
  the Centurion.

### Support call-outs (format of the per-plan "helps" text)

1. **Khitans vs Italians** — main Elite Steppe Lancer, support **Elite Skirmisher**:
   - *Elite Genoese Crossbowman* (main loss): Skirmisher Complete dominance, keeps 54% HP,
     army 263 vs 625 VM; Steppe Lancer Cheap loss (winner keeps 77% HP).
   - *Pikeman* (main struggles): both win, Skirmisher keeps 80% HP, Steppe Lancer 34%.
2. **Romans vs Berbers** — main Cavalier, support **Halberdier**: beats Heavy Camel Rider
   (55% HP) and Cavalier (pending) where Cavalier loses; beats Elite Camel Archer with a
   ≥ 25% cheaper army (118 vs 226 VM); beats Pikeman keeping 59% HP where Cavalier keeps 17%.
3. **Celts vs Saracens** — main Paladin (Heavy Scorpion excluded as main), support
   **Heavy Scorpion**: beats Elite Mameluke (35% HP) where Paladin has a cheap loss; beats
   Heavy Camel Rider where Paladin loses (pending); beats Heavy Cavalry Archer keeping 61%
   HP where Paladin keeps 34%; beats Knight keeping 57% where Paladin keeps 42%.

### Odd cases and open questions (each with a recommendation)

1. **Castle cost makes unique units lose the main slot (biggest effect).** Under the 60-s
   investment (owner decision 1) most unique-unit wins are *Power wins*, so with Power win
   at 0.6 the unique unit loses to a generic unit with plain wins: single-civ mains fall
   from 1,148 to 532 (Elite Leitis → Paladin 49 plans, Elite Coustillier → Paladin 47,
   Elite War Elephant → Savar 51, Elite Tiger Cavalry → Heavy Hei-Kuang Cavalry 42…).
   Power win at 0.8 → 809; at 1.0 → 1,148 (but then Ballista Elephants, Hussite Wagons and
   Organ Guns return: 120 slow-siege mains). Scoring the categories on army purchase price
   only gives 1,302 unique mains. *Recommendation:* decide this first. If "Castle units
   are worse value" is intended, keep 0.6; if not, use 0.8, or classify on purchase price
   for the scoring only (badges can keep the 60-s basis).
2. **Weights to discuss.** Default makes a loss worth half a win (so broad winners stay
   ahead) and cost-efficiency worth about half a win. *Recommendation:* agree on three
   numbers first — Power win, Eco win and the loss scale; the rest follows (eco win 0 vs
   0.25 moves 79 mains, losses × 2 moves 172).
3. **Strength normalisation.** Min-max 0.5–1.5 keeps magnitudes (a unit that beats
   everything stands out); rank-based gives almost the same plans (57 mains differ) and is
   robust to one outlier. Narrower or wider ranges move ~80 mains; no multiplier moves 172.
   *Recommendation:* keep min-max 0.5–1.5. Losses use the mirrored multiplier
   (2 − strength); *recommendation:* keep — it is symmetric and bounded.
4. **"Struggles".** Half of the power-win struggles (1,564 of 2,983) have the main at
   ≥ 75% HP (example: Khmer Elite Battle Elephant beats Turkish Skirmishers keeping 97% HP,
   yet the Skirmisher counts as a target because the elephants cost more).
   *Recommendation:* power win counts as a struggle only below 75% HP (162 supports change,
   no-support plans 42 → 63); keep close and "< 50% HP" as struggles.
5. **Scorpions as support: 851 plans (28%).** Heavy Scorpions beat most infantry and many
   cavalry, so they win the support slot often. *Recommendation:* fine if intended; else
   count a Scorpion's help at half value, or allow it only when no trash unit helps.
6. **Other slow siege as main** (not excluded): Elite Hussite Wagon 31, War Chariot 24,
   Elite Organ Gun 2 (default). The catalog `line: scorpion` also holds War Chariot, Elite
   Ballista Elephant and Mounted Trebuchet. *Question for the owner:* exclude War Chariot
   and Hussite Wagon too? (Excluding the three `scorpion`-line extras changes 24 mains.)
7. **No support in 42 plans.** 3 have no target at all (the main wins everything
   comfortably: Bengalis vs Poles, Gurjaras vs Poles, Gurjaras vs Turks). In the other 39 no
   trash unit or Scorpion does better than the main against any target (e.g. Aztecs vs
   Britons, main Champion: targets Heavy Scorpion, Champion, Cavalier, Arbalester, Elite
   Longbowman). *Recommendation:* show "no support
   needed" for the 3, and the best trash unit by advantage without a call-out for the rest.
8. **Pending cells.** 649 support helps (9%) rest on an inferred cell (support or main side);
   they are flagged "[pending re-sim]" in the text. *Recommendation:* rerun after the
   re-simulation lands; no rule change.
9. **Mirror losses.** A main can lose to the enemy's version of the same unit (Romans
   Cavalier vs Berbers Cavalier); the support then answers it like any other loss.

### Reproduce (Revision 4)

```sh
export ADVISOR_ECO_OUT=/path/to/scratch   # holds cells.csv.gz from extract_cells.py
python tools/economy/advisor_eco/impact_rev4.py   # ≈ 1 min; writes impact_rev4.json, changes_rev4*.md and docs/army-economics/advisor-plans-rev4.json.gz
cp $ADVISOR_ECO_OUT/impact_rev4.json docs/army-economics/advisor-plans-rev4-summary.json
```

## Revision 3 — owner decisions 2026-11-12 (later the same day)

- **Kite rule:** only real ranged skirmishers qualify. Siege-class ranged units (War Chariot,
  Scorpions) and short-range units (Elite Mameluke, range 3) never get the clear-win credit
  (`classify.kite_eligible`: not `siege_ranged` and range > 3 tiles). Clear kite wins: 223 → 97 cells.
- **Ranged units that could kite but lost the simulated battle keep the loss** (confirmed).
- **Complete dominance needs a comfortable win:** the winner keeps at least 50% HP. A cheaper winner
  that finishes below 50% (or has no HP record) is a plain win. Dominance: 10,569 → 3,580 cells.
- Thresholds unchanged: winner < 50% HP, cheaper army ≥ 25% cheaper; upgrade badge at ≤ 50%.

| Winner / loser | Cells | Distinct battles |
|---|---:|---:|
| Plain win / Plain loss | 91,062 | 39,185 |
| Power win / Cheap loss | 22,452 | 10,985 |
| Power win / Eco win | 8,663 | 4,920 |
| Complete dominance / Outclassed loss | 3,580 | 2,507 |
| Power win / Cheap loss (HP unknown) | 116 | 22 |
| Clear win (kite) / Kited loss | 97 | 76 |

Recommendation impact (all 1,540 civ pairs, 3,080 plans): 86 plans change their main unit or
sidekick; 64 main units change. Full list: `advisor-plan-changes-rev3.json`
(script `tools/economy/advisor_eco/list_changes_rev3.py`). Per-cell table regenerated in
`advisor-classification.csv.gz`.

## Revision 2 — owner decisions 2026-11-12

**Status, 2026-11-12 (evening):** analysis only, as before. No site code, data
or published output changed. This revision applies the owner's decisions on the
first analysis (kept below, "Revision 1", for history). New scripts in
`tools/economy/advisor_eco/`: `classify.py`, `examples_rev2.py`,
`impact_rev2.py`, `model_rev2.mjs` (scratch copy of the advisor model) and
`dump_js_plans_rev2.mjs`. Browsable export:
`docs/army-economics/advisor-classification.csv.gz` (4.2 MB, one row per decided
cell) and `advisor-classification-summary.json`.

### Decisions applied

1. **Cost basis unchanged:** the whole-army 60-second investment, production
   buildings (Castles) included. Dravidians Elite Elephant Archer vs Italians
   Genoese is treated as correct.
2. **Wider thresholds:** the winner keeps **under 50%** of its starting HP (seed
   mean; lost seeds count 0; one seed is enough) and the cheaper army costs **at
   least 25% less** villager time (`cheaper ≤ 0.75 × dearer`).
3. **Kite rule (new).** For a ranged unit beating a melee unit:
   `effective kite speed = speed × (1 − attack delay / base reload)`
   (`simulation_real.BattleUnit.effective_kite_speed`; base reload =
   1/attack_speed = `reload_seconds`). If it is **greater** than the melee
   unit's movement speed, the cell is a **Clear win (kite)**: no eco override and
   no narrow label. Important context: every 2026 campaign context was simulated
   with `disableKiting` (all 58,678 contexts), so the simulated battles are
   stand-and-fight battles.
   - **Data:** the frozen bundle the campaigns used, `git show
     matchup-runs:aoe2x/matchups/bundles/campaign-2026-185872-188329.json.gz`
     (`bundleHash 201cec0c…`, checked). All 555 advisor units match a variant
     by `civilization|slug`, and their `profileHash` matches. Fields:
     `mechanics.speed_tiles_per_second`, `attack_delay_seconds`,
     `reload_seconds`, `behavior_class`, `attack_range_tiles`, plus `group`.
   - **Ranged vs melee:** the campaigns' own rule (`isRangedClass`,
     `aoe2x/matchups/battle.py`): `behavior_class` ∈ {`mobile_ranged`,
     `siege_ranged`}. For all 555 variants this is the same as range > 1 tile,
     and for all 130,756 simulated cells it reproduces the evidence `family`
     (melee_vs_ranged etc.). Melee units split into Infantry (147 variants) and
     Cavalry (134) by `group`.
   - The live simulator DB gives other values for some of these fields (example:
     Heavy Cavalry Archer attack delay 0.767 s live vs 0.897 s in the bundle;
     Elite Conquistador 0.217 vs 0.404). The bundle values are used.
4. **Categories** (below), from both sides of every cell.
5. **Badge "cheaper to fully upgrade":** own full research package ≤ 50% of the
   opponent's, no minimum gap.
6. **Recommendations:** eco-win losses need no counter (caveat); a unit whose
   only losses are eco wins is a strong contender and replaces the usual main
   only when that main has a real loss; kite clear wins are full wins.

### Category mapping (winner side ↔ loser side)

Checked in this order for every decided cell:

| # | Condition | Winner side | Loser side |
|---|---|---|---|
| 1 | ranged winner, melee loser, winner's kite speed > loser's speed | **Clear win (kite)** | **Kited loss** *(new name)* |
| 2 | winner's army ≥ 25% cheaper | **Complete dominance** | **Outclassed loss** *(new name)* |
| 3 | loser's army ≥ 25% cheaper, winner HP < 50% | **Power win** | **Eco win** |
| 4 | loser's army ≥ 25% cheaper, winner HP ≥ 50% | **Power win** | **Cheap loss** *(added: not in the owner's list)* |
| 5 | loser's army ≥ 25% cheaper, no seed HP record in git | **Power win** | **Cheap loss (HP unknown)** *(added)* |
| 6 | costs within ±25% | **Plain win** | **Plain loss** |
| — | `close_uncertain` / `equivalent`, identity (mirror profile) | Close | Close |
| — | inferred (never simulated) | Pending re-simulation | Pending re-simulation |

Additions to the taxonomy, and why:
- **Cheap loss.** The owner's list defines "power win" for the winner whatever its
  HP, but names the loser's side only when the winner keeps < 50% ("eco win").
  When the winner keeps ≥ 50%, the cheaper army simply loses. That case is
  "Cheap loss", the largest non-plain group.
- **Cheap loss (HP unknown).** 962 decided cells have no seed HP record in git
  (ranking-era seeds; the `matchup-runs` archive has them). Only 116 of them
  need HP (case 5); the other 846 are classified without it.
- **Loser-side names** "Kited loss" and "Outclassed loss" are mine; rename freely.

### Category counts (HP < 50%, eco ≥ 25%)

| Winner / loser | Cells | Share of decided | Simulated contexts | Unit-name pairings |
|---|---:|---:|---:|---:|
| Plain win / Plain loss | 84,072 | 66.7% | 35,105 | 2,417 |
| Power win / Cheap loss | 22,367 | 17.8% | 10,926 | 2,006 |
| Complete dominance / Outclassed loss | 10,569 | 8.4% | 6,874 | 1,698 |
| **Power win / Eco win** | **8,623** | **6.8%** | **4,888** | **1,342** |
| Clear win (kite) / Kited loss | 223 | 0.2% | 168 | 70 |
| Power win / Cheap loss (HP unknown) | 116 | 0.1% | 22 | 21 |
| **decided cells** | **125,970** | | | |
| Close (close_uncertain 4,786 + identity 820) | 5,606 | | | |
| Pending re-simulation (inferred) | 19,647 | | | |
| **all advisor cells** | **151,223** | | | |

"Simulated contexts" are distinct battles (one battle serves every civ pair whose
units have identical mechanics); "unit-name pairings" ignore the civilization.
The 8,623 eco wins are 3,927 with HP < 33% (the old rule's band), 1,567 at
33–40% and 3,129 at 40–50%; 2,458 rest on a single seed, and 580 have at least
one seed at ≥ 50% HP.

### Sensitivity (cells)

| Winner HP below / eco at least | Dominance / Outclassed | **Power / Eco win** | Power / Cheap loss | Power / Cheap (HP unknown) | Plain | Kite |
|---|---:|---:|---:|---:|---:|---:|
| 33% / 25% | 10,569 | 3,933 | 27,057 | 116 | 84,072 | 223 |
| 33% / 33% | 7,498 | 2,906 | 18,345 | 98 | 96,900 | 223 |
| 40% / 25% | 10,569 | 5,500 | 25,490 | 116 | 84,072 | 223 |
| 40% / 33% | 7,498 | 4,192 | 17,059 | 98 | 96,900 | 223 |
| **50% / 25% (current)** | **10,569** | **8,623** | **22,367** | **116** | **84,072** | **223** |
| 50% / 33% | 7,498 | 6,592 | 14,659 | 98 | 96,900 | 223 |

The HP threshold only moves cells between "Eco win" and "Cheap loss"; the eco
threshold moves cells into or out of "Plain". At 33%/33% the count is 2,906
eco wins: the Revision 1 figure (2,943) minus 37 cells that the kite rule now
takes out.

### Kite rule

| | Cells |
|---|---:|
| ranged unit beats melee unit (simulated, decided) | 23,269 |
| — of which the ranged unit can out-kite the melee unit → **Clear win (kite)** | **223** (1.0%) |
| — too slow to kite (rule does not apply) | 23,046 |
| kite cells that would otherwise be Power win / Eco win (eco label removed) | 97 |
| … Power win / Cheap loss | 120 |
| … Plain win / Plain loss | 4 |
| … Complete dominance (ranged winner was also cheaper; now labelled kite) | 2 |
| Kited losers: infantry / cavalry | 215 / 8 (6 Battle Elephants, 1 Paladin, 1 Cavalier) |
| kite clear wins where the winner kept ≥ 50% HP anyway | 123 |

- **Winners:** Elite Mameluke 82, Elite Conquistador 50, War Chariot 44, Elite
  Kipchak 23, Elite Arambai 8, Elite Mangudai 7, Elite Camel Archer 4, Elite
  Genitour 3, Hand Cannoneer 1, Heavy Scorpion 1.
- **Top pairs:** Elite Mameluke > Champion 29, Elite Conquistador > Champion
  28, War Chariot > Champion 24, War Chariot > Two-Handed Swordsman 10, Elite
  Conquistador > Two-Handed Swordsman 10, Elite Kipchak > Pikeman 9, Elite
  Mameluke > Pikeman 9, Elite Mameluke > Halberdier 8.
- **Eco labels removed** most often: Elite Conquistador > Champion 25, Elite
  Kipchak > Pikeman 8, Elite Mameluke > Halberdier 8, War Chariot > Champion 7.
- **Kite speeds** (bundle): Elite Mameluke 1.386, Elite Genitour 1.238, Elite
  Conquistador 1.231, Elite Kipchak 1.196, War Chariot 1.096, Elite Mangudai
  1.003, Elite Arambai 1.001. Every other ranged unit is under 1.0: Heavy
  Cavalry Archer 0.58–0.85, Arbalester ≤ 0.88, Hand Cannoneer ≤ 0.95. Melee
  speeds start at 0.88 (Elite Teutonic Knight, Elite War Elephant), then
  Champion 0.96–1.15, Halberdier 1.00–1.21.
- **Champions vs Conquistadors (owner's example):** of 31 decided Champion ×
  Elite Conquistador cells, **28 are Clear win (kite)** for the Conquistador
  (kite 1.231 > Champion 1.056 or slower). The other 3 (Armenians, Dravidians
  and Vikings Champions) were **won by the Champions** in the no-kite
  simulation. The rule needs the ranged unit to win, so they stay Complete
  dominance for the Champion. There are also 3 close cells and 4 pending cells.
  See odd case 1.

### Examples

VM = weighted villager-minutes of the 60-second army investment (army purchase
alone in brackets). HP is the winner's remaining HP, seed mean (range).

1. **Kite: Aztecs Champion vs Spanish Elite Conquistador.** 19 Conquistadors beat
   27 Champions keeping 12% (3 seeds, 5–21%). VM 673 vs 133 (140 vs 91).
   Without the kite rule this was Power win / Eco win. Now **Clear win (kite) /
   Kited loss**: kite speed 1.23 > 1.06. Conquistador also gets the badge
   (upgrades 118 vs 249 VM).
2. **Kite, odd: Saracens Elite Mameluke vs Aztecs Champion.** 19 Mamelukes beat 27
   Champions keeping 51% (49–53%). VM 798 vs 182 (139 vs 91). Clear win (kite).
   The Mameluke counts as ranged (range 3, `mobile_ranged`) and is the most
   frequent kite winner (82 cells).
3. **Kite, odd: Shu War Chariot vs Bengalis Champion.** 17 War Chariots beat 27
   Champions keeping 90% (1 seed). VM 252 vs 151. Clear win (kite). The War
   Chariot is a `siege_ranged` unit with a 6.5 s reload, so its windup tax is
   small (kite 1.096).
4. **Eco win: Burmese Champion vs Mapuche Heavy Scorpion.** 19 Heavy Scorpions beat
   27 Champions keeping 33% (26–39%). VM 200 vs 144 (130 vs 92). The Champions
   are cheaper on purchase price too. **Power win / Eco win.** In the advisor,
   Champion becomes Burmese main vs Mapuche (it replaces Cavalier, which loses
   to Halberdier).
5. **Eco win, Castle-driven (accepted): Dravidians Elite Elephant Archer vs Italians
   Elite Genoese Crossbowman.** 27 Genoese beat 20 Elephant Archers keeping 14%
   (13–17%). VM 721 vs 396; purchase 108 vs **168**. Power win / Eco win, and
   Elephant Archer becomes Dravidian main vs Italians.
6. **Eco win in the new 40–50% band: Slavs Champion vs Lithuanians Elite Leitis.**
   20 Leitis beat 27 Champions keeping 49% (1 seed). VM 533 vs 158 (128 vs 85).
   Power win / Eco win.
7. **Power win / Cheap loss: Bengalis Heavy Scorpion vs Armenians Halberdier.** 17
   Heavy Scorpions beat 27 Halberdiers keeping 88% (87–89%). VM 172 vs 118
   (113 vs 67). The cheaper Halberdiers are beaten soundly.
8. **Power win, Castle-driven: Armenians Elite Composite Bowman vs Danes Knight.**
   27 Composite Bowmen beat 20 Knights keeping 59% (56–61%). VM 421 vs 200,
   but purchase 92 vs **138**. The winner's "power" label comes from its
   Castles; on purchase price it is the cheaper army.
9. **Dominance: Armenians Halberdier vs Georgians Cavalier.** 27 Halberdiers beat 17
   Cavaliers keeping 46%. VM 166 vs 222 (67 vs 120). Complete dominance /
   Outclassed loss. Halberdier > Cavalier is the most common dominance pair
   (405 cells).
10. **Dominance, odd: Armenians Champion vs Gurjaras Elite Chakram Thrower.** 27
    Champions beat 25 Chakram Throwers keeping **2.5%** (1–4%). VM 213 vs 550
    (92 vs 98). This is a near-draw, yet it is labelled "complete dominance"
    because dominance has no HP condition.
11. **Odd: Vikings Champion vs Spanish Elite Conquistador.** 27 Champions beat 19
    Conquistadors keeping 24% (22–26%). VM 144 vs 673. Complete dominance for
    the Champion, although the Conquistador out-kites it (1.231 > 1.056) and
    in the game would not stand and fight.
12. **Odd: Armenians Halberdier vs Berbers Elite Genitour.** 27 Halberdiers beat 24
    Genitours keeping 53%. VM 118 vs 122. Plain win / Plain loss, although the
    Genitour (kite 1.238) out-runs the Halberdier (1.10).

### Odd cases for the owner to review

1. **Kite-capable ranged units that lose the no-kite battle: 392 cells** (melee
   winner infantry 345, cavalry 47), plus 53 close cells.
   - Top pairs: Halberdier > Elite Genitour 43, Halberdier > Elite
     Conquistador 42, Champion > Elite Kipchak 34, Halberdier > Elite Kipchak
     33, Champion > Elite Genitour 33.
   - The rule as decided needs the ranged unit to win. In the game these ranged
     units would keep retreating too. Champions vs Conquistadors has 3 such
     cells.
   - *Option:* extend the rule to "ranged out-kites melee ⇒ clear win for the
     ranged unit whoever won the simulation". That would also flip these 392
     cells, but it would be a prediction, not a simulated result. A kiting
     re-simulation would answer it properly.
2. **Mameluke and War Chariot as kiters.** Together they are 126 of the 223 kite
   cells.
   - The Mameluke (range 3) is ranged by the campaigns' class rule, and its
     0.2 s windup gives it the highest kite speed (1.386). Its 8 kited cavalry
     cells include a Teutons Paladin and a Vikings Cavalier (speed 1.35, no
     Husbandry).
   - The War Chariot is a `siege_ranged` unit. With a 6.5 s reload its windup
     tax is about 4%.
   - Whether either really kites in play is a game-knowledge call.
3. **Heavy Cavalry Archers never qualify** for the kite rule.
   - Their bundle windup (0.897 s of a 1.8 s cycle) gives a kite speed of
     0.58–0.85, below every Champion. Mongol HCA (faster reload, 1.44 s) gets
     only 0.58, which only the slingers undercut: the formula penalises faster
     firing.
   - This is the formula as decided, but it runs against the usual game
     intuition that cavalry archers kite infantry.
4. **Dominance has no HP condition.** 6,926 of the 10,569 dominance cells have a
   winner under 50% HP, 3,698 under 33% and 380 under 10% (example 10).
   - The mirror rule to "eco win" would be a "narrow win, cheaper army" label.
   - Proposal: keep "Complete dominance" only when the winner keeps ≥ 50%, and
     call the rest "Eco-favoured win".
5. **Castle-driven labels.** These are accepted under decision 1, and listed only
   so the size is known.
   - 2,569 of 8,623 eco wins (30%) have a loser whose army purchase alone is
     *not* cheaper.
   - 4,817 of 31,106 power wins have a winner whose purchase is cheaper than or
     equal to the loser's (example 8).
6. **Threshold edges.**
   - 161 eco wins have a seed-mean HP in [49.5%, 50%). Example: 23 Berbers Hand
     Cannoneers beat 27 Slavs Champions with exactly 50.0% (seeds 46–55%).
   - 2,458 eco wins rest on one seed.
7. **Contender mains can carry several caveats.** With the wider thresholds, 24
   of the 61 swapped mains have 2–4 eco-win losses. Example: Goths vs Poles,
   Champion replaces Cavalier with 4 caveats (Cavalier, Elite Obuch,
   Arbalester, Winged Hussar).
   - In 22 of the 61 swaps the old main's only real losses were to
     Halberdier/Pikeman/Spearman.
   - In 40 of the 61 the old plan needed no addition (the sidekick already
     covered the loss).
   - Paladin → Heavy Scorpion (7 plans, Celts/Teutons) makes a siege unit the
     main.
   - *Option:* require at most one or two eco-win caveats for a contender to
     replace the main.

### "Cheaper to fully upgrade" badge (≤ 50%, no floor)

| Scope | Cells with the badge (either side) | Share |
|---|---:|---:|
| all non-identity cells (incl. close and pending) | 23,399 of 150,403 | 15.6% |
| decided cells | 19,724 of 125,970 | 15.7% |
| — badge on the battle winner / on the loser | 4,513 / 15,211 | |
| sensitivity: ≤ 40% / ≤ 67% (all cells) | 12,236 / 57,574 | 8.1% / 38.3% |

- **Units without a value:** 554 of 555 units have a full package. Flemish Militia
  has none: its Flemish Revolution cost is variable.
- **Effect of dropping the floor:** dropping the old 60-VM floor adds only 249
  cells (23,150 → 23,399). As a badge it appears on about one in six cells,
  mostly on gunpowder and siege units facing cavalry archers and elephants.

### Recommendation impact (1,540 pairs, 3,080 plans)

Rule: `model_rev2.mjs` (a scratch copy of `apps/web/src/features/advisor/model.mjs`;
Python twin `advisor_model.py` variant `eco_lite_main`). **JS vs Python: 0
differences on all 3,080 plans.**

| Plans changed (headline 50% / 25%) | Caveat only ("lite") | **Lite + contender main (decided)** |
|---|---:|---:|
| main unit | 0 | **61** |
| sidekick | 20 | **38** |
| additions (all fewer) | 97 | **118** |
| any of main / sidekick / additions | 100 | **160** (5.2%) |
| additions in total | 968 → 871 | **968 → 850** |
| unanswered threats in total | 944 → 788 | **944 → 783** |
| main shows ≥ 1 eco-win caveat | | 402 |
| plans with a strong contender | | 179 |
| main is a strong contender | | 126 |
| main has no real loss (before → after) | | 776 → 902 |

| Thresholds (HP / eco) | Eco-win cells | Plans changed: lite | **Lite + contender main**: main | sidekick | fewer additions | any | Additions | Main caveat | Contender plans | Main is contender |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 33% / 25% | 3,933 | 55 | 31 | 15 | 64 | 85 | 968 → 904 | 210 | 97 | 72 |
| 33% / 33% | 2,906 | 41 | 26 | 11 | 48 | 66 | 968 → 920 | 176 | 80 | 58 |
| 40% / 25% | 5,500 | 81 | 41 | 23 | 93 | 121 | 968 → 875 | 289 | 126 | 92 |
| 40% / 33% | 4,192 | 59 | 30 | 16 | 67 | 88 | 968 → 901 | 240 | 96 | 68 |
| **50% / 25%** | **8,623** | **100** | **61** | **38** | **118** | **160** | **968 → 850** | **402** | **179** | **126** |
| 50% / 33% | 6,592 | 77 | 35 | 24 | 88 | 111 | 968 → 880 | 326 | 121 | 85 |

- **Main changes**, most frequent:
  - Cavalier → Champion 8;
  - Paladin → Heavy Scorpion 7;
  - Elite Centurion → Legionary 4;
  - Cavalier → Heavy Scorpion 4;
  - Heavy Scorpion → Champion 3;
  - Elite Boyar → Champion 3;
  - then 1–2 each: Jaguar/Eagle Warrior → Champion, Elite Steppe Lancer →
    Grenadier, Champion → Elite Elephant Archer (Dravidians vs Italians),
    Elite Tiger Cavalry → Heavy Hei-Kuang Cavalry.
- **Effect of the kite rule on plans:** without it the same thresholds give 8,720
  eco-win cells and 167 changed plans (64 mains). The kite rule therefore keeps a
  net 7 plans from changing: their counters against Conquistadors, Mamelukes and
  War Chariots stay.

### Reproduce (Revision 2)

```sh
export ADVISOR_ECO_OUT=/tmp/advisor-eco
python tools/economy/advisor_eco/extract_cells.py --jobs 1   # ≈ 10 min single-process; output byte-identical to Revision 1
python tools/economy/advisor_eco/classify.py                 # categories, sensitivity, kite, badge (≈ 15 s; reads the bundle from branch matchup-runs)
python tools/economy/advisor_eco/examples_rev2.py            # per-category tops, odd-case counts, curated examples
python tools/economy/advisor_eco/impact_rev2.py              # plan impact, threshold grid, JS parity of model_rev2.mjs (≈ 1 min)
cp $ADVISOR_ECO_OUT/classification.csv.gz docs/army-economics/advisor-classification.csv.gz
```

CSV columns: `civ_a, unit_a, civ_b, unit_b, count_a, count_b, winner (a/b),
winner_unit, family, hp_avg_pct, hp_min_pct, hp_max_pct, seeds, vm_a, vm_b`
(60-s investment), `army_vm_a, army_vm_b` (purchase only),
`loser_to_winner_vm_ratio, class_a, class_b` (ranged / melee-infantry /
melee-cavalry), `speed_a, speed_b, kite_speed_a, kite_speed_b` (ranged only),
`category_a, category_b, category_without_kite_rule_a/_b, full_upgrade_vm_a/_b,
badge_cheaper_upgrade_a/_b, a_id, b_id, evidence_id`.

---

# Revision 1 (2026-11-12, kept for history)

**Status, 2026-11-12:** analysis and design only. No site code, data or published
output changed. Scripts: `tools/economy/advisor_eco/` (stdlib Python + the
existing `aoe2x.economy`; one small Node harness to check the Python copy of the
advisor model). Inputs: `data/golden/civ_matchups_first_pass.db` (sha256
`bdbbeacf…`) and `data/army_economics/army_context.jsonl.gz` (`contextVersion`
`98755303…`).

## Summary for the owner

- **What the rule finds.** Of the 125,008 simulated, decided unit-vs-unit cells,
  **2,943 (2.4%, 1,845 distinct fights)** meet both conditions: the winner kept
  under 33% of its HP **and** the loser's army costs at least 33% less villager
  time (60-second army investment). Each condition alone is common (22% and
  17% of cells); both together are rare.
- **What drives the cost gap: Castles.** In 91% of the labelled cells more than
  half of the cost gap is **production buildings**, not the army. Most winners
  are Castle units (Throwing Axemen, Janissaries, Kona, Conquistadors, Jaguar
  Warriors…) that need 4–6 Castles to be trained within 60 seconds. On the
  armies' purchase price alone, only 570 of the 2,943 labelled cells (19%) still
  qualify. In several labelled cells the losing army is actually **dearer** to
  buy. Example: 20 Elite Elephant Archers cost 168 villager-minutes against 108
  for 27 Genoese Crossbowmen. They count as "cheaper" only because the Italians
  need 6 Castles. Nobody rebuilds Castles after losing a fight, so the
  headline's wording "cheaper to rebuild" does not match what it measures.
- **Effect on recommendations (all 1,540 civ pairs, 3,080 plans).** With the rule
  as asked (a semi-loss is a caveat, not a threat needing a counter):
  - 40 plans drop a counter unit (968 → 928 additions) and 8 change the
    sidekick. The main unit never changes.
  - 181 main units show a caveat.
  - 84 plans have a **strong contender**: a unit whose only losses are
    semi-losses.
  - If a strong contender also replaces a main unit that still has real
    losses, the main changes in 27 plans (68 plans change in total).
  - The stricter alternative also stops counting the semi-loss as a **win** for
    the winner. That rewrites 390 mains, mostly by demoting Castle units, and
    sometimes gives clearly worse answers. I do not recommend it.
- **Army sizes do not bias the headline rule toward cheap units.** The losing
  unit is the cheaper unit in 59% of labelled cells, the same as in all losses
  (61%). A purchase-price-only rule would be biased: by construction it flags
  only cheap units (100%), because the advisor sizes armies so the dearer unit's
  army always costs more.
- **"Cheaper to fully upgrade" note.** Full research packages range from 25
  (Korean Hand Cannoneer) to 348 villager-minutes. With the proposed threshold
  (one package at most half the other's and at least 60 villager-minutes
  cheaper), the note appears on **15% of all cells**. That is fine for a detail
  panel, but too often to be a headline badge.
- **Coverage.** All 555 advisor units map to an economics profile. Not
  labelled:
  - inferred cells (19,647, never simulated);
  - identity cells (820);
  - close cells (4,786: exactly the cells whose seeds disagree);
  - 962 decided cells whose seed HP records are not in git.
  
  Re-simulation with the `matchup-runs` tooling fills all of these.
- **Recommendation.** Compute the label at backend build time into a small
  committed annotation file. Serve it as an optional 10th element on labelled
  advisor rows (about +1 KB gzipped per civilization). Apply it on the loser's
  side only, and use strong contenders as main only when the usual main has a
  real loss. Before release, decide open question 1: whether "cheaper to
  rebuild" should leave out production buildings (at least Castles).

## Method

**Winner HP.** Every simulated context stores its seeds:

| Seed source in the evidence blob | Contexts |
|---|---:|
| `forecastValidation.seedResults` (`winnerOwner`, `winnerHpFraction`) | 39,112 |
| `mismatchValidation.seedResults` (same fields) | 10,215 |
| `recoveryValidation.measuredRecords` | 36 |
| `sourceRunIds` (first-pass campaign runs) | 9,315 |

- **Seed HP fields.** `winnerHpFraction` is already *remaining HP / starting
  HP* of the seed winner. For `sourceRunIds`, the run records are read with
  `git show` from `origin/simulations/civ-matchups-campaign-2026-10-31`
  (`207c3128`). They carry `unitStartingHp`/`opponentStartingHp` and the
  remaining HP of both sides.
- **Starting HP.** It is taken from the evidence, not derived from counts × unit
  HP. It is stored explicitly in the 8,487 exact-replay results
  (`startingHpByOwner`) and in all 30,612 run records. In all 8,487 replays,
  `winnerHp/startingHp` equals the stored `winnerHpFraction`.
- **Orientation.** Owner 2 is `context.profiles[0]` and owner 3 is
  `context.profiles[1]` (the evidence `outcome` follows the `pairKey` order).
  Checked: the cell outcome equals the seed majority in every decided cell.
- **Losers are wiped out.** In 30,610 of 30,612 run records and 8,487 of 8,487
  replays the loser has 0 HP left, so a seed the cell winner lost counts as 0%
  for it.
- **Unresolved records.** 294 `runs.jsonl:<n>` references (ranking-era seeds,
  about 98 contexts, 962 cells) are not in git. The `matchup-runs` result index
  has them.
- **HP figure.** The cell's figure is the **mean over all its seeds**. Min/max
  are kept for display. Every decided cell is unanimous, so a mean "over won
  seeds only" gives the same 2,943 labels.

**Seeds and the existing close rule (confirmed).**

| Seeds per cell | Cells |
|---|---:|
| 1 | 40,874 |
| 3 | 84,134 |
| 10 | 4,786 |
| none recoverable | 962 |

The 4,786 `close_uncertain` cells are the 10-seed cells; 4,783 have split
winners (3 unanimous ones are close by margin). The advisor model treats
`close_uncertain` and `equivalent` as "close" (`model.mjs` `isClose`). They stay
close and never get the label.

**Army cost.** For every cell, `evaluate_matchup(data, (civA, unitIdA, mode,
count_a), (civB, unitIdB, mode, count_b))` gives each army's headline (weighted
villager-minutes: purchase bill, 60-s production buildings and common research).
The condition is `1 − loser/winner ≥ 0.33`. All 130,756 evaluations succeeded
(no unit over 60 s or with an unresolved cost appears in a simulated cell).

**Unit mapping.** All **555/555** advisor units match exactly one economics
profile by (civilization, display name), except Shu War Chariot, which has two
modes (`focus_fire`, `barrage`). Both give the same headline; `default`-first
order picks `focus_fire`.

18 units have a different price in economics than in the advisor catalog, which
sized the armies. The economics price is the corrected one:
- Saxon −20% (7 units);
- Mayan/Mapuche discounts;
- Elite Kona 55F 34G;
- Korean and Gurjara half-up rounding;
- Elephant Archer 70F;
- Magyar Huszar (catalog 35F 45G, economics 80F 0G).

The advisor armies keep their simulated counts; only the bill uses the economics
price (`check_mapping.py`).

## Results

### Coverage

| Cells | Count |
|---|---:|
| all advisor cells | 151,223 |
| identity (mirror profiles, no fight) | 820 |
| inferred (never simulated; 10,193 contexts) | 19,647 |
| observed (simulated; 58,678 contexts) | 130,756 |
| — close_uncertain (stay close) | 4,786 |
| — decided, no seed HP in git | 962 |
| **evaluated for the label** | **125,008** |

### Distributions and sensitivity

| Winner HP left (seed mean) | Cells | | Loser army cheaper by | Cells |
|---|---:|---|---|---:|
| 0–10% | 2,788 | | loser dearer | 49,508 |
| 10–20% | 8,037 | | 0–10% | 22,487 |
| 20–33% | 17,182 | | 10–25% | 21,806 |
| 33–40% | 10,788 | | 25–33% | 9,741 |
| 40–50% | 17,639 | | 33–50% | 5,045 |
| 50–75% | 39,183 | | ≥ 50% | 16,421 |
| 75–100% | 29,321 | | | |

| Rule | Cells | Share | Contexts |
|---|---:|---:|---:|
| winner HP < 33% (any cost) | 28,007 | 22.4% | |
| loser army ≥ 33% cheaper (any HP) | 21,466 | 17.2% | |
| **both: narrow loss, cheaper to rebuild** | **2,943** | **2.4%** | **1,845** |
| near miss: HP 33–40%, cost ≥ 33% | 1,315 | 1.1% | 856 |
| near miss: HP < 33%, cost 25–33% | 1,028 | 0.8% | 431 |

Moving either threshold by a few points changes the count by about 40%. The
rule is sensitive, but not unstable.

### What creates the cost gap

| Cost test (HP < 33% unchanged) | Label cells |
|---|---:|
| headline: purchase + 60-s buildings + common research (owner's rule) | 2,943 |
| purchase + buildings, without common research | 3,375 |
| purchase bill only (what is re-bought after a fight) | 2,188 |
| headline labels that also pass on purchase bill only | 570 (19%) |
| headline labels where > half the gap is production buildings | 2,683 (91%) |
| winner's buildings share of its headline, median in label cells | 74% |

| Buildings to train within 60 s (winner / loser) | Label cells |
|---|---:|
| 4 Castles / 9 Barracks | 206 |
| 5 Castles / 9 Barracks | 183 |
| 4 Castles / 14 Archery Ranges | 118 |
| 5 Castles / 10 Siege Workshops | 87 |
| 5 Castles / 14 Archery Ranges | 87 |
| 6 Castles / 9 Barracks | 77 |

A Castle is 650 stone, weighted ×3, so each one adds about 75 villager-minutes.

### By unit class and civilization

| Loser → winner (trash = no gold) | Decided cells | Labels | Rate | Share of labels |
|---|---:|---:|---:|---:|
| gold → gold | 63,211 | 2,233 | 3.5% | 75.9% |
| trash → gold | 37,513 | 706 | 1.9% | 24.0% |
| trash → trash | 9,374 | 2 | 0.0% | 0.1% |
| gold → trash | 14,910 | 2 | 0.0% | 0.1% |

- **By unit group:** Ranged→Ranged 965 (3.2%), Ranged→Infantry 414,
  Infantry→Cavalry 347 (5.3%, the highest rate), Infantry→Ranged 346.
- **Most frequent losers:** Heavy Scorpion 408, Halberdier 304, Champion 302,
  Arbalester 256, Elite Skirmisher 213, Heavy Cavalry Archer 212, Cavalier 197.
- **Most frequent winners:** Elite Throwing Axeman 101, Elite Janissary 98,
  Elite Kona 93, Scorpion 87, Elite Conquistador 86, Elite Arambai 79.

As the cheaper loser, rates per civilization range from Magyars 4.0%, Goths
3.9% and Saxons 3.3% down to Mapuche 1.5%. Khitans (125) and Mapuche (94) are the
most frequent winners.

### Army-sizing bias

The advisor sizes armies with "27-geometric-cost": the cheaper unit gets 27 and
the dearer unit 27·√(cheap/dear). So the dearer unit's army always costs more in
resources, by √(cost ratio). The page says "army sizes adjusted so both sides
cost the same"; that is only approximately true.

| Measure | Value |
|---|---:|
| label cells where the loser is the cheaper unit (per-unit weighted cost) | 1,740 (59.1%) |
| baseline, all decided cells | 76,090 (60.9%) |
| winner/loser unit-cost ratio in label cells (min / median / max) | 0.23 / 1.13 / 7.58 |
| purchase-only variant: loser is the cheaper unit | 2,188 of 2,188 (100%) |

Under the owner's headline rule, the label is **not** skewed toward cheap units:
Castles dominate it instead. Under a purchase-only rule the label is "a cheap
unit that narrowly loses to a unit at least about 2.2× its price" (√2.2 ≈ 1/0.67).

### Recommendation impact (1,540 pairs × 2 sides = 3,080 plans)

`advisor_model.py` is a Python copy of `model.mjs`. `check_js_parity.py` runs
the real module under Node for all 1,540 pairs and finds **0 differences**.

The variants differ in two ways:
- **"Lite"** changes the loser only: the semi-loss leaves its losses (no counter
  needed) and is shown as a caveat. The winner keeps the row as a win.
- **"Symmetric"** also removes it from the winner's wins and from its threat
  weight.

"+ contender main" means that if the usual main still has a real loss, the
best-ranked gold strong contender becomes main.

| Plans changed (of 3,080) | Lite | **Lite + contender main** | Symmetric | Symmetric + contender main | Lite, purchase-only cost |
|---|---:|---:|---:|---:|---:|
| main unit | 0 | **27** | 390 | 409 | 2 |
| sidekick | 8 | **11** | 207 | 210 | 2 |
| additions | 40 (all fewer) | **49 (all fewer)** | 273 (92 fewer, 88 more) | 279 | 9 |
| any of main/sidekick/additions | 42 | **68** | 568 | 586 | 11 |
| total additions | 968 → 928 | **968 → 919** | 968 → 967 | 968 → 961 | 968 → 959 |
| main shows a semi-loss caveat | 181 | 181 | 197 | — | 28 |
| plans with a strong contender | 84 | 84 | 84 | 84 | 11 |
| main is a strong contender | — | 60 | 42 | — | 9 |

The symmetric variant's 390 main changes are mostly Castle units losing their
narrow wins: Elite Cataphract → Paladin (22 plans), Elite Tiger Cavalry →
Heavy Hei-Kuang Cavalry (19), Elite Coustillier → Paladin (17), Elite Ballista
Elephant → Elite Battle Elephant (17). It turns a cost artefact into a
different army, so I do not recommend it.

### Examples (rule as asked; "lite + contender main")

All figures use the advisor's simulated army sizes. "VM" is weighted
villager-minutes: the 60-s investment, with the purchase bill alone in
brackets.

1. **Aztecs vs Spanish — counter no longer needed.**
   - Main Champion, sidekick Elite Skirmisher. Before, Pikeman was added
     against Elite Conquistador.
   - Fight: 19 Elite Conquistadors beat 27 Champions keeping only 12% HP (3
     seeds, 5–21%).
   - Cost: the Champions cost 133 VM against 673 (purchase 91 vs 140). That is
     80% cheaper, and still cheaper without buildings.
   - After: no addition, and the caveat "narrow loss, cheaper to rebuild". This
     is the case the rule is meant for.
2. **Berbers vs Malians — counter dropped on a Castle-driven gap.**
   - Main Heavy Camel Rider; before, Cavalier was added against Elite Gbeto.
   - Fight: 27 Gbetos beat 27 Heavy Camel Riders keeping 24% HP.
   - Cost: 204 vs 674 VM, 70% cheaper, but purchase 126 vs 117: the camels cost
     slightly more to buy.
   - After: Cavalier dropped. Defensible as a trade, but "cheaper to rebuild"
     overstates it.
3. **Jurchens vs Romans — Grenadier becomes a strong contender and main.**
   - Before: main Elite Iron Pagoda, which loses to Elite Centurion.
   - Grenadier beats 8 Roman units and loses only narrowly to the ninth: 22
     Elite Centurions beat 27 Grenadiers keeping 9% HP (3 seeds, 8–10%).
   - Cost: 195 vs 666 VM (Centurions need 6 Castles); purchase 143 vs 173.
   - After: Grenadier is main.
4. **Aztecs vs Mapuche — Champion becomes main, Eagle Warrior is dropped.**
   - Before: main Elite Eagle Warrior, plus Champion as an addition against
     Elite Champi Warrior.
   - Champion beats 7 units and loses only narrowly to 19 Heavy Scorpions,
     which keep 33% HP (32.9% mean; seeds 26–38%).
   - Cost: 133 vs 200 VM (purchase 91 vs 129).
   - After: main Champion, no additions. It sits right on the HP threshold, so
     a near miss in the other direction.
5. **Byzantines vs Aztecs — contender flagged, main kept.**
   - Elite Cataphract stays main (no losses).
   - Paladin is flagged as a strong contender: it beats 6 of 7 units, and 27
     Elite Jaguar Warriors beat 22 Paladins keeping 20% HP.
   - Cost: 239 vs 442 VM, but purchase 152 vs 118. The gap is the Aztecs' 4
     Castles.
6. **Dravidians vs Italians — arguably a bad answer.**
   - Before: main Champion, which loses to Hand Cannoneer, Elite Skirmisher as
     sidekick.
   - After: main **Elite Elephant Archer**, a "strong contender". 20 Elite
     Elephant Archers lose to 27 Elite Genoese Crossbowmen, which keep 14% HP.
   - Cost: 396 vs 721 VM, yet purchase **168 vs 108**. The elephant army costs
     55% *more* to replace; the whole gap is the Genoese's 6 Castles (457 VM).
   - Huns vs Italians (Elite Tarkan → Paladin) is the same pattern. Open
     question 1 fixes both.
7. **Byzantines vs Armenians — why not the symmetric variant.**
   - Before: Elite Cataphract with no losses.
   - The symmetric rule discounts its narrow wins and makes Paladin main.
     Paladin loses outright to Champion and Halberdier and needs Elite
     Cataphract as a counter.
   - A flawless main is replaced by a weaker one.

### "Cheaper to fully upgrade" (note only)

This is unit-level, so it also applies to inferred cells. Flemish Militia has no
fixed full cost: its Flemish Revolution cost is variable and unvalidated.

| Threshold (cheaper package vs dearer) | Cells | Share of 150,679 |
|---|---:|---:|
| ≤ 80% and ≥ 20 VM cheaper | 93,432 | 62.0% |
| ≤ 67% and ≥ 20 VM cheaper | 57,601 | 38.2% |
| ≤ 50% and ≥ 40 VM cheaper | 23,406 | 15.5% |
| **≤ 50% and ≥ 60 VM cheaper (proposed)** | **23,150** | **15.4%** |
| ≤ 40% and ≥ 60 VM cheaper | 12,220 | 8.1% |

Full packages, weighted VM: min 25, quartiles 132 / 163 / 203, max 348.
- Cheapest: Korean Hand Cannoneer 25, Italian Heavy Scorpion 36.
- Dearest: Gurjara Elite Elephant Archer 348, Khmer Elite Ballista Elephant 339.

The note mostly separates gunpowder/siege units (few upgrades) from cavalry
archers and elephants.

## Design

### Where it is computed

| Option | For | Against |
|---|---|---|
| A. Reuse `cells.flags` / `tier` in the advisor DB | No schema change; the site already ignores both | `matchup-runs` `build-db` already uses `flags` bit 4 ("not re-simulated"). The label depends on economics, so every economy change would rewrite the 99 MB advisor DB in `data/golden`, which the simulator/engine versions hash. The two components' versions become coupled. |
| B. Compute in the advisor API service at request/export time | Always current | The packaged backend has only `aoe2x/economy/artefact.py`, not `matchup.py`/`accounting.py`. 9,315 contexts need seed records from git history, which is unavailable in the Vercel/CI checkout. |
| **C. Offline tool → committed annotation artefact; the advisor service attaches it (recommended)** | Same pattern as the economy runtime (compiled offline, committed, served from the packaged runtime); small; deterministic; the advisor DB is untouched | One more input in the advisor component; it must be rebuilt when either input changes (a freshness test catches it) |
| D. Separate data component with its own `/data/<version>/` files | Fully separate versions | A second fetch per civilization for about 1 KB of data; more loader code |

**Recommended (C):**

1. `tools/economy/advisor_eco/build_annotations.py` (to be written from
   `extract_cells.py`) reads:
   - the advisor DB;
   - seed HP from the evidence and, for now, the campaign run records in git;
   - the economy artefact.
   
   It writes `data/army_economics/advisor_annotations.json.gz` (outside
   `data/golden`, added to `backend_sources`). Only cells with HP < 33% need an
   economics evaluation (28,007, about 2 minutes single-threaded).
2. The `advisor_matchups` service appends an optional **10th element** to a
   labelled row: `[hpPermille, vmOwn, vmOpp, code]`, oriented to the requesting
   civilization. The values are `code 1` = narrow loss, cheaper to rebuild, and
   `code 2` = narrow win, dearer to rebuild. Unlabelled rows stay 9 elements
   long.

   Size, measured on Armenians and Chinese:
   - labelled rows only: 33.1 → 34.4 KB gzipped per civilization;
   - numbers on every decided row (for a detail panel): 62–66 KB, +88%.

   I recommend labelled rows only.
3. `advisor_catalog()` gains:
   - per-unit `fullResearchVM` (555 numbers) for the upgrade note, computed in
     the browser with the fixed thresholds;
   - a `dataset.economyAnnotations` block: rule id `narrow-loss-cheaper-rebuild/v1`,
     thresholds, cost basis, economy `contextVersion`, advisor DB sha256, HP
     source, counts.

### Data shape of the artefact

```json
{"format": "aoe2matchup.advisor-eco", "formatVersion": 1,
 "rule": {"id": "narrow-loss-cheaper-rebuild/v1", "hpBelow": 0.33, "savingAtLeast": 0.33,
          "cost": "headline", "hp": "mean over seeds, lost seeds = 0"},
 "advisorDatasetSha256": "bdbbeacf…", "economyContextVersion": "98755303…",
 "units": {"<advisor id>": {"fullResearchVM": 147.7}},
 "cells": [[a, b, hpPermille, hpMinPermille, hpMaxPermille, seeds, vmA, vmB, code]]}
```

`a` and `b` are in the DB's cell order, and `code` is set from the loser's side.

### Versioning

- **Component versions.** The advisor component version is the hash of its
  files, so it moves when the annotations change. The economy component is
  unaffected.
- **Freshness tests.**
  - The advisor service refuses to serve annotations whose
    `advisorDatasetSha256` or `economyContextVersion` does not match the
    packaged DB and artefact.
  - The test suite asserts both. Any economy rebuild then forces a rebuild of
    the annotations in the same commit, like the parity fixture.
- **Rule changes.** A threshold or rule change bumps `rule.id`.

### Inferred cells, after re-simulation

1. Re-simulate the inferred contexts with `aoe2x/matchups` (`run`). Steps 1–3
   are verified.
2. `build-db` (unverified draft) writes compact evidence that keeps per-seed
   `[seed, winnerOwner, ticks, unit/opponent remaining HP, survivors, starting HP]`.
3. Point `build_annotations.py` at the new DB. It then needs no git-history
   reads, and the 962 cells without a recoverable HP record are filled as well
   (the 2026 result index has their 294 seeds).
4. Cells carried over unsimulated (`flags & 4`) stay unlabelled.

### Model change (browser, `model.mjs`)

- **Grouping.** `group()` puts a row with annotation code 1 into a new
  `semiLosses` list instead of `losses`. Code-2 rows stay in `wins` ("lite").
- **Contender.** `entry.contender = !losses.length && semiLosses.length > 0`.
- **Main choice.** After the usual main is chosen, if it still has losses and a
  gold contender with wins exists, the best-ranked one becomes main.
- **Unchanged.** Sidekick and additions still cover `main.losses` only, so no
  counter is assigned for a semi-loss.

`advisor_model.py` is a working reference (variant `eco_lite_main`).

### Tests

- **Python rule.** Boundaries: HP 0.33 is not labelled; saving 0.33 is labelled.
  Close, inferred and identity cells are never labelled. Orientation follows
  `pairKey` vs `context.profiles`. Shu War Chariot modes give equal results.
- **Freshness.** The artefact hashes match the DB and economy, and a 200-cell
  sample is recomputed exactly.
- **API and export.** A labelled row has 10 elements and the static file equals
  the API. Update `projections.json` `$defs/advisor` for the optional element.
- **JS model.** With no annotations the output is unchanged (existing tests).
  A semi row is not in `losses` and gets no counter. The contender flag and
  main switch are covered. A Python-vs-JS fixture over all 1,540 pairs, as in
  `check_js_parity.py`, confirms the result.

### What the UI would show

| Where | Text |
|---|---|
| Unit card line (amber, after "Loses to") | **Narrow loss, cheaper to rebuild** |
| Icon tooltip, loser side | "{Winner} wins but keeps only {hp}% of its army's HP. Your {n} {unit} take {x}% less villager time to field again ({a} vs {b} villager-minutes, including production buildings and shared upgrades)." |
| Winner side (enemy plan) | **Narrow win, dearer to rebuild** — "{Unit} wins with {hp}% HP left, but its army takes {x}% more villager time to field." |
| Badge on a unit card | **Strong contender** — "Beats everything here except narrow losses where it is cheaper to rebuild." |
| Detail panel, note only | "{Unit} is much cheaper to fully upgrade ({a} vs {b} villager-minutes of research). Not part of the verdict." |
| Footnote | "Villager time is an estimate (simulated gathering rates, post-Imperial, weights food 1 / wood 1 / gold 1.5 / stone 3)." |

## Open questions for the owner

1. **Should "cheaper to rebuild" leave out production buildings?** 91% of the
   labels come from Castles or other buildings, which are not rebuilt after a
   fight. In examples 2, 5 and 6 the "cheaper" army costs more to buy.
   - *Recommendation:* compare **purchase bill only** ("cheaper to replace").
     That gives 2,188 labels and changes 11 plans. Alternatively keep the
     headline but drop Castle routes from the comparison.
   - Note: purchase-only flags only cheap units (by the army sizing), which is
     what "cheaper to replace" means.
2. **Should the winner's narrow win still count as a win?**
   - *Recommendation:* yes ("lite"). Discounting it too rewrites 390 main units
     and gives worse answers (example 7).
3. **Should a strong contender replace the main unit?**
   - *Recommendation:* only when the usual main still has a real loss: 27
     plans; the flag alone otherwise. Never replace a main with no losses.
4. **Are single-seed cells (40,874) good enough for the 33% HP test?** The
   sampling policy ran one seed only when the result was decisive and agreed
   with the forecast.
   - *Recommendation:* accept them. Show the seed count and HP range in the
     tooltip.
5. **Upgrade note threshold.**
   - *Recommendation:* at most 50% of the other package and at least 60
     villager-minutes cheaper, in the detail panel only. That applies to 15% of
     cells, too often for a badge.

## Reproduce

```sh
export ADVISOR_ECO_OUT=/tmp/advisor-eco          # outputs (cells.csv.gz ≈ 6.5 MB) stay out of git
python tools/economy/advisor_eco/extract_cells.py --jobs 4   # ≈ 3 min; needs origin/simulations/civ-matchups-campaign-2026-10-31
python tools/economy/advisor_eco/report.py                   # tables above (report.md, report_summary.json)
python tools/economy/advisor_eco/check_js_parity.py          # Python model == model.mjs for 1,540 pairs
python tools/economy/advisor_eco/impact.py [--cost purchase] # plan changes + examples (impact*.json)
python tools/economy/advisor_eco/check_mapping.py            # advisor -> economics unit mapping
```
