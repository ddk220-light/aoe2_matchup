# JS Engine Extraction + Test Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the battle-sim engine out of `apps/website/static/js/simulate.js` into a shared ESM module consumed by the Battle Sim page, a standalone diagnostic harness page, and a headless Node runner — with a bit-for-bit parity gate proving zero behavior change.

**Architecture:** The engine classes (`Projectile`, `MeleeEffect`, `BattleUnit`, plus the tick core of `BattleSimulation`) move into `apps/website/static/js/engine/` as DOM-free ES modules with a seeded RNG. All render code moves to a browser-only `sim_renderer.js`. A golden panel captured from the *unmodified* engine (via the vm harness from the recording branch) gates every step; the production page cuts over only when parity is bit-exact.

**Tech Stack:** Vanilla ES modules (no bundler), Node v20.10 (`node --test`, no `require(esm)` — use `.mjs` or dynamic import), Flask serves everything static, Python only for the one-off combat-dict dump.

**Spec:** `docs/superpowers/specs/2026-07-28-js-engine-extraction-design.md`. Background: `docs/simulation-engine-migration.md` (measurements that motivated all of this).

## Global Constraints

- **Branch `improved-simulation`. Commit after every task. NEVER `git push` — pushing deploys; only the user pushes.**
- **ZERO behavior change.** Copy formulas byte-for-byte, including oddities (e.g. `resolveCollisions` clamps to `CANVAS_WIDTH`/`CANVAS_HEIGHT` constants, not `this.W`). If something looks wrong, add `// TODO(accuracy): <note>` and preserve it exactly.
- **`engine/` purity:** relative imports only; no `document`, `window`, `Image`, `fetch`, `alert`, `requestAnimationFrame`, `performance`; no `Math.random` (a test enforces this). Engine files use `.js` extension (browser-served) with `apps/website/static/js/engine/package.json` = `{"type": "module"}` making Node parse them as ESM.
- **Tick is fixed `1/60` everywhere.** Never introduce another timestep.
- **`tools/simjs/golden/panel.json` is immutable truth** once captured in Task 2. A parity mismatch is ALWAYS an extraction bug: fix the engine, never regenerate the golden, never loosen the comparison.
- **Node tests live in `tests/js/engine/*.test.mjs`**, run with `node --test tests/js/engine/`. Python tests: `pytest` from repo root.
- The RNG is mulberry32 with state `(seed >>> 0) || 1` — the EXACT algorithm below (it matches the vm harness used for the golden capture; any deviation breaks parity).
- Do not touch `aoe2x/` Python engines, `sim_version.py`, batch scripts, or `.golden/baseline.json` — out of scope for this sub-project.

---

### Task 1: Engine scaffolding + seeded RNG

**Files:**
- Create: `apps/website/static/js/engine/package.json`
- Create: `apps/website/static/js/engine/rng.js`
- Test: `tests/js/engine/rng.test.mjs`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `makeRng(seed)` → `{ next(): number, getState(): number }`. `next()` returns a float in `[0, 1)`; `getState()` returns the uint32 internal state. All later engine code draws randomness ONLY through an instance of this.

- [ ] **Step 1: Write the failing test**

```js
// tests/js/engine/rng.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

test("same seed produces the identical sequence", () => {
    const a = makeRng(42), b = makeRng(42);
    for (let i = 0; i < 1000; i++) assert.equal(a.next(), b.next());
});

test("different seeds diverge", () => {
    const a = makeRng(1), b = makeRng(2);
    const same = Array.from({ length: 100 }, () => a.next() === b.next());
    assert.ok(same.includes(false));
});

test("values lie in [0, 1)", () => {
    const r = makeRng(7);
    for (let i = 0; i < 10000; i++) {
        const v = r.next();
        assert.ok(v >= 0 && v < 1);
    }
});

test("seed 0 is coerced to 1 (vm-harness semantics)", () => {
    const z = makeRng(0), one = makeRng(1);
    assert.equal(z.next(), one.next());
});

test("getState changes with each draw and is a uint32", () => {
    const r = makeRng(5);
    const s0 = r.getState();
    r.next();
    const s1 = r.getState();
    assert.notEqual(s0, s1);
    assert.equal(s1, s1 >>> 0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/`
Expected: FAIL — cannot find module `.../engine/rng.js`

- [ ] **Step 3: Write the implementation**

```json
// apps/website/static/js/engine/package.json
{ "type": "module" }
```

```js
// apps/website/static/js/engine/rng.js
// Seeded PRNG (mulberry32). EXACT algorithm and seeding semantics of the vm
// harness that captured tools/simjs/golden/panel.json (state = (seed>>>0)||1)
// — do not alter: bit-for-bit parity with the golden depends on it.
export function makeRng(seed) {
    let state = (seed >>> 0) || 1;
    return {
        next() {
            state |= 0;
            state = (state + 0x6d2b79f5) | 0;
            let t = Math.imul(state ^ (state >>> 15), 1 | state);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        },
        getState() {
            return state >>> 0;
        },
    };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/js/engine/`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/engine/ tests/js/engine/rng.test.mjs
git commit -m "feat(engine): ESM scaffolding + seeded mulberry32 RNG"
```

---

### Task 2: Golden parity capture from the UNMODIFIED engine

Capture the ground truth BEFORE anything else changes. `simulate.js` must be byte-identical to git HEAD when this runs (`git diff --quiet apps/website/static/js/simulate.js` first — abort if dirty).

**Files:**
- Create: `tools/simjs/dump_combat_dicts.py`
- Create: `tools/simjs/golden/panel_spec.json`
- Create: `tools/simjs/legacy_harness.cjs` (adapted copy of the recording branch's vm harness)
- Create: `tools/simjs/parity_capture.mjs`
- Create: `tools/simjs/golden/combat_dicts.json` (generated, committed)
- Create: `tools/simjs/golden/panel.json` (generated, committed — the immutable truth)

**Interfaces:**
- Consumes: the unmodified `apps/website/static/js/simulate.js`; `aoe2x.sim.combat_unit_loader.build_combat_dict_from_ref`; `data/golden/aoe2_reference.db`.
- Produces: `golden/combat_dicts.json` = `{ "<civ>|<slug>": {combat dict} }`; `golden/panel.json` = array of `{ id, civ1, slug1, n1, civ2, slug2, n2, seed, snapshots, final }` where `snapshots` = array (tick 0 after spawn, then every 60 ticks) of `{ tick, units: [[team, idx, x, y, hp, state], …] }` (team-1 units in array order, then team-2) and `final` = `{ winner, time, alive1, alive2, hp1, hp2 }` (`hp1`/`hp2` = sum of living `currentHp`). Numbers stored at full JSON double precision — never rounded.

- [ ] **Step 1: Write the panel spec**

`tools/simjs/golden/panel_spec.json` — entries `{ "id", "civ1", "slug1", "n1", "civ2", "slug2", "n2" }`. Include ALL of the following (ability-coverage panel; seeds 1–5 are applied to every row by the capture tool, giving ~140 fights):

```json
[
  { "id": "champ-v-jaguar",      "civ1": "Franks",      "slug1": "champion",                    "n1": 20, "civ2": "Aztecs",     "slug2": "elite_jaguar_warrior_aztecs", "n2": 20 },
  { "id": "teuton-v-cata",       "civ1": "Teutons",     "slug1": "elite_teutonic_knight_teutons","n1": 15, "civ2": "Byzantines", "slug2": "elite_cataphract_byzantines", "n2": 15 },
  { "id": "slinger-v-elephant",  "civ1": "Incas",       "slug1": "slinger",                     "n1": 21, "civ2": "Bengalis",   "slug2": "elite_battle_elephant",       "n2": 6 },
  { "id": "slinger-v-paladin",   "civ1": "Incas",       "slug1": "slinger",                     "n1": 21, "civ2": "Huns",       "slug2": "paladin",                     "n2": 7 },
  { "id": "slinger-v-hussar",    "civ1": "Incas",       "slug1": "slinger",                     "n1": 21, "civ2": "Bulgarians", "slug2": "hussar",                      "n2": 15 },
  { "id": "slinger-v-cata-50",   "civ1": "Incas",       "slug1": "slinger",                     "n1": 50, "civ2": "Byzantines", "slug2": "elite_cataphract_byzantines", "n2": 20 },
  { "id": "arb-v-ckn",           "civ1": "Britons",     "slug1": "arbalester",                  "n1": 20, "civ2": "Chinese",    "slug2": "elite_chu_ko_nu_chinese",     "n2": 15 },
  { "id": "arb-v-skirm",         "civ1": "Britons",     "slug1": "arbalester",                  "n1": 20, "civ2": "Aztecs",     "slug2": "elite_skirmisher",            "n2": 21 },
  { "id": "konnik-v-champ",      "civ1": "Bulgarians",  "slug1": "elite_konnik_bulgarians",     "n1": 15, "civ2": "Vikings",    "slug2": "champion",                    "n2": 20 },
  { "id": "leitis-v-paladin",    "civ1": "Lithuanians", "slug1": "elite_leitis_lithuanians",    "n1": 15, "civ2": "Franks",     "slug2": "paladin",                     "n2": 15 },
  { "id": "arambai-v-arb",       "civ1": "Burmese",     "slug1": "elite_arambai_burmese",       "n1": 20, "civ2": "Britons",    "slug2": "arbalester",                  "n2": 20 },
  { "id": "mangudai-v-mangonel", "civ1": "Mongols",     "slug1": "elite_mangudai_mongols",      "n1": 15, "civ2": "Celts",      "slug2": "mangonel",                    "n2": 5  },
  { "id": "onager-v-champ",      "civ1": "Celts",       "slug1": "onager",                      "n1": 5,  "civ2": "Japanese",   "slug2": "champion",                    "n2": 25 },
  { "id": "scorp-v-halb",        "civ1": "Celts",       "slug1": "heavy_scorpion",              "n1": 8,  "civ2": "Goths",      "slug2": "halberdier",                  "n2": 25 },
  { "id": "huskarl-v-arb",       "civ1": "Goths",       "slug1": "elite_huskarl_goths",         "n1": 20, "civ2": "Britons",    "slug2": "arbalester",                  "n2": 20 },
  { "id": "warele-v-halb",       "civ1": "Persians",    "slug1": "elite_war_elephant_persians", "n1": 5,  "civ2": "Byzantines", "slug2": "halberdier",                  "n2": 25 },
  { "id": "shrivamsha-v-arb",    "civ1": "Gurjaras",    "slug1": "elite_shrivamsha_rider_gurjaras", "n1": 15, "civ2": "Britons", "slug2": "arbalester",                 "n2": 20 },
  { "id": "keshik-v-champ",      "civ1": "Tatars",      "slug1": "elite_keshik_tatars",         "n1": 15, "civ2": "Slavs",      "slug2": "champion",                    "n2": 20 },
  { "id": "kipchak-v-skirm",     "civ1": "Cumans",      "slug1": "elite_kipchak_cumans",        "n1": 15, "civ2": "Vietnamese", "slug2": "elite_skirmisher",            "n2": 20 },
  { "id": "rattan-v-arb",        "civ1": "Vietnamese",  "slug1": "elite_rattan_archer_vietnamese", "n1": 18, "civ2": "Ethiopians", "slug2": "arbalester",               "n2": 20 },
  { "id": "hussar-v-genoese",    "civ1": "Poles",       "slug1": "hussar",                      "n1": 20, "civ2": "Italians",   "slug2": "elite_genoese_crossbowman_italians", "n2": 20 },
  { "id": "plumed-v-halb",       "civ1": "Mayans",      "slug1": "elite_plumed_archer_mayans",  "n1": 20, "civ2": "Teutons",    "slug2": "halberdier",                  "n2": 20 },
  { "id": "camarcher-v-knight",  "civ1": "Berbers",     "slug1": "camel_archer_berbers",        "n1": 18, "civ2": "Franks",     "slug2": "knight",                      "n2": 18 },
  { "id": "tiger-v-halb",        "civ1": "Wei",         "slug1": "elite_tiger_cavalry_wei",     "n1": 15, "civ2": "Vikings",    "slug2": "halberdier",                  "n2": 20 }
]
```

Additionally append 4 rows for these mechanics by finding the exact slugs in the DB (they exist; suffixes may differ): Rocket Cart volley (`… LIKE '%rocket%'`), Fire Lancer charge projectiles (`… LIKE '%fire_lancer%'`), Jian Swordsman transform (`… LIKE '%jian%'`), Guecha Warrior ally-death-heal (`… LIKE '%guecha%'`). Query:
`python -c "import sqlite3; c=sqlite3.connect('data/golden/aoe2_reference.db'); print(c.execute(\"select distinct civ_name, unit_slug from ref_units where unit_slug like '%rocket%'\").fetchall())"`
Give each a 15-unit army against a sensible 20-unit generic opponent (champion/halberdier/arbalester).

- [ ] **Step 2: Write the dump script**

```python
# tools/simjs/dump_combat_dicts.py
"""One-off: dump combat dicts for every (civ, slug) in golden/panel_spec.json.

Run with the conda python (needs the repo on sys.path):
    python tools/simjs/dump_combat_dicts.py
Fails loudly on any slug not found — fix panel_spec.json, don't skip rows.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402

spec = json.loads((ROOT / "tools/simjs/golden/panel_spec.json").read_text())
pairs = sorted({(r["civ1"], r["slug1"]) for r in spec} | {(r["civ2"], r["slug2"]) for r in spec})

con = sqlite3.connect(ROOT / "data/golden/aoe2_reference.db")
con.row_factory = sqlite3.Row
out, missing = {}, []
for civ, slug in pairs:
    row = con.execute(
        "select * from ref_units where civ_name=? and unit_slug=? and age='Imperial'",
        (civ, slug),
    ).fetchone()
    if row is None:
        missing.append(f"{civ}/{slug}")
        continue
    out[f"{civ}|{slug}"] = build_combat_dict_from_ref(row)

if missing:
    sys.exit("NOT IN DB: " + ", ".join(missing))
dest = ROOT / "tools/simjs/golden/combat_dicts.json"
dest.write_text(json.dumps(out, indent=1, sort_keys=True))
print(f"wrote {len(out)} dicts -> {dest}")
```

- [ ] **Step 3: Run the dump; fix any missing slugs**

Run: `python tools/simjs/dump_combat_dicts.py`
Expected: `wrote N dicts -> …/combat_dicts.json`. If it exits with `NOT IN DB`, query the DB for the right slug (unique units carry a `_<civ>` suffix, e.g. `huskarl_goths`) and correct `panel_spec.json` — keep the ability coverage, never delete a mechanic row.

- [ ] **Step 4: Bring in the vm harness**

Run: `git fetch origin aoe2_ai_for_simulation` then
`git show origin/aoe2_ai_for_simulation:apps/video/sim_v2/headless_sim.js > tools/simjs/legacy_harness.cjs`
Read the file. It loads the real `simulate.js` (plus siblings in browser load order) into a `vm` sandbox with Proxy DOM stubs, injects mulberry32 as `Math.random` (`__setSeed(n)` sets state `(n>>>0)||1` — identical to `engine/rng.js`), and exposes `runFight(...)`. Adapt it minimally so `parity_capture.mjs` can drive fights snapshot-by-snapshot: export a function that (a) constructs `BattleSimulation` with a 900×600 canvas stub, (b) stubs `fetch` so `/api/ref/combat-unit/<civ>/<slug>` resolves from `combat_dicts.json`, (c) calls `__setSeed(seed)`, then `await sim.setupTeam(1, slug1, civ1, n1, "Imperial", {})` and `await sim.setupTeam(2, …)`, (d) loops `sim.update(1/60)` up to 600 s recording snapshots. Do NOT set any of its env transform knobs (`RAMP`/`PACK`/`RTRUE` etc. must stay at production defaults — with no transforms this harness is production behavior).

- [ ] **Step 5: Write the capture tool**

```js
// tools/simjs/parity_capture.mjs
// Captures golden/panel.json from the UNMODIFIED simulate.js via legacy_harness.cjs.
// Refuses to run if simulate.js differs from git HEAD.
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
try {
    execSync("git diff --quiet apps/website/static/js/simulate.js");
} catch {
    console.error("simulate.js is dirty — capture must run against HEAD");
    process.exit(1);
}

const harness = require("./legacy_harness.cjs");
const spec = JSON.parse(readFileSync("tools/simjs/golden/panel_spec.json", "utf8"));
const dicts = JSON.parse(readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"));
const SEEDS = [1, 2, 3, 4, 5];
const results = [];
for (const row of spec) {
    for (const seed of SEEDS) {
        const r = await harness.runFightCaptured(dicts, row, seed, 600);
        // r = { snapshots: [{tick, units:[[team,idx,x,y,hp,state],…]},…],
        //       final: {winner, time, alive1, alive2, hp1, hp2} }
        results.push({ ...row, seed, ...r });
        console.log(`${row.id} seed ${seed}: winner=${r.final.winner} t=${r.final.time.toFixed(1)}`);
    }
}
writeFileSync("tools/simjs/golden/panel.json", JSON.stringify(results));
console.log(`captured ${results.length} fights`);
```

Snapshot cadence: tick 0 (immediately after both `setupTeam` calls, before any `update`), then after every 60th `update` call, plus one final snapshot when the fight ends. `state` is the unit's state string. Units in team order (all team-1 in array order, then all team-2), dead units included.

- [ ] **Step 6: Run the capture**

Run: `node tools/simjs/parity_capture.mjs`
Expected: ~140 lines of fight results, then `captured 140 fights`. Sanity: `slinger-v-elephant` should end with elephants alive at high HP; long stalemate rows hitting `t=600.0` are EXPECTED (the known residue-kiter gap) and are valid golden data. If the harness errors on load-order or a missing stub, fix `legacy_harness.cjs` — never edit `simulate.js`.

- [ ] **Step 7: Commit (golden included)**

```bash
git add tools/simjs/
git commit -m "test(parity): golden panel captured from unmodified simulate.js (~140 fights)"
```

---

### Task 3: Extract constants, Projectile, MeleeEffect

**Files:**
- Create: `apps/website/static/js/engine/constants.js`
- Create: `apps/website/static/js/engine/projectile.js`
- Create: `apps/website/static/js/engine/melee_effect.js`
- Read (source of the code to copy): `apps/website/static/js/simulate.js`
- Test: `tests/js/engine/projectile.test.mjs`

`simulate.js` is NOT modified in this task — the classes are copied out now and deleted from `simulate.js` at cutover (Task 8). The parity gate (Task 7) proves the copies are faithful.

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `constants.js`: `export const CANVAS_WIDTH = 900, CANVAS_HEIGHT = 600, TILE_SIZE = 30, MELEE_RANGE_BUFFER = 5;` plus `export const RELIC_MAX = 4;`, `export const RELIC_BONUS_UNITS = new Set(["paladin", "elite_leitis_lithuanians"]);`, `export const KILL_BONUS_MAX = 4;`, `export const KILL_BONUS_UNITS = new Set(["elite_jaguar_warrior_aztecs", "elite_tiger_cavalry_wei"]);` (values copied verbatim from `simulate.js` lines 17–19, 54, 73–82).
  - `projectile.js`: `export function classifyProjectile(slug, unitName)` (copied from `simulate.js:567`) and `export class Projectile` — constructor `(startX, startY, targetX, targetY, speed, team, kind, onHit)` and `update(dt)` copied verbatim from `simulate.js:582–631`. NO render methods (`_renderBall`, `render` stay behind for Task 6).
  - `melee_effect.js`: `export class MeleeEffect` — constructor `(x, y, team, splashRadius)` and `update(dt)` copied verbatim from `simulate.js:778–792`. NO `render`.

- [ ] **Step 1: Write the failing test**

```js
// tests/js/engine/projectile.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { Projectile, classifyProjectile } from "../../../apps/website/static/js/engine/projectile.js";
import { MeleeEffect } from "../../../apps/website/static/js/engine/melee_effect.js";
import { TILE_SIZE } from "../../../apps/website/static/js/engine/constants.js";

test("projectile flies toward target and fires onHit exactly once on arrival", () => {
    let hits = 0;
    const p = new Projectile(0, 0, 300, 0, 7 * TILE_SIZE, 1, "arrow", () => hits++);
    let ticks = 0;
    while (!p.done && ticks++ < 600) p.update(1 / 60);
    assert.equal(p.done, true);
    assert.equal(p.x, 300);
    assert.equal(hits, 1);
    p.update(1 / 60); // done projectiles are inert
    assert.equal(hits, 1);
});

test("non-string truthy kind maps to legacy siege stone", () => {
    const p = new Projectile(0, 0, 1, 1, 100, 1, 1, null);
    assert.equal(p.kind, "stone");
});

test("melee effect expires after its lifetime", () => {
    const e = new MeleeEffect(10, 10, 1, 0);
    for (let i = 0; i < 13; i++) e.update(1 / 60); // 0.216s > 0.2s lifetime
    assert.equal(e.done, true);
});

test("classifyProjectile is a pure string mapping", () => {
    assert.equal(typeof classifyProjectile("arbalester", "Arbalester"), "string");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/`
Expected: FAIL — cannot find module `projectile.js`

- [ ] **Step 3: Create the three modules by copying from simulate.js**

Copy the exact code at the line ranges listed in Interfaces. Add `import { TILE_SIZE } from "./constants.js";` where the copied code references `TILE_SIZE` (Projectile's speed fallback `7 * TILE_SIZE`). Keep every comment. Do not reformat, rename, or "improve".

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/js/engine/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/engine/ tests/js/engine/projectile.test.mjs
git commit -m "feat(engine): extract constants, Projectile, MeleeEffect (logic only, render stays)"
```

---

### Task 4: Extract BattleUnit

The big mechanical move: `class BattleUnit` spans `simulate.js:834–2316`; its `render(ctx)` method (starting `simulate.js:2175`) and any helpers used only by render do NOT move.

**Files:**
- Create: `apps/website/static/js/engine/battle_unit.js`
- Read: `apps/website/static/js/simulate.js` (lines 834–2316; also 67, 535–580 for context)
- Test: `tests/js/engine/battle_unit.test.mjs`

**Interfaces:**
- Consumes: `Projectile`, `classifyProjectile` from `./projectile.js`; `MeleeEffect` from `./melee_effect.js`; `TILE_SIZE`, `MELEE_RANGE_BUFFER` from `./constants.js`.
- Produces:
  - `export class BattleUnit` — constructor `(id, team, stats, slug = "", civName = "", sim = null)`; sets `this.sim = sim`. All other fields exactly as today (`update(dt, allUnits, enemies)`, `takeDamage(damage, attacker)`, `distanceTo(other)`, `applyDismount()`, `getDamageAgainst(...)`, states `"idle"|"moving"|"attacking"|"kiting"|"committed"|"dead"`, `this.radius = Math.round(10 + Math.min(outlineSize, 1.0) * 20)`, …).
  - `export function setArmorClassNames(map)` — replaces the page-global `armorClassNames` lookup.
  - Later tasks rely on: `unit.x/y/currentHp/maxHp/state/target/attackRange/radius/team/slug/civName`, `unit.sim`, and that units push into `this.sim.projectiles` / `this.sim.effects`.

- [ ] **Step 1: Write the failing test**

```js
// tests/js/engine/battle_unit.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit, setArmorClassNames } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 90, unit_name: "Test Archer",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("derived stats match the legacy formulas", () => {
    const u = new BattleUnit("1-0", 1, STATS, "test", "Franks", simStub());
    assert.equal(u.attackRange, 5 * 30 + 5);      // tiles*TILE_SIZE + MELEE_RANGE_BUFFER
    assert.equal(u.radius, 14);                   // round(10 + 0.2*20)
    assert.equal(u.reloadTime, 2.0);              // 1/attack_speed
    assert.equal(u.moveSpeed, 0.96 * 30);
    assert.equal(u.accuracy, 0.9);
    assert.equal(u.state, "idle");
});

test("fireProjectile pushes into this.sim.projectiles and draws from sim.rng", () => {
    const sim = simStub(3);
    const a = new BattleUnit("1-0", 1, STATS, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    const before = sim.rng.getState();
    a.fireProjectile(b);
    assert.equal(sim.projectiles.length, 1);
    assert.notEqual(sim.rng.getState(), before); // accuracy 0.9 < 1 must roll
});

test("setArmorClassNames feeds the damage-breakdown labels", () => {
    setArmorClassNames({ 4: "Base Melee" });
    // No assertion beyond not throwing: labels are display-only.
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/engine/battle_unit.test.mjs`
Expected: FAIL — cannot find module `battle_unit.js`

- [ ] **Step 3: Copy the class and apply EXACTLY these transformations**

Copy `simulate.js:834` (`class BattleUnit {`) through the end of the class at line 2316, then:

1. **Cut the render section**: delete the `render(ctx)` method (begins `simulate.js:2175`) and any method used ONLY by render (inspect each method between 2000–2316; keep `applyDismount` and any method touched by `update`/damage paths). Save the deleted text to a scratch file — Task 6 needs it verbatim.
2. **Header**: `import { TILE_SIZE, MELEE_RANGE_BUFFER } from "./constants.js";`, `import { Projectile, classifyProjectile } from "./projectile.js";`, `import { MeleeEffect } from "./melee_effect.js";`, and prepend `export` to the class.
3. **Constructor**: signature becomes `(id, team, stats, slug = "", civName = "", sim = null)`; add `this.sim = sim;` as the first body line.
4. **Global-singleton references**: replace every `simulation.` with `this.sim.` — there are ~15 (lines 1276, 1484, 1558–1559, 1599–1600, 1625, 1643–1644, 1676–1677, 1709, 1755, 1852–1853, 1876–1877, 1901–1902, 1933 in the original numbering). Inside `fireProjectile`, the onHit closure aliases `const attacker = this;` — closure references become `attacker.sim.`. After the replacement, `grep -c "simulation\." engine/battle_unit.js` must print 0 (the render-only use at 2212 left with the render cut).
5. **RNG**: replace the 3 `Math.random()` calls (accuracy roll at original line 1516, miss scatter at 1552–1553) with `this.sim.rng.next()` — inside the fireProjectile body they are pre-closure, so `this.` is correct there; verify each site's `this` binding before choosing `this.sim` vs `attacker.sim`.
6. **armorClassNames**: add at module top `let armorClassNames = {};` and `export function setArmorClassNames(map) { armorClassNames = map || {}; }` — the two lookup sites (original 1089, 1100) then work unchanged.
7. Nothing else changes. Every formula, constant, comment, and ordering stays byte-identical.

- [ ] **Step 4: Run tests + purity greps**

Run: `node --test tests/js/engine/` and
`grep -n "Math\.random\|document\.\|window\.\|simulation\." apps/website/static/js/engine/battle_unit.js`
Expected: tests PASS; grep prints nothing.

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/engine/battle_unit.js tests/js/engine/battle_unit.test.mjs
git commit -m "feat(engine): extract BattleUnit — sim back-reference, seeded rng, injectable armor-class names"
```

---

### Task 5: Simulation core + scenario + public API

**Files:**
- Create: `apps/website/static/js/engine/sim.js`
- Create: `apps/website/static/js/engine/scenario.js`
- Create: `apps/website/static/js/engine/index.js`
- Read: `apps/website/static/js/simulate.js` (lines 2376–2470 `setupTeam`, 2535–2654 `update`/`resolveCollisions`)
- Test: `tests/js/engine/sim.test.mjs`, `tests/js/engine/purity.test.mjs`

**Interfaces:**
- Consumes: `BattleUnit` (Task 4), `makeRng` (Task 1), constants (Task 3).
- Produces:
  - `sim.js`: `export class Simulation` with fields `W, H, team1, team2, projectiles, effects, battleTime, winner (null|0|1|2), rng` and methods:
    - `update(dt)` — copied from `simulate.js:2535–2612` with ONLY these changes: `this.updateStats();` deleted; the three `updateBattleWinner(n)` calls deleted (winner assignment + `this.running = false` stay); `TILE_SIZE` imported.
    - `resolveCollisions(allUnits)` — copied verbatim from `simulate.js:2614–2654` (keep the `CANVAS_WIDTH`/`CANVAS_HEIGHT` clamp constants exactly).
    - `step(dt = 1/60)` — alias calling `this.update(dt)`.
    - `runToEnd(maxSeconds = 600)` — `while (this.winner === null && this.battleTime < maxSeconds - 1e-9) this.update(1/60);` then returns `{ winner: this.winner, time: this.battleTime, alive1, alive2, hp1, hp2 }` (alive = count of non-dead; hp = sum of living `currentHp`).
    - `stateHash()` — FNV-1a 32-bit (offset 0x811c9dc5, prime 0x01000193) over, in order: for each unit of team1 then team2: float64 bits of `x`, `y`, `currentHp` (via one shared `DataView`), then `STATE_IDS[unit.state]`; then `projectiles.length`, `effects.length`, `rng.getState()`, float64 bits of `battleTime`. `const STATE_IDS = { idle: 0, moving: 1, attacking: 2, kiting: 3, committed: 4, dead: 5 };` Returns a uint32.
  - `scenario.js`: `export function createSimulation({ mapW = 900, mapH = 600, teams, seed })` — builds `Simulation`, sets `rng = makeRng(seed)`, then for `teams[0]` (team 1) and `teams[1]` (team 2) replays `setupTeam`'s logic minus DOM/fetch/sprites: relic-delta transform (original 2392–2410 — applies when `relics !== RELIC_MAX && civ === "Lithuanians" && RELIC_BONUS_UNITS.has(slug)`, mutating a **deep copy** of the combat dict, never the caller's), radius/spawn-line math (2413–2435 verbatim; team 1 `startX = 30 + unitRadius`, team 2 `mapW - 30 - unitRadius`), unit construction loop (2437–2454) with jitter `unit.x = startX + (sim.rng.next() - 0.5) * 10;` and the startKills clamp. **Draw order = team-1 units in index order, then team-2 — this must match the legacy capture exactly.**
  - `index.js`: re-exports everything public: `createSimulation`, `Simulation`, `BattleUnit`, `setArmorClassNames`, `Projectile`, `classifyProjectile`, `MeleeEffect`, `makeRng`, and all of `constants.js`.

- [ ] **Step 1: Write the failing tests**

```js
// tests/js/engine/sim.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createSimulation } from "../../../apps/website/static/js/engine/index.js";
import { readFileSync } from "node:fs";

const dicts = JSON.parse(readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"));
const CHAMP = dicts["Franks|champion"];
const JAG = dicts["Aztecs|elite_jaguar_warrior_aztecs"];

function makeSim(seed) {
    return createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: 10 },
            { combatDict: JAG, slug: "elite_jaguar_warrior_aztecs", civ: "Aztecs", count: 10 },
        ],
        seed,
    });
}

test("same seed => identical hash stream for 600 ticks", () => {
    const a = makeSim(11), b = makeSim(11);
    assert.equal(a.stateHash(), b.stateHash()); // spawn state identical
    for (let i = 0; i < 600; i++) {
        a.step(); b.step();
        assert.equal(a.stateHash(), b.stateHash(), `diverged at tick ${i + 1}`);
    }
});

test("different seeds diverge within the fight", () => {
    const a = makeSim(1), b = makeSim(2);
    let diverged = a.stateHash() !== b.stateHash();
    for (let i = 0; i < 3600 && !diverged; i++) {
        a.step(); b.step();
        diverged = a.stateHash() !== b.stateHash();
    }
    assert.ok(diverged);
});

test("runToEnd finishes a melee fight with a winner and consistent survivors", () => {
    const r = makeSim(5).runToEnd(600);
    assert.ok([0, 1, 2].includes(r.winner));
    assert.ok(r.alive1 === 0 || r.alive2 === 0);
    assert.ok(r.time > 0 && r.time <= 600);
});

test("relics delta only applies to Lithuanian relic units", () => {
    const base = createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: 1, relics: 0 },
            { combatDict: JAG, slug: "elite_jaguar_warrior_aztecs", civ: "Aztecs", count: 1 },
        ],
        seed: 1,
    });
    assert.equal(base.team1[0].attack, CHAMP.attack); // non-Lithuanian: untouched
});
```

```js
// tests/js/engine/purity.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const DIR = "apps/website/static/js/engine";
const BANNED = /Math\.random|document\.|window\.|getElementById|requestAnimationFrame|performance\.now|new Image|fetch\(|alert\(/;

test("engine sources are DOM-free and Math.random-free", () => {
    for (const f of readdirSync(DIR).filter((f) => f.endsWith(".js"))) {
        const src = readFileSync(`${DIR}/${f}`, "utf8");
        const hit = src.match(BANNED);
        assert.equal(hit, null, `${f} contains banned token: ${hit && hit[0]}`);
    }
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/engine/`
Expected: sim.test.mjs FAILS (no `sim.js`); purity test may already pass — fine.

- [ ] **Step 3: Implement `sim.js`, `scenario.js`, `index.js` per the Interfaces block**

The `update`/`resolveCollisions` bodies are COPIES from the listed line ranges; only the listed deletions are allowed. `stateHash` reference implementation:

```js
const STATE_IDS = { idle: 0, moving: 1, attacking: 2, kiting: 3, committed: 4, dead: 5 };
const _hbuf = new DataView(new ArrayBuffer(8));
function fnv(h, u32) {
    h ^= u32 & 0xff;          h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 8) & 0xff;  h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 16) & 0xff; h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 24) & 0xff; h = Math.imul(h, 0x01000193);
    return h >>> 0;
}
function fnvF64(h, v) {
    _hbuf.setFloat64(0, v);
    return fnv(fnv(h, _hbuf.getUint32(0)), _hbuf.getUint32(4));
}
// in class Simulation:
stateHash() {
    let h = 0x811c9dc5;
    for (const u of [...this.team1, ...this.team2]) {
        h = fnvF64(h, u.x); h = fnvF64(h, u.y); h = fnvF64(h, u.currentHp);
        h = fnv(h, STATE_IDS[u.state] ?? 255);
    }
    h = fnv(h, this.projectiles.length);
    h = fnv(h, this.effects.length);
    h = fnv(h, this.rng.getState());
    return fnvF64(h, this.battleTime);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/engine/`
Expected: PASS (all files)

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/engine/ tests/js/engine/
git commit -m "feat(engine): Simulation core, scenario builder, public API, purity + determinism tests"
```

---

### Task 6: Browser renderer module

**Files:**
- Create: `apps/website/static/js/sim_renderer.js`
- Read: `apps/website/static/js/simulate.js` (lines 21–53 palette, 115–122 asset maps, `Projectile._renderBall`/`render` 636–777, `MeleeEffect.render` 794–831, `BattleUnit.render` 2175–2316, `BattleSimulation` render/drawGrid/drawWinner 2656–2740 and `resizeBackingStore` 2359–2374) — plus the render-only helper methods cut in Task 4 (the scratch file).

**Interfaces:**
- Consumes: engine classes' public state (`sim.team1/team2/projectiles/effects/battleTime/winner`, unit fields); `TILE_SIZE`, `CANVAS_WIDTH`, `CANVAS_HEIGHT` from `engine/constants.js`.
- Produces: `export class SimRenderer` —
  - `constructor(canvas)`: stores canvas/ctx, copies the `CANVAS_PAL` + `refreshCanvasPalette` + MutationObserver logic (original lines 21–53), the DPR backing-store logic + ResizeObserver (original 2342–2374).
  - `setTeamAssets(team, { img, isSprite, sheet })`: replaces the legacy per-unit `spriteImg/isSprite/attackSheet` stamping — the draw path reads assets from `this.assets[unit.team]`.
  - `render(sim)`: the original `BattleSimulation.render` body (2656–2679) with `this.*` sim reads becoming `sim.*`, delegating to module-local `drawUnit(ctx, unit, assets, sim, pal)`, `drawProjectile(ctx, p)`, `drawEffect(ctx, e)`, `drawGrid`, `drawWinner` — each the verbatim body of the corresponding legacy `render` method with `this.` rewritten to its parameter (e.g. `this.x` → `unit.x`, `simulation.battleTime` → `sim.battleTime` at original line 2212).

- [ ] **Step 1: Assemble the module** from the listed sources. This file is browser-only (it MAY use `document`/`window` — it lives outside `engine/`). Keep every drawing formula and color verbatim.

- [ ] **Step 2: Syntax-check**

Run: `node --check apps/website/static/js/sim_renderer.js`
Expected: no output (exit 0). (Behavioral verification is the Task 8 UI smoke — canvas code has no headless test.)

- [ ] **Step 3: Purity check still green**

Run: `node --test tests/js/engine/`
Expected: PASS — proves no render code leaked back into `engine/`.

- [ ] **Step 4: Commit**

```bash
git add apps/website/static/js/sim_renderer.js
git commit -m "feat(sim): browser-only SimRenderer — all canvas drawing extracted from engine classes"
```

---

### Task 7: Headless runner + THE parity gate

**Files:**
- Create: `tools/simjs/headless.mjs`
- Create: `tools/simjs/parity_check.mjs`

**Interfaces:**
- Consumes: `engine/index.js` (Task 5), `golden/panel.json` + `golden/combat_dicts.json` + `golden/panel_spec.json` (Task 2).
- Produces: `headless.mjs` exports `runFight({ dicts, row, seed, maxSeconds })` → `{ snapshots, final }` in EXACTLY the golden capture's shape (same cadence: tick 0 post-spawn, every 60th tick, final; same unit tuple `[team, idx, x, y, hp, state]`). `parity_check.mjs` is a CLI: exit 0 = bit-exact, exit 1 with a first-divergence report.

- [ ] **Step 1: Write `headless.mjs`**

```js
// tools/simjs/headless.mjs
import { createSimulation } from "../../apps/website/static/js/engine/index.js";

export function runFight({ dicts, row, seed, maxSeconds = 600 }) {
    const sim = createSimulation({
        teams: [
            { combatDict: dicts[`${row.civ1}|${row.slug1}`], slug: row.slug1, civ: row.civ1, count: row.n1 },
            { combatDict: dicts[`${row.civ2}|${row.slug2}`], slug: row.slug2, civ: row.civ2, count: row.n2 },
        ],
        seed,
    });
    const snap = (tick) => ({
        tick,
        units: [...sim.team1.map((u, i) => [1, i, u.x, u.y, u.currentHp, u.state]),
                ...sim.team2.map((u, i) => [2, i, u.x, u.y, u.currentHp, u.state])],
    });
    const snapshots = [snap(0)];
    let tick = 0;
    while (sim.winner === null && sim.battleTime < maxSeconds - 1e-9) {
        sim.step();
        tick++;
        if (tick % 60 === 0) snapshots.push(snap(tick));
    }
    if (tick % 60 !== 0) snapshots.push(snap(tick));
    const alive1 = sim.team1.filter((u) => u.state !== "dead");
    const alive2 = sim.team2.filter((u) => u.state !== "dead");
    return {
        snapshots,
        final: {
            winner: sim.winner, time: sim.battleTime,
            alive1: alive1.length, alive2: alive2.length,
            hp1: alive1.reduce((s, u) => s + u.currentHp, 0),
            hp2: alive2.reduce((s, u) => s + u.currentHp, 0),
        },
    };
}
```

NOTE: match the legacy capture's exact snapshot/final semantics from Task 2 (winner encoding, end-of-fight cadence). If Task 2 recorded them differently in any detail, mirror Task 2 — the golden defines the format.

- [ ] **Step 2: Write `parity_check.mjs`**

```js
// tools/simjs/parity_check.mjs
import { readFileSync } from "node:fs";
import { runFight } from "./headless.mjs";

const golden = JSON.parse(readFileSync("tools/simjs/golden/panel.json", "utf8"));
const dicts = JSON.parse(readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"));
let checked = 0;
for (const g of golden) {
    const r = runFight({ dicts, row: g, seed: g.seed, maxSeconds: 600 });
    const a = JSON.stringify({ snapshots: r.snapshots, final: r.final });
    const b = JSON.stringify({ snapshots: g.snapshots, final: g.final });
    if (a !== b) {
        // locate first divergent snapshot / unit / field for the report
        for (let s = 0; s < g.snapshots.length; s++) {
            const gs = g.snapshots[s], rs = r.snapshots[s];
            if (JSON.stringify(gs) === JSON.stringify(rs)) continue;
            for (let u = 0; u < gs.units.length; u++) {
                if (JSON.stringify(gs.units[u]) !== JSON.stringify(rs?.units?.[u])) {
                    console.error(`DIVERGED: ${g.id} seed ${g.seed} tick ${gs.tick} unit ${u}`);
                    console.error(`  golden: ${JSON.stringify(gs.units[u])}`);
                    console.error(`  engine: ${JSON.stringify(rs?.units?.[u])}`);
                    process.exit(1);
                }
            }
            console.error(`DIVERGED: ${g.id} seed ${g.seed} tick ${gs.tick} (snapshot shape)`);
            process.exit(1);
        }
        console.error(`DIVERGED: ${g.id} seed ${g.seed} (final block only)`);
        process.exit(1);
    }
    checked++;
}
console.log(`PARITY OK — ${checked} fights bit-exact`);
```

- [ ] **Step 3: Run the gate; fix the engine until bit-exact**

Run: `node tools/simjs/parity_check.mjs`
Expected eventually: `PARITY OK — ~140 fights bit-exact`.

Every mismatch is an extraction bug. Debug method: the report gives matchup/seed/tick; reproduce with `runFight` on that one row, bisect the tick range with `stateHash()` per tick, inspect which unit field moved. Common causes: an rng draw out of order (spawn jitter order!), a `this.sim` vs `attacker.sim` mix-up in closures, a render-only method that actually mutated state, a missed `simulation.` reference. FORBIDDEN fixes: editing `golden/panel.json`, rounding, tolerances, reordering golden data.

- [ ] **Step 4: Commit**

```bash
git add tools/simjs/headless.mjs tools/simjs/parity_check.mjs
git commit -m "test(parity): headless runner + bit-exact parity gate vs golden panel — PASSING"
```

---

### Task 8: Production page cutover

Now — and only now — `simulate.js` changes. The engine classes are deleted from it; the page imports the engine + renderer.

**Files:**
- Modify: `apps/website/static/js/simulate.js` (delete lines 582–2316 class definitions and the tick core inside `BattleSimulation`; rewrite the glue)
- Modify: `apps/website/templates/simulate.html` (line 176: add `type="module"`)
- Modify: `tests/test_frontend_projectile_miss.js` (import instead of brace-extraction)
- Modify: `tests/test_ability_registry.py` (line 61: point the `"js"` source at the engine files)

**Interfaces:**
- Consumes: `createSimulation`, `setArmorClassNames`, `RELIC_MAX`, `RELIC_BONUS_UNITS`, `KILL_BONUS_MAX`, `KILL_BONUS_UNITS`, constants from `./engine/index.js`; `SimRenderer` from `./sim_renderer.js`.
- Produces: the Battle Sim page, behavior-identical. A thin `class PageSim` in `simulate.js` replaces the old `BattleSimulation` surface for the page code: fields `speedMultiplier, running, paused, winner (delegates to engine sim)`; methods `setup(teams)`, `start()`, `pause()`, `reset()`, `render()`.

- [ ] **Step 1: Rewrite `simulate.js`**

1. Template `simulate.html:176` becomes `<script type="module" src="{{ url_for('static', filename='js/simulate.js') }}"></script>`. (`sim_params.js` on line 175 stays a classic script; its `readSimParams` global and the inline `const UNIT_SEARCH` are visible to module code — verify, don't assume: load the page and check the console.)
2. Top of `simulate.js`: `import { createSimulation, setArmorClassNames, RELIC_MAX, RELIC_BONUS_UNITS, KILL_BONUS_MAX, KILL_BONUS_UNITS, CANVAS_WIDTH, CANVAS_HEIGHT, TILE_SIZE } from "./engine/index.js";` and `import { SimRenderer } from "./sim_renderer.js";` — then delete the now-imported constant declarations (17–19, 54, 73–82) and the palette block (21–53, lives in SimRenderer).
3. Delete `class Projectile`, `class MeleeEffect`, `class BattleUnit`, `class BattleSimulation` bodies entirely. Keep ALL selection-UI code (lines ~93–535), `classifyProjectile` callers (none outside the engine now), `startBattle`, the count-mode logic, deep-link handling — those are page concerns and stay.
4. Write `PageSim` (replaces `BattleSimulation` for the page):

```js
class PageSim {
    constructor(canvas) {
        this.renderer = new SimRenderer(canvas);
        this.sim = null;
        this.speedMultiplier = 3.0;
        this.running = false;
        this.paused = false;
        this.lastTimestamp = 0;
    }
    get winner() { return this.sim ? this.sim.winner : null; }
    setup({ teams, seed }) {
        this.sim = createSimulation({ mapW: CANVAS_WIDTH, mapH: CANVAS_HEIGHT, teams, seed });
    }
    start() {
        if (!this.sim) { alert("Please configure both teams"); return; }
        this.running = true;
        this.paused = false;
        this.lastTimestamp = performance.now();
        updateStats(this.sim);
        updateDebugPanel(this.sim);
        this.loop();
    }
    pause() {
        this.paused = !this.paused;
        if (!this.paused) { this.lastTimestamp = performance.now(); this.loop(); }
    }
    reset() {
        this.sim = null;
        this.running = false;
        this.paused = false;
        updateStats(null);
        this.render();
        document.getElementById("debugContent").innerHTML =
            '<p style="color:var(--text-muted)">Start a battle to see combat stats</p>';
    }
    loop() {
        if (!this.running || this.paused) return;
        const now = performance.now();
        let remaining = Math.min(((now - this.lastTimestamp) / 1000) * this.speedMultiplier, 0.25);
        this.lastTimestamp = now;
        const STEP = 1 / 60;
        while (remaining > 1e-6 && this.sim.winner === null) {
            this.sim.step(Math.min(remaining, STEP));
            remaining -= Math.min(remaining, STEP);
        }
        updateStats(this.sim);           // was per-sub-step; per-frame is visually identical
        this.render();
        if (this.sim.winner !== null) {
            this.running = false;
            updateBattleWinner(this.sim.winner);
        } else {
            requestAnimationFrame(() => this.loop());
        }
    }
    render() { if (this.sim) this.renderer.render(this.sim); else this.renderer.renderEmpty(); }
}
```

`updateStats`/`updateDebugPanel` become free functions taking the sim (their DOM bodies move out of the old class unchanged; they read `sim.team1/team2` and unit methods like `getDamageAgainst`). `SimRenderer.renderEmpty()` draws bg + grid only (add it to sim_renderer.js — the pre-battle frame).

5. `startBattle` changes: it already fetches combat-unit stats for the count modes; extend that to always fetch both dicts once, apply nothing (relics/startKills go into the scenario team entries — the engine handles the delta), preload sprites into the renderer via `pageSim.renderer.setTeamAssets(1, …)` / `(2, …)` (reusing the existing `unitImages`/`unitIsSprite`/`unitSheets` preload code), then `pageSim.setup({ teams, seed })` with `const seed = (Math.random() * 2 ** 32) >>> 0;` (page-side seeding is allowed; log it: `console.log("battle seed:", seed)`), then the existing stats-panel code, `setSimPhase(true)`, `pageSim.start()`.
6. The `/api/armor-classes` fetch (original 3063–3064) now calls `setArmorClassNames(await resp.json())`.
7. Global exposure for any stragglers: end of module — `window.simulation = pageSim;` if anything else (e.g. inline template code) references it; grep templates first.

- [ ] **Step 2: Repoint the two coupled tests**

`tests/test_frontend_projectile_miss.js`: delete the brace-extraction + `eval` block (lines ~15–68); replace with:

```js
const assert = require("assert");
async function main() {
    const { BattleUnit } = await import(
        "../apps/website/static/js/engine/battle_unit.js"
    );
    const { makeRng } = await import("../apps/website/static/js/engine/rng.js");
    // … existing test bodies, constructing units as
    // new BattleUnit(id, team, stats, "", "", simStub())
    // where simStub() = { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(1) };
}
main().then(() => console.log("ok"), (e) => { console.error(e); process.exit(1); });
```

Keep every existing assertion; the mocked-globals section shrinks to just the sim stub (TILE_SIZE etc. now come from the real engine imports). Update the file's header comment.

`tests/test_ability_registry.py:61`: replace the single-file read with a concatenation of the engine sources:

```python
"js": "\n".join(
    (ROOT / "apps" / "website" / "static" / "js" / "engine" / f).read_text(encoding="utf-8")
    for f in ("battle_unit.js", "sim.js", "scenario.js", "projectile.js", "melee_effect.js")
),
```

Also update the docstring at line ~19 that names `simulate.js`.

- [ ] **Step 3: Verify everything**

Run, in order:
1. `node --test tests/js/engine/` → PASS
2. `node tools/simjs/parity_check.mjs` → `PARITY OK` (engine untouched by this task — confirms it)
3. `node tests/test_frontend_projectile_miss.js` → `ok`
4. `pytest tests/test_ability_registry.py -q` → PASS
5. `pytest -q` → same pass/skip counts as before this plan (350 passed, 13 skipped at branch point)

- [ ] **Step 4: UI smoke via the browser preview**

Start the dev server (preview tool, launch config, or `PORT=5002 python apps/website/app.py`), open `/`, and verify: unit pickers populate; a Frank Paladin vs Goth Huskarl battle runs and animates with sprites; pause/resume/reset work; speed slider works; relic picker appears for Lithuanian Leitis; the damage debug panel fills in; deep-link `/?civ1=Franks&unit1=paladin&civ2=Goths&unit2=elite_huskarl_goths&autorun=1` starts a fight; browser console shows zero errors. Screenshot the mid-battle canvas as proof.

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/js/simulate.js apps/website/templates/simulate.html tests/test_frontend_projectile_miss.js tests/test_ability_registry.py apps/website/static/js/sim_renderer.js
git commit -m "feat(sim)!: Battle Sim page cut over to the shared engine module — legacy classes deleted from simulate.js"
```

---

### Task 9: Standalone diagnostic harness

**Files:**
- Create: `apps/website/static/lab/sim_harness.html`
- Create: `apps/website/static/lab/sim_harness.js`
- Create: `apps/website/static/lab/sim_worker.js`
- Modify: `apps/website/static/js/engine/sim.js` + `battle_unit.js` (combat counters — additive bookkeeping ONLY)

**Interfaces:**
- Consumes: `engine/index.js`, `sim_renderer.js`, `/api/ref/civ/<civ>` (unit lists: `units_by_age.Imperial`, entries `{unit_slug, unit_name}`), `/api/ref/combat-unit/<civ>/<slug>?age=Imperial`, `window.ENABLED_CIVS` from `/static/js/constants.js`.
- Produces: the harness page at `/static/lab/sim_harness.html` (Flask serves it; `app.py` already binds `0.0.0.0`, so it is reachable over Tailscale at `http://<tailnet-ip>:5002/static/lab/sim_harness.html`). Engine gains `sim.combatStats = { 1: { swings: 0, hitsLanded: 0, damageDealt: 0 }, 2: { … } }`.

- [ ] **Step 1: Add engine combat counters (bookkeeping only, parity-gated)**

In `sim.js` constructor: initialize `this.combatStats` as above. In `battle_unit.js`: increment `swings` where an attack/projectile is launched (`performAttackOn` entry, `fireProjectile` entry), and in `takeDamage(damage, attacker)` increment `attacker.sim.combatStats[attacker.team].hitsLanded` and add the ACTUAL applied damage to `damageDealt` (guard `attacker && attacker.sim`). Counters must not touch rng, positions, HP math, or ordering. `stateHash()` does NOT include them.

Run: `node tools/simjs/parity_check.mjs`
Expected: `PARITY OK` — this run is the proof the counters are behavior-neutral. If it diverges, the counter placement mutated state — fix it.

- [ ] **Step 2: Build the page**

`sim_harness.html`: dark minimal page, no site chrome. Loads `<script src="/static/js/constants.js"></script>` (classic, for `ENABLED_CIVS`) then `<script type="module" src="/static/lab/sim_harness.js"></script>`. Layout: left control rail, 900×600 canvas center, right/below results area.

`sim_harness.js` implements, importing from `/static/js/engine/index.js` and `/static/js/sim_renderer.js` (absolute paths — the page lives under `/static/lab/`):

1. **Pickers**: two `<select>`s from `ENABLED_CIVS`; on civ change fetch `/api/ref/civ/<civ>`, fill unit `<select>` from `units_by_age.Imperial`. Count inputs with a mode radio per team pair:
   - `explicit` — use the numbers typed.
   - `ui-rule` — `Math.max(1, Math.floor(budget / ((cd.cost_wood||0)+(cd.cost_food||0)+(cd.cost_gold||0))))`, budget input default 3000.
   - `corpus-rule` — weighted cost `food*1.0 + wood*1.0 + gold*1.5`, divided by `TRAIN_BATCH[slug] || 1` where `const TRAIN_BATCH = { blackwood_archer_tupi: 2, elite_blackwood_archer_tupi: 2 };` budget 3000, cap 21: cheaper side `min(21, floor(3000/cost))`; pricier side scaled to equal spend (`floor(cheapCount * cheapCost / dearCost)`, min 1).
2. **Presets** `<select>` — a `PRESETS` array in the file with at least the six doc problem fights: Slinger 21 v Bengalis Elite Battle Elephant 6, Slinger 21 v Huns Paladin 7, Slinger 21 v Bulgarians Hussar 15, Slinger 50 v Byzantines Elite Cataphract 20, Britons Arbalester 20 v Chinese Elite Chu Ko Nu 15, Berbers Camel Archer 18 v Franks Knight 18. Selecting one fills civs/units/counts/mode.
3. **Seed + time**: numeric seed input, Randomize button (`(Math.random()*2**32)>>>0`), Run button (builds scenario exactly like the Battle Sim page: fetch dicts → `createSimulation`), Pause/Resume, Step (one `sim.step()` then render), speed select `0.25/0.5/1/2/4/8` feeding the same clamped rAF loop as `PageSim.loop`.
4. **Overlays** — checkboxes, drawn AFTER `renderer.render(sim)` each frame on the same canvas:
   - *State colors*: ring per unit, `{idle:"#888", moving:"#4aa3ff", attacking:"#ff4a4a", kiting:"#ffd14a", committed:"#ff9900", dead:"#333"}`.
   - *Target lines*: `ctx.strokeStyle` team color, line from `(u.x,u.y)` to `(u.target.x, u.target.y)` for living units with a target.
   - *Range rings*: circle radius `u.attackRange` for ranged units (`u.rawAttackRange > 0`), 0.15 alpha.
   - *Stats readout* (HTML, not canvas): per side — alive count, HP sum, `swings`, `hitsLanded`, `damageDealt`, live DPS (damageDealt delta over the last 5 s of battleTime, ring buffer), and **free-fire timer**: battleTime at the first tick where the melee side's (`rawAttackRange === 0`) `damageDealt` became > 0; shows "∞" until then. Fight clock `sim.battleTime.toFixed(1)`.
5. **Multi-seed scoreboard**: N-seeds input (default 10) + Run-N button → `new Worker("/static/lab/sim_worker.js", { type: "module" })`, posts `{ dicts, teams, seeds }`; worker replies per-seed. Table rows: seed | winner | time | alive1 | hp1% | alive2 | hp2% ; footer: win-rate per side, mean time, mean survivors, mean HP%. HP% = living HP sum / (count × maxHp of the unit).

`sim_worker.js`:

```js
// apps/website/static/lab/sim_worker.js
import { createSimulation } from "/static/js/engine/index.js";
onmessage = (e) => {
    const { teams, seeds } = e.data;
    for (const seed of seeds) {
        const sim = createSimulation({ teams, seed });
        const r = sim.runToEnd(600);
        postMessage({ seed, ...r });
    }
    postMessage({ done: true });
};
```

- [ ] **Step 3: Verify in the browser preview**

Open `/static/lab/sim_harness.html` on the dev server: load the Slinger-v-Elephant preset, Run — the fight renders with overlays toggling live; Step advances exactly one tick when paused; same seed twice → identical scoreboard rows (check two runs of seed 1); Run-10 fills the table while the page stays responsive; the known signature appears (elephants win with most units alive; some seeds hit t=600 with residue Slingers — that's the documented gap, not a harness bug). Console error-free. Screenshot the overlays mid-fight.

- [ ] **Step 4: Full test sweep**

Run: `node --test tests/js/engine/` ; `node tools/simjs/parity_check.mjs` ; `pytest -q`
Expected: all green / `PARITY OK` / unchanged counts.

- [ ] **Step 5: Commit**

```bash
git add apps/website/static/lab/ apps/website/static/js/engine/
git commit -m "feat(lab): standalone sim harness — presets, seed control, overlays, worker scoreboard"
```

---

### Task 10: Documentation + final verification

**Files:**
- Modify: `CLAUDE.md` (three-engines table + cross-file sync rule 1)
- Modify: `docs/architecture/README.md` (system map: engine module + harness + tools/simjs)
- Modify: `docs/architecture/runbooks.md` (§3 new-combat-column checklist: the JS handler now lives in `engine/battle_unit.js`, tests in `tests/js/engine/`)
- Modify: `docs/simulation-engine-migration.md` (top: link this plan + spec as "sub-project 1, implemented")

**Interfaces:**
- Consumes: everything built above.
- Produces: docs that match reality; a session-end verification record.

- [ ] **Step 1: Update the docs**

In `CLAUDE.md`: the engine table row `Frontend canvas (BattleUnit) | apps/website/static/js/simulate.js` becomes `Frontend canvas (shared engine) | apps/website/static/js/engine/ (page shell: simulate.js, renderer: sim_renderer.js)`; in Cross-File Sync Rules 1, replace `static/js/simulate.js` with `static/js/engine/battle_unit.js` as the JS handler location and note the parity gate `tools/simjs/parity_check.mjs`. Keep edits surgical — these files are read by every future session.

In `docs/architecture/README.md` and `runbooks.md`: mirror the same path changes; add `tools/simjs/` (golden panel, capture/check) and `/static/lab/sim_harness.html` to the system map with one-line descriptions.

In `docs/simulation-engine-migration.md`: under the title add: `> Sub-project 1 (engine extraction + harness) implemented — see docs/superpowers/specs/2026-07-28-js-engine-extraction-design.md and docs/superpowers/plans/2026-07-28-js-engine-extraction.md.`

- [ ] **Step 2: Final full verification**

Run, in order, expect all green:
1. `node --test tests/js/engine/`
2. `node tools/simjs/parity_check.mjs` → `PARITY OK`
3. `node tests/test_frontend_projectile_miss.js` → `ok`
4. `pytest -q` → 350 passed, 13 skipped (as at branch point)
5. Battle Sim page + harness page both load and run in the preview, console clean.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: record the shared JS engine layout, parity gate, and harness"
```

**Do not push.** Report completion to the user with the verification outputs; the user decides when anything leaves the machine.

---

### Task 11: Cross-engine comparison — JS engine vs Python `simulation_real.py`

Read-only experiment (no engine or data changes): a 10-per-side round-robin over a representative unit roster, run through BOTH engines, to see where the two land relative to each other. This is analysis, not a gate — divergence is EXPECTED (the migration doc §6 documents six behavioral differences); the deliverable is the map of where and how big.

**Files:**
- Create: `lab/cross_engine/roster.json`
- Create: `lab/cross_engine/run_js.mjs`
- Create: `lab/cross_engine/run_py.py`
- Create: `lab/cross_engine/compare.py`
- Create: `lab/cross_engine/REPORT.md` (generated, committed)

**Interfaces:**
- Consumes: `tools/simjs/headless.mjs` (Task 7), `tools/simjs/dump_combat_dicts.py` pattern (Task 2), `aoe2x/sim/simulation_real.py` + `aoe2x/sim/combat_unit_loader.py` (existing, untouched).
- Produces: `REPORT.md` — per-pair and aggregate comparison tables.

- [ ] **Step 1: Define the roster** — `roster.json`, one entry per unit type class: `champion` (Vikings), `halberdier` (Goths), `arbalester` (Britons), `elite_skirmisher` (Aztecs), `paladin` (Franks), `hussar` (Huns), `heavy_camel_rider` (Saracens), `heavy_cavalry_archer` (Mongols), `elite_battle_elephant` (Bengalis), `onager` (Celts), `heavy_scorpion` (Celts), `hand_cannoneer` (Turks), `elite_huskarl_goths` (Goths), `elite_cataphract_byzantines` (Byzantines), `elite_teutonic_knight_teutons` (Teutons), `elite_mangudai_mongols` (Mongols). Validate every slug against the reference DB (same LIKE-query recovery as Task 2); dump combat dicts for all of them into `lab/cross_engine/combat_dicts.json` (reuse `dump_combat_dicts.py` logic with this roster).
- [ ] **Step 2: JS runs** — `run_js.mjs`: all unordered pairs (16 units → 120 pairs), 10v10, seeds 1–5, `runFight` with `maxSeconds 600`; write `lab/cross_engine/js_results.json` rows `{a, b, seed, winner, time, alive1, alive2, hp1, hp2}`.
- [ ] **Step 3: Python runs** — `run_py.py`: same pairs/counts/seeds through `simulation_real.py` (build units via `combat_unit_loader`, follow the batch scripts' usage — see `aoe2x/batch/run_matchup_battles.py` for the call pattern; CPython is fine at this volume); write `py_results.json` in the same shape.
- [ ] **Step 4: Compare + report** — `compare.py` writes `REPORT.md`: (1) per-pair majority winner (3-of-5 seeds) for each engine + agree/disagree flag; (2) aggregate: winner-agreement %, mean |survivor diff|, mean |HP% diff|, mean fight-time ratio; (3) the 10 worst-diverging pairs with per-seed detail; (4) counts of 600 s timeouts per engine (the JS residue-kiter signature vs the Python kite-stop). No conclusions beyond the numbers — flag, don't fix.
- [ ] **Step 5: Commit**

```bash
git add lab/cross_engine/
git commit -m "lab: cross-engine comparison — JS engine vs simulation_real, 16-unit round-robin 10v10"
```
