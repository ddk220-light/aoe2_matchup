# AoE2 Battle-Sim Fidelity Investigation — Elite Temple Guard (Muisca)

> **Productionized.** This is the calibration record for the "V2" position-aware sim
> model. The finalized model + categorization pipeline now live in code at
> [`apps/video/sim_v2/`](../../../apps/video/sim_v2/) — see its `README.md` for how to
> run it. References to `$SP` below are the original scratchpad; the equivalent
> productionized files are noted in the sim_v2 README. The physics-fix knobs described
> in §11 are frozen in `apps/video/sim_v2/sim_v2_model.js`.

**Purpose of this document:** a complete, self-contained record of an investigation into why the
project's battle simulator mis-predicts three Age of Empires II matchups, every experiment run
(with full numeric results), the diagnostic instrumentation, the deep-dive findings, the code, and
the open path forward. Written so a different LLM (with no access to this conversation) can fully
understand the problem, audit the reasoning, reproduce the experiments, and continue the work.

Date: 2026-07-06 (updated same day with **§10 — 20-run in-game validation**, which materially
revises the premise below). Repo: `C:\dev\aoe2\aoe2_matchup`. All experiment scripts live in the
scratchpad dir referenced as `$SP` = `C:\Users\ddk22\AppData\Local\Temp\claude\C--dev-aoe2-aoe2-matchup\0787130c-e8a8-4d48-a53f-893b2bc59361\scratchpad`.

---

## 0. TL;DR

- **Problem:** A per-unit "analysis video" categorizes each opponent of the Elite Temple Guard (ETG,
  Muisca) into expected/unexpected win/counter buckets using a pre-computed matchup database. Three
  fights are labeled **"unexpected win"** (ETG wins) — **Elite White Feather Guard (Shu), Elite
  Ibirapema Warrior (Tupi), Elite Huskarl (Goths)** — but the **single filmed recording** of each
  showed **ETG LOSING**. Goal: find why the sim is wrong and fix it.
- **⚠ CRITICAL LATE REVISION (§10):** those single recordings were **unreliable**. A **20-run** in-game
  re-test of Huskarl shows the matchup is a **55/45 COIN-FLIP** (mean score S = **+3.6**, sd 21). So
  the three "flips" are **near-even fights, not clean ETG losses** — and the sim's real error is the
  win-*rate*, not the win-*margin* (the improved sim's winner-HP% already matches the game). Read §10
  before acting on §0–§9, which were written under the "ETG clearly loses" premise.
- **Ruled out — the attack-speed ramp.** ETG has a unique attack-speed ramp. The shipped sim modeled
  it as a *monotonic* accumulator; the real mechanic is a *5-second decaying window*. Implementing
  the faithful window changes outcomes negligibly (ramp is continuous in a sustained melee). **Fixed
  anyway** (it was genuinely wrong) and shipped to `apps/website/static/js/simulate.js`
  (Temple-Guard-only, safe).
- **Ruled out — unit stats.** The sim computes **per-hit damage exactly correctly** for all three
  opponents (verified by armor-class decomposition). Not a stats/ability bug.
- **Root cause — melee envelopment.** The sim cannot bring an outnumbering melee army's surplus
  bodies into contact. Measured: only **~7 of 21** attackers ever engage; **32–41% stand idle**
  (alive but never in melee range), queued single-file behind their own front rank. The real game
  achieves **instant, full engagement** (measured from in-game HP-drain: effective attackers are
  100–140% of the alive count from t=0) and the fight is decided by **body count**.
- **Partial fix built — slot-aware ("nearest-reachable") targeting.** Grounded in the real AoE2
  mechanic. **Halves the ETG margins** and gets White Feather to a genuine coin-flip (67% ETG,
  matching its real 2-unit loss) while keeping all 9 correct fights correct. But it plateaus: the
  physical route-around of the idle ~32% is beyond this engine's movement model, so Huskarl and
  Ibirapema don't fully flip.
- **Open decision:** (A) model "instant engagement to a per-defender cap" directly (data-grounded,
  no re-record), (B) re-record fights capturing per-unit positions to calibrate, or (C) ship the
  partial fix + correct residual near-coin-flips from the recordings we already have.

---

## 1. System context

### 1.1 Three sim engines
| Engine | File | Role |
|---|---|---|
| Abstract tick (no positions) | `aoe2x/sim/simulation.py` | `/api/matchup-sims` overlay |
| Position-based 2D | `aoe2x/sim/simulation_real.py` | ALL batch matchup data (the matchup DB) |
| Frontend canvas (`BattleUnit`) | `apps/website/static/js/simulate.js` | interactive Battle-Sim page (client-side) |

The **matchup DB** that drives the video's categorization is produced by `simulation_real.py`. The
**interactive web sim** is `simulate.js` — it independently implements steering (a boids-like
separation/avoidance force) + stuck-detection retargeting, i.e. a "flanking" model the position sim
lacks. This investigation uses `simulate.js` run **headless** (see §5) because the user asked to use
the webapp's flanking sim as the geometry engine and to make its logic reflect the game.

### 1.2 Scoring
A fight's score/margin used here = `(team1_hp_fraction − team2_hp_fraction) × 100`, averaged over
seeds. `team1` = subject (ETG), `team2` = opponent. Positive = ETG ahead. "SIM win%" = fraction of
seeds ETG is the surviving side. A fight "matches" the game iff `(sim ETG-favored) == (game ETG won)`.

### 1.3 The 12 filmed fights (in-game ground truth)
Counts are the exact in-game starting counts (21-unit arena cap). `E a:b` = ETG survivors : opponent
survivors at end (in-game). Equal-resources (3000) matchups; the arena is a compact ~16×16 cluster.

| Category | Opponent (civ) | Counts (ETG v opp) | In-game result |
|---|---|---|---|
| expected_win | Heavy Camel Rider | 21 v 19 | ETG win (21:0) |
| expected_win | Elite Tarkan (Huns) | 21 v 19 | ETG win (19:0) |
| expected_win | Elite Shrivamsha Rider (Gurjaras) | 14 v 21 | ETG win (11:0) |
| **unexpected_win** | **Elite White Feather Guard (Shu)** | **12 v 21** | **ETG LOSE (0:2)** |
| **unexpected_win** | **Elite Ibirapema Warrior (Tupi)** | **18 v 21** | **ETG LOSE (0:17)** |
| **unexpected_win** | **Elite Huskarl (Goths)** | **13 v 21** | **ETG LOSE (0:4)** |
| expected_counter | Grenadier (Jurchens) | 20 v 21 | ETG lose (0:17) |
| expected_counter | Elite Chakram Thrower (Gurjaras) | 14 v 21 | ETG lose (0:15) |
| expected_counter | Elite Chu Ko Nu (Chinese) | 12 v 21 | ETG lose (0:20) |
| unexpected_counter | Elite Urumi Swordsman (Dravidians) | 14 v 21 | ETG lose (0:19) |
| unexpected_counter | Elite Obuch (Poles) | 12 v 21 | ETG lose (0:19) |
| unexpected_counter | Elite Serjeant (Sicilians) | 14 v 21 | ETG lose (0:21) |

The 3 bolded "unexpected_win" fights are the ones the sim gets wrong. Note they are the *closest*
fights in reality: White Feather won by 2, Huskarl by 4; only Ibirapema is a blowout (trample).

---

## 2. Combat stats (from the reference DB, exactly what `/api/ref/combat-unit` serves)

Armor/attack classes: `4`=base melee, `3`=base pierce, `8`=cavalry (ETG anti-cav), `29` = a class
ALL these opponents have a bonus against and which ETG carries in its armor list (value 0), `21` =
a class ETG does NOT have in its armor list, `15` = archer (Huskarl anti-archer).

```
ETG  Muisca/elite_temple_guard_muisca
  hp 115  attack 16  attacks {"4":16,"8":8,"5":8,"30":6,"16":6,"21":2}
  armors {"1":0,"4":5,"3":6,"19":0,"31":0,"29":0}  melee_armor 5  pierce_armor 6
  attack_speed 0.5 (=2.0s base reload)  attack_speed_ramp 0.2  attack_speed_min 1.0
  movement_speed 1.05  cost 70f/45g  pop 1

WFG  Shu/elite_white_feather_guard_shu
  hp 100  attack 9  attacks {"4":9,"8":8,"5":8,"30":7,"29":4,"21":4,"15":0}
  armors {"1":0,"4":3,"3":7,...}  melee_armor 3  pierce_armor 7
  attack_speed 0.5  movement_speed 1.05  cost 60f/15g

Ibirapema  Tupi/elite_ibirapema_warrior_tupi
  hp 90  attack 13  attacks {"4":13,"29":3,"21":4,...}
  armors {"1":0,"4":5,"3":5,...}  melee_armor 5  pierce_armor 5
  attack_speed 0.5  movement_speed 1.1  trample_percent 1.0  trample_radius 0.5t  cost 30f/60g

Huskarl  Goths/elite_huskarl_goths
  hp 70  attack 16  attacks {"4":16,"15":10,"29":3,"21":6,...}
  armors {"1":0,"4":2,"3":10,...}  melee_armor 2  pierce_armor 10
  attack_speed 0.5  movement_speed 1.16  cost 53f/25g
```

### 2.1 Per-hit damage decomposition — STATS ARE CORRECT (ruled out)
The sim's measured damage-per-attack (from instrumentation, §6) matches the exact armor-class math:

- **WFG → ETG:** base `9−5=4` + class-29 `4−0=4` = **8.0** ✓ (sim measured 8.0)
- **Huskarl → ETG:** base `16−5=11` + class-29 `3−0=3` = **14.0** ✓ (its +6-vs-class-21 does NOT
  apply — ETG has no class-21 armor). (sim measured 14.0)
- **Ibirapema → ETG:** base `13−5=8` + class-29 `3−0=3` = **11.0** ✓ (sim measured 11.0)
- **ETG → cavalry** (Heavy Camel / Tarkan / Shrivamsha): base + class-8 `+8` anti-cav bonus →
  explains why the 3 expected-wins (all cavalry) are decisive ETG wins.

Conclusion: the over-valuation is **not** a mis-modeled stat or ability. It is purely geometric.

---

## 3. The attack-speed ramp — investigated and fixed (not the cause)

### 3.1 The real mechanic (user-supplied, verified against a published 16-second hit table)
Each Temple Guard attack adds a `−0.2s` reload stack that **expires 5.0s later**. Reload =
`max(1.0, 2.0 − 0.2 × (hits landed in the last 5.0s))`. Base reload 2.0s (attack_speed 0.5); floor
1.0s; stabilizes at 1.0s reload after ~14.6s of continuous attacking.

### 3.2 The shipped bug and the fix
The shipped `simulate.js` modeled the ramp as a **monotonic accumulator** (`rampReduction` only
grows, capped at `base−min`, never decays). That is wrong: it never decays when the unit stops
attacking (walking between targets). **Only the Elite Temple Guard has `attack_speed_ramp>0`**, so
the fix is Temple-Guard-only and safe.

**SHIPPED to `apps/website/static/js/simulate.js`** (replaced the monotonic block, ~line 1827):
```javascript
// Attack-speed ramp (Temple Guard): each hit adds a -attackSpeedRamp stack that
// EXPIRES 5s later, so reload = max(min, base - ramp*stacks) where stacks = hits
// landed in the last 5s. This is the real game mechanic (a decaying 5s window),
// not a monotonic accumulator — walking between targets lets the ramp decay back.
if (this.attackSpeedRamp > 0) {
    const baseReload = this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
    const now = (typeof simulation !== "undefined" && simulation) ? simulation.battleTime : 0;
    if (!this.rampHits) this.rampHits = [];
    const cutoff = now - 5.0;
    this.rampHits = this.rampHits.filter((h) => h > cutoff);
    this.rampHits.push(now);
    this.reloadTime = Math.max(this.attackSpeedMin,
        baseReload - this.attackSpeedRamp * this.rampHits.length);
}
```
(Legacy field `this.rampReduction` is left initialized-but-unused to minimize the diff.)

### 3.3 Ramp is NOT the lever
In a sustained melee the ETG attacks continuously, so the window ramp and the monotonic ramp both
sit at the 1.0s floor. Swapping ship→window ramp changes the 12-fight verdict count by **zero**
(9/12 both) and only shifts the 3 miss margins by ~4 points (§4). A prior investigation in
`simulation_real.py` reached the same conclusion (both give 9/12; only *disabling* the ramp entirely
— a blunt 2× DPS cut — reached 11/12 there, which is not a faithful change).

---

## 4. Experiment log — the headless webapp sim vs the 12 in-game fights

All runs use the headless harness (`$SP/headless_sim.js`, §5) which loads the REAL `simulate.js`.
Columns: `SIMwin%` = fraction of seeds ETG survives; `surv E:O` = mean survivors each side; `margin`
= mean `(hp1−hp2)×100`; `match` = agrees with in-game. Env knobs: `RAMP` (ship|window|off), `PACK`
(collision/avoidance spacing scale, 1.0=ship), `BLOCK` (compact-block spawn vs full-height line),
`GAP` (block center separation px), `SLOT` (per-defender attacker cap for reachability targeting),
`FLANK` (tangential slide strength), `AVHALO`/`AVFORCE` (avoidance halo/standoff force).

### E1 — Baseline: ship ramp, LINE spawn, PACK=1, 6 seeds → **9/12**
```
category            opponent                 counts  GAME          SIMwin%  surv E:O   margin  match
expected_win        Heavy Camel Rider        21v19   E21:0 ETGwin  100%     21.0:0.0    86.0   OK
expected_win        Elite Tarkan             21v19   E19:0 ETGwin  100%     19.5:0.0    65.7   OK
expected_win        Elite Shrivamsha Rider   14v21   E11:0 ETGwin  100%     13.5:0.0    69.1   OK
unexpected_win      Elite White Feather Guar 12v21   E 0:2 ETGlose 100%     11.0:0.0    45.4   **MISS**
unexpected_win      Elite Ibirapema Warrior  18v21   E 0:17 ETGlose 100%    15.3:0.0    52.0   **MISS**
unexpected_win      Elite Huskarl            13v21   E 0:4 ETGlose 100%     10.8:0.0    44.3   **MISS**
expected_counter    Grenadier                20v21   E 0:17 ETGlose  0%      0.0:21.0  -100.0   OK
expected_counter    Elite Chakram Thrower    14v21   E 0:15 ETGlose  0%      0.0:19.3   -78.3   OK
expected_counter    Elite Chu Ko Nu          12v21   E 0:20 ETGlose  0%      0.0:21.0  -100.0   OK
unexpected_counter  Elite Urumi Swordsman    14v21   E 0:19 ETGlose 33%      0.7:6.7    -15.9   OK
unexpected_counter  Elite Obuch              12v21   E 0:19 ETGlose 33%      1.8:5.0    -10.1   OK
unexpected_counter  Elite Serjeant           14v21   E 0:21 ETGlose  0%      0.0:10.5   -29.0   OK
```
**The headless webapp flanking sim reproduces the exact same 9/12 as `simulation_real.py`** — the
flanking model as-built does NOT fix the ETG over-valuation.

### E2 — Window ramp, LINE, PACK=1, 6 seeds → **9/12** (ramp is not the lever)
Only the 3 misses changed, slightly: White Feather 45.4→**41.1**, Ibirapema 52.0→**48.3**, Huskarl
44.3→**42.7**. All still ETG-win 100%.

### E3 — Packing sweep (window ramp, LINE), 5 seeds → all **9/12**
| PACK | White Feather | Ibirapema | Huskarl |
|---|---|---|---|
| 1.0 | +41.1 (11.0 surv) | +48.3 | +42.7 |
| 0.8 | +31.6 (8.6) | +36.9 | +29.1 |
| 0.6 | +20.2 (6.6) | +21.3 | +22.8 |
| 0.45 | (timeout — instability) | | |
Tighter packing lowers margins monotonically but never flips; <0.45 destabilizes.

### E4 — Diagnostics, LINE spawn (`diag_web.js`, seed 1000)
`focus-fire` = opponents in melee range per living ETG; `xspread` = ETG cluster x-extent (tiles);
`dmg/atk` = opponent damage per primary hit; `secondary` = extra (trample) hits.
```
PACK=1.0 (line):
  WhiteFeather ETG:11:0 primHits=86 secondary=0(0%)  dmg/atk=8.0  focus-fire=0.49  xspread=1.96t
  Ibirapema    ETG:16:0 primHits=89 secondary=0(0%)  dmg/atk=11.0 focus-fire=0.42  xspread=2.56t
  Huskarl      ETG:10:0 primHits=71 secondary=0(0%)  dmg/atk=14.0 focus-fire=0.46  xspread=1.62t
PACK=0.6 (line):
  WhiteFeather ETG:8:0  primHits=128 secondary=0(0%)  dmg/atk=8.0  focus-fire=0.93  xspread=0.69t
  Ibirapema    ETG:10:0 primHits=113 secondary=19(17%) dmg/atk=12.8 focus-fire=0.67 xspread=0.82t
  Huskarl      ETG:5:0  primHits=92 secondary=0(0%)  dmg/atk=14.0 focus-fire=0.77  xspread=0.65t
```
Key: focus-fire ~0.45 (need ~3); Ibirapema trample lands **0%** at PACK=1 (units 2.5t apart, splash
ring only 0.97t); packing to 0.6 lifts focus-fire to ~0.8 and starts landing trample (17%).

### E5 — Compact-block spawn, window ramp, PACK=1, GAP=130, 5 seeds → **9/12** (worse)
White Feather **+47.2**, Ibirapema **+53.5**, Huskarl **+53.0**. A loose block is just a fat frontal
blob; worse than a line at PACK=1.

### E6 — Block + tight packing
| Config (seeds) | White Feather | Ibirapema | Huskarl |
|---|---|---|---|
| BLOCK GAP=80 PACK=0.5 (4) | +45.2 (100%) | **+2.4 (50%)** | +31.3 (100%) |
| BLOCK GAP=70 PACK=0.4 (4) | +38.8 | +23.5 | +35.8 |
| BLOCK GAP=80 PACK=0.5 (6) | +44.5 (100%) | **+4.3 (50%)** | +33.9 (100%) |
Block + tight packing makes **Ibirapema (trample) a coin-flip** (its trample finally lands on packed
ETG) but the two non-trample fights don't flip.

### E7 — Diagnostics, BLOCK GAP=80 PACK=0.5 (idle metric added)
`idle-opp` = time-avg fraction of living opponents NOT in melee range of any ETG.
```
No flank:
  WhiteFeather ETG:11:0 focus-fire=1.43 idle-opp=32%
  Ibirapema    ETG:0:12 focus-fire=1.43 idle-opp=40% trample=51%   (Ibira WINS)
  Huskarl      ETG:10:0 focus-fire=1.15 idle-opp=41%
```
**Smoking gun: 32–41% of the opponents stand idle.** Block+pack triples focus-fire (0.45→1.4) and
makes Ibirapema's trample land (0%→51%, flipping it), but a third of the army never engages.

### E8 — Flank tangent alone, LINE, window → **9/12** (no effect)
FLANK 1.0/2.0 leave White Feather ~46, Ibirapema ~47, Huskarl ~43. A line spawn has no rear pile-up
to flow around. FLANK=3 timed out.

### E9 — Flank tangent + block + pack (4 seeds)
FLANK 1.5: White Feather +45.9, Ibirapema 75% (13.2), Huskarl +32.1. FLANK 2.5: WF +48.3, Ibira 75%
(7.6), Huskarl +38.4. The tangent scatters units without producing coherent wrap.

### E10 — "Part A" (reduce soft avoidance): AVHALO=1.0 AVFORCE=0, BLOCK PACK=1, 4 seeds → **WORSE**
Idea (from the pathing reference): the soft-avoidance halo (active to 45px) sits OUTSIDE the 33px
melee contact ring, so rear units are repelled before they can strike. Collapsing it BACKFIRED:
```
White Feather +66.9 (11.0)   Ibirapema +57.3 (14.5)   Huskarl +58.3 (10.5)   [all MISS]
Obuch flipped to 50% (broke a previously-correct fight)
diag Huskarl: focus-fire 0.67 (was 1.15), idle-opp 49% (was 41%)  → WORSE
```
The soft halo was actually providing lateral **dispersion** that helped units find contact; removing
it makes them clog single-file. Part A is a misread — dropped.

### E11 — "Part B" (slot-aware nearest-reachable targeting): SLOT=6, BLOCK PACK=0.5, 4 seeds
The real AoE2 mechanic: an enemy whose contact ring already holds ≥SLOT attackers is treated as
not-reachable; overflow picks the next-nearest → spreads around the perimeter. Re-evaluated every
tick for melee.
```
White Feather +22.8 (5.5 surv)   Ibirapema +41.2 (11.8)   Huskarl +29.0 (7.0)   [all still MISS]
9 correct fights unchanged.
```
**Halves the ETG margins** (White Feather 45→23) — the right mechanic, right direction, no chaos.

### E12 — Diagnostics, SLOT sweep (Huskarl, BLOCK PACK=0.5)
```
SLOT=0  focus-fire=1.15  idle-opp=41%  primHits=68  (ETG 10 surv)
SLOT=6  focus-fire=0.79  idle-opp=34%  primHits=76  (ETG 8)
SLOT=4  focus-fire=0.89  idle-opp=32%  primHits=77  (ETG 8)
SLOT=3  focus-fire=0.77  idle-opp=34%  primHits=75  (ETG 8)
```
Slot-awareness *distributes* attackers across more ETG (instantaneous focus-fire per-ETG drops, but
total hits/throughput rise and idle drops). It cannot push idle below ~32% because the redirected
units still can't *physically* route to the open flank ETG.

### E13/E14 — Slot + flank (with a block-timer trigger that survives retargeting)
`findTarget` zeroes `stuckTimer` every tick under Part B's continuous retargeting, so the flank
never fired (E13: identical numbers). After giving the flank its own `_blockT` counter (E14), it
fires but *scatters*: idle-opp 32%→36% (FLANK 1.5)→44% (FLANK 3). Steering-based route-around does
not work in this engine.

### E15 — Part B SLOT=4, BLOCK GAP=80 PACK=0.5, window ramp, 6 seeds
```
Heavy Camel 100% +84.3   Tarkan 100% +63.4   Shrivamsha 100% +65.0
White Feather 100% +17.4 (4.2 surv)   Ibirapema 100% +41.1 (11.2)   Huskarl 100% +29.7 (7.0)
Grenadier 0% -100  Chakram 0% -51.9  ChuKoNu 0% -99.6
Urumi 0% -38.8  Obuch 0% -58.5  Serjeant 0% -55.2
```

### E16 — Part B SLOT=3, BLOCK GAP=80 PACK=0.5, window ramp, 6 seeds (BEST principled result)
```
Heavy Camel 100% +83.8   Tarkan 100% +63.0   Shrivamsha 100% +65.5
White Feather 67% +12.7 (3.7:1.3)   Ibirapema 100% +42.7 (11.3)   Huskarl 100% +27.1 (7.3)
Grenadier 0% -100  Chakram 0% -52.8  ChuKoNu 0% -99.6
Urumi 0% -43.8  Obuch 0% -56.8  Serjeant 0% -56.4
```
**White Feather reaches a genuine coin-flip (67% ETG)** — matching its real "won by 2 units" margin.
Huskarl and Ibirapema remain ETG-wins (~27, ~43). All 9 correct fights hold. Note slot-spreading
slightly *hurts* Ibirapema (spreading reduces trample concentration) — the trample-packing and
slot-spreading mechanisms partially conflict.

### 4.1 What worked / what didn't (summary)
| Lever | Effect on the 3 misses | Verdict |
|---|---|---|
| Window ramp (faithful) | −4 margin | Correct fix, but not the lever. **Shipped.** |
| Tighter packing (PACK) | −20 margin, trample starts landing | Helps; destabilizes <0.45 |
| Compact-block spawn | enables trample; alone at PACK=1 is worse | Needed WITH tight pack |
| Block + tight pack | **Ibirapema → coin-flip** (trample) | Fixes the trample case only |
| Reduce soft avoidance (Part A) | **WORSE** (idle 41→49%) | Misread — dropped |
| Flank tangent | scatters units (idle up) | Does not work in this engine |
| **Slot-aware targeting (Part B)** | **halves margins; WF → coin-flip** | **Best principled fix; keeper** |
| Full envelopment of idle ~32% | would flip all 3 | Needs route-around the engine can't do |

---

## 5. The headless harness — how the webapp sim is run offline (with code)

`simulate.js` is a browser script (3400+ lines) coupled to DOM/canvas. To run it faithfully offline,
the harness loads it (plus its sibling scripts, in browser order) inside a Node `vm` sandbox with
DOM/canvas stubbed and `Math.random` replaced by a seeded PRNG. Combat/steering/flanking are
byte-identical to production; only rendering is skipped. It drives `BattleSimulation.update(1/60)`
(the webapp's fixed timestep). Env knobs apply targeted source-string replacements to test mechanics.

Node v26 is available. System `python` (3.12) has the repo's `aoe2x` package. Combat dicts are the
exact JSON `/api/ref/combat-unit/<civ>/<slug>` serves, dumped offline.

### 5.1 `export_fights.py` — dumps combat-dicts + the 12 fights
```python
"""Export combat-dicts + the 12 ETG fights (in-game counts/outcomes) as JSON for the
headless Node run. combat_dicts.json : {"Civ/slug": <exactly what /api/ref/combat-unit serves>}.
fights.json : [{category, rank, name, opp_civ, opp_slug, opp_name, etg_start, opp_start,
etg_end, opp_end, game_etg_won}]."""
import json, sys
from pathlib import Path
REPO = Path(r"C:\dev\aoe2\aoe2_matchup"); sys.path.insert(0, str(REPO))
import sqlite3
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
REF_DB = REPO / "data/golden/aoe2_reference.db"
CLIPS = Path(r"<scratchpad>/etg_clips")                 # the recorded .hp.json sidecars
SB = REPO / "apps/video/media/units/elite_temple_guard_muisca/storyboard.json"
ETG_CIV, ETG_SLUG, ETG_MAX_HP = "Muisca", "elite_temple_guard_muisca", 115.0
conn = sqlite3.connect(str(REF_DB)); conn.row_factory = sqlite3.Row
def combat_dict(civ, slug, age="Imperial"):
    row = conn.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
                       (civ, slug, age)).fetchone() or \
          conn.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?", (civ, slug)).fetchone()
    d = build_combat_dict_from_ref(row)
    d["name"] = row["unit_name"]; d["civ"] = civ
    d["total_cost"] = (row["final_cost_food"] or 0)+(row["final_cost_wood"] or 0)+(row["final_cost_gold"] or 0)
    d["outline_size"] = row["outline_size_x"] or 0.2
    return d
def ingame_result(name):
    hp = CLIPS / f"{name}.hp.json"
    if not hp.exists(): return None
    rows = (json.loads(hp.read_text()).get("rows") or [])
    if not rows: return None
    first, last = rows[0], rows[-1]
    def per_unit(side):
        c = int(first[side]["count"]); return (first[side]["hp"]/c) if c else 0
    e,o = ("side1","side2") if abs(per_unit("side1")-ETG_MAX_HP) <= abs(per_unit("side2")-ETG_MAX_HP) else ("side2","side1")
    return {"etg_start":int(first[e]["count"]),"opp_start":int(first[o]["count"]),
            "etg_end":int(last[e]["count"]),"opp_end":int(last[o]["count"])}
cds = {f"{ETG_CIV}/{ETG_SLUG}": combat_dict(ETG_CIV, ETG_SLUG)}; fights = []
for seg in json.loads(SB.read_text())["segments"]:
    cat, rank, opp = seg["category"], seg["rank"], seg["opponent"]
    ig = ingame_result(f"{cat}_{rank}_{opp['slug']}")
    if ig is None: continue
    key = f"{opp['civ']}/{opp['slug']}"
    if key not in cds: cds[key] = combat_dict(opp["civ"], opp["slug"])
    fights.append({"category":cat,"rank":rank,"name":f"{cat}_{rank}_{opp['slug']}",
        "opp_civ":opp["civ"],"opp_slug":opp["slug"],"opp_name":opp["name"],
        "etg_start":ig["etg_start"],"opp_start":ig["opp_start"],"etg_end":ig["etg_end"],
        "opp_end":ig["opp_end"],"game_etg_won": ig["etg_end"]>0 and ig["opp_end"]<=0})
# writes combat_dicts.json + fights.json
```

### 5.2 `headless_sim.js` — the runner (full source)
Key implementation points: (1) siblings `constants.js/unit_sprites.js/api_client.js/sim_params.js`
are prepended (browser load order) so module-scope constants resolve; (2) CRLF normalized to LF so
source-string replacements match; (3) a shim appends `globalThis.__HL = {BattleSimulation,...}` and
`__setSim` so the module-scope `simulation` var (used by `performAttackOn` for trample) points at our
instance; (4) `sim.updateStats/updateDebugPanel/render` are stubbed to no-ops per instance; (5)
`fetch` is stubbed to return the injected combat dicts by URL.

```javascript
// Headless runner for the webapp's flanking battle sim (apps/website/static/js/simulate.js).
// Loads the REAL file (+ its sibling scripts, in browser load order) in a vm sandbox so
// every closure/const is intact, stubs DOM/canvas, seeds Math.random for determinism, and
// drives BattleSimulation.update() at the webapp's fixed 1/60 timestep.
// Usage: node headless_sim.js [ramp=ship|window|off] [nSeeds] [maxSeconds]
const fs = require("fs"); const vm = require("vm"); const path = require("path");
const REPO = "C:/dev/aoe2/aoe2_matchup"; const HERE = __dirname;
const JSDIR = path.join(REPO, "apps/website/static/js");
const RAMP = process.env.RAMP || process.argv[2] || "ship";
const N_SEEDS = parseInt(process.env.SEEDS || process.argv[3] || "8", 10);
const MAX_S = parseFloat(process.env.MAXS || process.argv[4] || "180");
const PACK = parseFloat(process.env.PACK || "1.0");   // collision/avoidance spacing scale

// ---- seeded PRNG (mulberry32), injected as Math.random for determinism -------
let _rngState = 1;
function rng() {
    _rngState |= 0; _rngState = (_rngState + 0x6D2B79F5) | 0;
    let t = Math.imul(_rngState ^ (_rngState >>> 15), 1 | _rngState);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
// ---- permissive DOM element stub --------
function elStub() {
    const f = function () { return f; };
    return new Proxy(f, {
        get(_t, k) {
            if (k === "value") return "";
            if (k === "classList") return { add(){}, remove(){}, toggle(){}, contains(){return false;} };
            if (k === "getContext") return () => elStub();
            if (k === "width") return 900; if (k === "height") return 600;
            if (k === Symbol.toPrimitive) return () => ""; return elStub();
        },
        set() { return true; }, apply() { return elStub(); },
    });
}
const documentStub = {
    getElementById: () => elStub(), querySelector: () => elStub(), querySelectorAll: () => [],
    createElement: () => elStub(), createTextNode: () => elStub(),
    addEventListener: () => {}, body: elStub(), head: elStub(),
};
const defaultFetch = async () => ({ ok: true, json: async () => ({}) });
const sandbox = {
    document: documentStub,
    window: { addEventListener: () => {}, location: { search: "" }, devicePixelRatio: 1 },
    navigator: { userAgent: "node" }, performance: { now: () => 0 },
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
    setTimeout: (fn) => 0, clearTimeout: () => {},
    Image: class { constructor(){ this.complete=false; this.naturalWidth=0; } },
    alert: () => {}, console, URLSearchParams, TextEncoder, TextDecoder,
    fetch: defaultFetch, __rng: rng,
    __setSeed: (n) => { _rngState = (n >>> 0) || 1; }, UNIT_SEARCH: {},
};
sandbox.globalThis = sandbox;

// ---- assemble source: sibling scripts (browser order) + simulate.js ----------
function read(f) { return fs.readFileSync(path.join(JSDIR, f), "utf8").replace(/\r\n/g, "\n"); }
let simSrc = read("simulate.js");

const SHIP_RAMP = `        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            this.rampReduction = Math.min(
                this.rampReduction + this.attackSpeedRamp,
                Math.max(0, baseReload - this.attackSpeedMin),
            );
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.rampReduction,
            );
        }`;
const WINDOW_RAMP = `        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            const _t = (typeof simulation !== "undefined" && simulation) ? simulation.battleTime : 0;
            if (!this._rampHits) this._rampHits = [];
            const _cut = _t - 5.0;
            this._rampHits = this._rampHits.filter((h) => h > _cut);
            this._rampHits.push(_t);
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.attackSpeedRamp * this._rampHits.length,
            );
        }`;
const OFF_RAMP = `        if (this.attackSpeedRamp > 0) {
            this.reloadTime = this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
        }`;
const fileIsWindow = simSrc.includes("this.rampHits");   // real file now ships window ramp
if (RAMP === "window") {
    if (simSrc.includes(SHIP_RAMP)) simSrc = simSrc.replace(SHIP_RAMP, WINDOW_RAMP);
    else if (!fileIsWindow) { console.error("!! neither ship nor window ramp found"); process.exit(2); }
} else if (RAMP === "off") {
    if (simSrc.includes(SHIP_RAMP)) simSrc = simSrc.replace(SHIP_RAMP, OFF_RAMP);
    else if (fileIsWindow) {
        const winBlock = simSrc.match(/if \(this\.attackSpeedRamp > 0\) \{[\s\S]*?this\.rampHits\.length,\n\s*\);\n\s*\}/);
        if (winBlock) simSrc = simSrc.replace(winBlock[0], "if (this.attackSpeedRamp > 0) {\n            this.reloadTime = this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;\n        }");
    }
}
if (PACK !== 1.0) {   // scale hard-collision + soft-avoidance spacing
    const c1 = "const minDist = a.radius + b.radius + 1;";
    const c2 = "const minDist = this.radius + other.radius + 2;";
    if (!simSrc.includes(c1) || !simSrc.includes(c2)) { console.error("!! spacing lines not found"); process.exit(2); }
    simSrc = simSrc.replace(c1, `const minDist = (a.radius + b.radius) * ${PACK} + 1;`)
                   .replace(c2, `const minDist = (this.radius + other.radius) * ${PACK} + 2;`);
}
// AVHALO/AVFORCE = "Part A" (reduce soft-avoidance halo/standoff). Found HARMFUL.
const AVHALO = parseFloat(process.env.AVHALO || "1.5");
const AVFORCE = process.env.AVFORCE != null ? parseFloat(process.env.AVFORCE) : 0.5;
if (AVHALO !== 1.5 || AVFORCE !== 0.5) {
    const a1 = "if (dist < minDist * 1.5 && dist > 0) {";
    const a2 = "const force = overlap > 0 ? 3 + overlap * 5 : 0.5;";
    if (!simSrc.includes(a1) || !simSrc.includes(a2)) { console.error("!! avoidance lines not found"); process.exit(2); }
    simSrc = simSrc.replace(a1, `if (dist < minDist * ${AVHALO} && dist > 0) {`)
                   .replace(a2, `const force = overlap > 0 ? 3 + overlap * 5 : ${AVFORCE};`);
}
// SLOT = "Part B" (slot-aware nearest-reachable targeting). The KEEPER.
// Skip enemies whose contact ring already holds >= SLOT attackers; re-evaluate melee
// targets every tick so overflow attackers pick the next-nearest (flank/rear) enemy.
const SLOT = parseInt(process.env.SLOT || "0", 10);
if (SLOT > 0) {
    const F_OLD = `            const dist = this.distanceTo(enemy);
            // Prefer targets not in blockedTargets
            if (!this.blockedTargets.has(enemy)) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const F_NEW = `            const dist = this.distanceTo(enemy);
            let _open = !this.blockedTargets.has(enemy);
            const _ring = enemy.radius + this.radius + this.attackRange + 4;
            if (_open && !this.isRanged() && dist > _ring) {
                const _mates = this.team === 1 ? simulation.team1 : simulation.team2;
                let _load = 0;
                for (const _m of _mates) {
                    if (_m === this || _m.state === "dead") continue;
                    const _dx = _m.x - enemy.x, _dy = _m.y - enemy.y;
                    if (_dx * _dx + _dy * _dy <= _ring * _ring) { if (++_load >= ${SLOT}) { _open = false; break; } }
                }
            }
            if (_open) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const U_OLD = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    const U_NEW = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        } else if (!this.isRanged() && !this.inRange()) {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    if (!simSrc.includes(F_OLD)) { console.error("!! findTarget block not found"); process.exit(2); }
    if (!simSrc.includes(U_OLD)) { console.error("!! update target-acq block not found"); process.exit(2); }
    simSrc = simSrc.replace(F_OLD, F_NEW).replace(U_OLD, U_NEW);
}
// FLANK = tangential slide when blocked (uses a _blockT counter that findTarget doesn't reset).
// Found HARMFUL (scatters units).
const FLANK = parseFloat(process.env.FLANK || "0");
if (FLANK > 0) {
    const OLD_AV = `        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }`;
    const NEW_AV = `        const _seekx = dx, _seeky = dy;
        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }
        if (!this.isRanged() && (this._blockT || 0) > 0.3) {
            let _tx = -_seeky, _ty = _seekx;
            if (_tx * avoidance.x + _ty * avoidance.y < 0) { _tx = -_tx; _ty = -_ty; }
            const _f = Math.min(1, (this._blockT || 0) - 0.3) * ${FLANK};
            dx += _tx * _f; dy += _ty * _f;
        }`;
    if (!simSrc.includes(OLD_AV)) { console.error("!! moveTowardTarget avoidance block not found"); process.exit(2); }
    simSrc = simSrc.replace(OLD_AV, NEW_AV);
    const S_OLD = `        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }`;
    const S_NEW = `        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
            this._blockT = (this._blockT || 0) + dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
            this._blockT = Math.max(0, (this._blockT || 0) - dt * 2);
        }`;
    if (!simSrc.includes(S_OLD)) { console.error("!! stuck-detection block not found"); process.exit(2); }
    simSrc = simSrc.replace(S_OLD, S_NEW);
}

const shim = `
;Math.random = __rng;
globalThis.__HL = { BattleSimulation, BattleUnit, Projectile, MeleeEffect, TILE_SIZE };
globalThis.__setSim = function (s) { simulation = s; };
`;
const combined = [
    read("constants.js"), read("unit_sprites.js"), read("api_client.js"),
    read("sim_params.js"), simSrc, shim,
].join("\n;\n");
const ctx = vm.createContext(sandbox);
vm.runInContext(combined, ctx, { filename: "combined.js" });
const { BattleSimulation } = sandbox.__HL;

// ---- run one battle (team1 = subject, team2 = opponent) ----------------------
async function runFight(cd1, slug1, civ1, n1, cd2, slug2, civ2, n2, seed) {
    sandbox.__setSeed(seed);
    const fakeCanvas = { width: 900, height: 600, style: {}, getContext: () => elStub(),
        getBoundingClientRect: () => ({ width: 900, height: 600, left: 0, top: 0, right: 900, bottom: 600 }) };
    const sim = new BattleSimulation(fakeCanvas);
    sandbox.__setSim(sim);
    sim.updateStats = () => {}; sim.updateDebugPanel = () => {}; sim.render = () => {};
    const key = (civ, slug) => `/api/ref/combat-unit/${encodeURIComponent(civ)}/${slug}?age=Imperial`;
    const STATS = { [key(civ1, slug1)]: cd1, [key(civ2, slug2)]: cd2 };
    sandbox.fetch = async (url) => ({ ok: true, json: async () => STATS[url] });
    await sim.setupTeam(1, slug1, civ1, n1, "Imperial", {});
    await sim.setupTeam(2, slug2, civ2, n2, "Imperial", {});
    sandbox.fetch = defaultFetch;
    if (process.env.BLOCK) {   // compact-block spawn (matches the real ~16x16 arena)
        const gap = parseFloat(process.env.GAP || "130");
        const blockify = (team, cx) => {
            const n = team.length; if (!n) return;
            const r = team[0].radius; const sp = r * 2.0 * (PACK < 1 ? PACK : 1);
            const cols = Math.max(1, Math.round(Math.sqrt(n))); const rows = Math.ceil(n / cols);
            for (let i = 0; i < n; i++) {
                const rr = Math.floor(i / cols), cc = i % cols;
                team[i].x = cx + (cc - (cols - 1) / 2) * sp + (rng() - 0.5) * 2;
                team[i].y = 300 + (rr - (rows - 1) / 2) * sp + (rng() - 0.5) * 2;
            }
        };
        blockify(sim.team1, 450 - gap); blockify(sim.team2, 450 + gap);
    }
    const STEP = 1 / 60; let t = 0;
    while (sim.winner === null && t < MAX_S) { sim.update(STEP); t += STEP; }
    const alive = (tm) => sim[tm].filter((u) => u.state !== "dead").length;
    const hp = (tm) => sim[tm].reduce((s, u) => s + Math.max(0, u.currentHp), 0);
    const mhp = (tm) => sim[tm].reduce((s, u) => s + u.maxHp, 0);
    const h1 = hp("team1") / Math.max(1, mhp("team1"));
    const h2 = hp("team2") / Math.max(1, mhp("team2"));
    let winner = sim.winner;
    if (winner === null) winner = h1 > h2 ? 1 : h2 > h1 ? 2 : 0;
    return { winner, alive1: alive("team1"), alive2: alive("team2"), h1, h2,
             margin: (h1 - h2) * 100, time: sim.battleTime };
}
module.exports = { runFight, RAMP, N_SEEDS, MAX_S, sandbox };

// ---- main: validate against the 12 in-game fights ---------------------------
if (require.main === module) {
    (async () => {
        const cds = JSON.parse(fs.readFileSync(path.join(HERE, "combat_dicts.json"), "utf8"));
        const fights = JSON.parse(fs.readFileSync(path.join(HERE, "fights.json"), "utf8"));
        const cdE = cds["Muisca/elite_temple_guard_muisca"];
        console.log(`=== headless simulate.js  PACK=${PACK} AVHALO=${AVHALO} AVFORCE=${AVFORCE} FLANK=${process.env.FLANK || 0} BLOCK=${process.env.BLOCK ? 1 : 0}  seeds=${N_SEEDS} ===`);
        let nMatch = 0, nMiss = 0;
        for (const f of fights) {
            const cdO = cds[`${f.opp_civ}/${f.opp_slug}`];
            let wins = 0, eSum = 0, oSum = 0, mSum = 0;
            for (let s = 0; s < N_SEEDS; s++) {
                const r = await runFight(cdE, "elite_temple_guard_muisca", "Muisca", f.etg_start,
                    cdO, f.opp_slug, f.opp_civ, f.opp_start, 1000 + s);
                wins += r.winner === 1 ? 1 : 0; eSum += r.alive1; oSum += r.alive2; mSum += r.margin;
            }
            const wr = wins / N_SEEDS, simWon = wr >= 0.5, match = simWon === f.game_etg_won;
            match ? nMatch++ : nMiss++;
            const gameStr = `E${f.etg_end}:${f.opp_end} ${f.game_etg_won ? "ETGwin" : "ETGlose"}`;
            console.log(`${f.category}  ${f.opp_name}  ${f.etg_start}v${f.opp_start}  ${gameStr}  ` +
                `SIM ${(wr*100).toFixed(0)}%  surv ${(eSum/N_SEEDS).toFixed(1)}:${(oSum/N_SEEDS).toFixed(1)}  ` +
                `margin ${(mSum/N_SEEDS).toFixed(1)}  ${match ? "OK" : "**MISS**"}`);
        }
        console.log(`ramp=${RAMP}: ${nMatch} match / ${nMiss} mismatch (of ${nMatch + nMiss})`);
    })();
}
```

### 5.3 `diag_web.js` — instrumentation (focus-fire / trample / idle)
Wraps `BattleUnit.prototype.takeDamage` (attribute opp→ETG damage; `oppHits` counts every hit;
`secondary = oppHits − primHits` = trample) and `performAttackOn` (`primHits`). Samples at ~4 Hz:
opponents in melee range per living ETG (focus-fire), and fraction of living opponents engaging none
(idle-opp). Supports the same BLOCK/PACK/SLOT env (they propagate through the required `headless_sim`).

```javascript
// Diagnose focus-fire / trample / idle in the headless webapp sim for the 3 flips.
const fs = require("fs"); const path = require("path");
const H = require("./headless_sim");                 // main() does NOT run on require
const { sandbox } = H;
const { BattleSimulation, BattleUnit, TILE_SIZE } = sandbox.__HL;
const cds = JSON.parse(fs.readFileSync(path.join(__dirname, "combat_dicts.json"), "utf8"));
const cdE = cds["Muisca/elite_temple_guard_muisca"];
const FIGHTS = [
    ["Shu", "elite_white_feather_guard_shu", "WhiteFeather", 12, 21],
    ["Tupi", "elite_ibirapema_warrior_tupi", "Ibirapema", 18, 21],
    ["Goths", "elite_huskarl_goths", "Huskarl", 13, 21],
];
// oppHits = every opp->ETG hit; primHits = opp performAttackOn count; trample = oppHits - primHits.
const origTake = BattleUnit.prototype.takeDamage;
let probe = null;
BattleUnit.prototype.takeDamage = function (amount, attacker) {
    if (probe && attacker && attacker.team === 2 && this.team === 1) { probe.oppDmg += amount; probe.oppHits += 1; }
    return origTake.call(this, amount, attacker);
};
const origPAO = BattleUnit.prototype.performAttackOn;
BattleUnit.prototype.performAttackOn = function (target) {
    if (probe && this.team === 2) probe.primHits += 1;
    return origPAO.call(this, target);
};
async function run(civ, slug, name, ne, no, seed = 1000) {
    sandbox.__setSeed(seed);
    const fake = { width: 900, height: 600, style: {}, getContext: () => new Proxy({}, { get: () => () => {} }),
        getBoundingClientRect: () => ({ width: 900, height: 600, left: 0, top: 0, right: 900, bottom: 600 }) };
    const sim = new BattleSimulation(fake);
    sandbox.__setSim(sim);
    sim.updateStats = () => {}; sim.updateDebugPanel = () => {}; sim.render = () => {};
    const key = (c, s) => `/api/ref/combat-unit/${encodeURIComponent(c)}/${s}?age=Imperial`;
    const STATS = { [key("Muisca", "elite_temple_guard_muisca")]: cdE, [key(civ, slug)]: cds[`${civ}/${slug}`] };
    sandbox.fetch = async (u) => ({ ok: true, json: async () => STATS[u] });
    await sim.setupTeam(1, "elite_temple_guard_muisca", "Muisca", ne, "Imperial", {});
    await sim.setupTeam(2, slug, civ, no, "Imperial", {});
    if (process.env.BLOCK) {
        const gap = parseFloat(process.env.GAP || "80"); const PACK = parseFloat(process.env.PACK || "1");
        const blockify = (team, cx) => {
            const nn = team.length; if (!nn) return;
            const r = team[0].radius, sp = r * 2.0 * (PACK < 1 ? PACK : 1);
            const cols = Math.max(1, Math.round(Math.sqrt(nn))), rows = Math.ceil(nn / cols);
            for (let i = 0; i < nn; i++) { team[i].x = cx + (i%cols - (cols-1)/2)*sp; team[i].y = 300 + (Math.floor(i/cols) - (rows-1)/2)*sp; }
        };
        blockify(sim.team1, 450 - gap); blockify(sim.team2, 450 + gap);
    }
    probe = { oppDmg: 0, primHits: 0, oppHits: 0 };
    const ff = [], idle = []; const STEP = 1 / 60; let t = 0, k = 0;
    while (sim.winner === null && t < 180) {
        sim.update(STEP); t += STEP; k++;
        if (k % 15 === 0) {          // ~4 Hz
            const le = sim.team1.filter((u) => u.state !== "dead");
            const lo = sim.team2.filter((u) => u.state !== "dead");
            if (le.length && lo.length) {
                for (const e of le) {
                    let n = 0;
                    for (const o of lo) { const eff = o.attackRange + o.radius + e.radius;
                        const dx = o.x - e.x, dy = o.y - e.y; if (Math.sqrt(dx*dx+dy*dy) <= eff) n++; }
                    ff.push(n);
                }
                let engaged = 0;
                for (const o of lo) for (const e of le) { const eff = o.attackRange + o.radius + e.radius;
                    const dx = o.x - e.x, dy = o.y - e.y; if (Math.sqrt(dx*dx+dy*dy) <= eff) { engaged++; break; } }
                idle.push((lo.length - engaged) / lo.length);
            }
        }
    }
    const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
    const dpa = probe.primHits ? probe.oppDmg / probe.primHits : 0;
    const secPct = probe.primHits ? (100 * (probe.oppHits - probe.primHits) / probe.primHits) : 0;
    const le_len = (tm) => sim[tm === 1 ? "team1" : "team2"].filter((u) => u.state !== "dead").length;
    console.log(`${name}  ETG:${le_len(1)}:${le_len(2)}  t=${sim.battleTime.toFixed(0)}s  ` +
        `primHits=${probe.primHits} trample=${probe.oppHits - probe.primHits}(${secPct.toFixed(0)}%)  ` +
        `dmg/atk=${dpa.toFixed(1)}  focus-fire=${mean(ff).toFixed(2)}  idle-opp=${(mean(idle)*100).toFixed(0)}%`);
}
(async () => { for (const f of FIGHTS) await run(...f); })();
```

### 5.4 The `simulate.js` mechanics touched (for reference)
- `moveTowardTarget(dt, allUnits)`: seek(target) + `calculateAvoidance` (soft separation), smoothed
  velocity, then stuck-detection (`stuckTimer`; at >0.8s adds target to `blockedTargets`, nulls it).
- `calculateAvoidance(allUnits)`: for every other unit within `1.5×minDist` (minDist = r+r+2 = 30px),
  add a repulsive force (`3+overlap*5` when overlapping, else `0.5`). Halo active to **45px**.
- `resolveCollisions`: hard positional push-apart to `minDist = r+r+1 = 29px`, 3 passes per tick.
- `findTarget(enemies)`: nearest enemy not in `blockedTargets`, else nearest overall. Called only
  when target is null/dead. Resets `stuckTimer=0`, `lastDistToTarget`.
- `inRange()`: `dist ≤ attackRange + r_self + r_target`. Melee `attackRange = MELEE_RANGE_BUFFER = 5px`.
- Geometry: unit radius = `10 + min(outline,1)*20` px; ETG r=14px. Melee contact ring = 5+14+14 =
  **33px = 1.10 tiles** (TILE_SIZE=30). CANVAS 900×600 = 30×20 tiles.
- `setupTeam`: spawns each army as a **single full-height column** at left/right (x = 30+r or W−30−r),
  spread over the full 600px height. This is the "single-column" limitation shared with the position
  sim; the BLOCK env overrides it with a compact grid.

---

## 6. Deep-dive workflow findings (3 parallel agents, verbatim)

A parallel workflow ran three investigators: (A) sim idle-diagnosis, (B) in-game data mining, (C)
AoE2 pathfinding reference. Their structured findings:

### 6.1 Sim idle-diagnosis (Huskarl fight, BLOCK GAP=80 PACK=0.5)
- **Root cause:** "Melee combat has zero lateral/wrap steering, so the 21-Huskarl block queues
  single-file behind its own front rank, and the avoidance collision wall (45px) — which is larger
  than the 33px melee-contact ring — repels the rear ranks before they can reach striking distance,
  capping active attackers at ~7 while ~32% of living Huskarls stall in 'moving' just outside contact."
- **idle-opp:** time-avg **32.2%** (per-seed 36.2 / 28.3 / 32.1). **Mean Huskarls in melee = 7.13**
  of ~13 alive of 21 total; **peak simultaneous 11–12**.
- **Effective-attackers curve (seed 1000):** t=0.5s:0, 1.0s:0, 1.5s:4, 2.0s:6, 3.0s:7, 3.5–4.5s:8,
  5.0s:9, 6–7s:10, plateau ~8–11. Against the 21 total: 0% for ~1s, ~38% by 4s, peak ~52%. Idle
  drains to 0 only after ~14.5s once attrition thins the block.
- **Key numbers:** "100% of idle-Huskarl samples (699/699) have a living ally straddling the line to
  their nearest ETG → blocked by own front rank"; "79% of idle Huskarls are within 45px of an ENGAGED
  front-rank ally"; "Idle-Huskarl state 100% 'moving'"; "target==null ~1–2%"; "stuckTimer mean
  0.21–0.24s (only ~30% >0.3s)"; "distance to nearest ETG mean 1.91–1.97 tiles"; "0% ever wrap to the
  ETG far side"; "geometric contact ring fits ~25 Huskarls, only ~7 engaged → cap is NOT the binding
  limit; the single-file column + front-rank wall is."
- **Fix implications:** "(1) close the collision-vs-contact gap … (2) add tangential/flanking steering
  … (3) do NOT rely on stuck→blockedTargets→null-target: it re-picks the same nearest ETG every frame …
  retargeting must be paired with actual lateral movement or a 'attack an ETG that has fewer attackers
  on it' load-balancing rule." (Note: this project's subsequent testing found the tangential steering
  scatters units in this engine; the load-balancing rule = Part B is what worked.)

### 6.2 In-game data mining
- **Data available:** the `.hp.json` sidecars are AGGREGATE per-side only (`[game_s, side1{count,hp},
  side2{count,hp}]` at ~0.59s cadence; `game_s` is already VIDEO seconds = game-sim seconds / 1.7).
  No per-unit data in the sidecar. The three unexpected-win fights: Huskarl (13 ETG/1495hp vs 21/1470,
  ETG 0 / Husk 4), White Feather (12/1380 vs 21/2100, 0 / 2), Ibirapema (18/2070 vs 21/1890, 0 / 17).
- **Per-unit positions ARE capturable:** the gRPC decoder already parses per-unit `world_x`(idx 3),
  `world_y`(4), `state`(8), `hp`(12), `owner`(2), `type`(11) — schema in `aoe2x/grpc/reference_model.rs`
  (Entity struct lines 673–718); `aoe2x/grpc/decode_state_v2.py` writes all fields into `entity_store`
  and already prints a per-entity x/y/hp/state debug table (lines ~891–904). `aoe2x/grpc/redecode_hp.py`
  just aggregates them away (`totals()`/`derive_army()`). **BUT the raw streams (`*.frames.bin`) for the
  12 recorded fights were NOT archived** — only `.hp.json` + `.mp4` remain — so per-unit data requires a
  **re-record** with a ~10-line emitter added to `redecode_hp.py`, not an offline backfill.
- **Huskarl attrition analysis:** the ETG and Huskarl HP curves fall **near-parallel** for the first
  ~4–5s (dead heat: at t4.7s ETG 1117 vs Husk 1120), then diverge; total damage dealt is **nearly EVEN**
  (Huskarls 1495, ETG 1344; ratio 1.11). "The Huskarls win purely because they started with 21 bodies
  vs 13 … ETG runs out of models first." → the single-column failure mode.
- **Inferred effective attackers (the key result):** using Huskarl 14 dmg/hit ÷ 2.0s = 7 dmg/s each,
  effective Huskarls landing = (−dHP_ETG/dt)/7. Curve: t2.4=23.7, t3.5=25.4, t4.7=24.3, t5.3=27.7,
  t6.5=24.1, … i.e. **~100–140% of the alive Huskarl count from the very first data point** — "it does
  NOT start low and rise. … full engagement from t=0." ETG-on-Huskarl similarly ~full engagement. "Both
  sides are essentially fully committed immediately; this is a fair fight decided by unit count,
  confirming the encirclement is instantaneous in-game, not gradual."
- **Path to capture per-unit:** add an emitter in `redecode_hp.py` main loop reading `e.get(3/4/5/12/8)`
  per unit to a `<pfx>.units.jsonl`; optionally drop the one-row-per-second gate for finer cadence.

### 6.3 AoE2:DE pathfinding reference (with sources)
- **Two-layer movement:** tile-based A* (fixed/sped-up in DE) returns coarse waypoints; low-level
  steering uses **circular unit obstructions**, prefers straight-line when safe, has a stuck-unit
  watchdog. Melee target selection = **"attack the nearest reachable enemy"**; a commanded target is
  honored only ~1s then it redirects to the closest enemy ("so group attack works without units
  overprioritizing a single targeted enemy").
- **Encirclement is EMERGENT** — no flank/surround command. It falls out of: (1) nearest-reachable
  targeting re-evaluated frequently, (2) hard circular collision (finite contact ring), (3)
  straight-line-preferred steering + stuck watchdog. Overflow attackers with nothing reachable in
  front flow along the perimeter to the flanks/rear because those become the nearest reachable enemies.
  "The bigger the numeric edge, the more overflow wraps around … super-linearly lethal
  (Lanchester-square-like)."
- **Max attackers per defender ≈ 6** (occasionally 7–8): kissing-number geometry — attacker centers
  sit at ~2r from the defender and mustn't overlap each other; `2·asin(0.5)=60°`, `360/60=6`. Gives the
  outnumbering side a ~6:1 local damage ratio at each wrapped defender.
- **Where the abstract sim diverges + minimal principled fix (no fudge):**
  "(A) Give every unit a hard circular collision radius r (≈0.2 tile) and resolve overlaps as a
  positional constraint, NOT a soft boids force … only ~6 attacker disks fit tangent around a defender.
  (B) Make target selection 'nearest REACHABLE enemy', re-evaluated every tick: a unit whose nearest
  enemy's contact ring is full treats it as not-currently-reachable and picks the next nearest …
  encirclement emerges. That's the whole fix … no explicit surround bonus / flank multiplier /
  Lanchester exponent needed." Splash/trample should be modeled separately as AoE-per-swing.
  Sources: richg42.blogspot.com/2018/02/on-age-des-pathingmovement.html;
  forums.ageofempires.com/t/units-attack-closest-target-over-commanded-target/66582;
  ugc.aoe2.rocks/general/attributes/attributes/; ageofempires.fandom.com/wiki/Unit_formation.

**Note on Part A vs the reference:** the reference recommended replacing soft separation with hard
collision. This project's E10 test of *reducing* soft avoidance BACKFIRED (idle 41→49%) because in
THIS engine the soft halo provides useful lateral dispersion and the hard-collision layer
(`resolveCollisions`) is a post-hoc positional push, not a continuous constraint. So the reference's
part (A) does not transfer cleanly to this engine's movement model; part (B) (reachability targeting)
is what worked (Part B / E11–E16). Reconciling this is an open item (§8).

---

## 7. Current state

- **Shipped to the repo:** the 5s-window ramp fix in `apps/website/static/js/simulate.js`
  (Temple-Guard-only; frontend only; does NOT bump `sim_version`; nothing pushed).
- **Experimental (scratchpad only, via env knobs; NOT in the repo):** PACK, BLOCK/GAP, SLOT, FLANK,
  AVHALO/AVFORCE source-replacements in `headless_sim.js`.
- **Best principled config:** window ramp + BLOCK GAP=80 + PACK=0.5 + SLOT=3–4 → halves the ETG
  margins, White Feather becomes a coin-flip, all 9 correct fights hold; Huskarl/Ibirapema still
  ETG-win (~27 / ~43). This is ~9.5/12, up from 9/12, with the errors substantially reduced.
- **Nothing committed or pushed** this session beyond the ramp edit on the working branch.

---

## 8. Open questions / path forward (for the next analyst)

1. **Why does SLOT-spreading hurt Ibirapema but help the attrition fights?** Slot-awareness disperses
   attackers, reducing trample concentration. The trample-packing and slot-spreading mechanisms
   conflict. A faithful model needs BOTH: dense packing for AoE units + full engagement for attrition.
2. **The residual idle ~32% is a physical-routing failure.** This engine's `seek + soft-avoid +
   post-hoc resolveCollisions` movement cannot route rear units around their own front rank fast
   enough (the game does it instantly). Steering hacks (flank tangent) scatter. Options:
   - **(A) Model the observed mechanic directly:** in-game engagement is instant + full up to the
     per-defender cap (~6). Implement "effective attackers = min(alive_enemies, Σ min(6, …))" reached
     ~immediately — data-grounded (matches the measured 100–140%-from-t0 curve), not a fudge. Likely
     flips all 3 cleanly. Doable offline (no re-record).
   - **(B) Re-record per-unit positions** (add the `redecode_hp.py` emitter; §6.2) to get ground-truth
     trajectories and calibrate the envelopment/effective-attacker function directly. Needs the game
     running.
   - **(C) Ship Part B (slot-aware targeting) as the improvement** and correct the residual near-coin-
     flips (White Feather, Huskarl) using the in-game outcomes already recorded; flag that fight class
     as lower-confidence in the pool ranking.
3. **Hard-disk collision done right:** re-implement `resolveCollisions` as a proper continuous
   constraint AND weaken soft avoidance together (the reference's part A) — E10 only did half of it
   and backfired. Worth testing whether the full swap reproduces the ~6-cap packing without losing
   dispersion.
4. **Generalization / overfitting guard:** any envelopment change is global (affects all ~500k
   matchups' interactive sims). It must (a) keep all 9 correct ETG fights correct, (b) not distort the
   many non-swarm matchups, (c) be justified by the real mechanic, not tuned to 12 data points. SLOT=3
   is already at the aggressive end; going lower to force flips would overfit.

## 9. Reproduction quick-reference
```bash
# 1. dump combat dicts + fights (system python with aoe2x on path)
python $SP/export_fights.py
# 2. baseline (ship-equivalent; the file now has the window ramp)
cd $SP && SEEDS=6 node headless_sim.js
# 3. best principled config
SLOT=3 BLOCK=1 GAP=80 PACK=0.5 SEEDS=6 node headless_sim.js
# 4. diagnostics (focus-fire / idle / trample) for the 3 flips
SLOT=3 BLOCK=1 GAP=80 PACK=0.5 node diag_web.js
```
Env knobs (all optional, default = ship behavior): `RAMP=ship|window|off`, `PACK=<float>` (1.0=ship),
`BLOCK=1` + `GAP=<px>` (compact-block spawn), `SLOT=<int>` (per-defender reachability cap), `FLANK=<f>`
(tangential slide — found harmful), `AVHALO`/`AVFORCE` (avoidance halo/standoff — Part A, found harmful).
`SEEDS`, `MAXS` control sampling. Seeds are `1000..1000+N`; PRNG is mulberry32 (deterministic).

---

## 10. In-game multi-run validation — the COIN-FLIP finding (2026-07-06, added after §0–§9)

### 10.1 Why this section supersedes the premise
Everything in §0–§9 rested on **one filmed recording per fight**. The single Huskarl recording
(ETG 0 : Huskarl 4) implied a clean ETG loss, which framed the whole investigation as "the sim
wrongly says ETG wins; make it flip to ETG-loss." To test that premise's robustness, ETG(13) vs
Huskarl(21) was re-run in-game **20 times**. The premise was wrong: **the matchup is an even
coin-flip**, not an ETG loss.

### 10.2 Method — the golden recording rig, record-only
- Requires **AoE2:DE running, fullscreen in the Scenario Editor**. Rig lives in `apps/video`, run with
  its `.venv` python (`apps/video/.venv/Scripts/python.exe`), which has the deps (AoE2ScenarioParser,
  opencv, rapidocr, pydirectinput, grpc). System python lacks these.
- Single-fight entry point (`auto.orchestrate_matchup.run_matchup`):
  `run_matchup(civ1, slug1, civ2, slug2, name=, raw_copy_to=, mode="resources", unit_cap=21,
  live_overlay=True, compose=False, build_fn=build_golden_from_sides)`. `civ1/slug1` = subject (ETG,
  → player P2); `civ2/slug2` = opponent (Huskarl, → P3). `unit_cap=21` = arena cap. `mode="resources"`
  = equal 3000 resources (cheaper unit capped at 21). **`compose=False` = RECORD-ONLY**: skips the
  CPU-bound video compose but STILL writes the gRPC `.hp.json` sidecar (line 524) AND archives the
  raw `.frames.bin` stream (per-unit game state) next to the `.mov`.
- Drivers (in `$SP`): `run_huskarl_5x.py` (runs 1–5), `run_huskarl_15more.py` (runs 6–20). Each loops
  `return_to_editor()` → `run_matchup(...)`; sidecars land in `$SP/huskarl_verify/raw recordings/
  huskarl_verify_<i>.hp.json`. ~105 s/run.
- **Read-only game-state check before injecting input** (confirm the editor is up):
  `from auto.platform_io import grab; from auto.vision import detect_state; detect_state(grab())`
  → `"editor"`; `from auto.orchestrate_matchup import _in_editor`.
- Sidecar = AGGREGATE per-side time-series: `rows[] = [{game_s, side1{count,hp}, side2{count,hp}}]`
  at ~0.6 s cadence (`game_s` already in video seconds = game-sim / 1.7). ETG = the side whose start
  hp/count ≈ 115. Winner's remaining HP% = final army hp / start army hp.

### 10.3 Results — 20 in-game runs (ETG 13 vs Huskarl 21, equal 3k)
`S = ETG_hp% − Huskarl_hp%` (the DB score convention). Loser is wiped to 0% in every run.
```
run winner  ETGhp%  Huskhp%    S       run winner  ETGhp%  Huskhp%    S
  1 ETG      30.6     0.0  +30.6        11 ETG      13.4     0.0  +13.4
  2 Husk      0.0    21.9  -21.9        12 Husk      0.0     7.6   -7.6
  3 Husk      0.0    22.9  -22.9        13 ETG      15.3     0.0  +15.3
  4 Husk      0.0    31.4  -31.4        14 Husk      0.0    19.0  -19.0
  5 ETG      28.6     0.0  +28.6        15 ETG      26.9     0.0  +26.9
  6 ETG       4.5     0.0   +4.5        16 ETG       9.0     0.0   +9.0
  7 ETG      27.8     0.0  +27.8        17 ETG      13.5     0.0  +13.5
  8 Husk      0.0     9.5   -9.5        18 Husk      0.0    17.1  -17.1
  9 ETG      16.4     0.0  +16.4        19 ETG      42.5     0.0  +42.5
 10 Husk      0.0    16.2  -16.2        20 Husk      0.0    11.4  -11.4
```
- **ETG win-rate = 11/20 = 55%** (Huskarl 9/20 = 45%) — a coin-flip, decided by the opening clash.
- **mean score S = +3.6, sd 21.2** — statistically **even**; the large sd is the bimodality.
- **winner HP% = mean 19% / median 17% / range [5, 42]** (when ETG wins: mean 21%, n=11; when Huskarl
  wins: mean 17%, n=9). Fights last ~22–32 s.
- The first-5 sample alone read 40% (2/5) — small-sample noise; 20 runs settle at ~55%.

### 10.4 What the SHIPPED matchup DB stores for this pair
Query on `C:\AI\matchup_baseline_177723.db` (302 MB; produced by the single-column
`simulation_real.py`, 8 seeds each). `matchup_means` (score = mean of `(team1_hp_pct−team2_hp_pct)×100`):
```
elite_temple_guard_muisca vs elite_huskarl_goths  @30v30  mean=+65.58  sd=4.5  n=8  verdict=win
elite_temple_guard_muisca vs elite_huskarl_goths  @3k     mean=+42.59  sd=4.8  n=8  verdict=win
```
`matchup_battles` (representative aggregated row; team1=ETG, team2=Huskarl; hp_pct = fraction):
```
@30v30  ETG 30 v 30 Husk | winner=1  ETGhp%=0.66 surv=28  Huskhp%=0.0 surv=0  runs=8 sd=4.5 t=35s
@3k     ETG 20 v 30 Husk | winner=1  ETGhp%=0.40 surv=15  Huskhp%=0.0 surv=0  runs=8 sd=4.8 t=38s
```
So the DB is **confident ETG win (+42.6 @3k, +65.6 @30v30, sd ~4.5 — never wavers)**, ETG keeping
40–66% HP. NOTE the DB uses **different counts** (@3k = 20 v 30, not the arena's 13 v 21; it does not
apply the 21-cap), which makes the single-column envelopment failure worse and inflates the ETG edge.

### 10.5 What the IMPROVED sim produces (per-seed distribution)
`$SP/huskarl_sim_dist.js` (env `SLOT=3 BLOCK=1 GAP=80 PACK=0.5`, 20 seeds, ETG 13 v 21):
- **ETG win-rate 20/20 = 100%**; winner HP% mean **26.0%**, range [17, 33]; **mean S = +26.0**.
- Every seed lands ETG-win at ~26% HP — unimodal; it never reaches the Huskarl basin for this fight.
  (For Ibirapema the improved sim DOES reach both basins — block+pack put it at ~50%, a real
  coin-flip — so bimodality is matchup-dependent.)

### 10.6 Three-way comparison + conclusions
| Source | Counts | ETG win-rate | Mean score S | Winner HP% |
|---|---|---|---|---|
| **Game (20 runs)** | 13 v 21 | **55%** | **+3.6** (sd 21) | ~17–21% |
| Improved sim (SLOT=3) | 13 v 21 | 100% | +26.0 | ~26% |
| Shipped DB @3k | 20 v 30 | 100% | +42.6 | ~40% |
| Shipped DB @30v30 | 30 v 30 | 100% | +65.6 | ~66% |

1. **The matchup is EVEN** (mean S ≈ +3.6, 55/45). Correct bucket for Huskarl = **"even / toss-up"** —
   NOT "unexpected win" (DB) and NOT "clear loss" (single recording).
2. **Shipped DB is the most wrong**: +42.6 vs true ~0, and it overstates the winner's HP cushion
   (ETG ~40% vs game ~25%). Its tiny sd (4.5) means it is confidently wrong.
3. **The improved sim's error is win-RATE, not margin.** Its winner-HP% (~26%) MATCHES the game's
   magnitude (~25%), and its +26 ≈ the game's *conditional* "when ETG wins" margin (~+21). It is even
   directionally right (the game IS 55% ETG). Its only failure is landing in the ETG basin 100% of the
   time instead of ~55% — i.e. it does not reproduce the coin-flip. More seeds do NOT fix this (all 20
   land ETG); the basin is decided by chaotic opening-clash dynamics the sim doesn't replicate at the
   right frequency.
4. **REFRAMED GOAL:** the sim does not need to "flip" these fights to ETG-loss (§0–§9's framing). It
   needs to represent them as **near-even / high-variance coin-flips** (score ≈ 0, wide spread). Since
   the improved sim already gets the win *magnitude* right, the remaining work is reproducing the
   *win-basin frequency* (the opening-clash variance) — a different, arguably harder problem than the
   envelopment fix, and one better settled by multi-run in-game ground truth for the marginal fights.
5. **Single recordings mislead** for high-variance swarm fights — use ~20 runs. White Feather and
   Ibirapema are **not yet multi-run-verified** (their single 0:2 and 0:17 recordings likely also
   understate variance; WFG is probably a coin-flip too, Ibirapema's trample blowout probably robust).

### 10.7 Bonus — per-unit trajectories are now captured
Because the 20 runs used record-only mode, each archived its raw `.frames.bin` next to the `.mov` in
`$SP/huskarl_verify/raw recordings/`. Per §6.2 the decoder (`aoe2x/grpc/decode_state_v2.py`) reads
per-unit `world_x`/`world_y`/`hp`/`state` from that stream — so **per-unit position/HP trajectories
for the Huskarl fight ARE now recoverable** (the thing §6.2 said would need a re-record), ready to
directly calibrate an envelopment / effective-attacker model.

---

## 11. The physical fix — calibrated from the per-unit decodes (2026-07-06, evening)

### 11.1 Per-unit decode of the 20 runs (`$SP/decode_units.py`, ~0.6s/run)
Reuses `redecode_hp.py`'s segment logic but samples per-unit `(x, y, hp)` every 250ms (fields:
1=master, 2=owner, 3=x, 4=y, 8=state, 12=hp). Writes `<pfx>.units.json`. All 20 fights decode to
start (13,21); outcomes match the sidecars exactly.

### 11.2 What the ground truth says (`analyze_units.py`, `analyze_decision.py`)
1. **Initial formations are IDENTICAL in all 20 runs** (units on tile centers; ETG box x[2.5..9.5]
   y[2.5..8.5], Husk box x[6.5..13.5] y[5.5..12.5], diagonal, nearly touching). The 55/45 coin-flip
   comes entirely from engine-internal micro-nondeterminism amplified by chaos — NOT from spawn.
2. **The opening does NOT decide the fight; the 6–10s death-reshuffle does.** Every run: D(t) =
   ETG_hp%−Husk_hp% is slightly NEGATIVE at t=2–6s (−2..−6, both E-wins and H-wins). sign(D)
   predicts the final winner only 10/20 at t=6s → **19/20 at t=10s**. Median decision ~7s into ~40s.
3. **Engagement:** Huskarls engaged (≤0.8t of a living ETG): 50% at first blood, 73% t+1, 83% t+2,
   88% t+3, 90% t+5, dip 68% t+8 (post-death walk), ~85% after. Per-ETG attacker loads max 3–5
   (typical [3,2,2,2]) — the theoretical ~6 cap never binds at 21v13.
4. **Effective reload (hp-drain / 14dmg / living units), the decisive measurement:**
   ```
   window   ETG    Husk        window   ETG    Husk
   t0-2    2.20    3.09        t8-10   5.86    8.82   <- death-reshuffle stall
   t2-4    1.93    2.51        t10-12  2.97    4.54
   t4-6    1.84    2.45        t12-16  ~2.5    ~3.2
   t6-8    3.90    5.97        t16-20  ~3.0    ~3.7
   ```
   BOTH sides run 25–45% over nominal (2.0s) continuously — mêlée churn (chasing moved targets,
   shoving, turning). The ETG ramp nets only a ~25–30% rate edge (ratio ~0.75–0.85), never the
   static-melee 1.67x the sim produced. The t6–10 stall (reload 4–9s!) is the mass repathing after
   the first death wave — exactly where the basins bifurcate.

### 11.3 The physics package (harness env knobs; all in `$SP/headless_sim.js`)
| Knob | Mechanism | Physical grounding |
|---|---|---|
| `RTRUE=1` | collision radius = `outline_size * TILE_SIZE` (ETG 6px) instead of `10+outline*20` (14px) | the ship formula is a RENDERING choice leaked into physics; bodies were 2.3x too fat -> traffic jam. Fixes idle 32%→~10% ALONE. |
| `ADELAY/AJIT` | melee arrival wind-up: first swing after ANY movement pays `max(cd, A+rand*J)` (melee branch had NO gate — `wasMoving` was never consumed) | stop/turn/raise-weapon; staggers first contact like the game |
| `RETARGET/JITTER` | ADDITIVE cooldown on target switch (`max()` is swallowed by the 1.8s reload) | walk+re-engage after your target dies; reproduces the t6–10 stall |
| `CHURN` (+`CROWDN`) | per-swing `+rand[0,CHURN)*crowding` for melee, crowding = neighbors≤2t / CROWDN, saturating | crowd interference; decays the ramp window naturally; vanishes in mop-up |
| `SPAWN=game` / `BSP=30` | exact decoded spawn / tile-center block spacing | removes spawn-geometry guesswork |

### 11.4 Calibration results (ETG 13 v Huskarl 21, 20 seeds, `huskarl_validate.js`)
| Config | win% | S mean | S sd | winner hp% |
|---|---|---|---|---|
| RTRUE only | 100% | +45.3 | 0.0 (deterministic!) | 45 |
| + wind-ups (RETARGET max-based) | 100% | +41 | 0.7 | 41 |
| + additive RETARGET 1.6/1.6 | 100% | +19.4 | 3.5 | 19 |
| + CHURN 3.0, RT 1.5 | 70% | +7.1 | 12.1 | 13 |
| + crowd-scaled CHURN 3.5, RT 1.5 | **70%** | **+8.0** | **11.6** | **13** |
| **GAME (20 runs)** | **55%** | **+3.6** | **21.2** | **19** |
Bimodality achieved; win-rate within the n=20 CI of 55% ([32,77]). Residual gaps: sd 12 vs 21 and
winner-hp 13 vs 19 (the game snowballs harder once ahead).

### 11.5 THE 12-FIGHT SUITE: 11/12 (was 9/12), and the "miss" is the suspect label
`RTRUE=1 BLOCK=1 GAP=160 BSP=30 CHURN=3.5 RETARGET=1.5 JITTER=0.8 ADELAY=0.4 AJIT=0.8 SEEDS=8`:
- All 9 previously-correct fights stay correct AND stay decisive (cav +60..70; ranged −85..−100;
  melee counters −50..−61) — the knobs do not flatten genuine verdicts.
- **Ibirapema: 0% ETG, −36.5** — now a proper loss (true radii + tile spawn let trample land). OK.
- **Huskarl: 25% ETG, −9.0** — near-even, bimodal ⇒ "even" bucket ✓ (game 55/45).
- **White Feather: 63% ETG, +1.2** — the nominal MISS, but the sim says *coin-flip*, and WF's
  ground-truth label rests on a SINGLE recording where it lost by 2 units of 21. Very likely WF is
  a coin-flip in reality too ⇒ needs its own 20-run in-game validation before calling this a miss.

### 11.6 Bucket rule + next steps
- Coin-flip detection: per-seed S distribution bimodal or |mean S| below ~10–12 with both basins
  occupied ⇒ "even/toss-up", listed at the end of the video. One-sided distributions at +26 stay
  genuine counters (the user's discriminator).
- Next: (1) 20-run in-game White Feather validation (Ibirapema optional — sim & single recording
  agree on a blowout); (2) ship the package to `simulate.js` (decouple DRAW radius from COLLISION
  radius — rendering can keep 10+outline*20; physics uses outline*TILE_SIZE); (3) re-sim the ETG
  pool with the new physics and re-segment.

---

## 12. Alternate simulation model "v2" + the three-engine pool comparison (2026-07-06)

### 12.1 The model, recorded (`$SP/sim_v2_model.js`)
The physical fix (§11.3) is frozen as a named, self-contained model: `sim_v2_model.js` sets the
calibrated knobs and re-exports the real headless runner, so v2 = the REAL `simulate.js` + these
transforms (no fork; stays in lockstep with shipped combat):

```
RTRUE=1                collision radius = outline_size*TILE_SIZE (game-true body), NOT 10+outline*20
ADELAY=0.4 AJIT=0.8    melee arrival wind-up: first swing after moving pays max(cd, 0.4+rand*0.8)s
RETARGET=1.5 JITTER=0.8 additive cooldown on target switch (death-reshuffle stall)
CHURN=3.5 CROWDN=6     per-swing +rand[0,3.5)*min(1,neighbors/6), melee only (crowd interference)
BLOCK=1 GAP=160 BSP=30 compact 1-tile-spaced block spawn (the ~16x16 arena), not the ship line
RAMP = shipped 5s-window ramp; no SLOT (superseded by RTRUE)
```
Randomness = seeded mulberry32 consumed by the JITTER/CHURN terms → per-seed variance mirroring the
game's engine-timing nondeterminism; same seed ⇒ identical fight.

### 12.2 The three engines compared
| Column | Engine | Positions? | Randomness | Counts |
|---|---|---|---|---|
| **DB** | `simulation_real.py` batch (shipped `matchup_baseline_177723.db`) | single vertical column | multi-seed accuracy/trample | its OWN, uncapped (e.g. Huskarl 20v30) |
| **Abstract** | `simulation.py` (`simulate_battle`) | NONE (tick attrition) | accuracy/trample/scatter only | arena, cap 21 |
| **V2 (new)** | `simulate.js` + §12.1 transforms | full 2D steering + envelopment | wind-up/churn jitter (+combat RNG) | arena, cap 21 |

Arena counts = `equal_resource_counts(cap=21)` (apps/video/auto/pure.py) — the in-game/video
convention (Huskarl → 13 ETG v 21). Both live engines use identical arena counts (apples-to-apples);
the DB keeps its stored uncapped counts (shown in-table).

### 12.3 Method (`$SP`: extract_pool.py → run_abstract.py / run_pool_v2.js → build_table.py)
- Pool = `opponent_pool.build_pool('Muisca','elite_temple_guard_muisca')` = **75** (63 unique units +
  12 generic staples).
- Each engine: **5 seeds; if |mean S| < 33, +10 more (total 15)** — the user's escalation for the
  uncertain (near-even) matchups.
- Abstract sim counts forced exactly via the cost-override trick (`resources=1e5,
  cost_override=1e5//n` ⇒ `count = 1e5 // (1e5//n) = n`).
- Metrics per matchup: ETG win-rate, mean S, sd S, winner-HP%, **bimodal** flag (both basins occupied
  = coin-flip signal). Bucket = ETG win / coin-flip / ETG loss.

### 12.4 Key structural finding (pre-results)
The **abstract sim is deterministic for melee-vs-melee** (sd 0 across seeds — its only RNG is
accuracy/trample/scatter, none of which fire in a melee mirror). It therefore CANNOT produce a
coin-flip for pure-melee fights; every such matchup is unimodal. Only V2 (position chaos) reproduces
bimodality. Example: Huskarl 13v21 — Abstract +20.7 (100% ETG, sd 0, unimodal); V2 −6 (33% ETG, sd 17,
BIMODAL); game +3.6 (55%, sd 21). Full table: `$SP/comparison_table.md` / `.html`.

### 12.5 RESULTS — 75-opponent three-engine comparison (full: $SP/comparison_table.md / .html)
Bucket tallies (ETG win / coin-flip / ETG loss):
```
DB (simulation_real):     37 win / 1 flip / 37 loss
Abstract (simulation.py): 41 win / 0 flip / 34 loss
V2 (new model):           22 win / 9 flip / 44 loss
All three agree: 54/75.
```
**Headline — all 3 filmed fights corrected by V2, matching the game:**
| Opponent | DB | Abstract | V2 | game |
|---|---|---|---|---|
| ★White Feather (Shu) | +46 win | +11 win | **-1 coin-flip** (60%) | lost by 2 (~even) |
| ★Huskarl (Goths) | +43 win | +21 win | **-6 coin-flip** (33%, bimodal) | 55/45 coin-flip |
| ★Ibirapema (Tupi) | +35 win | +15 win | **-35 ETG loss** | 0:17 blowout loss |

**V2's 9 coin-flips** (bimodal, both basins): Arambai, Battle Elephant, Condottiero, Kamayuk,
Blackwood Archer, White Feather, Warrior Priest, Huskarl, Shotel. These are the marginal
swarm/trade fights — exactly the class single recordings mislead on.

**15 DB "ETG win" downgraded by V2** (swarm/envelopment inflation corrected): Arambai +55→+10,
Battle Elephant +56→+9, Condottiero +48→+4, Kamayuk +68→+1, Blackwood +28→+1, White Feather +46→-1,
Warrior Priest +27→-4, Huskarl +43→-6, Shotel +32→-10, Konnik +54→-32, Ibirapema +35→-35,
Genitour +58→-39, Ghulam +55→-42, Woad +24→-45, Berserk +24→-57.

**Abstract sim's structural failures** (why "no positions" is worst for some classes):
- Overrates ETG vs MOBILE RANGED (can't kite): Janissary +8, Conquistador +23, Bolas Rider +27,
  Fire Archer +44, Guecha +26 — all called ETG WIN by abstract, all losses in DB+V2+reality
  (10 such matchups).
- Deterministic for melee mirrors (sd 0) → 0 coin-flips found across the whole pool.

**Where all three agree (54/75):** ETG's designed strengths and hard counters are robust — anti-cav
wins (Heavy Camel +68, Shrivamsha +65, Centurion +63, Tiger Cav +61, Tarkan +59…) and archer/skirm
losses (Chakram -87, Plumed -88, Hand Cannon -81, Longbow -69…) survive all three engines. V2 only
moves the MARGINAL swarm/trade fights, which is the intended behavior.

**Bucket rule confirmed:** genuine counters/wins stay one-basin decisive; only near-even fights go
bimodal. V2 (win 22 / flip 9 / loss 44) is the segmentation to drive the video — the 9 flips are the
"even / coin-flip" tail to list separately.

---

## 13. In-game multi-run validation of 3 V2 predictions (5 runs each, 2026-07-06)
Golden rig, record-only (compose=False), arena counts. Drivers: run_wfg_ibira_5x.py, run_genitour_5x.py.

| Fight | Counts | In-game (5 runs) | V2 (new) | DB | Abstract | Verdict |
|---|---|---|---|---|---|---|
| **Ibirapema** | 18v21 | ETG **0/5**, S=**-51** sd4 (clean LOSS) | -35 LOSS | +35 WIN | +15 WIN | **V2 CORRECT**; DB+abstract dead wrong |
| **White Feather** | 12v21 | ETG **0/5**, S=**-30** sd12 (LOSS, 1 game close -11) | -1 coin-flip (60%) | +46 WIN | +11 WIN | V2 direction right, ~30 too ETG-generous (loss, not toss-up) |
| **Genitour** | 9v21 | ETG **2/5=40%**, S=**+7.6** sd**47.7** (wild COIN-FLIP) | -39 LOSS | +58 WIN | +54 WIN | true toss-up; ALL miss — V2 too harsh, DB+abstract too kind |

Per-run detail:
- WFG: all 5 ETG losses; WFG survivors 5-14 of 21 (11-49% hp). Milder/higher-variance than Ibirapema.
- Ibirapema: all 5 ETG losses; Ibira survivors 16-19 (45-54% hp) — trample blowout, very tight sd.
- Genitour: runs 1,3 = ETG wins HUGE (all 9 survive @ 49-79% hp); runs 2,4,5 = ETG wiped (Geni 5-16
  survive). Extreme bimodality (sd 47.7): if ETG corners the skirmishers it slaughters them; if they
  kite it loses completely.

### 13.1 What the validation says about each engine
- **DB (simulation_real): wrong on all 3** — called every one a confident ETG WIN (+35/+46/+58). The
  single-column-no-kite-no-envelop engine over-values ETG in exactly these swarm/skirmisher fights.
- **Abstract (simulation.py): wrong on all 3** the same way (+15/+11/+54) — no positions ⇒ can't kite
  (Genitour) or trample-cluster (Ibirapema).
- **V2: directionally correct on all 3** (none are ETG wins). Bucket EXACT on Ibirapema; on WFG it says
  toss-up where the truth is a marginal loss (~30 too generous); on Genitour it says clean LOSS where
  the truth is a 40% coin-flip — **V2's skirmisher kiting is TOO effective** (in-game the AI sometimes
  clumps/mis-micros and ETG catches them; V2 kites perfectly every seed → unimodal loss).

### 13.2 Answer: "is Genitour really a loss for the ETG?"
**No — it's a coin-flip (~40% ETG), not a loss.** When ETG wins it wins big (all 9 survive); when it
loses it's wiped. The DB's "+58 decisive win" is wrong, but so is V2's "-39 clean loss." The honest
bucket is EVEN/high-variance. This is the one case where V2's fix over-corrects: its skirmisher
kiting AI is stronger than the game's, converting a real toss-up into a modeled loss. A future
calibration lever = add kiting imperfection (skirmishers occasionally fail to keep distance).

### 13.3 Net
Multi-run ground truth reverses the DB on all 3 filmed "unexpected wins" (all are ETG loss or
coin-flip, never win). V2 is far closer than the DB everywhere and exact on Ibirapema, with a known
residual: it slightly over-punishes ETG in melee-vs-melee (WFG) and over-rewards perfect kiting vs
mounted skirmishers (Genitour). Both residuals are ~1 bucket and in opposite directions, i.e. no
systematic bias — good enough to drive the video's win/coin-flip/loss segmentation.
