// How many of each unit an even fight buys.
//
// Measured, not chosen: this rule reproduces the starting counts of all 101
// distinct matchups in the standard-units archive exactly. The cheaper side
// buys as many as a 3000 budget allows, capped at 21; the other side then
// spends that same weighted amount, which is what makes the fight even rather
// than the counts equal.
import { unitBySlug } from "./unit-registry.js";


export const PURCHASE_BUDGET = 3000;
export const PURCHASE_CAP = 21;

const GOLD_WEIGHT = 1.5;


export function weightedCost({ food = 0, wood = 0, gold = 0 } = {}) {
  return food + wood + GOLD_WEIGHT * gold;
}


function costFor(slug) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  return weightedCost(unit.baseCost);
}


export function deriveCounts(slugA, slugB, {
  budget = PURCHASE_BUDGET,
  cap = PURCHASE_CAP,
  // Placement capacity is per (owner, family) and asymmetric (a side-2 siege
  // block holds only 16), but this module knows nothing about owners or
  // families -- the caller resolves those and passes the two ceilings in.
  // Defaulting to Infinity means every call site that does not pass them
  // (in particular the 101-row archive-reproduction test) is unaffected:
  // capacity must never bind on a recorded matchup.
  capacityA = Infinity,
  capacityB = Infinity,
} = {}) {
  const costA = costFor(slugA);
  const costB = costFor(slugB);
  return deriveCountsFromCosts(costA, costB, {
    budget, cap, capacityA, capacityB,
  });
}


export function deriveCountsFromCosts(costA, costB, {
  budget = PURCHASE_BUDGET,
  cap = PURCHASE_CAP,
  capacityA = Infinity,
  capacityB = Infinity,
} = {}) {
  if (!(costA > 0) || !(costB > 0)) {
    throw new RangeError(`unit costs must be positive, got ${costA} and ${costB}`);
  }
  const cheaperIsA = costA <= costB;
  const cheapCost = cheaperIsA ? costA : costB;
  const dearCost = cheaperIsA ? costB : costA;
  const cheapCapacity = cheaperIsA ? capacityA : capacityB;
  const dearCapacity = cheaperIsA ? capacityB : capacityA;

  const cheapCount = Math.min(cap, Math.floor(budget / cheapCost), cheapCapacity);
  const cheapSpend = cheapCount * cheapCost;
  const dearCount = Math.max(1, Math.min(Math.floor(cheapSpend / dearCost), dearCapacity));

  const countA = cheaperIsA ? cheapCount : dearCount;
  const countB = cheaperIsA ? dearCount : cheapCount;
  return {
    countA,
    countB,
    costA,
    costB,
    spendA: countA * costA,
    spendB: countB * costB,
  };
}
