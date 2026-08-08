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
} = {}) {
  const costA = costFor(slugA);
  const costB = costFor(slugB);
  const cheaperIsA = costA <= costB;
  const cheapCost = cheaperIsA ? costA : costB;
  const dearCost = cheaperIsA ? costB : costA;

  const cheapCount = Math.min(cap, Math.floor(budget / cheapCost));
  const cheapSpend = cheapCount * cheapCost;
  const dearCount = Math.max(1, Math.floor(cheapSpend / dearCost));

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
