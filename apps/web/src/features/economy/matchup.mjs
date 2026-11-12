/**
 * The 60-second army investment of one Battle Sim pair, computed in the browser
 * from the two civilizations' published economy documents. A port of
 * aoe2x/economy/matchup.py evaluate_matchup() (the Python reference): same
 * inputs, same result object, number for number (see accounting.mjs).
 *
 * Pure functions, no DOM, no I/O. loader.mjs fetches the documents.
 */
import {
    CONTEXT_SCHEMA_VERSION, addCosts, armyInvestment, compareResearch, get, investmentComparison,
    queueSeconds, researchInfrastructure, researchSummary, researchTotals, selectInvestmentRoute,
} from './accounting.mjs';

const PACKAGES = ['military', 'production', 'economicSetup'];
const clone = value => structuredClone(value);

/**
 * Runtime data equivalent to Python's RuntimeData: the metadata document
 * (/data/<version>/metadata.json or /api/economy) plus any number of
 * civilization documents (/data/<version>/<civ>.json or /api/economy/<Civ>).
 */
export function createRuntimeData(metadataDocument, civilizationDocuments) {
    const metadata = metadataDocument.metadata;
    if (metadata?.schemaVersion !== CONTEXT_SCHEMA_VERSION) throw new Error('Unsupported army context schema');
    const civilizations = new Map(), units = new Map();
    for (const document of civilizationDocuments) {
        if (document.schemaVersion !== metadata.schemaVersion || document.contextVersion !== metadata.contextVersion) {
            throw new Error(`Army economics data for ${document.civ} belongs to another release`);
        }
        civilizations.set(document.civ, document.civilization);
        for (const unit of document.units) units.set(`${document.civ}\u0000${unit.unitId}\u0000${unit.mode}`, unit);
    }
    return {
        metadata,
        unit(civ, unitId, mode = 'default') {
            const unit = units.get(`${civ}\u0000${unitId}\u0000${mode}`);
            if (!unit) throw new Error(`units row missing: ${civ}, ${unitId}, ${mode}`);
            return unit;
        },
        civilization(civ) {
            if (!civilizations.has(civ)) throw new Error(`civilizations row missing: ${civ}`);
            return civilizations.get(civ);
        },
    };
}

function team(data, [civ, unitId, mode, count], population) {
    const unit = clone(data.unit(civ, unitId, mode));
    if (typeof count !== 'number' || !Number.isInteger(count) || !(count >= 0 && count < unit.lookup.length)) {
        throw new RangeError('count must be an integer between 0 and 27');
    }
    unit.count = count;
    unit.lookup = unit.lookup.slice(0, count + 1);
    unit.startingArmy = unit.lookup[count];  // the same entry object, as in Python
    const spare = unit.startingArmy.surplusUnits;
    unit.replacementLookup = [];
    for (let n = 0; n <= count; n += 1) {
        const credited = Math.min(n, spare);
        const replacement = clone(unit.lookup[n - credited]);
        Object.assign(replacement, {count: n, initialSurplusUsed: credited,
            surplusUnits: spare - credited + replacement.surplusUnits});
        unit.replacementLookup.push(replacement);
    }
    unit.economy = clone(data.civilization(civ));
    for (const name of PACKAGES) {
        for (const tech of unit.research[name].technologies) {
            const variable = get(tech, 'variableCost', null);
            if (variable && Object.keys(variable).length && population !== null) {
                tech.upfront = Object.fromEntries(Object.entries(variable.base)
                    .map(([r, v]) => [r, v + variable.perVillager[r] * population]));
                tech.net = Object.fromEntries(Object.entries(tech.upfront).map(([r, v]) => [r, v - tech.refund[r]]));
                tech.populationInput = population;
                tech.costIsFixed = variable.status === 'validated';
            }
        }
        unit.research[name].totals = researchTotals(unit.research[name].technologies);
    }
    return unit;
}

/**
 * `left`/`right` are `[civ, unitId, mode, count]`; `populations` are the
 * converted villagers for variable-cost research (Flemish Revolution) or null.
 *
 * Headline: army bill + 60-second production buildings + net cost of the
 * research both armies share (common technology IDs), in weighted
 * villager-minutes. `teams[i].researchSummary` reports common / exclusive / full.
 */
export function evaluateMatchup(data, left, right, populations = [null, null]) {
    populations = [0, 1].map(index => populations[index] ?? null);
    for (const population of populations) {
        if (population !== null && (typeof population !== 'number' || !Number.isInteger(population)
            || !(population >= 0 && population <= 1000))) {
            throw new RangeError('convertedVillagers must be integers between 0 and 1000, or null');
        }
    }
    const teams = [left, right].map((selection, index) => team(data, selection, populations[index]));
    const comparison = compareResearch(teams[0].research.military.technologies, teams[1].research.military.technologies);
    teams.forEach((unit, index) => {
        const common = comparison.common[index];
        const prices = unit.economy.laborPrices;
        const start = unit.startingArmy;
        const [production, alternatives] = selectInvestmentRoute(unit.productionRoutes, start.orders,
            unit.pricing.unitsPerPurchase, addCosts(start.cost, common.net), prices);
        unit.production = production;
        unit.alternativeRoutes = alternatives;
        unit.investment = armyInvestment(start.cost, production, common, prices);
        for (const entry of [...unit.lookup, ...unit.replacementLookup]) {
            entry.trainingSeconds = queueSeconds(entry.orders, production);
        }
        const research = unit.research;
        const allTechs = [];
        for (const name of PACKAGES) {
            const technologies = research[name].technologies;
            allTechs.push(...technologies);
            research[name].infrastructure = researchInfrastructure(technologies, production);
        }
        research.infrastructure = researchInfrastructure(
            [...research.military.technologies, ...research.production.technologies], production);
        research.allInfrastructure = researchInfrastructure(allTechs, production);
        unit.researchSummary = {
            common: researchSummary(common, prices),
            exclusive: researchSummary(comparison.exclusive[index], prices),
            full: researchSummary(research.military.totals, prices),
            inHeadline: 'common',
        };
    });
    const metadata = data.metadata;
    return {schemaVersion: CONTEXT_SCHEMA_VERSION,
        trainingWindowSeconds: metadata.trainingWindowSeconds,
        resourceWeights: metadata.resourceWeights,
        contextVersion: metadata.contextVersion,
        status: metadata.releaseReady ? 'estimate' : 'review',
        releaseReady: metadata.releaseReady,
        assumptions: metadata.assumptions, teams,
        scopeExceptions: get(metadata, 'scopeExceptions', []),
        auraAssumption: get(metadata, 'auraAssumption', null),
        investmentComparison: investmentComparison(teams), researchComparison: comparison};
}
