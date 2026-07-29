# Simulation engine — findings and the decision to migrate to JavaScript

> **Sub-project 1 (engine extraction + harness) implemented** — see
> [docs/superpowers/specs/2026-07-28-js-engine-extraction-design.md](superpowers/specs/2026-07-28-js-engine-extraction-design.md)
> and [docs/superpowers/plans/2026-07-28-js-engine-extraction.md](superpowers/plans/2026-07-28-js-engine-extraction.md).
> The engine now lives in `apps/website/static/js/engine/` (pure ESM, DOM-free);
> `simulate.js` is the page shell and `sim_renderer.js` the drawing layer. The parity
> gate (`tools/simjs/parity_check.mjs`) proves the extracted engine bit-exact against the
> pre-extraction engine over 205 fights.

**Date:** 2026-07-28 · **Branch:** `improved-simulation` · **Status:** findings recorded,
migration plan not yet written.

**The decision:** stop developing `aoe2x/sim/simulation_real.py`. Make production
`apps/website/static/js/simulate.js` the single engine for both the UI and the batch.

This document records everything measured on 2026-07-28 that led there, so the migration
can start cold. It supersedes nothing in `docs/updated-simulation-results-2026-07-28.md` —
that document is still accurate about the Python engine, but it was written before the
divergence in §6 was discovered, and its framing is therefore misleading.

---

## 1. Why migrate (the short version)

1. **`simulation_real.py` is not the port it claims to be.** Its own docstring says
   "Python port of the JS canvas sim." It has diverged from `simulate.js` in six
   material ways (§6), two of them decisive, and nothing in the codebase compared them.
2. **You can eyeball the JS.** The single biggest practical advantage. On the Battle Sim
   page a wrong result is *visibly* wrong and its cause is usually obvious — e.g. in
   Slinger-vs-Elephant the Slingers scatter to the four corners and the Elephants dither
   over which to chase. That diagnosis took seconds in the UI. The equivalent finding in
   Python took a day of instrumentation.
3. **Three engines is the root problem.** `simulation.py`, `simulation_real.py` and
   `simulate.js` all implement the same physics and drift apart. Collapsing the batch onto
   the UI engine removes the drift permanently.
4. **The Python is fitted; the JS is not.** `KITE_STOP_TIME`, `CHURN_MAX`, `can_out_kite`
   and a doubled map were all tuned against 38 adversarially-selected corpus rows. The JS
   carries none of that.
5. **Performance is not the blocker it appears to be** (§8).

---

## 2. State of the Python engine as of this branch point

| | |
|---|---|
| HEAD | `362c5a9` |
| `sim_version` | `7c4e06c0d45519c0` |
| Tape agreement (recorded counts) | **36/38** |
| Equal-count agreement | **34/38** |
| Tests | **350 passed, 13 skipped** |
| Rig cost | 380 fights / 79.5 s / 209 ms per fight (PyPy) |
| Baseline DB at this `sim_version` | **none** — both on-disk baselines are stale |
| What the site serves | unchanged, pre-fidelity data |

A rig run at the current engine is recorded in `data/validation/tape_runs.db` as
`review-current-7c4e06c0-20260729T002708Z-sv7c4e06c0`. Before that run the DB had no
measurement of the shipped engine at all — the four session-2 kiting runs were never
committed.

**Nothing in the engine was changed on 2026-07-28.** Every experiment below was
monkeypatched from a scratchpad; `simulation_real.py` is byte-identical to `362c5a9`.

---

## 3. The measuring instruments

### 3.1 The tape corpus (existing)

`aoe2x/validation/tape_corpus.json` — 38 in-game recorded fights across 5 subjects,
extracted from `origin/aoe2_ai_for_simulation:apps/video/sim_v2/`. `tape_outcome` is
ground truth. Driven by `aoe2x/validation/tape_rig.py`, results in
`data/validation/tape_runs.db`.

**It scores one bit per row: did the right side win.** Two caveats that matter more than
they look:

- **It is adversarially selected** — rows were filmed *because* an engine looked wrong on
  them. 36/38 is a regression gate, not an accuracy estimate.
- **It has been overfitted.** All three of the Python engine's invented constants were
  selected on this exact metric. A configuration scoring well on it is partly scoring its
  own training set.

For reference on the same 38 rows, the **V2 JS engine** (`sim_v2_model.js`, with its
transform stack) scores **11/38**. That is *not* production `simulate.js` — see §7.

### 3.2 The margin metric (new, 2026-07-28)

The corpus discards the in-game **survivor and HP counts**, which exist in prose inside
`apps/video/sim_v2/overrides/imp_slinger.json` → `_ingame_note` on the recording branch.
Eleven Slinger rows have real numbers. Extracted and scored as mean absolute error:

| row | tape truth |
|---|---|
| vs 4 War Elephant (Persians) | 0 Slingers; 4 alive @ 1844 hp = 74.4% |
| vs 6 Battle Elephant (Bengalis) | 0 Slingers; 6 alive @ 1354 hp = 70.5% |
| vs 7 Paladin (Huns) | 0 Slingers; 7 alive @ 798 hp = 63.3% |
| vs 15 Hussar (Bulgarians) | 0 Slingers; 13 alive @ 833 hp = 58.5% |
| vs 9 Temple Guard | 18 Slingers left |
| vs 9 Teutonic Knight | 18 left |
| vs 15 Champion | 18 left |
| vs 6 Elite Cataphract | 16 left |
| vs 5 Elite Hussite Wagon | 9 left |
| vs 13 Elite Chu Ko Nu | 9 left, all CKN dead |
| vs 21 Elite Skirmisher | 0 Slingers; 17 Skirms alive |

**This metric was never used for fitting, so it is a genuine holdout.** The shipped Python
engine scores **2.62 units / 8.51 HP points** on it. Every subject-survivor error is
**positive** — the engine never kills too many of the winning ranged side, only too few.
A one-sided bias of that kind is a systematic defect, not noise.

**Recommendation for the migration: score on margins, not on the corpus bit.** The bit
metric can no longer distinguish a good engine from a well-tuned one — two configurations
that behave completely differently scored 70 and 65 on it while ranking the other way
round on margins.

### 3.3 The cost model (verified this session)

`tape_rig.arena_counts` reproduces **all 38 recorded counts exactly**:

```
weighted cost = food·1.0 + wood·1.0 + gold·1.5, divided by TRAIN_BATCH
TRAIN_BATCH   = {blackwood_archer_tupi: 2, elite_blackwood_archer_tupi: 2}
budget 3000, cap 21
cheaper side gets min(21, 3000 // cost); pricier side scaled to equal spend
```

The `TRAIN_BATCH` divisor is essential — without it three Blackwood Archer rows mismatch
(35/38). `apps/video/MATCHUP_SCENARIO_SYSTEM.md` documents a *different* model (wood 0.7,
cap 25) belonging to `build_civ_copies.py`; **that one is stale for the recordings.**

**The production UI uses a third rule** (§7.1) — an unweighted sum with no cap. All three
must be kept straight; they produce very different fights.

---

## 4. What was measured on the Python engine

### 4.1 Forensics: Slinger 21 v Bengalis Elite Battle Elephant 6

Tape: 0 Slingers, 6 elephants @ 70.5%. Engine: 0 Slingers, ~3 elephants @ 16.6%. The
largest margin error in the corpus, and it fails in the *opposite* direction to every
other row (the sim over-kills the elephants).

```
slinger  -> elephant :  2 damage/hit   (9 pierce attack - 7 pierce armour: minimum damage)
elephant -> slinger  : 16 damage/hit
  21 slingers  = 21.0 dps -> 91 s to clear 1920 elephant hp
   6 elephants = 57.6 dps -> 13 s to clear 735 slinger hp
```

A stand-up fight ends in 13 s with the elephants at ~86%. The tape's 70.5% implies roughly
27 s of Slinger fire. **The sim gives them 120 s.**

Attack ledger, seed 0:

| | landed | nominal | throughput |
|---|---|---|---|
| slingers | 777 hits | 1264 | 61% |
| elephants | ~39 real swings (67 damage events incl. trample) | 433 | **9%** |

The elephants are in state `moving` for the **first 57 seconds** and land their first blow
at t≈57. The Slingers open fire at t≈12. **45 seconds of unopposed shooting.**

`elHP` turned out to be almost a pure function of fight duration — Slinger DPS is roughly
constant while they live:

| t_end | 37.6 | 70.8 | 88.6 | 98.0 | 103.6 | 115.3 | 126.9 |
|---|---|---|---|---|---|---|---|
| elephant HP% | 73.2 | 59.8 | 49.0 | 35.2 | 34.7 | 30.3 | 21.9 |

### 4.2 The kite model is wrong about its own engine

`effective_kite_speed()` claims `move_speed × (1 − attack_delay / reload)`. Verified by
tick-level trace of one Slinger:

- **The windup freeze is real and exact** — 0.233 s = `attack_delay`, zero displacement,
  then `attack_cooldown = reload − delay`. That part of the model is sound.
- **But the unit never moves at 0.848.** It moves at **0.960 or 0.000**, nothing between.
- **There is a third phase the formula has no term for.** `move_away_from_target` has no
  stop condition: it retreats for the whole 1.767 s cooldown, ends up ~1 tile *outside* its
  own range, then walks back in. Measured shot-to-shot cycle **2.633 s against a nominal
  2.000 s — +32%.**

Over the unit's whole life: `kiting` 29.8%, `attacking` (standing) 25.0%, `moving`
**toward** the enemy 19.9%, `windup` 8.5%, dead 16.8%.

```
predicted effective kite speed   0.8482 t/s
realized mean speed (alive)      0.573  t/s
net RETREAT component            ~0.11  t/s     (40% of its motion is forwards)
```

**Off by roughly 8× on the quantity it claims to model.** `can_out_kite()` — the gate that
won three tape rows in `1af83e2` — compares two of these numbers. It ranked units correctly
by luck; the magnitudes are fiction. Anything reasoning quantitatively from that formula is
reasoning from a number the engine does not produce.

### 4.3 `KITE_STOP_TIME` sweep (never previously run)

The rig DB had runs at cutoff 60 and cutoff-removed, nothing between.

| cutoff | tape | equal | sum | mean fight |
|---|---|---|---|---|
| 0 / 5 / 10 | 32/38 | 29/38 | 61 | ~36 s |
| 15 | 36/38 | 30/38 | 66 | 42.9 s |
| 20 | 36/38 | 29/38 | 65 | 48.5 s |
| **30** | **37/38** | **34/38** | **71** | 51.4 s |
| 45 | 36/38 | 34/38 | 70 | 57.6 s |
| **60 (shipped)** | 36/38 | 34/38 | 70 | 61.3 s |
| 90 | 36/38 | 34/38 | 70 | 68.1 s |

- 45/60/90 give **identical verdicts** — the shipped 60 sits in a dead zone, costing
  simulated time for nothing.
- Cutoff 30 buys exactly **one row** over the flat plateau at 5 seeds — noise-level, and
  it is a plateau *edge*, which the `CHURN` re-fit methodology explicitly refuses.
- **The margin error falls monotonically as the window shrinks**: 8.51 → 7.81 → 5.70 →
  5.72 → 3.47. Independent confirmation that the ranged side gets far too much free fire.
- Deleting the cutoff is catastrophic (breaks 11 rows) — consistent with the existing doc.

### 4.4 Physics experiments — five mechanisms, four failed

| experiment | result |
|---|---|
| **Mass-weighted separation** (heavier body shoves lighter) | Rejected before running — the user corrected it on game grounds: in AoE2 a villager body-blocks an elephant; there is no shoving. |
| **E1 — contact clipping, avoidance halo kept** | **Byte-identical to baseline.** Jam fraction 0.0% at every sample. The avoidance force field (activating at 1.5× contact distance, magnitudes `3 + overlap×5`) repels units *before* they can touch, so hard contact is geometrically unreachable. |
| **E1b — contact clipping + avoidance force deleted** | **38/38 tape**, 34/38 equal, margin 7.49, and ~12% *faster* (74 s vs 84 s). First perfect tape score ever recorded. Both Guecha rows flip correct. |
| **E4 — E1b + `CHURN=0`** | 36/38. Breaks exactly the two ETG rows CHURN was fitted for. Also: **all five seeds became bit-identical** — CHURN's random draw is the only variance source in a 100%-accuracy melee fight. |
| **E5 — E1b + `KITE_STOP=600`** | 32/38. Elephant row becomes a 5-minute coin flip. The clip makes wall-sliding free, so a pinned kiter skates the boundary and wheels corners forever. |
| **Blob spawn** (3×7, depth 2.0 t) | **Worse** than the line (21.9% vs 35.2%). |
| **Square blob** (5×5, depth 4.0 t) | **Worse still** (15.9%). Fights *longer*, `inReach` *down*, and jam *fell* despite doubling depth — because every unit in a blob is inside range 8, so they all kite in the same phase and there is no counter-flow to jam against. |
| **Melee-kite gate** (don't kite what you can't outrun) | Elephant row 74.1%, margin **2.25 pts** — but 35/38 tape, 29/38 equal. Right outcome via wrong behaviour: the tape's Slingers do keep moving. |

**Only one of five proposed mechanisms beat doing nothing.** The instrumentation earned
its keep; reasoning about physics repeatedly did not.

---

## 5. The recording arena — ground truth

Extracted from `origin/aoe2_ai_for_simulation:apps/video/templates/golden_*.aoe2scenario`
with `AoE2ScenarioParser` 0.8.2. **This is a fixture to reproduce, not a parameter to fit.**

### 5.1 Geometry

**16×16 tiles, flat (elevation 0), 101 gaia objects** — Italian Pine ×32, Monkey Puzzle
×19, Acacia ×14, Green Oak ×12, Olive ×8, Forest Oak ×7, Bush B ×7, Panda Rock ×1 (at
9.0, 7.0), Rainforest ×1. They occupy **101 of 256 tiles — 39% of the map is solid.**

```
golden_cavvsranged      X = tree/rock   A = Knights x29   B = Camel Archers x28   + = patrol corner
       0123456789012345
     0 XXXXXXXXXXXXXXXX
     1 XXXXXX........XX
     2 XXXXX..........X
     3 XXXX........AAAX
     4 XXX........AAAAX
     5 XX...+..XX.AAAAX     <- central cluster
     6 X......X..XAAAAX
     7 X......X.XXAAAAX     <- Panda Rock (9,7)
     8 X.......XX.AAAAX
     9 X...B.......AAAX
    10 X..B.BBBB...AAXX
    11 X.BBBBBB...+AXXX
    12 X.BBBBBB....XXXX
    13 X.BBBBBB...XXXXX
    14 XX.BBBB...XXXXXX
    15 XXXXXXXXXXXXXXXX
```

A perimeter forest ring, a central cluster around (7–10, 5–8), and a navigable annulus
between them — a **donut**. The blocked set is irregular (thicker at the NW and SE corners);
use the actual per-tile set, not an idealised inset.

### 5.2 The patrol AI

`ddkMatchupAI` = `ddkSquareV25`, a **clockwise square patrol**:

```
A(5,5) -> B(11,5) -> D(11,11) -> C(5,11) -> A ...
LEG = 6 tiles, STEP = 1.5 tiles, arrival gate D < 3.5 tiles, corner index advances only (mod 4)
```

**Edge A→B runs along y=5 from x=5 to x=11 — and tiles (8,5) and (9,5) are solid trees.**
The clockwise leg drives the kiting ball into the central cluster by construction.

State machine: `gState` 18 = KITE/move, 22 = VOLLEY/hold; 22→18 requires `gKiteOK` (our
range out-ranges the enemy median). Full history in
`apps/video/ai_experiments/SQUARE_PATROL_EXPERIMENTS.md`.

### 5.3 Spawns — armies start almost on top of each other

| template | army A | army B | centroid gap | **nearest pair** |
|---|---|---|---|---|
| cavvsranged | Knight ×29, centroid (13.1, 7.0) EAST | Camel Archer ×28, centroid (5.2, 12.3) SW | 9.53 t | **3.61 t** |
| infvsinf | Elite Jaguar ×36, (6.8, 3.9) N | Militia ×40, (5.6, 12.4) S | 8.56 t | **3.00 t** |
| rangedvsinf | Elite Arambai ×30, (6.8, 4.0) N | Militia ×34, (5.9, 11.9) S | 7.96 t | **3.00 t** |

Armies spawn **as blobs** (~10×6 tiles, 4–6 ranks deep), **close together on one side**.

Trim rule for smaller armies (user-specified): **keep the units closest to the enemy**,
working inward. Reconstructed 21 Slinger v 6 Battle Elephant:

```
slingers  centroid (5.88, 12.02)   bbox x[3.5..8.5] y[9.5..14.5]
elephants centroid (12.17, 9.33)   positions (11.5,8.5) (11.5,7.5) (12.5,8.5)
                                             (12.5,9.5) (12.5,10.5) (12.5,11.5)
centroid gap 6.84 t      nearest pair 3.61 t
```

*Unverified:* no generated matchup scenario is committed (they are written straight to the
AoE2 save folder), so the trim rule could not be checked against a real output.

**The diamond does not matter.** AoE2's tile grid is square; the diamond is a display
rotation (`sx=(x+y)k, sy=(y-x)k`). Distances are Euclidean in tile space — confirmed by the
`engine_viewer` work on `game_simulation`, which reproduced real gRPC game state working
purely in tile coordinates.

### 5.4 Fixture ladder (Python, each stage adds one element)

| stage | subj MAE | HP MAE | elephant row | fight |
|---|---|---|---|---|
| S0 — 60×20, line spawn | 2.84 u | 7.49 | 5u @ 37.9% | 90–98 s |
| **S1 — 16×16 + real spawns** | **1.24 u** | **2.80** | 4–6u @ 57.1% | 76–82 s |
| S2 — + obstructions | ~8 u | ~44 | **slingers win** | 115 s |
| S3 — + clockwise patrol | 2.05 u | 6.68 | 6u @ 80.1% | **29–35 s** |

- **S1 is the largest accuracy gain of the session, with no physics change at all.** It
  fixed the Chu Ko Nu row (**+12.0 → +0.2**) that had survived every physics experiment,
  and landed War Elephant at −0.2.
- **S2 breaks badly.** Obstructions without pathfinding give the kiter cover the chaser
  cannot route around. Earlier claims that "there is nothing to path around" were true of
  the invented open box and false of the real arena.
- **S3 gets the clock right** (29–35 s vs tape ~30 s) but overshoots cavalry HP by +7…+10
  and destroys the Cataphract row. S1 and S3 **bracket** the truth — the real AI spends more
  time stopped and volleying than the crude patrol model does.

S1 was never scored on the full corpus. **That run is still outstanding** and is the main
unfinished measurement on the Python side.

---

## 6. THE KEY FINDING — six divergences from the JS

`simulation_real.py` docstring: *"Python port of the JS canvas sim in
static/js/simulate.js."* It is not.

| # | mechanic | production `simulate.js` | `simulation_real.py` |
|---|---|---|---|
| 1 | **map** | 900×600 px ÷ TILE_SIZE 30 = **30 × 20 tiles** | **60 × 20** |
| 2 | **spawn X** | `30 + radius` px / `W − 30 − radius` px → **~1 tile from each map edge** | centre ± 15 → **15 tiles of open runway behind each army** |
| 3 | **spawn jitter** | `startX + (rand−0.5)·10` px = ±0.167 t | **none** |
| 4 | **collision radius** | `10 + outline·20` px → infantry **0.467 t** | `outline_size` → **0.200 t** |
| 5 | **kite gate** | `shouldKite = !target.isRanged()` — the entire rule | `+ KITE_STOP_TIME 60` **and** `can_out_kite()` |
| 6 | **crowd churn** | **does not exist** | `CHURN_MAX 1.25`, neighbour-scaled |

**#1 and #2 together are the origin of most of the trouble.** In the JS, armies spawn one
tile from opposite walls: a kiting Slinger has essentially *no* runway, backs into the wall
within a second, and stands there while the chaser closes 28 tiles. The Python doubled the
map and moved the armies to the middle, inventing **15 tiles of free retreat**. The
docstring admits the intent: *"Width widened to 60 so ranged units have room to kite."*

That invented runway *is* the free-fire window measured from every other angle — the 41 s
to first elephant swing, the 9% chaser throughput, the one-sided margin bias.

**And #5 and #6 exist to paper over #2.** Once kiters have 15 tiles of runway, kiting never
resolves, so a 60-second cutoff was invented to force an ending and a random reload delay
was invented to slow melee down. Neither could ever be deleted cleanly because both were
patching a self-inflicted wound.

### 6.1 Reverting the divergences does **not** fix the corpus

| config | tape | equal | sum | subj MAE | HP MAE |
|---|---|---|---|---|---|
| **shipped Python** | **36/38** | **34/38** | **70** | 2.62 u | 8.51 |
| JS geometry only (30×20, wall spawn, jitter) | 33/38 | 32/38 | 65 | **2.38 u** | **7.32** |
| full JS replica (+ sprite radii, no cutoff/gate, churn 0) | 32/38 | 32/38 | 64 | **2.38 u** | 13.05 |

Restoring the JS geometry **loses 3–4 tape rows** while slightly improving margins. The
explanation is §3.1: the corpus bit metric is the Python's own training set. On the
unfitted metric the unfitted geometry wins, narrowly — and that gain comes almost entirely
from one row (Bengalis elephant, −53.9 → −25.4), offset by Paladin and Hussar getting worse.

**Conclusion: neither engine is right. The Python is fitted; the JS is unfitted but has its
own gaps (§7.2).** The migration is justified by architecture and observability, not by the
JS currently scoring better.

---

## 7. The production JS engine — measured

### 7.1 Its count rule is different again

`simulate.js:3251,3294` — **unweighted** sum, no cap:

```js
unitCost = cost_wood + cost_food + cost_gold
count    = max(1, floor(totalResources / unitCost))
```

At 3000 resources: Slinger 60 → **50**; Elite Cataphract 145 → **20**; Burmese Elite
Battle Elephant 170 → **17**. These are *not* the corpus counts (21 v 6). Comparing a UI
observation to a tape row without accounting for this is an error — it was made during this
session.

### 7.2 Actual results, production `simulate.js`, unmodified

**Slinger ×50 v Elite Cataphract ×20**

```
seed 0: CATAPHRACTS  t=119.1s   slingers  0u/ 0.0%   cataphracts  2u/ 3.6%
seed 1: CATAPHRACTS  t=119.1s   slingers  0u/ 0.0%   cataphracts  2u/ 3.6%
seed 2: SLINGERS     t= 73.8s   slingers 16u/21.1%   cataphracts  0u/ 0.0%
seed 3: SLINGERS     t= 71.2s   slingers 16u/19.4%   cataphracts  0u/ 0.0%
seed 4: SLINGERS     t= 66.5s   slingers 18u/26.3%   cataphracts  0u/ 0.0%
  -> Slingers win 3/5 (bimodal)
```

**Slinger ×50 v Burmese Elite Battle Elephant ×17**

```
seed 0: ELEPHANTS  t=600.0s   slingers 2u/ 4.0%   elephants 17u/69.1%
seed 1: ELEPHANTS  t=600.0s   slingers 2u/ 4.0%   elephants 17u/69.1%
seed 2: ELEPHANTS  t=368.5s   slingers 0u/ 0.0%   elephants 17u/63.3%
seed 3: ELEPHANTS  t=600.0s   slingers 2u/ 3.0%   elephants 17u/61.9%
seed 4: ELEPHANTS  t=269.9s   slingers 0u/ 0.0%   elephants 17u/67.0%
  -> Elephants win 5/5, all alive, 61.9-69.1% HP
```

The elephant result matches in-game expectations closely (~70% HP). **But 3 of 5 seeds hit
the 600 s cap with 2 Slingers still alive** — the JS has no kite-stop, so a residue of
kiters is never caught. Diagnosed visually in the UI: the Slingers scatter to the four
corners and the Elephants dither over which to chase. **Likely fix: keep chasers committed
to one target rather than re-picking.** This is the JS's own fidelity gap and must be
solved regardless of language.

### 7.3 Other JS facts worth knowing

- **Collision is index-ordered** (`for i / for j=i+1` over an array), so it never had the
  `id()`-memory-address nondeterminism that Python needed `362c5a9` to fix.
- **Only 4 `Math.random()` call sites** in the whole file — seeding is trivial.
- **Collision is O(N²) with 3 passes**, and `calculateAvoidance(allUnits)` is O(N²) again.
  There is **no spatial grid**. This is the main performance gap (§8), and it is fixable.
- The armour damage-class fix is present in the matchup panel (`baseClass`, line 2869);
  whether the *simulation* path carries it needs checking on this branch.

---

## 8. Performance

Same 5 matchups × 5 seeds, identical counts, both JITs warmed.

| | Node (production `simulate.js`) | PyPy (`simulation_real.py`) | ratio |
|---|---|---|---|
| ms/fight | 788.3 | 159.3 | **4.9× slower** |
| ms CPU per simulated second | 11.12 | 3.08 | **3.6× slower** |
| µs per tick | 185.3 | 102.6 | **1.8× slower** |
| tick rate | 60 Hz | 30 Hz | — |

**Two of the three factors are not the language:**

1. The 2× is a **design choice** (1/60 vs 1/30).
2. Most of the remaining 1.8×/tick is **algorithmic** — the JS has no spatial grid and runs
   two O(N²) loops per tick. At 67 units that is ~2,200 pairs × 3 passes versus a few
   hundred grid lookups.

**Expect near parity after porting the spatial grid.** Measure it before committing.
Batch estimate: ~8–14 h rather than the ~28 h the raw ratio implies, before
`worker_threads` (24 cores available; the Python batch already saturates 23).

### 8.1 GPU — not worth it

Tooling is real (WebGPU reached candidate recommendation March 2026; Node bindings exist
via the `webgpu` npm package). The workload is wrong:

- **Nothing to parallelise inside a fight** — 30–60 units is nothing for a GPU. The only
  axis is *across* fights.
- **Catastrophic branch divergence** — ~50 branchy abilities, mixed unit types per lane,
  fight lengths from 67 s to 600 s. A warp runs at its worst lane.
- **WGSL has no objects, dictionaries or dynamic allocation.** The combat dict, ability
  registry and projectile list would all need flattening. That is a reimplementation.
- **It would be a fourth implementation of the same physics** — the exact drift problem
  this migration exists to end.

`worker_threads` is the right lever.

---

## 9. How to drive the production JS headlessly

The harness on the recording branch loads the **real** `simulate.js` (plus siblings, in
browser load order) in a `vm` sandbox with DOM stubs and a seeded RNG:

```
origin/aoe2_ai_for_simulation:apps/video/sim_v2/headless_sim.js
  exports runFight(cd1, slug1, civ1, n1, cd2, slug2, civ2, n2, seed)
  env: JSDIR (engine dir), MAXS, SEEDS, RAMP
  with NO env transforms set, this is production behaviour
```

Combat dicts are exactly what `/api/ref/combat-unit/<civ>/<slug>?age=Imperial` returns,
i.e. `aoe2x/sim/combat_unit_loader.build_combat_dict_from_ref(row)`. Dump them from Python:

```python
import sqlite3, json, sys
sys.path.insert(0, "D:/AI/aoe2_matchup")
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
c = sqlite3.connect("data/golden/aoe2_reference.db"); c.row_factory = sqlite3.Row
row = c.execute("select * from ref_units where civ_name=? and unit_slug=? and age='Imperial'",
                (civ, slug)).fetchone()
json.dump(build_combat_dict_from_ref(row), open("cd.json", "w"))
```

Driver:

```js
process.env.JSDIR = "D:/AI/aoe2_matchup/apps/website/static/js";
process.env.MAXS  = "600";
const H = require("./headless_sim.js");
const CD = JSON.parse(require("fs").readFileSync("cds.json", "utf8"));
const cost = s => (s.cost_food||0) + (s.cost_wood||0) + (s.cost_gold||0);   // UI rule
const n1 = Math.max(1, Math.floor(3000 / cost(A)));
const r = await H.runFight(A, slugA, civA, n1, B, slugB, civB, n2, seed);
// r = { winner, alive1, alive2, h1, h2, margin, time }
```

**Caveat:** this harness is a *validation* tool — `vm` sandbox plus Proxy-based DOM stubs.
Fine for hundreds of fights, wrong for 500k. The migration needs a clean headless build
that imports the sim classes without the DOM layer.

---

## 10. What the migration has to replace

| piece | today | note |
|---|---|---|
| batch runner | `aoe2x/batch/rebuild_matchup_baseline.py`, `run_matchup_battles.py`, `patch_resim.py` | Node + `better-sqlite3` + `worker_threads` |
| validation rig | `aoe2x/validation/tape_rig.py`, `report.py`, `tape_runs.db` | keep the schema; re-point at Node |
| derive layer | `derive_unit_rankings.py`, `derive_pool_scores.py`, `best_units.py` | **can stay Python** — reads SQLite. This is the natural seam. |
| tests | 350 pytest | JS equivalents, or shell out to Node |
| `sim_version` | byte-hash of `simulation_real.py` + `config_combat.py` | trivial to re-point at the JS files |
| determinism | seeded `random` | only 4 `Math.random()` sites; collision already index-ordered |

Suggested order (not yet a plan — to be brainstormed):

1. Clean headless Node runner + seeded RNG; reproduce UI results exactly.
2. Port the spatial grid into the JS; re-benchmark.
3. Score the 38-row corpus **and the margin metric** through it.
4. Only then touch the batch pipeline.

Steps 1–3 are useful even if the migration stalls.

---

## 11. Lessons

- **A "port" nobody diffed is not a port.** Six divergences accumulated in
  `simulation_real.py` and none were caught, because no test ever compared the two engines
  on the same matchup. Whatever replaces it needs a standing cross-engine equivalence check.
- **Fitted constants hide the bug they were fitted to.** `KITE_STOP_TIME` and `CHURN_MAX`
  both exist to compensate for a doubled map. Each looked like a modelling decision and
  each was measured, swept and defended — while the actual defect sat in a constant nobody
  questioned.
- **Score on a holdout.** The corpus bit metric was the Python's training set and can no
  longer rank engines. The margin metric — which existed in prose in the repo the whole time
  — separated configurations the bit metric called equal.
- **Observability beats instrumentation.** A day of tick-level tracing produced less
  actionable insight than looking at the UI for thirty seconds. That is the migration's
  strongest justification.
- **Five physics mechanisms were proposed; four measured worse than doing nothing.**
  Mass shoving, blob depth, obstructions and the JS revert all looked compelling. Only
  contact clipping survived. Measure before believing.
