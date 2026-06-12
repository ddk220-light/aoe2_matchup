# Engine Viewer (4_lumber slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browser game-engine that re-simulates the 4_lumber scenario from replay commands and verifiably matches the gRPC-captured real game state.

**Architecture:** Pure-ESM JavaScript tick engine (`public/engine.js`, no DOM) consumed by both the canvas viewer and a headless Node verifier; two Python extractors bake `commands.json` (from `.aoe2record` via mgz) and `truth.json` (from the gRPC capture via `decode_state_v2`); a thin Flask server hosts it all on port 5003.

**Tech Stack:** Python 3 (mgz fork + decode_state_v2, both already working in `apps/video/.venv`), ES modules, Node 20 (verifier), Flask, canvas 2D.

**Spec:** `docs/superpowers/specs/2026-06-12-game-simulation-design.md` — tolerances and ground-truth fixtures live there.

**Conventions for all tasks:** venv python = `D:\AI\aoe2_matchup\apps\video\.venv\Scripts\python.exe` (alias `$PY` below). Repo root = `D:\AI\aoe2_matchup`. Commit after every task on branch `game_simulation`.

---

### Task 1: Scaffold

**Files:**
- Create: `apps/engine_viewer/package.json`, `apps/engine_viewer/README.md`, dirs `tools/ data/4_lumber/ public/assets/ verify/`

- [x] **Step 1: package.json** (makes Node treat `public/*.js` as ESM)

```json
{
  "name": "aoe2-engine-viewer",
  "private": true,
  "type": "module",
  "version": "0.1.0"
}
```

- [x] **Step 2: README.md** — quickstart block:

```markdown
# engine_viewer — browser re-simulation of AoE2 replays (4_lumber slice)

Run: `python apps/engine_viewer/server.py` -> http://127.0.0.1:5003/
Verify vs ground truth: `node apps/engine_viewer/verify/verify.mjs`
Rebake data: `tools/extract_commands.py` (replay) / `tools/extract_truth.py` (gRPC capture).
Design: ../../docs/superpowers/specs/2026-06-12-game-simulation-design.md
```

- [x] **Step 3: Commit** `git add apps/engine_viewer && git commit -m "engine_viewer: scaffold"`

### Task 2: extract_commands.py (replay -> commands.json)

**Files:**
- Create: `apps/engine_viewer/tools/extract_commands.py`
- Output: `apps/engine_viewer/data/4_lumber/commands.json`

- [x] **Step 1: Write extractor with built-in self-check.** Parse with `mgz.model.parse_match`; emit scenario JSON. Starting entities come from the replay header (`match.players[].objects` for villagers/TC/scout, `match.gaia` for the tree + nearby prop trees). Self-check asserts the known shape and FAILS loudly if the record doesn't match.

```python
"""rec.aoe2record -> data/4_lumber/commands.json (sim input, replay-pure)."""
import json, math, sys
from pathlib import Path
import mgz.model

REPLAY = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\rec.aoe2record")
OUT = Path(__file__).resolve().parents[1] / "data" / "4_lumber" / "commands.json"
TYPE_BY_NAME = {"Villager": "villager", "Town Center": "town_center", "Scout Cavalry": "scout"}

match = mgz.model.parse_match(open(REPLAY, "rb"))
p1 = match.players[0]
entities, props = [], []
for obj in p1.objects:
    name = str(obj.name)
    t = TYPE_BY_NAME.get(name)
    if t:
        entities.append({"id": obj.instance_id, "type": t, "owner": 1,
                         "x": obj.position.x, "y": obj.position.y})
cmds = []
for a in match.actions:
    ty, pl = str(a.type), (a.payload or {})
    ts = a.timestamp.total_seconds()
    if ty == "Action.ORDER":
        cmds.append({"t": ts, "type": "order", "unit_ids": pl["object_ids"], "target_id": pl["target_id"]})
    elif ty == "Action.GATHER_POINT":
        cmds.append({"t": ts, "type": "gather_point", "building_id": pl["object_ids"][0], "target_id": pl["target_id"]})
    elif ty == "Action.DE_QUEUE" and pl.get("unit_id") == 83:
        cmds.append({"t": ts, "type": "queue", "building_id": pl["object_ids"][0], "unit": "villager", "train_time": 25.0})
    elif ty == "Action.RESIGN":
        cmds.append({"t": ts, "type": "resign", "player": 1})
target_ids = {c.get("target_id") for c in cmds if c.get("target_id")}
tc = next(e for e in entities if e["type"] == "town_center")
for g in match.gaia:  # the ordered tree + nearby backdrop trees
    if "tree" not in str(g.name).lower():
        continue
    d = math.hypot(g.position.x - tc["x"], g.position.y - tc["y"])
    if g.instance_id in target_ids:
        entities.append({"id": g.instance_id, "type": "tree", "owner": 0,
                         "x": g.position.x, "y": g.position.y, "wood": 100.0, "hp": 20.0})
    elif d < 18:
        props.append({"x": g.position.x, "y": g.position.y, "kind": "tree"})
doc = {"scenario": "4_lumber", "map": {"dimension": match.map.dimension},
       "players": [{"id": 1, "name": p1.name, "civ": str(p1.civilization),
                    "start_wood": 150.0, "start_wood_source": "ui_observed"}],
       "duration": match.duration.total_seconds(), "entities": entities,
       "props": props, "commands": cmds}
# ---- self-check (ground-truth shape from the spec) ----
kinds = [c["type"] for c in cmds]
assert kinds == ["order", "gather_point", "queue", "resign"], kinds
assert sorted(cmds[0]["unit_ids"]) == [3652, 3654, 3656] and cmds[0]["target_id"] == 3662
assert abs(cmds[2]["t"] - 10.269) < 0.01
assert any(e["id"] == 3662 for e in entities), "ordered tree missing from gaia header"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=1))
print(f"OK {OUT}  entities={len(entities)} props={len(props)} cmds={kinds}")
```

NOTE: `p1.objects` / `g.position` attribute names must be confirmed against the
mgz fork at execution time (`dir(obj)`); the replay blueprint
(`aoe2x/replay/blueprint.py`, `starting_units` and `_extract_map_objects`)
shows the working access patterns to copy if these differ.

- [x] **Step 2: Run:** `$PY apps/engine_viewer/tools/extract_commands.py` — Expected: `OK ... cmds=['order','gather_point','queue','resign']`. If attribute errors: fix per blueprint patterns.
- [x] **Step 3: Commit** extractor + data: `git add apps/engine_viewer/tools/extract_commands.py apps/engine_viewer/data && git commit -m "engine_viewer: bake commands.json from rec replay"`

### Task 3: extract_truth.py (gRPC capture -> truth.json)

**Files:**
- Create: `apps/engine_viewer/tools/extract_truth.py` (productionized from the session probe — segmenting + per-frame transitions)
- Output: `apps/engine_viewer/data/4_lumber/truth.json`

- [x] **Step 1: Write extractor.** Same segment-picking as the probe (split on >400KB patches / clock resets, pick longest-span snapshot segment). Differences from probe: deposit detection per FRAME (carry>5 then <1 between consecutive frames -> deposit at that frame's t), spawn events for owner-1 entities, tree felled_t (hp first 0), empty_t (wood first 0), removed_t (entity gone), per-second rows for the chart. Core loop (after seeding, vars `es`, `doc`, `world_id` as in probe):

```python
F_X, F_Y, F_CARRY, F_HP, F_MASTER, F_OWNER = 3, 4, 6, 12, 1, 2
TRACKED = [3652, 3654, 3656]          # grows when owner-1 spawns appear
deposits, spawns, rows = [], [], []
prev_carry, known = {}, set(es)
felled_t = empty_t = removed_t = None
next_row = 0
for t, patch, events in seg["frames"]:
    if patch:
        D.apply_patch(doc, patch, es, world_id)
    for which, ev in events:
        if which == "entityKilled":
            es.pop(ev.entityKilled.id, None)
    for eid in set(es) - known:
        e = es[eid]
        if e.get(F_OWNER) == 1:
            spawns.append({"eid": eid, "t": t / 1000, "master": e.get(F_MASTER)})
            TRACKED.append(eid)
    known |= set(es)
    for eid in TRACKED:
        e = es.get(eid)
        c = e.get(F_CARRY) if e else None
        p = prev_carry.get(eid)
        if p is not None and c is not None and p > 5 and c < 1:
            deposits.append({"t": round(t / 1000, 2), "eid": eid, "amount": round(p, 2)})
        if c is not None:
            prev_carry[eid] = c
    tree = es.get(3662)
    if tree:
        if felled_t is None and (tree.get(F_HP) or 1) <= 0: felled_t = t / 1000
        if empty_t is None and (tree.get(F_CARRY) or 1) <= 0: empty_t = t / 1000
    elif removed_t is None and felled_t is not None:
        removed_t = t / 1000
    if t >= next_row:                  # 1 Hz chart rows
        next_row = (t // 1000 + 1) * 1000
        rows.append({"t": round(t / 1000, 1),
                     "vills": {str(eid): [round(es[eid][F_X], 2), round(es[eid][F_Y], 2),
                                          round(es[eid].get(F_CARRY) or 0, 2)]
                               for eid in TRACKED if eid in es},
                     "tree_wood": round(tree.get(F_CARRY), 2) if tree else 0.0})
```

Output doc + self-check:

```python
out = {"scenario": "4_lumber", "spawn": spawns[0], "deposits": deposits,
       "tree": {"start_wood": 100.0, "hp": 20.0, "felled_t": felled_t,
                "empty_t": empty_t, "removed_t": removed_t},
       "total_delivered": round(sum(d["amount"] for d in deposits), 2),
       "rows": rows}
assert len(deposits) == 11, deposits
assert abs(spawns[0]["t"] - 35.26) < 0.1
assert 100 <= empty_t <= 104 and abs(out["total_delivered"] - 100.3) < 1.0
```

- [x] **Step 2: Run:** `$PY apps/engine_viewer/tools/extract_truth.py` — Expected: `OK ... deposits=11 spawn=35.26 empty=102.x total=100.3`
- [x] **Step 3: Commit:** `git add apps/engine_viewer/tools/extract_truth.py apps/engine_viewer/data && git commit -m "engine_viewer: bake truth.json from gRPC capture"`

### Task 4: constants.js + engine skeleton + RED verifier

**Files:**
- Create: `apps/engine_viewer/public/constants.js`, `apps/engine_viewer/public/engine.js`, `apps/engine_viewer/verify/verify.mjs`

- [x] **Step 1: constants.js** — every value with provenance comment:

```js
// Sources: [dat] = game data file (known constants), [cap] = measured from
// the 4_lumber gRPC capture (lab/captures/4_lumber.frames.bin, build 178524).
export const TICK = 1 / 20;            // [engine] 20 Hz sim tick
export const VILL_SPEED = 0.8;         // [dat] tiles/s   [cap] confirms 0.8
export const GATHER_RATE = 0.39;       // [dat] wood/s    [cap] measured 0.391
export const CARRY_CAP = 10;           // [dat]           [cap] confirms 10.0
export const TRAIN_TIME_VILLAGER = 25; // [dat]           [cap] 10.27 -> 35.26
export const TREE_WOOD = 100;          // [dat]           [cap] confirms 100.0
export const TREE_HP = 20;             // [dat]           [cap] confirms 20.0
export const FELL_DPS = 4.55;          // [cap] solo fell ~4.4s (20 HP / 4.4)
export const GATHER_REACH = 0.9;       // [cap] stand dist from tree center
export const TC_SIZE = 4;              // [dat] 4x4 footprint
export const DEPOSIT_REACH = 0.8;      // [cap] deposit dist from TC footprint
```

- [x] **Step 2: engine.js skeleton** — API + command intake only; `step()` moves nothing yet (so the verifier runs RED end-to-end):

```js
import * as C from "./constants.js";

export function createGame(scenario) {
  const ents = new Map();
  for (const e of scenario.entities) ents.set(e.id, structuredClone(e));
  for (const e of ents.values()) {
    if (e.type === "villager" || e.type === "scout") Object.assign(e, { task: "idle", carry: 0, tx: e.x, ty: e.y });
    if (e.type === "town_center") Object.assign(e, { queue: [], rally: null });
    if (e.type === "tree") Object.assign(e, { felled: false });
  }
  return { t: 0, ents, wood: scenario.players[0].start_wood,
           pending: [...scenario.commands].sort((a, b) => a.t - b.t),
           events: [], ended: false, nextId: 4236 };
}
export function step(g) { g.t += C.TICK; applyCommands(g); }
export function run(g, untilT) { while (g.t < untilT && !g.ended) step(g); return g; }
function emit(g, kind, data) { g.events.push({ t: +g.t.toFixed(2), kind, ...data }); }
function applyCommands(g) {
  while (g.pending.length && g.pending[0].t <= g.t) {
    const c = g.pending.shift();
    if (c.type === "order") for (const id of c.unit_ids) assignGather(g, g.ents.get(id), c.target_id);
    else if (c.type === "gather_point") g.ents.get(c.building_id).rally = c.target_id;
    else if (c.type === "queue") g.ents.get(c.building_id).queue.push({ remaining: c.train_time });
    else if (c.type === "resign") { g.ended = true; emit(g, "end", {}); }
  }
}
function assignGather(g, v, treeId) { v.task = "to_tree"; v.target = treeId; } // stub
```

- [x] **Step 3: verify.mjs** — full scorer (this is the acceptance test; tolerances from the spec):

```js
import { readFileSync } from "node:fs";
import { createGame, run } from "../public/engine.js";
const dir = new URL("../data/4_lumber/", import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));
const truth = JSON.parse(readFileSync(new URL("truth.json", dir)));
const g = run(createGame(scen), scen.duration + 1);
const dep = g.events.filter(e => e.kind === "deposit");
const spawn = g.events.find(e => e.kind === "spawn");
const empty = g.events.find(e => e.kind === "tree_empty");
const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok, detail });
add("4th villager spawn ±0.5s", !!spawn && Math.abs(spawn.t - truth.spawn.t) <= 0.5,
    `truth ${truth.spawn.t} sim ${spawn?.t ?? "-"}`);
const simLeft = [...dep];
for (const td of truth.deposits) {
  let best = null;
  for (const sd of simLeft) if (!best || Math.abs(sd.t - td.t) < Math.abs(best.t - td.t)) best = sd;
  const ok = !!best && Math.abs(best.t - td.t) <= 1.5 && Math.abs(best.amount - td.amount) <= 0.5;
  add(`deposit @${td.t} (${td.amount})`, ok, best ? `sim ${best.t} (${best.amount})` : "none");
  if (best) simLeft.splice(simLeft.indexOf(best), 1);
}
add("no extra sim deposits", simLeft.length === 0, `${simLeft.length} extra`);
add("tree empty ±3s", !!empty && Math.abs(empty.t - truth.tree.empty_t) <= 3,
    `truth ${truth.tree.empty_t} sim ${empty?.t ?? "-"}`);
const total = dep.reduce((s, d) => s + d.amount, 0);
add("total wood ±1", Math.abs(total - truth.total_delivered) <= 1, `truth ${truth.total_delivered} sim ${total.toFixed(2)}`);
const vills = [...g.ents.values()].filter(e => e.type === "villager").length;
add("final villager count = 4", vills === 4, `sim ${vills}`);
let fails = 0;
for (const c of checks) { if (!c.ok) fails++; console.log(`${c.ok ? "PASS" : "FAIL"}  ${c.name}  [${c.detail}]`); }
console.log(fails ? `\n${fails}/${checks.length} FAILED` : `\nALL ${checks.length} PASSED`);
process.exit(fails ? 1 : 0);
```

- [x] **Step 4: Run RED:** `node apps/engine_viewer/verify/verify.mjs` — Expected: exit 1, ~15 FAIL lines (spawn none, all deposits none...). This proves the harness wiring before mechanics exist.
- [x] **Step 5: Commit:** `git commit -m "engine_viewer: constants, engine skeleton, RED verifier"`

### Task 5: Engine mechanics -> verifier GREEN

**Files:**
- Modify: `apps/engine_viewer/public/engine.js`

- [x] **Step 1: Implement the villager FSM + TC + tree inside `step()`** (replaces stubs; complete logic):

```js
export function step(g) {
  g.t += C.TICK; applyCommands(g);
  for (const e of g.ents.values()) {
    if (e.type === "town_center") stepTC(g, e);
    else if (e.type === "villager") stepVill(g, e);
  }
}
function stepTC(g, tc) {
  if (!tc.queue.length) return;
  tc.queue[0].remaining -= C.TICK;
  if (tc.queue[0].remaining > 0) return;
  tc.queue.shift();
  const v = { id: g.nextId++, type: "villager", owner: 1, task: "idle", carry: 0,
              x: tc.x - 2.2, y: tc.y + 2.2 };          // SW corner toward rally
  g.ents.set(v.id, v);
  emit(g, "spawn", { eid: v.id });
  if (tc.rally != null && g.ents.get(tc.rally)?.type === "tree") assignGather(g, v, tc.rally);
}
function assignGather(g, v, treeId) {
  const tree = g.ents.get(treeId);
  if (!tree) { v.task = "idle"; return; }
  v.target = treeId; v.task = "to_tree";
  const n = ++tree.slots || (tree.slots = 1);          // stand-slot ring
  const ang = [200, 60, 320, 130, 250][(n - 1) % 5] * Math.PI / 180;
  v.tx = tree.x + Math.cos(ang) * C.GATHER_REACH;
  v.ty = tree.y + Math.sin(ang) * C.GATHER_REACH;
}
function moveToward(e, tx, ty) {
  const dx = tx - e.x, dy = ty - e.y, d = Math.hypot(dx, dy), s = C.VILL_SPEED * C.TICK;
  if (d <= s) { e.x = tx; e.y = ty; return true; }
  e.x += dx / d * s; e.y += dy / d * s; return false;
}
function tcDropPoint(g, e) {           // nearest point ON the footprint edge, then stand off it
  const tc = [...g.ents.values()].find(x => x.type === "town_center");
  const h = C.TC_SIZE / 2;
  const px = Math.max(tc.x - h, Math.min(e.x, tc.x + h));
  const py = Math.max(tc.y - h, Math.min(e.y, tc.y + h));
  return { tc, px, py };
}
function stepVill(g, v) {
  const tree = v.target != null ? g.ents.get(v.target) : null;
  if (v.task === "to_tree") {
    if (!tree) { v.task = v.carry > 0 ? "to_tc" : "idle"; return; }
    if (moveToward(v, v.tx, v.ty)) v.task = tree.felled ? "gather" : "fell";
  } else if (v.task === "fell") {
    if (!tree) { v.task = "idle"; return; }
    if (tree.felled) { v.task = "gather"; return; }
    tree.hp -= C.FELL_DPS * C.TICK;
    if (tree.hp <= 0) { tree.felled = true; emit(g, "tree_felled", { eid: tree.id }); v.task = "gather"; }
  } else if (v.task === "gather") {
    if (!tree || tree.wood <= 0) { v.task = v.carry > 0 ? "to_tc" : "idle"; return; }
    const take = Math.min(C.GATHER_RATE * C.TICK, C.CARRY_CAP - v.carry, tree.wood);
    v.carry += take; tree.wood -= take;
    if (tree.wood <= 1e-9) {
      tree.wood = 0; emit(g, "tree_empty", { eid: tree.id }); g.ents.delete(tree.id);
      for (const o of g.ents.values())
        if (o.type === "villager" && o.target === tree.id)
          o.task = o.carry > 0 ? "to_tc" : "idle";
      return;
    }
    if (v.carry >= C.CARRY_CAP - 1e-9) { v.carry = C.CARRY_CAP; v.task = "to_tc"; }
  } else if (v.task === "to_tc") {
    const { px, py } = tcDropPoint(g, v);
    if (Math.hypot(px - v.x, py - v.y) <= C.DEPOSIT_REACH) {
      g.wood += v.carry; emit(g, "deposit", { eid: v.id, amount: +v.carry.toFixed(2) });
      v.carry = 0;
      if (g.ents.get(v.target)) assignGather(g, v, v.target); else v.task = "idle";
    } else moveToward(v, px, py);
  }
}
```

- [x] **Step 2: Run:** `node apps/engine_viewer/verify/verify.mjs` — Expected GREEN or near-green. Calibration order if specific checks fail: first-trip deposit times off -> adjust `FELL_DPS` / slot angles (arrival distance); spawn time off -> queue starts at command intake (it does — `remaining: 25.0` from command, ticked next step; expected sim spawn ≈ 35.27); late deposits off -> `DEPOSIT_REACH`. Iterate constants within [cap] plausibility only — do not touch [dat] values.
- [x] **Step 3: Commit:** `git commit -m "engine_viewer: mechanics — verifier green vs gRPC truth"`

### Task 6: server.py

**Files:**
- Create: `apps/engine_viewer/server.py`

- [x] **Step 1: Write it:**

```python
"""Engine-viewer host: static SPA + scenario data. PORT env, default 5003."""
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(ROOT / "public"), static_url_path="")

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/api/scenarios")
def scenarios():
    return jsonify(sorted(p.name for p in (ROOT / "data").iterdir() if p.is_dir()))

@app.get("/data/<scen>/<name>.json")
def data(scen, name):
    if name not in ("commands", "truth"):
        return jsonify({"error": "unknown file"}), 404
    return send_from_directory(ROOT / "data" / scen, f"{name}.json")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5003)), debug=False)
```

- [x] **Step 2: Smoke:** start in background, then `curl http://127.0.0.1:5003/api/scenarios` -> `["4_lumber"]`, `curl -s http://127.0.0.1:5003/data/4_lumber/commands.json | head -c 80`. Flask present in PATH python (webapp deps) — else `$PY -m pip install flask` and run with `$PY`.
- [x] **Step 3: Commit:** `git commit -m "engine_viewer: flask host"`

### Task 7: Viewer (index.html, render.js, app.js, assets)

**Files:**
- Create: `apps/engine_viewer/public/index.html`, `public/render.js`, `public/app.js`
- Copy: `aoe2x/replay/public/assets/sprites/units/villager.png`, `units/scoutcavalry.webp`, `buildings/towncenter.png` -> `apps/engine_viewer/public/assets/`

- [x] **Step 1: index.html** — dark shell, canvas, HUD bar (wood count, clock, play/pause, speed 1/2/4/8, scrub range input), right-side verify panel (`<div id="scorecard">` + `<canvas id="chart">`), loads `<script type="module" src="app.js">`.
- [x] **Step 2: render.js** — isometric projection (`sx=(x+y)*TW/2`, `sy=(y-x)*TH/2`, TW=32, TH=16 at zoom 1), camera centered on TC, zoom/pan (wheel/drag); draws: grass gradient backdrop, prop trees (procedural: trunk rect + two green circles), the live tree (bigger, shows remaining-wood ring; stump after felled; gone after removal), TC sprite, villager sprites (player-blue tint disc under sprite, small log icon when carry > 5), scout sprite, selection-free. Procedural fallback if a sprite file 404s.
- [x] **Step 3: app.js** — fetch `/data/4_lumber/commands.json` + `truth.json`; build `createGame`; RAF loop advancing `speed × dt` of sim time via repeated `step()`; scrub = `createGame` fresh + `run(g, T)` (deterministic re-sim, instant at this scale); HUD bindings; verify overlay: run a throwaway full sim at load, compare events vs truth (same logic as verify.mjs, duplicated small — note the lockstep comment both sides), render PASS/FAIL rows into `#scorecard`, draw wood-over-time chart (sim line = `150 + Σdeposits(t)` stepped; truth line = `150 + Σtruth.deposits(t)`; tree-wood lines from truth.rows vs sim sampled per second).
- [x] **Step 4: Manual check:** open http://127.0.0.1:5003/ — villagers walk, chop, shuttle; wood ticks to 250; scorecard green; chart lines hug.
- [x] **Step 5: Commit:** `git commit -m "engine_viewer: canvas viewer + verify overlay"`

### Task 8: Final verification + hand-off

- [x] **Step 1:** `node apps/engine_viewer/verify/verify.mjs` — ALL PASSED, exit 0.
- [x] **Step 2:** `pytest` quick: existing suite untouched (no shared files modified) — run `pytest -q` to confirm zero regressions. *(279 passed, 13 skipped — clean, 64s)*
- [x] **Step 3:** Server running in background on 5003; deliver link + summary + scorecard output to user.
- [x] **Step 4:** Update `apps/engine_viewer/README.md` with verify output snapshot; final commit.

## Self-review notes

- Spec coverage: extractors (Tasks 2–3), engine+constants (4–5), verifier (4–5), server (6), viewer+overlay (7), acceptance (8). Starting-stockpile fallback honored in Task 2 (`start_wood_source: "ui_observed"`). Out-of-scope items absent. ✓
- mgz attribute-name risk flagged in Task 2 with the blueprint as the reference implementation. ✓
- Type consistency: event kinds (`spawn/deposit/tree_felled/tree_empty/end`) match between engine (Task 5) and verifier (Task 4); `train_time` injected by extractor (Task 2) and consumed by `applyCommands` (Task 4). ✓
