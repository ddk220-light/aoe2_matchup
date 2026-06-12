// Deterministic AoE2 economy engine — pure logic, no DOM. Consumed by the
// browser viewer (app.js) and the headless verifier (verify/verify.mjs).
//
// Supports two scenario shapes from commands.json:
//   - order/gather_point on a single tree (4_lumber)
//   - build a lumber camp, then auto-gather a forest with retargeting and
//     nearest-dropsite deposits (camp300)
import * as C from "./constants.js";

export function createGame(scenario) {
  const ents = new Map();
  for (const e of scenario.entities) ents.set(e.id, structuredClone(e));
  for (const e of ents.values()) {
    if (e.type === "villager" || e.type === "scout") {
      Object.assign(e, { task: "idle", carry: 0, tx: e.x, ty: e.y,
                         target: null, phase: 0 });
    }
    if (e.type === "town_center") Object.assign(e, { queue: [], rally: null });
    if (e.type === "tree") Object.assign(e, { gatherers: 0, felled: false });
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
    ents,
    wood: scenario.players[0].start_wood,
    collected: 0,                  // cumulative wood delivered (the headline metric)
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

// Immovable obstacles: trees with wood left, and building footprints from
// the moment construction starts (farms, when they exist, will be exempt —
// walkable). A tree's gather capacity = its free orthogonal neighbor tiles
// (capture: trees walled in by forest + the camp footprint were never
// harvested; the rally tree capped at 2 because the camp blocks its east face).
function recomputeObstacles(g) {
  const blocked = new Set();
  const tile = (x, y) => `${Math.floor(x)},${Math.floor(y)}`;
  for (const e of g.ents.values()) {
    if (e.type === "tree" && e.wood > 0) blocked.add(tile(e.x, e.y));
    if (e.type === "town_center" || e.type === "lumber_camp") {
      const half = e.type === "town_center" ? C.TC_SIZE / 2 : C.CAMP_SIZE / 2;
      for (let tx = Math.floor(e.x - half); tx < e.x + half; tx++)
        for (let ty = Math.floor(e.y - half); ty < e.y + half; ty++)
          blocked.add(`${tx},${ty}`);
    }
  }
  g.blocked = blocked;
  for (const e of g.ents.values()) {
    if (e.type !== "tree") continue;
    const tx = Math.floor(e.x), ty = Math.floor(e.y);
    let spots = 0;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      if (!blocked.has(`${tx + dx},${ty + dy}`)) spots++;
    }
    e.spots = spots;
  }
}

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
  for (const e of [...g.ents.values()]) {
    if (e.type === "town_center") stepTC(g, e);
    else if (e.type === "lumber_camp") stepCamp(g, e);
    else if (e.type === "villager") stepVill(g, e);
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
      const camp = {
        id: g.nextId++, type: "lumber_camp", owner: 1,
        x: c.x, y: c.y, built: false, progress: 0,
      };
      g.ents.set(camp.id, camp);
      g.wood -= C.CAMP_COST_WOOD;
      emit(g, "foundation", { eid: camp.id, building: c.building });
      recomputeObstacles(g);       // footprint blocks tiles + gather spots
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (u) { u.task = "to_build"; u.target = camp.id; assignBuildSpot(g, u, camp); }
      }
    } else if (c.type === "order") {
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (u) assignGather(g, u, c.target_id);
      }
    } else if (c.type === "gather_point") {
      const b = g.ents.get(c.building_id);
      if (b) b.rally = { x: c.x, y: c.y, target_id: c.target_id };
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
  tc.queue[0].remaining -= C.TICK;
  if (tc.queue[0].remaining > 0) return;
  tc.queue.shift();
  const v = {
    id: g.nextId++, type: "villager", owner: 1, task: "idle", carry: 0,
    x: tc.x - C.TC_SIZE / 2 - 0.2, y: tc.y + C.TC_SIZE / 2 + 0.2,
    target: null, phase: 0, num: g.nextNum++,
  };
  g.ents.set(v.id, v);
  emit(g, "spawn", { eid: v.id });
  // Trained villagers walk to the rally point, then gather the forest there.
  if (tc.rally) {
    v.task = "to_rally";
    v.tx = tc.rally.x; v.ty = tc.rally.y;
    v.rallyTarget = tc.rally.target_id;
  }
}

// Construction: count active builders each tick, accrue points by the real
// multi-builder formula (3*T1/(n+2) total time), complete at T1 points.
function stepCamp(g, camp) {
  if (camp.built) return;
  let n = 0;
  for (const e of g.ents.values()) {
    if (e.type === "villager" && e.task === "building" && e.target === camp.id) n++;
  }
  if (!n) return;
  camp.progress += C.BUILD_RATE(n) * C.TICK;
  if (camp.progress >= C.BUILD_TIME_LUMBER_CAMP) {
    camp.built = true;
    emit(g, "built", { eid: camp.id, n });
  }
}

// --------------------------------------------------------------- helpers
function dist(a, b, x, y) { return Math.hypot(a - x, b - y); }

function dropsites(g) {
  const out = [];
  for (const e of g.ents.values()) {
    if (e.type === "town_center") out.push({ e, half: C.TC_SIZE / 2 });
    else if (e.type === "lumber_camp" && e.built) out.push({ e, half: C.CAMP_SIZE / 2 });
  }
  return out;
}

function nearestDrop(g, x, y) {
  let best = null, bd = Infinity;
  for (const d of dropsites(g)) {
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

// Tree choice with soft crowding: villagers prefer a free tree nearby over
// sharing an occupied one (observed in the capture: trained villager #2
// bounced off the occupied rally tree to the free straggler next to it).
function treeCap(e) { return Math.min(e.spots ?? 4, C.TREE_CAP); }

// Nearest tree with a free gather spot. Crowding is handled physically by
// the face/spot capacity model — no artificial distance penalty (one caused
// endgame villagers to skip near half-occupied trees for far empty ones).
function nearestTree(g, x, y) {
  let best = null, bs = Infinity;
  for (const e of g.ents.values()) {
    if (e.type !== "tree" || e.wood <= 0 || e.gatherers >= treeCap(e)) continue;
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
function assignBuildSpot(g, v, camp) {
  const dx = v.x - camp.x, dy = v.y - camp.y;
  const n = (camp.builders = (camp.builders ?? 0) + 1);
  const off = (n - 1 - 1) * 0.45;               // -0.45, 0, +0.45 ...
  if (Math.abs(dy) >= Math.abs(dx)) {
    v.ty = camp.y + Math.sign(dy || -1) * C.BUILD_REACH;
    v.tx = camp.x + off;
  } else {
    v.tx = camp.x + Math.sign(dx) * C.BUILD_REACH;
    v.ty = camp.y + off;
  }
}

// Assign villager to gather a specific tree (or nearest if id missing/empty).
// A directly-targeted tree that is already crowded also falls through to the
// nearest-with-space choice (rally tree behavior seen in the capture).
// Stand on a free, unoccupied face tile of the tree (orthogonal neighbor),
// pulled in to gather reach. Faces are exclusive — the physical spot model.
function takeFace(g, v, tree) {
  const tx0 = Math.floor(tree.x), ty0 = Math.floor(tree.y);
  tree.faceUsed ??= new Set();
  const faces = [];
  [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([dx, dy], i) => {
    if (g.blocked.has(`${tx0 + dx},${ty0 + dy}`)) return;
    if (tree.faceUsed.has(i)) return;
    faces.push({ i, x: tree.x + dx * C.GATHER_REACH, y: tree.y + dy * C.GATHER_REACH });
  });
  if (!faces.length) return false;
  faces.sort((a, b) => dist(a.x, a.y, v.x, v.y) - dist(b.x, b.y, v.x, v.y));
  tree.faceUsed.add(faces[0].i);
  v.face = faces[0].i;
  v.tx = faces[0].x;
  v.ty = faces[0].y;
  return true;
}

function assignGather(g, v, treeId) {
  releaseTree(g, v);
  let tree = treeId != null ? g.ents.get(treeId) : null;
  const direct = tree && tree.type === "tree" && tree.wood > 0
                 && tree.gatherers < treeCap(tree);
  if (!direct) {
    tree = nearestTree(g, v.x, v.y);
    if (tree) {
      emit(g, "retarget", { eid: v.id, num: v.num,
                            from: [+v.x.toFixed(1), +v.y.toFixed(1)],
                            tree: tree.id,
                            d: +dist(tree.x, tree.y, v.x, v.y).toFixed(2) });
    }
  }
  if (!tree) { v.task = v.carry > 0 ? "to_drop" : "idle"; return; }
  if (!takeFace(g, v, tree)) { v.task = v.carry > 0 ? "to_drop" : "idle"; return; }
  tree.gatherers++;
  v.target = tree.id;
  v.task = "to_tree";
  v.dropT = null;
}

function releaseTree(g, v) {
  if (v.target != null) {
    const tr = g.ents.get(v.target);
    if (tr && tr.type === "tree") {
      if (tr.gatherers > 0) tr.gatherers--;
      if (v.face != null) tr.faceUsed?.delete(v.face);
    }
  }
  v.target = null;
  v.face = null;
}

// --------------------------------------------------------------- villager FSM
function stepVill(g, v) {
  switch (v.task) {
    case "to_build": {
      const camp = g.ents.get(v.target);
      if (!camp) { v.task = "idle"; return; }
      if (camp.built) {                 // group auto-gather: nearest available
        const tr = nearestTree(g, v.x, v.y);
        assignGather(g, v, tr ? tr.id : null);
        return;
      }
      if (moveAlong(g, v, v.tx, v.ty)) v.task = "building";
      return;
    }
    case "building": {
      const camp = g.ents.get(v.target);
      if (!camp) { v.task = "idle"; return; }
      if (camp.built) {
        const tr = nearestTree(g, v.x, v.y);
        assignGather(g, v, tr ? tr.id : null);
        return;
      }
      // construction points accrue in stepCamp (multi-builder formula)
      return;
    }
    case "to_rally": {
      if (moveAlong(g, v, v.tx, v.ty)) assignGather(g, v, v.rallyTarget);
      return;
    }
    case "to_tree": {
      const tree = g.ents.get(v.target);
      if (!tree || tree.wood <= 0) { assignGather(g, v, null); return; }
      if (moveAlong(g, v, v.tx, v.ty)) { v.task = "settle"; v.phase = C.SETTLE_TIME; }
      return;
    }
    case "settle": {
      const tree = g.ents.get(v.target);
      if (!tree) { v.task = v.carry > 0 ? "to_drop" : "idle"; return; }
      v.phase -= C.TICK;
      if (v.phase <= 0) {
        // Felling happens once per TREE (first villager cuts it down);
        // later arrivals and repeat trips gather immediately.
        if (tree.felled) { v.task = "gather"; }
        else { v.task = "fell"; v.phase = C.FELL_TIME; }
      }
      return;
    }
    case "fell": {
      const tree = g.ents.get(v.target);
      if (!tree || tree.wood <= 0) { assignGather(g, v, null); return; }
      if (tree.felled) { v.task = "gather"; return; }
      v.phase -= C.TICK;
      if (v.phase <= 0) { tree.felled = true; emit(g, "tree_felled", { eid: tree.id }); v.task = "gather"; }
      return;
    }
    case "gather": {
      const tree = g.ents.get(v.target);
      if (!tree || tree.wood <= 0) {
        releaseTree(g, v);
        v.task = v.carry > 0 ? "to_drop" : "to_tree_next";
        return;
      }
      const take = Math.min(C.GATHER_RATE * C.TICK, C.CARRY_CAP - v.carry, tree.wood);
      v.carry += take; tree.wood -= take;
      if (tree.wood <= 1e-9) {
        tree.wood = 0;
        emit(g, "tree_empty", { eid: tree.id });
        recomputeObstacles(g);       // empty tree stops blocking movement/spots
      }
      if (v.carry >= C.CARRY_CAP - 1e-9) { v.carry = C.CARRY_CAP; v.task = "to_drop"; }
      return;
    }
    case "to_tree_next": {           // tree emptied with no load: find a new one
      assignGather(g, v, null);
      return;
    }
    case "to_drop": {
      if (!v.dropT) {
        const d = nearestDrop(g, v.x, v.y);
        if (!d) return;              // no dropsite yet (camp still building)
        v.dropT = dropStand(g, d, v);
        if (!v.dropT) return;        // dropsite fully walled in
      }
      if (moveAlong(g, v, v.dropT[0], v.dropT[1])) {
        v.dropT = null;
        g.wood += v.carry; g.collected += v.carry;
        emit(g, "deposit", { eid: v.id, amount: +v.carry.toFixed(2) });
        v.carry = 0;
        const tree = v.target != null ? g.ents.get(v.target) : null;
        if (tree && tree.type === "tree" && tree.wood > 0) {
          v.task = "to_tree";        // same tree still has wood: go back
        } else {
          assignGather(g, v, null);  // retarget to nearest non-empty tree
        }
      }
      return;
    }
    default: return;                 // idle
  }
}
