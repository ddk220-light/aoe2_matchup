# Updated simulation results — 2026-07-28

Fidelity work on **`aoe2x/sim/simulation_real.py`**, the position-based engine
that produces every matchup number the site serves. Written as a resume point:
everything needed to pick this up cold is here.

- **Branch:** `updated-simulation-results-2026-07-28`
- **Engine state:** `sim_version dd3d17dfc94147c2`
- **Agreement with in-game recordings: 36/38 (95%)** at recorded counts,
  34/38 (89%) at equal counts — up from a **31/38 (82%)** baseline
- **Tests:** 350 passed, 13 skipped
- **Nothing the site serves has moved.** All committed DBs still hold
  pre-change data.

> **PAUSED — do not run any simulation.** Standing instruction (2026-07-28):
> no re-sim until the outstanding engine issues are closed. The blocking one is
> §6.1: `KITE_STOP_TIME` is back in the engine as a crude stand-in for a real
> constraint, and it has to be replaced by physics that lets an elephant
> legitimately run a skirmisher down. See §6.1 for the candidate mechanisms.

**Two baselines exist on disk. Neither is current.**

| file | rows | `sim_version` | status |
|---|---|---|---|
| `D:/AI/matchup_baseline_180059.db` | 540,920 | `b9be1ba0` | built 2026-07-28, now stale |
| `D:/AI/archive/matchup_baseline_177723.db` | 521,658 | `e221c8a3` | the previous baseline, also in both Railway buckets |

The `180059` in that filename is **not a game build** — `patches.db` says 177723
is current and there is no 180059. It was an invented label; rename on the next
rebuild.

---

## 1. Resume in one minute

```bash
git checkout updated-simulation-results-2026-07-28

# Where does the engine currently stand? (~75s)
pypy3 -m aoe2x.validation.tape_rig --label resume-check --seeds 5 --scales tape,equal_count

# What has been measured before, and what did each change do?
python -m aoe2x.validation.report --list
python -m aoe2x.validation.report --diff <before_tag> <after_tag>
```

The rig is the whole point: **never change this engine without a before/after
number.** `--diff` names the matchups whose verdict flipped, so a change that
repairs three rows while breaking two cannot be mistaken for progress. That has
already happened twice in this work.

---

## 2. The measuring instrument (build it before trusting anything)

`aoe2x/validation/` — added first, deliberately, before any engine edit.

| File | Role |
|---|---|
| `extract_tapes.py` | Pulls the in-game recordings off `origin/aoe2_ai_for_simulation` into a committed fixture. Re-run only if the recordings change. |
| `tape_corpus.json` | 38 tape-verified matchups across 5 subjects. **Ground truth.** |
| `tape_rig.py` | Runs the engine over the corpus, records every fight in full. |
| `report.py` | `--list`, `--run`, `--diff`. |

**Field semantics in the source recordings** (verified, not assumed): `outcome`
is tape truth; `wr` / `*_hp` are the *JS* engine's answer; `n_subject` /
`n_opp` are the exact counts each fight was recorded at. The Steppe Lancer row
proves it — `wr: 1` (JS says Slinger wins) with `outcome: "loss"`.

Every fight is stored at full granularity in `data/validation/tape_runs.db`
using the `matchup_battles` column set, plus the tape verdict, signed score and
wall-clock, tagged with a unique `run_tag` and full provenance (commit, branch,
dirty flag, interpreter, `sim_version`).

**The corpus is adversarially selected.** Rows were filmed *because* the JS
engine looked wrong on them. It is an excellent regression gate and a bad
estimate of overall accuracy. Do not quote 87% as "the engine is 87% accurate".

Two scales are recorded. `tape` uses the counts the fight was actually filmed
at and is the one to weight. `equal_count` (N v N) is a synthetic second lens.
The ported equal-resource sizing — weighted cost with gold ×1.5 and `/batch`,
budget 3000, cap 21 — **reproduces all 38 recorded counts exactly**, which is
what confirms the cost model matches the recorder.

---

## 3. What changed, and why

### Shipped

| Commit | Change | Effect |
|---|---|---|
| `6d396d5` | Tape-validation rig | baseline **31/38** |
| `7cd9d17` | Three correctness bugs | 31/38 (corpus can't see them) |
| `39462e5` | True collision radii + frame-rate-independent stuck test | **32/38**, batch **48% faster** |
| `7d10fb2` | Crowd interference for melee | **33/38** tape |
| `a3ac8df` | Re-fit `CHURN_MAX` 2.25 → 1.25 | 33/38 + **32/38** |
| `69554fe` | Batch: failed groups no longer become silent holes | run safety |

**The three correctness bugs** (`7cd9d17`) — each a defect with a known-correct
answer, verified by running the behaviour against the stashed pre-fix engine:

- Armor was resolved by *delivery* rather than damage class. A ranged unit whose
  base attack is class 4 with no class-3 entry is resisted by **melee** armor:
  19 units (thrown-melee, mangonel line, bombards, trebuchets, warships).
  Elite Gbeto into Elite Huskarl: **5 → 13 damage**. The `ignores_*_armor`
  branch keyed off the same wrong signal, so an armor-ignoring thrown-melee
  attack silently paid full melee armor.
- Trample measured from a point, not the body hull — the attacker's own radius
  was missing from an edge-to-edge reach.
- The Temple Guard ramp was a monotonic accumulator; the game uses a decaying
  5s window. Reload after a 6s gap: **1.20 → 1.80**.

**True collision radii** (`39462e5`) — the engine was using the *sprite-drawing*
formula `(10 + outline*20)/30`, ported from the browser canvas, ~2.3× too wide
for infantry. A rendering number was driving the physics. Also made the batch
**48% faster** (2.75 → 4.1 groups/s) because fights resolve instead of grinding.

**Crowd interference** (`7d10fb2`) — see §4; this engine had none for any unit.
Applied to **both** melee attack paths. The JS engine patches only
`perform_attack`, so its crowd interference silently never applies to any unit
with `attack_delay > 0` — which is the entire cavalry roster. This port does not
inherit that.

### Session 2 (2026-07-28 afternoon)

| Commit | Change | Effect |
|---|---|---|
| `9b55513` | Batch: skip stat-identical pairs, not same-named ones | +36,116 rows |
| `51e3df8` | Carry-forward design (runbooks §2a) + §6.1 correction | docs |
| `1af83e2` | Ranged units kite ranged units they can outrun | **36/38** tape |

**The full baseline ran and was verified** — 114,236 groups → 504,804 rows in
6h13m, then a 7,216-group top-up for the same-slug fix, 540,920 rows total,
`groups_failed = 0`, 100% `eliminated`, mean fight 46.4s. It is now stale
(`sim_version` moved), but it is kept as the comparison point and as the
carry-forward source.

**What the full table revealed that the corpus could not.** §6.2 predicted this:
the armour damage-class fix touches 23 units, none of which are in the corpus.
Measured against the old baseline over 493,584 shared matchups — 3.58% of
winners flipped, mean signed-score delta **+0.00** (redistribution, not
inflation) — the movers separate cleanly by cause:

- **armour damage-class**: Chakram Thrower **+35.8**, Throwing Axeman +17.1,
  Gbeto +12.8, Mameluke +11.1 — verified to be exactly the class-4-no-class-3 set
- **true collision radii** (bodies 0.47 → 0.20 tiles, so AoE catches more):
  Ibirapema +23.9, Urumi +14.3, Grenadier +11.6
- **crowd interference**: Konnik −9.3, Kona −7.9, Temple Guard −7.6 (the unit
  the fix was built for), Iron Pagoda −7.2, Keshik −7.1

**Elephant trample was provably dead before the trample fix.** Old reach 0.97
tiles against a minimum possible separation of 1.20 — shorter than the closest
an enemy can physically stand, so a War Elephant's trample hit *nothing, ever*.
Now 1.30 vs 0.80, with ~15 neighbours geometrically reachable. Yet outcomes moved
only +1.1, and crowd interference is not the reason (elephants pay only −0.4 to
−1.1 for it, versus ~−7 for infantry, because big bodies cannot pack six
neighbours into a 2-tile radius). A mechanic going from 0 to 15 targets and
moving outcomes by one point is the first real evidence for the `TRAMPLE_K` /
`GRAZE_K` packing factors in §6.3.

**Same-name is not same-unit** (`9b55513`). The enumeration skipped every
`my_slug == opp_slug` pair, discarding 9,780 genuine cross-civ matchups to avoid
522 real mirrors. Wu Halberdier (60hp/10atk) beats Gurjaras Halberdier
(45hp/5atk) 30-to-0 with 96% health; 22.5% of cross-civ same-slug pairs are
blowouts, against 0% for true mirrors. Now keyed on the **fingerprint**, so
stat-identical pairs are still skipped — they record a *fake winner* from spawn
side (the 318 true mirrors split 238/80), not a draw.

### Deliberately not shipped

- **Block spawn + attacker capacity** — preserved on `sim/phase2cd-experiment`
  (`fd5e768`). Net regression 32 → 30. See §5.
- **16×16 arena** — measured and rejected. See §5.

---

## 4. How the wins were actually found

Both real gains came from instrumenting a specific failing fight, not from
tuning. Worth repeating as method.

**Crowd interference.** Three rows had an *outnumbered melee subject winning in
sim but losing on tape*. The obvious reading — the bigger army can't bring its
numbers to bear — was wrong twice: both sides engaged for a similar share of the
fight (53% vs 57%) and every unit landed hits, and at 17-vs-21 there are ~1.2
attackers per target against a capacity of 6, so an envelopment cap could never
bind. The asymmetry was throughput:

| | nominal reload | observed |
|---|---|---|
| Elite Temple Guard (ramp 0.2, floor 1.0) | 2.00s | **2.43 s/hit** |
| Warrior Priest (no ramp) | 2.00s | **4.28 s/hit** |

The ETG's ramp was paying off in full, because in an uninterrupted melee it
always holds enough hits inside the 5s window. The recordings say the opposite —
in-game ETG throughput matches a *flat* 2.0s reload, because the ramp never gets
to build while it is being shoved and losing targets. Adding crowd interference
flipped both rows to the correct winner with tape-like margins (Priest keeps
6/21 against the tape's 9/21).

**Re-fitting `CHURN_MAX`.** 2.25 was inherited from the JS engine's geometry.
Swept against the corpus before committing 8 hours to it:

| `CHURN_MAX` | tape | equal_count | combined |
|---|---|---|---|
| 0.00 (off) | 32/38 | 32/38 | 64 |
| 1.00 | 33/38 | 32/38 | 65 |
| **1.25** ← chosen | **33/38** | **32/38** | **65** |
| 1.50 | 33/38 | 32/38 | 65 |
| 2.25 *(inherited)* | 33/38 | 31/38 | 64 |
| 4.00 | 32/38 | 30/38 | 62 |

Tape agreement peaks broadly; equal-count agreement falls **monotonically** as
churn rises. Joint optimum is the 1.0–1.5 plateau, midpoint taken. **This value
is a property of the arena, not the units — re-fit it if the geometry changes.**

---

## 5. Decisions taken on evidence (do not silently revisit)

**Arena stays 60×20, offset 15.** The recording rig uses 16×16, and it was
tested: fidelity gets *worse*, 33/38 → 31/38 tape and 32/38 → 28/38 equal-count.
Copying the map dimension without the rig's patrol dynamics does not reproduce
its conditions. It also costs the ranged roster heavily, because map width *is*
kiting room (the map was widened to 60 for exactly that reason):

| range | unit | S @60×20 | S @16×16 | swing |
|---|---|---|---|---|
| 7 | Hand Cannoneer | +84.9 | −13.3 | **−98.2** |
| 7 | Elite Mangudai | +38.3 | −49.6 | −87.9 |
| 8 | Slinger | +100.0 | +41.1 | −58.9 |
| 12 | Elite Longbowman | −27.2 | −64.6 | −37.4 |

The swing tracks *dependence on kiting room*, not range — which is why range-7
units suffered more than range-12 ones.

**Block spawn + attacker capacity are not merged.** Block spawn is not
worthless: it **fixed all three ranged-vs-ranged failures**, which nothing else
has touched, because in a full-height line only the near end of an army is ever
in range while a blob concentrates fire. But it broke five melee rows — massed
ranged can all fire from inside a blob (AoE2 has no line-of-sight blocking)
while melee only engages at the perimeter. Attacker capacity, meant to fix
exactly that, is **inert**: instrumented at **0 saturations in 23,278 checks**,
ring occupancy averaging 0.37 against a capacity of 6, because true radii shrink
the contact ring to 0.7 tiles. Those two changes work against each other.

**Two engines, not one.** Benchmarked: Node runs the JS engine at ~3.5× PyPy at
60 Hz, ~1.5× at matched 30 Hz. Collapsing to a single engine was rejected —
tick rate currently *is* physics, so the two rates give different fight
outcomes.

**No GPU port.** The batch hard-requires PyPy, and PyPy cannot load CuPy, Numba
or `torch.cuda` (verified). A port means abandoning PyPy's JIT and rewriting the
engine as masked array code parallel *across* fights — 30–60 units cannot fill
21k CUDA cores — plus reimplementing ~50 branchy abilities, plus full
re-validation. It would also be a *third* implementation of the same physics,
which is the drift problem this work exists to fix. CPU is already saturated at
**99.9%**, and SMT is worth only ~1.7% (12 workers 4.07 grp/s vs 23 workers
4.14).

---

## 6. Open work, in priority order

### 6.1 Kiting model — the last real cluster

Five rows still disagree: three ranged-vs-ranged (Chu Ko Nu ×2, Hussite Wagon)
and two Guecha (vs Ratha-melee, vs Heavy Camel). The Guecha rows are
ranged-subject fights where crowd interference slows the melee chaser but not
the kiter.

**Correction (2026-07-28): an earlier draft of this section claimed the kite gate
keys off damage-per-hit. That is the JS engine. This engine has no damage gate**
— the finding was carried over without re-reading the Python source. The whole
gate is two lines in `unit_step`:

```python
should_kite = not self.target.is_ranged()
can_kite    = sim.battle_time < KITE_STOP_TIME
```

**The effective-speed model is already implemented here, as physics rather than
formula.** When `attack_delay > 0` the unit sets `committed_attack`, enters
`windup`, and the next tick returns *before any movement* — it is genuinely
frozen while winding up. So

```
effective retreat speed = movement_speed × (1 − attack_delay / reload_time)
```

emerges from the simulation instead of being computed. Measured on the current
roster: Janissary (delay 0.00) never freezes and kites at its full 0.96; Heavy
Cav Archer (0.58 / 2.00) is frozen 29% of its cycle and kites like a 1.09 unit
despite 1.54 paper speed; Arbalester (0.33 / 2.00) kites at 0.80.

### Item 2 is DONE (`1af83e2`) — item 1 is the open blocker

**Shipped: a ranged unit now kites another ranged unit it can genuinely outrun.**

```python
effective_kite_speed = movement_speed * (1 - attack_delay / reload_time)
kite a ranged target iff  effective_speed > theirs  AND  attack_range > theirs
```

Derived from `attack_speed`, not `self.reload_time` — the latter is rewritten in
place by `attack_speed_ramp` and would make eligibility flicker mid-fight.

| | before | after |
|---|---|---|
| tape | 33/38 | **36/38 (95%)** — FIXED 3, BROKE 0 |
| equal_count | 32/38 | **34/38 (89%)** — FIXED 2, BROKE 0 |

All three fixed rows are the long-standing ranged-vs-ranged cluster: Slinger vs
Hussite Wagon, Slinger vs Chu Ko Nu, Blackwood Archer vs Chu Ko Nu.

**Not shipped: removing `KITE_STOP_TIME`. It was tried and it measured worse.**
Deleting the cutoff took tape agreement to **31/38**, breaking four elephant
rows, and cost 45% more simulated time. With no time limit a Slinger out-kites a
War Elephant *forever*, because the elephant closes at only `0.88 − 0.85 = 0.03`
tiles/s of effective speed. The recordings say the elephant wins.

The lesson is worth keeping: the cutoff is a **bad model of a real constraint**,
not a fiction. Perfect kiting does not happen in game — formations bunch,
terrain clips, micro fails, maps have edges. Deleting it replaced a bad model
with *no* model, which is worse. So it stays, under protest, until something
physical replaces it.

### 6.1a The open blocker — make an elephant able to catch a skirmisher

**Standing instruction (2026-07-28): no re-sim until this is closed.** A 60s
wall-clock switch is not acceptable as the permanent answer; the engine has to
produce the catch on its own.

Why it currently cannot: a chaser runs in a straight line, while a kiter is only
penalised for the windup it spends standing still. That is the *only* cost
kiting pays today. Candidate mechanisms, most promising first:

1. **Turn rate.** A kiter reverses direction twice per attack cycle — turn away,
   run, turn back, fire. A chaser never turns. AoE2 units have a real rotation
   speed and it is *not* currently modelled: `ref_units` has no turn column, but
   `aoe2x/extract/extract_effects.py:40` maps effect 6 to `rotation_speed`, so
   the dat carries it and we simply do not extract it. This is the one candidate
   that is both physical and asymmetric in exactly the right direction.
2. **Retreat crowding.** A mass of units backing away collides with itself; the
   back rank blocks the front. Only the leading edge retreats at full speed.
   Analogous to the `CHURN` interference already applied to melee swings, and
   the geometry to do it already exists.
3. **Map edge.** Kiting room is a real limit and 60×20 may simply be too wide.
   Note the 16×16 experiment was already measured and **rejected** (§5) — do not
   simply re-run it; the finding was that copying the recording rig's dimension
   without its patrol dynamics makes fidelity worse.

Sequence: extract turn rate → model turn cost → re-measure on the corpus →
only then try removing `KITE_STOP_TIME` again and confirm the four elephant rows
hold. The rig makes this cheap: ~90 seconds per attempt.

### 6.1b The decided-fight exit is inert, and that is recorded on purpose

`_decide_kited_fight` exists and never fires. Sampled 70 fights: only 5 reached
the 120s decision point, and the kiting side had lost a **median 87%** of its
army by then. No threshold up to 70% fires even once.

The reason is structural and worth not rediscovering: **a kite that works ends
by elimination long before 120s; only a failing kite is still running at 120s.**
The test is simultaneously too late to catch a successful kite and unnecessary
for one.

Extrapolating the final HP instead of simulating it was also tried, because the
tail of a decided fight is expensive. Best model found (`M6`) was
`winner_hp − 0.5 × loss_rate × min(time_to_loser_zero, 120)` with the loser set
to 0 — **3.03 mean absolute error**, beating naive truncation's 5.13, and
unbiased. It was still rejected: only 12% of fights run past 120s, so cutting
all of them saves **9%** of simulated seconds, and the error lands on slow
grinding matchups that sit near the `BAND = 10` tossup boundary. Eighteen
minutes is not worth blurring those rows. The harness is in the scratchpad if a
fast mode is ever needed; the honest use for M6 is as the `time_cap` resolution
rule, replacing the current arbitrary raw-HP comparison.

### 6.2 Re-check what the corpus cannot see

The corpus contains **none of the 19 units** affected by the armor damage-class
fix — no Gbeto, Mameluke, mangonel, bombard or warship. That fix is covered by
`tests/test_ranged_melee_class_armor.py` and nothing else. Its real effect lands
in the 504k table.

### 6.3 Smaller items

- `TRAMPLE_K` / `GRAZE_K` equivalents were never ported and may not be needed —
  they compensate for JS arena packing. Verify before importing them.
- `contact_capacity()`'s floating-point fix is worth salvaging from
  `sim/phase2cd-experiment` even without envelopment: `asin(0.5)` lands one ULP
  above π/6, so the naive expression returns **5 instead of 6** for equal-sized
  bodies. The JS engine has the same bug — its comment claims 6 while
  `Math.floor` gives 5.

---

## 7. The full baseline run

```bash
pypy3 -m aoe2x.batch.rebuild_matchup_baseline \
    --out D:/AI/matchup_baseline_180059.db --workers 23
```

- **114,236 dedup groups → 504,804 matchup rows**, escalating 8–40 seeds
- **~7.8 hours** at the measured 4.1 groups/s; 90% of groups stop at 8 seeds
- Output path is **outside the repo** — never commit a baseline
- Resumable: completed groups are skipped, so a resume is cheap
- 672 GB free; needs ~200 MB

**Guard rails.** `end_reason` and `game_time_s` are recorded per row. The
pre-change Slinger sweep was **100% `eliminated`, zero `time_cap`, mean fight
46.1s**. That is the baseline to defend — an appreciable `time_cap` share means
fights are dragging, which is the risk if `KITE_STOP_TIME` is removed.

**Completeness.** The run now refuses to look clean while carrying holes; a
failed group stays pending for retry instead of being recorded as done with
`n=0`. Confirm at the end:

```sql
SELECT COUNT(*) FROM groups_failed;              -- must be 0
SELECT COUNT(*) FROM groups_done WHERE n = 0;    -- must be 0
```

**After the run:** `derive_unit_rankings.py`, `derive_pool_scores.py`,
`best_units.py` exports, then `python .golden/capture_baseline.py`, then
`pytest`. Commit the regenerated DBs on `staging` and smoke-test before any
promotion.

**One re-sim window.** `simulation_real.py` is byte-hashed into `sim_version`,
so *any* edit — even a comment — stales every row. This is what carry-forward
(runbooks §2a) exists to soften.

**When the block in §6.1a clears, the run is small.** The kiting change alone has
a narrow, provable blast radius — everything else is byte-identical to
`matchup_baseline_180059.db` and can be carried forward:

| set | groups |
|---|---|
| ranged-v-ranged where one side out-speeds AND out-ranges | 3,728 |
| any group whose fights approach the 120s decision point (>90s mean) | 4,708 |
| **union → re-sim** | **8,392** (6.9%) |
| **carry forward** | **113,060** (93.1%) |

~27 minutes rather than 6.6 hours. This is the narrow case runbooks §2a was
written for, and a far better debut for carry-forward than the 75%-of-table
version considered earlier. Whatever fixes §6.1a will widen this — recompute the
blast radius against the *actual* change, do not reuse these numbers.

Non-negotiables from §2a when that run happens: write to a **new DB file** (never
overwrite, or the diff that would catch a bad carry-forward is destroyed), stamp
copied rows with the new `sim_version` plus a `simmed_at_version` provenance
column, and draw the **verification sample from the 40–50s band** — a uniform
sample would mostly draw from the safe bulk and prove nothing.

---

## 8. Things that bit me

- **A test that passes before *and* after proves nothing.** The existing ramp
  and trample tests passed either way — one landed a single hit
  (indistinguishable from the accumulator), the other checked gating rather than
  reach. Both were rewritten to discriminate, and every fix was verified against
  the stashed pre-fix engine.
- **Hardcoded geometry in tests silently rots.** The trample test pinned a
  1.2-tile placement tuned to the old fat radius and stopped discriminating
  under true radii. Its own guard assertion caught it; it now derives placement
  from live radii.
- **The `.golden` baseline does not cover this engine.** `test_simulations.py`
  runs through `simulation.py`. Real coverage is
  `test_position_sim_abilities.py` and friends.
- **Check the column the engine actually reads.** An early claim that Kamayuk
  and Steppe Lancer were hit by the armor bug was wrong: they have
  `final_range >= 1` but `is_ranged = 0`, and `combat_unit_loader` zeroes
  `attack_range` unless `is_ranged` is set. The affected list is exactly 19.
- **Verify the integrity check on every exit path.** The first version of the
  silent-hole fix was bypassed by the early return taken when nothing is
  pending — exactly the case it existed for.
- **Read the units before believing the number.** `team*_hp_pct` is a fraction,
  not a percentage, so a "0.36 gap" is 36 points of HP. Misreading it produced a
  confident, wrong claim that cross-civ same-slug fights were all draws when
  22.5% are blowouts.
- **A stored column is a mean over 8–40 seeds.** `game_time_s` reading 45s does
  not mean no seed ran 70s. Measured: rows in the 40–50s band have a 5.7–8.6%
  chance of containing a seed past 60s. Never scope a carry-forward from an
  averaged field (runbooks §2a).
- **Look in the archive before declaring something missing.** The previous
  baseline was reported absent because the glob was `/d/AI/*.db`; it was in
  `D:/AI/archive/`, which `data/inputs/MANIFEST.md:57` documents as the canonical
  location — and in both Railway buckets besides.
- **Deleting a crude model is not the same as fixing it.** `KITE_STOP_TIME` reads
  as an unphysical hack, and removing it cost four tape rows. A bad model of a
  real constraint still beats no model. Replace, then delete — never the reverse.
- **A plausible mechanism that never fires is worthless.** Attacker capacity: 0
  saturations in 23,278 checks. The decided-fight exit: 0 firings in 70 fights at
  any threshold up to 70%. Instrument whether a new mechanism actually triggers
  before tuning its constants.
