# Phase C2-c — pure flight during a contact break, built and refuted

One rule, one flag, shipped **OFF**. Like C2-a before it the mechanism works
exactly as specified and the prediction fails — but this round the failure is
worth more than the rule was, because it kills the *class* of fix rather than
one member of it, and it does so on a number nobody had measured.

| | |
|---|---|
| **The spec** | C2-a's probe found the break's bearing is 22 % of the vector `moveAwayFromTarget` sums (`\|basis\|` 1.000 against `\|orbit+cohesion\|` 1.249 + `\|avoidance\|` 2.221), and its report forbade rebuilding the rule as a different basis. C-c instead changes the COMPOSITION: while a break is live, movement is the break bearing + COLLISION avoidance only — no orbit, no cohesion, and avoidance restricted to genuinely overlapping pairs instead of the 1.0–1.5× `minDist` social band. |
| **Built** | `C2C.pureFlight` (one flag). **No constant.** Both dropped weights keep their values and keep applying off the break; the avoidance narrowing selects between two bands `calculateAvoidance` already distinguishes (`overlap > 0`). |
| **Is it live?** | Yes, and it does precisely what it says: `\|orbit+cohesion\|` **1.379 → 0.000**, `\|avoidance\|` **1.875 → 1.716**. The basis goes from 22 % of the sum to **37 %**. |
| **Did the heading move?** | **No.** `cos(actual tick step, break bearing)` **0.276 → 0.276** — unchanged to three decimals. Family-median `cosAtt` 0.63 → **0.64** against a tape 0.88. |
| **Did the separation move?** | **Backwards.** Victim radial displacement per reload **0.087 → 0.046** tiles (base 0.050, tape 1.027). Net gap change per reload 0.003 → **0.000** (tape +0.383). |
| **Cost** | Corpus winners **194 → 187 (C-a) → 181 (C-a+C-c)**. `champion__vs__heavy_cav_archer` stays at **1/9**; a SECOND canary family breaks, `hand_cannoneer__vs__heavy_camel` **6/6 → 0/6**. |
| **Verdict** | Shipped OFF. And the Phase-C falsifiable test came back **negative**: the kiter does not leave, the chaser's output does not fall, so C-a is refuted outright rather than blocked. |

---

## 1. What was built

One flag in `apps/website/static/js/engine/constants.js` (`C2C`), the same shape
as `C2A` / `C2B`:

* **C-c `pureFlight`** — on any tick where `contactBreakHitter()` is non-null:
  1. `kiteSteering`'s orbit + cohesion contribution (`steering.x/y`) is **not
     added**. The retreat *basis* is untouched — C2-a already replaced it with
     the hitter radial for the duration of the break, so `steering` is simply
     unread while pure flight holds.
  2. `calculateAvoidance` is evaluated over **imminent-overlap pairs only**
     (`dist < minDist`), dropping the flat `0.5`-per-neighbour social band
     between 1.0× and 1.5× `minDist`.

  Both revert on the tick the break ends — a distance, not a timer.

`calculateAvoidance` gained one optional parameter (`overlapOnly = false`) and
one `continue`. Every other call site, and every flag-off path, evaluates the
identical expression.

**Scope is INHERITED, not re-declared.** The rule is reachable only inside
C2-a's state, which requires a melee hit on a non-siege ranged body. So
ranged-vs-ranged, melee-vs-melee and siege are untouched by exactly the
construction C2-a already proved. Verified over the full corpus at 20 seeds,
sha256 per class of the whole per-seed record:

```
class             base run                          C-a+C-c run                       identical
melee             e704ca2d…13598d12                 e704ca2d…13598d12                 YES
ranged-v-ranged   d455a3f5…cd68b6ba                 d455a3f5…cd68b6ba                 YES
siege             78fd8f47…c2e2b7ec                 78fd8f47…c2e2b7ec                 YES
ranged-v-melee    8ec13bac…89b78af6                 4b10372b…4c3aa3632                no (this is the rule)
```

## 2. The measurement that matters — the social band was never the problem

`tools/simjs/c2a_break_probe.mjs`, extended this round to mirror the new
composition and to report what pure flight dropped. 86 chase fights × 5 seeds,
`--verify-identity` PASS on both runs.

```
                                        C-a            C-a + C-c
kiter unit-ticks with a live break      16.2 %         15.8 %
break episodes                          3547           3983
  median / mean / p90 (s)               2.25/2.84/5.87 1.78/2.40/4.65

term magnitudes on a BREAK tick (mean, pre-normalisation)
  |radial basis|                        1.000          1.000
  |orbit + cohesion|                    1.249          0.000   (dropped 1.379)
  |avoidance|                           2.221          1.716   (full band: 1.875)

basis share of the summed magnitudes    22 %           37 %
cos(pre-smoothing heading, bearing)     0.374          0.396
cos(actual tick step,      bearing)     0.276          0.276
```

Read the avoidance line carefully, because it refutes the premise this round
was built on. C2-a's report described `calculateAvoidance`'s 2.221 as a force
being "used as a social force"; the spec asked for it to be restricted to real
overlaps on the assumption that most of that magnitude was the polite-spacing
band. **It is not.** Narrowing to actual interpenetration removes only
**1.875 → 1.716, i.e. 8.5 %** of the magnitude.

That is a fact about the geometry, not about the code: a kiter with a break
live is by definition inside a melee scrum, packed against its own ball
(compressed by E8's combat pack) with chasers touching it. Nearly everything
within 1.5× `minDist` of it is **already overlapping**, and each such pair
contributes 3–8, not 0.5. The body-repulsion sum is real collision physics and
there is nothing social left to remove.

So the composition after pure flight is `1.000` of bearing against `1.716` of
collision — and the realised heading does not move at all. The pre-smoothing
cosine buys +0.022; the velocity smoothing (`v = 0.3·v + 0.7·dir`) gives it
straight back, exactly as it did in C2-a.

**The kiter cannot beeline because it is physically boxed in, not because it is
badly steered.** No selection or weighting of the steering terms can reach
cos 0.88 here; only a change to how tightly bodies pack, or to how a unit
resolves contact with them, could.

## 3. Emergence table

Median over the 29 melee-swing families of the C1 chase corpus, computed by
`tools/simjs/c1_chaser_cadence.py` off `c1_chase_probe.mjs` dumps, 86 fights ×
20 seeds. "tape" is C1 M2's value.

| quantity | tape | base | C-a | **C-a+C-c** | moved |
|---|---|---|---|---|---|
| post-hit seconds until reach is lost | 0.08 | 0.42 | 0.29 | **0.23** | toward |
| cos(flee, away-from-the-hitter) | 0.88 | 0.61 | 0.63 | **0.64** | toward, by 0.01 |
| cos(flee, away-from-enemy-centroid) | 0.78 | 0.67 | 0.39 | **0.71** | **recovered** |
| victim radial displacement / reload (tiles) | 1.03 | 0.05 | 0.09 | **0.05** | **away** |
| net change in separation / reload (tiles) | +0.383 | 0.000 | 0.003 | **0.000** | **away** |
| windows that lose reach | 100.0 % | 57.0 % | 57.9 % | **55.3 %** | **away** |
| chaser hits on a STOPPED victim | 9.9 % | 55.2 % | 42.4 % | **42.6 %** | flat |
| kiter stopped duty cycle | 0.319 | 0.467 | 0.462 | **0.469** | **away** |
| kiter median move-run (s) | 1.38 | 0.70 | 0.40 | **0.40** | **away** |
| chaser cycles that lose contact | 97.2 % | 54.1 % | 51.1 % | **51.9 %** | **away** |
| chaser seconds IN REACH per cycle | 0.66 | 1.81 | 1.90 | **1.79** | toward, by 0.11 |
| chaser landed hits / chaser-alive-second | 0.0964 | 0.1602 | 0.1678 | **0.1719** | **away** |

Foot-shooter run lengths, the second C1 M2 defect the spec hoped this would
touch (median move-run, seconds, families where the kiter is that unit):

| kiter | tape | base | C-a | C-a+C-c |
|---|---|---|---|---|
| hand_cannoneer | 3.35 | 0.40 | 0.30 | **0.30** |
| imp_elite_skirm | 2.71 | 0.30 | 0.30 | **0.30** |
| arbalester | 1.37 | 0.92 | 0.50 | **0.50** |

Unmoved. The 0.3–0.4 s dribble is not a steering-composition defect.

**One quantity genuinely recovered**: alignment with the enemy centroid,
0.39 → 0.71 against a tape 0.78. C2-a's central cost was that swapping E10a's
shared basis for a per-hitter one reinstated MILLING (0.67 → 0.39); dropping
cohesion during the break undoes that, because a unit no longer being dragged
back into its ball ends up pointing roughly where the ball is going anyway. It
buys nothing on the board.

## 4. Does the chaser close anyway? — the answer the spec asked for

Yes, and by more than before. Median over the 29 melee-swing families, per
chaser reload window following a landed hit:

| quantity | tape | base | C-a | **C-a+C-c** |
|---|---|---|---|---|
| victim radial displacement (tiles) | 1.027 | 0.050 | 0.087 | **0.046** |
| CHASER radial displacement (tiles) | 0.734 | 0.055 | 0.081 | **0.065** |
| net change in separation (tiles) | +0.383 | 0.000 | +0.003 | **0.000** |
| victim total displacement (tiles) | 1.288 | 0.465 | 0.362 | **0.353** |
| chaser total displacement (tiles) | 0.865 | 0.187 | 0.232 | **0.187** |
| chaser landed hits / chaser-alive-s | 0.0964 | 0.1602 | 0.1678 | **0.1719** |

The kiter moves LESS in total (0.465 → 0.353 tiles per window) and converts
none of it into radial distance. Under pure flight the victim opens 0.046 tiles
while the chaser closes 0.065, and the net gap change is zero to three
decimals. **The break approach does not fail because the kiter is steered
wrong; it fails because at contact range in this engine neither party can move
relative to the other at all.**

## 5. The boards

Full corpus, 216 scoreable fights × 20 seeds, tapebox, all other flags at
shipped defaults (P1/P2 OFF).

```
class                 n     base      C-a  C-a+C-c
ranged-v-ranged       3        3        3        3     (byte-identical)
ranged-v-melee       78       73       66       60
melee                99       83       83       83     (byte-identical)
siege                36       35       35       35     (byte-identical)
TOTAL               216      194      187      181
mean per-seed agr          0.8981   0.8574   0.8486
```

(The class split above is computed from `attack_range`/`min_attack_range` in
`combat_dicts.json`, which sorts the Fire Lancer as ranged; earlier rounds'
tables used a different split. The totals and the per-family rows are the
comparable numbers.)

Per-family winner changes, base → C-a → C-a+C-c: **exactly two families**.

```
champion__vs__heavy_cav_archer     8/9 -> 1/9 -> 1/9    (C-a's loss, unrecovered)
hand_cannoneer__vs__heavy_camel    6/6 -> 6/6 -> 0/6    (NEW, C-c's own)
```

Canaries:

```
canary family                            base      C-a  C-a+C-c
champion__vs__arbalester                  6/6      6/6      6/6
hand_cannoneer__vs__heavy_camel           6/6      6/6      0/6   <---
heavy_cav_archer__vs__elite_steppe        6/6      6/6      6/6
champion__vs__heavy_cav_archer            8/9      1/9      1/9   <---
```

### 5a. `champion__vs__heavy_cav_archer` — the falsifiable Phase-C test, failed

C1 M5's ledger, recomputed for each configuration (9 recordings × 20 seeds =
180 runs). The tape's winner here is the **kiter**: the HCA takes 8 of 9.

| | tape | base | C-a | **C-a+C-c** |
|---|---|---|---|---|
| winner = chaser (champions) | 1/9 | 0/180 | 180/180 | **180/180** |
| agrees with tape | — | 88.9 % | 11.1 % | **11.1 %** |
| chaser damage per run | 603 | 943 | 960 | **960** |
| kiter damage per run | 1456 | 1470 | 878 | **882** |
| kiter launches per run | 267 | 261 | 154 | **153** |
| survivors at 40 s | 32.8 % | 28.6 % | 61.9 % | **71.4 %** |

C1 M5 stated the enable criterion as a number: **champion damage per run must
fall from 943 to ~603 (0.64×)**. Under pure flight it is **960 — it went UP**.
The HCA still loses 41 % of its launches to the retreat and still collects no
separation for them. The family does not recover, and the C1 M5 prediction
("if the kiter now actually LEAVES, the chaser's output falls the tape's way")
is answered: the kiter does not leave, so the chain's premise is refuted rather
than merely blocked.

### 5b. `hand_cannoneer__vs__heavy_camel` — C-c's own casualty, same mechanism

The family C1 M6 named as P1's blocker, and a canary since B2. 6 recordings ×
20 seeds:

| | tape | base | C-a | **C-a+C-c** |
|---|---|---|---|---|
| winner = chaser (camels) | 0/6 | 0/120 | 36/120 | **72/120** |
| seed agreement with tape | — | 100 % | 70 % | **40 %** |
| chaser damage per run | 273 | 591 | 630 | **768** |
| kiter shots per run | 227 | 224 | 209 | **197** |

Identical shape to the champion family: the kiter pays 12 % of its shots for
the retreat and the chaser's damage rises 30 %. C1 M6 measured this chaser
already delivering 2.16× the tape's share of the kiter army's HP; pure flight
makes that worse, not better.

## 6. What this licenses

**Established.**

1. Pure flight is implementable with **no new constant**, and with
   ranged-vs-ranged, melee-vs-melee and siege **byte-identical** over the full
   corpus (hashes in §1) — inherited from C2-a's construction, not re-argued.
2. The rule is live and does exactly what it claims: the group terms are gone
   (1.379 → 0.000) and avoidance is narrowed to real overlaps.
3. **`calculateAvoidance`'s magnitude during a break is 91.5 % genuine body
   overlap, not social spacing** (1.875 vs 1.716). This is new, and it retires
   the "avoidance is being used as a social force" reading of C2-a's 2.221.
4. **A kiter's realised retreat heading is not reachable by term selection.**
   With the basis raised from 22 % to 37 % of the sum, the realised cosine is
   unchanged to three decimals (0.276). Combined with C2-a's finding that no
   *choice* of basis moves it either, the whole steering-composition family is
   closed: bearing rules, basis rules and term-selection rules all move the
   realised cosine by ≈0.02.
5. **The break approach itself is refuted, not blocked.** The Phase-C chain
   predicted that a kiter which actually leaves would drop the chaser's output
   toward the tape's. The kiter's net separation per reload is **0.000 tiles**
   under the strongest version of the rule the campaign can build without a
   fitted constant, and the chaser's hits per chaser-second went **up** in both
   families. The counterpart rule named in C2-a §5 (chaser stop-to-swing) was
   already measured in C2-b and shipped OFF; with both halves built and both
   negative, there is no remaining member of this family to gate.
6. The residual defect is **relative motion at contact**, not steering: over a
   full reload window at contact range the victim moves 0.35 tiles total and
   opens 0.05 of them, against a tape 1.29 / 1.03. Whatever produces the tape's
   1.03 tiles is upstream of every rule Phase C has written.

**Not established, and deliberately not attempted.**

- Whether relaxing the velocity smoothing (`0.3`) would let a bearing bite. It
  is a fitted constant shared with every other movement path in the engine, and
  changing it is a global re-tune, not a break rule.
- Whether the packing itself (E8's combat pack, `minDist`, `resolveCollisions`)
  is what caps radial displacement at ~0.05 tiles per reload. §2 and §4 point
  straight at it and this round did not test it. It is the obvious next
  measurement and it is **not** a steering question.
- Anything about P1/P2. Neither was enabled in any run here.

## 7. Reproducing

```bash
# the corpus is DERIVED, not listed
PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --print-tags > tags.txt

# boards
node tools/simjs/calib_runner.mjs --seeds 20 --out-dir <base>
node tools/simjs/calib_runner.mjs --seeds 20 --out-dir <ca>  \
     --c2a contactBreak,breakPriority
node tools/simjs/calib_runner.mjs --seeds 20 --out-dir <cac> \
     --c2a contactBreak,breakPriority --c2c pureFlight
python -m aoe2x.calibration.score --all --sim-runs-dir <dir> --label <label>

# emergence table
node tools/simjs/c1_chase_probe.mjs --tags-file tags.txt --seeds 20 \
     --c2a contactBreak,breakPriority --c2c pureFlight --out-dir <probe>
PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --section all \
     --seeds 20 --sim-runs-dir <probe> --json out.json

# the term-magnitude diagnosis
node tools/simjs/c2a_break_probe.mjs --tags-file tags.txt --seeds 5 \
     --c2a contactBreak,breakPriority --c2c pureFlight --verify-identity
```

**Off-switch identity.** HEAD with shipped defaults is byte-identical to base
commit `bb2e6fa` over all 216 fights × 20 seeds — sha256 of the full
damage + missile + winner + duration record of every run:

```
base commit bb2e6fa      6b40fba434e1f4513023a4b5a6b0761dab484405560f730f23bcbd80ffe4c41f
HEAD shipped defaults    6b40fba434e1f4513023a4b5a6b0761dab484405560f730f23bcbd80ffe4c41f
```

The **C2A-on** path is unchanged too — HEAD and `bb2e6fa` with
`contactBreak,breakPriority` armed on both engines, same 4320 runs:

```
base commit bb2e6fa      a7592f45654b0d5844bd5a4736f683bf83c2d958aa3707dac6e517bfeb0915ec
HEAD --c2a both on       a7592f45654b0d5844bd5a4736f683bf83c2d958aa3707dac6e517bfeb0915ec
```

`node --test tests/js/engine/` — **313 pass** (290 at base + 23 new).
`node tools/simjs/parity_check.mjs` is red at base and equally red here: it
diverges on `champ-v-jaguar` at **tick 0** on spawn coordinates, i.e. a stale
golden panel — nothing this round can reach.
