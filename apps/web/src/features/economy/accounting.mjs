/**
 * Army-economics accounting for one Battle Sim pair: a line-for-line port of the
 * runtime part of aoe2x/economy/accounting.py (the Python reference). Pure
 * functions, no DOM, no I/O.
 *
 * Exact parity rules (checked by tests/economy/matchup-parity.test.mjs):
 * - Every Python sum() goes through pySum(), which reproduces CPython >= 3.12
 *   float summation (Neumaier compensation; the site's Python is 3.13).
 * - Operation order, max()/min() tie behaviour, dict (Map) insertion order and
 *   object identity (shared lookup entries) follow the Python code.
 */

export const RESOURCES = Object.freeze(['food', 'wood', 'gold', 'stone']);
export const CONTEXT_SCHEMA_VERSION = 4;
export const TRAINING_WINDOW_SECONDS = 60;
export const RESOURCE_WEIGHTS = Object.freeze({food: 1, wood: 1, gold: 1.5, stone: 3});

const hasOwn = (object, key) => object != null && Object.prototype.hasOwnProperty.call(object, key);
/** dict.get(key, fallback) */
export const get = (object, key, fallback) => (hasOwn(object, key) ? object[key] : fallback);
/** Python truthiness of a JSON value. */
export function truthy(value) {
    if (value === null || value === undefined || value === false || value === 0 || value === '') return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === 'object') return Object.keys(value).length > 0;
    return true;
}

/**
 * CPython (>= 3.12) builtin sum() over floats: the first item is added to the
 * integer start 0 plainly, then Neumaier-compensated addition; the compensation
 * is applied once at the end when it is nonzero and finite.
 */
export function pySum(values) {
    let total = 0, compensation = 0, started = false;
    for (const x of values) {
        if (!started) { total = 0 + x; started = true; continue; }
        const t = total + x;
        if (Math.abs(total) >= Math.abs(x)) compensation += (total - t) + x;
        else compensation += (x - t) + total;
        total = t;
    }
    if (compensation !== 0 && Number.isFinite(compensation)) total += compensation;
    return total;
}

/** math.isclose(a, b, rel_tol, abs_tol) */
export function isClose(a, b, relTol = 1e-9, absTol = 0) {
    if (a === b) return true;
    if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
    const diff = Math.abs(b - a);
    return diff <= Math.abs(relTol * b) || diff <= Math.abs(relTol * a) || diff <= absTol;
}

export function resources(values) {
    const source = truthy(values) ? values : {};
    return Object.fromEntries(RESOURCES.map(r => [r, Number(get(source, r, 0))]));
}

export function buildingValue(cost) {
    return pySum(RESOURCES.map(r => get(cost, r, 0) * RESOURCE_WEIGHTS[r]));
}

export function addCosts(...costs) {
    return Object.fromEntries(RESOURCES.map(r => [r, pySum(costs.map(c => get(c, r, 0)))]));
}

export function weightedCost(cost) {
    return Object.fromEntries(RESOURCES.map(r => [r, get(cost, r, 0) * RESOURCE_WEIGHTS[r]]));
}

/** Evaluate the compiled labor price vertices; negative resource bills are rebates. */
export function compiledLabor(cost, prices) {
    const demand = Object.values(resources(cost));
    if (demand.some(v => !Number.isFinite(v))) throw new RangeError('Resource bill must be finite');
    let seconds;
    if (demand.every(v => v <= 0)) seconds = 0;
    else if (prices === null || prices === undefined) return null;
    else {
        if (!prices.length) throw new RangeError('max() arg is an empty sequence');
        let best;
        prices.forEach((row, index) => {
            const value = pySum(demand.map((v, i) => v * row[i]));
            if (index === 0 || value > best) best = value;
        });
        seconds = best > 0 ? best : 0;  // max(0.0, best)
    }
    return {seconds, villagerMinutes: seconds / 60};
}

/** Whole buildings completing all purchase orders within the fixed window. */
export function productionForWindow(route, orders, unitsPerPurchase = 1) {
    const result = {...(route || {}), windowSeconds: TRAINING_WINDOW_SECONDS,
        buildingCount: null, investmentCost: null, grossInvestmentCost: null, rebate: null,
        weightedInvestmentCost: null, ordersPerBuilding: null, trainingSeconds: null, spareUnitCapacity: null};
    if (route === null || route === undefined) return {...result, status: 'unresolved_training_route'};
    const seconds = route.secondsPerOrder;
    if (!Number.isFinite(seconds) || seconds <= 0) throw new RangeError('Training time must be positive and finite');
    if (Object.values(resources(route.cost)).some(v => !Number.isFinite(v) || v < 0)) {
        throw new RangeError('Building costs must be finite and nonnegative');
    }
    const perBuilding = Math.floor(TRAINING_WINDOW_SECONDS / seconds);
    result.ordersPerBuilding = perBuilding;
    if (truthy(orders) && !truthy(perBuilding)) return {...result, status: 'training_exceeds_window'};
    const count = truthy(orders) ? Math.ceil(orders / perBuilding) : 0;
    // A completion rebate (Wu: +55 food per military building/Dock) is credited
    // against each building; the gross cost stays visible.
    const rebate = resources(get(route, 'completionRebate', null) || {});
    const cost = resources(route.cost);
    const net = Object.fromEntries(Object.entries(cost).map(([r, v]) => [r, v - rebate[r]]));
    const scale = values => Object.fromEntries(Object.entries(values).map(([r, v]) => [r, v * count]));
    return {...result, status: 'modeled', buildingCount: count,
        investmentCost: scale(net), grossInvestmentCost: scale(cost), rebate: scale(rebate),
        weightedInvestmentCost: buildingValue(net) * count,
        trainingSeconds: truthy(orders) ? Math.ceil(orders / count) * seconds : 0,
        spareUnitCapacity: (count * perBuilding - orders) * unitsPerPurchase};
}

function compareTuples(a, b) {
    for (let i = 0; i < a.length; i += 1) {
        if (a[i] < b[i]) return -1;
        if (a[i] > b[i]) return 1;
    }
    return 0;
}

export function selectInvestmentRoute(routes, orders, batch, baseCost, prices) {
    const alternatives = routes.map(route => productionForWindow(route, orders, batch));
    const feasible = alternatives.filter(route => route.status === 'modeled');
    for (const route of feasible) {
        route.combinedLabor = compiledLabor(weightedCost(addCosts(baseCost, route.investmentCost)), prices);
    }
    if (!feasible.length) {
        const result = productionForWindow(null, orders, batch);
        if (alternatives.length) result.status = 'training_exceeds_window';
        return [result, alternatives];
    }
    // Withheld labor can still show a provisional resource-priced building
    // setup. It never makes the headline investment score available.
    const key = route => [route.combinedLabor !== null ? route.combinedLabor.seconds : route.weightedInvestmentCost,
        route.trainingSeconds, route.id, get(route, 'trainedUnitId', 0)];
    feasible.sort((a, b) => compareTuples(key(a), key(b)));
    return [feasible[0], [...feasible, ...alternatives.filter(route => route.status !== 'modeled')]];
}

export function queueSeconds(orders, production) {
    if (orders === 0) return 0;
    const count = production.buildingCount;
    const seconds = get(production, 'secondsPerOrder', null);
    if (count === null || count === undefined || count <= 0 || seconds === null) return null;
    return Math.ceil(orders / count) * seconds;
}

export function armyInvestment(armyCost, production, commonResearch, prices) {
    let status = production.status;
    if (status === 'modeled' && !commonResearch.costIsFixed) status = 'unresolved_common_research_cost';
    if (status === 'modeled' && (prices === null || prices === undefined)) status = 'unresolved_labor';
    const components = {army: resources(armyCost), buildings: production.investmentCost,
        commonResearch: commonResearch.net};
    const bill = components.buildings !== null ? addCosts(...Object.values(components)) : null;
    const standaloneLabor = Object.fromEntries(Object.entries(components).map(([key, cost]) => [key,
        cost !== null && (key !== 'commonResearch' || commonResearch.costIsFixed)
            ? compiledLabor(weightedCost(cost), prices) : null]));
    return {status, components, cost: bill,
        weightedCost: bill !== null ? weightedCost(bill) : null,
        standaloneLabor,
        labor: status === 'modeled' ? compiledLabor(weightedCost(bill), prices) : null};
}

export function investmentComparison(teams) {
    const scores = teams.map(team => team.investment.labor);
    if (scores.some(score => score === null)) return {status: 'unavailable', lowerTeam: null, savingPercent: null};
    const [a, b] = scores.map(score => score.seconds);
    const equal = isClose(a, b, 1e-9, 1e-9);
    const low = b < a ? b : a, high = b > a ? b : a;  // Python min()/max() keep the first on ties
    return {status: 'available', lowerTeam: equal ? null : (a < b ? 1 : 2),
        savingPercent: equal ? 0 : 100 * (1 - low / high)};
}

export function researchTotals(technologies) {
    const byId = new Map();
    for (const tech of technologies) byId.set(tech.id, tech);  // dict: first position, last value
    const rows = [...byId.values()];
    const workload = rows.some(t => t.seconds === null) ? null : pySum(rows.map(t => t.seconds));
    const byBuilding = {};
    for (const t of rows) {
        if (t.seconds !== null && t.seconds > 0) {
            const name = get(get(t, 'building', {}), 'name', 'Unknown');
            byBuilding[name] = get(byBuilding, name, 0) + t.seconds;
        }
    }
    const totals = {technologyCount: rows.length, workloadSeconds: workload, workloadByBuilding: byBuilding,
        costIsFixed: rows.every(t => truthy(get(t, 'costIsFixed', true)))};
    for (const kind of ['upfront', 'refund', 'net']) {
        totals[kind] = Object.fromEntries(RESOURCES.map(r => [r, pySum(rows.map(t => get(t[kind], r, 0)))]));
    }
    return totals;
}

export function compareResearch(left, right) {
    const maps = [left, right].map(side => {
        const map = new Map();
        for (const tech of side) map.set(tech.id, tech);
        return map;
    });
    const common = new Set([...maps[0].keys()].filter(id => maps[1].has(id)));
    const ids = [...common].sort((a, b) => a - b);
    const commonSides = maps.map(map => researchTotals(ids.map(id => map.get(id))));
    return {commonIds: ids, common: commonSides,
        exclusive: maps.map(map => researchTotals([...map].filter(([id]) => !common.has(id)).map(([, tech]) => tech))),
        commonWorkloadDifferenceSeconds: commonSides.every(side => side.workloadSeconds !== null)
            ? commonSides[0].workloadSeconds - commonSides[1].workloadSeconds : null,
        commonCostDifference: Object.fromEntries(RESOURCES.map(r => [r, commonSides[0].net[r] - commonSides[1].net[r]]))};
}

/** Cost, weighted cost, weighted villager-minutes and summed research time of a package. */
export function researchSummary(totals, prices) {
    const weighted = weightedCost(totals.net);
    const labor = totals.costIsFixed ? compiledLabor(weighted, prices) : null;
    return {technologyCount: totals.technologyCount, net: totals.net,
        weightedCost: pySum(Object.values(weighted)),
        villagerMinutes: labor === null ? null : labor.villagerMinutes,
        workloadSeconds: totals.workloadSeconds, costIsFixed: totals.costIsFixed};
}

export function researchInfrastructure(technologies, production) {
    const buildings = new Map();
    const existing = truthy(get(production, 'buildingCount', 0)) ? get(production, 'id', null) : null;
    for (const tech of technologies) {
        const building = get(tech, 'building', null);
        if (!truthy(building) || truthy(get(tech, 'automaticFree', null))) continue;
        buildings.set(building.id, {...building, alreadyAvailable: building.id === existing});
    }
    const rows = [...buildings.keys()].sort((a, b) => a - b).map(id => buildings.get(id));
    return {buildings: rows, additionalCost: Object.fromEntries(RESOURCES.map(r => [r,
        pySum(rows.filter(b => !b.alreadyAvailable).map(b => get(b.cost, r, 0)))]))};
}
