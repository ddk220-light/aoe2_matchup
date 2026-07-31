# B2 — the melee bump valve, made reachable (and then narrowed)

**Date:** 2026-07-31 · **Base:** `716a522` (improved-simulation) · **Scope:**
one engine rule, melee only. Follow-up to `b1_engagement_forensics.md`.

B1 named one defect and one mechanism: E14's bump-retarget rule — the release
valve for a melee unit frozen on an unreachable target — never fires, so
surrounded units stand still while hittable enemies press against them. This
report fixes it, corrects B1's diagnosis by one pixel, and records what the fix
does to the board.

---

## 0. Headline

| Question | Answer |
|---|---|
| Was B1's diagnosis right? | **The defect yes, the cause no.** The valve really was dead (eligible on 0.1-0.2% of frozen ticks). But the cause is not that `resolveCollisions` pushes the pair apart before the rule looks — it is that the pair **never reaches the hard floor at all**. |
| What actually holds the pair apart? | **`calculateAvoidance`'s soft floor, `radius + radius + 2`** — one pixel WIDER than `resolveCollisions`' `radius + radius + 1`. Cross-team bodies settle against the soft floor, so the hard pass never touches them, and the bump asked the hard pass. |
| Does the resolver-event fix work? | **No — measured inert.** Consuming `resolveCollisions`' own contact event moves eligibility from 0.001 to 0.002. It is shipped anyway (it is free and it is right when it fires), but it is not the fix. |
| What is the fix? | Contact = the **soft floor** OR the hard pass's contact event. Eligibility on a frozen tick 0.001 → **0.321**. No new constant: both floors already existed. |
| Did that fix the defect? | **Yes, completely.** Outnumbered WASTED share of alive ticks 0.075 → 0.009; worst lock episode 35.6 s → 2.2 s; `halberdier__vs__paladin` swinging share 0.31x → 1.06x of tape. |
| Any cost? | **Yes, and it needed a second rule.** Alone it over-fires on units that were never stuck: pooled old-corpus shares 0.98x/1.01x → 1.11x/1.18x, corpus winners 194 → 190. |
| The narrowing | Read update 81058's "**and cannot reach the current target**" as the engine's own unreachability verdict (the 0.8 s stuck bar tripping while E14's lock re-arms it), not as `!inRange()`. Collapse fix survives intact; majority comes back to 1.05x/1.03x; winners 194. |
| Net | **Winners held (194/216), melee HP gate improved** (within-10 120 → 126, within-5 93 → 98, mean \|err\| 6.89 → 6.42 pts). Ranged, siege and all four canaries **byte-identical**. |

---

## 1. The one-pixel correction to B1

B1 §2b reads:

> `meleeBumpRetarget` triggers on `dist <= this.radius + enemy.radius + 1`.
> `Simulation.resolveCollisions` uses `minDist = a.radius + b.radius + 1` … so
> on the following tick the pair is at or just above the floor and the `<=`
> test fails.

That is a timing story, and it implies a timing fix: have the resolver record
the contact and have the rule consume the event. **That fix was implemented
first and measured, and it does nothing.** Over `halberdier__vs__paladin`,
`halberdier__vs__elite_elephant` and `champion__vs__paladin`, 2 seeds each,
counted on frozen ticks that had a hittable non-target melee foe present:

```
predicate                                                      share of frozen ticks
hard floor      dist <= r+r+1        (the pre-B2 trigger)                     0.001
resolver EVENT  the hard pass recorded this pair this tick                    0.002
soft floor      dist <  r+r+2        (calculateAvoidance's own threshold)     0.321
avoidance EVENT the soft pass repelled this pair last tick                    0.316
                dist <  r+r+3                                                 0.788
                dist <  r+r+5                                                 1.000
```

The reason the event changes nothing is visible in the raw geometry. On a
frozen tick the nearest **hittable** non-target foe sits this far past the hard
floor:

```
                                    n      p10     med     p90     min
halberdier__vs__paladin          4874    0.60    1.19    2.70   -0.00  px
halberdier__vs__elite_elephant   3676    0.70    1.17    2.99   -0.00  px
```

and the hard pass recorded **any** cross-team contact for that unit on 4 of
38 066 and 6 of 39 790 frozen ticks — 0.000. The bodies are never inside
`r+r+1`, so nothing the hard pass does or records can help.

They are, however, reliably inside `r+r+2`, because that is
`calculateAvoidance`'s own `minDist` for a cross-team pair:

```js
// battle_unit.js calculateAvoidance
let minDist = this.radius + other.radius + 2;   // cross-team: never scaled
...
const overlap = Math.max(0, minDist - dist) / minDist;
const force   = overlap > 0 ? 3 + overlap * 5 : 0.5;   // strong push inside
```

**The engine has two body floors, one pixel apart, and the cross-team standoff
is held by the wider one.** B1's measured "median 1.0-1.7 px past the bump
floor" is not fp noise or a timing lag — it is the soft floor, seen from the
hard floor.

---

## 2. What shipped

`B2.resolverContactBump` (B2a) — "in contact" is:

```js
const contact = useEvent
    ? (dist < this.radius + enemy.radius + 2 ||   // the SOFT floor
       this.bumpContacts.has(enemy))              // the HARD pass's event
    : dist <= this.radius + enemy.radius + 1;     // pre-B2
```

`bumpContacts` is a per-unit `Set` cleared at the top of every
`resolveCollisions` and written for every cross-team pair that pass finds at or
inside its floor. It is absent from `stateHash()` and read by nothing else.

`B2.stuckGatedBump` (B2b) — the rule additionally requires
`this.meleeStuckOn === this.target`, a latch set in `moveTowardTarget` when the
0.8 s stuck bar trips and E14's lock re-arms it. It stores the TARGET, so it
self-clears on any re-pick; it is dropped when the unit gets in reach, and
consumed by a successful bump.

**Constants introduced: none.** `r+r+2` is quoted from `calculateAvoidance`,
`r+r+1` from `resolveCollisions`, `0.8 s` from the pre-existing stuck bar.
`+3 px` (0.788 coverage) and `+5 px` (1.000) were measured and rejected: the
first is a number picked for its coverage, and for 0-range melee
`radius+radius+5` **is reach** (`MELEE_RANGE_BUFFER` = 5), so it would silently
rewrite the rule as "retarget to anything you can hit".

`<= r+r+1` implies `< r+r+2`, so B2a is a strict superset of the pre-B2 rule.
B2b is a narrowing of B2a and is meaningless without it.

---

## 3. The fix-target table (B1 §9), before and after

Old corpus, 20 seeds, `share` = swinging fraction of living bodies, ratio
engine/tape. `B2a` is the fix alone; `AB` is what shipped.

| Target | goal | base | B2a | **AB (shipped)** |
|---|---|---|---|---|
| old corpus, outnumbered pooled `share` | hold 1.00x | 0.98x | 1.11x | **1.05x** |
| old corpus, superior pooled `share` | hold | 1.01x | 1.18x | **1.03x** |
| `halberdier__vs__paladin` outnumbered | 1.00x (0.217 → 0.706) | **0.31x** (0.217) | 1.06x (0.745) | **1.06x (0.747)** |
| `halberdier__vs__elite_elephant` outnumbered | 1.00x (0.256 → 0.561) | **0.46x** (0.256) | 1.28x (0.721) | **1.28x (0.721)** |
| `halberdier__vs__heavy_camel` | hold 0.98x | 0.98x | 1.50x | **1.24x** |
| `halberdier__vs__hussar` | hold 1.54x | 1.54x | 2.00x | **1.54x** |
| v2 `champion__vs__paladin` paladin | 1.00x (0.834 → 0.914) | 0.91x | 0.95x | **0.94x** |
| v2 `champion__vs__paladin` champion | 1.00x (0.532 → 0.677) | 0.79x | 0.82x | **0.80x** |
| v2 `paladin__vs__elite_steppe` paladin | do not raise | 1.17x | 1.18x | **1.17x** |

Read plainly:

* **The two collapse families are fixed.** `halberdier__vs__paladin` lands at
  1.06x — the single largest miss on B1's board, closed. `__elite_elephant`
  overshoots to 1.28x.
* **The healthy majority is nearly held.** B2b brings the pooled ratios back
  from 1.11x/1.18x to 1.05x/1.03x and restores `halberdier__vs__hussar`
  exactly. `halberdier__vs__heavy_camel` is the residual: 0.98x → 1.24x.
* **v2 `champion__vs__paladin` barely moves** (0.91x → 0.94x outnumbered,
  0.79x → 0.80x superior). B1 said it did not explain the superior side's
  0.79x; this fix does not either.
* **v2 `paladin__vs__elite_steppe` is untouched at 1.17x**, as instructed. Its
  error is survivorship and it is not addressed here.

### Internal budgets (B1 §9, second table)

```
outnumbered side, pooled                    base      B2a        AB
WASTED share of alive ticks                0.075    0.009     0.047
engaged share of alive ticks               0.561    0.594     0.561
bump eligible on wasted ticks              0.002    0.000     0.009
prime-suspect episode p90 / max (s)     1.39/35.60  0.32/2.17  1.12/9.43
prime episode count                        12 960    4 140    11 860
crowded out                                0.000    0.000     0.000

prime/alive, the two collapse families
  halberdier__vs__paladin                   0.398    0.027     0.080
  halberdier__vs__elite_elephant            0.333    0.040     0.040
corpus norm (the healthy families)      0.065-0.10  0.003-0.015  0.001-0.14
```

B2a drives the freeze essentially to zero **everywhere**, including where the
tape says the engine was already right — which is the same fact the share table
reports as an overshoot. B2b restores the healthy waste and keeps the collapse
families' fix. `bump eligible` reads 0.000 under B2a because an eligible unit
now retargets and stops being frozen; under AB it reads 0.009 because the gate
holds some units frozen for a beat, which is the intended behaviour.

---

## 4. The board

Full corpus, 216 fights x 20 seeds, `--arena tapebox`.

```
                                      base 716a522    B2a      AB (shipped)
corpus winner agreement                 194/216     190/216      194/216
mean per-seed agreement                  0.8981      0.8796       0.8981

melee HP gate (166 sides)
  within 10 pts                          120         125          126
  within  5 pts                           93         103           98
  within  1 pt                            72          75           73
  mean |err|, pts                        6.89        6.70         6.42
  median |err|, pts                      3.81        1.90         2.42
  melee winners                          67/83       63/83        67/83
  basic-melee winners                    33/35       29/35        33/35
```

Per-family HP error, mean |err| in HP-points:

```
family                                   base     B2a       AB
halberdier__vs__paladin (n=4)            5.95     2.08     0.89
halberdier__vs__elite_elephant (n=4)     5.07     2.84     2.84
v2 champion__vs__paladin r7-13 (n=14)   13.31    12.15    12.83
v2 paladin__vs__elite_steppe (n=24)     12.14    11.01    12.14
```

`halberdier__vs__paladin`'s own halberdier side goes **+22.6 → +1.2 pts**.

### Blast radius

```
                          B2a vs base        AB vs base
ranged-vs-ranged        120/120 identical  120/120 identical
siege-bearing fights    500/500 identical  500/500 identical
canary families (4)      24/24 identical    24/24 identical
melee fights moved            81/83              64/83
mixed fights moved            15                 14      (all elite_fire_lancer,
                                                          a melee unit absent from
                                                          fight_sets.json's melee list)
```

`halberdier__vs__heavy_cav_archer` is ranged-vs-MELEE and was watched
specifically: it does **not** move. The halberdier's target is a ranged unit, so
E14's melee-vs-melee scope declines the bump before B2 is consulted — the same
gate that keeps `champion__vs__arbalester` at 6/6.

### Off-switch

`B2.resolverContactBump = false, stuckGatedBump = false`
(`calib_runner.mjs --b2 off`) reproduces `716a522` over the **whole corpus x 20
seeds, 4320/4320 files byte-identical** — not the 3-seed ranged-subset hash the
brief asked for, but the strictly stronger claim.

---

## 5. What this does not fix, stated plainly

* **v2 `champion__vs__paladin`'s +24.6 pt margin error.** It moves from +43.8 to
  +42.9 on its worst recording. The superior side's 0.79x share is the worst
  ratio on B1's board and neither report explains it.
* **v2 `paladin__vs__elite_steppe`.** Untouched by construction; its error is
  survivorship with an unmeasured mechanism.
* **`halberdier__vs__elite_elephant` overshoots** to 1.28x, and
  `halberdier__vs__heavy_camel` to 1.24x. The rule is now slightly too eager in
  halberdier fights specifically — the same unit B1 flagged as the common factor
  and could not attribute to a property.
* **Which halberdier property drives any of it** (3.0 s reload, 6 px infantry
  body, extreme count ratio). Still unseparated; still needs a per-property A/B.
* **`parity_check.mjs` is red**, as it was at `716a522` before any edit here
  (verified by checking the base engine out and running it). The golden panel is
  stale; B2 is a deliberate melee behaviour change and would fail it regardless.

---

## Artifacts

| what | where |
|---|---|
| off-switch object + derivation | `apps/website/static/js/engine/constants.js` (`B2`) |
| the contact test | `apps/website/static/js/engine/battle_unit.js` `meleeBumpRetarget` |
| the contact event | `apps/website/static/js/engine/sim.js` `resolveCollisions` |
| the stuck latch | `battle_unit.js` `moveTowardTarget` (`meleeStuckOn`) |
| tests (28) | `tests/js/engine/b2_bump_contact.test.mjs` |
| harness flag | `calib_runner.mjs --b2 off\|resolverContactBump[,stuckGatedBump]` |
| base / B2a / AB run dirs | `D:/AI/aoe2_golden/simruns_b2_{base,on,ab}` |
| off-switch identity run | `D:/AI/aoe2_golden/simruns_b2_off2` |
| probe runs + reports | `D:/AI/aoe2_golden/b2_probe_{base,on,ab}`, `b2_report_{base,on,ab}.txt` |
