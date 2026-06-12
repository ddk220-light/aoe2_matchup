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
  const g = {
    t: 0,
    ents,
    wood: scenario.players[0].start_wood,
    collected: 0,                  // cumulative wood delivered (the headline metric)
    pending: [...scenario.commands].sort((a, b) => a.t - b.t),
    events: [],
    ended: false,
    nextId: 10000,
  };
  recomputeTreeSpots(g);
  return g;
}

// A tree's gather capacity = its free orthogonal neighbor tiles (capture:
// trees walled in by forest + the camp footprint were never harvested; the
// rally tree capped at 2 because the camp blocks its east face).
function recomputeTreeSpots(g) {
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
      recomputeTreeSpots(g);       // the footprint blocks adjacent gather spots
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
    target: null, phase: 0,
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

function stepCamp(g, camp) {
  // Construction advances by the number of builders currently adjacent.
  if (camp.built) return;
  // builders are counted in stepVill via camp.buildContrib accumulation
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

function dropPoint(d, x, y) {
  const px = Math.max(d.e.x - d.half, Math.min(x, d.e.x + d.half));
  const py = Math.max(d.e.y - d.half, Math.min(y, d.e.y + d.half));
  return [px, py];
}

// Tree choice with soft crowding: villagers prefer a free tree nearby over
// sharing an occupied one (observed in the capture: trained villager #2
// bounced off the occupied rally tree to the free straggler next to it).
function treeCap(e) { return Math.min(e.spots ?? 4, C.TREE_CAP); }

function nearestTree(g, x, y, crowdPenalty = C.CROWD_PENALTY) {
  let best = null, bs = Infinity;
  for (const e of g.ents.values()) {
    if (e.type !== "tree" || e.wood <= 0 || e.gatherers >= treeCap(e)) continue;
    const score = dist(e.x, e.y, x, y) + crowdPenalty * e.gatherers;
    if (score < bs) { bs = score; best = e; }
  }
  return best;
}

function moveToward(e, tx, ty) {
  const dx = tx - e.x, dy = ty - e.y;
  const d = Math.hypot(dx, dy), s = C.VILL_SPEED * C.TICK;
  if (d <= s) { e.x = tx; e.y = ty; return true; }
  e.x += (dx / d) * s; e.y += (dy / d) * s;
  return false;
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
function assignGather(g, v, treeId) {
  let tree = treeId != null ? g.ents.get(treeId) : null;
  if (!tree || tree.type !== "tree" || tree.wood <= 0
      || tree.gatherers >= treeCap(tree))
    tree = nearestTree(g, v.x, v.y);
  if (!tree) { v.task = v.carry > 0 ? "to_drop" : "idle"; return; }
  if (v.target != null) {
    const old = g.ents.get(v.target);
    if (old && old.type === "tree" && old.gatherers > 0) old.gatherers--;
  }
  tree.gatherers++;
  v.target = tree.id;
  v.task = "to_tree";
  const ang = (tree.gatherers * 90 + (v.id % 4) * 25) * Math.PI / 180;
  v.tx = tree.x + Math.cos(ang) * C.GATHER_REACH;
  v.ty = tree.y + Math.sin(ang) * C.GATHER_REACH;
}

function releaseTree(g, v) {
  if (v.target != null) {
    const tr = g.ents.get(v.target);
    if (tr && tr.type === "tree" && tr.gatherers > 0) tr.gatherers--;
  }
}

// --------------------------------------------------------------- villager FSM
function stepVill(g, v) {
  switch (v.task) {
    case "to_build": {
      const camp = g.ents.get(v.target);
      if (!camp) { v.task = "idle"; return; }
      if (camp.built) {                 // group auto-gather: nearest by pure
        const tr = nearestTree(g, v.x, v.y, 0);   // distance, no spread penalty
        assignGather(g, v, tr ? tr.id : null);
        return;
      }
      if (moveToward(v, v.tx, v.ty)) v.task = "building";
      return;
    }
    case "building": {
      const camp = g.ents.get(v.target);
      if (!camp) { v.task = "idle"; return; }
      if (camp.built) {
        const tr = nearestTree(g, v.x, v.y, 0);
        assignGather(g, v, tr ? tr.id : null);
        return;
      }
      camp.progress += C.TICK;                    // one builder-second per tick-second
      if (camp.progress >= C.CAMP_BUILD_POINTS) {
        camp.built = true;
        camp.autoTreeId = null;   // each builder picks from its own stand spot
        emit(g, "built", { eid: camp.id });
      }
      return;
    }
    case "to_rally": {
      if (moveToward(v, v.tx, v.ty)) assignGather(g, v, v.rallyTarget);
      return;
    }
    case "to_tree": {
      const tree = g.ents.get(v.target);
      if (!tree || tree.wood <= 0) { releaseTree(g, v); assignGather(g, v, null); return; }
      if (moveToward(v, v.tx, v.ty)) { v.task = "settle"; v.phase = C.SETTLE_TIME; }
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
      if (!tree || tree.wood <= 0) { releaseTree(g, v); assignGather(g, v, null); return; }
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
      }
      if (v.carry >= C.CARRY_CAP - 1e-9) { v.carry = C.CARRY_CAP; v.task = "to_drop"; }
      return;
    }
    case "to_tree_next": {           // tree emptied with no load: find a new one
      releaseTree(g, v);
      assignGather(g, v, null);
      return;
    }
    case "to_drop": {
      const d = nearestDrop(g, v.x, v.y);
      if (!d) return;                // no dropsite yet (camp still building)
      const [px, py] = dropPoint(d, v.x, v.y);
      if (Math.hypot(px - v.x, py - v.y) <= C.DEPOSIT_REACH) {
        g.wood += v.carry; g.collected += v.carry;
        emit(g, "deposit", { eid: v.id, amount: +v.carry.toFixed(2) });
        v.carry = 0;
        const tree = v.target != null ? g.ents.get(v.target) : null;
        if (tree && tree.type === "tree" && tree.wood > 0) {
          v.task = "to_tree";        // same tree still has wood: go back
        } else {
          assignGather(g, v, null);  // retarget to nearest non-empty tree
        }
      } else moveToward(v, px, py);
      return;
    }
    default: return;                 // idle
  }
}
