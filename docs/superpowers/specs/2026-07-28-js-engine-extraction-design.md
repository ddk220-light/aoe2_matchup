# JS engine extraction + test harness — design

**Date:** 2026-07-28 · **Branch:** `improved-simulation` · **Status:** approved design, plan pending

Sub-project 1 of the simulation-engine migration decided in
`docs/simulation-engine-migration.md`: make production `simulate.js` the single
engine for both the UI and the batch. This spec covers **the instrument only** —
extract the engine into a shared module, build the standalone diagnostic harness,
and prove headless Node reproduces the UI bit-for-bit. **No behavior changes.**

Later sub-projects (separate specs): accuracy work guided by this instrument,
then the batch/rig/`sim_version` migration.

---

## 1. Goals and non-goals

**Goals**

1. One engine codebase imported unmodified by three consumers: the Battle Sim
   page, the standalone harness page, and a headless Node runner.
2. Deterministic: seeded RNG, fixed 1/60 tick, per-tick state hashing. Same
   scenario + seed ⇒ identical hash stream (V8 canonical).
3. A diagnostic harness good enough to replace tick-level instrumentation —
   the "look at it for thirty seconds" workflow, reachable over Tailscale from
   any device.
4. A parity gate proving the extracted engine reproduces today's engine
   bit-for-bit before the production page cuts over.

**Non-goals (deliberately excluded)**

- Any behavior or accuracy change. Suspicious code found during extraction gets
  a `TODO(accuracy)` comment, never a fix.
- The spatial grid (changes float-op order ⇒ breaks parity; it is the *first*
  change of the accuracy phase, validated by this instrument).
- Tile-space conversion (engine keeps pixel space: 900×600, TILE_SIZE 30).
- Corpus/margin scoring rig, batch pipeline, `sim_version` re-pointing.
- Changes to the Python engines or the pytest suite.

## 2. File layout

```
apps/website/static/js/engine/          # THE engine — one copy, served + imported
  package.json        # {"type": "module"} so Node treats .js as ESM
  index.js            # public API re-exports
  rng.js              # mulberry32(seed) → rng instance
  constants.js        # engine constants only (MELEE_RANGE_BUFFER, …)
  projectile.js       # Projectile — update logic, no render
  melee_effect.js     # MeleeEffect — timers/state, no render
  battle_unit.js      # BattleUnit — combat/ability core, no render
  sim.js              # step(dt), collision + avoidance passes, winner, stateHash()
  scenario.js         # scenario config → initial state (spawns, jitter, teams)

apps/website/static/js/sim_renderer.js  # browser-only renderer: reads engine state;
                                        # owns sprites/Image/palette (w/ unit_sprites.js)
apps/website/static/js/simulate.js      # shrinks to the page shell: selection UI,
                                        # canvas glue, rAF loop → engine + renderer
apps/website/static/lab/sim_harness.html
apps/website/static/lab/sim_harness.js  # the standalone harness page
apps/website/static/lab/sim_worker.js   # Web Worker for the multi-seed scoreboard

tools/simjs/
  headless.mjs        # runFight(scenario) → outcome + optional hash stream
  parity_capture.mjs  # drives TODAY's simulate.js (vm harness, seeded stub) → golden
  parity_check.mjs    # same panel through the new engine → bit-for-bit diff
  golden/panel.json   # the captured parity panel
```

**Rules for `engine/`:** relative imports only; no Node or browser built-ins; no
`document`/`window`/`Image`; no `Math.random` (test-enforced). Render methods
move **out** of the classes into `sim_renderer.js`, which reads public state —
the core is DOM-free by construction, not by convention.

## 3. Engine API

```js
const sim = createSimulation({
  mapW: 900, mapH: 600,
  teams: [ {combatDict, slug, civ, count, relics, startKills}, {…} ],
  seed: 12345,
});
sim.step(1/60);      // one tick — UI calls this in its rAF sub-step loop
sim.runToEnd(600);   // headless/scoreboard path, same code, no rendering
sim.state;           // units, projectiles, effects, time, winner
sim.stateHash();     // FNV-1a over raw float bits of (x, y, hp, state) per unit + rng state
```

- Combat dicts are exactly what `/api/ref/combat-unit/<civ>/<slug>?age=Imperial`
  returns — the production data path, unchanged.
- One RNG instance per simulation, threaded to every draw site (the 3
  accuracy/miss sites, spawn jitter, plus anything extraction uncovers).
- **Determinism contract:** same scenario + seed ⇒ identical `stateHash()`
  stream on V8 (Node + Chrome). Firefox/Safari may micro-diverge on
  transcendentals; they are display surfaces, not ground truth.
- **Tick is 1/60 everywhere** — UI, harness, headless, and later the batch.
  A batch-only tick rate would be divergence #7; banned.
- The hash stream is the standing cross-engine equivalence check: a parity
  failure names the tick it first diverged.

## 4. The harness page

Served by the same Flask app at `/static/lab/sim_harness.html` (no route
changes); run Flask on `0.0.0.0` and open via the tailnet address from any
device. Four capability groups, all v1:

1. **Scenario setup** — team pickers from the same unit/civ API as the Battle
   Sim; count fields with three fill modes: explicit number, the UI rule
   (unweighted sum, no cap), or the corpus rule (gold ×1.5, budget 3000, cap 21,
   `TRAIN_BATCH` divisor). Preset dropdown for the known problem fights with
   corpus counts (Slinger v Bengalis Elephant, v Cataphract, v Huns Paladin,
   v Bulgarians Hussar, …).
2. **Seed + time control** — seed field, randomize, replay-this-seed;
   pause / resume / single-tick step; speed 0.25×–8× (scales `step()` calls per
   frame; tick math never changes).
3. **Diagnostic overlays** (toggleable) — unit state coloring
   (kiting/windup/attacking/moving/dead), target lines, range rings, per-side
   live DPS and hits-landed vs nominal, fight clock, and the **free-fire
   timer** (seconds until the melee side lands its first blow — the number that
   exposed the Python's 45 s hole).
4. **Multi-seed scoreboard** — run N seeds in a Web Worker; table of
   seed / winner / time / survivors / HP%; aggregates (win rate, mean survivors,
   mean HP%). The mini-rig until the Node rig exists.

Overlays read `sim.state` exactly as the renderer does — no private hooks.

## 5. Parity gate and testing

1. **Capture** (`parity_capture.mjs`): 20–30 matchups × 5 fixed seeds (final
   list pinned in the implementation plan) covering
   ability breadth (plain melee, kiting ranged-v-melee, ranged-v-ranged,
   trample/elephants, Konnik rebirth, Chu Ko Nu multi-shot, Rocket Cart volley,
   Leitis relics, …). Drives the **unmodified** `simulate.js` through the vm
   harness borrowed from `origin/aoe2_ai_for_simulation` with `Math.random`
   stubbed to `mulberry32(seed)`. Records final outcome, survivor HP vector,
   fight time, and unit-position snapshots every 60 ticks → `golden/panel.json`.
   (Snapshots, not `stateHash()` — the old engine has no hash method; the hash
   stream is for new-engine determinism tests only.)
2. **Check** (`parity_check.mjs`): replays the panel through the extracted
   engine after each extraction step; a mismatch names matchup, seed, and first
   divergent snapshot. Bit-for-bit match required before cutover.
3. **Engine unit tests** (`node --test`, zero deps): determinism (same seed
   twice ⇒ identical hash stream; different seeds ⇒ different), the
   `Math.random` grep ban over `engine/`, spawn-layout goldens, ability
   micro-fixtures.
4. **Cutover**: `simulate.js` becomes a `type="module"` script; globals shared
   with `sim_params.js` are converted to imports or deliberate `window.X =`
   exports. Deploy to staging, manually smoke the Battle Sim page (sprites,
   relic/kill options, matchup panel), then promote via the normal
   staging → main flow with explicit user approval at each push.

The 350-test pytest suite is untouched; the Python engine keeps serving the
batch until sub-project 3.

## 6. Risks

| Risk | Mitigation |
|---|---|
| vm-harness capture hits script-load-order quirks | It already runs on the recording branch; capture is a one-off tool |
| Module conversion surfaces hidden global couplings in the page | Parity gate + staging smoke before promotion |
| Two engine copies exist mid-extraction | Short-lived by design; parity check runs at every step; sub-project ends with the cutover |
| Non-V8 browsers micro-diverge | V8 is canonical for all golden claims; other browsers are display only |

## 7. Decisions of record

- Instrument first; accuracy and batch are later specs. (User, 2026-07-28)
- Move + cutover within this sub-project — no long-lived copy. (User)
- Harness served over Tailscale from the local Flask app. (User)
- All four harness capability groups are v1. (User)
- Multi-file engine dir + render split + tick hashing + parity gate. (User: "A")
- Primary accuracy metric for later phases is **margins, not the corpus bit**
  (per `docs/simulation-engine-migration.md` §3.2); widening the margin holdout
  (more recorded fights) should precede heavy tuning.
