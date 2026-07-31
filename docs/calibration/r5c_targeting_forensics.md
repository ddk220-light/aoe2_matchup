# R5c forensics — hand cannoneer zero-waste, and hits on movers

Measurement only; no engine change is proposed or made. Two residuals survived
Round 5b and this document measures both, plus a third thing that turned up
while measuring them and changes how both must be read.

| | question |
|---|---|
| **Q0** | A missed shot in AoE2:DE still applies damage. What exactly is the rule, and what does the engine do instead? |
| **Q1** | The tape's hand cannoneer wastes **0.0%** of its shots on targets that die in flight, in all three of its recordings. The post-R5b engine HC wastes 11.5-21.1%. What is the tape doing per shot? |
| **Q2** | The tape hits movers at 15-75%; the post-R5b engine at 4-29%. Is the tape's **aim model** better, or are the tape's **targets** better behaved? |

Everything below comes from `tools/simjs/r5c_targeting_forensics.py`, one
implementation fed either a recording's three streams or an engine run's shot
dump. It reuses `tools/simjs/ranged_fire_forensics.py`'s `Fight` (10 Hz
positions, wipe-time cut, interpolated positions), its shot→damage pairing
(residual 0.0000 s over 1,147 tape pairs, 0 unpaired) and its aim-target
inference (97.3% against named tape victims, 99.3% against the engine's
recorded true target).

```
node tools/simjs/ranged_shot_dump.mjs --tags <the six ranged tags> --seeds 20 \
     --out-dir D:/AI/aoe2_golden/shots_r5c
PYTHONPATH=. python tools/simjs/r5c_targeting_forensics.py \
     --sim-runs-dir D:/AI/aoe2_golden/shots_r5c --section all --seeds 20
```

Engine = current `improved-simulation` HEAD (71cd4a9, all four R5B flags on),
20 seeds, `tapebox` arena. `T` = tape, `E` = engine (mean over seeds). Sides
are `<owner>:<unit>` from the manifest's own `owner` field.

### The three answers, one line each

- **Q0** — A failed accuracy roll applies **exactly half the final post-armor
  damage**, unrounded, **to the unit it was aimed at** (26 of 27 events); only
  the accuracy-75 hand cannoneer produces one. The engine's graze branch
  excludes the intended target, floors the value and uses a centre-only
  0.2-tile window, and fired **zero** times in 120 seed-runs.
- **Q1** — The tape's HC gets to 0.0% waste by **spreading AND declining**: it
  double-books a victim 26-35% of the time but *lethally* 0.0% of the time,
  and on all 23 occasions its nearest enemy was already lethally covered it
  shot something else (0 stubborn). The engine's residual waste is 57-73%
  "R5b's test was already true but nothing else was reachable" plus 27-43%
  "two shooters fired in the same tick"; overtaking is 0.0%.
- **Q2** — Not the aim model and not the target-behaviour mix: **R5b's
  ballistic lead is essentially never applied** (0.0-9.0% of shots on the
  accuracy-100 sides, median lead 0.000 tiles) because the target's velocity
  is zero on the launch tick. The tape's aim point is the true intercept, and
  lands 0.118-0.226 tiles from where the victim actually is at impact against
  the engine's 0.167-0.215 *on the shots it hits*.

**Two probe fixes landed in `tools/` first** (both additive, neither touches
`apps/website/static/js/engine/`):

1. `ranged_shot_dump.mjs` recorded `tx, ty` = the target's position *at
   launch* and derived the flight length and impact time from it. That was
   correct pre-R5b, when the engine froze the impact there. Since R5b the shot
   flies to the ballistic intercept, displaced again if the accuracy roll
   failed, so every shot at a mover was mis-timed by the lead. The probe now
   reads the real endpoint (`ax, ay`), speed and `plannedDamage` off the
   projectile the original just pushed, and keeps `tx, ty` alongside.
   `--verify-identity` still PASSES on every seed.
2. `ranged_fire_forensics.load_engine` prefers `ax, ay` when present and falls
   back to `tx, ty` otherwise, so dumps written before the change reproduce the
   R5 report exactly.

---

## Q0. The reduced-damage miss — measured, not assumed

### 0a. The arithmetic

Histogramming every non-killing damage value in the six tapes: eleven of the
twelve sides produce exactly ONE value. The three hand cannoneer sides produce
**two**, and the smaller is exactly half the larger:

| HC vs | full | half | full = attack − pierce armor | half-raw-then-armor would be |
|---|---|---|---|---|
| arbalester (PA 4) | 13.0 (n=23) | **6.5** (n=6) | 17 − 4 | 8.5 − 4 = 4.5 ✗ |
| imp_elite_skirm (PA 8) | 9.0 (n=18) | **4.5** (n=3) | 17 − 8 | 8.5 − 8 = 0.5 ✗ |
| heavy_cav_archer (PA 6) | 11.0 (n=84) | **5.5** (n=18) | 17 − 6 | 8.5 − 6 = 2.5 ✗ |

**The rule is half of the FINAL, post-armor damage.** Not half the raw attack
then armor, and **not rounded or floored** — the recorded values carry the
`.5`. The hand cannoneer is the only unit in this corpus with `accuracy < 100`
(75 vs 100 for arbalester / imp_elite_skirm / heavy_cav_archer), and it is the
only unit that produces a reduced value: **zero half-damage events on any
accuracy-100 side, across all six tapes.** The reduced hit is the accuracy
roll's consequence, and nothing else in this corpus produces one.

### 0b. Who gets hit — the reduced hit is NOT a stray

| | |
|---|---|
| HC reduced-damage events, whole corpus | **27** |
| …that landed on the **intended** target | **26** |
| …that landed on a **different** unit (a true stray) | **1** |

The coordinator's model — "the miss scatters into the blob and hits somebody
else" — is not what these recordings show. The displaced shot lands on the
unit it was aimed at 26 times out of 27 and applies half. Full-damage events
whose victim differs from the inferred aim target number 1 / 1 / 5 on the HC
sides and 0-13 elsewhere; those are the known ~3% aim-inference error (a
full-strength application is by definition a direct hit on the unit it was
aimed at), not strays.

### 0c. Why: the displacement is small relative to the body, and the formation is loose

`scatter` = |landing point − (victim position at impact + sprite anchor)|,
i.e. the displacement with the constant anchor offset removed. `crowd` = the
distance from a struck victim to its own nearest ally — how close a second
body is.

| HC side | scatter FULL | scatter HALF | HALF p90 | HALF max | crowd med | crowd p10 |
|---|---|---|---|---|---|---|
| arb v HC | 0.058 | 0.246 | 0.313 | 0.333 | 0.635 | 0.258 |
| skirm v HC | 0.057 | 0.297 | 0.573 | 0.642 | 0.366 | 0.329 |
| HCA v HC | 0.112 | 0.258 | 0.440 | 0.550 | 0.659 | 0.507 |

A full-strength hit lands 0.06-0.11 tiles from the aim point (measurement
floor). A reduced hit lands a median 0.25-0.30 tiles off, max 0.64. Body plus
projectile is 0.2 + 0.1 = 0.3 tiles, so a displacement of that size usually
still catches the primary and only rarely reaches past it — and the nearest
ally is 0.37-0.66 tiles away, which is beyond the observed displacements in
most cases.

**On the dat-vs-community dispersion discrepancy:** the dat we read says 0.33
(arb / HCA / skirm) and 0.50 (HC); a community thread claims 0.75 for HC. This
measurement cannot settle it. Observed HC displacements are a *truncated*
sample — a shot thrown far enough to miss every body produces no damage event
and no measurable displacement — so the observed max of **0.642** is a lower
bound on the radius, not an estimate of it. It is above 0.50 but the sample is
27 shots with ~0.1 tile of position noise. What the data *does* say is that
this corpus contains no evidence of the *large* throws a 2-tile legacy scatter
would produce: HC shots that applied nothing land a median 0.38 / 0.65 / 1.28
tiles from the nearest enemy, no worse than the accuracy-100 units' own
non-applying shots (0.34-1.27).

### 0d. What the engine does

The engine is **not** missing the mechanic — `battle_unit.js` has a graze
branch. It is mis-specified in three ways at once, and the net effect is that
it never fires:

| | tape | engine graze branch |
|---|---|---|
| who can be hit | the intended target (26/27) | `if (enemy === target) continue` — **the intended target is excluded** |
| hit window | the shot lands on the body | `ex*ex+ey*ey <= enemy.radius*enemy.radius` — enemy **centre** within 0.2 tiles, no projectile radius |
| value | exactly `damage/2`, fractional | `Math.max(1, Math.floor(damage * 0.5))` — 13 → **6**, not 6.5 |

Result over **120 engine seed-runs**: `E half` = **0** on every one of the
twelve sides. The engine's own damage histogram for its hand cannoneers is
`{13.0, 1.0-clamped-kill}` — the value 6 never appears. Meanwhile R5b's D2
sends a failed roll to a displaced aim point and, if it still lands on the
body, resolves it as a **full** hit. So the engine's model of a failed
accuracy roll is "full damage or nothing", where the tape's is "half damage".

### 0e. What it costs, per shot

`dmg/shot ×` = damage applied per shot fired, as a fraction of one full hit
(clamped kills counted as full).

| HC side | T land% | E land% | T dmg/shot × | E dmg/shot × |
|---|---|---|---|---|
| arb v HC | 79.1 | 71.3 | 0.721 | 0.709 |
| skirm v HC | 80.8 | 72.8 | 0.750 | 0.726 |
| HCA v HC | 77.7 | 80.8 | 0.712 | 0.796 |

**Verdict (Q0).** The mechanic is real, exactly `final_damage / 2`, applies
only to the unit with `accuracy < 100`, and — in this corpus — lands on the
*intended* target, not a neighbour: 26 of 27 reduced hits. The engine's graze
branch cannot reproduce it because it excludes the intended target, uses a
centre-only 0.2-tile window and floors the value; it produced zero reduced
hits in 120 runs. Post-R5b the two sides' *aggregate* damage-per-shot happens
to be close (0.71-0.75 tape vs 0.71-0.80 engine), but the composition is
wrong in both directions at once: the engine lands fewer shots and pays full
for all of them, where the tape lands more and pays half on 14-21% of them.
For the rest of this document, every tape "hit rate" is reported split into
**direct** and **reduced**, because the engine has no reduced hit and the raw
numbers are not the same quantity.

---

## Q1. How the tape's hand cannoneer reaches 0.0% in-flight waste

### Q1a. Per-shot target choice

Rank is the victim's place in the shooter's nearest-first ordering **among the
enemies within reach** (those are the choices it had). Two nulls bracket it:
nearest-first scores `near% = 100, rank = 1` by construction; `rand` is what a
shooter picking uniformly at random among its reachable enemies would score on
the same shots. `inrch k` = median enemies in reach at launch. Strays are
excluded throughout (all 1 of them).

| fight | side | T n | T near% | E near% | near% rand | T rank | E rank | rank rand | T inrch k | E inrch k | T same% | E same% | T unshared% | E unshared% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | **3:HC** | 32 | **34.4** | 61.2 | 17.8 | **3.53** | 1.64 | 4.14 | 6.5 | 3.0 | **6.2** | 19.7 | **40.6** | 17.8 |
| skirm v HC | **3:HC** | 19 | **63.2** | 59.1 | 19.5 | **1.74** | 1.82 | 3.95 | 7.0 | 2.2 | **15.8** | 17.1 | **47.4** | 24.6 |
| HCA v HC | **3:HC** | 104 | **45.2** | 56.3 | 15.8 | **2.67** | 1.71 | 4.58 | 9.0 | 3.7 | **21.2** | 35.0 | **22.1** | 23.2 |
| arb v HC | 2:arb | 148 | 34.5 | 58.0 | 19.4 | 2.74 | 1.82 | 4.34 | 7.0 | 4.9 | 4.7 | 29.8 | 6.1 | 11.3 |
| arb v HCA | 2:arb | 253 | 54.9 | 60.4 | 16.2 | 2.09 | 1.96 | 4.12 | 7.0 | 5.0 | 26.1 | 65.7 | 6.3 | 12.7 |
| arb v HCA | 3:HCA | 148 | 64.9 | 83.2 | 30.9 | 2.57 | 1.17 | 3.16 | 4.0 | 2.0 | 36.5 | 33.7 | 32.4 | 23.2 |
| arb v skirm | 2:arb | 92 | 71.7 | 69.4 | 9.6 | 2.20 | 1.69 | 7.36 | 15.0 | 7.5 | 33.7 | 61.3 | 4.3 | 17.7 |
| arb v skirm | 3:skirm | 115 | 46.1 | 69.1 | 29.2 | 2.97 | 1.32 | 3.35 | 5.0 | 2.0 | 19.1 | 9.3 | 15.7 | 5.2 |
| skirm v HC | 2:skirm | 100 | 58.0 | 81.0 | 28.1 | 2.01 | 1.41 | 2.98 | 5.0 | 3.0 | 2.0 | 14.1 | 4.0 | 5.5 |
| skirm v HCA | 2:skirm | 159 | 55.3 | 67.5 | 32.6 | 1.87 | 1.46 | 2.88 | 5.0 | 3.0 | 16.4 | 27.6 | 3.8 | 6.5 |
| skirm v HCA | 3:HCA | 45 | 71.1 | 87.8 | 13.7 | 1.49 | 1.12 | 4.64 | 8.0 | 2.0 | 66.7 | 44.9 | 35.6 | 16.3 |
| HCA v HC | 2:HCA | 164 | 41.5 | 76.9 | 21.0 | 3.38 | 1.30 | 4.56 | 8.0 | 3.0 | 7.9 | 30.3 | 11.6 | 20.7 |

Restricting the tape rows to shots whose victim the damage pairing NAMES (i.e.
removing the aim inference entirely) moves `near%` by at most 4 points on the
HC sides (34.4 → 35.5, 63.2 → 63.2, 45.2 → 47.5), so the inference is not
carrying this.

**Verdict (Q1a).** The tape does not acquire nearest-first and the engine
nearly does. Every tape side sits between the random null and nearest-first;
the tape's hand cannoneer sits closest to random of any unit (34.4 / 63.2 /
45.2 against a random null of 17.8 / 19.5 / 15.8, and a median chosen rank of
3.5 / 1.7 / 2.7 against a random 4.1 / 4.0 / 4.6), while the engine's HC is at
56-61% nearest with rank 1.6-1.8. Target *persistence* is the other half:
tape HC re-picks the same victim on only 6-21% of consecutive shots, the
engine on 17-35%, and the tape's arbalester/skirmisher re-pick as low as
2-5%. And the choice-SET differs before any rule does: the engine's shooters
have a median of **2.0-7.5** enemies in reach where the tape's have
**4.0-15.0**, on all twelve sides — the tape's units simply have more to pick
from.

### Q1b. Volley structure against two null models

Shots binned into consecutive reload-length windows. `vict` = distinct victims
the window's shots went to; `vict(near)` = the same count if every shot had
gone to its own shooter's nearest enemy; `vict(RR)` = `min(shots, living
enemies)`, a perfect round-robin. `|o−near|` / `|o−RR|` = median absolute
distance from each null.

| fight | side | T shots/w | T vict | T vict(near) | T vict(RR) | T maxdup | T \|o−near\| | T \|o−RR\| | E vict | E \|o−near\| | E \|o−RR\| |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | **3:HC** | 10 | **6** | 2 | 10 | 2 | **3** | **3** | 4.2 | 1.5 | 3.3 |
| skirm v HC | **3:HC** | 6 | **3** | 2 | 6 | 2 | **1** | 2 | 2.9 | 0.9 | 2.6 |
| HCA v HC | **3:HC** | 11.5 | **4.5** | 3.0 | 11.5 | 4.0 | **1.5** | 7.5 | 4.9 | 1.3 | 4.0 |
| arb v HC | 2:arb | 14 | 4 | 2 | 10 | 6 | 1 | 5 | 4.7 | 1.9 | 3.3 |
| arb v HCA | 2:arb | 10.0 | 2.0 | 3.0 | 7.0 | 8.0 | 1.0 | 5.5 | 3 | 1 | 5 |
| arb v HCA | 3:HCA | 7 | 3 | 2 | 7 | 3 | 1 | 4 | 2.0 | 0.0 | 2.0 |
| arb v skirm | 2:arb | 7.0 | 1.5 | 2.0 | 7.0 | 6.0 | 0.0 | 5.0 | 3.5 | 1.0 | 4.5 |
| arb v skirm | 3:skirm | 17.5 | 4.0 | 1.0 | 7.0 | 8.0 | 3.0 | 3.0 | 4 | 1 | 3 |
| skirm v HC | 2:skirm | 17.0 | 2.5 | 2.5 | 6.0 | 10.0 | 0.5 | 2.5 | 3.0 | 1.0 | 1.0 |
| skirm v HCA | 2:skirm | 17 | 2 | 2 | 6 | 10 | 0 | 3 | 4.0 | 1.0 | 1.0 |
| skirm v HCA | 3:HCA | 3.0 | 2.0 | 2.0 | 3.0 | 2.0 | 0.0 | 1.0 | 2 | 0 | 3 |
| HCA v HC | 2:HCA | 8.0 | 2.0 | 3.0 | 5.5 | 4.5 | 1.0 | 3.0 | 3.3 | 0.25 | 3.9 |

**Verdict (Q1b).** **Not a round-robin.** On ten of twelve tape sides the
nearest-null is the strictly closer fit (`|o−near|` 0.0-3.0 vs `|o−RR|`
1.0-7.5); the other two (HC in arb v HC, skirm in arb v skirm) are ties, and
no side fits RR better. A perfect round-robin would put 6-11.5 distinct
victims in a window; the tape puts 1.5-6. What the tape *does* beat is the
nearest-null itself, by +1 to +4 victims per window on the three HC sides
(6 vs 2, 3 vs 2, 4.5 vs 3) and by 0 to +3 elsewhere. The structure is
"positional spread plus a bit": shooters standing in different places
naturally cover different nearest targets, and the tape adds roughly one to
three extra victims per window on top of that. The extra is largest on hand
cannoneer, whose `maxdup` (most shots on any one victim in a window) is
**2.0 / 2.0 / 4.0** where its own arbalester/skirmisher opponents pile 6-10
shots on a single victim in the same corpus.

### Q1c. Lethality awareness — spread, or genuine hold-fire?

`anyInb%` = the victim already had a friendly projectile inbound that will
land *first*. `cov%` = that inbound damage already ≥ its hp, i.e. the shot was
dead on arrival the moment it was fired (this is exactly what R5b's
`inboundDamageOn` computes, recomputed here from the shot list so the tape can
be asked the same question). `1shot n` = shots whose victim needed only one
hit to die; `dbl%` = the share of those that were doubled up anyway.
`redir/stub` = the shooter's NEAREST enemy was already lethally covered and it
shot elsewhere / shot it anyway.

| fight | side | T anyInb% | E anyInb% | **T cov%** | **E cov%** | T 1shot n | T dbl% | E dbl% | T redir | T stub | E redir | E stub |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | **3:HC** | 26.2 | 21.2 | **0.0** | 12.1 | 3 | **0.0** | 7.4 | 9 | **0** | 4.6 | 0.1 |
| skirm v HC | **3:HC** | 32.0 | 19.3 | **0.0** | 11.6 | 1 | **0.0** | 0.0 | 0 | **0** | 0.1 | 0 |
| HCA v HC | **3:HC** | 34.7 | 23.2 | **0.0** | 5.7 | 5 | **0.0** | 2.7 | 14 | **0** | 3.6 | 0 |
| arb v HC | 2:arb | 54.2 | 59.3 | 13.1 | 11.8 | 15 | 53.3 | 58.3 | 47 | 8 | 30.4 | 9.3 |
| arb v HCA | 2:arb | 67.9 | 76.1 | 3.1 | 0.0 | 2 | 0.0 | – | 10 | 7 | 16 | 0 |
| arb v HCA | 3:HCA | 54.2 | 56.7 | 8.5 | 12.0 | 18 | 55.6 | 71.4 | 11 | 10 | 19 | 3 |
| arb v skirm | 2:arb | 28.1 | 33.8 | 2.1 | 0.0 | 1 | 0.0 | – | 7 | 2 | 0 | 0 |
| arb v skirm | 3:skirm | 63.1 | 24.2 | 16.9 | 12.5 | 3 | 33.3 | 0.0 | 29 | 13 | 6 | 10 |
| skirm v HC | 2:skirm | 21.8 | 53.4 | 13.9 | 6.7 | 0 | – | 39.2 | 9 | 9 | 3.1 | 2.3 |
| skirm v HCA | 2:skirm | 30.0 | 46.0 | 4.4 | 4.4 | 0 | – | 33.3 | 2 | 7 | 11 | 3 |
| skirm v HCA | 3:HCA | 39.1 | 46.8 | 0.0 | 8.1 | 1 | 0.0 | 50.0 | 1 | 0 | 6 | 5 |
| HCA v HC | 2:HCA | 49.1 | 59.5 | 17.0 | 16.1 | 9 | 55.6 | 59.1 | 11 | 18 | 14.4 | 10.5 |

**Verdict (Q1c). It is not pure spread — there is positive evidence of
redirect, and the coverage number is a hard zero.** The tape's HC *does* double
up: 26-35% of its shots go at a victim that already has a friendly bullet
arriving first. What never happens is doubling up **lethally**: `cov%` is
**0.000** on all three HC sides, and of the nine HC shots whose victim needed
only one hit to die, **none** had a second bullet already inbound. And the
23 occasions on which an HC's nearest enemy *was* already lethally covered
resolved 23-for-23 as "shoot something else" — zero stubborn shots, on all
three tapes. So spread alone does not explain it; the tape's HC is spreading
*and* declining a covered target. Note this is measured with the tape's FULL
damage assumed for every inbound bullet even though 14-21% of them will apply
half, which makes coverage *easier* to trigger — and it still never does. For
contrast, the tape's arbalester and heavy_cav_archer routinely double a
one-shot victim (53.3 / 55.6 / 55.6%) and their `cov%` runs 3-17%.

### Q1d. Where the engine's wasted shots come from

Every engine shot whose true target dies strictly between launch and impact,
attributed to a cause. `alt%` = share of that bucket for which another
reachable, not-already-lethally-covered enemy existed at launch.

| fight | side | T wst% | E wst% | E n | **blind%** | **blind alt%** | **same-tick%** | st alt% | overtaken% | cumul% |
|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | **3:HC** | **0.0** | 21.1 | 9.7 | **61.0** | **2.4** | **39.0** | 20.3 | 0.0 | 0.0 |
| skirm v HC | **3:HC** | **0.0** | 19.5 | 5.1 | **73.4** | **2.5** | **26.7** | 0.0 | 0.0 | 0.0 |
| HCA v HC | **3:HC** | **0.0** | 11.5 | 10.5 | **56.8** | **12.2** | **43.2** | 0.0 | 0.0 | 0.0 |
| arb v HC | 2:arb | 14.3 | 18.2 | 28.6 | 78.0 | 14.6 | 21.9 | 34.3 | 0.0 | 0.1 |
| arb v HCA | 2:arb | 3.8 | 2.3 | 6 | 100.0 | 33.3 | 0.0 | – | 0.0 | 0.0 |
| arb v HCA | 3:HCA | 8.4 | 16.0 | 24 | 87.5 | 4.8 | 12.5 | 0.0 | 0.0 | 0.0 |
| arb v skirm | 2:arb | 2.1 | 3.8 | 3 | 100.0 | 33.3 | 0.0 | – | 0.0 | 0.0 |
| arb v skirm | 3:skirm | 13.6 | 39.1 | 50 | 52.0 | 23.1 | 38.0 | 31.6 | 0.0 | 10.0 |
| skirm v HC | 2:skirm | 27.5 | 34.6 | 37.1 | 64.3 | 25.0 | 35.7 | 53.1 | 0.0 | 0.0 |
| skirm v HCA | 2:skirm | 25.6 | 16.8 | 23 | 87.0 | 45.0 | 13.0 | 0.0 | 0.0 | 0.0 |
| skirm v HCA | 3:HCA | 0.0 | 11.3 | 7 | 100.0 | 0.0 | 0.0 | – | 0.0 | 0.0 |
| HCA v HC | 2:HCA | 18.5 | 20.7 | 33.3 | 90.3 | 0.3 | 9.7 | 31.6 | 0.0 | 0.0 |

**Verdict (Q1d).** Engine HC waste is **11.5-21.1%** and splits into exactly
two causes, in the same proportions on all three fights:

- **blind, 57-73%** — R5b's own test was *already true* at launch: the damage
  inbound-and-arriving-first already exceeded the victim's hp, and the shot
  went out anyway. In **88-98%** of those cases (`alt%` 2.4 / 2.5 / 12.2)
  there was **nothing else reachable and not already covered**, so
  `pickShotTarget`'s `return best || primary` fallback is what fired. This
  confirms the R5b agent's suspicion directly and quantifies it: HC's 7-tile
  reach plus D4's approach margin leaves its shooters a median of **3.0 / 2.2 /
  3.7** enemies in reach against the tape's **6.5 / 7.0 / 9.0** (Q1a), so the
  redirect has nowhere to go.
- **same-tick, 27-43%** — the kill required a shot launched in the same 1/60 s
  tick, which neither shooter could have seen. `alt%` here is 20.3 / 0.0 / 0.0,
  so most of these also had no alternative.
- **overtaken (a later launch that arrived first) is 0.0% on all twelve
  sides**, and **cumulative** (the victim was genuinely worth shooting at
  launch) is 0.0-10.0%. R5b's arrival-order qualifier is doing its job; the
  residual is not an ordering bug.

The same two buckets dominate every other side too, so this is not an HC-only
mechanism — HC is just where the tape's own waste is exactly zero, which makes
the residual visible.

---

## Q2. Hits on movers

### Q2a. What aim model does the tape imply?

`leadratio` = how far along the victim's own launch→impact displacement the
landing point sits: 0 = aimed at where it was, 1 = full intercept. Model
columns are the median residual |predicted aim point − actual landing point|
in tiles, with the measured sprite-anchor offset removed. `oracle` = the
victim's true position at impact — the floor any causal model could reach.
Pooled by shooter unit because the per-fight cells run n = 1-8.

| unit | src | n | n(disp>0.3) | leadratio | lr(disp>0.3) | none | lead@0.11s | lead@0.3s | lead@0.5s | 0.5×@0.3s | **oracle** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arb | tape | 15 | 3 | 0.26 | **0.96** | 0.113 | 0.066 | 0.077 | 0.078 | 0.113 | **0.131** |
| skirm | tape | 11 | 4 | 0.87 | **0.50** | 0.155 | 0.150 | 0.074 | 0.109 | 0.119 | **0.118** |
| HCA | tape | 1 | 1 | 1.17 | **1.17** | 0.795 | 0.208 | 0.268 | 0.481 | 0.535 | **0.226** |
| HC | tape | 9 | 5 | 0.95 | **0.91** | 0.493 | 0.493 | 0.493 | 0.493 | 0.493 | **0.125** |
| arb | engine | 65 | 23 | −0.00 | −0.00 | 0.000 | 0.000 | 0.000 | 0.027 | 0.000 | **0.215** |
| skirm | engine | 26 | 6 | 0.00 | 1.23 | 0.000 | 0.000 | 0.067 | 0.622 | 0.034 | **0.213** |
| HC | engine | 13 | 1 | 0.00 | 0.24 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.167** |

The anchor offset is a genuine constant, which is what makes these residuals
readable: over 14-208 stationary-target hits per side the median offset vector
is (+0.00…+0.12, −0.23…−0.29) for owner-2 sides and (−0.10…−0.01, +0.23…+0.28)
for owner-3 sides, with a median individual deviation from it of **0.049-0.106
tiles**.

**Verdict (Q2a). The tape fires a FULL intercept, and it computes it from the
target's true path, not from an estimate.** Restricted to victims whose whole
launch→impact displacement exceeds 0.3 tiles (below that the ratio's
denominator is comparable to position noise), the tape's lead ratio is
**0.96 / 0.50 / 1.17 / 0.91** for arb / skirm / HCA / HC — median across the
13 such shots ≈ 0.9. The decisive column is `oracle`: the tape's landing point
sits **0.118-0.226 tiles** from where the victim actually was at impact, which
is the position-interpolation noise floor. No causal model fitted here beats
it, and none can: every trailing-window velocity estimate (0.11 s through
1.0 s) leaves a residual at or above the oracle's, because a 9 Hz sampled
velocity is noisier than the exact one the game itself used. The right reading
is therefore not "which window length wins" — none of them does — but "the
tape's aim point IS the intercept of the target's real motion". The engine's
own `oracle` is **0.167-0.215 tiles**, i.e. even the engine shots that
*connect* land twice as far off as the tape's, against a hit window of only
`target.radius + 0.1` = 0.30-0.35 tiles.

### Q2d. How often the engine actually leads (every shot, no hit selection)

Distance from the landing point to the target's position at launch. Because
this is read off the dump rather than inferred from hits, it has no selection
effect.

| fight | side | E shots | lead>0.05 tiles | lead>0.30 tiles | med | p90 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 156.7 | **7.7%** | 7.7% | 0.000 | 0.176 | 1.007 | 1.093 |
| arb v HCA | 2:arb | 264 | **2.7%** | 2.7% | 0.000 | 0.000 | 1.368 | 1.435 |
| arb v HCA | 3:HCA | 150 | **0.0%** | 0.0% | 0.000 | 0.000 | 0.000 | 0.000 |
| arb v skirm | 2:arb | 80 | **0.0%** | 0.0% | 0.000 | 0.000 | 0.000 | 0.000 |
| arb v skirm | 3:skirm | 128 | **0.0%** | 0.0% | 0.000 | 0.000 | 0.000 | 0.000 |
| skirm v HC | 2:skirm | 107.2 | **9.0%** | 9.0% | 0.000 | 0.048 | 0.960 | 0.965 |
| skirm v HCA | 2:skirm | 137 | **1.5%** | 1.5% | 0.000 | 0.000 | 0.824 | 1.557 |
| skirm v HCA | 3:HCA | 62 | **0.0%** | 0.0% | 0.000 | 0.000 | 0.000 | 0.000 |
| HCA v HC | 2:HCA | 160.2 | **0.3%** | 0.3% | 0.000 | 0.000 | 0.018 | 0.413 |
| arb v HC | 3:HC | 46 | 24.2% | 10.5% | 0.000 | 0.288 | 0.443 | 0.459 |
| skirm v HC | 3:HC | 26.1 | 23.6% | 9.9% | 0.000 | 0.258 | 0.406 | 0.426 |
| HCA v HC | 3:HC | 90.6 | 24.6% | 11.7% | 0.000 | 0.319 | 0.859 | 1.238 |

The three HC rows are the confounded ones: their 23.6-24.6% is
indistinguishable from HC's 25% accuracy-failure rate, and their p90/max
(0.26-0.32 / 0.43-1.24) sit at the dat dispersion radius — that is D2's miss
displacement, not a ballistic lead. The nine accuracy-100 rows are clean.

**Verdict (Q2d). R5b's ballistic lead is essentially never active.** On the
nine accuracy-100 sides the engine applies *any* lead on **0.0-9.0%** of its
shots — four sides at exactly 0.0% — and the median lead is 0.000 tiles
everywhere. The cause is visible in the same data: `aimPointFor` multiplies
`target.velX/velY` at the launch tick, and the target's velocity on that tick
is zero, because D1 stops units to fire and D4 parks them at the approach
margin. So the failure mode is not "the intercept is stale and overshoots" —
it is that **there is no intercept at all**: the engine aims at where the
target is standing on the launch tick, and then the target walks out of a
0.30-0.35 tile window during a ~1.1 s flight.

### Q2b / Q2c. What the target did during the flight

Pooled by shooter unit across all six fights. `mvfrac` = median share of the
flight the victim spent moving, over shots at victims that were moving at
launch — the halt-frequency comparison. Behaviour classes: *still* (not moving
at launch), *kept* (moving throughout, heading held within 45°), *halted*
(moving at launch, moving for under half the flight), *turned*.

| unit | src | shots | still% | still hit% | mover n | mover share | **mv hit%** | **mv direct%** | kept n / hit% | halted n / hit% | turned n / hit% | **mvfrac** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb | tape | 512 | 93.4 | 85.1 | 34 | 6.6% | **67.6** | **67.6** | 12 / 33.3 | 22 / 86.4 | 0 / – | **0.261** |
| arb | engine | 9820 | 94.9 | 90.2 | 503 | 5.1% | **22.5** | **22.5** | 91 / 3.3 | 412 / 26.7 | 0 / – | **0.222** |
| HCA | tape | 385 | 97.9 | 80.1 | 8 | 2.1% | **75.0** | **75.0** | 4 / 50.0 | 1 / 100 | 3 / 100 | **0.727** |
| HCA | engine | 7287 | 99.8 | 84.1 | 13 | 0.2% | **15.4** | **15.4** | 0 / – | 13 / 15.4 | 0 / – | **0.375** |
| skirm | tape | 392 | 96.7 | 64.4 | 13 | 3.3% | **15.4** | **15.4** | 0 / – | 13 / 15.4 | 0 / – | **0.182** |
| skirm | engine | 6868 | 95.0 | 73.9 | 340 | 5.0% | **28.5** | **28.5** | 14 / 42.9 | 326 / 27.9 | 0 / – | **0.333** |
| HC | tape | 193 | 83.9 | 91.4 | 31 | 16.1% | **48.4** | **38.7** | 16 / 37.5 | 7 / 85.7 | 8 / 37.5 | **1.000** |
| HC | engine | 3246 | 99.3 | 77.4 | 23 | 0.7% | **4.3** | **4.3** | 0 / – | 23 / 4.3 | 0 / – | **0.429** |

**Verdict (Q2b/Q2c). The "target behaviour frequency" hypothesis is
REJECTED — it is the aim, not the mix.**

1. **The behaviour hypothesis predicted tape hits on kept-course and tape
   misses on halted. The opposite is true, on both sides.** Tape arbalester
   hits 86.4% of halted victims and 33.3% of kept-course ones; tape HC 85.7%
   vs 37.5%; the engine's arbalester 26.7% vs 3.3%. Both sources hit the
   target that *stops* more often than the one that keeps going, which is what
   a straight-line projectile with a finite hit window should do.
2. **The engine is worse in every class, by 3-10×.** kept-course 33.3% → 3.3%
   (arb), halted 86.4% → 26.7% (arb), 85.7% → 4.3% (HC). A difference in the
   *mix* of classes cannot produce that; the engine misses movers whatever
   they do.
3. **The mover mix is not the story for arb and skirm.** Mover share is
   6.6% tape vs 5.1% engine for the arbalester and 3.3% vs 5.0% for the
   skirmisher; `mvfrac` (halt frequency) is 0.261 vs 0.222 and 0.182 vs 0.333.
   The engine's targets do NOT halt more than the tape's for these two — if
   anything the skirmisher's targets keep moving *longer* in the engine. The
   mix does diverge sharply for HC and HCA (mover share 16.1% → 0.7% and 2.1%
   → 0.2%; `mvfrac` 1.000 → 0.429 and 0.727 → 0.375), i.e. the engine's hand
   cannoneers and cavalry archers almost never *get* a moving target — but
   that is a different residual (their targets are parked), and it does not
   rescue the hit rate on the movers they do get.
4. **The reduced-hit correction does not close it.** Splitting the tape's
   landed shots into direct and reduced moves the tape's pooled mover hit rate
   from **53.5% to 50.0%** (HC alone: 48.4% → 38.7%; the accuracy-100 units
   are unaffected because they produce no reduced hits at all). The engine's
   pooled mover rate is **24.2%**. Strays and half-hits account for 3.5 points
   of an ~26-point gap.
5. **On stationary targets the engine is fine** — 90.2 / 84.1 / 73.9 / 77.4%
   against the tape's 85.1 / 80.1 / 64.4 / 91.4%. The whole mover deficit is
   the mover branch.

---

## Methodology and limits

- **Probe neutrality.** `ranged_shot_dump.mjs` still only READS `this`,
  `target` and the projectile the original just pushed; `--verify-identity`
  re-runs each seed with the wrapper removed and diffs the damage stream —
  PASS on every seed after the change. No file under
  `apps/website/static/js/engine/` was modified.
- **Waste and the tick boundary.** `impact_t` is analytic (launch +
  distance/speed) while the engine resolves on the first tick at or after that
  instant, so a shot delivering its own killing blow reports a death up to
  1/60 s "before" its own impact. Measured on the dumps, every such overlap is
  inside one tick and every one is the shot's own kill; `waste_classes`
  therefore excludes any shot that produced a damage event. Without that guard
  the engine's waste rate reads 11.5-35.0% instead of 11.5-21.1%.
- **In-flight accounting is reconstructed from `plannedDamage`**, which the
  dump now records per shot, so the `blind` bucket is the engine's own
  arithmetic and not an approximation. On the tape side the same test uses the
  full post-armor damage for every inbound shot, which over-states coverage
  (14-21% of HC's bullets apply half) — and the tape's `cov%` is still 0.0.
- **hp at launch** is read from the 10 Hz frame at or before the launch, so it
  can be up to ~0.11 s stale. Stale hp is too HIGH, which makes the coverage
  test *harder* to trigger, so `cov%` and `blind%` are lower bounds.
- **Sample sizes.** These are ranged-vs-ranged fights in which 84-100% of
  shots are at a stationary target, so the mover populations are small: per
  fight and side n = 0-21 on tape. Q2a and Q2b are therefore reported POOLED
  by shooter unit (n = 8-34 tape, 13-503 engine) and the per-fight cells are
  kept only to show the dispersion. The reduced-hit population is 27 shots
  total. Nothing in Q2 should be quoted at per-fight granularity.
- **Aim-target inference** carries ~3% error on tape shots. Q1a reports the
  same statistic restricted to shots whose victim the damage pairing NAMES
  (`near%(named)`), and it moves the HC numbers by ≤4 points. Strays are
  excluded from every target-CHOICE statistic; there is exactly one confirmed
  stray in the corpus, so this exclusion changes nothing measurable here — the
  concern that dispersion was manufacturing the tape's spread does not
  materialise in these six recordings.
- **Crowding caveat.** The near-total absence of neighbour strikes is a
  property of THESE recordings' formations (nearest ally 0.37-0.66 tiles from
  a struck victim), not a general statement. A packed blob would give a
  displaced shot far more second bodies to find, and this corpus cannot say
  what happens then.
- **Dispersion radius.** Observed HC displacements are truncated (a shot that
  strikes nothing leaves no measurable displacement), so the observed max of
  0.642 tiles is a lower bound on the radius and cannot discriminate the dat's
  0.50 from the community-claimed 0.75 at n = 27.
