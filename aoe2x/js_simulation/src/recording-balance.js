// Default benchmark for NEW plans. Historical plans keep their explicit mode.
// Comparison prices are synthetic; purchase prices always remain real prices.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const POLICY = 'geometric_shared_discount_unit_count_v2';
const RESOURCES = ['food', 'wood', 'gold'];

function positive(value, name) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${name} must be positive and finite`);
  }
}

function resources(value) {
  return value && RESOURCES.every(r => Number.isFinite(value[r]) && value[r] >= 0);
}

export function comparisonResourcesFor(purchase, shared) {
  if (!purchase || !Number.isSafeInteger(purchase.unitsPerPurchase) || purchase.unitsPerPurchase < 1
      || !resources(purchase.baseCost) || !resources(purchase.effectiveCost) || typeof shared !== 'boolean') {
    throw new RangeError('Invalid per-unit purchase or shared-unit classification');
  }
  const basePerUnit = Object.fromEntries(
    RESOURCES.map(r => [r, purchase.baseCost[r] / purchase.unitsPerPurchase]),
  );
  const comparisonResources = { ...purchase.effectiveCost };
  if (shared) {
    // Only soften positive savings. Gold and cost increases stay fully effective.
    for (const r of ['food', 'wood']) {
      comparisonResources[r] += 0.5 * Math.max(0, basePerUnit[r] - comparisonResources[r]);
    }
  }
  return { basePerUnit, comparisonResources };
}

export function geometricEvidence(unit, civ, weights) {
  const bytes = readFileSync(new URL('../../../data/recording-balance.json', import.meta.url));
  const catalog = JSON.parse(bytes);
  if (catalog.schemaVersion !== 1 || catalog.policy !== POLICY || catalog.populationMode !== 'one_per_unit'
      || catalog.foodDiscountEffectiveness !== 0.5 || catalog.woodDiscountEffectiveness !== 0.5
      || catalog.goldDiscountEffectiveness !== 1) {
    throw new RangeError('Unsupported geometric benchmark policy');
  }
  const costs = JSON.parse(readFileSync(new URL('../../../data/recording-costs.json', import.meta.url)));
  const key = `${civ}|${unit.slug}`;
  const entry = catalog.units[key];
  const purchase = costs.units[key];
  if (!entry || entry.master !== unit.master || !purchase || purchase.master !== unit.master) {
    throw new RangeError(`No verified geometric balance identity: ${key}`);
  }
  positive(entry.population, 'Population');
  if (!resources(weights) || Object.keys(weights).length !== RESOURCES.length) {
    throw new RangeError('Invalid resource weights');
  }
  const { basePerUnit, comparisonResources } = comparisonResourcesFor(purchase, entry.sharedAcrossCivilizations);
  const comparisonCost = RESOURCES.reduce((sum, r) => sum + comparisonResources[r] * weights[r], 0);
  positive(comparisonCost, 'Comparison cost');
  return {
    policy: catalog.policy,
    catalogSha256: createHash('sha256').update(bytes).digest('hex'),
    basePerUnit,
    comparisonResources,
    comparisonCost,
    // This benchmark gives every physical unit equal population weight. Keep
    // game population as provenance, never as a multiplier for new counts.
    population: 1,
    catalogPopulation: entry.population,
    sharedAcrossCivilizations: entry.sharedAcrossCivilizations,
    score: comparisonCost,
  };
}

export function geometricCounts(a, b, cap) {
  positive(a, 'Side 2 score');
  positive(b, 'Side 3 score');
  if (!Number.isSafeInteger(cap) || cap < 1 || cap > 27) {
    throw new RangeError('Cap must be an integer 1-27');
  }
  const ratio = Math.sqrt(Math.min(a, b) / Math.max(a, b));
  const smaller = Math.max(1, Math.min(cap, Math.floor(cap * ratio + 0.5)));
  return a <= b ? [cap, smaller] : [smaller, cap];
}
