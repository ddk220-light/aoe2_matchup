// Spawn placement, derived from the recorded tapes and verified against every
// one of them (tests/placement.test.mjs). No fixture is read at runtime.
//
// The only thing that selects a block is (owner, family). Band edge is NOT a
// key: the same family sits at different edges depending on army size, and two
// different families share an edge -- keying on it collides.
import { PLACEMENT_TABLE } from "./placement-table.js";


// The four spawn blocks the archive records. Exported because capacity is per
// (owner, family): anything that needs to enumerate the families -- the units
// endpoint's capacityByFamily, for one -- must read them from here rather than
// keep a hand-mirrored copy that can drift.
export const FAMILIES = Object.freeze(["rvr", "kite", "siege", "waves"]);
const RANGED = new Set(["mobile_ranged", "siege_ranged"]);


// Which spawn block a pairing uses, from the two units' combat classes. The
// order of these tests is the archive's own: both-ranged wins over one-mobile,
// which wins over one-siege.
export function resolveFamily({ side2Class, side3Class }) {
  const bothRanged = RANGED.has(side2Class) && RANGED.has(side3Class);
  if (bothRanged) return "rvr";
  if (side2Class === "mobile_ranged" || side3Class === "mobile_ranged") return "kite";
  if (side2Class === "siege_ranged" || side3Class === "siege_ranged") return "siege";
  return "waves";
}


function cellsFor(owner, family) {
  if (owner !== 2 && owner !== 3) {
    throw new RangeError(`owner must be 2 or 3, got ${owner}`);
  }
  if (!FAMILIES.includes(family)) {
    throw new RangeError(`unknown family ${family}`);
  }
  return PLACEMENT_TABLE[`${owner}@${family}`];
}


// How many units this side can field in this family. The archive never grew a
// side-2 siege block past 16, so that is the honest ceiling: beyond it there is
// no measured geometry, and inventing some would be exactly the fitting this
// simulator exists to avoid.
export function sideCapacity(owner, family) {
  return cellsFor(owner, family).length;
}


export function placeArmy({ owner, count, family }) {
  const cells = cellsFor(owner, family);
  if (!Number.isSafeInteger(count) || count < 1) {
    throw new RangeError(`count must be a positive integer, got ${count}`);
  }
  if (count > cells.length) {
    throw new RangeError(
      `owner ${owner} family ${family} has only ${cells.length} cells, asked for ${count}`);
  }
  return Object.freeze(cells.slice(0, count).map(
    ([x, y]) => Object.freeze({ x, y })));
}
