// Per-unit obstacle-aware pursuit pathing (AOE2X_EXP_CHASE_PATH=grid).
//
// The real game plans a route on its obstruction grid before walking; this
// engine historically had no plan step at all -- a chaser beelines at its
// target and reacts body-by-body, which presses it onto the kiting ball at
// partial speed (the 12v21 forensics, docs/HCC_CHASER_MOBILITY_2026-08-07.md).
// This module is the missing plan step, per unit, against the actual bodies:
//
//   * obstacles = the map's static obstruction cells plus enemy collision
//     boxes except the pursuit target (walking into the target is the catch);
//     friendly crowd bodies stay dynamic in local avoidance/collision;
//   * a coarse A* over 0.25-tile cells, 8-connected, octile heuristic,
//     deterministic tie-breaks (cell index order);
//   * straight line clear -> no plan, the caller keeps its live tracking;
//   * target cell unreachable -> best-effort: path toward the closest
//     reachable approach, and when no approach improves on where the unit
//     stands, STAND STILL -- the tape's stopped-at-clearance chasers;
//   * the plan yields one waypoint a couple of tiles ahead; execution stays
//     with the ordinary movement/collision layers underneath.
//
// Everything is a pure function of this tick's positions. No RNG, no clock.
import {
  attackReach,
  collisionRadius,
  MELEE_CONTACT_TOLERANCE_TILES,
  outlineRadius,
} from "./targeting.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "./pair-interactions.js";
import { areAllies, areOpponents } from "./diplomacy.js";

const CELL_TILES = 0.25;
// One waypoint this far along the path (in cells) is handed to the walker.
const WAYPOINT_LOOKAHEAD_CELLS = 8; // 2.0 tiles
// A* node budget. The grid is 64x64 = 4096 cells on the 16x16 recording map;
// the budget only exists so a degenerate map cannot spin.
const MAX_EXPANSIONS = 8192;
const STRAIGHT_COST = 10;
const DIAGONAL_COST = 14;
const ROUTE_WAYPOINT_REACHED_TILES = CELL_TILES * 0.75;
const MAX_DEEP_CONTACT_DEGREE = 2;
const SLOT_OCCUPYING_CONTACT_KINDS = new Set([
  "allied-transit",
  "ranged-ingress",
  "enemy-transit",
  "engagement-contact",
]);
const ALLIED_SLOT_CONTACT_KINDS = new Set([
  "allied-transit",
  "ranged-ingress",
]);

function cellIndex(cx, cy, cols) {
  return cy * cols + cx;
}

function octile(ax, ay, bx, by) {
  const dx = Math.abs(ax - bx);
  const dy = Math.abs(ay - by);
  return dx > dy
    ? STRAIGHT_COST * (dx - dy) + DIAGONAL_COST * dy
    : STRAIGHT_COST * (dy - dx) + DIAGONAL_COST * dx;
}

function obstacleRadius(body) {
  const explicit = body?.radius ?? body?.collisionRadius ?? body?.collision_radius;
  if (explicit === undefined) return collisionRadius(body);
  if (!Number.isFinite(explicit) || explicit <= 0) {
    throw new RangeError("path obstacle radius must be positive and finite");
  }
  return explicit;
}

// Blocked-cell grid for ONE mover: a cell is blocked when placing the mover's
// centre there would overlap an obstacle body (Chebyshev, radius sum -- the
// same test the collision solver applies).
function buildBlockedGrid(mover, obstacles, cols, rows, options = {}) {
  const blocked = new Uint8Array(cols * rows);
  const moverRadius = collisionRadius(mover);
  const pairInteractions = options.pairInteractions
    ?? createPairInteractionSnapshot();
  for (const body of obstacles) {
    const dynamicEnemy = body.owner !== undefined && areOpponents(body, mover);
    const interaction = dynamicEnemy
      ? resolvePairInteraction(mover, body, pairInteractions)
      : null;
    if (interaction && !interaction.pathObstructs) continue;
    const reach = interaction?.collisionExtent ?? moverRadius + obstacleRadius(body);
    const loX = Math.max(0, Math.floor((body.x - reach) / CELL_TILES - 0.5) + 1);
    const hiX = Math.min(cols - 1, Math.ceil((body.x + reach) / CELL_TILES - 0.5) - 1);
    const loY = Math.max(0, Math.floor((body.y - reach) / CELL_TILES - 0.5) + 1);
    const hiY = Math.min(rows - 1, Math.ceil((body.y + reach) / CELL_TILES - 0.5) - 1);
    for (let cy = loY; cy <= hiY; cy += 1) {
      for (let cx = loX; cx <= hiX; cx += 1) {
        const centreX = (cx + 0.5) * CELL_TILES;
        const centreY = (cy + 0.5) * CELL_TILES;
        if (Math.max(Math.abs(centreX - body.x), Math.abs(centreY - body.y))
          < reach) {
          blocked[cellIndex(cx, cy, cols)] = 1;
        }
      }
    }
  }
  return blocked;
}

function toCell(value, limit) {
  return Math.max(0, Math.min(limit - 1, Math.floor(value / CELL_TILES)));
}

// Straight-line clearance over the blocked grid (conservative supercover walk).
function lineClear(blocked, cols, ax, ay, bx, by) {
  const steps = Math.max(Math.abs(bx - ax), Math.abs(by - ay));
  if (steps === 0) return true;
  for (let i = 1; i <= steps; i += 1) {
    const cx = Math.round(ax + ((bx - ax) * i) / steps);
    const cy = Math.round(ay + ((by - ay) * i) / steps);
    if (blocked[cellIndex(cx, cy, cols)]) return false;
  }
  return true;
}

// Binary min-heap keyed on (f, h, index) for deterministic pops.
function heapPush(heap, node) {
  heap.push(node);
  let i = heap.length - 1;
  while (i > 0) {
    const parent = (i - 1) >> 1;
    if (compare(heap[parent], heap[i]) <= 0) break;
    [heap[parent], heap[i]] = [heap[i], heap[parent]];
    i = parent;
  }
}

function compare(a, b) {
  if (a.f !== b.f) return a.f - b.f;
  if (a.h !== b.h) return a.h - b.h;
  return a.index - b.index;
}

function heapPop(heap) {
  const top = heap[0];
  const last = heap.pop();
  if (heap.length > 0) {
    heap[0] = last;
    let i = 0;
    for (;;) {
      const left = 2 * i + 1;
      const right = left + 1;
      let smallest = i;
      if (left < heap.length && compare(heap[left], heap[smallest]) < 0) smallest = left;
      if (right < heap.length && compare(heap[right], heap[smallest]) < 0) smallest = right;
      if (smallest === i) break;
      [heap[i], heap[smallest]] = [heap[smallest], heap[i]];
      i = smallest;
    }
  }
  return top;
}

const NEIGHBORS = Object.freeze([
  [1, 0, STRAIGHT_COST], [-1, 0, STRAIGHT_COST],
  [0, 1, STRAIGHT_COST], [0, -1, STRAIGHT_COST],
  [1, 1, DIAGONAL_COST], [1, -1, DIAGONAL_COST],
  [-1, 1, DIAGONAL_COST], [-1, -1, DIAGONAL_COST],
]);

// Plan a walk aim for `mover` toward `target` around `obstacles`.
// Returns:
//   null                     -- straight line is clear; keep live tracking
//   { stand: true }          -- no reachable progress; stand still
//   { x, y }                 -- next waypoint along the planned path (tiles)
function planGridAim(mover, target, obstacles, map, enterBlockedGoal, options = {}) {
  const cols = Math.max(1, Math.round(map.width / CELL_TILES));
  const rows = Math.max(1, Math.round(map.height / CELL_TILES));
  const blocked = buildBlockedGrid(mover, obstacles, cols, rows, options);

  const startX = toCell(mover.x, cols);
  const startY = toCell(mover.y, rows);
  const goalX = toCell(target.x, cols);
  const goalY = toCell(target.y, rows);
  // Continuous collision has already established that the mover's exact
  // position is legal. Its coarse cell centre can nevertheless fall inside
  // inflated obstacle geometry, especially at obstacle corners. Never trap
  // the mover inside that rasterization error.
  const startIndex = cellIndex(startX, startY, cols);
  const startCellWasBlocked = blocked[startIndex] === 1;
  blocked[startIndex] = 0;
  if (lineClear(blocked, cols, startX, startY, goalX, goalY)) return null;

  const goalIndex = cellIndex(goalX, goalY, cols);
  const gScore = new Map([[startIndex, 0]]);
  const cameFrom = new Map();
  const closed = new Set();
  const startH = octile(startX, startY, goalX, goalY);
  const heap = [{ index: startIndex, g: 0, h: startH, f: startH }];
  let best = { index: startIndex, h: startH };
  let expansions = 0;

  while (heap.length > 0 && expansions < MAX_EXPANSIONS) {
    const current = heapPop(heap);
    if (closed.has(current.index)) continue;
    closed.add(current.index);
    expansions += 1;
    if (current.h < best.h
      || (current.h === best.h && current.index < best.index)) {
      best = { index: current.index, h: current.h };
    }
    if (current.index === goalIndex) { best = current; break; }
    const cx = current.index % cols;
    const cy = (current.index - cx) / cols;
    for (const [dx, dy, cost] of NEIGHBORS) {
      const nx = cx + dx;
      const ny = cy + dy;
      if (nx < 0 || nx >= cols || ny < 0 || ny >= rows) continue;
      const nIndex = cellIndex(nx, ny, cols);
      if (closed.has(nIndex)) continue;
      // The goal cell is enterable even when covered by clutter near the
      // target; every other blocked cell is not.
      if (blocked[nIndex] && (!enterBlockedGoal || nIndex !== goalIndex)) continue;
      // No corner cutting between two blocked orthogonals.
      if (dx !== 0 && dy !== 0) {
        if (blocked[cellIndex(cx + dx, cy, cols)]
          || blocked[cellIndex(cx, cy + dy, cols)]) continue;
      }
      const tentative = current.g + cost;
      const known = gScore.get(nIndex);
      if (known !== undefined && known <= tentative) continue;
      gScore.set(nIndex, tentative);
      cameFrom.set(nIndex, current.index);
      const h = octile(nx, ny, goalX, goalY);
      heapPush(heap, { index: nIndex, g: tentative, h, f: tentative + h });
    }
  }

  if (best.index === startIndex) {
    return startCellWasBlocked && enterBlockedGoal
      ? null
      : Object.freeze({ stand: true });
  }

  // Rebuild the path start -> best, then take the lookahead waypoint.
  const path = [];
  for (let index = best.index; index !== undefined; index = cameFrom.get(index)) {
    path.push(index);
    if (index === startIndex) break;
  }
  path.reverse();
  const waypointIndex = path[Math.min(WAYPOINT_LOOKAHEAD_CELLS, path.length - 1)];
  const wx = (waypointIndex % cols + 0.5) * CELL_TILES;
  const wy = (Math.floor(waypointIndex / cols) + 0.5) * CELL_TILES;
  return Object.freeze({ x: wx, y: wy });
}


// Plan toward an unoccupied move-order coordinate. Unlike pursuit, a blocked
// goal cell is not enterable: the best reachable approach is used instead.
export function planMoveAim(mover, goal, obstacles, map, options = {}) {
  const planned = planGridAim(
    mover, goal, [...(map.obstacles ?? []), ...obstacles], map, false, options,
  );
  if (planned?.stand !== true || !obstacles.some(({ owner }) => owner !== undefined)) {
    return planned;
  }
  // A temporary ring of moving bodies must not become a permanent movement
  // order. Retry against static geometry only and let pairwise collision and
  // local avoidance resolve the live escape direction on this tick.
  return planGridAim(
    mover,
    goal,
    [
      ...(map.obstacles ?? []),
      ...obstacles.filter(({ owner }) => owner === undefined),
    ],
    map,
    false,
    options,
  );
}


export function planChaseAim(mover, target, obstacles, map, options = {}) {
  const blocking = obstacles.filter((body) => (
    body.owner === undefined || areOpponents(body, mover)
  ));
  const planned = planGridAim(
    mover, target, [...(map.obstacles ?? []), ...blocking], map, true, options,
  );
  if (planned?.stand !== true || blocking.length === 0) return planned;
  // Dynamic bodies can move on the very next tick. If only those bodies make
  // A* declare the mover boxed in, continue live pursuit and let the local
  // collision layers handle this tick. Static map geometry may still produce
  // a genuine stand result.
  return planGridAim(mover, target, map.obstacles ?? [], map, true, options);
}


function addHardBody(blocked, body, reach, cols, rows) {
  const loX = Math.max(0, Math.floor((body.x - reach) / CELL_TILES - 0.5) + 1);
  const hiX = Math.min(cols - 1, Math.ceil((body.x + reach) / CELL_TILES - 0.5) - 1);
  const loY = Math.max(0, Math.floor((body.y - reach) / CELL_TILES - 0.5) + 1);
  const hiY = Math.min(rows - 1, Math.ceil((body.y + reach) / CELL_TILES - 0.5) - 1);
  for (let cy = loY; cy <= hiY; cy += 1) {
    for (let cx = loX; cx <= hiX; cx += 1) {
      const centreX = (cx + 0.5) * CELL_TILES;
      const centreY = (cy + 0.5) * CELL_TILES;
      if (Math.max(Math.abs(centreX - body.x), Math.abs(centreY - body.y)) < reach) {
        blocked[cellIndex(cx, cy, cols)] = 1;
      }
    }
  }
}


function addAlliedBody(alliedOccupancy, alliedHardOccupancy, congestion,
  body, reach, hard, cols, rows) {
  const loX = Math.max(0, Math.floor((body.x - reach) / CELL_TILES - 0.5) + 1);
  const hiX = Math.min(cols - 1, Math.ceil((body.x + reach) / CELL_TILES - 0.5) - 1);
  const loY = Math.max(0, Math.floor((body.y - reach) / CELL_TILES - 0.5) + 1);
  const hiY = Math.min(rows - 1, Math.ceil((body.y + reach) / CELL_TILES - 0.5) - 1);
  for (let cy = loY; cy <= hiY; cy += 1) {
    for (let cx = loX; cx <= hiX; cx += 1) {
      const centreX = (cx + 0.5) * CELL_TILES;
      const centreY = (cy + 0.5) * CELL_TILES;
      const penetration = reach - Math.max(
        Math.abs(centreX - body.x),
        Math.abs(centreY - body.y),
      );
      if (penetration <= 0) continue;
      const index = cellIndex(cx, cy, cols);
      alliedOccupancy[index] = Math.min(255, alliedOccupancy[index] + 1);
      if (hard) {
        alliedHardOccupancy[index] = Math.min(255, alliedHardOccupancy[index] + 1);
      }
      congestion[index] += Math.ceil(penetration / CELL_TILES) * STRAIGHT_COST;
    }
  }
}


function contactSlotUsage(pairInteractions) {
  const deepDegree = new Map();
  const allied = new Set();
  for (const reservation of pairInteractions.contactReservations.values()) {
    if (!SLOT_OCCUPYING_CONTACT_KINDS.has(reservation.kind)) continue;
    for (const referenceId of [reservation.leftId, reservation.rightId]) {
      deepDegree.set(referenceId, (deepDegree.get(referenceId) ?? 0) + 1);
      if (ALLIED_SLOT_CONTACT_KINDS.has(reservation.kind)) allied.add(referenceId);
    }
  }
  return { deepDegree, allied };
}


function alliedTransitSlotAvailable(mover, body, slots) {
  return !slots.allied.has(mover.referenceId)
    && !slots.allied.has(body.referenceId)
    && (slots.deepDegree.get(mover.referenceId) ?? 0) < MAX_DEEP_CONTACT_DEGREE
    && (slots.deepDegree.get(body.referenceId) ?? 0) < MAX_DEEP_CONTACT_DEGREE;
}


// Persistent pursuit differs from the legacy one-waypoint planner in how it
// treats FRIENDLY bodies. They are not hard walls: AoE2's dat-derived friendly
// shrink and this engine's pair interactions can permit a shallow crossing.
// Instead, a candidate cell pays the geometric clearance distance needed to
// leave every allied body it penetrates. One ally can therefore remain the
// shortest physical route; the costs of a dense pack add and make walking
// around the connected crowd cheaper without a roster-size or unit-name gate.
function buildPersistentGrid(mover, target, obstacles, cols, rows, options = {}) {
  const hardBlocked = new Uint8Array(cols * rows);
  const congestion = new Uint32Array(cols * rows);
  const alliedOccupancy = new Uint8Array(cols * rows);
  const alliedHardOccupancy = new Uint8Array(cols * rows);
  const moverRadius = collisionRadius(mover);
  const pairInteractions = options.pairInteractions
    ?? createPairInteractionSnapshot();
  // Ordinary pursuit may rely on a non-obstructing contact reservation to
  // pass through a friendly lane. Once the final movement solver has already
  // demonstrated that such a lane is not producing progress, recovery must
  // plan against the reservation's real collision surface instead of calling
  // the same straight line clear again. This is an evidence-of-blockage mode,
  // not a new physical extent: it uses the exact collision surface already
  // published by the pair authority.
  const includeNonObstructingContacts
    = options.includeNonObstructingContacts === true;
  const contactSlots = contactSlotUsage(pairInteractions);
  for (const body of [...(options.mapObstacles ?? []), ...obstacles]) {
    if (body.referenceId === mover.referenceId
        || body.referenceId === target.referenceId) continue;
    const dynamic = body.owner !== undefined;
    const interaction = dynamic
      ? resolvePairInteraction(mover, body, pairInteractions)
      : null;
    if (interaction && !interaction.pathObstructs
        && !includeNonObstructingContacts) continue;
    const reach = interaction?.collisionExtent ?? moverRadius + obstacleRadius(body);
    if (!dynamic || !areAllies(body, mover)) {
      addHardBody(hardBlocked, body, reach, cols, rows);
      continue;
    }
    // A planner may admit one ally only when the unified contact authority
    // can actually publish that pair on this tick. If either body already
    // owns its one allied lane (or its two total deep-contact slots), the
    // next ally is route geometry, not a second simultaneous transit. An
    // existing releasing surface is likewise hard until separation.
    const hard = interaction.kind !== "hard"
      || !alliedTransitSlotAvailable(mover, body, contactSlots);
    // Preserve allied obstruction as crowd pressure rather than static wall
    // geometry. Normal routes still block it under the same slot rules; a
    // mover already inside the rasterized crowd may only traverse cells whose
    // pressure does not increase until it reaches free space.
    addAlliedBody(
      alliedOccupancy,
      alliedHardOccupancy,
      congestion,
      body,
      reach,
      hard,
      cols,
      rows,
    );
  }
  const blocked = new Uint8Array(cols * rows);
  const crowdBlocked = new Uint8Array(cols * rows);
  for (let index = 0; index < alliedOccupancy.length; index += 1) {
    if (alliedHardOccupancy[index] >= 1 || alliedOccupancy[index] >= 2) {
      crowdBlocked[index] = 1;
    }
    if (hardBlocked[index] || crowdBlocked[index]) blocked[index] = 1;
  }
  return {
    blocked,
    hardBlocked,
    crowdBlocked,
    alliedOccupancy,
    alliedHardOccupancy,
    congestion,
    pairInteractions,
  };
}


function lineHasPersistentObstruction(blocked, congestion, cols, ax, ay, bx, by) {
  const steps = Math.max(Math.abs(bx - ax), Math.abs(by - ay));
  if (steps === 0) return false;
  for (let i = 1; i <= steps; i += 1) {
    const cx = Math.round(ax + ((bx - ax) * i) / steps);
    const cy = Math.round(ay + ((by - ay) * i) / steps);
    const index = cellIndex(cx, cy, cols);
    // A single transit-eligible ally is a cost if A* is already routing, not
    // a reason to abandon a clear direct pursuit. Only hard geometry (which
    // includes simultaneous penetration of two allies) starts a detour.
    if (blocked[index]) return true;
  }
  return false;
}


function pursuitStopSpec(mover, target, pairInteractions) {
  if (mover?.mechanics?.ranged) {
    return Object.freeze({
      metric: "euclidean",
      reach: outlineRadius(mover) + outlineRadius(target) + attackReach(mover),
    });
  }
  const range = mover?.mechanics?.attack_range_tiles ?? 0;
  if (!Number.isFinite(range) || range < 0) {
    throw new RangeError("persistent chase attack range must be nonnegative and finite");
  }
  const interaction = resolvePairInteraction(mover, target, pairInteractions);
  const stop = interaction.kind === "enemy-transit"
    ? range
    : Math.max(range, MELEE_CONTACT_TOLERANCE_TILES);
  return Object.freeze({
    metric: "chebyshev",
    reach: interaction.attackSurfaceExtent + stop,
  });
}


function inGoalEnvelope(cx, cy, target, stopSpec) {
  const x = (cx + 0.5) * CELL_TILES;
  const y = (cy + 0.5) * CELL_TILES;
  const dx = Math.abs(x - target.x);
  const dy = Math.abs(y - target.y);
  const distance = stopSpec.metric === "euclidean" ? Math.hypot(dx, dy) : Math.max(dx, dy);
  return distance <= stopSpec.reach + 1e-12;
}


function envelopeHeuristic(cx, cy, target, stopSpec) {
  // Dijkstra for a circular projectile envelope. A zero heuristic is exact,
  // deterministic, and comfortably bounded by the 64x64 golden map grid.
  // The melee box-envelope keeps the tighter admissible octile heuristic.
  if (stopSpec.metric === "euclidean") return 0;
  const x = (cx + 0.5) * CELL_TILES;
  const y = (cy + 0.5) * CELL_TILES;
  const dx = Math.max(0, Math.abs(x - target.x) - stopSpec.reach);
  const dy = Math.max(0, Math.abs(y - target.y) - stopSpec.reach);
  // Floor keeps this heuristic admissible for a goal envelope whose edge may
  // fall between cell centres.
  return octile(
    0,
    0,
    Math.floor(dx / CELL_TILES),
    Math.floor(dy / CELL_TILES),
  );
}


function freezePersistentRoute(target, path, cols) {
  const waypoints = Object.freeze(path.slice(1).map((index) => Object.freeze({
    x: (index % cols + 0.5) * CELL_TILES,
    y: (Math.floor(index / cols) + 0.5) * CELL_TILES,
  })));
  return Object.freeze({
    targetReferenceId: target.referenceId,
    targetX: target.x,
    targetY: target.y,
    waypoints,
    waypointIndex: 0,
  });
}


function detourPrefix(path, blocked, congestion, cols, targetX, targetY) {
  // A pursuit target moves continuously. Persist only until the path has
  // cleared the obstruction that forced the detour, then hand control back to
  // live target tracking. Persisting the complete A* path would chase the
  // target's old position after every kite beat.
  for (let pathIndex = 1; pathIndex < path.length; pathIndex += 1) {
    const index = path[pathIndex];
    const cx = index % cols;
    const cy = (index - cx) / cols;
    if (!lineHasPersistentObstruction(
      blocked, congestion, cols, cx, cy, targetX, targetY,
    )) {
      return path.slice(0, pathIndex + 1);
    }
  }
  return path;
}


// Return a complete, persistent detour corridor. `null` deliberately means
// the live direct route is clear; the caller should continue tracking the
// moving target. Unlike planChaseAim, this plans to the actor's physical stop
// envelope and includes geometric allied congestion in the route cost.
export function planPersistentChaseRoute(mover, target, obstacles, map, options = {}) {
  const cols = Math.max(1, Math.round(map.width / CELL_TILES));
  const rows = Math.max(1, Math.round(map.height / CELL_TILES));
  const {
    blocked,
    hardBlocked,
    crowdBlocked,
    alliedOccupancy,
    alliedHardOccupancy,
    congestion,
    pairInteractions,
  } = buildPersistentGrid(
    mover,
    target,
    obstacles,
    cols,
    rows,
    { ...options, mapObstacles: map.obstacles ?? [] },
  );
  const startX = toCell(mover.x, cols);
  const startY = toCell(mover.y, rows);
  const targetX = toCell(target.x, cols);
  const targetY = toCell(target.y, rows);
  const startIndex = cellIndex(startX, startY, cols);
  blocked[startIndex] = 0;
  congestion[startIndex] = 0;
  const stopSpec = pursuitStopSpec(mover, target, pairInteractions);
  if (inGoalEnvelope(startX, startY, target, stopSpec)) return null;
  if (!lineHasPersistentObstruction(
    blocked, congestion, cols, startX, startY, targetX, targetY,
  )) return null;

  const gScore = new Map([[startIndex, 0]]);
  const cameFrom = new Map();
  const closed = new Set();
  const startH = envelopeHeuristic(startX, startY, target, stopSpec);
  const heap = [{ index: startIndex, g: 0, h: startH, f: startH }];
  let goalIndex = null;
  let expansions = 0;
  const crowdPressure = (index) => (
    alliedHardOccupancy[index] * 64 + alliedOccupancy[index]
  );
  const canEnterFrom = (fromIndex, toIndex) => {
    if (hardBlocked[toIndex]) return false;
    if (!crowdBlocked[toIndex]) return true;
    // Once the route leaves a compressed allied basin it cannot re-enter it.
    // Inside the basin it may cross equal-pressure raster cells, but it may
    // never deepen the current allied overlap to escape.
    if (!crowdBlocked[fromIndex]) return false;
    return crowdPressure(toIndex) <= crowdPressure(fromIndex);
  };
  while (heap.length > 0 && expansions < MAX_EXPANSIONS) {
    const current = heapPop(heap);
    if (closed.has(current.index)) continue;
    closed.add(current.index);
    expansions += 1;
    const cx = current.index % cols;
    const cy = (current.index - cx) / cols;
    if (inGoalEnvelope(cx, cy, target, stopSpec)) {
      goalIndex = current.index;
      break;
    }
    for (const [dx, dy, cost] of NEIGHBORS) {
      const nx = cx + dx;
      const ny = cy + dy;
      if (nx < 0 || nx >= cols || ny < 0 || ny >= rows) continue;
      const nIndex = cellIndex(nx, ny, cols);
      if (closed.has(nIndex) || !canEnterFrom(current.index, nIndex)) continue;
      if (dx !== 0 && dy !== 0
          && (!canEnterFrom(current.index, cellIndex(cx + dx, cy, cols))
            || !canEnterFrom(current.index, cellIndex(cx, cy + dy, cols)))) continue;
      const tentative = current.g + cost + congestion[nIndex];
      const known = gScore.get(nIndex);
      if (known !== undefined && known <= tentative) continue;
      gScore.set(nIndex, tentative);
      cameFrom.set(nIndex, current.index);
      const h = envelopeHeuristic(nx, ny, target, stopSpec);
      heapPush(heap, { index: nIndex, g: tentative, h, f: tentative + h });
    }
  }
  if (goalIndex === null) return Object.freeze({ stand: true });
  const path = [];
  for (let index = goalIndex; index !== undefined; index = cameFrom.get(index)) {
    path.push(index);
    if (index === startIndex) break;
  }
  path.reverse();
  return freezePersistentRoute(
    target,
    detourPrefix(path, blocked, congestion, cols, targetX, targetY),
    cols,
  );
}


export function advancePersistentChaseRoute(mover, route) {
  if (!route || !Array.isArray(route.waypoints)) {
    throw new TypeError("persistent chase route with waypoints is required");
  }
  let waypointIndex = route.waypointIndex;
  while (waypointIndex < route.waypoints.length) {
    const waypoint = route.waypoints[waypointIndex];
    if (Math.hypot(waypoint.x - mover.x, waypoint.y - mover.y)
        > ROUTE_WAYPOINT_REACHED_TILES + 1e-12) break;
    waypointIndex += 1;
  }
  if (waypointIndex === route.waypointIndex) return route;
  return Object.freeze({ ...route, waypointIndex });
}


export function persistentRouteMotionStalled(before, after) {
  return Math.hypot(after.x - before.x, after.y - before.y) <= 1e-12;
}
