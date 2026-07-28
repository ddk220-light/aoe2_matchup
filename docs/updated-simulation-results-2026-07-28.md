# Updated simulation results — 2026-07-28

Fidelity work on **`aoe2x/sim/simulation_real.py`**, the position-based engine
that produces every matchup number the site serves. Written as a resume point:
everything needed to pick this up cold is here.

- **Branch:** `updated-simulation-results-2026-07-28` (8 commits, off `staging`)
- **Engine state:** `sim_version b9be1ba0a03b8395`
- **Agreement with in-game recordings: 33/38 (87%)** at recorded counts,
  32/38 (84%) at equal counts — up from a **31/38 (82%)** baseline
- **Tests:** 350 passed, 13 skipped
- **Nothing has been re-simulated yet.** All committed DBs still hold
  pre-change data. Nothing the site serves has moved.

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

The kite gate keys off **damage-per-hit**, which provably cannot work:
**Blackwood does 1 dmg/hit and wins; Xianbei does 1 dmg/hit and loses.** Same
number, opposite outcomes.

The replacement derived from the JS-side investigation is the end-to-end cycle
race:

```
effective retreat speed = movement_speed × (1 − attack_delay / reload_time)
```

A unit that must stand still to fire is slower than its paper speed. This
already predicts rows nothing else did — the **War Elephant at 0.88 catches the
Slinger** because the Slinger's *effective* speed is 0.85, despite the elephant
being slower on paper. Xianbei stands still 38% of its cycle and kites like a
0.95 unit despite 1.54 speed; Mangudai and Janissary have ~0 attack delay and
are excellent kiters.

Note `KITE_STOP_TIME = 60` still exists in the Python engine — an unphysical
global cutoff that switches kiting off mid-fight. It is what currently
guarantees fights resolve. If it is removed, replace it with a *decided-fight*
exit (one side taking no damage while dealing steady damage) rather than a
timer, and watch the guard rails in §7.

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
so *any* edit — even a comment — stales all 504,804 rows. Decide whether the
kiting work (§6.1) lands before the run, or accept a second ~8-hour run.

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
