import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
// Candidate density is numerical search resolution, not a unit calibration:
// the movement budget and lookahead below still come entirely from sourced
// unit collision geometry and the already-computed physics proposal.
const TURN_INCREMENT = Math.PI / 12;
const MAX_TURNS = 6;


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function normalizeInputs(snapshot, proposals, owner) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!Array.isArray(proposals)) throw new TypeError("proposals must be an array");
  requireReferenceId(owner, "steering owner");
  const units = [...snapshot].sort((left, right) => (
    requireReferenceId(left?.referenceId) - requireReferenceId(right?.referenceId)
  ));
  const byReference = new Map();
  for (const unit of units) {
    if (byReference.has(unit.referenceId)) {
      throw new Error(`duplicate unit reference ${unit.referenceId}`);
    }
    byReference.set(unit.referenceId, unit);
  }
  const proposalByReference = new Map();
  for (const row of proposals) {
    const referenceId = requireReferenceId(row?.referenceId, "proposal reference ID");
    if (!byReference.has(referenceId)) {
      throw new Error(`movement proposal references unknown unit ${referenceId}`);
    }
    if (proposalByReference.has(referenceId)) {
      throw new Error(`duplicate movement proposal for reference ${referenceId}`);
    }
    proposalByReference.set(referenceId, Object.freeze({
      referenceId,
      dx: requireFinite(row.dx, "proposal dx"),
      dy: requireFinite(row.dy, "proposal dy"),
    }));
  }
  for (const unit of units) {
    if (!proposalByReference.has(unit.referenceId)) {
      proposalByReference.set(unit.referenceId, Object.freeze({
        referenceId: unit.referenceId,
        dx: 0,
        dy: 0,
      }));
    }
  }
  return { units, byReference, proposalByReference };
}


function contactExtent(left, right) {
  return collisionRadius(left) + collisionRadius(right);
}


function touches(left, leftPoint, right, rightPoint) {
  return Math.max(
    Math.abs(leftPoint.x - rightPoint.x),
    Math.abs(leftPoint.y - rightPoint.y),
  ) < contactExtent(left, right) - EPSILON;
}


function graphFor(units, points) {
  const neighbors = new Map(units.map(({ referenceId }) => [referenceId, new Set()]));
  for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
    const left = units[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
      const right = units[rightIndex];
      if (!touches(
        left, points.get(left.referenceId), right, points.get(right.referenceId),
      )) continue;
      neighbors.get(left.referenceId).add(right.referenceId);
      neighbors.get(right.referenceId).add(left.referenceId);
    }
  }
  return neighbors;
}


function componentIds(graph, start) {
  const seen = new Set([start]);
  const queue = [start];
  while (queue.length) {
    const current = queue.shift();
    for (const neighbor of graph.get(current) ?? []) {
      if (seen.has(neighbor)) continue;
      seen.add(neighbor);
      queue.push(neighbor);
    }
  }
  return seen;
}


function movementHorizon(unit, proposal, byReference, alliedUnits) {
  const distance = Math.hypot(proposal.dx, proposal.dy);
  if (distance <= EPSILON) return 0;
  const largestAllyRadius = alliedUnits.reduce(
    (maximum, ally) => Math.max(maximum, collisionRadius(ally)),
    collisionRadius(unit),
  );
  let horizon = collisionRadius(unit) + largestAllyRadius;
  const target = byReference.get(unit.pursuitTargetId);
  if (target?.alive !== false && target && target.owner !== unit.owner) {
    const centerDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
    const attackRange = Number.isFinite(unit?.mechanics?.attack_range_tiles)
      ? Math.max(0, unit.mechanics.attack_range_tiles) : 0;
    const remaining = Math.max(
      0,
      centerDistance - contactExtent(unit, target) - attackRange,
    );
    horizon = Math.min(horizon, remaining);
  }
  return Math.max(distance, horizon);
}


function projectedPoint(unit, proposal, byReference, alliedUnits) {
  const distance = Math.hypot(proposal.dx, proposal.dy);
  if (distance <= EPSILON) return { x: unit.x, y: unit.y };
  const horizon = movementHorizon(unit, proposal, byReference, alliedUnits);
  return {
    x: unit.x + proposal.dx / distance * horizon,
    y: unit.y + proposal.dy / distance * horizon,
  };
}


function staticGeometryClears(unit, proposal, map) {
  if (!map) return true;
  const radius = collisionRadius(unit);
  const end = { x: unit.x + proposal.dx, y: unit.y + proposal.dy };
  if (
    end.x < radius - EPSILON
    || end.x > map.width - radius + EPSILON
    || end.y < radius - EPSILON
    || end.y > map.height - radius + EPSILON
  ) return false;
  for (const obstacle of map.obstacles ?? []) {
    const obstacleRadius = obstacle.radius
      ?? obstacle.collisionRadius
      ?? obstacle.collision_radius
      ?? collisionRadius(obstacle);
    const vx = end.x - unit.x;
    const vy = end.y - unit.y;
    const lengthSquared = vx * vx + vy * vy;
    const projection = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1, (
      (obstacle.x - unit.x) * vx + (obstacle.y - unit.y) * vy
    ) / lengthSquared));
    const nearestX = unit.x + projection * vx;
    const nearestY = unit.y + projection * vy;
    if (Math.hypot(obstacle.x - nearestX, obstacle.y - nearestY)
        < radius + obstacleRadius - EPSILON) return false;
  }
  return true;
}


function riskFor(mover, alliedUnits, currentGraph, projectedPoints) {
  const projectedGraph = graphFor(alliedUnits, projectedPoints);
  const moverId = mover.referenceId;
  const neighbors = [...projectedGraph.get(moverId)].sort((left, right) => left - right);
  const currentNeighbors = currentGraph.get(moverId);
  const currentComponent = componentIds(currentGraph, moverId);
  let triangles = 0;
  let fourCliques = 0;
  for (let leftIndex = 0; leftIndex < neighbors.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < neighbors.length; rightIndex += 1) {
      if (!projectedGraph.get(neighbors[leftIndex]).has(neighbors[rightIndex])) continue;
      triangles += 1;
      for (let thirdIndex = rightIndex + 1; thirdIndex < neighbors.length; thirdIndex += 1) {
        const third = neighbors[thirdIndex];
        if (
          projectedGraph.get(neighbors[leftIndex]).has(third)
          && projectedGraph.get(neighbors[rightIndex]).has(third)
        ) fourCliques += 1;
      }
    }
  }
  const newNeighbors = neighbors.filter((referenceId) => !currentNeighbors.has(referenceId));
  const internalClosures = newNeighbors.filter((referenceId) => (
    currentComponent.has(referenceId)
  )).length;
  return Object.freeze({
    fourCliques,
    triangles,
    internalClosures,
    multiAdmission: currentNeighbors.size === 0 && neighbors.length >= 2 ? 1 : 0,
    newContacts: newNeighbors.length,
  });
}


function riskTuple(risk) {
  return [
    risk.fourCliques,
    risk.triangles,
    risk.internalClosures,
    risk.multiAdmission,
    risk.newContacts,
  ];
}


function compareRisk(left, right) {
  const leftTuple = riskTuple(left);
  const rightTuple = riskTuple(right);
  for (let index = 0; index < leftTuple.length; index += 1) {
    if (leftTuple[index] !== rightTuple[index]) return leftTuple[index] - rightTuple[index];
  }
  return 0;
}


function isCompactRisk(risk) {
  return risk.fourCliques > 0
    || risk.triangles > 0
    || risk.internalClosures > 0
    || risk.multiAdmission > 0;
}


function rotatedProposal(proposal, side, turn) {
  if (turn === 0) return proposal;
  const distance = Math.hypot(proposal.dx, proposal.dy);
  const heading = Math.atan2(proposal.dy, proposal.dx) + side * turn * TURN_INCREMENT;
  return Object.freeze({
    referenceId: proposal.referenceId,
    dx: Math.cos(heading) * distance,
    dy: Math.sin(heading) * distance,
  });
}


function moverPriority(left, right, byReference) {
  const targetDistance = (unit) => {
    const target = byReference.get(unit.pursuitTargetId);
    return target && target.owner !== unit.owner
      ? Math.hypot(target.x - unit.x, target.y - unit.y)
      : Infinity;
  };
  return targetDistance(left) - targetDistance(right)
    || left.referenceId - right.referenceId;
}


export function planPreventiveContactSteering(snapshot, proposals, map, { owner } = {}) {
  const {
    units, byReference, proposalByReference,
  } = normalizeInputs(snapshot, proposals, owner);
  const alliedUnits = units.filter((unit) => unit.alive !== false && unit.owner === owner);
  const currentPoints = new Map(alliedUnits.map((unit) => [
    unit.referenceId, { x: unit.x, y: unit.y },
  ]));
  const currentGraph = graphFor(alliedUnits, currentPoints);
  const chosen = new Map(proposalByReference);
  const steered = [];
  const movers = alliedUnits
    .filter((unit) => {
      const row = chosen.get(unit.referenceId);
      return Math.hypot(row.dx, row.dy) > EPSILON;
    })
    .sort((left, right) => moverPriority(left, right, byReference));

  for (const mover of movers) {
    const direct = chosen.get(mover.referenceId);
    const projectedFor = (candidate) => new Map(alliedUnits.map((unit) => {
      const row = unit.referenceId === mover.referenceId
        ? candidate : chosen.get(unit.referenceId);
      return [unit.referenceId, projectedPoint(unit, row, byReference, alliedUnits)];
    }));
    const directRisk = riskFor(mover, alliedUnits, currentGraph, projectedFor(direct));
    if (!isCompactRisk(directRisk)) continue;

    const preferredSide = mover.avoidance?.side === -1 || mover.avoidance?.side === 1
      ? mover.avoidance.side : 1;
    const candidates = [];
    for (let turn = 1; turn <= MAX_TURNS; turn += 1) {
      for (const side of [preferredSide, -preferredSide]) {
        const proposal = rotatedProposal(direct, side, turn);
        if (!staticGeometryClears(mover, proposal, map)) continue;
        candidates.push({
          proposal,
          side,
          turn,
          risk: riskFor(mover, alliedUnits, currentGraph, projectedFor(proposal)),
        });
      }
    }
    candidates.sort((left, right) => (
      compareRisk(left.risk, right.risk)
      || left.turn - right.turn
      || (left.side === preferredSide ? -1 : 1)
    ));
    const selected = candidates[0];
    if (!selected || compareRisk(selected.risk, directRisk) >= 0) continue;
    chosen.set(mover.referenceId, selected.proposal);
    steered.push(Object.freeze({
      referenceId: mover.referenceId,
      reason: "compact-contact",
      side: selected.side,
      turnRadians: selected.turn * TURN_INCREMENT,
    }));
  }

  return Object.freeze({
    proposals: Object.freeze([...chosen.values()].sort((left, right) => (
      left.referenceId - right.referenceId
    ))),
    steered: Object.freeze(steered.sort((left, right) => (
      left.referenceId - right.referenceId
    ))),
  });
}
