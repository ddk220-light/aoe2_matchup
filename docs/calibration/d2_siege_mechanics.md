# D2 — the siege round: four rules built off the D1 forensics, all four shipped OFF

Implementation of the D1 measurements as engine rules. Everything below is measured on
`bb2e6fa` + the D2 commits, tapebox arena, 20 seeds, the same 25 siege recordings D1 used.

**Headline.** The scorpion's pass-through law (S1) reproduces every emergence quantity D1
measured — victims per bolt, the two-tier damage law, the corridor, the overshoot — and
its own-HP error improves. It is still shipped OFF, because the four fights it damages are
the four whose opponents are a packed melee blob, and D1 §4 had already shown that blob is
the B1/B2/C1/C2 cadence defect and not a siege problem. The onager's two rules (S2a blast
zero point, S2b arc) are each directionally right in isolation and cost the board; S2c
(debris) is the one rule the boards endorse, and it is the one that is not really a rule at
all — it is a dat fact the pipeline was dropping.

**Reproduce**

```
node tools/simjs/calib_runner.mjs --seeds 20 --d2 <spec> --out-dir <dir>
node tools/simjs/ranged_shot_dump.mjs --seeds 20 --tags-file <25 siege tags> \
     --d2 <spec> --out-dir <dir>
D:/miniconda3/python.exe tools/simjs/d1_siege_forensics.py --section all --sim-runs-dir <dir>
D:/miniconda3/python.exe -m aoe2x.calibration.score --all --sim-runs-dir <dir> --label <l>
```

`<spec>` is `off` or a comma list of `boltCorridor,blastZeroPoint,projectileArc,blastDebris`.

---

## 0. What the engine did before this round

| | file:line (at `bb2e6fa`) | behaviour |
|---|---|---|
| scorpion pass-through | `battle_unit.js:2525-2556`, inside `fireProjectile`'s `onHit` | `Math.max(1, Math.floor(damage * passThroughPercent))` to **one** victim — the nearest living enemy **to the target, in any direction**, despite the comment saying "behind target". `passThroughPercent` is the dict's derived `0.4286`, and the floor makes it 0.333x of full against a Persian Hussar. |
| onager blast | `battle_unit.js:2448-2491` | `falloff = 1 - (dist - enemy.radius)/splashRadius`, rounded, floored at 1, over enemies within `splashRadius + enemy.radius`. E4's rule; correct in shape. |
| projectile flight | `projectile.js:69-88` | straight line at the dat `speed` from muzzle to aim point, `onHit()` on arrival, then `done`. No arc term, no swept collision, no travel past the aim point. |
| the six dat fields | — | not carried. `blast_attack_level`, `projectile_arc`, `vanish_mode`, `hit_mode`, `secondary_projectile_unit` count and the projectile's own `collision_x` have no column anywhere in extraction → `ref_units` → combat dict. |

---

## 1. THE RULES AS BUILT

All four live in `constants.js`'s `D2` object with a `setD2()` harness entry point and a
`--d2 <spec>` CLI on `calib_runner.mjs` / `calib_worker.mjs` / `ranged_shot_dump.mjs`. **All
four default to `false`.**

### S1 `boltCorridor` — the bolt is a line

A unit with `pass_through_percent > 0` gets a `sweep` descriptor attached to its projectile
(`battle_unit.js`, after the `new Projectile(...)`; the flight itself is
`Projectile.updateSweeping`). The bolt:

* pays **1.00x** to its aim target at the aim point, through the *unmodified* arrival
  callback — same coordinates, same accuracy machinery, same tick;
* keeps flying to `BOLT_TOTAL_FLIGHT_TILES` = **10.6** tiles from the muzzle;
* pays **exactly 0.500x, unfloored**, of *that victim's own* post-armor damage to every
  other **enemy** body whose centre comes within `(its radius + the projectile's 0.1 tiles)`
  of the swept path, **once per bolt, with no cap**;
* sweeps **tick by tick against a segment**, not once at launch, because the tape's damage
  events on one bolt fire at different times along the flight (D1 §0).

The old 1-victim block is skipped when the corridor is live, not deleted.

### S2a `blastZeroPoint` — the ramp is longer than the blast radius

`falloff = 1 - edge / BLAST_FALLOFF_ZERO_TILES` with `BLAST_FALLOFF_ZERO_TILES = 1.667`, and
the reach test moves with it (a disc still paying at 1.6 tiles cannot stop at 1.5). Shape,
rounding and the 1-damage floor are E4's, untouched.

### S2b `projectileArc` — the stone is lobbed

`speed /= arcFlightFactor(projectile_arc)`. See §2 for the derivation.

### S2c `blastDebris` — nine fragments, one damage each

`BattleUnit.scatterBlastDebris`: nine landing points on a golden-angle spiral at
`r_k = R·sqrt((k+0.5)/9)`, `R = 1.0` tile, oriented by the shot's own heading. Each fragment
deals exactly 1 damage to the nearest body it overlaps, or nothing. **No rng draw** — the
spiral is an equal-area sample of the disc computed, not drawn, so this rule perturbs no
other consumer of `sim.rng` and its A/B is a comparison of the same battle.

### S3 — pipeline carriage

Six fields now read **dict-first, per-slug-dat-fallback**, the contract
`ACCURACY_DISPERSION_BY_SLUG` already uses: `projectile_arc`, `vanish_mode`, `hit_mode`,
`blast_attack_level`, `secondary_projectile_count`, `projectile_collision`. Maps live in
`constants.js` and are pinned only for `heavy_scorpion` and `siege_onager` — the two slugs
whose dat values were actually read. A unit with no entry gets no behaviour it would not
already have had.

---

## 2. DAT FINDINGS

Read from `D:/AI/aoe2_golden/d1_dat_audit.json` (D1's own dump of the live install).

### What supports the 10.6-tile flight: **nothing in the dat**

| candidate | value | verdict |
|---|---|---|
| HWBAL 542 `max_range` | 7.0 (dict 8.0 post-upgrade) | not 10.6 |
| projectile **627** `max_range` | **0.0** | the projectile carries no range of its own |
| projectile 628 / 1114 (the *fire* graphic variants) | 20.0 | not the unit that fires |
| stone 656 `max_range` | 25.0 | different line |
| `graphic_displacement` | [0.0, 0.2, 0.5] | muzzle offset, order of magnitude too small |

So `BOLT_TOTAL_FLIGHT_TILES = 10.6` is a **measured tape constant**, in E9's category, and
labelled as one in the source. D1 §2.3: median 10.56, p10 9.45, p90 10.66, 271 of 647 bolts
in the single 10.6 bin, independent of target distance. The honest limit is stated in the
comment: a corpus in which every scorpion is a range-8 Heavy Scorpion cannot separate
"range + 2.6" from "range × 1.32", and one recording of a non-upgraded Scorpion would.

What the dat **does** say, and it is worth having: projectile 627 carries
`vanish_mode = 1` — Genie's own boolean for "this projectile passes through units" — against
`0` on the stone 656, and `blast_attack_level = 3`, which this repo's `ability_registry.py`
already classifies as `pass_through`. Two independent dat witnesses that S1 belongs to
exactly the line it was applied to.

### The arc formula

The only primary-source statement found is the AoE2DE UGC Guide's attribute table, which
documents attribute 69 (Projectile Arc) as **"controls the maximum height of the fired
projectile"** — no formula. Taking that literally, with the apex as a fraction of the shot's
span and the dat `speed` as speed *along the path*:

```
apex h = arc x D,  k = 4 x arc
L = integral_0^D sqrt(1 + k^2 (1 - 2x/D)^2) dx = D x [ sqrt(1+k^2)/2 + asinh(k)/(2k) ]
```

`arcFlightFactor(0.4) = 1.3338`. Nothing is fitted; the number falls out of `arc = 0.4`.

Two checks that this is the right reading rather than a convenient one:

* the **absolute-height** reading (apex 0.4 *tiles*, not 0.4 × span) predicts a 2.6% longer
  flight at 4 tiles — two orders of magnitude too small for D1's 1.16 s → 1.88 s;
* the **ballistic** reading (constant horizontal speed, gravity solves the vertical)
  predicts flight time `D / speed` exactly — i.e. no change at all from today's engine,
  which the measurement rules out.

Measured effect (`E_flt_s`, median stone flight, base → S2b, tape in brackets): camel
1.16 → 1.43 [1.88], hussar 1.23 → **1.64** [1.58], paladin 1.15 → **1.49** [1.56], champion
1.16 → 1.53 [1.99], steppe 1.24 → 1.65 [1.83], elephant 1.36 → 1.60 [1.76]. The rule does
what it says.

---

## 3. EMERGENCE — every D1 quantity, base vs D2

| quantity (scorpion) | tape | engine base | engine D2-S1 |
|---|---|---|---|
| victims per bolt that landed | **2.56** | 2.00 (hard ceiling 2) | **2.42** |
| max victims on one bolt | 10 | 2 | **7** |
| non-primary share of scorpion DAMAGE | **53.3%** | 28.6% | **47.9%** |
| damage at the 0.500x tier, share of events | 68.9% | 22.0% (modal value 0.333x) | **62.7%** |
| damage at the 1.000x tier | 26.7% | 45.4% | **33.3%** |
| corridor, half-tier perp **p99** | 0.569 | **3.244** | **0.464** |
| corridor, half-tier perp **max** | 0.837 | **6.765** | **0.572** |
| bolt flight length, tiles | 10.31 – 10.63 | 2.97 – 8.10 | **10.6** everywhere |
| tiles travelled PAST the full-damage body (median) | 5.07 | **0.00** | **4.48** |
| extra victims past that body (mean) | 1.27 | 0.22 | **1.29** |
| bolts with a victim past the full-damage body | 58.6% | 21.5% | **67.0%** |

Every single one moves from the engine column to the tape column. The corridor discipline
number the brief asked for — D1's "only 20.6% of the engine's pass-through victims sit
inside the tape's ≤0.5-tile corridor" — is now **100%**: the engine's worst half-tier victim
is 0.572 tiles off the line against the tape's 0.837 envelope.

| quantity (onager) | tape | base | D2 |
|---|---|---|---|
| falloff zero point, tiles from the stone (0.2-tile body) | 1.954 (fitted, n=467) | 1.700 | **1.867** (S2a) |
| stone flight, close fights (s) | 1.56 – 1.99 | 1.15 – 1.24 | **1.43 – 1.64** (S2b) |
| victims per landed stone | 5.24 | 5.94 | 6.47 (S2a) |
| debris fragments per stone | 9.000 | 0 | **9** (S2c) |

**A tooling correction was required to see any of this.** `ranged_shot_dump.mjs` recorded a
missile as launch → *aim point*, and `d1_siege_forensics.attribute_engine` paired damage
events by `|t − impact_t|`. A corridor bolt's overshoot events fire seconds after its aim
point, so with the old probe the corridor read as **1.18** victims per bolt — *lower* than
the pre-D2 engine's 2.00 — purely because two thirds of its damage landed in the
unattributed bin. The probe now records the bolt's true end point and end time when the
engine attached a sweep, and the forensics models such a shot the way it already models a
TAPE bolt. A dump without those keys takes the original code path verbatim: the pre-D2 board
still prints 24/25, siege 6.42, opp 13.87, 9.06/11.34, 3.77/16.39 after the change.

---

## 4. THE SIEGE BOARD — 25 recordings x 20 seeds

```
cfg    winners   siege|err|  opp|err|   scorp:siege scorp:opp   onagr:siege onagr:opp
off      24/25         6.42     13.87          9.06     11.34          3.77     16.39
S1       24/25         6.12     15.94          8.47     15.48          3.77     16.39
S2a      22/25         8.58     15.79          9.06     11.34          8.11     20.23
S2b      24/25         6.93     19.55          9.06     11.34          4.80     27.75
S2c      24/25         6.42     13.35          9.06     11.34          3.77     15.36
S1+S2c   24/25         6.12     15.42          8.47     15.48          3.77     15.36
all      24/25         6.37     22.50          8.47     15.48          4.28     29.51
```

Per fight (mean |HP err|, pts):

```
tag                                        off      S1     S2a     S2b     S2c     all
hand_cannoneer__vs__heavy_scorpion        32.8    27.5    32.8    32.8    32.8    27.5
halberdier__vs__siege_onager              24.3    24.3    36.6    17.0    24.4    33.4
imp_elite_skirm__vs__heavy_scorpion       19.9    16.6    19.9    19.9    19.9    16.6
elite_fire_lancer__vs__siege_onager       18.1    18.1    34.6    19.1    18.1    18.8
siege_onager__vs__elite_elephant          16.1    16.1    10.5    32.9    16.1    31.6
champion__vs__heavy_scorpion              13.7    38.0    13.7    13.7    13.7    38.0
arbalester__vs__heavy_scorpion            13.5    13.3    13.5    13.5    13.5    13.3
heavy_scorpion__vs__heavy_camel           12.6     6.2    12.6    12.6    12.6     6.2
siege_onager__vs__heavy_camel             12.0    12.0    15.9    13.4    12.2    12.8
arbalester__vs__siege_onager              11.7    11.7    11.7     9.7    11.7    10.6
siege_onager__vs__hussar                  10.6    10.6     8.6    29.9    10.3    29.9
champion__vs__siege_onager                 8.9     8.9    33.8    20.2     3.3    18.8
imp_elite_skirm__vs__siege_onager          8.3     8.3     7.8     8.6     8.3     8.1
elite_fire_lancer__vs__heavy_scorpion      6.2     1.6     6.2     6.2     6.2     1.6
siege_onager__vs__paladin                  6.0     6.0     3.0    15.6     5.7    13.2
heavy_cav_archer__vs__heavy_scorpion       5.8     2.0     5.8     5.8     5.8     2.0
heavy_scorpion__vs__elite_elephant         5.4    15.4     5.4     5.4     5.4    15.4
heavy_scorpion__vs__hussar                 3.9     1.4     3.9     3.9     3.9     1.4
halberdier__vs__heavy_scorpion             3.6    17.9     3.6     3.6     3.6    17.9
heavy_scorpion__vs__elite_steppe           3.3     0.8     3.3     3.3     3.3     0.8
hand_cannoneer__vs__siege_onager           2.1     2.1     4.8     5.4     2.1     6.2
siege_onager__vs__elite_steppe             2.1     2.1     0.2    18.5     1.9    18.5
heavy_scorpion__vs__paladin                1.8     3.0     1.8     1.8     1.8     3.0
heavy_scorpion__vs__siege_onager           1.8     0.3     1.8     0.0     1.8     4.7
heavy_cav_archer__vs__siege_onager         0.6     0.6     2.5     5.2     0.6     0.9
```

### 4a. S1 — the split is completely clean, and it is not about the bolt

Eight of the twelve scorpion fights improve, four blow up, and the four are the same four
every time:

| improve (opponent is ranged, fast, or loose) | | worsen (opponent is a packed melee blob) | |
|---|---|---|---|
| elite_steppe | 3.3 → 0.8 | champion | 13.7 → **38.0** |
| heavy_cav_archer | 5.8 → 2.0 | halberdier | 3.6 → **17.9** |
| hussar | 3.9 → 1.4 | elite_elephant | 5.4 → **15.4** |
| elite_fire_lancer | 6.2 → 1.6 | paladin | 1.8 → 3.0 |
| heavy_camel | 12.6 → 6.2 | | |
| imp_elite_skirm | 19.9 → 16.6 | | |
| hand_cannoneer | 32.8 → 27.5 | | |
| arbalester | 13.5 → 13.3 | | |

The mechanism is measured, not guessed. In `champion__vs__heavy_scorpion` the engine's bolt
finds **3.59 victims** against that tape's **1.12** — the tape's champions are not standing
in the bolt's line and the engine's are. That is D1 §4's finding arriving from the other
side: those same four opponents are exactly the families whose cadence is 0.48–0.60x of the
tape's, i.e. the engine's melee blob stands clumped where the tape's spreads out and fights.
**The bolt law is right; the formation it is fired into is wrong.**

`hand_cannoneer__vs__heavy_scorpion` — the round's one flip and the fight the brief wanted
back — moves the right way and does not flip: 32.8 → 27.5, scorpion HP 0.2 → 0.5 against the
tape's 42.1, engine win share still 5.0%. S1 supplies its half of D1's predicted 2.3x swing
(scorpion `dps_x` 0.79 → 0.94); the other half is the hand cannoneer's `cad_x` 1.24, which
is not a siege mechanism.

### 4b. S2a — right where D1 predicted, and it costs two winners

Every one of the four **under-kill** rows D1 named improves, three of them a lot: elephant
16.1 → 10.5, hussar 10.6 → 8.6, paladin 6.0 → 3.0, steppe 2.1 → **0.2**. Every **over-kill**
row gets worse: halberdier 24.3 → 36.6, fire lancer 18.1 → 34.6, champion 8.9 → 33.8. Net
−2 winners (24/25 → 22/25) and onager siege-side 3.77 → 8.11. The engine's onager was
already too lethal against a packed melee line before the ramp was lengthened; lengthening
it cannot help there. Two of the three casualties (`halberdier__vs__siege_onager` 3 stones,
`champion__vs__siege_onager` 6 stones) are D1 §8 re-record candidates.

### 4c. S2b — the flight time is right and the stone stops connecting

The arc closes most of the flight-time gap (§2) and then the onager stops hitting anything
that moves. `siege_onager__vs__hussar` and `siege_onager__vs__elite_steppe` both go to
**`shot_x` 0.00** — zero damage per stone, every stone missing — and the elephant and camel
rows collapse to 0.93 and 0.33 victims per stone from 3.12 and 1.91.

This is a real finding and it is not about the arc. R5b-D2 resolves a shot **on arrival**
against where the target actually is, and this engine's lead model cannot throw a stone
1.6 s ahead of a 1.5-speed hussar and have it land. The tape's onager flies for 1.58 s and
*does* land. So the missing mechanism is whatever makes a real 1.9-second lob connect — and
it is not in this round's scope. **The arc must not ship until that is understood**, because
shipping it alone would trade a wrong flight time for a wrong hit rate.

### 4d. S2c — the only rule the boards endorse, and the one that is a dat fact

Nine 1-damage fragments per stone: opponent |err| 13.87 → **13.35**, onager opponent
16.39 → **15.36**, `champion__vs__siege_onager` 8.9 → **3.3**, no winner lost anywhere, no
row worse by more than 0.2. Full corpus 194/216 and mean per-seed agreement 0.8981, both
unchanged.

**Measured both ways, as the brief asked.** The fragments are worth at most 9 damage per
stone against a blast that routinely does 100+, so the direct arithmetic says "immaterial" —
and the board says it is the best of the four anyway, because in a packed fight those nine
chips are nine near-certain hits distributed over nine *different* bodies, which finishes
units the blast left at 1–8 HP. That is a real effect, it is small, and it is exactly the
size D1 predicted (0.37–3.2 chip events per stone).

### 4e. Friendly fire — a deliberate absence

Not implemented. D1 §3.3: 2 events in 25 recordings and 3,956 damage events. Recorded here
so a later round does not have to re-derive that it was considered.

---

## 5. THE OFF-SWITCH, AND WHAT DOES NOT MOVE

**Full corpus, 216 fights x 20 seeds, byte-compared against the pre-D2 engine (`bb2e6fa`,
checked out and re-run):**

```
category           n     --d2 off    --d2 blastDebris    --d2 <all four>
melee-v-melee     99      99/99            99/99              99/99
ranged-v-melee    86      86/86            86/86              86/86
ranged-v-ranged    6        6/6              6/6                6/6
siege             25      25/25            12/25               0/25
```

(cells: fights whose entire 20-seed output is byte-identical to the pre-D2 engine)

* `--d2 off` is the pre-D2 engine on **all 216 fights**. The siege subset alone hashes
  identical too: sha256 `8fedef9f5a1ea6aec53270affb13fe1ed4addb08b0ded93ddfdc27a10919aaba`
  over 500 files, for both the base-engine run and the new engine with `--d2 off`.
* With **every rule on**, all 191 non-siege fights are still byte-identical. Only the 25
  fights containing a scorpion or an onager move — which is the scope claim, verified rather
  than asserted.
* `blastDebris` alone leaves the 12 scorpion-only fights untouched, as it must.
* The four canaries — `champion__vs__arbalester`, `champion__vs__heavy_cav_archer`,
  `heavy_cav_archer__vs__elite_steppe`, `hand_cannoneer__vs__heavy_camel` — are
  **4/4 byte-identical** with all four rules on.

**Full-corpus winners:** 194/216 with mean per-seed agreement 0.8981, base and all-four-on,
and **not one fight's winner block changes**. One verdict moves
(`heavy_scorpion__vs__elite_steppe` MISMATCH → INCONCLUSIVE).

**Tests:** `node --test tests/js/engine/` 309 pass, 0 fail (290 at base + 19 new in
`tests/js/engine/d2_siege.test.mjs`). `node tools/simjs/parity_check.mjs` is red at tick 0
on spawn positions — **pre-existing**, verified by re-running it with the engine directory
stashed and getting the identical failure.

---

## 6. SHIPPING DECISION

| rule | flag | ship | why |
|---|---|---|---|
| S1 bolt corridor | `boltCorridor` | **OFF** | Every emergence quantity lands on the tape and the scorpion's own-HP error improves 9.06 → 8.47, but the opponent column goes 11.34 → 15.48 and all of that loss is four fights whose opponents the engine clumps. Re-gate it **with** the melee cadence fix, not before. |
| S2a blast zero point | `blastZeroPoint` | **OFF** | Costs 2 winners. Correct on all four under-kill rows, fatal on the over-kill rows, two of which are D1 re-record candidates. |
| S2b projectile arc | `projectileArc` | **OFF** | Fixes the flight time and breaks the hit rate: two families go to zero damage per stone. Blocked on the aim model, not on the arc. |
| S2c blast debris | `blastDebris` | **OFF**, recommended ON | The only rule with no cost anywhere: −0.52 opponent |err|, −1.03 on the onager side, 194/216 held, no row worse by >0.2. It is also a dat fact (`secondary_projectile_unit` 369 x 9, ratio 9.000 in every recording) rather than a hypothesis. Left off only because turning it on is a sim-behaviour change with the usual downstream obligations (`.golden/baseline.json`, `blast_falloff.test.mjs`, re-sim of matchup data) that belong to the merge, not to this round. |

### What would make S1 testable again

Stated as a prediction. S1's entire loss is `victims per bolt` in the four melee-blob
fights: 3.59 and 2.97 in `champion` / `halberdier` against tape 1.12 and 2.24. The engine's
champions are stacked in the bolt's line because they are not fighting — D1 §4 measured them
landing 0.48–0.60x the tape's swings per unit-second, with first blood 2.2 s late. Fix the
cadence and the blob spreads; when it does, S1's four losses should evaporate while its
eight wins stay, because none of the eight involves a clump. **Re-gate S1 against the same
corpus immediately after any B/C-family cadence rule lands**, and specifically re-measure
`victims per bolt` in `champion__vs__heavy_scorpion` — if it drops from 3.59 toward 1.12,
S1 ships.

### What would make S2b testable again

The onager needs to be able to hit a mover over a 1.9-second flight. Either the tape's
victims are less mobile than the engine's (measurable directly from the recordings' unit
streams — do the hussars in `siege_onager__vs__hussar` actually move during the flight?), or
Genie solves the intercept differently for an arced shot. Answer that first; the arc term
itself is derived and is not in doubt.

---

## 7. WHAT S3 DID, AND WHAT THE PERMANENT FIX NEEDS

Carried now, engine-side only, via `constants.js` per-slug maps + a dict-first read in
`BattleUnit`: `projectile_arc`, `vanish_mode`, `hit_mode`, `blast_attack_level`,
`secondary_projectile_count`, `projectile_collision`.

**The permanent fix is a `docs/architecture/runbooks.md` §3 change and was deliberately not
done tonight.** For each of the six it needs:

1. `aoe2x/extract/extract_units.py` — read the field. `secondary_projectile_unit` is
   *already* extracted (line 442) and then dropped; `blast_attack_level`, `hit_mode`,
   `vanish_mode`, `projectile_arc` and the projectile's `collision_x` are not read at all.
   `accuracy_dispersion` is in the same bucket and should ride along, retiring
   `ACCURACY_DISPERSION_BY_SLUG` at the same time.
2. `aoe2x/dbgen/ability_registry.py` — one entry per column. The ref-DB schema, writer,
   audit chain and `combat_unit_loader.build_combat_dict_from_ref()` are all GENERATED from
   the registry, so those four files need no hand edits.
3. `aoe2x/dbgen/generate_main_db.py` — the one legacy file that still needs hand editing.
4. Regenerate `aoe2_reference.db` + `aoe2_units.db` + `data/calibration/combat_dicts.json`
   (`tools/simjs/dump_calib_dicts.py`), then delete the four per-slug maps.

One design note worth carrying forward. `pass_through_percent` is a **derived** column
(projectile attack ÷ unit attack = 0.4286) occupying the slot where the real quantity
belongs, and the tape says the real quantity is a flat 0.5. `blast_damage` — the one dat
field that could plausibly encode it — is spent on `splash_on_hit_fraction`. And
`blast_attack_level`, the field that says whether an effect is a **line** or a **disc**, is
carried by nothing while the engine infers the shape from `splash_radius > 0` vs
`pass_through_percent > 0`. That inference happens to be right for these two units and
encodes nothing about the shape, which is the entire scorpion problem. Fixing the classifier
to read `blast_attack_level` is the right permanent move and is a registry change, not a D2
rule — so S1 gates on `passThroughPercent`, the same field the block it replaces gated on,
and the dat's `vanish_mode` is carried and reported rather than used.

---

## 8. UNPREDICTED

1. **The forensics could not see the rule it was written to test.** The corridor initially
   measured 1.18 victims per bolt — *worse* than the 2.00 it replaced — because the shot
   probe recorded the bolt as ending at its aim point. The engine was right and the ruler
   was short. Anything that changes when damage lands relative to a projectile's nominal
   impact has to update the probe in the same commit.
2. **S2b's failure mode is total, not gradual.** Two families go to exactly zero damage per
   stone. A rule that makes a projectile slower interacts with arrival-resolution far more
   violently than "some shots now miss" suggests.
3. **S2c beat all three real rules.** The mechanic dismissed in advance as numerically
   negligible is the only one the board endorses, because nine near-certain 1-damage hits on
   nine *different* bodies finish more units than the same 9 damage on one.
4. **S1's damage and its cost are the same number.** The engine's bolt finds 3.59 victims
   where the tape's finds 1.12 in the one fight it ruins — the rule is not too strong, the
   thing it is fired into is too dense. Nothing in the siege round can fix that.
