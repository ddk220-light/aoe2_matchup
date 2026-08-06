# Standard-units archive — blind gap report (2026-08-06)

Archive: `aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` (SHA-256
`38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`),
339 fights, 122 named matchups over the complete 14-unit grid (91 unique
unordered pairs + swapped-name duplicates). Six units were new to the
engine: Halberdier, Hand Cannoneer, Heavy Camel Rider, Hussar, Imperial
(Elite) Skirmisher (= existing master 6), Siege Onager. **No engine
changes were made for this run** — results are the blind state of the sim.

## Part 1 — independent prediction, verified against every tape

1. **Unit counts: 122/122 predicted exactly.** The generator rule, fully
   recovered from dat base costs: `c = food + wood + 1.5×gold`; the
   cheaper unit gets `n = min(21, floor(3000 / c))`; the budget is
   `n × c`; the other side gets `floor(budget / c_other)`. The 3000
   weighted-resource cap is measured from the data (it binds for camels
   at 20 and every siege pairing); gold ×1.5 beats ×1.0 and ×2.0
   decisively in log-ratio fit (0.051 vs 0.143 / 0.074).
2. **AI-order model: 119/122 command signatures match** the predicted
   category:
   - mobile ranged (arbalester / skirmisher / heavy cav archer / hand
     cannoneer) vs melee → the full kiting script (formation moves +
     beat interacts + melee aiOrder wave), profile beat = the 0.667 s
     clock slot ceiling of the kiter's reload (predicts the hand
     cannoneer's observed 4.0 s beat from its 3.45 s reload);
   - siege ranged (heavy scorpion / siege onager) vs melee → aiOrder
     waves only, both sides native — exactly the svc/svp basics model;
   - ranged vs ranged → a light script (patrol + volley interacts) the
     engine does NOT model; run native and flagged. The 3 signature
     "mismatches" are scorpion rvr fights that are aiOrder-only, i.e.
     they match the native mode they were run in.
3. **Spawn layouts** are recorder-deterministic per (side, unit, count)
   in 78% of keys (96 keys, 21 with a second variant); anchors differ by
   scenario category. Sim runs use the tape's recorded starts.
4. New-unit civs pinned from tape observables (HP, per-hit damage vs
   known-civ opponents, top speed, swing intervals, fire range):
   Halberdier→Bulgarians-class (60 hp, atk 10, 1.1 speed), Hand
   Cannoneer→Bohemians (40 hp, atk 17, speed 1.1, reload 3.45), Heavy
   Camel→Berbers-class (140/11/1.6/2.0), Hussar→Berbers-class
   (95/11/1.65/1.9), Siege Onager→Slavs-class (70/76/0.6/6.0, range 9,
   min range 3). All five exported as dat-locked fixtures.

## Part 2 — sim vs tape (5 sampled acquisition orders per matchup)

| category | n | correct winners | wrong | mean band | median band |
|---|---|---|---|---|---|
| kiting (modeled) | 47 | 45 | 2 | 13.1 | 8.3 |
| native waves (modeled) | 54 | 53 | 1 | 10.3 | 5.7 |
| ranged-vs-ranged (unmodeled script) | 21 | 15 | 6 | 30.2 | 8.9 |
| **total** | **122** | **113 (92.6%)** | **9** | **14.8** | **6.6** |

In the two MODELED categories: **98/101 correct winners (97%)**. Many
matchups have a single tape repeat, so band errors are noisier than the
calibration corpus's five-repeat bands.

### The 9 wrong winners, root-caused

- **5× mobile-ranged vs siege onager / cav-archer mirrors** (all in the
  unmodeled rvr bucket): the tape's script lets the mobile side outrange
  or dance inside the SO's 3-tile minimum range and win; run native the
  SO/HCA side wins instead. Model gap, not stat gap.
- **hand_cannoneer / arbalester vs heavy_cav_archer mirrors** (rvr): same
  unmodeled-script bucket.
- **heavy_cav_archer_vs_champion** (kite, single repeat): counts 12v21 —
  sim has the HCA side winning where the tape's champions ground it out.
- **imp_elite_skirm_vs_heavy_camel** (kite, single repeat): sim
  under-catches with the 1.6-speed camel chaser vs the skirmisher.
- **champion_vs_paladin at 21v9** (native): sim +7 vs tape -19..-35 — a
  marginal flip at a ratio outside the calibrated basics set.

### Largest correct-winner residuals (systematic, engine gaps known)

- **Siege onager vs melee** (native): sim over-favors the SO by 50-72
  points — the sim's min-range retreat keeps 0.6-speed onagers alive far
  longer than the tape, where melee corner and kill them; blast-area
  splash is also unimplemented (only bolt pass-through and trample are).
- **Hand cannoneer as kiter** (vs elephant/steppe/hussar): sim
  over-favors the HC by 30-46 — its dat 75% accuracy is not modeled
  (every sim shot aims true), and its 17-damage volleys land in full.
- Scorpion rvr fights (skirm/SO opponents): unmodeled script bucket.

## Bottom line

The gap is substantially closed for everything the engine models: 97%
correct winners across kiting + native categories on a blind archive
with six never-calibrated units, median band error ~6. The remaining
distance is concentrated in three named mechanics: the ranged-vs-ranged
duel script, siege-onager blast + evasion behavior, and gunpowder
accuracy — all measurable from this archive's raw recordings when we
choose to close them.
