/**
 * Playback engine - handles game state and action processing
 * Units move smoothly between command positions based on timing
 */

class Playback {
  constructor(data) {
    this.data = data;
    this.duration = data.match.duration_seconds;

    // Playback state
    this.currentTime = 0;
    this.isPlaying = false;
    this.playbackSpeed = 1;

    // Game state
    this.units = new Map(); // unit_name -> {x, y, player, type, alive, dying, movements: [...]}
    this.buildings = new Map(); // building_key -> {x, y, player, type}

    // Callbacks
    this.onTimeUpdate = null;
    this.onActionProcessed = null;

    // Animation
    this.lastFrameTime = 0;
    this.animationId = null;

    // Track which actions have been logged
    this.lastLoggedActionIndex = -1;

    // Build unit ownership map from starting units
    this.unitOwners = new Map();
    for (const unit of this.data.starting_units) {
      this.unitOwners.set(unit.id, unit.player);
    }

    // Pre-process all unit movements
    this.preprocessMovements();

    // Build the static + time-aware obstacle grid used for pathfinding so units
    // route around trees, resources and buildings instead of walking through them.
    this.buildObstacleGrid();
    this._pathCache = new Map();

    // Initialize state
    this.initializeUnits();
  }

  // Extract owner from unit name (format: type_player_number)
  getOwnerFromUnitName(unitName) {
    // First check if we already know the owner
    if (this.unitOwners.has(unitName)) {
      return this.unitOwners.get(unitName);
    }

    // Parse from name: villager_Shadeslayer II_1 -> Shadeslayer II
    const parts = unitName.split("_");
    if (parts.length >= 3) {
      // Join all parts except first (type) and last (number)
      return parts.slice(1, -1).join("_");
    }
    return null;
  }

  // Pre-process all actions to build movement timelines for each unit
  preprocessMovements() {
    this.unitMovements = new Map(); // unit_name -> [{time, x, y, actionType}, ...]
    this.buildingEvents = []; // [{time, player, type, x, y}, ...]
    this.unitDeletions = new Map(); // unit_name -> deletion_time
    this.buildingDeletions = []; // [{time, x, y}, ...]
    this.attackActions = []; // [{time, attackerNames, targetX, targetY, player}, ...]
    this.targetPositions = new Map(); // target_id -> {x, y} for tracking attack targets

    const actions = this.data.actions;

    for (const action of actions) {
      const { type, player, subjects, target, target_id, x, y, time } = action;

      // Track ORDER (attack) actions with target positions
      if (type === "ORDER" && target_id && x !== null && y !== null) {
        // Store target position for this target_id
        this.targetPositions.set(target_id, { x, y, time });

        // Record attack action
        if (subjects && subjects.length > 0) {
          this.attackActions.push({
            time: time,
            attackerNames: subjects,
            targetX: x,
            targetY: y,
            targetId: target_id,
            player: player,
          });
        }
      }

      // Track DELETE actions
      if (type === "DELETE") {
        // Handle unit deletions
        if (subjects && subjects.length > 0) {
          for (const unitName of subjects) {
            const owner = this.getOwnerFromUnitName(unitName);

            // Only process deletions from the owner
            if (owner && owner !== player) {
              continue;
            }

            // Record deletion time for this unit
            if (!this.unitDeletions.has(unitName)) {
              this.unitDeletions.set(unitName, time);
            }
          }
        }

        // Handle building deletions (by position)
        if (x !== null && y !== null) {
          this.buildingDeletions.push({
            time: time,
            x: Math.round(x),
            y: Math.round(y),
            player: player,
          });
        }
      }

      // Track position-based actions for units
      // ONLY include actions where the commanding player owns the unit
      if (subjects && subjects.length > 0 && x !== null && y !== null) {
        for (const unitName of subjects) {
          const owner = this.getOwnerFromUnitName(unitName);

          // Skip if the action player doesn't match the unit owner
          if (owner && owner !== player) {
            continue;
          }

          // Store owner if we don't have it yet
          if (!this.unitOwners.has(unitName)) {
            this.unitOwners.set(unitName, player);
          }

          if (!this.unitMovements.has(unitName)) {
            this.unitMovements.set(unitName, []);
          }

          // For ORDER (attack) actions, check if this is a ranged unit
          // Ranged units don't move all the way to the target
          const isAttack = type === "ORDER" && target_id;

          this.unitMovements.get(unitName).push({
            time: time,
            x: x,
            y: y,
            actionType: type,
            isAttack: isAttack,
            targetId: isAttack ? target_id : null,
          });
        }
      }

      // Track building placements
      if (type === "BUILD" && x !== null && y !== null && target) {
        this.buildingEvents.push({
          time: time,
          player: player,
          type: target,
          x: x,
          y: y,
        });
      }
    }

    // Sort movements by time for each unit
    for (const [unitName, movements] of this.unitMovements) {
      movements.sort((a, b) => a.time - b.time);
    }

    // Sort building events by time
    this.buildingEvents.sort((a, b) => a.time - b.time);

    // Building interactions: when a player used a building (trained, researched,
    // set a gather point, castle attack, ...). Keyed the same way buildings are
    // keyed in getState (player + rounded tile) -> sorted list of use times, so
    // a building can be re-brightened from the moment it was last interacted.
    this.buildingInteractions = new Map();
    for (const it of this.data.building_interactions || []) {
      const key = `${it.player}_${Math.round(it.x)}_${Math.round(it.y)}`;
      if (!this.buildingInteractions.has(key)) {
        this.buildingInteractions.set(key, []);
      }
      this.buildingInteractions.get(key).push(it.time);
    }
    for (const times of this.buildingInteractions.values()) {
      times.sort((a, b) => a - b);
    }

    // Server-resolved building removals (abandoned foundations, razed
    // buildings). DELETE actions in the replay only name a building by id with
    // no position, so the backend recovers the position; here we just feed them
    // into the same deletion list getState already checks.
    for (const d of this.data.building_deletions || []) {
      this.buildingDeletions.push({
        time: d.time,
        x: Math.round(d.x),
        y: Math.round(d.y),
        player: d.player,
      });
    }

    // Siege bombardment episodes (trebuchets and bombard cannons). The unit
    // keeps firing at its target from the moment it's ordered to attack until
    // its next command (or until it fades, i.e. it was destroyed). We record
    // [start, end] windows + the target position so getState can spawn arcing
    // projectiles during the window.
    this.trebAttacks = [];
    const matchDuration =
      (this.data.match && this.data.match.duration_seconds) || 1e9;
    const deaths = this.data.unit_deaths || {};
    for (const [unitName, movements] of this.unitMovements) {
      if (!Playback.SIEGE_SHOOTER_RE.test(unitName)) continue;
      const player = this.unitOwners.get(unitName);
      const kind = /bombard/i.test(unitName) ? "bombard" : "treb";
      for (let i = 0; i < movements.length; i++) {
        if (!movements[i].isAttack) continue;
        const end =
          i + 1 < movements.length
            ? movements[i + 1].time
            : deaths[unitName] != null
              ? deaths[unitName]
              : matchDuration;
        this.trebAttacks.push({
          unitName,
          player,
          kind, // "treb" (flaming lob) or "bombard" (flat black cannonball)
          targetX: movements[i].x, // the ORDER position = the targeted building
          targetY: movements[i].y,
          start: movements[i].time,
          end,
        });
      }
    }
  }

  // Latest interaction time <= `t` for a building key, or null. Binary search
  // over the per-building sorted time list.
  lastInteractionBefore(key, t) {
    const times = this.buildingInteractions
      ? this.buildingInteractions.get(key)
      : null;
    if (!times || times.length === 0) return null;
    let lo = 0,
      hi = times.length - 1,
      ans = null;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (times[mid] <= t) {
        ans = times[mid];
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return ans;
  }

  // Siege units that bombard buildings at range with arcing projectiles
  // (trebuchets, bombard cannons). Matched against unit names.
  static SIEGE_SHOOTER_RE = /trebuchet|bombard/i;

  // ---- Pathfinding: obstacle grid + A* so units route around static obstacles ----

  // Approximate building footprints in tiles (keyword -> side length). Units path
  // around the whole footprint. Exact sizes aren't important for routing.
  static BUILDING_TILE_SIZES = [
    [/town\s*cent|\btc\b/, 4],
    [/castle|krepost/, 4],
    [/wonder/, 4],
    [/wall|gate|tower|outpost/, 1],
    [/house/, 2],
    [/mill|lumber|mining|\bcamp\b|dock|fish trap/, 2],
    [/farm/, 3],
    [/barrack|archery|stable|siege|blacksmith|market|monaster|universit|harbor|donjon|feitoria/, 3],
  ];

  buildingTileSize(type) {
    const t = (type || "").toLowerCase();
    for (const [re, n] of Playback.BUILDING_TILE_SIZES) {
      if (re.test(t)) return n;
    }
    return 3; // default footprint
  }

  // Build the occupancy grid. Static blockers (forest terrain + resource piles)
  // never change; buildings are recorded with the time they appear so paths
  // computed earlier in the game don't avoid a building that isn't placed yet.
  buildObstacleGrid() {
    this.pf = null;
    const terrain = this.data.terrain;
    if (!terrain || !terrain.ids || !terrain.dimension) return; // no map -> straight lines

    const dim = terrain.dimension;
    const staticBlocked = new Uint8Array(dim * dim);

    // Forest tiles (baked into terrain, colored as forest green).
    const palette = terrain.palette || {};
    const FOREST_HEX = "#2f4d24";
    for (let i = 0; i < terrain.ids.length; i++) {
      if (palette[terrain.ids[i]] === FOREST_HEX) staticBlocked[i] = 1;
    }

    // Resource piles (gold / stone / relic / forage) occupy their tile.
    const BLOCKING_RES = new Set(["gold", "stone", "relic", "forage"]);
    for (const o of this.data.map_objects || []) {
      if (!BLOCKING_RES.has(o.c)) continue;
      const tx = Math.floor(o.x);
      const ty = Math.floor(o.y);
      if (tx >= 0 && ty >= 0 && tx < dim && ty < dim) staticBlocked[ty * dim + tx] = 1;
    }

    // Buildings: tile -> earliest build time (so blocking is time-aware).
    const buildingBlockTime = new Map();
    for (const b of this.buildingEvents) {
      const s = this.buildingTileSize(b.type);
      const x0 = Math.round(b.x - s / 2);
      const y0 = Math.round(b.y - s / 2);
      for (let dy = 0; dy < s; dy++) {
        for (let dx = 0; dx < s; dx++) {
          const tx = x0 + dx;
          const ty = y0 + dy;
          if (tx < 0 || ty < 0 || tx >= dim || ty >= dim) continue;
          const idx = ty * dim + tx;
          const prev = buildingBlockTime.get(idx);
          if (prev === undefined || b.time < prev) buildingBlockTime.set(idx, b.time);
        }
      }
    }

    this.pf = { dim, staticBlocked, buildingBlockTime };
  }

  // Is tile (tx,ty) blocked at `time`? The start and goal tiles are always
  // passable so a unit can leave/enter a resource or building tile it was
  // commanded onto (e.g. a villager sent to mine gold).
  isTileBlocked(tx, ty, time, sx, sy, gx, gy) {
    const pf = this.pf;
    if (tx < 0 || ty < 0 || tx >= pf.dim || ty >= pf.dim) return true;
    if ((tx === sx && ty === sy) || (tx === gx && ty === gy)) return false;
    const idx = ty * pf.dim + tx;
    if (pf.staticBlocked[idx]) return true;
    const bt = pf.buildingBlockTime.get(idx);
    return bt !== undefined && bt <= time;
  }

  // Straight line from a to b is clear of obstacles (used to smooth A* paths).
  lineClear(ax, ay, bx, by, time, sx, sy, gx, gy) {
    const dx = bx - ax;
    const dy = by - ay;
    const dist = Math.hypot(dx, dy);
    const steps = Math.max(1, Math.ceil(dist / 0.25));
    for (let k = 1; k < steps; k++) {
      const px = ax + (dx * k) / steps;
      const py = ay + (dy * k) / steps;
      if (this.isTileBlocked(Math.floor(px), Math.floor(py), time, sx, sy, gx, gy)) {
        return false;
      }
    }
    return true;
  }

  // Like isTileBlocked but without the start/goal exemption: the raw occupancy
  // of a tile at `time`. Used to detect commands that target a blocked tile.
  tileBlockedRaw(tx, ty, time) {
    const pf = this.pf;
    if (tx < 0 || ty < 0 || tx >= pf.dim || ty >= pf.dim) return true;
    const idx = ty * pf.dim + tx;
    if (pf.staticBlocked[idx]) return true;
    const bt = pf.buildingBlockTime.get(idx);
    return bt !== undefined && bt <= time;
  }

  // Nearest free tile to (tx,ty) by expanding Chebyshev rings (null if none
  // within maxR). Lets a unit sent onto a tree/resource stop at its edge.
  nearestFreeTile(tx, ty, time, maxR) {
    if (!this.tileBlockedRaw(tx, ty, time)) return { x: tx, y: ty };
    for (let r = 1; r <= maxR; r++) {
      for (let dx = -r; dx <= r; dx++) {
        for (let dy = -r; dy <= r; dy++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue; // ring perimeter only
          if (!this.tileBlockedRaw(tx + dx, ty + dy, time)) {
            return { x: tx + dx, y: ty + dy };
          }
        }
      }
    }
    return null;
  }

  // Where a unit actually comes to rest for a command whose target may be on a
  // blocked tile (wood / gold / stone): the resource edge, matching how findPath
  // resolves a blocked goal. Keeps boundary/resting positions out of obstacles.
  resolvedStop(x, y, time) {
    if (!this.pf || !this.tileBlockedRaw(Math.floor(x), Math.floor(y), time)) {
      return { x, y };
    }
    const f = this.nearestFreeTile(Math.floor(x), Math.floor(y), time, 8);
    return f ? { x: f.x + 0.5, y: f.y + 0.5 } : { x, y };
  }

  // A* on the tile grid from (sx,sy) to (gx,gy) at `time`. Returns a smoothed
  // list of waypoints [{x,y}, ...] from start to goal, or a straight [start,goal]
  // fallback if there's no grid, no obstacle in the way, or no path within budget.
  findPath(sx, sy, gx, gy, time) {
    const pf = this.pf;
    if (!pf) {
      return [
        { x: sx, y: sy },
        { x: gx, y: gy },
      ];
    }

    // If an endpoint sits on a blocked tile (a villager commanded onto a tree or
    // gold/stone pile), pathfind to/from the nearest free tile instead of into
    // it. Otherwise the target is unreachable from open ground and A* clips
    // straight in. The unit stops at the forest/resource edge, like real
    // gathering. A blocked start keeps the real start as a first hop out.
    let ax = sx, ay = sy, bx = gx, by = gy;
    let prefix = null;
    if (this.tileBlockedRaw(Math.floor(sx), Math.floor(sy), time)) {
      const f = this.nearestFreeTile(Math.floor(sx), Math.floor(sy), time, 8);
      if (f) {
        prefix = { x: sx, y: sy };
        ax = f.x + 0.5;
        ay = f.y + 0.5;
      }
    }
    if (this.tileBlockedRaw(Math.floor(gx), Math.floor(gy), time)) {
      const f = this.nearestFreeTile(Math.floor(gx), Math.floor(gy), time, 8);
      if (f) {
        bx = f.x + 0.5;
        by = f.y + 0.5;
      }
    }
    const finalize = (core) => (prefix ? [prefix, ...core] : core);

    const start = { x: Math.floor(ax), y: Math.floor(ay) };
    const goal = { x: Math.floor(bx), y: Math.floor(by) };
    if (start.x === goal.x && start.y === goal.y) {
      return finalize([{ x: ax, y: ay }, { x: bx, y: by }]);
    }

    // Nothing in the way -> keep it cheap and exact.
    if (this.lineClear(ax, ay, bx, by, time, start.x, start.y, goal.x, goal.y)) {
      return finalize([{ x: ax, y: ay }, { x: bx, y: by }]);
    }

    // Shared cache (buildings change slowly, so bucket time coarsely).
    const bucket = Math.floor(time / 20);
    const key = `${start.x},${start.y},${goal.x},${goal.y},${bucket}`;
    const cached = this._pathCache.get(key);
    if (cached) return finalize(cached);

    const dim = pf.dim;
    const gScore = new Map();
    const came = new Map();
    const closed = new Set();
    const sIdx = start.y * dim + start.x;
    const gIdx = goal.y * dim + goal.x;
    const h = (x, y) => {
      const ddx = Math.abs(x - goal.x);
      const ddy = Math.abs(y - goal.y);
      return Math.max(ddx, ddy) + (Math.SQRT2 - 1) * Math.min(ddx, ddy);
    };

    // Binary min-heap of [f, idx] so the lowest-f node is O(log n) to pop.
    const heap = [];
    const hpush = (f, idx) => {
      heap.push([f, idx]);
      let i = heap.length - 1;
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (heap[p][0] <= heap[i][0]) break;
        const tmp = heap[p]; heap[p] = heap[i]; heap[i] = tmp;
        i = p;
      }
    };
    const hpop = () => {
      const top = heap[0];
      const last = heap.pop();
      if (heap.length) {
        heap[0] = last;
        let i = 0;
        const n = heap.length;
        for (;;) {
          const l = 2 * i + 1;
          const r = 2 * i + 2;
          let s = i;
          if (l < n && heap[l][0] < heap[s][0]) s = l;
          if (r < n && heap[r][0] < heap[s][0]) s = r;
          if (s === i) break;
          const tmp = heap[s]; heap[s] = heap[i]; heap[i] = tmp;
          i = s;
        }
      }
      return top;
    };

    gScore.set(sIdx, 0);
    hpush(h(start.x, start.y), sIdx);

    const NEIGHBORS = [
      [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
      [1, 1, Math.SQRT2], [1, -1, Math.SQRT2],
      [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
    ];
    const MAX_EXPANSIONS = 8000;
    let expansions = 0;
    let found = false;

    while (heap.length > 0) {
      const curIdx = hpop()[1];
      if (closed.has(curIdx)) continue; // stale heap entry
      if (curIdx === gIdx) {
        found = true;
        break;
      }
      closed.add(curIdx);
      if (++expansions > MAX_EXPANSIONS) break;

      const cx = curIdx % dim;
      const cy = (curIdx - cx) / dim;
      const cg = gScore.get(curIdx);
      for (const [ndx, ndy, cost] of NEIGHBORS) {
        const nx = cx + ndx;
        const ny = cy + ndy;
        if (this.isTileBlocked(nx, ny, time, start.x, start.y, goal.x, goal.y)) continue;
        // Don't cut diagonally between two blocked tiles.
        if (ndx !== 0 && ndy !== 0) {
          if (
            this.isTileBlocked(cx + ndx, cy, time, start.x, start.y, goal.x, goal.y) &&
            this.isTileBlocked(cx, cy + ndy, time, start.x, start.y, goal.x, goal.y)
          ) {
            continue;
          }
        }
        const nIdx = ny * dim + nx;
        if (closed.has(nIdx)) continue;
        const tentative = cg + cost;
        if (tentative < (gScore.get(nIdx) ?? Infinity)) {
          came.set(nIdx, curIdx);
          gScore.set(nIdx, tentative);
          hpush(tentative + h(nx, ny), nIdx);
        }
      }
    }

    if (!found) {
      // No route within budget: stop at the resolved (edge) endpoints rather
      // than the raw command target, so we don't draw a line into the forest.
      const fallback = [{ x: ax, y: ay }, { x: bx, y: by }];
      this._pathCache.set(key, fallback);
      return finalize(fallback);
    }

    // Reconstruct tile path, then smooth it with line-of-sight string pulling.
    const tiles = [];
    let cur = gIdx;
    while (cur !== undefined) {
      const cx = cur % dim;
      const cy = (cur - cx) / dim;
      tiles.push({ x: cx + 0.5, y: cy + 0.5 });
      if (cur === sIdx) break;
      cur = came.get(cur);
    }
    tiles.reverse();
    // Anchor the resolved start/goal so motion is exact at both ends.
    tiles[0] = { x: ax, y: ay };
    tiles[tiles.length - 1] = { x: bx, y: by };

    const smoothed = [tiles[0]];
    let anchor = 0;
    for (let i = 2; i < tiles.length; i++) {
      if (
        !this.lineClear(
          tiles[anchor].x, tiles[anchor].y, tiles[i].x, tiles[i].y,
          time, start.x, start.y, goal.x, goal.y,
        )
      ) {
        smoothed.push(tiles[i - 1]);
        anchor = i - 1;
      }
    }
    smoothed.push(tiles[tiles.length - 1]);

    this._pathCache.set(key, smoothed);
    return finalize(smoothed);
  }

  // Walk `dist` tiles along a polyline path; returns the resulting {x,y}.
  advanceAlongPath(path, dist) {
    if (!path || path.length === 0) return null;
    if (dist <= 0) return { x: path[0].x, y: path[0].y };
    let remaining = dist;
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i];
      const b = path[i + 1];
      const segLen = Math.hypot(b.x - a.x, b.y - a.y);
      if (segLen === 0) continue;
      if (remaining <= segLen) {
        const t = remaining / segLen;
        return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
      }
      remaining -= segLen;
    }
    const last = path[path.length - 1];
    return { x: last.x, y: last.y };
  }

  initializeUnits() {
    this.units.clear();
    this.buildings.clear();
    this.lastLoggedActionIndex = -1;

    // Add starting units with their movement timelines
    for (const unit of this.data.starting_units) {
      const movements = this.unitMovements.get(unit.id) || [];

      // Determine starting position: use first movement if no initial position
      let startX = unit.x;
      let startY = unit.y;
      if ((startX === null || startY === null) && movements.length > 0) {
        startX = movements[0].x;
        startY = movements[0].y;
      }

      this.units.set(unit.id, {
        x: startX,
        y: startY,
        player: unit.player,
        type: unit.type,
        alive: true,
        dying: false,
        movements: movements,
        instanceId: unit.instance_id,
      });
    }

    // Create units that appear later (not in starting units)
    for (const [unitName, movements] of this.unitMovements) {
      if (!this.units.has(unitName) && movements.length > 0) {
        const player = this.unitOwners.get(unitName) || "unknown";

        // Determine type from name
        const type = this.classifyUnitType(unitName);

        this.units.set(unitName, {
          x: null, // Will be set when unit first appears
          y: null,
          player: player,
          type: type,
          alive: false, // Not alive until first seen
          dying: false,
          movements: movements,
          spawnTime: movements[0].time, // When unit first appears
        });
      }
    }
  }

  // Classify unit type from unit name
  classifyUnitType(unitName) {
    const name = unitName.toLowerCase();

    if (name.includes("villager")) return "villager";
    if (name.includes("scout")) return "cavalry";
    if (
      name.includes("knight") ||
      name.includes("cavalier") ||
      name.includes("paladin") ||
      name.includes("hussar") ||
      name.includes("camel") ||
      name.includes("elephant") ||
      name.includes("cavalry") ||
      name.includes("tarkan") ||
      name.includes("boyar") ||
      name.includes("konnik") ||
      name.includes("leitis") ||
      name.includes("keshik") ||
      name.includes("cataphract") ||
      name.includes("mameluke")
    )
      return "cavalry";
    if (
      name.includes("archer") ||
      name.includes("crossbow") ||
      name.includes("arbalest") ||
      name.includes("skirmisher") ||
      name.includes("longbow") ||
      name.includes("mangudai") ||
      name.includes("handcannoneer") ||
      name.includes("janissary") ||
      name.includes("conquistador") ||
      name.includes("chukonou") ||
      name.includes("plumed") ||
      name.includes("genitour") ||
      name.includes("kipchak") ||
      name.includes("arambai") ||
      name.includes("rattan")
    )
      return "archer";
    if (
      name.includes("militia") ||
      name.includes("swordsman") ||
      name.includes("champion") ||
      name.includes("spearman") ||
      name.includes("pikeman") ||
      name.includes("halberdier") ||
      name.includes("eagle") ||
      name.includes("huskarl") ||
      name.includes("berserk") ||
      name.includes("samurai") ||
      name.includes("jaguar") ||
      name.includes("woad") ||
      name.includes("teutonic") ||
      name.includes("throwing") ||
      name.includes("gbeto") ||
      name.includes("kamayuk") ||
      name.includes("shotel") ||
      name.includes("serjeant") ||
      name.includes("obuch") ||
      name.includes("urumi")
    )
      return "infantry";
    if (
      name.includes("ram") ||
      name.includes("mangonel") ||
      name.includes("onager") ||
      name.includes("scorpion") ||
      name.includes("trebuchet") ||
      name.includes("bombard") ||
      name.includes("siege")
    )
      return "siege";
    if (name.includes("monk") || name.includes("missionary")) return "monk";
    if (
      name.includes("galley") ||
      name.includes("ship") ||
      name.includes("boat") ||
      name.includes("caravel") ||
      name.includes("longboat") ||
      name.includes("turtle") ||
      name.includes("cannon galleon") ||
      name.includes("dromon")
    )
      return "ship";
    if (name.includes("king")) return "king";

    return "military";
  }

  // Get interpolated position for a unit at current time
  // Uses speed-based movement: units move at a fixed speed toward their destination
  // If interrupted by a new command, the new starting position is where they actually were
  getUnitPosition(unit) {
    const movements = unit.movements;
    if (!movements || movements.length === 0) {
      return { x: unit.x, y: unit.y };
    }

    // Unit movement speeds (tiles per second) - approximate AoE2 speeds
    const UNIT_SPEEDS = {
      villager: 0.8,
      infantry: 0.9,
      archer: 0.96,
      cavalry: 1.35,
      siege: 0.6,
      monk: 0.7,
      ship: 1.5,
      king: 0.9,
      military: 0.9,
    };

    const speed = UNIT_SPEEDS[unit.type] || 0.9;

    // Find the movement command that applies at currentTime
    let commandIndex = -1;
    for (let i = 0; i < movements.length; i++) {
      if (movements[i].time <= this.currentTime) {
        commandIndex = i;
      } else {
        break;
      }
    }

    // Before first movement - use starting position
    if (commandIndex < 0) {
      if (unit.x !== null && unit.y !== null) {
        return { x: unit.x, y: unit.y };
      }
      if (movements.length > 0) {
        return { x: movements[0].x, y: movements[0].y };
      }
      return { x: unit.x, y: unit.y };
    }

    // Starting position (spawned units have no initial x/y until first seen).
    const startX = unit.x !== null ? unit.x : movements[0].x;
    const startY = unit.y !== null ? unit.y : movements[0].y;

    // Ranged units stop short of their attack target instead of walking onto it.
    // Siege (esp. trebuchets) holds at long range; archers stop a few tiles off.
    const isRangedUnit = unit.type === "archer" || unit.type === "siege";
    const RANGED_ATTACK_DISTANCE = unit.type === "siege" ? 12 : 5; // tiles

    // Effective destination of command i, given the unit begins it at `from`.
    const destFor = (i, from) => {
      let dx2 = movements[i].x;
      let dy2 = movements[i].y;
      if (isRangedUnit && movements[i].isAttack) {
        const dx = dx2 - from.x;
        const dy = dy2 - from.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > RANGED_ATTACK_DISTANCE) {
          const ratio = (distance - RANGED_ATTACK_DISTANCE) / distance;
          dx2 = from.x + dx * ratio;
          dy2 = from.y + dy * ratio;
        } else {
          dx2 = from.x;
          dy2 = from.y;
        }
      }
      return { x: dx2, y: dy2 };
    };

    // We only ever RENDER the currently-active command, so that's the only one
    // worth the A* cost. Completed commands just need an end position to seed the
    // next segment's start, which a cheap straight-line advance gives (units that
    // finished a command rest exactly on its target either way). This keeps even a
    // far timeline seek to ~one A* per unit instead of one per command.
    let pf = unit._pf;
    if (!pf)
      pf = unit._pf = {
        boundaries: [], upto: -1, activeIndex: -1, activePath: null,
        restIndex: -1, restPos: null,
      };

    const segStartTime = (i) =>
      i === 0 ? movements[0].time - 10 : movements[i].time; // assume it existed ~10s before its first command
    const segStartPos = (i) =>
      i === 0 ? { x: startX, y: startY } : pf.boundaries[i - 1];

    // Extend the cached boundary chain over every command that's already
    // finished. Resolve targets off blocked tiles so a unit that finished a
    // gather command rests at the resource edge, not inside the forest/pile.
    for (let i = pf.upto + 1; i < commandIndex; i++) {
      const from = segStartPos(i);
      const t0i = segStartTime(i);
      const raw = destFor(i, from);
      const dest = this.resolvedStop(raw.x, raw.y, t0i);
      const avail = Math.max(0, movements[i + 1].time - t0i) * speed;
      pf.boundaries[i] = this.advanceStraight(from, dest, avail);
      pf.upto = i;
    }

    // Active command: route around obstacles, then follow that path by however
    // far the unit has travelled.
    const from = segStartPos(commandIndex);
    const t0 = segStartTime(commandIndex);
    const dest = destFor(commandIndex, from);
    const dist = Math.max(0, this.currentTime - t0) * speed;

    // Resting shortcut: once the unit has had far more time than even a heavily
    // detoured route could need, it's sitting on the target — return it directly
    // and skip A* entirely. This is what keeps a far timeline seek cheap, since
    // most units are idle on their last command at any given moment. A target on
    // a blocked tile (e.g. wood/gold) resolves to the resource edge so the unit
    // doesn't rest inside the forest. Cache the resolved spot per command.
    const straightDist = Math.hypot(dest.x - from.x, dest.y - from.y);
    if (dist >= straightDist * 4 + 8) {
      pf.activeIndex = -1;
      pf.activePath = null;
      if (pf.restIndex !== commandIndex) {
        pf.restPos = this.resolvedStop(dest.x, dest.y, t0);
        pf.restIndex = commandIndex;
      }
      return pf.restPos;
    }

    // Otherwise compute (and cache until the command changes) the avoidance path.
    if (pf.activeIndex !== commandIndex || !pf.activePath) {
      pf.activePath = this.findPath(from.x, from.y, dest.x, dest.y, t0);
      pf.activeIndex = commandIndex;
    }
    return this.advanceAlongPath(pf.activePath, dist) || { x: startX, y: startY };
  }

  // Straight-line advance of `dist` tiles from `from` toward `dest` (clamped).
  advanceStraight(from, dest, dist) {
    const dx = dest.x - from.x;
    const dy = dest.y - from.y;
    const d = Math.hypot(dx, dy);
    if (d === 0 || dist >= d) return { x: dest.x, y: dest.y };
    const r = dist / d;
    return { x: from.x + dx * r, y: from.y + dy * r };
  }

  // Get current game state for rendering
  getState() {
    // Update unit positions based on interpolation
    const interpolatedUnits = new Map();

    // Constants for idle/death detection
    const VILLAGER_IDLE_THRESHOLD = 30; // 30 seconds for villager idle detection
    const END_GAME_BUFFER = 3 * 60; // Last 3 minutes of game - don't mark units as dead
    const isEndGame = this.currentTime >= this.duration - END_GAME_BUFFER;

    for (const [name, unit] of this.units) {
      // Check if unit should be alive
      let alive = unit.alive;
      const isVillager = unit.type === "villager";

      // Unit spawns when first movement occurs
      if (unit.spawnTime !== undefined) {
        if (this.currentTime < unit.spawnTime) {
          alive = false;
        } else {
          alive = true;
        }
      }

      // Check for death
      const deathTime = this.data.unit_deaths[name];
      let dying = false;
      if (deathTime !== undefined) {
        if (this.currentTime >= deathTime) {
          alive = false;
        } else if (this.currentTime >= deathTime - 30) {
          dying = true;
        }
      }

      // Check for deletion by player
      const deletionTime = this.unitDeletions.get(name);
      if (deletionTime !== undefined && this.currentTime >= deletionTime) {
        alive = false;
      }

      // Track last command time and idle state
      const movements = unit.movements || [];
      let lastCommandTime = null;
      let lastCommandInGame = null; // Last command ever for this unit

      if (movements.length > 0) {
        // Find the last command ever (for non-villager death detection)
        lastCommandInGame = movements[movements.length - 1].time;

        // Find the last command before or at current time
        for (const movement of movements) {
          if (movement.time <= this.currentTime) {
            lastCommandTime = movement.time;
          }
        }
      }

      // For non-villagers: if they have no more actions after current time, they're dead
      // Exception: don't apply this in the last 3 minutes of game
      let idleVillager = false;

      // Siege is exempt: a trebuchet/mangonel keeps firing long after its last
      // command (you click the target once and leave it), so it must stay alive
      // until its actual fade (unit_deaths, +5min idle) instead of vanishing the
      // moment it has no further command.
      if (
        !isVillager &&
        unit.type !== "siege" &&
        alive &&
        lastCommandInGame !== null
      ) {
        // Check if unit has no future commands (last command is in the past)
        if (lastCommandTime !== null && lastCommandTime === lastCommandInGame) {
          // This unit has no more commands after this point
          // Don't mark dead in end game (units may still be alive)
          if (!isEndGame) {
            alive = false;
          }
        }
      }

      // For villagers: check 30-second idle threshold for opacity reduction
      let villagerIdleTime = 0;
      if (isVillager && alive && lastCommandTime !== null) {
        const timeSinceLastCommand = this.currentTime - lastCommandTime;
        if (timeSinceLastCommand > VILLAGER_IDLE_THRESHOLD) {
          idleVillager = true;
          villagerIdleTime = timeSinceLastCommand;
        }
      }

      // Legacy 5-minute inactivity check for villagers only (keep them visible but faded)
      const INACTIVITY_THRESHOLD = 5 * 60; // 5 minutes in seconds
      if (isVillager && movements.length > 0 && lastCommandTime !== null) {
        const timeSinceLastCommand = this.currentTime - lastCommandTime;
        if (timeSinceLastCommand > INACTIVITY_THRESHOLD) {
          // Villager hasn't been commanded in 5+ minutes, consider it dead
          alive = false;
          // Mark as dying if within 30 seconds of the threshold
          if (timeSinceLastCommand <= INACTIVITY_THRESHOLD + 30) {
            dying = true;
          }
        }
      }

      // Get interpolated position
      const pos = this.getUnitPosition(unit);

      // Skip units with no valid position
      if (pos.x === null || pos.y === null) {
        continue;
      }

      interpolatedUnits.set(name, {
        x: pos.x,
        y: pos.y,
        player: unit.player,
        type: unit.type,
        alive: alive,
        dying: dying,
        idleVillager: idleVillager, // New flag for idle villagers
        idleTime: villagerIdleTime, // Time since last command (for opacity fade)
      });
    }

    // Update buildings based on time, tracking age for opacity
    const currentBuildings = new Map();
    for (const event of this.buildingEvents) {
      if (event.time <= this.currentTime) {
        const roundedX = Math.round(event.x);
        const roundedY = Math.round(event.y);

        // Check if this building was deleted (after it was placed)
        let deleted = false;
        for (const deletion of this.buildingDeletions) {
          // Deletion must happen after the building was placed and before current time
          if (
            deletion.time > event.time &&
            deletion.time <= this.currentTime &&
            deletion.player === event.player &&
            Math.abs(deletion.x - roundedX) <= 2 &&
            Math.abs(deletion.y - roundedY) <= 2
          ) {
            deleted = true;
            break;
          }
        }

        if (!deleted) {
          const key = `${event.type}_${event.player}_${roundedX}_${roundedY}`;
          // Age is measured from the most recent activity on this building: its
          // placement, or a later interaction (production/research/etc.). This
          // makes a building snap back to full opacity whenever it's used.
          const useKey = `${event.player}_${roundedX}_${roundedY}`;
          const lastUse = this.lastInteractionBefore(useKey, this.currentTime);
          const origin =
            lastUse != null && lastUse > event.time ? lastUse : event.time;
          const buildingAge = this.currentTime - origin;
          currentBuildings.set(key, {
            x: event.x,
            y: event.y,
            player: event.player,
            type: event.type,
            age: buildingAge, // Time since building was placed
            time: event.time, // When it was placed (for base recency)
          });
        }
      }
    }

    // Get active attack actions (within last 5 seconds)
    const ATTACK_DISPLAY_DURATION = 5; // Show attack arrows for 5 seconds
    const activeAttacks = [];
    for (const attack of this.attackActions) {
      const timeSinceAttack = this.currentTime - attack.time;
      if (timeSinceAttack >= 0 && timeSinceAttack <= ATTACK_DISPLAY_DURATION) {
        // Get attacker positions
        for (const attackerName of attack.attackerNames) {
          // Siege bombarders show arcing projectiles instead of a static arrow.
          if (Playback.SIEGE_SHOOTER_RE.test(attackerName)) continue;
          const attackerUnit = interpolatedUnits.get(attackerName);
          if (attackerUnit && attackerUnit.alive) {
            activeAttacks.push({
              fromX: attackerUnit.x,
              fromY: attackerUnit.y,
              toX: attack.targetX,
              toY: attack.targetY,
              player: attack.player,
              opacity: 1 - timeSinceAttack / ATTACK_DISPLAY_DURATION, // Fade out over 5s
            });
          }
        }
      }
    }

    // Trebuchet projectiles: during a firing window, a treb lobs a shot every
    // RELOAD seconds; each shot is airborne for FLIGHT seconds. We emit the
    // in-flight shots (progress 0..1) launching from the treb's current spot to
    // the targeted building, for the renderer to draw as arcing flaming balls.
    const TREB_WINDUP = 2; // s to move into range + unpack before first shot
    const TREB_RELOAD = 10; // s between shots (realistic siege cadence)
    const TREB_FLIGHT = 2.5; // s a shot is airborne (slow, lofty arc)
    const trebProjectiles = [];
    for (const ep of this.trebAttacks || []) {
      const fireStart = ep.start + TREB_WINDUP;
      if (this.currentTime < fireStart || this.currentTime > ep.end) continue;
      const attacker = interpolatedUnits.get(ep.unitName);
      if (!attacker || !attacker.alive) continue;
      // Mark the treb as actively firing so the renderer enlarges it (3×) for
      // the whole barrage window, independent of individual shot drawing.
      attacker.firing = true;
      const firstK = Math.max(
        0,
        Math.ceil((this.currentTime - TREB_FLIGHT - fireStart) / TREB_RELOAD),
      );
      const lastK = Math.floor((this.currentTime - fireStart) / TREB_RELOAD);
      const shots = [];
      for (let k = firstK; k <= lastK; k++) {
        const launch = fireStart + k * TREB_RELOAD;
        if (launch > ep.end) break;
        const p = (this.currentTime - launch) / TREB_FLIGHT;
        if (p >= 0 && p <= 1) shots.push(p);
      }
      if (shots.length) {
        trebProjectiles.push({
          fromX: attacker.x,
          fromY: attacker.y,
          toX: ep.targetX,
          toY: ep.targetY,
          player: ep.player,
          kind: ep.kind,
          shots,
        });
      }
    }

    // Update walls based on time
    const currentWalls = [];
    const walls = this.data.walls || [];
    for (const wall of walls) {
      if (wall.time <= this.currentTime) {
        currentWalls.push({
          x_start: wall.x_start,
          y_start: wall.y_start,
          x_end: wall.x_end,
          y_end: wall.y_end,
          player: wall.player,
          type: wall.type,
        });
      }
    }

    return {
      units: interpolatedUnits,
      buildings: currentBuildings,
      walls: currentWalls,
      attacks: activeAttacks, // Attack arrows to draw
      trebProjectiles: trebProjectiles, // Arcing siege shots to animate
      actionLines: [], // Deprecated, kept for backward compatibility
      currentTime: this.currentTime,
    };
  }

  // Format time as MM:SS
  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  // Process actions for logging purposes
  processActionsForLog() {
    const actions = this.data.actions;

    // Find actions that should be logged
    while (
      this.lastLoggedActionIndex + 1 < actions.length &&
      actions[this.lastLoggedActionIndex + 1].time <= this.currentTime
    ) {
      this.lastLoggedActionIndex++;
      const action = actions[this.lastLoggedActionIndex];

      if (this.onActionProcessed) {
        this.onActionProcessed(action);
      }
    }
  }

  // Seek to a specific time
  seekTo(time) {
    time = Math.max(0, Math.min(this.duration, time));

    // If going backwards, reset log index
    if (time < this.currentTime) {
      this.lastLoggedActionIndex = -1;
    }

    this.currentTime = time;
    this.processActionsForLog();

    if (this.onTimeUpdate) {
      this.onTimeUpdate(this.currentTime);
    }
  }

  // Step forward/backward by one action
  stepForward() {
    const actions = this.data.actions;
    const nextIndex = this.lastLoggedActionIndex + 1;
    if (nextIndex < actions.length) {
      this.seekTo(actions[nextIndex].time + 0.001);
    }
  }

  stepBackward() {
    const actions = this.data.actions;
    if (this.lastLoggedActionIndex > 0) {
      const targetIndex = this.lastLoggedActionIndex - 1;
      // Reset and seek to just after that action
      this.lastLoggedActionIndex = -1;
      this.seekTo(actions[targetIndex].time + 0.001);
    } else {
      this.seekTo(0);
    }
  }

  // Animation loop
  animate(timestamp) {
    if (!this.isPlaying) return;

    if (this.lastFrameTime === 0) {
      this.lastFrameTime = timestamp;
    }

    const deltaTime = (timestamp - this.lastFrameTime) / 1000; // Convert to seconds
    this.lastFrameTime = timestamp;

    // Advance game time. AoE2's "normal" speed runs the simulation at 1.7 game
    // seconds per real second (internally 20 ticks/game-second). So the 1x speed
    // button matches AoE2 normal speed, and 2x/4x/... are multiples of it.
    this.currentTime += deltaTime * this.playbackSpeed * Playback.NORMAL_SPEED;

    // Check if we've reached the end
    if (this.currentTime >= this.duration) {
      this.currentTime = this.duration;
      this.pause();
    }

    // Process actions for logging
    this.processActionsForLog();

    // Update UI
    if (this.onTimeUpdate) {
      this.onTimeUpdate(this.currentTime);
    }

    // Continue animation
    if (this.isPlaying) {
      this.animationId = requestAnimationFrame((t) => this.animate(t));
    }
  }

  // Playback controls
  play() {
    if (this.isPlaying) return;

    this.isPlaying = true;
    this.lastFrameTime = 0;
    this.animationId = requestAnimationFrame((t) => this.animate(t));
  }

  pause() {
    this.isPlaying = false;
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }

  togglePlayPause() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
    return this.isPlaying;
  }

  setSpeed(speed) {
    this.playbackSpeed = speed;
  }

  goToStart() {
    this.pause();
    this.lastLoggedActionIndex = -1;
    this.seekTo(0);
  }

  goToEnd() {
    this.pause();
    this.seekTo(this.duration);
  }
}

// AoE2 "normal" game speed: 1.7 game-seconds advance per real second. The 1x
// playback-speed button is anchored to this so it matches watching at normal
// speed in-game; higher speed buttons multiply it.
Playback.NORMAL_SPEED = 1.7;

// Export for use in other modules
window.Playback = Playback;
