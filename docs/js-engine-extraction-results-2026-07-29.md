# JS engine extraction — results and findings

**Date:** 2026-07-29 · **Branch:** `improved-simulation` (20 commits, `7a37993..5b651cf`) ·
**Status:** sub-project 1 of the simulation-engine migration COMPLETE; final whole-branch
review verdict SHIP.

Spec: `docs/superpowers/specs/2026-07-28-js-engine-extraction-design.md` ·
Plan: `docs/superpowers/plans/2026-07-28-js-engine-extraction.md` ·
Background: `docs/simulation-engine-migration.md`

---

## 1. What was built

- **One engine, three consumers.** `apps/website/static/js/engine/` (8 DOM-free ESM
  files: rng, constants, projectile, melee_effect, battle_unit, sim, scenario, index)
  is imported unmodified by the Battle Sim page (`simulate.js`, now a 1,339-line page
  shell + `sim_renderer.js`), the lab harness, and the headless Node runner.
- **Determinism contract.** Seeded mulberry32 threaded through every draw site
  (spawn jitter, accuracy roll, two miss-scatter draws); zero `Math.random` in
  `engine/` (test-enforced); fixed 1/60 tick everywhere; `sim.stateHash()` (FNV-1a
  over positions/HP/states + rng state) for tick-level divergence detection.
- **The parity gate** (`tools/simjs/parity_check.mjs`): a 205-fight golden panel
  (41 rows × seeds 1–5, all 32 JS abilities exercised — verified by
  `tools/simjs/ability_coverage.py`) captured from the pre-extraction engine via a
  vm harness with seeded RNG. The extracted engine reproduces it **bit-exactly** —
  it passed on the first run with zero engine fixes, and was re-verified after every
  subsequent change (combat counters, cleanups). A negative control confirmed the
  gate detects drift at the 1e-13 level. Provenance: `tools/simjs/golden/panel.meta.json`
  records the pre-cutover `simulate.js` blob SHA (`d96492d7…`) and capture commit
  (`c889c39`). Exit codes: 0 parity, 1 divergence, 2 gate-broken (meta mismatch /
  empty selection).
- **The diagnostic harness** (`/static/lab/sim_harness.html`): problem-fight presets
  (corpus counts, Imperial-only slugs), three count modes (explicit / UI rule /
  corpus rule with gold ×1.5, cap 21, TRAIN_BATCH), seed replay + single-tick
  stepping + 0.25–8× speed, toggleable overlays (unit-state colors, target lines,
  range rings, per-side swings/hits/damage/DPS, free-fire timer), and a Web-Worker
  multi-seed scoreboard. Flask binds 0.0.0.0, so it is reachable over Tailscale at
  `http://<tailnet-ip>:5002/static/lab/sim_harness.html`.
- **Engine counters** (`sim.combatStats`: swings / hitsLanded / damageDealt per
  team): pure bookkeeping, excluded from `stateHash`, proven behavior-neutral by a
  parity re-run.

**Final verification on HEAD:** 17/17 engine node tests · PARITY OK 205 fights
bit-exact · 7/7 projectile-miss tests (now importing engine modules; the
brace-extraction hack is gone) · pytest 350 passed / 13 skipped (unchanged from
branch point) · Battle Sim page + harness both smoke-tested in-browser, console
clean.

**The standing rule** (also in CLAUDE.md and `docs/architecture/runbooks.md` §3):
any edit to `engine/*.js` re-runs `node tools/simjs/parity_check.mjs`. Behavior
changes are the accuracy phase's job and invalidate the golden *intentionally* —
the procedure is a documented re-capture, never silencing the gate.

## 2. Cross-engine comparison — where the JS and Python engines land

Full tables: `lab/cross_engine/REPORT.md` (raw per-seed data in
`js_results.json` / `py_results.json`). Setup: 16 unit types (one per class,
Imperial, DB-validated slugs), all 120 unordered pairs, 10v10, seeds 1–5, 600
fights per engine, same combat dicts from `aoe2_reference.db`, 600 s cap.
Every aggregate below was independently re-derived by a reviewer from the raw
rows — zero discrepancies.

| metric | value |
|---|---|
| winner agreement (per-pair, 3-of-5 majority) | **109/120 = 90.8 %** |
| … melee-only pairs | 35/36 = 97.2 % |
| … pairs containing a ranged unit | 74/84 = 88.1 % (10 of the 11 disagreements) |
| mean \|Δ survivor margin\| | 1.79 units (median 0, max 18) |
| mean \|Δ HP % margin\| | 12.9 pp |
| mean fight-time ratio (JS / Python) | 1.39× (55.8 s vs 36.1 s mean) |
| 600 s timeouts | JS **7**/600 (residue-kiter signature) · Python **0**/600 |

Reading the shape, not judging a winner (neither engine is ground truth — that is
the tape/margin metric's job, next sub-project):

- **Melee physics essentially agree** across the two engines despite the six
  documented implementation divergences (`docs/simulation-engine-migration.md` §6).
- **The disagreement is concentrated exactly on the kiting/geometry axis** §6
  predicted: map size, wall-adjacent vs centered spawns, and the Python's fitted
  `KITE_STOP_TIME`/`CHURN` constants. Every Python fight ended by elimination
  (longest 109.3 s — its kite-stop always forces an ending); the JS lets kiting
  run, 1.4× longer fights and 7 cap-outs.
- **Largest single divergence:** Mongols Heavy Cav Archer vs Bengalis Elite Battle
  Elephant — JS: cav archers sweep with 7–8 survivors at 310–420 s; Python: cav
  archers wiped 0/10 in ~45 s. A perfect first case to watch in the harness.
- Perf note (not a benchmark): the 600-fight sweep took 5.9 s in Node
  (`headless.mjs`, no vm overhead, small 10v10 fights) vs 106 s in CPython.

## 3. Execution record

Executed via subagent-driven development: 11 tasks, each implemented by an Opus
subagent, each gated by an independent review (spec compliance + quality), fix
rounds until clean, then a final whole-branch review (verdict SHIP). Notable
review catches along the way: the golden panel's ability coverage was extended
from 19/32 to 32/32 *before* the golden froze; a factually wrong timing rationale
in the headless runner was corrected against measurement; the parity gate gained
a meta-file assertion so a truncated golden can't silently weaken it.

The wiring facts future sessions need are already inline in the code and
architecture docs; two deliberate cosmetic-state writes by render hosts are
documented at their sites (`sim_renderer.js` writes `unit.faceRight`; animating
hosts stamp `unit.attackSheet` — both excluded from `stateHash`, never read by
combat logic).

## 4. Known deferred items (triaged FINE-TO-DEFER at final review)

None block merging; listed so they aren't rediscovered:

- `parity_check.mjs`: progress denominator wrong under `--id`/`--seed`; a
  misspelled/last-position CLI flag silently degrades to the (stricter) full run;
  snapshot-0 divergence message reads "ticks 1..0"; crash and DIVERGED share
  exit 1 (exit 2 = gate-broken).
- `legacy_harness.cjs` (frozen one-off capture tool): dead exports
  (`CONE_SLUGS`, `RAMP`, `MAX_S`); the git-HEAD cleanliness check lives in
  `parity_capture.mjs` rather than the harness body.
- Harness: no `cancelAnimationFrame` id stored (scripted pause/resume in the same
  frame can double-run the loop for one self-correcting frame); no automated test
  (an engine field rename breaks it silently with parity still green;
  `window.__harness` hooks exist for scripted smoke).
- Wording: the harness seed card and `simulate.js` (~line 1215) overstate
  seed-replay exactness for the *watched* (wall-clock-stepped) fight — the
  tick-exact claim holds for the scoreboard/headless path; the watched fight's
  final sub-step per frame is partial (inherited legacy behavior, documented in
  the scoreboard hint). Overlays skip one frame on a mid-pause resize repaint.
- `tests/test_ability_registry.py`: the "js" source concatenates the page shell
  (only `pop_space` relies on it — army sizing is page logic); a tighter split
  needs an `ability_registry.py` change.
- Parked with ruling: the page shell uses `winner === null` where legacy used
  falsy `!winner` — a draw now stops at the draw tick with a single winner
  callback (strictly more correct; engine/parity untouched).

## 5. Next (accuracy phase — separate spec)

1. Spatial grid for the O(N²) collision/avoidance loops — the first intentional
   behavior change; lands with a documented golden re-capture and a benchmark.
2. Chaser target-commitment for the residue-kiter cap-outs (watch the 7 timeout
   fights and the cav-archer/elephant pair in the harness first).
3. Score on margins (holdout), not the corpus bit; widen the margin holdout with
   more recorded fights before tuning (`docs/simulation-engine-migration.md` §3.2).
