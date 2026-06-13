// Deterministic AoE2 economy engine — pure logic, no DOM. Consumed by the
// browser viewer (app.js) and the headless verifier (verify/verify.mjs).
//
// Scenario shapes supported (commands.json):
//   - order/gather_point on a single tree (4_lumber)
//   - build a lumber camp, auto-gather a forest, train villagers (camp300)
//   - build mill + house, forage berries, POPULATION CAP gating the TC
//     queue — training timer is FROZEN while housed (millpop)
//   - convert + herd geese, KILL them, gather the carcass while it ROTS at a
//     fixed rate, moving-unit retargeting + sequential consumption (sheep)
import * as C from "./constants.js";

// A herdable is a gatherable food node only once it is SLAIN (a carcass).
// Live herdables are mobile units that must be killed first.
const isNode = (e) =>
  e.type === "tree" || e.type === "bush" || (e.type === "herdable" && e.dead);
const nodePool = (e) => (e.type === "tree" ? e.wood : e.food);
const drainNode = (e, amt) => { if (e.type === "tree") e.wood -= amt; else e.food -= amt; };

export function createGame(scenario) {
  const ents = new Map();
  for (const e of scenario.entities) ents.set(e.id, structuredClone(e));
  for (const e of ents.values()) {
    if (e.type === "villager" || e.type === "scout") {
      Object.assign(e, { task: "idle", carry: 0, carryRes: null, tx: e.x, ty: e.y,
                         target: null, phase: 0, moveTarget: null });
    }
    if (e.type === "town_center") Object.assign(e, { queue: [], rally: null, built: true });
    if (e.type === "tree" || e.type === "bush") {
      Object.assign(e, { gatherers: 0, felled: e.type !== "tree" });
    }
    if (e.type === "herdable") {
      // alive food unit; dead=carcass(gatherable). felled=true: no fell delay.
      Object.assign(e, { gatherers: 0, felled: true, dead: false, alive: true,
                         hp: 7, moveTarget: null });
    }
  }
  // debug numbering: starting villagers 1..n (by id), trained continue
  let num = 1;
  for (const e of [...ents.values()]
      .filter((e) => e.type === "villager").sort((a, b) => a.id - b.id)) {
    e.num = num++;
  }
  const xs = scenario.entities.map((e) => e.x);
  const ys = scenario.entities.map((e) => e.y);
  const g = {
    t: 0,
    civ: scenario.players[0].civ,
    ents,
    wood: scenario.players[0].start_wood,
    food: scenario.players[0].start_food ?? 0,
    collected: 0,                  // cumulative resources delivered (headline metric)
    rotted: 0,                     // food lost to carcass decay (sheep scenario)
    pending: [...scenario.commands].sort((a, b) => a.t - b.t),
    events: [],
    ended: false,
    nextId: 10000,
    nextNum: num,
    blocked: new Set(),
    bounds: { minX: Math.floor(Math.min(...xs)) - 6, maxX: Math.ceil(Math.max(...xs)) + 6,
              minY: Math.floor(Math.min(...ys)) - 6, maxY: Math.ceil(Math.max(...ys)) + 6 },
  };
  recomputeObstacles(g);
  return g;
}

// ------------------------------------------------------------- population
// Pop = every living unit; cap = pop room of COMPLETED buildings only.
// While pop >= cap the TC queue head's timer is FROZEN (capture: spawn #2
// landed at house_complete + exactly 25.0s, not earlier).
export function popCount(g) {
  let n = 0;
  for (const e of g.ents.values()) {
    if (e.type === "villager" || e.type === "scout") n++;
  }
  return n;
}

export function popCap(g) {
  if (C.CIV_NO_HOUSES.has(g.civ)) return Infinity;   // Huns: no houses needed
  let cap = 0;
  for (const e of g.ents.values()) {
    const spec = C.BUILDINGS[e.type];
    if (spec && spec.pop && e.built) cap += spec.pop;
  }
  return cap;
}

// Immovable obstacles: resource nodes with pool left (trees AND berry
// bushes), and building footprints from the moment construction starts.
// A node's gather capacity = its free orthogonal neighbor tiles (capture:
// bush 3143, walled in by 3 bushes + the mill footprint, was never touched).
function recomputeObstacles(g) {
  const blocked = new Set();
  const tile = (x, y) => `${Math.floor(x)},${Math.floor(y)}`;
  for (const e of g.ents.values()) {
    if (isNode(e) && nodePool(e) > 0) blocked.add(tile(e.x, e.y));
    const spec = C.BUILDINGS[e.type];
    if (spec) {
      const half = spec.size / 2;
      for (let tx = Math.floor(e.x - half); tx < e.x + half; tx++)
        for (let ty = Math.floor(e.y - half); ty < e.y + half; ty++)
          blocked.add(`${tx},${ty}`);
    }
  }
  g.blocked = blocked;
  // Gather capacity. Trees: 1 villager per free orthogonal face (max 3).
  // Bushes: villagers PACK — capture shows 2 per orth face tile (0.4 apart)
  // plus diagonal-corner stands; 6 worked one bush simultaneously.
  for (const e of g.ents.values()) {
    if (!isNode(e)) continue;
    const tx = Math.floor(e.x), ty = Math.floor(e.y);
    let orth = 0, diag = 0;
    for (const [dx, dy] of ORTH) {
      if (!blocked.has(`${tx + dx},${ty + dy}`)) orth++;
    }
    for (const [dx, dy] of DIAG) {
      if (!blocked.has(`${tx + dx},${ty + dy}`)) diag++;
    }
    e.spots = e.type === "tree" ? orth : 2 * orth + diag;
  }
}

const ORTH = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const DIAG = [[1, 1], [1, -1], [-1, 1], [-1, -1]];

// ----------------------------------------------------------------- pathing
function losClear(g, x0, y0, x1, y1) {
  const d = Math.hypot(x1 - x0, y1 - y0);
  const steps = Math.max(1, Math.ceil(d / 0.3));
  for (let i = 1; i <= steps; i++) {
    const x = x0 + ((x1 - x0) * i) / steps;
    const y = y0 + ((y1 - y0) * i) / steps;
    if (g.blocked.has(`${Math.floor(x)},${Math.floor(y)}`)) return false;
  }
  return true;
}

// Tile A* (8-dir, no corner cutting), returns waypoints in world coords or
// null when unreachable. Greedy line-of-sight smoothing afterwards.
function findPath(g, x0, y0, x1, y1) {
  if (losClear(g, x0, y0, x1, y1)) return [[x1, y1]];
  const { minX, maxX, minY, maxY } = g.bounds;
  const sx = Math.floor(x0), sy = Math.floor(y0);
  const gx = Math.floor(x1), gy = Math.floor(y1);
  const key = (x, y) => `${x},${y}`;
  const free = (x, y) =>
    x >= minX && x <= maxX && y >= minY && y <= maxY && !g.blocked.has(key(x, y));
  if (!free(gx, gy)) return null;
  const open = [[Math.hypot(gx - sx, gy - sy), 0, sx, sy]];
  const came = new Map([[key(sx, sy), null]]);
  const gcost = new Map([[key(sx, sy), 0]]);
  const DIRS = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
                [1, 1, 1.41], [1, -1, 1.41], [-1, 1, 1.41], [-1, -1, 1.41]];
  let found = false;
  while (open.length) {
    open.sort((a, b) => a[0] - b[0]);
    const [, gc, cx, cy] = open.shift();
    if (cx === gx && cy === gy) { found = true; break; }
    for (const [dx, dy, w] of DIRS) {
      const nx = cx + dx, ny = cy + dy;
      if (!free(nx, ny)) continue;
      if (dx && dy && (!free(cx + dx, cy) || !free(cx, cy + dy))) continue;
      const nk = key(nx, ny), ng = gc + w;
      if (gcost.has(nk) && gcost.get(nk) <= ng) continue;
      gcost.set(nk, ng);
      came.set(nk, key(cx, cy));
      open.push([ng + Math.hypot(gx - nx, gy - ny), ng, nx, ny]);
    }
  }
  if (!found) return null;
  const tiles = [];
  let cur = key(gx, gy);
  while (cur) { tiles.push(cur); cur = came.get(cur); }
  tiles.reverse();
  let pts = tiles.slice(1).map((k) => {
    const [tx, ty] = k.split(",").map(Number);
    return [tx + 0.5, ty + 0.5];
  });
  pts[pts.length - 1] = [x1, y1];
  // greedy LOS smoothing
  const out = [];
  let from = [x0, y0];
  let i = 0;
  while (i < pts.length) {
    let j = pts.length - 1;
    while (j > i && !losClear(g, from[0], from[1], pts[j][0], pts[j][1])) j--;
    out.push(pts[j]);
    from = pts[j];
    i = j + 1;
  }
  return out;
}

export function step(g) {
  g.t += C.TICK;
  applyCommands(g);
  convertHerdables(g);
  for (const e of [...g.ents.values()]) {
    if (e.type === "town_center") stepTC(g, e);
    else if (C.BUILDINGS[e.type]) stepBuilding(g, e);
    else if (e.type === "villager") stepVill(g, e);
    else if (e.type === "scout") stepScout(g, e);
    else if (e.type === "herdable") stepHerdable(g, e);
  }
}

// Gaia herdables within CONVERT_RANGE of an owned unit flip to the player
// (capture: the 4 geese near the scout's path converted; the 4 far ones
// stayed gaia). Conversion is permanent and emits a visual event.
function convertHerdables(g) {
  const owned = [];
  for (const e of g.ents.values()) {
    if ((e.type === "scout" || e.type === "villager") && e.owner === 1)
      owned.push(e);
  }
  for (const h of g.ents.values()) {
    if (h.type !== "herdable" || h.owner === 1 || !h.alive) continue;
    for (const u of owned) {
      if (dist(h.x, h.y, u.x, u.y) <= C.CONVERT_RANGE) {
        h.owner = 1;
        h.convertedAt = g.t;       // render: brief conversion pulse
        emit(g, "convert", { eid: h.id, by: u.id });
        break;
      }
    }
  }
}

// Scout: walk to its MOVE target (visual / conversion driver only).
function stepScout(g, s) {
  if (s.moveTarget) {
    if (moveAlong(g, s, s.moveTarget[0], s.moveTarget[1])) s.moveTarget = null;
  }
}

// Herdable: while alive + herded, walk toward its MOVE target at herd speed.
// Once slain, the carcass DECAYS at a fixed rate (independent of gatherers);
// the rotted food is lost, never banked.
function stepHerdable(g, h) {
  if (h.alive && h.moveTarget) {
    const [tx, ty] = h.moveTarget;
    const d = Math.hypot(tx - h.x, ty - h.y);
    const budget = C.HERD_SPEED * C.TICK;
    if (d <= budget) { h.x = tx; h.y = ty; h.moveTarget = null; }
    else { h.x += ((tx - h.x) / d) * budget; h.y += ((ty - h.y) / d) * budget; }
  }
  if (h.dead && h.food > 0) {
    const rot = Math.min(C.ROT_RATE * C.TICK, h.food);
    h.food -= rot;
    g.rotted += rot;
    if (h.food <= 1e-9) {
      h.food = 0;
      emit(g, "node_empty", { eid: h.id });
      recomputeObstacles(g);
    }
  }
}

export function run(g, untilT) {
  while (g.t < untilT && !g.ended) step(g);
  return g;
}

function emit(g, kind, data) {
  g.events.push({ t: +g.t.toFixed(2), kind, ...data });
}

// --------------------------------------------------------------- commands
function applyCommands(g) {
  while (g.pending.length && g.pending[0].t <= g.t) {
    const c = g.pending.shift();
    if (c.type === "build") {
      const btype = C.BUILDING_BY_NAME[c.building] || "lumber_camp";
      const spec = C.BUILDINGS[btype];
      const b = {
        id: g.nextId++, type: btype, owner: 1,
        x: c.x, y: c.y, built: false, progress: 0,
      };
      g.ents.set(b.id, b);
      g.wood -= spec.cost || 0;
      emit(g, "foundation", { eid: b.id, building: btype });
      recomputeObstacles(g);       // footprint blocks tiles + gather spots
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (u) {
          releaseNode(g, u);
          u.task = "to_build"; u.target = b.id; u.queuedOrder = null;
          assignBuildSpot(g, u, b);
        }
      }
    } else if (c.type === "order") {
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (!u) continue;
        // An order issued while the unit is constructing is a shift-queued
        // follow-up (millpop: build house, THEN return to bush 3153) —
        // defer it to building completion instead of cancelling the build.
        if (u.task === "to_build" || u.task === "building") u.queuedOrder = c.target_id;
        else assignGather(g, u, c.target_id);
      }
    } else if (c.type === "move") {
      // MOVE retargets a scout (visual) or HERDS owned herdables to a point.
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (!u) continue;
        if (u.type === "herdable") { if (u.alive) u.moveTarget = [c.x, c.y]; }
        else if (u.type === "scout") u.moveTarget = [c.x, c.y];
      }
    } else if (c.type === "gather_point") {
      const b = g.ents.get(c.building_id);
      const tgt = g.ents.get(c.target_id);
      const rx = c.x ?? tgt?.x, ry = c.y ?? tgt?.y;   // older commands.json lack coords
      if (b && rx != null) b.rally = { x: rx, y: ry, target_id: c.target_id };
    } else if (c.type === "queue") {
      const b = g.ents.get(c.building_id);
      if (b) b.queue.push({ remaining: c.train_time });
    } else if (c.type === "resign") {
      g.ended = true;
      emit(g, "end", {});
    }
  }
}

// --------------------------------------------------------------- buildings
function stepTC(g, tc) {
  if (!tc.queue.length) return;
  if (popCount(g) + 1 > popCap(g)) return;   // housed: timer frozen
  tc.queue[0].remaining -= C.TICK;
  if (tc.queue[0].remaining > 0) return;
  tc.queue.shift();
  // Spawn on the rally-facing side of the TC (capture: trained villagers
  // appeared at (67.5,16.5), the berry-side edge — not a fixed corner).
  const half = C.BUILDINGS.town_center.size / 2 + 0.5;
  let sx = tc.x - half, sy = tc.y + half;
  if (tc.rally) {
    const dx = tc.rally.x - tc.x, dy = tc.rally.y - tc.y;
    const m = Math.max(Math.abs(dx), Math.abs(dy)) || 1;
    sx = tc.x + (dx / m) * half;
    sy = tc.y + (dy / m) * half;
  }
  const v = {
    id: g.nextId++, type: "villager", owner: 1, task: "idle", carry: 0,
    carryRes: null,
    x: sx, y: sy,
    target: null, phase: 0, num: g.nextNum++,
  };
  g.ents.set(v.id, v);
  emit(g, "spawn", { eid: v.id });
  // Trained villagers walk to the rally point, then gather there.
  if (tc.rally) {
    v.task = "to_rally";
    v.tx = tc.rally.x; v.ty = tc.rally.y;
    v.rallyTarget = tc.rally.target_id;
  }
}

// Construction: count active builders each tick, accrue points by the real
// multi-builder formula (3*T1/(n+2) total time), complete at T1 points.
function stepBuilding(g, b) {
  if (b.built) return;
  let n = 0;
  for (const e of g.ents.values()) {
    if (e.type === "villager" && e.task === "building" && e.target === b.id) n++;
  }
  if (!n) return;
  b.progress += C.BUILD_RATE(n) * C.TICK;
  if (b.progress >= C.BUILDINGS[b.type].t1) {
    b.built = true;
    emit(g, "built", { eid: b.id, building: b.type, n });
  }
}

// --------------------------------------------------------------- helpers
function dist(a, b, x, y) { return Math.hypot(a - x, b - y); }

function dropsites(g, res) {
  const out = [];
  for (const e of g.ents.values()) {
    const spec = C.BUILDINGS[e.type];
    if (spec && spec.drop && e.built && spec.drop.includes(res)) {
      out.push({ e, half: spec.size / 2 });
    }
  }
  return out;
}

function nearestDrop(g, x, y, res) {
  let best = null, bd = Infinity;
  for (const d of dropsites(g, res)) {
    const dd = dist(d.e.x, d.e.y, x, y);
    if (dd < bd) { bd = dd; best = d; }
  }
  return best;
}

// Deposit stand point: nearest FREE tile on the dropsite's perimeter ring —
// always a legal pathfinding destination (the old geometric edge point could
// land inside an adjacent tree tile, defeating the path planner).
function dropStand(g, d, v) {
  const x0 = Math.floor(d.e.x - d.half), x1 = Math.ceil(d.e.x + d.half) - 1;
  const y0 = Math.floor(d.e.y - d.half), y1 = Math.ceil(d.e.y + d.half) - 1;
  let best = null, bd = Infinity;
  for (let tx = x0 - 1; tx <= x1 + 1; tx++) {
    for (let ty = y0 - 1; ty <= y1 + 1; ty++) {
      if (tx >= x0 && tx <= x1 && ty >= y0 && ty <= y1) continue; // inside
      if (g.blocked.has(`${tx},${ty}`)) continue;
      // nearest legal point WITHIN this free tile (not its center) — keeps
      // the walk as short as the old geometric edge point allowed
      const sx = Math.max(tx + 0.15, Math.min(v.x, tx + 0.85));
      const sy = Math.max(ty + 0.15, Math.min(v.y, ty + 0.85));
      const dd = Math.hypot(sx - v.x, sy - v.y);
      if (dd < bd) { bd = dd; best = [sx, sy]; }
    }
  }
  return best;
}

function nodeCap(e) {
  if (e.type === "herdable") return C.HERD_CAP;  // carcass swarmed at the TC
  return e.spots ?? 4;       // free-face slots; bushes pack 2/face + corners
}

// Nearest node of the SAME resource with a free gather spot. Crowding is
// handled physically by the face/spot capacity model — no distance penalty.
function nearestNode(g, x, y, res) {
  let best = null, bs = Infinity;
  for (const e of g.ents.values()) {
    if (!isNode(e) || C.NODE_RES[e.type] !== res) continue;
    if (nodePool(e) <= 0 || e.gatherers >= nodeCap(e)) continue;
    const score = dist(e.x, e.y, x, y);
    if (score < bs) { bs = score; best = e; }
  }
  return best;
}

// Path-following movement: (re)plans via findPath when the target changes,
// then walks the waypoints. Falls back to a straight line if unreachable so
// units never freeze.
function moveAlong(g, v, tx, ty) {
  const key = `${tx.toFixed(2)},${ty.toFixed(2)}`;
  if (v.pathKey !== key) {
    v.path = findPath(g, v.x, v.y, tx, ty) || [[tx, ty]];
    v.pathKey = key;
  }
  let budget = C.VILL_SPEED * C.TICK;
  while (budget > 1e-9 && v.path.length) {
    const [wx, wy] = v.path[0];
    const d = Math.hypot(wx - v.x, wy - v.y);
    if (d <= budget) { v.x = wx; v.y = wy; v.path.shift(); budget -= d; }
    else { v.x += ((wx - v.x) / d) * budget; v.y += ((wy - v.y) / d) * budget; budget = 0; }
  }
  return !v.path.length;
}

// Builders line up on the foundation face they approach from (capture:
// 3 builders stood in a row on the camp's north face at ~0.4 spacing).
function assignBuildSpot(g, v, b) {
  const dx = v.x - b.x, dy = v.y - b.y;
  const n = (b.builders = (b.builders ?? 0) + 1);
  const off = (n - 1 - 1) * 0.45;               // -0.45, 0, +0.45 ...
  if (Math.abs(dy) >= Math.abs(dx)) {
    v.ty = b.y + Math.sign(dy || -1) * C.BUILD_REACH;
    v.tx = b.x + off;
  } else {
    v.tx = b.x + Math.sign(dx) * C.BUILD_REACH;
    v.ty = b.y + off;
  }
}

// Stand slots around a node. Trees: one exclusive slot per free orthogonal
// face at GATHER_REACH. Bushes: villagers pack — 2 slots per free orth face
// (±0.22 along the face at 0.7 reach) plus 1 per free diagonal corner
// (matches capture positions: (63.4,11.2)/(63.8,11.2) shared a face tile of
// bush 3153 while (64.2,11.3) stood on the corner).
function nodeSlots(g, node) {
  const tx0 = Math.floor(node.x), ty0 = Math.floor(node.y);
  const slots = [];
  ORTH.forEach(([dx, dy], i) => {
    if (g.blocked.has(`${tx0 + dx},${ty0 + dy}`)) return;
    if (node.type === "tree") {
      slots.push({ id: `o${i}`, x: node.x + dx * C.GATHER_REACH,
                   y: node.y + dy * C.GATHER_REACH });
    } else {                       // bush + carcass: villagers pack the faces
      for (const s of [-0.22, 0.22]) {
        slots.push({ id: `o${i}${s > 0 ? "+" : "-"}`,
                     x: node.x + dx * 0.7 + (dy ? s : 0),
                     y: node.y + dy * 0.7 + (dx ? s : 0) });
      }
    }
  });
  if (node.type !== "tree") {
    DIAG.forEach(([dx, dy], i) => {
      if (g.blocked.has(`${tx0 + dx},${ty0 + dy}`)) return;
      slots.push({ id: `d${i}`, x: node.x + dx * 0.7, y: node.y + dy * 0.7 });
    });
  }
  return slots;
}

// Carcass stand placement: villagers pack the OPEN side of a slain herdable
// (capture: 9-10 overlapping near the TC). Non-exclusive — they fan out in
// rows on whatever neighbor tiles aren't a building, so a TC-jammed carcass
// still feeds a full swarm.
function herdStand(g, v, node) {
  const tx0 = Math.floor(node.x), ty0 = Math.floor(node.y);
  let dir = null;
  for (const [dx, dy] of [...ORTH, ...DIAG]) {
    if (!g.blocked.has(`${tx0 + dx},${ty0 + dy}`)) { dir = [dx, dy]; break; }
  }
  if (!dir) dir = [-1, 0];
  const len = Math.hypot(dir[0], dir[1]) || 1;
  const ux = dir[0] / len, uy = dir[1] / len;
  const n = node.gatherers;                 // 0-based index of this gatherer
  const lane = ((n % 4) - 1.5) * 0.28;       // fan across the open side
  const depth = 0.7 + Math.floor(n / 4) * 0.42;  // back rows
  v.face = `h${n}`;
  v.tx = node.x + ux * depth - uy * lane;
  v.ty = node.y + uy * depth + ux * lane;
  return true;
}

function takeFace(g, v, node) {
  if (node.type === "herdable") return herdStand(g, v, node);
  node.faceUsed ??= new Set();
  const free = nodeSlots(g, node).filter((s) => !node.faceUsed.has(s.id));
  if (!free.length) return false;
  free.sort((a, b) => dist(a.x, a.y, v.x, v.y) - dist(b.x, b.y, v.x, v.y));
  node.faceUsed.add(free[0].id);
  v.face = free[0].id;
  v.tx = free[0].x;
  v.ty = free[0].y;
  return true;
}

// Nearest live owned herdable with food left (a hunt target to be killed).
// When `avail` is set, only herdables the player has HERDED IN (within
// HERD_AVAIL of a dropsite) qualify — villagers wait near the TC instead of
// running out to slay sheep still parked at the cluster (capture: kills
// followed the herding order, not raw distance).
function nearestLiveHerd(g, x, y, avail) {
  const drops = avail ? dropsites(g, "food") : null;
  let best = null, bs = Infinity;
  for (const e of g.ents.values()) {
    if (e.type !== "herdable" || e.dead || e.owner !== 1 || e.food <= 0) continue;
    if (drops && !drops.some((d) => dist(d.e.x, d.e.y, e.x, e.y) <= C.HERD_AVAIL))
      continue;
    const d = dist(e.x, e.y, x, y);
    if (d < bs) { bs = d; best = e; }
  }
  return best;
}

// Send a villager to slay a live herdable (then it gathers the carcass).
function goHerd(g, v, h) {
  v.target = h.id;
  v.task = "to_herd";
  v.dropT = null;
}

// Assign villager to gather a specific node (or nearest if id missing/empty/
// crowded — rally-overflow behavior seen in the captures). A live owned
// herdable target is hunted first; food with no ready carcass falls through
// to the nearest live herdable (sequential sheep consumption).
// `direct` (an explicit command target) bypasses the herding-availability
// gate — the player ordered this unit onto that herdable. Auto-retargets
// (nodeId == null) respect the gate so sheep are eaten in herding order.
function assignGather(g, v, nodeId, resHint) {
  releaseNode(g, v);
  const explicit = nodeId != null;
  let node = explicit ? g.ents.get(nodeId) : null;
  if (node && node.type === "herdable" && !node.dead && node.owner === 1) {
    goHerd(g, v, node); return;
  }
  let res = node && isNode(node) ? C.NODE_RES[node.type] : (resHint || v.lastRes || "wood");
  v.lastRes = res;             // remember so a parked seeker retries the right resource
  const direct = node && isNode(node) && nodePool(node) > 0
                 && node.gatherers < nodeCap(node);
  if (!direct) {
    node = nearestNode(g, v.x, v.y, res);
    if (!node && res === "food") {
      const live = nearestLiveHerd(g, v.x, v.y, !explicit);
      if (live) { goHerd(g, v, live); return; }
    }
    if (node) {
      emit(g, "retarget", { eid: v.id, num: v.num,
                            from: [+v.x.toFixed(1), +v.y.toFixed(1)],
                            tree: node.id,
                            d: +dist(node.x, node.y, v.x, v.y).toFixed(2) });
    }
  }
  if (!node || !takeFace(g, v, node)) { parkSeeker(g, v); return; }
  node.gatherers++;
  v.target = node.id;
  v.lastRes = C.NODE_RES[node.type];
  v.task = "to_node";
  v.dropT = null;
}

// No work right now: deliver any load, else WAIT and retry shortly. Idle must
// never be terminal — a villager parks near the TC until the next sheep is
// herded in, then picks it up (capture: spare villagers waited, then swarmed).
function parkSeeker(g, v) {
  if (v.carry > 0) { v.task = "to_drop"; return; }
  v.task = "seek";
  v.seekTimer = 0.5;
}

function releaseNode(g, v) {
  if (v.target != null) {
    const n = g.ents.get(v.target);
    if (n && isNode(n)) {
      if (n.gatherers > 0) n.gatherers--;
      if (v.face != null) n.faceUsed?.delete(v.face);
    }
  }
  v.target = null;
  v.face = null;
}

// After finishing a build: queued order wins; else if the building is a
// dropsite, auto-gather the nearest node it accepts (mill -> berries,
// lumber camp -> trees); else (house) go idle.
function afterBuild(g, v, b) {
  if (v.queuedOrder != null) {
    const q = v.queuedOrder; v.queuedOrder = null;
    assignGather(g, v, q);
    return;
  }
  const spec = C.BUILDINGS[b.type];
  for (const res of spec.drop || []) {
    const node = nearestNode(g, v.x, v.y, res);
    if (node) { assignGather(g, v, node.id); return; }
  }
  v.task = "idle";
}

// --------------------------------------------------------------- villager FSM
function stepVill(g, v) {
  switch (v.task) {
    case "to_build": {
      const b = g.ents.get(v.target);
      if (!b) { v.task = "idle"; return; }
      if (b.built) { afterBuild(g, v, b); return; }
      if (moveAlong(g, v, v.tx, v.ty)) v.task = "building";
      return;
    }
    case "building": {
      const b = g.ents.get(v.target);
      if (!b) { v.task = "idle"; return; }
      if (b.built) { afterBuild(g, v, b); return; }
      // construction points accrue in stepBuilding (multi-builder formula)
      return;
    }
    case "to_rally": {
      if (moveAlong(g, v, v.tx, v.ty)) assignGather(g, v, v.rallyTarget);
      return;
    }
    case "seek": {                   // parked: retry for work every 0.5s
      v.seekTimer -= C.TICK;
      if (v.seekTimer <= 0) assignGather(g, v, null);
      return;
    }
    case "to_herd": {                // walk to a live herdable to slay it
      const h = g.ents.get(v.target);
      if (!h || h.type !== "herdable") { assignGather(g, v, null); return; }
      if (h.dead) { assignGather(g, v, h.id); return; }   // already slain → eat
      if (moveAlong(g, v, h.x, h.y)) { v.task = "kill"; v.phase = C.KILL_TIME; }
      return;
    }
    case "kill": {
      const h = g.ents.get(v.target);
      if (!h || h.type !== "herdable") { assignGather(g, v, null); return; }
      if (h.dead) { assignGather(g, v, h.id); return; }
      v.phase -= C.TICK;
      if (v.phase <= 0) {
        h.dead = true; h.alive = false; h.moveTarget = null; h.hp = 0;
        emit(g, "kill", { eid: h.id, by: v.id });
        recomputeObstacles(g);       // carcass now blocks its tile + gives slots
        assignGather(g, v, h.id);     // start eating the carcass
      }
      return;
    }
    case "to_node": {
      const node = g.ents.get(v.target);
      if (!node || nodePool(node) <= 0) { assignGather(g, v, null); return; }
      if (moveAlong(g, v, v.tx, v.ty)) { v.task = "settle"; v.phase = C.SETTLE_TIME; }
      return;
    }
    case "settle": {
      const node = g.ents.get(v.target);
      if (!node) { parkSeeker(g, v); return; }
      v.phase -= C.TICK;
      if (v.phase <= 0) {
        // Felling happens once per TREE (first villager cuts it down);
        // bushes and repeat trips gather immediately.
        if (node.felled) { v.task = "gather"; }
        else { v.task = "fell"; v.phase = C.FELL_TIME; }
      }
      return;
    }
    case "fell": {
      const node = g.ents.get(v.target);
      if (!node || nodePool(node) <= 0) { assignGather(g, v, null); return; }
      if (node.felled) { v.task = "gather"; return; }
      v.phase -= C.TICK;
      if (v.phase <= 0) { node.felled = true; emit(g, "tree_felled", { eid: node.id }); v.task = "gather"; }
      return;
    }
    case "gather": {
      const node = g.ents.get(v.target);
      if (!node || nodePool(node) <= 0) {
        releaseNode(g, v);
        // Node ran dry mid-load: keep a partial carry and top up at the next
        // node; only a NEARLY FULL load goes straight to the dropsite
        // (capture: 9.14/9.49 deposited at bush-empty, 2-4 carried on).
        v.task = v.carry >= C.CARRY_CAP - 1 ? "to_drop" : "to_node_next";
        return;
      }
      const rate = C.NODE_RATE[node.type];
      const take = Math.min(rate * C.TICK, C.CARRY_CAP - v.carry, nodePool(node));
      v.carry += take; v.carryRes = C.NODE_RES[node.type];
      drainNode(node, take);
      if (nodePool(node) <= 1e-9) {
        if (node.type === "tree") node.wood = 0; else node.food = 0;
        emit(g, "node_empty", { eid: node.id });
        recomputeObstacles(g);       // empty node stops blocking movement/spots
      }
      if (v.carry >= C.CARRY_CAP - 1e-9) { v.carry = C.CARRY_CAP; v.task = "to_drop"; }
      return;
    }
    case "to_node_next": {           // node emptied with no load: find a new one
      assignGather(g, v, null);
      return;
    }
    case "to_drop": {
      if (!v.dropT) {
        const d = nearestDrop(g, v.x, v.y, v.carryRes || "wood");
        if (!d) return;              // no dropsite yet (still building)
        v.dropT = dropStand(g, d, v);
        if (!v.dropT) return;        // dropsite fully walled in
      }
      if (moveAlong(g, v, v.dropT[0], v.dropT[1])) {
        v.dropT = null;
        g[v.carryRes || "wood"] += v.carry;
        g.collected += v.carry;
        emit(g, "deposit", { eid: v.id, amount: +v.carry.toFixed(2), res: v.carryRes });
        v.carry = 0;
        const node = v.target != null ? g.ents.get(v.target) : null;
        if (node && isNode(node) && nodePool(node) > 0) {
          v.task = "to_node";        // same node still has stock: go back
        } else {
          assignGather(g, v, null);  // retarget to nearest same-resource node
        }
      }
      return;
    }
    default: return;                 // idle
  }
}
