# D1 — the siege round: what the 25 scorpion/onager recordings do that the engine does not

**Measurement only.** No engine file was touched (`git diff HEAD -- apps/website/static/js/engine/` is
empty). Everything below is tape-vs-engine, engine run fresh off `bb2e6fa` with no rule flags, 20 seeds
per fight, tapebox arena.

**Reproduce**

```
node tools/simjs/ranged_shot_dump.mjs --tags <the 25 siege tags> --seeds 20 \
     --out-dir D:/AI/aoe2_golden/shots_d1_siege
D:/miniconda3/python.exe tools/simjs/d1_dat_audit.py \
     --dat "…/AoE2DE/resources/_common/dat/empires2_x2_p1.dat" \
     --json D:/AI/aoe2_golden/d1_dat_audit.json
D:/miniconda3/python.exe tools/simjs/d1_siege_forensics.py --section all \
     --sim-runs-dir D:/AI/aoe2_golden/shots_d1_siege --json D:/AI/aoe2_golden/d1_siege_forensics.json
```

**Scope.** 25 manifest fights have `heavy_scorpion` or `siege_onager` on at least one side — 12 with a
scorpion, 12 with an onager, 1 (`heavy_scorpion__vs__siege_onager`) with both. There is no
mangonel-line recording in the corpus. None of the 25 is quarantined. Every family is a **single
recording**; the re-record flags are in §8.

---

## 0. How a shot is reconstructed (and why the old method could not see this round)

`ranged_fire_forensics` reconstructs a shot as *launch → impact*, then pairs it to the one damage event
nearest that impact. That is correct for an arbalester and structurally wrong for both siege units:

* a **scorpion bolt does not stop**. On tape its missile track flies its full length while damage
  events fire at *different times* along the way. Missile −2 of `heavy_scorpion__vs__hussar`:
  launched t=1.026 at (4.5, 6.808), still moving at t=2.864 at (4.5, 15.89) — and it damaged unit 1607
  for 9.0 at t=1.488, unit 1605 for 4.5 at t=1.902, and unit 1622 for 4.5 at t=2.016. Nearest-impact
  pairing would have kept one of those three.
* an **onager fires ten projectiles per shot**, not one — see §4.

`tools/simjs/d1_siege_forensics.py` therefore attributes a damage event to the missile whose *track
position at the instant of the event* is nearest the victim, among that shooter's missiles that were
airborne then. The pairing is audited, not assumed (`--section pair`): 3,242 / 3,956 tape damage events
attribute (the remainder are melee swings, which have no missile at all), with a residual — victim
distance from the bolt at that moment — of **median 0.34 tiles, max 0.52** on the scorpion side and
**median 0.61, max 2.04** on the onager side (the onager number is a blast radius, not an error).

---

## 1. THE BOARD — ranked residuals

24/25 winners agree. Mean |HP error| **6.42 on the siege side, 13.87 on the opponent side**.

| tag | siege | tape win | eng win% | side1 (tape→eng, err) | side2 (tape→eng, err) | mean abs |
|---|---|---|---|---|---|---|
| hand_cannoneer__vs__heavy_scorpion | scorp | 3 | **5.0 FLIP** | HC 0.0→23.5 (+23.5) | scorp 42.1→0.2 (**−42.0**) | 32.8 |
| halberdier__vs__siege_onager | onager | 3 | 100 | onager 0.0→0.0 (0.0) | halb 79.9→31.3 (**−48.6**) | 24.3 |
| imp_elite_skirm__vs__heavy_scorpion | scorp | 3 | 100 | skirm 0.0→0.0 (0.0) | scorp 70.8→31.1 (**−39.7**) | 19.9 |
| elite_fire_lancer__vs__siege_onager | onager | 3 | 100 | onager 0.0→0.0 (0.0) | EFL 56.1→19.9 (−36.2) | 18.1 |
| siege_onager__vs__elite_elephant | onager | 3 | 100 | onager 0.0→0.0 (0.0) | eleph 14.7→47.1 (**+32.3**) | 16.1 |
| champion__vs__heavy_scorpion | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | champ 87.5→60.2 (−27.3) | 13.7 |
| arbalester__vs__heavy_scorpion | scorp | 3 | 100 | arb 0.0→0.0 (0.0) | scorp 38.0→11.0 (−27.0) | 13.5 |
| heavy_scorpion__vs__heavy_camel | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | camel 54.5→79.7 (+25.2) | 12.6 |
| siege_onager__vs__heavy_camel | onager | 3 | 100 | onager 0.0→0.0 (0.0) | camel 64.1→40.1 (−24.0) | 12.0 |
| arbalester__vs__siege_onager | onager | 3 | 100 | arb 0.0→0.0 (0.0) | onager 22.3→45.7 (+23.4) | 11.7 |
| siege_onager__vs__hussar | onager | 3 | 100 | onager 0.0→0.0 (0.0) | huss 40.3→61.5 (+21.2) | 10.6 |
| champion__vs__siege_onager | onager | 3 | 100 | onager 0.0→0.0 (0.0) | champ 36.8→18.8 (−17.9) | 8.9 |
| imp_elite_skirm__vs__siege_onager | onager | 3 | 100 | skirm 0.0→0.0 (0.0) | onager 78.6→61.9 (−16.7) | 8.3 |
| elite_fire_lancer__vs__heavy_scorpion | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | EFL 58.8→71.2 (+12.4) | 6.2 |
| siege_onager__vs__paladin | onager | 3 | 100 | onager 0.0→0.0 (0.0) | pala 33.7→45.7 (+12.0) | 6.0 |
| heavy_cav_archer__vs__heavy_scorpion | scorp | **2** | 100 | HCA 20.1→31.8 (+11.7) | scorp 0.0→0.0 (0.0) | 5.8 |
| heavy_scorpion__vs__elite_elephant | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | eleph 61.3→50.4 (−10.8) | 5.4 |
| heavy_scorpion__vs__hussar | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | huss 80.8→88.6 (+7.7) | 3.9 |
| halberdier__vs__heavy_scorpion | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | halb 68.8→61.5 (−7.3) | 3.6 |
| heavy_scorpion__vs__elite_steppe | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | steppe 75.1→81.7 (+6.6) | 3.3 |
| hand_cannoneer__vs__siege_onager | onager | 3 | 100 | HC 0.2→0.0 (−0.2) | onager 60.2→64.2 (+4.0) | 2.1 |
| siege_onager__vs__elite_steppe | onager | 3 | 100 | onager 0.0→0.0 (0.0) | steppe 63.0→67.3 (+4.3) | 2.1 |
| heavy_scorpion__vs__paladin | scorp | 3 | 100 | scorp 0.0→0.0 (0.0) | pala 81.3→84.9 (+3.6) | 1.8 |
| heavy_scorpion__vs__siege_onager | both | 3 | 100 | scorp 0.0→0.0 (0.0) | onager 53.8→50.2 (−3.6) | 1.8 |
| heavy_cav_archer__vs__siege_onager | onager | 3 | 100 | HCA 0.0→0.0 (0.0) | onager 57.3→58.6 (+1.2) | 0.6 |

Split by family:

| family | n | winners | mean abs err, siege side | mean abs err, opponent side |
|---|---|---|---|---|
| heavy_scorpion | 12 | 11/12 | **9.06** | 11.34 |
| siege_onager | 12 | 12/12 | **3.77** | **16.39** |

**The two families fail differently.** The scorpion's own HP is the worse of its two columns — the
engine's scorpions *die* when the tape's survive (−42.0, −39.7, −27.0). The onager's own HP is nearly
perfect (3.77); its error is entirely on the other side of the board — the engine either over-kills the
opponent (halberdier −48.6, fire lancer −36.2, camel −24.0) or under-kills it (elephant +32.3,
hussar +21.2). Both patterns are traced to their mechanisms in §3 and §4.

### 1b. Siege-side output, decomposed (fire rate × damage-per-shot)

`dps_x = rate_x × shot_x`, engine ÷ tape:

| family | rate_x (shots per unit-minute) | shot_x (damage per shot) | dps_x |
|---|---|---|---|
| heavy_scorpion | **0.98** | **0.76** | 0.78 |
| siege_onager | **1.23** | 0.91 | 1.13 |

* the scorpion's **cadence is already right**; its **damage per shot is 24% short**. That is one number
  and §3 says exactly where it comes from.
* the onager's **damage per stone is 9% short** but it fires **23% too often**, and the two partly
  cancel in the score. The worst per-fight cases are `siege_onager__vs__elite_elephant`
  (shot_x 0.54 — 181.9 damage per tape stone vs 98.8 in the engine) and `siege_onager__vs__hussar`
  (shot_x 0.46).

---

## 2. PASS-THROUGH — what the tape actually does

### 2.1 The damage law: exactly two tiers, and it is NOT distance

Over all 13 scorpion recordings, 1,510 attributed damage events:

| damage / that fight's full hit | events | share |
|---|---|---|
| 1.000 | 403 | 26.7% |
| **0.500** | **1041** | **68.9%** |
| everything else | 66 | 4.4% — every one an HP-clamped killing blow |

There is nothing between the two values. And **no bolt in the corpus ever has more than one
full-damage victim** — the per-bolt histogram of full-tier hits is `{0: n, 1: m}` in all 13 fights,
never `{2: …}`.

The law is therefore:

> a scorpion bolt pays **100%** to its aim target and **exactly 50%** to every other body it passes
> through.

**It is not distance-dependent.** Bucketed by how far the bolt had already flown when it hit the body:

| tiles flown | n | mean damage / full |
|---|---|---|
| 0–2 | 49 | 0.4915 |
| 2–4 | 130 | 0.4917 |
| 4–6 | 203 | 0.4932 |
| 6–8 | 300 | 0.4815 |
| 8–10 | 363 | 0.4850 |
| 10–12 | 40 | 0.5000 |

Flat at 0.5 out to 12 tiles (the sub-0.5 means are the HP-clamped kills in each bucket; 94–100% of
events in every bucket are *exactly* 0.500×). The full-tier column is likewise flat at ~1.0. **The
user's recollection that scorpion damage varies with distance is not what these recordings show** —
what varies is *which* body is the aim target, and everything else is a flat half.

**Independently corroborated.** The AoE2 wiki's pass-through page states the same rule the tape shows:
"only the targeted unit gets full damage; all other units hit only get half damage", and that range
upgrades "also increase the extra range that the projectile travels and deals pass-through damage in".
One community phrasing describes the secondary hit as *half attack against half armour* rather than
half of the net damage — algebraically identical (`(A−D)/2 ≡ A/2 − D/2`), and the two differ only at
the minimum-damage clamp, which no event in this corpus reaches.
([wiki](https://ageofempires.fandom.com/wiki/Pass-through_damage))

### 2.2 How many bodies, and where

| | tape | engine |
|---|---|---|
| victims per bolt that landed | **2.56** | 2.00 (hard ceiling: 1 primary + 1 pass-through) |
| max victims on one bolt | **10** (`imp_elite_skirm__vs__heavy_scorpion`) | 2 |
| bolts that hit >1 body | 28.6–95.8% by fight, ~65% typical | 96.8–100% (by construction) |
| non-primary share of scorpion **damage** | **53.3%** | 28.6% |
| non-primary share of damage **events** | 71.8% | 50% |

Corridor geometry — perpendicular distance from the bolt's own launch→end line to the victim's centre:

| source | tier | n | perp median | p90 | p99 | max |
|---|---|---|---|---|---|---|
| tape | full (aim target) | 425 | 0.019 | 0.237 | 0.450 | 0.635 |
| tape | half (passed through) | 1085 | 0.213 | 0.391 | 0.569 | **0.837** |
| engine | full | 12347 | 0.000 | 0.134 | 0.308 | 0.370 |
| engine | half | 13161 | 0.717 | 1.110 | 3.244 | **6.765** |

The tape's corridor **scales with the victim's body**, and nothing else:

| victim collision_size | fights | perp p99 |
|---|---|---|
| 0.20 (champion, halb, arb, skirm, EFL, HC) | 6 | 0.373 – 0.406 |
| 0.25 (HCA, elephant, steppe, camel, hussar, paladin) | 6 | 0.458 – 0.665 |
| 0.50 (siege onager) | 1 | 0.837 |

i.e. **half-width ≈ victim radius + ~0.2 tiles** (the projectile's own `collision_x` is 0.1; the rest is
10 Hz position-sampling slack). It is a *line* test against the body, not a radius around a point.

The engine's pass-through victim is picked as *the nearest living enemy to the target, in any
direction* (`battle_unit.js`, the `passThroughPercent` block — the loop has no directional term
despite the comment saying "behind target"). Measured consequence: only **20.6%** of its pass-through
victims sit inside the tape's ≤0.5-tile corridor, 17% are not even within 1.0 tile of the line, and one
was 6.77 tiles off it.

### 2.3 Overshoot — the bolt does not stop at its target

| | tape | engine |
|---|---|---|
| tiles the bolt travelled *past* the body it paid full damage to (median) | **5.07** | **0.00** |
| p90 | 7.18 | 0.10 |
| bolts with at least one further victim past that body | 58.6% | 87.5% (its single extra victim is placed near the target, not past it) |

The tape's bolt flies a **near-constant ~10.6 tiles** from the muzzle regardless of how far the target
is (n=647: median 10.56, p10 9.45, p90 10.66; 271/647 land in the single 10.6 bin), truncated only when
it reaches the arena wall. The unit's own range is 8. **The bolt overruns its own maximum range by
~2.6 tiles and keeps damaging bodies the whole way.** The engine's projectile terminates at the aim
point, so `along/flight = 1.000` for every engine victim.

Median spacing between consecutive victims on the same tape bolt: **0.54 tiles** (p10 0.14, p90 1.32) —
i.e. the bolt is threading a packed column.

### 2.4 The engine's fraction is also wrong

Dict `pass_through_percent = 0.4286` (= projectile attack 6 ÷ unit attack 14, derived by the pipeline),
applied as `Math.max(1, Math.floor(damage * 0.4286))`. Against a Persian Hussar that is
`floor(9 × 0.4286) = 3`, i.e. **0.333× full**. The tape pays **0.500× full, unfloored** (4.5).
Engine tier histogram confirms it: 45.4% of engine scorpion events at 1.000 and the modal
pass-through value at 0.333.

### 2.5 Quantified: this one mechanic is the whole scorpion deficit

Full-damage-equivalents delivered per landed bolt:

* tape: `1 × 1.0 + 1.56 × 0.5 = 1.78`
* engine: `1 × 1.0 + 1.00 × 0.333 = 1.333`

ratio **1.335**. Measured engine ÷ tape damage per scorpion shot is **0.76**. `0.76 × 1.335 = 1.01`.
The scorpion's entire 24% damage-per-shot deficit is accounted for by (victim count × fraction) with
nothing left over — fire rate is already 0.98.

---

## 3. ONAGER — a shot is TEN projectiles, and the blast is one disc

### 3.1 The ten-projectile structure (new, and the reason every prior onager count was 10× off)

Every siege-onager shot launches **ten missiles on the same frame from the same unit**:

* 1 × master **656** — *Projectile Mangonel (Primary)*, the unit's own `projectile_unit_id`;
* 9 × master **369** — *Projectile Mangonel (Secondary)*.

Counts are exact: `champion__vs__siege_onager` 6 primary / 54 secondary; `arbalester__vs__siege_onager`
19 / 171. Ratio 9.000 everywhere. A naive missile count therefore reports 60 "onager shots" where the
onagers fired 6.

Debris geometry (n=1,566 fragments, offsets relative to the primary stone's landing point, along the
firing direction):

| offset from stone | median | p90 | max | forward component | lateral |
|---|---|---|---|---|---|
| 0.628 | | 0.954 | 2.033 | median +0.039, range −1.96 … +1.90 | median −0.010, p90 \|lat\| 0.723 |

So the fragments scatter roughly isotropically inside ~1 blast radius of the stone, land 0.016 s later
on median, and — critically — **each fragment that lands on a body deals exactly 1.00 damage** (the
minimum-damage floor; the master-369 unit's `type_50.attacks` is empty). Mean 0.37–3.2 such 1-damage
"chip" events per stone depending on how packed the crowd is. They are cosmetically important and
numerically negligible.

**The damage is one disc centred on the primary stone**, not ten little ones. Proof: the damage-vs-
distance curve is monotone in the distance to the *primary's* landing point and is not monotone in the
distance to the *nearest fragment's* landing point. (Example, `siege_onager__vs__hussar` stone at
t=0.94: 73.00 at 0.25 from the stone, 60.00 at 0.53, 50.82 at 0.80, 44.66 at 0.94, 39.23 at 1.03,
29.00 at 1.22, 26.11 at 1.21, 22.02 at 1.34, 17.10 at 1.48, 5.76 at 1.68 — while distance to nearest
fragment for the same events runs 0.55, 0.28, 0.45, 1.19, 0.31, 1.28, 0.72, 0.21, 1.65, 1.22.)

### 3.2 The blast profile vs E4's linear falloff — E4 is RIGHT IN SHAPE, ~8% TOO STEEP

E4 shipped `frac = 1 − (dist − victim_radius)/1.5`, floored at 1 damage. Regressing the tape's
non-kill events (n=470, edge distance = dist − the victim's own `collision_size`):

```
frac = 1.0728 − 0.6436 × edge      →  full damage out to edge 0.113, ZERO at edge 1.667
E4:   frac = 1.0000 − 0.6667 × edge →  full damage out to edge 0.000, zero at edge 1.500
```

Residual of the shipped rule, observed − predicted:

| edge distance (tiles) | n | observed frac | E4 predicted | diff |
|---|---|---|---|---|
| −0.2 … 0.2 | 16 | 0.994 | 0.959 | +0.035 |
| 0.2 … 0.5 | 46 | 0.847 | 0.761 | **+0.086** |
| 0.5 … 0.8 | 64 | 0.649 | 0.555 | **+0.094** |
| 0.8 … 1.1 | 113 | 0.465 | 0.358 | **+0.107** |
| 1.1 … 1.4 | 154 | 0.257 | 0.149 | **+0.108** |
| 1.4 … 1.8 | 76 | 0.100 | 0.025 | +0.075 |

Mean residual **+0.095**, median **+0.063**. The *shape* is confirmed (linear, floored at 1) — E4's
central finding stands. The *slope* is ~4% too steep and, more importantly, the zero point is at
**1.667 tiles beyond the body edge, not 1.500**, so the engine pays every off-centre unit 6–11
percentage points of full damage too little. That is the mechanical source of the onager's
`shot_x = 0.91`, and of the two big under-kill rows (elephant +32.3, hussar +21.2) where victims are
large and clumped and therefore mostly sit at edge 0.8–1.4.

Side-by-side, damage/full by distance from the stone (kills included, so the near band is depressed by
HP clamping on both sides):

| dist from stone | tape n | tape frac | engine n | engine frac |
|---|---|---|---|---|
| 0.00–0.25 | 7 | 0.731 | 1700 | 0.691 |
| 0.25–0.50 | 51 | 0.786 | 615 | 0.838 |
| 0.50–0.75 | 64 | 0.763 | 1188 | 0.633 |
| 0.75–1.00 | 93 | 0.627 | 1590 | 0.602 |
| 1.00–1.25 | 109 | 0.491 | 2466 | 0.516 |
| 1.25–1.50 | 116 | 0.337 | 2246 | 0.298 |
| 1.50–1.75 | 134 | 0.159 | 1100 | 0.121 |
| 1.75–2.00 | 34 | 0.170 | 40 | 0.115 |
| 2.00–2.50 | 3 | 0.099 | 0 | — |

Note the tape's tail: **37 events beyond 1.75 tiles** (p99 1.95, furthest **2.05**, still doing 2.6–8.6
damage). The engine's disc stops dead at `splashRadius + enemy.radius` = 1.75 and has 40 events in that
band against the tape's 37 at a third of the sample size.

Victims per landed stone, corpus mean: **tape 5.24, engine 5.94**.

### 3.3 Friendly fire

**The tapes show essentially none.** Across all 25 recordings and 3,956 damage events there are exactly
**2** events whose attacker and victim share an owner: `siege_onager__vs__paladin`, 53.6 damage,
1 kill (1.45% of that fight's events). Every other recording is 0. The engine produces 0.

So the game-lore expectation "onagers hit their own units" is **not visible in this corpus at the rate
one would expect** — with 8 onagers firing into a melee at 1.5-tile blast, two events in 25 fights is
close to nothing. Two readings are possible and this corpus cannot separate them: (a) the recorder's
capture only streams cross-owner damage except in rare cases, or (b) these particular engagements kept
the onagers behind their own line. Either way, **implementing friendly fire has no support in the
measurement**, and the dat's `blast_attack_level = 1` on Onager/Siege Onager (vs 2 on Mangonel and on
the Onager Ship) is the only evidence pointing the other way. Flag for a dedicated re-record if the
main session wants this.

### 3.4 Flight time, arc, range

| | tape | engine |
|---|---|---|
| stone flight time, median (s) | 1.56 – 2.58 by fight | 1.15 – 2.30 |
| shot range (muzzle → the body that took full damage), median | 4.0 – 9.6 | 4.8 – 8.4 |

The engine's stone is consistently **faster in the air** in the close-range fights (e.g. hussar
1.58 s tape vs 1.23 s engine; camel 1.88 vs 1.16) even though its median range is slightly *shorter*.
The dat has `projectile_arc = 0.4` on projectile 656, which the combat dict does not carry and no
engine models: a lobbed stone travels a longer path than the straight line the engine flies, which is
exactly the sign of the discrepancy. Scorpion projectile 627 has `projectile_arc = 0.0` and its tape
flight times match a straight 6.0 tiles/s.

### 3.5 Minimum range — not a gap

Measuring each shot's range as the muzzle-to-**aim-target** distance (not muzzle-to-first-victim; a
pass-through bolt aimed 8 tiles away routinely damages something 1 tile away first, and scoring that as
a 1-tile shot invents violations that never happened):

* onager (`min_attack_range` 3.0): **0.0%** of tape shots inside min range in all 12 fights; engine
  0.0%. Engine minimum observed 3.00.
* scorpion (min 2.0): 0.0% in 10 of 13 fights; 7.7% / 6.7% / 2.0% in `champion__vs__heavy_scorpion`,
  `heavy_scorpion__vs__hussar`, `heavy_scorpion__vs__heavy_camel` — a handful of shots at 1.5–1.8 tiles,
  consistent with the aim target closing during the 0.1 s attack delay. Engine 0.0%.
* the engine *does* fire slightly **beyond** max range (effective reach = range + both radii):
  2.5–19.4% of shots in the ranged matchups. Small, and the same rule every ranged unit uses.

**Verdict: the min-range dead zone is not a siege-round problem.**

---

## 4. THE OPPONENT SIDE — cadence, not damage

`dps_x = cad_x × dph_x`, engine ÷ tape, for the non-siege side of each fight (full table in
`--section opponent`). **`dph_x` (damage per landed hit) is exactly 1.00 in 19 of 24 fights.** The
engine and the game agree about what one swing is worth; they disagree about how many swings happen.

Worst opponent rows and where the error sits:

| tag | opp | dps_x | cad_x | dph_x | reading |
|---|---|---|---|---|---|
| hand_cannoneer__vs__siege_onager | HC | 1.99 | **1.90** | 1.05 | cadence |
| heavy_cav_archer__vs__siege_onager | HCA | 1.90 | **1.90** | 1.00 | cadence |
| hand_cannoneer__vs__heavy_scorpion | HC | 1.40 | **1.24** | 1.13 | cadence (+ a little dph) |
| elite_fire_lancer__vs__heavy_scorpion | EFL | 1.38 | **2.06** | 0.67 | charge mechanic, not siege |
| halberdier__vs__heavy_scorpion | halb | 0.49 | **0.49** | 1.00 | cadence |
| halberdier__vs__siege_onager | halb | 0.50 | **0.50** | 1.00 | cadence |
| heavy_scorpion__vs__elite_elephant | eleph | 0.50 | **0.48** | 1.05 | cadence |
| siege_onager__vs__elite_elephant | eleph | 0.59 | **0.59** | 1.00 | cadence |
| siege_onager__vs__heavy_camel | camel | 0.60 | **0.60** | 1.00 | cadence |
| champion__vs__heavy_scorpion | champ | 0.60 | **0.60** | 1.00 | cadence |

**Decomposition verdict.** The opponent-side error in this round is a **contact/cadence** error, i.e.
the chase-and-approach family from B1/B2/C1/C2 — not a siege mechanic. The melee opponents
(halberdier, champion, elephant, camel) all land **~half** the swings per unit-second the tape does,
with first-blood arriving *later* in the engine (halberdier 5.57→7.78 s, champion 6.57→6.37 s,
elephant 6.11→4.67 s) and a lower share of units ever swinging (halberdier 0.76→0.76, champion
0.67→0.67 — the fraction is right, the *rate* is not). The ranged opponents (HC, HCA) show the mirror
image: **~1.9× too many** shots per unit-second against onagers.

Two caveats that do belong to this round:

1. `cad_x` and the siege mechanics are coupled. A tape onager that kills 6 halberdiers per stone
   removes 6 swingers; an engine onager that kills 6.4 removes more. The halberdier's `cad_x = 0.50`
   is *partly* the engine's onager being too lethal (that fight's siege side is 0.0 vs 0.0, so the
   error shows up only on the halberdier column).
2. The elite fire lancer's `dph_x = 0.53–0.67` is the only genuine damage-per-hit gap in the round, and
   it is the charge-volley mechanic, not siege.

---

## 5. DURATION — the tail correction applies cleanly

Every one of the 25 recordings wipes a side. Recorder tail (stream length − wipe time) is **10.6 –
22.1 s, median ~15 s**, exactly the 17–20 s band `ranged_fire_forensics` established on the ranged
corpus. Using the manifest's `duration_s` would make the engine look 0.30–1.65× the tape's length; using
the true wipe:

* engine/wipe ratio: **mean 1.28, median 1.23, min 0.46, max 2.22**

Slowest engine fights (ratio ≫ 1): `imp_elite_skirm__vs__heavy_scorpion` 2.22,
`halberdier__vs__heavy_scorpion` 2.04, `halberdier__vs__siege_onager` 2.00,
`heavy_scorpion__vs__elite_elephant` 1.98. Fastest (ratio ≪ 1): `hand_cannoneer__vs__siege_onager`
0.46, `heavy_cav_archer__vs__siege_onager` 0.51. The slow tail is the same cadence deficit as §4 (a
fight in which everyone swings half as often takes twice as long); the fast tail is the ranged
opponents shooting 1.9× too fast.

**No duration artefact specific to siege.** The correction applies cleanly and no recording needs a
special rule.

---

## 6. DAT vs COMBAT DICT — what the pipeline carries and what it drops

Read from a live install via `tools/simjs/d1_dat_audit.py`. Unit ids: Scorpion 279 (`SCBAL`),
Mangonel 280 (`MANGO`), Heavy Scorpion **542** (`HWBAL`), Onager 550 (`ONAGR`), Siege Onager **588**
(`SNAGR`).

| dat field | Heavy Scorpion (542) | in dict? | Siege Onager (588) | in dict? |
|---|---|---|---|---|
| `max_range` | 7.0 | ✔ 8.0 (post-upgrade) | 8.0 | ✔ 9.0 |
| `min_range` | 2.0 | ✔ 2.0 | 3.0 | ✔ 3.0 |
| `reload_time` | 3.6 | ✔ | 6.0 | ✔ |
| `frame_delay`/60 | 0.100 | ✔ | 0.0 | ✔ |
| `accuracy_percent` | 100 | ✔ | 100 | ✔ |
| `accuracy_dispersion` | 0.0 | **✗ no column** | 0.0 | **✗ no column** |
| `blast_width` | 0.0 | ✔ (`splash_radius` 0) | 1.5 | ✔ (`splash_radius` 1.5) |
| **`blast_attack_level`** | **3** | **✗ no column** | **1** | **✗ no column** |
| `blast_damage` | 1.0 | ✔ (`splash_on_hit_fraction`) | 1.0 | ✔ |
| projectile unit | 627 | — | 656 | — |
| projectile `speed` | 6.0 | ✔ | 3.5 | ✔ |
| **projectile `projectile_arc`** | 0.0 | **✗ no column** | **0.4** | **✗ no column** |
| projectile `hit_mode` | **1** | **✗ no column** | 0 | **✗ no column** |
| projectile `vanish_mode` | **1** | **✗ no column** | 0 | **✗ no column** |
| projectile `smart_mode` | 0 | ✗ | 0 | ✗ |
| projectile `area_effect_specials` | 0 | ✗ | 0 | ✗ |
| projectile `collision_x` | 0.1 | **✗ no column** | 0.1 | **✗ no column** |
| projectile `type_50.attacks` | `{11:4, 5:6, 3:6, 17:1, 1:2}` | folded into `pass_through_percent = 0.4286` | `[]` (empty) | `pass_through_percent = 0` |
| `secondary_projectile_unit` | (none) | — | **369, ×9 per shot** | **✗ nothing carries it** |
| — | — | `pass_through_count = 3` (not a dat field; JS ignores it) | — | `pass_through_count = 1` |

**The drop list, ranked by how much this round's error it explains:**

1. **`blast_attack_level` is not carried at all.** 3 on the scorpion, 1 on both onagers, 2 on the
   Mangonel and the Onager Ship. (This repo's own `ability_registry.py` already encodes the convention
   — `level 3 & multi-class secondary attacks → pass_through`, `level 2 & 0<blast_damage<1 → trample`,
   `level 11 → grenadier splash`, `level 162 → conical` — so the *classifier* reads it while no
   *column* survives.) The engine instead infers the family from `splash_radius > 0` vs
   `passThroughPercent > 0`, which happens to work for these two but carries no information about the
   *shape* of the effect — line vs disc — which is the entire scorpion problem.
2. **`pass_through_percent = 0.4286` is a derived quantity, and it is wrong.** It is
   `projectile attack (6) ÷ unit attack (14)`. The tape says the pass-through fraction is exactly
   **0.5**, unfloored, and is *not* a function of the projectile's own attack table. `blast_damage`
   is 1.0 for the scorpion and the dict maps that to `splash_on_hit_fraction`, so the one dat field
   that could plausibly encode the pass-through fraction is being spent on a different column.
3. **`pass_through_count`** exists in the dict (3) and is documented as unused by the JS engine —
   which pins the engine at 1. The tape's real cap, if there is one, is ≥ 10.
4. **The nine secondary projectiles are invisible to the pipeline.** `secondary_projectile_unit` *is*
   extracted (`extract_units.py` line 442) but no dict column survives for the onager, so the engine
   has no idea a stone is a ten-body event. Numerically this is a 1-damage-per-fragment effect, but it
   is the reason every raw missile count on the onager side is 10× off.
5. **`projectile_arc = 0.4`** — no column, no engine term. Directly matches the observed
   too-short stone flight times (§3.4).
6. **`hit_mode` / `vanish_mode`** — **1 / 1** on the scorpion bolt (627) vs **0 / 0** on the stone (656).
   The Genie modding documentation is explicit that **`vanish_mode = 1` is what makes a projectile pass
   through units**, with `hit_mode = 1` stopping it on an obstacle such as a building. This is the dat's
   own boolean for the entire §2.3 overshoot behaviour, it is set correctly on exactly the one unit that
   needs it, and nothing in this repo reads it. Related: `blast_attack_level` on the *unit* is compared
   against each target's *blast defense level* to decide which bodies a passing projectile can collide
   with — a second field pair the pipeline does not carry.
   ([AGE wiki](https://agecommunity.fandom.com/wiki/Units),
   [SWGB Heaven](https://swgb.heavengames.com/cgi-bin/forums/display.cgi?action=st&fn=10&tn=11998))
7. `accuracy_dispersion = 0.0` on both — carried by neither, but genuinely zero here, so no effect
   this round (unlike the ranged corpus).
8. Projectile `collision_x = 0.1` — no column. It is the other half of the pass-through corridor
   half-width in §2.2.

---

## 7. VERDICTS

| # | question | verdict |
|---|---|---|
| 1 | the board | 24/25 winners. Siege side mean \|err\| 6.42, opponent side 13.87. Scorpion family carries its error on **its own** HP (9.06); onager family carries it on the **opponent's** (16.39). |
| 2 | does the tape's scorpion bolt hit multiple units? | **Yes — 2.56 bodies per landed bolt, up to 10.** Engine ceiling is 2. |
| 2 | geometry of multi-victim events | **Collinear.** Victims sit ≤ (victim radius + ~0.2) tiles off the bolt's own line — p99 0.373–0.837 scaling exactly with the victim's `collision_size`. Median spacing 0.54 tiles. |
| 2 | damage as a function of position along the path | **No dependence.** Two tiers only: 1.00× for the aim target, exactly 0.500× for everything else, flat from 0 to 12 tiles flown. The "damage varies with distance" recollection is not supported. |
| 2 | overshoot | **Confirmed and large.** The bolt flies a near-constant ~10.6 tiles — 2.6 beyond the unit's own 8-tile range — and keeps damaging bodies for a median 5.07 tiles *past* the one it paid full damage to. The engine's projectile stops at the aim point (0.00). |
| 2 | fraction of tape scorpion damage that is non-primary | **53.3%** of damage, 71.8% of events. Engine: **28.6%** / 50%, and its one extra victim is chosen by proximity to the target in any direction — only 20.6% of them are inside the tape's corridor. |
| 2 | is there really no pass-through in the engine? | **There is one** (`battle_unit.js` `passThroughPercent` block) — but capped at exactly 1 extra victim, at `floor(dmg × 0.4286)` = 0.333× instead of 0.5×, and with no directional constraint. Not "absent"; wrong on all three axes. |
| 3 | onager blast radius truth | Victims per landed stone tape **5.24** vs engine **5.94**. The disc reaches ~2.3 tiles from the stone on tape; the engine's stops at 1.75. |
| 3 | damage-vs-distance vs E4's linear falloff | **E4's shape is confirmed** (linear from full at the body edge, floored at 1) and **its slope is ~4% too steep**: measured zero point is **1.667 tiles** beyond the body edge, not 1.500. The shipped rule under-pays every off-centre unit by 6–11 pp of full damage (mean residual +0.095). |
| 3 | friendly fire | **2 events in 25 recordings** (one fight, 53.6 damage, 1 kill). No measurable support for implementing it; the dat's `blast_attack_level = 1` is the only contrary evidence. Needs a dedicated recording to settle. |
| 3 | minimum range | **Not a gap.** 0.0% of tape and engine onager shots inside min range; scorpion violations are 3 fights at 2–8%, all at 1.5–1.8 tiles, explained by target closure during the 0.1 s attack delay. |
| 3 | projectile flight time / arc | Engine stone is **too fast in the air** in close-range fights (1.16 vs 1.88 s median). `projectile_arc = 0.4` exists in the dat, is not carried, and is not modelled. |
| 4 | opponent-side decomposition | **Cadence, not damage.** `dph_x = 1.00` in 19/24. Melee opponents land ~half the tape's swings per unit-second; ranged opponents land ~1.9× too many. This is the B1/B2/C1/C2 contact family, *not* a siege mechanic — with the caveat that the engine's over-lethal onager blast removes swingers faster and therefore *contributes* to the melee half. |
| 5 | dat-vs-dict | 8 dropped fields, listed in §6. The two that matter: **`blast_attack_level` (the effect's SHAPE) is not carried at all**, and **`pass_through_percent` is a derived 0.4286 where the truth is a flat 0.5**. |
| 6 | duration / wipe | Tail 10.6–22.1 s, median ~15 s, every recording wipes. Correction applies cleanly; engine/wipe ratio mean 1.28, median 1.23. No siege-specific artefact. |

---

## 8. Tapes to flag for the re-record list

Every siege family is a single recording. These four should not be treated as gospel:

1. **`halberdier__vs__siege_onager`** — only **3 onager stones in the whole fight** (3 onagers,
   15.5 s to wipe; a 6 s reload predicts ~7). It is also the second-largest residual on the board
   (halberdier −48.6). Three stones is not enough to constrain either the blast or the cadence.
2. **`siege_onager__vs__heavy_camel`** — 8 onagers, 24.1 s, **8 stones**: roughly one shot per onager
   in four reload cycles. Predicted ~31. Either the onagers spent the fight walking, or the capture is
   short a segment.
3. **`siege_onager__vs__hussar`** — 4 onagers, 18.9 s, **5 stones** (predicted ~12), and it produces
   the corpus's most extreme `T_dmg/shot` (238.2, vs 45–180 elsewhere) off those 5 stones.
4. **`hand_cannoneer__vs__heavy_scorpion`** — the round's only wrong winner and its largest residual
   (−42.0 on the scorpion side). 21 Japanese hand cannoneers vs 13 Japanese heavy scorpions; the tape
   has the scorpions wiping the cannoneers and finishing at 42.1% HP, the engine has the reverse in
   19/20 seeds. Both mechanisms in this report push that way (scorpion `dps_x` 0.61, hand cannoneer
   `dps_x` 1.40 — a combined 2.3× swing), so it is probably *not* a bad tape; but it is the one fight
   whose verdict flips on a single recording, and a second capture would make the design safe.

`champion__vs__siege_onager` (6 stones from 4 onagers in 19.9 s, predicted ~13) is on the same
under-firing pattern as (1)–(3) but it is the recording E4's blast fit was built on and its curve is
internally clean, so it is listed here for awareness rather than suspicion.

---

## 9. Files

* `tools/simjs/d1_siege_forensics.py` — all measurements. Sections: `board`, `duration`, `pair`,
  `passthrough`, `blast`, `friendly`, `minrange`, `siegeout`, `opponent`, `dictgap`, `all`.
* `tools/simjs/d1_dat_audit.py` — dat reader for both siege lines and their projectiles.
* Engine runs: `D:/AI/aoe2_golden/shots_d1_siege` (25 fights × 20 seeds, `ranged_shot_dump.mjs`, no flags).
* Machine-readable dumps: `D:/AI/aoe2_golden/d1_siege_forensics.json`, `…/d1_dat_audit.json`,
  `…/d1_minrange.json`, `…/d1_siegeout.json`.
