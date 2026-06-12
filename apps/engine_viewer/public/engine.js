// Deterministic AoE2 economy engine — pure logic, no DOM. Consumed by the
// browser viewer (app.js) and the headless verifier (verify/verify.mjs).
import * as C from "./constants.js";

export function createGame(scenario) {
  const ents = new Map();
  for (const e of scenario.entities) ents.set(e.id, structuredClone(e));
  for (const e of ents.values()) {
    if (e.type === "villager" || e.type === "scout") {
      Object.assign(e, { task: "idle", carry: 0, tx: e.x, ty: e.y });
    }
    if (e.type === "town_center") Object.assign(e, { queue: [], rally: null });
    if (e.type === "tree") Object.assign(e, { felled: false });
  }
  return {
    t: 0,
    ents,
    wood: scenario.players[0].start_wood,
    pending: [...scenario.commands].sort((a, b) => a.t - b.t),
    events: [],
    ended: false,
    nextId: 10000,
  };
}

export function step(g) {
  g.t += C.TICK;
  applyCommands(g);
  for (const e of [...g.ents.values()]) {
    if (e.type === "town_center") stepTC(g, e);
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

function applyCommands(g) {
  while (g.pending.length && g.pending[0].t <= g.t) {
    const c = g.pending.shift();
    if (c.type === "order") {
      for (const id of c.unit_ids) {
        const u = g.ents.get(id);
        if (u) assignGather(g, u, c.target_id);
      }
    } else if (c.type === "gather_point") {
      const b = g.ents.get(c.building_id);
      if (b) b.rally = c.target_id;
    } else if (c.type === "queue") {
      const b = g.ents.get(c.building_id);
      if (b) b.queue.push({ remaining: c.train_time });
    } else if (c.type === "resign") {
      g.ended = true;
      emit(g, "end", {});
    }
  }
}

function stepTC(g, tc) {
  if (!tc.queue.length) return;
  tc.queue[0].remaining -= C.TICK;
  if (tc.queue[0].remaining > 0) return;
  tc.queue.shift();
  const v = {
    id: g.nextId++, type: "villager", owner: 1,
    task: "idle", carry: 0,
    x: tc.x - C.TC_SIZE / 2 - 0.2, y: tc.y + C.TC_SIZE / 2 + 0.2,
  };
  g.ents.set(v.id, v);
  emit(g, "spawn", { eid: v.id });
  const rallyTarget = tc.rally != null ? g.ents.get(tc.rally) : null;
  if (rallyTarget && rallyTarget.type === "tree") assignGather(g, v, tc.rally);
}

function angDiff(a, b) {
  const d = Math.abs(a - b) % (2 * Math.PI);
  return d > Math.PI ? 2 * Math.PI - d : d;
}

// Stand at the gather-reach circle point nearest the approach direction,
// zigzag-stepped 30° away from occupied slots (matches observed behavior:
// all gatherers end up on their walk-in side of the tree).
function assignGather(g, v, treeId) {
  const tree = g.ents.get(treeId);
  if (!tree || tree.type !== "tree") {
    v.task = v.carry > 0 ? "to_tc" : "idle";
    return;
  }
  v.target = treeId;
  v.task = "to_tree";
  const base = Math.atan2(v.y - tree.y, v.x - tree.x);
  const taken = [...g.ents.values()]
    .filter((o) => o !== v && o.type === "villager"
                   && o.target === treeId && o.slotAng != null)
    .map((o) => o.slotAng);
  const SEP = (25 * Math.PI) / 180;
  const STEP = (30 * Math.PI) / 180;
  let ang = base;
  for (let k = 1; taken.some((a) => angDiff(a, ang) < SEP) && k < 13; k++) {
    ang = base + (k % 2 ? Math.ceil(k / 2) : -Math.ceil(k / 2)) * STEP;
  }
  v.slotAng = ang;
  v.tx = tree.x + Math.cos(ang) * C.GATHER_REACH;
  v.ty = tree.y + Math.sin(ang) * C.GATHER_REACH;
}

function moveToward(e, tx, ty) {
  const dx = tx - e.x, dy = ty - e.y;
  const d = Math.hypot(dx, dy), s = C.VILL_SPEED * C.TICK;
  if (d <= s) { e.x = tx; e.y = ty; return true; }
  e.x += (dx / d) * s;
  e.y += (dy / d) * s;
  return false;
}

function tcDropPoint(g, e) {
  const tc = [...g.ents.values()].find((x) => x.type === "town_center");
  const h = C.TC_SIZE / 2;
  const px = Math.max(tc.x - h, Math.min(e.x, tc.x + h));
  const py = Math.max(tc.y - h, Math.min(e.y, tc.y + h));
  return { px, py };
}

function stepVill(g, v) {
  const tree = v.target != null ? g.ents.get(v.target) : null;
  if (v.task === "to_tree") {
    if (!tree) { v.task = v.carry > 0 ? "to_tc" : "idle"; return; }
    if (moveToward(v, v.tx, v.ty)) {
      v.task = "settle";
      v.settleLeft = C.SETTLE_TIME;
    }
  } else if (v.task === "settle") {
    if (!tree) { v.task = v.carry > 0 ? "to_tc" : "idle"; return; }
    v.settleLeft -= C.TICK;
    if (v.settleLeft <= 0) v.task = tree.felled ? "gather" : "fell";
  } else if (v.task === "fell") {
    if (!tree) { v.task = "idle"; return; }
    if (tree.felled) { v.task = "gather"; return; }
    tree.hp -= C.FELL_DPS * C.TICK;
    if (tree.hp <= 0) {
      tree.felled = true;
      emit(g, "tree_felled", { eid: tree.id });
      v.task = "gather";
    }
  } else if (v.task === "gather") {
    if (!tree || tree.wood <= 0) { v.task = v.carry > 0 ? "to_tc" : "idle"; return; }
    const take = Math.min(C.GATHER_RATE * C.TICK, C.CARRY_CAP - v.carry, tree.wood);
    v.carry += take;
    tree.wood -= take;
    if (tree.wood <= 1e-9) {
      tree.wood = 0;
      emit(g, "tree_empty", { eid: tree.id });
      g.ents.delete(tree.id);
      for (const o of g.ents.values()) {
        if (o.type === "villager" && o.target === tree.id) {
          o.task = o.carry > 0 ? "to_tc" : "idle";
          o.slotAng = null;
        }
      }
      return;
    }
    if (v.carry >= C.CARRY_CAP - 1e-9) { v.carry = C.CARRY_CAP; v.task = "to_tc"; }
  } else if (v.task === "to_tc") {
    const { px, py } = tcDropPoint(g, v);
    if (Math.hypot(px - v.x, py - v.y) <= C.DEPOSIT_REACH) {
      g.wood += v.carry;
      emit(g, "deposit", { eid: v.id, amount: +v.carry.toFixed(2) });
      v.carry = 0;
      if (v.target != null && g.ents.get(v.target)) assignGather(g, v, v.target);
      else v.task = "idle";
    } else {
      moveToward(v, px, py);
    }
  }
}
