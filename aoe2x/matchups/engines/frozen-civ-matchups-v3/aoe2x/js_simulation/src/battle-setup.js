import { isRangedClass } from "./lab-scenario.js";

// BALANCE_POLICY.md, September 22, 2026. effectiveCost is the fully
// discounted purchase cost of one physical unit, including batch division.
export function deriveRecordedBattleSetup(side2, side3, { cap = 27 } = {}) {
  const weightedCost = ({ effectiveCost: { food, wood, gold } }) => (
    food + 0.9 * wood + 1.1 * gold
  );
  const cost2 = weightedCost(side2);
  const cost3 = weightedCost(side3);
  const n2 = cost2 <= cost3 ? cap : Math.max(1, Math.round(cap * Math.sqrt(cost3 / cost2)));
  const n3 = cost3 <= cost2 ? cap : Math.max(1, Math.round(cap * Math.sqrt(cost2 / cost3)));
  const ranged2 = isRangedClass(side2.class);
  const ranged3 = isRangedClass(side3.class);
  const rangedOwner = ranged2 === ranged3 ? null : (ranged2 ? 2 : 3);
  const rangedArmyCost = rangedOwner === 2 ? n2 * cost2 : n3 * cost3;
  const player4Count = rangedOwner === null ? 0 : Math.round(
    Math.max(5, Math.min(10, 5 + (rangedArmyCost - 1000) / 1800)),
  );
  return { n2, n3, cost2, cost3, player4Count, rangedOwner,
    policy: "geometric_full_discount_weighted_resources_v3",
    bufferPolicy: "fielded_weighted_cost_v1" };
}
