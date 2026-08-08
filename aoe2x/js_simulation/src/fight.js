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
// Individual requests are bounded by the real per-(owner, family) capacity
// (see validateCount below), which is never larger than this.
export const FIGHT_SIDE_CAP = 21;

// Movement is fully observable from each snapshot's positions (every unit's
// x/y is already in the units array every tick), and at 60 Hz it is ~97% of
// the event log (measured: 71,469 of 73,810 events in an imp_elite_skirm vs
// halberdier 21v21 fight are move/blocked). Excluding them from the wire
// format is also a UX improvement, not just a size cut: it makes the
// viewer's event cursor step between hits instead of between movement ticks.
// eventLogHash below still hashes the full, unfiltered engine log, so this
// exclusion cannot hide a determinism regression.
const WIRE_EVENT_TYPES_EXCLUDED = Object.freeze(new Set(["move", "blocked"]));

const REFERENCE_BASE = { 2: 9000, 3: 9500 };
const MAX_TICKS = 9000;
const mechanicsCache = new Map();


async function loadMechanics(root, unit) {
  // Keyed on root as well as fixture: two callers pointed at different repo
  // roots (as the test suite and a running server both can be) must not
  // share a cache entry, matching the deliberately root-keyed
  // championDataByRoot in server.mjs.
  const key = `${root}|${unit.fixture}`;
  if (!mechanicsCache.has(key)) {
    mechanicsCache.set(key, JSON.parse(await readFile(
      new URL(`fixtures/unit_stats/${unit.fixture}`, root), "utf8")));
  }
  return mechanicsCache.get(key);
}


function requireUnit(slug) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  return unit;
}


// Placement capacity is per (owner, family) and asymmetric (a side-2 siege
// block holds only 16 cells; every other owner/family combination holds 21),
// so the global FIGHT_SIDE_CAP alone is not a valid bound for either side --
// deriveCounts can otherwise hand a side more units than its own placement
// block can seat, and an explicit n2/n3 can ask for the same thing directly.
function validateCount(count, capacity, family, owner) {
  if (!Number.isSafeInteger(count) || count < 1 || count > capacity) {
    throw new RangeError(
      `count must be an integer 1-${capacity} for owner ${owner}'s ${family} `
      + `formation, got ${count}`);
  }
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
// mechanics fixture, which was 85% of the payload. facing is included because
// it changes every tick (the renderer's direction arrow); the per-type fields
// the renderer also needs -- unit master, collision radius, attack range --
// do not change per tick, so they live once in unitIndex instead.
function slimSnapshot(snapshot) {
  return Object.freeze({
    tick: snapshot.tick,
    units: Object.freeze(snapshot.units.map((unit) => Object.freeze([
      unit.referenceId,
      unit.x,
      unit.y,
      unit.facing,
      unit.hp,
      unit.alive ? 1 : 0,
      unit.action,
      unit.pursuitTargetId,
      unit.engagedTargetId,
      unit.attackTargetId,
    ]))),
    events: Object.freeze(
      snapshot.events.filter((entry) => !WIRE_EVENT_TYPES_EXCLUDED.has(entry.type)),
    ),
  });
}


export async function runFight(root, { side2Slug, n2, side3Slug, n3 }) {
  // Counts are optional: omit BOTH and they come from the purchase rule, so
  // the formula lives in purchase.js and nowhere else. One given without the
  // other is a malformed request, not a half-derived fight -- the HTTP layer
  // already rejects that shape (server.mjs fightSelection); this guards the
  // module entry point the same way for any other caller.
  const n2Given = n2 !== undefined;
  const n3Given = n3 !== undefined;
  if (n2Given !== n3Given) {
    throw new RangeError("n2 and n3 must both be given, or both omitted to derive them");
  }
  const derivedCounts = !n2Given;

  const side2 = requireUnit(side2Slug);
  const side3 = requireUnit(side3Slug);

  // Family (and therefore each side's placement capacity) depends only on
  // the two units' combat classes, never on the counts -- so it is resolved
  // before deriveCounts runs, and its capacities are fed into deriveCounts
  // as the ceiling on what the purchase rule may hand out.
  const family = resolveFamily({ side2Class: side2.class, side3Class: side3.class });
  const capacity2 = sideCapacity(2, family);
  const capacity3 = sideCapacity(3, family);

  const derived = derivedCounts
    ? deriveCounts(side2Slug, side3Slug, { capacityA: capacity2, capacityB: capacity3 })
    : null;
  const count2 = derived ? derived.countA : n2;
  const count3 = derived ? derived.countB : n3;
  validateCount(count2, capacity2, family, 2);
  validateCount(count3, capacity3, family, 3);

  const [mechanics2, mechanics3] = await Promise.all([
    loadMechanics(root, side2),
    loadMechanics(root, side3),
  ]);

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
      owner,
      slug: unit.slug,
      label: unit.label,
      maxHp: mechanics.hp,
      master: mechanics.unit_master,
      collisionRadius: mechanics.collision_size_tiles.x,
      attackRange: mechanics.attack_range_tiles,
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
    // Hashes the full, unfiltered engine event log -- not the wire-slimmed
    // per-snapshot events below -- so dropping move/blocked from the payload
    // can never mask a change in what the engine actually did.
    eventLogHash: hashCanonicalJson(result.events),
    unitIndex: Object.freeze(unitIndex),
    snapshots: Object.freeze(result.snapshots.map(slimSnapshot)),
  });
}
