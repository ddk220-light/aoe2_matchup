// Per-unit obstacle-aware pursuit pathing (AOE2X_EXP_CHASE_PATH=grid).
//
// The real game plans a route on its obstruction grid before walking; this
// engine historically had no plan step at all -- a chaser beelines at its
// target and reacts body-by-body, which presses it onto the kiting ball at
// partial speed (the 12v21 forensics, docs/HCC_CHASER_MOBILITY_2026-08-07.md).
// This module is the missing plan step, per unit, against the actual bodies:
//
//   * obstacles = the map's static obstruction cells plus every living unit's
//     collision box EXCEPT the mover and its own pursuit target (walking into
//     the target is the catch);
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
import { collisionRadius } from "./targeting.js";

const CELL_TILES = 0.25;
// One waypoint this far along the path (in cells) is handed to the walker.
const WAYPOINT_LOOKAHEAD_CELLS = 8; // 2.0 tiles
// A* node budget. The grid is 64x64 = 4096 cells on the 16x16 recording map;
// the budget only exists so a degenerate map cannot spin.
const MAX_EXPANSIONS = 8192;
const STRAIGHT_COST = 10;
const DIAGONAL_COST = 14;

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
function buildBlockedGrid(mover, obstacles, cols, rows) {
  const blocked = new Uint8Array(cols * rows);
  const moverRadius = collisionRadius(mover);
  for (const body of obstacles) {
    const reach = moverRadius + obstacleRadius(body);
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
function planGridAim(mover, target, obstacles, map, enterBlockedGoal) {
  const cols = Math.max(1, Math.round(map.width / CELL_TILES));
  const rows = Math.max(1, Math.round(map.height / CELL_TILES));
  const blocked = buildBlockedGrid(mover, obstacles, cols, rows);

  const startX = toCell(mover.x, cols);
  const startY = toCell(mover.y, rows);
  const goalX = toCell(target.x, cols);
  const goalY = toCell(target.y, rows);
  if (lineClear(blocked, cols, startX, startY, goalX, goalY)) return null;

  const startIndex = cellIndex(startX, startY, cols);
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

  if (best.index === startIndex) return Object.freeze({ stand: true });

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
export function planMoveAim(mover, goal, obstacles, map) {
  return planGridAim(mover, goal, [...(map.obstacles ?? []), ...obstacles], map, false);
}


export function planChaseAim(mover, target, obstacles, map) {
  return planGridAim(mover, target, [...(map.obstacles ?? []), ...obstacles], map, true);
}
