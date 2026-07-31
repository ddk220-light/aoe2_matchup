# Phase C2-a — the kiter's contact break, built and refuted

One mechanism, two flags, shipped **OFF**. This document records what was
built, what it did, and — the part worth keeping — *why* the prediction failed,
because the reason is a measurement that constrains every future rule in this
region.

| | |
|---|---|
| **The spec** | C1 M2: after a melee hit a tape kiter (a) starts moving in ~0.08 s, (b) flees on a bearing dominated by away-from-the-hitter (cos 0.88 vs the engine's 0.61), (c) sustains it into ~1.03 tiles of radial separation per chaser reload (engine 0.05). Build that as a contact-break state; end it on a physical escape criterion, not a timer. |
| **Built** | `C2A.contactBreak` (latch the hitter; retreat basis becomes away-from-the-hitter, superseding E10a's shared centroid basis) + `C2A.breakPriority` (while live, retreating outranks R5B-D1 stop-to-fire and the re-approach arm). Escape = the hitter's own reach + the kiter's own body diameter. **No constant is introduced by either rule.** |
| **Is it live?** | Yes, and not marginally: a break occupies **16.2 %** of kiter unit-ticks over the 86-fight chase corpus and lasts a **median 2.25 s** (p90 5.87). |
| **Did it do what C1 predicted?** | **No.** cos to the hitter 0.61 → **0.63** (target 0.88); radial separation per reload 0.05 → **0.09** tiles (target 1.03); chaser in-reach per cycle 1.81 → **1.90 s** (target 0.66). Two secondary predictions did land: post-hit seconds-to-leave-reach 0.42 → **0.29**, stopped-victim hit share 55.2 % → **42.4 %**. |
| **Cost** | Corpus winners **194/216 → 187/216**, **+2.12 HP-pts**. All seven losses are one family: `champion__vs__heavy_cav_archer` **8/9 → 1/9** — the same family, flipping the same way, that already blocks P2 and R5f-A2. |
| **Verdict** | Shipped OFF, wired and tested under explicit override. The rule is not wrong in kind; it is **unreachable in this engine** for a reason that is now measured (below), and its counterpart is on the **chaser**, not the kiter. |

---

## 1. What was built

Two flags in `apps/website/static/js/engine/constants.js` (`C2A`), the same
shape as `R5B` / `R5D` / `B2` / `R5F`:

* **C-a1 `contactBreak`** — `takeDamage` latches the attacker when a **melee**
  unit puts damage on a **non-siege ranged** body. While that hitter is within
  `hitter.attackRange + hitter.radius + kiter.radius + 2 * kiter.radius`, the
  kiter's retreat basis in `moveAwayFromTarget` is the unit vector away from
  *the hitter*, replacing E10a's shared enemy-centroid basis. Cohesion and the
  orbit term are unchanged and still added on top.
* **C-a2 `breakPriority`** — while the break is live, R5B-D1's launch test and
  the `rangedShouldApproach` arm are skipped in favour of the retreat. The
  committed-shot windup and E9's `fireRecovery` are **not** overridden: those
  are measured commitments of an animation already in flight and are shared with
  the ranged-vs-ranged round.

Neither rule carries a number. The escape distance is two quantities the engine
already computes — `inRange()`'s own arithmetic for the pair, and the fleeing
body's own diameter. For a champion chasing a Heavy Cav Archer it evaluates to
~1.07 tiles, which is the same order as the 1.03 tiles of radial separation C1
measured the tape's kiter opening per reload. That is a consistency check on the
criterion, not its derivation.

**Scope is structural, not a check-list.** The trigger is a *melee* hit, so
ranged-vs-ranged fights cannot reach the rule (they contain no melee attacker).
The victim-side `isRanged()` gate keeps melee-vs-melee out. `minAttackRange > 0`
keeps siege out — the same clause `kiteSteering` uses, for the same reason.
Verified, not assumed: over 216 fights × 20 seeds with both rules ON, the
melee (83), ranged-v-ranged (6) and siege (25) blocks are **byte-identical** to
the flags-off run.

## 2. Emergence table

Engine columns are the median over the 29 melee-swing families of the C1 chase
corpus, computed by `tools/simjs/c1_chaser_cadence.py` off
`tools/simjs/c1_chase_probe.mjs --c2a …` dumps, 86 fights × 20 seeds. "Target"
is C1 M2's tape value.

| quantity | tape | base | C-a | moved |
|---|---|---|---|---|
| post-hit seconds until reach is lost | 0.08 | 0.42 | **0.29** | toward |
| cos(flee, away-from-the-hitter) | 0.88 | 0.61 | **0.63** | toward, by 0.02 |
| cos(flee, away-from-enemy-centroid) | 0.78 | 0.67 | **0.39** | **away** |
| victim radial displacement / reload (tiles) | 1.03 | 0.05 | **0.09** | toward, by 0.04 |
| windows that lose reach | 100.0 % | 57.0 % | 57.9 % | toward |
| chaser hits on a STOPPED victim | 9.9 % | 55.2 % | **42.4 %** | toward |
| kiter stopped duty cycle | 0.319 | 0.467 | 0.462 | toward |
| kiter median move-run (s) | 1.38 | 0.70 | **0.40** | **away** |
| chaser cycles that lose contact | 97.2 % | 54.1 % | **51.1 %** | **away** |
| chaser seconds IN REACH per cycle | 0.66 | 1.81 | **1.90** | **away** |
| chaser landed hits / chaser-alive-second | 0.0964 | 0.1602 | **0.1678** | **away** |

Read honestly: the rule moves the *reaction* (latency, stopped-victim share,
duty cycle) and fails to move the *outcome* (bearing, separation, contact
duration). The chaser ends up **more** in contact, not less.

## 3. Why — the measurement that matters

`tools/simjs/c2a_break_probe.mjs` (read-only wrapper on `moveAwayFromTarget`,
`--verify-identity` PASS) records the magnitude of every term the method sums
before it normalises, on ticks where a break is live. 86 fights × 5 seeds:

```
kiter unit-ticks with a live break   1 676 244 / 10 371 847  = 16.2 %
break episodes                       3 547   median 2.25s  mean 2.84s  p90 5.87s

term magnitudes on a BREAK tick (mean, pre-normalisation)
  |radial basis|        1.000     <- the break's bearing, unit by construction
  |orbit + cohesion|    1.249
  |avoidance|           2.221

cos(pre-smoothing heading, break bearing)   0.374
cos(actual tick step,      break bearing)   0.276
```

**The retreat heading in this engine is not basis-limited.** The basis is 1.000
of a 4.47-magnitude sum — 22 % of it. `KITE_COHESION_WEIGHT` (3.0) and
`calculateAvoidance`'s unbounded body-repulsion sum decide the direction; the
velocity smoothing then carries the previous heading forward, which is why the
realised per-tick cosine (0.276) is *lower* than the pre-smoothing one (0.374).
No **choice** of basis can reach cos 0.88 here. Only a re-weighting could, and
that would be a fitted constant that also undoes E10a.

**And the cost has a name: milling.** E10a exists because twelve kiters each
fleeing their own target ran twelve ways and the ball stopped receding. C-a1
partially reinstates exactly that for the touched members: cos to the enemy
centroid falls 0.67 → 0.39 (tape 0.78) while cos to the hitter buys +0.02. On
tape the two bases are nearly collinear — the tape's kiter satisfies 0.88 to its
hitter *and* 0.78 to the centroid at once. In this engine they are not, and
forcing one costs the other.

That the loss is the **basis change** and not the shot suppression is measured
directly: `--c2a contactBreak` alone (bearing, no priority) already costs the
full seven winners.

## 4. The board

Full corpus, 216 scoreable fights × 20 seeds, tapebox, all other flags at
shipped defaults (P1/P2 OFF).

```
class                 n     base      C-a  delta   |HP err| HP-pts base -> C-a
ranged-v-ranged       6        6        6     +0        2.33 -> 2.33   (identical)
ranged-v-melee      102       97       90     -7        9.90 -> 14.40
melee                83       67       67     +0        6.43 -> 6.43   (identical)
siege                25       24       24     +0        9.87 -> 9.87   (identical)
TOTAL               216      194      187     -7        8.35 -> 10.48
```

Per-family winner changes, base → C-a: **exactly one**.

```
champion__vs__heavy_cav_archer    8/9 -> 1/9   -7
```

Canaries `champion__vs__arbalester` ×6: **6/6 both ways**.

`--c2a contactBreak` alone gives the identical board (187/216, same family,
+2.03 HP-pts overall).

### The champion-vs-HCA ledger

C1 M5's own ledger, recomputed with C-a on (9 recordings × 20 seeds = 180 runs).
Note the tape's winner in this family is the **kiter**: HCA takes 8 of 9.

| | tape | base | C-a | base+P2 |
|---|---|---|---|---|
| winner = chaser (champions) | 1/9 | 0/180 | **180/180** | 180/180 |
| agrees with tape | — | 88.9 % | **11.1 %** | 11.1 % |
| chaser damage per run | 5427 | 169 740 | 172 800 | 172 800 |
| kiter damage per run | 13 100 | 264 600 | **158 040** | 190 080 |
| kiter launches | 2402 | 46 980 | **27 720** | 32 940 |
| survivors at 40 s | 32.8 % | 28.6 % | **61.9 %** | 57.1 % |

C-a costs the HCA **41 % of its launches** and buys it 0.04 tiles of extra
separation. The chaser's output is unchanged. That is the whole flip.

## 5. What this licenses

**Established.**

1. The contact break is implementable with **no new constant** and with
   ranged-vs-ranged, melee-vs-melee and siege untouched *by construction* —
   proven byte-identical over the full corpus, not argued.
2. The mechanism is **live and long-lived** (16.2 % occupancy, median 2.25 s),
   so its failure is not a wiring failure.
3. A kiter's realised retreat bearing in this engine is **decided by cohesion
   and body avoidance, not by the radial basis** (1.000 against 1.249 + 2.221).
   C1's cos-0.88 target is out of reach of any basis rule. **Do not rebuild this
   as a different basis; it will move the cosine by ~0.02 again.**
4. Away-from-the-hitter and away-from-the-centroid are **collinear on tape and
   not in this engine**; trading one for the other reinstates E10's milling.
5. The break's escape criterion is satisfiable in principle (~1.07 tiles) and is
   not satisfied in practice, because **the chaser walks straight back into
   contact inside the same reload**.

**The named counterpart, as a falsifiable prediction.** C1 M3 measured that the
tape's chaser is stationary at **100 %** of its landed hits (`cStep` 0.000 in
every one of the 29 families) and is in reach **0.66 s** per cycle against this
engine's 1.81. This engine's chaser lands 19.8 % of its hits while walking. A
chaser that must **stop to swing and stay stopped** is what turns a 1.07-tile
break into a break the kiter can hold. C-a should be re-gated *with* that rule
and only then against P1/P2. If C-a still costs `champion__vs__heavy_cav_archer`
with the chaser fixed, it is refuted outright rather than blocked.

**Not established, and deliberately not attempted.**

- Whether re-weighting `KITE_COHESION_WEIGHT` or `calculateAvoidance` would let
  a basis rule bite. It would be a fitted constant against a scoreboard, and it
  would undo E10a's own measured fix.
- Whether a *blend* (hitter-away plus centroid-away) does better than a
  replacement. The term-magnitude measurement says any basis variant moves the
  realised cosine by ~0.02, so the question is not worth a scoreboard.
- Anything about the foot-shooter duty-cycle defect (C1 M2's second finding:
  0.96 t/s shooters parked ~2x too often, moving in 0.3–0.4 s dribbles against
  the tape's 2.7–3.4 s runs). C-a made the move-runs **shorter** (0.70 → 0.40 s),
  which is a separate defect this rule was never going to fix.

## 6. Reproducing

```bash
# the corpus is DERIVED, not listed
PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --print-tags > tags.txt

# boards
node tools/simjs/calib_runner.mjs --seeds 20 --out-dir <base>          # shipped == base commit
node tools/simjs/calib_runner.mjs --seeds 20 --out-dir <ca> \
     --c2a contactBreak,breakPriority
python -m aoe2x.calibration.score --all --sim-runs-dir <base> --label c2base
python -m aoe2x.calibration.score --all --sim-runs-dir <ca>   --label c2a

# emergence table
node tools/simjs/c1_chase_probe.mjs --tags-file tags.txt --seeds 20 \
     --c2a contactBreak,breakPriority --out-dir <probe>
PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --section all \
     --sim-runs-dir <probe> --json out.json

# the term-magnitude diagnosis
node tools/simjs/c2a_break_probe.mjs --tags-file tags.txt --seeds 5 \
     --c2a contactBreak,breakPriority --verify-identity
```

**Off-switch identity.** The shipped engine (both flags off) is byte-identical
to base commit `0e2dbc5` over all 216 fights × 20 seeds:

```
base commit 0e2dbc5      55f718d5a8a6637778f5be9903c227a6ebb306960b47236f0594735f2a6f0b2e
HEAD shipped defaults    55f718d5a8a6637778f5be9903c227a6ebb306960b47236f0594735f2a6f0b2e
HEAD --c2a both on       9b06677ca944f064166ecbcce4ee698f64313a819b80ba2a7d88a31e95d3dbd1
```

`node --test tests/js/engine/` — 272 pass (242 at base + 30 new).
`node tools/simjs/parity_check.mjs` is red at base and equally red here: it
diverges on `champ-v-jaguar` at **tick 0**, on spawn coordinates, i.e. a stale
golden panel — nothing this round can reach.
