// One fight, composed from the registry and the derived placement. Nothing
// here reads a recorded roster: this is the path a product request takes.
import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "./canonical-json.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { placeArmy, resolveFamily, sideCapacity } from "./placement.js";
import { deriveCounts } from "./purchase.js";
import { unitBySlug } from "./unit-registry.js";


// Capacity is per (owner, family); this is the largest any of them offers.
export const FIGHT_SIDE_CAP = 21;

const REFERENCE_BASE = { 2: 9000, 3: 9500 };
const MAX_TICKS = 9000;
const mechanicsCache = new Map();


async function loadMechanics(root, unit) {
  if (!mechanicsCache.has(unit.fixture)) {
    mechanicsCache.set(unit.fixture, JSON.parse(await readFile(
      new URL(`fixtures/unit_stats/${unit.fixture}`, root), "utf8")));
  }
  return mechanicsCache.get(unit.fixture);
}


function resolveUnit(slug, count) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  if (!Number.isSafeInteger(count) || count < 1 || count > FIGHT_SIDE_CAP) {
    throw new RangeError(`count must be an integer 1-${FIGHT_SIDE_CAP}, got ${count}`);
  }
  return unit;
}


// Exactly one mobile-ranged side kites. That is the rule the archive follows in
// all 32 calibrated kiting matchups; siege never kites, and two mobile-ranged
// sides are the unmodelled ranged-vs-ranged case, which runs natively.
function kiteOwnerFor(side2, side3) {
  const two = side2.class === "mobile_ranged";
  const three = side3.class === "mobile_ranged";
  if (two === three) return null;
  return two ? 2 : 3;
}


// Same key names and freezing the viewer's cursor and renderer already demand
// (tick === index, frozen units array, frozen events array). Only the per-unit
// record changes: a positional array instead of an object carrying the whole
// mechanics fixture, which was 85% of the payload.
function slimSnapshot(snapshot) {
  return Object.freeze({
    tick: snapshot.tick,
    units: Object.freeze(snapshot.units.map((unit) => Object.freeze([
      unit.referenceId,
      unit.x,
      unit.y,
      unit.hp,
      unit.alive ? 1 : 0,
      unit.action,
      unit.pursuitTargetId,
      unit.engagedTargetId,
      unit.attackTargetId,
    ]))),
    events: snapshot.events,
  });
}


export async function runFight(root, { side2Slug, n2, side3Slug, n3 }) {
  // Counts are optional: omit either and both come from the purchase rule, so
  // the formula lives in purchase.js and nowhere else.
  const derivedCounts = n2 === undefined || n3 === undefined;
  const derived = derivedCounts ? deriveCounts(side2Slug, side3Slug) : null;
  const count2 = derived ? derived.countA : n2;
  const count3 = derived ? derived.countB : n3;

  const side2 = resolveUnit(side2Slug, count2);
  const side3 = resolveUnit(side3Slug, count3);
  const [mechanics2, mechanics3] = await Promise.all([
    loadMechanics(root, side2),
    loadMechanics(root, side3),
  ]);

  const family = resolveFamily({ side2Class: side2.class, side3Class: side3.class });
  const roster = [
    ...placeArmy({ owner: 2, count: count2, family })
      .map((cell, index) => ({ owner: 2, cell, index, unit: side2, mechanics: mechanics2 })),
    ...placeArmy({ owner: 3, count: count3, family })
      .map((cell, index) => ({ owner: 3, cell, index, unit: side3, mechanics: mechanics3 })),
  ];

  const units = roster.map(({ owner, cell, index, mechanics }, rank) => createUnitState({
    referenceId: REFERENCE_BASE[owner] + index,
    owner,
    x: cell.x,
    y: cell.y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: roster.length,
  }));

  const kiteOwner = kiteOwnerFor(side2, side3);
  const result = runWorld(createWorld({
    ratio: `${count2}v${count3}`,
    units,
    ...(kiteOwner === null ? {} : { kiteOwner }),
  }), { maxTicks: MAX_TICKS });

  const live = result.world.units.filter(({ alive }) => alive);
  const unitIndex = {};
  for (const { owner, index, unit, mechanics } of roster) {
    unitIndex[REFERENCE_BASE[owner] + index] = Object.freeze({
      owner, slug: unit.slug, label: unit.label, maxHp: mechanics.hp,
    });
  }

  return Object.freeze({
    schemaVersion: 1,
    side2: Object.freeze({
      slug: side2.slug, label: side2.label, civ: side2.civ, count: count2, class: side2.class }),
    side3: Object.freeze({
      slug: side3.slug, label: side3.label, civ: side3.civ, count: count3, class: side3.class }),
    family,
    derivedCounts,
    kiteOwner,
    ticks: result.ticks,
    winnerOwner: live.length ? live[0].owner : null,
    winnerHp: live.reduce((total, unit) => total + unit.hp, 0),
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick, ratio: `${count2}v${count3}`, units: result.world.units }),
    eventLogHash: hashCanonicalJson(result.events),
    unitIndex: Object.freeze(unitIndex),
    snapshots: Object.freeze(result.snapshots.map(slimSnapshot)),
    events: result.events,
  });
}
