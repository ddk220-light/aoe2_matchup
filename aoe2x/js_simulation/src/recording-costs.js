// Generated from the installed DAT, including civ and researched cost effects.
// Base registry prices are descriptive only, never a purchase-cost fallback.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const bytes = readFileSync(new URL('../../../data/recording-costs.json', import.meta.url));
const catalog = JSON.parse(bytes);
export const COST_BASIS = catalog.costBasis;
export const COST_CATALOG_SHA256 = createHash('sha256').update(bytes).digest('hex');

export function resolvePurchaseCost(unit, civ = unit.civ) {
  const entry = catalog.units[`${civ}|${unit.slug}`];
  if (!entry || entry.master !== unit.master) throw new RangeError(`No verified Imperial cost for ${civ}/${unit.slug}`);
  const cost = entry.effectiveCost;
  if (!['food', 'wood', 'gold'].every(r => Number.isFinite(cost[r]) && cost[r] >= 0)
      || Object.values(cost).reduce((a,b) => a+b,0) <= 0) throw new RangeError('Invalid effective purchase cost');
  return Object.freeze({...cost});
}
