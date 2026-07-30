# Target-thrash fix for the shared JS engine — design

**Date:** 2026-07-29 · **Branch:** `improved-simulation` · **Status:** approved design, pre-implementation

Fixes the pursuit pathology in `apps/website/static/js/engine/battle_unit.js` where a
chasing unit blacklists the target it is walking straight at every 0.8 s, oscillates
between enemies on opposite flanks, and never arrives. Observed by the user on the Battle
Sim page as an Elite Battle Elephant ping-ponging between two ranged units; measured as
the dominant JS-side driver of the cross-engine divergence recorded in
`lab/cross_engine/REPORT.md`.

Everything quantitative in this spec was **measured**, not predicted: the fix was
prototyped by monkeypatching the live engine in the sim-harness browser tab (zero file
edits; the wrapper reproduced the unmodified engine's 120-pair results bit-for-bit before
any variant was trusted), and the design survived a 12-agent adversarial verification
pass that falsified three earlier claims (recorded in §8).

---

## 1. Problem and root cause

Two defects in `moveTowardTarget` (`battle_unit.js:1332-1344`):

**Defect A — the progress bar is a per-frame constant, so it demands 1.0 tile/s.**
`if (newDist >= this.lastDistToTarget - 0.5)` charges `stuckTimer` unless the unit
*closes* ≥ 0.5 px per 1/60 s sub-step = 30 px/s = 1.0 tile/s. Almost no pursuit clears
that: seven roster units move slower than 1.0 t/s outright (Siege Onager 0.60, Heavy
Scorpion 0.65, Elite Teutonic Knight 0.88, Elite Skirmisher / Arbalester / Hand
Cannoneer 0.96, Elite Battle Elephant 0.99 — an elephant closing on a **pinned,
stationary** archer at full speed was measured being declared stuck at t = 4.0 s), and
even a Paladin (1.49 t/s) chasing a fleeing Arbalester closes at only ~0.53 t/s.
`simulation_real.py:186-195` documents this exact frame-rate coupling and normalized its
copy to a rate.

**Defect B — the response to "stuck" is blacklist-and-null.** `stuckTimer > 0.8` →
`blockedTargets.add(target); target = null` → next frame `findTarget` picks the nearest
*unblocked* enemy — typically on the opposite flank — and the cycle repeats until the
blacklist covers every living enemy and clears itself (`battle_unit.js:548-554`).

Measured consequences (10v10, seeds 1–5, combat dicts from `aoe2_reference.db`):

| symptom | baseline |
|---|---|
| elephant team target switches (HCA v ELE) | 12.5 /s (~4,374 per fight) |
| elephant net displacement / path walked | 2–35% per 10 s window |
| fights hitting the 600 s cap | 7 / 600 |
| mean fight length (JS vs Python 36.1 s) | 55.8 s |
| cross-engine majority agreement | 109/120 |

This is not an elephant problem: 10 of the 11 disagreeing cross-engine pairs contain a
ranged unit because *every* chase of a kiter fails the 1.0 t/s bar. The real game
commits — units fixate on a target while they believe they can catch it (bait tactics
depend on this) — so commitment is also the behavior to reproduce.

## 2. The engine change

All inside `moveTowardTarget`. Replace the accumulation condition; keep the 0.8 s
threshold, the decay branch, blacklist-and-null, and the clear-when-all-blocked rule
exactly as they are.

```js
// snapshot BEFORE the avoidance blend overwrites dx/dy in place (:1296-1300)
const toTgtX = dx, toTgtY = dy;          // unit vector toward target
const entryX = this.x, entryY = this.y;  // pre-move position
// ... existing avoidance / smoothing / move / bounds clamp, untouched ...

const moveAmount = this.moveSpeed * dt;
// POST-CLAMP actual displacement projected on intent — a wall-pinned unit reads 0
const intentProgress = (this.x - entryX) * toTgtX + (this.y - entryY) * toTgtY;
const newDist = this.distanceTo(this.target);

const stalled  = newDist >= this.lastDistToTarget - STUCK_PROGRESS_RATE * dt;
const pursuing = intentProgress >= PURSUIT_FRACTION * moveAmount;
const receding = /* target's radial displacement since last tick, along toTgt */ > RECEDE_EPS * moveAmount;

if (stalled && !(pursuing && receding)) this.stuckTimer += dt;
else this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
```

**The scope is inverted relative to a naive gate — this is the load-bearing decision.**
We do not gate the stuck path on "wedged"; we **exempt only the provably legitimate
case**: the unit is walking at its target (`pursuing`) *and* the target is actually
running away (`receding`). A plain `stalled && wedged` gate was measured deleting
89–99.8% of melee-scrum blacklist events — it removes the fan-out mechanism, not just
the misfire. With the `receding` conjunct, scrum rows retain ~49% of their blacklist
events (91/185 across three melee rows, seeds 1–3) and their majorities are unchanged,
while both elephant pairs stay fixed.

**Why `pursuing` can never misread an honest chase (theorem, not tuning):** velocity is
renormalized every frame with `smoothing = 0.3` (`:1309-1318`), so
`dot(v_new, desired) = (0.7 + 0.3c)/√(0.58 + 0.42c) ≥ 0.9035` for any prior heading
`c = cos(v_old, desired)` — even a full 180° reversal. A unit whose desired direction is
on target cannot score below 0.9035, so the 0.35 threshold cannot fire on it. Turn-lag
contributes exactly 0.0% of sub-threshold frames (measured across five golden panels).

**Constants** (module constants next to the existing ones, with comments):

| constant | value | status |
|---|---|---|
| `STUCK_PROGRESS_RATE` | **30 px/s** (1.0 t/s) | exactly today's 0.5 px/frame at dt = 1/60 — a provable no-op at the current tick rate, load-bearing only if dt ever changes (the Python ran at 1/30). Deliberately NOT Python's 15 px/s: measured outcome-identical across 7.5/15/30, so we keep the JS's own value and change one thing at a time. |
| `PURSUIT_FRACTION` | **0.35** | frozen choice, not a fit. Measured: no knee anywhere in 0.15–0.9 (monotone P(wedged\|stalled)); outcomes identical across 0.2/0.35/0.5. The 0.9035 floor means any value ≤ 0.9 passes honest chases. |
| `RECEDE_EPS` | **0.05** | float-noise guard on the radial-recession test, not a behavior knob. |

**New per-unit state:** previous-tick target position (`_prevTgtX/_prevTgtY/_prevTgt`)
for `receding`, plus a baseline-freshness marker (§3). `stateHash()` (`sim.js:232-244`)
hashes only `x, y, currentHp, state` per unit plus sim-level values — these fields are
invisible to it by construction, like `stuckTimer` and `vx/vy` already are. The purity
test is a source-text regex; also unaffected.

## 3. Companion fixes (same change, verified necessary)

**3a. Stale `lastDistToTarget` baseline.** It is written only inside `moveTowardTarget`
(`:1339`) and `findTarget` (`:1367-1369`); the kiting and attacking branches never touch
it. A ranged unit that kites for N frames and then re-enters the moving branch compares
an N-frame-old distance against a one-frame bar — `stalled` is not a rate at all for
such units. Fix: record when the baseline was last stamped; on re-entry after a gap,
re-baseline (`lastDistToTarget = current distance`) instead of judging `stalled` on an
unknown interval.

**3b. Reachability swap — the idle-chaser escape.** Commitment without an escape leaves
units permanently idle: in a committed Siege Ram ×10 v Arbalester ×10 fight, 4 of 10
rams were alive all 36,000 ticks with `inRange()` true on **zero** of them (their own
r=26 allies filled the corner), while two other rams stood within reach of a *different*
arbalester 26–27% of ticks and never swung. Fix: when `stalled` and some other living
enemy is currently within attack reach (`attackRange + radius + enemy.radius`), retarget
to it directly (no blacklist involvement, no new constant). This is what today's
detector accidentally provided and what a player would do.

**What deliberately stays unchanged:** the 0.8 s threshold, the −2·dt decay,
blacklist-and-null as the stuck response, `clear-when-all-blocked`, `findTarget`,
`moveAwayFromTarget` (no stuck detection there today; adding one is out of scope), the
kite gate, and the 600 s cap.

## 4. Measured results (prototype, full 120-pair matrix, seeds 1–5)

| metric | baseline | fixed (gate-only variant) |
|---|---|---|
| mean fight length | 55.8 s | **35.4 s** (Python: 36.1 s) |
| 600 s timeouts | 7/600 | **0/600** |
| target switches (HCA v ELE) | 12.5 /s | **1.1 /s** |
| cross-engine agreement | 109/120 | 111/120 |

With the `receding` conjunct (final design), spot-checked rows land closer to Python
still: elephant v Mangudai `a` @ 85.3 s vs Python's ~85 s. 8 disagreements resolved
(both elephant pairs, arb v ETK, arb v skirm, arb v ele, skirm v ETK, skirm v HC, halb v
camel), 6 created, 3 unchanged — **and all 9 residual disagreements point the same way:
the closing melee unit wins in fixed JS and loses in Python.** That single axis is the
open fidelity question (§8.1); the cross-engine winner metric cannot adjudicate it, by
construction.

## 5. Out of scope (recorded, not forgotten)

1. **Damage-floor stalemates & cap adjudication.** Ram v Arbalester runs 600 s with 377
   swings landed for 377 damage (`Math.max(1, …)` floor, `:334-337`); at the cap the JS
   returns `winner = null` while Python adjudicates by HP%. Pre-existing (commitment
   *reduces* cap-hits: tanky×shooter grid 99 → 30) and orthogonal — separate follow-up.
2. **3 px contact window.** `inRange` (`attackRange + r1 + r2`, MELEE_RANGE_BUFFER 5)
   exceeds the avoidance equilibrium (`r1 + r2 + 2`) by exactly 3 px; measured min gaps
   sit right on it. Any future tweak to either constant silently converts corner-pin
   fights into timeouts. Hazard note only.
3. **Map-size coupling.** `scenario.js` spawns off `sim.W` but every clamp uses
   `CANVAS_WIDTH` (`sim.js:194-207` TODO(accuracy)): at `mapW=1800` team 2 teleports
   875 px on tick 1. Widening the map is NOT an available mitigation for anything here.
4. **No port to `simulation_real.py`** — it is being replaced by this engine.
5. **`moveAwayFromTarget` stuck detection** (kiters have none today; unchanged).

## 6. Validation — the JS tape rig (build FIRST, measure BEFORE)

The 38-row tape corpus (`aoe2x/validation/tape_corpus.json`, real recorded fights) is
the only instrument that can adjudicate §8.1. It was the Python's training set but the
JS carries none of that fitting — for this engine it is a genuine holdout. All 31
distinct (civ, slug) pairs exist in the Imperial reference DB; zero slug fixups needed.

**Reusable as-is:** the corpus; `tape_rig.py`'s count rule (`weighted_cost` /
`arena_counts` — independently re-derived all 38 recorded count pairs, 0 mismatches);
its `CREATE TABLE IF NOT EXISTS` schema against the existing `data/validation/tape_runs.db`
(the `engine` column already exists); `report.py --diff` (engine-agnostic already);
`headless.mjs buildFight()` as the drive seam (NOT `runFight`, and never extend its
`final` block — parity compares `JSON.stringify` of it); `compute_sim_version(file_paths=…)`
pointed at sorted `engine/*.js`.

**To build:**

| piece | responsibility |
|---|---|
| `tools/simjs/dump_tape_dicts.py` → `data/validation/tape_combat_dicts.json` | corpus combat dicts (only 19/38 rows runnable off the golden dicts today). Never append to `tools/simjs/golden/` — write-once parity baseline. |
| `data/validation/tape_plan.json` (same script) | per-row explicit counts computed by `tape_rig.arena_counts` in Python. **The JS runner does zero count arithmetic** — three live count rules exist (tape rule; Battle-Sim resources rule; Battle-Sim pop rule) and not one Battle-Sim count matches any tape row. Literal integers only. |
| `tools/simjs/tape_runner.mjs` | drives `buildFight` + `sim.step(1/60)` to 600 s; emits the full `tape_battles` column set per fight (winner, end_reason, hp% with the whole-starting-team denominator, survivors, signed_score = (hp1% − hp2%)·100 matching the Python fallback). ~380 fights ≈ 15–25 s single-threaded. |
| `aoe2x/validation/tape_rig_js.py` | builds plan, spawns the runner, writes SQLite via `tape_rig.py`'s exact INSERT (no better-sqlite3 dep). `engine` string exact & greppable; `python_impl` records the node version; conventions in `notes`. |
| `aoe2x/validation/tape_margins.json` + `margin_score.py` | the §3.2 margin ground truth as a committed fixture (source: `_ingame_note` in `origin/aoe2_ai_for_simulation:apps/video/sim_v2/overrides/imp_slinger.json`, blob `3d40397…`, with provenance + `--check`); scorer reads the DB so it retro-scores all 14 existing Python runs. |
| `report.py` touch-ups | `--list` must print `engine` + `max_seconds`; `--diff` warns loudly when engine/cap/seeds differ. |

**Recording conventions (decided here):**
- **Seeds 1–5, never 0–4.** JS `makeRng(0)` ≡ `makeRng(1)` (`rng.js:5` `(seed>>>0) || 1`,
  verified byte-identical fights) — `range(5)` would double-count a seed.
- **`winner === null` at the cap → adjudicate by HP% (Python's own cap rule), with
  `end_reason='time_cap'` preserving identifiability.** Keeps the headline agreement
  figure comparable across engines; reason recorded in `notes`.
- **Python BEFORE at 600 s:** re-run `tape_rig` at `--max-seconds 600` (~2 min PyPy) so
  the like-for-like baseline exists (the HEAD run `review-current-7c4e06c0` is 180 s).
- **`team*_value_lost`:** reimplement Python's cost×damage formula in the runner (kill-
  bonus gains omitted, noted); nothing reads the column today.
- **Spawn-overflow caveat in `notes`:** at tape counts every fight starts with 1–6 units
  clamped to the bottom edge (spawn spacing vs 600 px map). Production-faithful and
  parity-locked, but the BEFORE number is measured on a squashed formation; report an
  equal_count channel alongside as the sanity check.

**Primary metric: margin MAE (survivors + HP pp), not the corpus bit.** The bit was the
Python's training set (Python HEAD scores 19/19 on runnable rows; unmodified JS 11/19 —
reporting only the bit would misframe the JS as a regression). Margins move on rows
whose bit never flips, which is exactly what a commitment fix does. Score and publish
both; margins decide.

## 7. Measurement ladder and gates

1. **Rig lands, engine untouched** → BEFORE scores (bit + margin, tape + equal_count),
   committed to `tape_runs.db`.
2. **Apply §2 + §3** → AFTER scores. Sanity sweep `PURSUIT_FRACTION` {0.2, 0.35, 0.5}
   through the rig (expected: no movement, per §2).
3. **Parity + tests:** `node --test tests/js/engine/` (must pass);
   `node tools/simjs/parity_check.mjs` **will fail — that is the fix working** (the
   prototype changes 112/123 golden finals, 12 winner flips). Per CLAUDE.md sync rule 1,
   re-capture with the reason recorded.
   **Blocker to resolve first:** the documented re-capture path is broken —
   `parity_capture.mjs` drives `legacy_harness.cjs`, which vm-evals `simulate.js`, now
   an ESM shell holding no engine copy. Decision: freeze `tools/simjs/golden/` as the
   pre-fix historical artifact and capture a **new** golden panel from `engine/` via
   `headless.mjs` (new capture script), recorded in the panel meta.
4. **Cross-engine re-run** (`lab/cross_engine`) as the secondary lens; expect ~92%
   agreement with the residual axis of §8.1, timeouts 0.
5. Unit tests for the predicate itself: honest-chase never accumulates (the 0.9035
   floor), scrum-wedge still blacklists, stale-baseline re-entry, reachability swap,
   determinism (two runs, same seed, identical `stateHash` stream).

Downstream (post-merge, per runbooks §2): golden `.golden/baseline.json` is the abstract
engine — unaffected. Matchup data re-sim happens whenever the batch pipeline moves to
this engine; `sim_version` for JS runs hashes `engine/*.js`, so rows stale correctly.

## 8. Risks and open questions

1. **THE open question — 84/720 (11.7%) 10v10 winner flips, all melee-ward.** ETK v
   Arbalester flips from 0/5 to 5/5 with 9–10 survivors in ~45 s; same shape for
   Champion v HCA, Elephant v HCA, Cataphract v Mangudai. One reading: AoE2 doctrine
   says the melee counter wins these; the thrash was robbing every closer. Other
   reading: corner-pin resolution on a 30×20 walled arena over-rewards melee at these
   margins. Both are priors. **The tape corpus decides; neither this spec nor the
   cross-engine number gets a vote.** If the tape says the flips overshoot, the knob to
   revisit first is the corner-pin geometry (spawn runway / arena), not the predicate.
2. **Chases that legitimately never resolve** (kiter strictly faster in open field:
   effective kite speeds measured — HCA 1.018 t/s, Mangudai 1.118 t/s vs foot archers
   0.82–0.89 which chasers DO out-close) end by corner, and 30 tanky×shooter cap-hits
   remain post-fix (damage-floor class, §5.1). Rig asserts timeout count ≤ baseline.
3. **Blacklist subsystem health:** with the exemption, chase rows still log hundreds of
   blacklist events and scrum rows keep ~49% — `blockedTargets` and its clear rule stay
   live. Rig records per-run blacklist counts so this is checkable, not asserted.
4. **Golden panel re-capture invalidates the extraction-era "zero behavior change"
   proof** — that proof stays valid *for its commit range*; the new panel's meta must
   state the predicate change as the cause. Provenance chain, not overwrite.

## 9. Prediction ledger (prototype-measured; the rig confirms or falsifies)

| corpus-relevant row | prediction | basis |
|---|---|---|
| Slinger v Elite Battle Elephant (the reference problem fight) | elephants close in <100 s; slinger survivor count drops toward tape's 0/6 @ 70.5% | measured winner flip + fight-time collapse on the elephant pairs |
| Slinger v Paladin / Hussar rows | fight length collapses (911 → ~7 blacklists measured on slinger-v-paladin) | pure-chase class |
| Both-ranged rows (Arb v CKN, skirm rows) with equal range | little movement | no kiting, bar rarely binding |
| Unequal-range ranged rows (skirm 9t v HC 7t) | DO move — the shorter-range side closes on a stationary target below the bar | measured flip, matches Python |
| Melee-scrum rows (Champion, Jaguar, TK mirrors) | majorities unchanged; blacklist events ≈ half of baseline | measured on 3 scrum rows |
| Margin MAE | improves on Python's 2.62 units / 8.51 pp on chase rows; degrades nowhere | fight-length convergence 55.8→35.4 s vs Python 36.1 s |

## 10. Success criteria

- Tape **margin MAE** (primary): improved on chase rows, no degradation elsewhere.
- Tape bit: JS AFTER ≥ JS BEFORE (11/19 on runnable rows) on the full 38.
- Rig timeout count ≤ BEFORE; zero units with 0 in-range ticks while an enemy stood in reach.
- `node --test tests/js/engine/` green; new predicate tests green; new golden panel
  captured with recorded cause; determinism check passes.
- Battle Sim page eyeball: elephant walks a line, arrives or dies.
