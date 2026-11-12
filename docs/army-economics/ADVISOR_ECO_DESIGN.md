# Matchup Advisor × army economics: "narrow loss, cheaper to rebuild"

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
