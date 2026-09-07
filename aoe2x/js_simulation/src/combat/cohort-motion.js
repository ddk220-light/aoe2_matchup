import { collisionRadius } from "./targeting.js";

const TURN_STEP_RADIANS = Math.PI / 12;
const MAX_TURNS = 6;
const EPSILON = 1e-12;

function stepClear(unit, dx, dy, enemies, map) {
  const radius = collisionRadius(unit);
  const x = unit.x + dx;
  const y = unit.y + dy;
  if (x < radius || x > map.width - radius || y < radius || y > map.height - radius) {
    return false;
  }
  for (const enemy of enemies) {
    const reach = radius + collisionRadius(enemy);
    if (Math.max(Math.abs(x - enemy.x), Math.abs(y - enemy.y)) < reach - EPSILON) {
      return false;
    }
  }
  return true;
}

function candidateOffsets(preferredTurn) {
  const result = [{ turns: 0, sideRank: 0 }];
  for (let turns = 1; turns <= MAX_TURNS; turns += 1) {
    result.push({ turns: preferredTurn * turns, sideRank: 0 });
    result.push({ turns: -preferredTurn * turns, sideRank: 1 });
  }
  return result;
}

function better(candidate, best) {
  if (best === null) return true;
  if (candidate.clear !== best.clear) return candidate.clear > best.clear;
  if (Math.abs(candidate.forward - best.forward) > EPSILON) {
    return candidate.forward > best.forward;
  }
  if (candidate.absTurns !== best.absTurns) return candidate.absTurns < best.absTurns;
  return candidate.sideRank < best.sideRank;
}

export function planCohortContactMotion({ units, proposals, enemies, map, preferredTurn }) {
  if (!Array.isArray(units) || !Array.isArray(proposals) || !Array.isArray(enemies)) {
    throw new TypeError("units, proposals, and enemies must be arrays");
  }
  if (units.length !== proposals.length) {
    throw new RangeError("cohort units and proposals must have equal length");
  }
  if (units.length < 2) return Object.freeze([...proposals]);
  const movers = proposals.map((proposal, index) => ({
    unit: units[index],
    proposal,
    distance: Math.hypot(proposal.dx, proposal.dy),
  })).filter(({ distance }) => distance > EPSILON);
  if (movers.length === 0) return Object.freeze([...proposals]);
  if (!movers.some(({ unit, proposal }) => (
    !stepClear(unit, proposal.dx, proposal.dy, enemies, map)
  ))) return Object.freeze([...proposals]);

  let meanX = 0;
  let meanY = 0;
  for (const { proposal, distance } of movers) {
    meanX += proposal.dx / distance;
    meanY += proposal.dy / distance;
  }
  if (Math.hypot(meanX, meanY) <= EPSILON) return Object.freeze([...proposals]);
  const baseAngle = Math.atan2(meanY, meanX);
  const turn = preferredTurn === -1 ? -1 : 1;
  let best = null;
  for (const offset of candidateOffsets(turn)) {
    const angle = baseAngle + offset.turns * TURN_STEP_RADIANS;
    const ux = Math.cos(angle);
    const uy = Math.sin(angle);
    let clear = 0;
    let forward = 0;
    for (const { unit, proposal, distance } of movers) {
      const dx = ux * distance;
      const dy = uy * distance;
      if (stepClear(unit, dx, dy, enemies, map)) clear += 1;
      forward += dx * (proposal.dx / distance) + dy * (proposal.dy / distance);
    }
    const candidate = {
      angle,
      clear,
      forward,
      absTurns: Math.abs(offset.turns),
      sideRank: offset.sideRank,
    };
    if (better(candidate, best)) best = candidate;
  }

  const ux = Math.cos(best.angle);
  const uy = Math.sin(best.angle);
  return Object.freeze(proposals.map((proposal) => {
    const distance = Math.hypot(proposal.dx, proposal.dy);
    return distance <= EPSILON
      ? Object.freeze({ referenceId: proposal.referenceId, dx: 0, dy: 0 })
      : Object.freeze({
        referenceId: proposal.referenceId,
        dx: ux * distance,
        dy: uy * distance,
      });
  }));
}
