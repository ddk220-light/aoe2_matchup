import { LatestRequest, requestJson } from "../shared/api.js";

/** Losses refer to initially purchased bodies, never HP fractions or spawns. */
export class CasualtyTracker {
    constructor() { this.reset(); }
    reset() { this.lost = new Set(); this.counts = [0, 0]; this.lastTick = -1; }
    consume(snapshot, unitIndex) {
        if (snapshot.tick < this.lastTick) this.reset();
        const lose = id => {
            const owner = unitIndex.get(id)?.owner;
            if ((owner !== 2 && owner !== 3) || this.lost.has(id)) return;
            this.lost.add(id);
            this.counts[owner - 2] += 1;
        };
        for (const event of snapshot.events || []) {
            if (event.type === "death") lose(event.targetId);
            if (event.type === "unit-dismount-pending" || event.type === "unit-dismounted") lose(event.actorId);
        }
        for (const unit of snapshot.units || []) {
            const id = Array.isArray(unit) ? unit[0] : unit.referenceId;
            const alive = Array.isArray(unit) ? unit[5] === 1 : unit.alive;
            if (!alive) lose(id);
        }
        this.lastTick = snapshot.tick;
    }
}

const RESOURCE_LABELS = {food: "F", wood: "W", gold: "G", stone: "S"};
const number = value => Number.isFinite(value) ? value.toLocaleString(undefined, {maximumFractionDigits: 1}) : "—";
export const formatResources = cost => cost == null ? "Unavailable" : Object.entries(RESOURCE_LABELS)
    .filter(([r]) => Math.abs(cost?.[r] || 0) > 0.0001)
    .map(([r, label]) => `${number(cost[r])}${label}`).join(" · ") || "0";
const seconds = value => Number.isFinite(value) ? `${number(value)}s` : "Unavailable";
const labor = value => value ? `${number(value.villagerMinutes)} villager-min` : "Model pending";
const buildings = production => production.buildingCount == null ? "Sizing unavailable"
    : `${production.buildingCount} ${production.name}`;
const weightedLabor = value => value ? `${number(value.villagerMinutes)} weighted villager-min` : "Unavailable";
export function investmentComparisonText(comparison) {
    if (comparison.status !== "available") return "Investment comparison unavailable: an economy, common upgrade cost or 60-second training setup is unresolved.";
    if (comparison.lowerTeam === null) return "Both displayed armies require equal weighted investment.";
    const side = comparison.lowerTeam === 1 ? "A" : "B", other = side === "A" ? "B" : "A";
    return `Army ${side} needs ${number(comparison.savingPercent)}% less weighted investment than Army ${other}.`;
}
function productionNote(production) {
    if (production.status === "training_exceeds_window") return "Cannot finish a purchase within 60 seconds";
    if (production.status !== "modeled") return "Training route unavailable";
    return `${buildings(production)} · ${seconds(production.trainingSeconds)} training within 60s`;
}
const SUMMARY_FIELDS = ["Score", "Investment", "Labor", "Comparison", "Upgrade", "Research", "Queue", "Losses", "Batch"];
function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
}
function setText(id, text) {
    const element = document.getElementById(id);
    if (element) element.textContent = text;
}
function table(headers, rows) {
    const wrapper = node("div", undefined, "army-table-wrap");
    const t = node("table");
    const head = node("thead"), tr = node("tr");
    for (const h of headers) tr.append(node("th", h));
    head.append(tr); t.append(head);
    const body = node("tbody");
    for (const row of rows) {
        const line = node("tr");
        for (const cell of row) line.append(node("td", cell));
        body.append(line);
    }
    t.append(body); wrapper.append(t);
    return wrapper;
}

export function createArmyEconomicsView() {
    const enabled = !!document.getElementById("armyEconomics");
    const requests = new LatestRequest();
    const tracker = new CasualtyTracker();
    let context = null, config = null, populations = [null, null];
    if (enabled) document.querySelectorAll('[data-army-details]').forEach(link => {
        link.addEventListener('click', () => { document.getElementById('armyEconomics').open = true; });
    });

    function clear() {
        requests.cancel(); tracker.reset(); context = null; config = null;
        populations = [null, null];
        if (enabled) {
            document.getElementById("armyEconomics").hidden = true;
            document.querySelectorAll(".army-summary").forEach(el => { el.hidden = true; });
        }
    }

    function renderLive() {
        if (!context) return;
        for (const [index, team] of context.teams.entries()) {
            const n = index + 1;
            const count = Math.min(team.count, tracker.counts[index]);
            const replacement = team.replacementLookup[count];
            setText(`eco${n}Score`, weightedLabor(team.investment.labor));
            setText(`eco${n}Investment`, formatResources(team.production.investmentCost));
            setText(`eco${n}Labor`, "Army + 60s production buildings + common upgrades");
            setText(`eco${n}Comparison`, investmentComparisonText(context.investmentComparison));
            setText(`eco${n}Upgrade`, formatResources(team.research.military.totals.upfront));
            setText(`eco${n}Research`, `${seconds(team.research.military.totals.workloadSeconds)} workload${team.research.military.totals.costIsFixed ? "" : " · variable cost"}`);
            setText(`eco${n}Losses`, `${count} replacement${count === 1 ? "" : "s"}: ${weightedLabor(replacement.weightedLabor)}${replacement.initialSurplusUsed ? ` · ${replacement.initialSurplusUsed} from initial surplus` : ""}`);
            setText(`eco${n}Queue`, productionNote(team.production));
            setText(`eco${n}Batch`, team.startingArmy.surplusUnits ? `Purchase includes ${team.startingArmy.surplusUnits} extra unit; kept for replacements` : "");
            setText(`armyReplacement${n}`, `${count} units · ${formatResources(replacement.cost)} · ${weightedLabor(replacement.weightedLabor)} · ${labor(replacement.labor)}${replacement.initialSurplusUsed ? ` · ${replacement.initialSurplusUsed} from initial surplus` : ""} · ${replacement.surplusUnits} surplus remaining`);
        }
    }

    function renderDetails() {
        const body = document.getElementById("armyEconomicsBody");
        body.replaceChildren();
        const names = context.teams.map(t => `${t.civ} ${t.name}`);
        const get = fn => context.teams.map(fn);
        const comparisonText = node("p", investmentComparisonText(context.investmentComparison));
        comparisonText.id = "armyInvestmentComparison";
        body.append(comparisonText, node("p", "60-second army investment combines the army, production buildings and common upgrade net costs. Lower weighted villager-minutes means less investment. Weights: food ×1, wood ×1, gold ×1.5, stone ×3. This is an investment score; the training window starts with buildings, upgrades and resources ready."));
        body.append(table(["Starting army", ...names], [
            ["Displayed units", ...get(t => String(t.count))],
            ["Purchase bill", ...get(t => formatResources(t.startingArmy.cost))],
            ["Purchase orders / units received", ...get(t => `${t.startingArmy.orders} / ${t.startingArmy.producedUnits}`)],
            ["Villager work", ...get(t => labor(t.startingArmy.labor))],
            ["Army work, weighted (standalone)", ...get(t => weightedLabor(t.investment.standaloneLabor.army))],
            ["Production buildings", ...get(t => productionNote(t.production))],
            ["Cost per building", ...get(t => formatResources(t.production.cost))],
            ["Total building investment", ...get(t => formatResources(t.production.investmentCost))],
            ["Building work, weighted (standalone)", ...get(t => weightedLabor(t.investment.standaloneLabor.buildings))],
            ["Common upgrade net cost", ...get(t => formatResources(t.investment.components.commonResearch))],
            ["Common upgrade work, weighted (standalone)", ...get(t => weightedLabor(t.investment.standaloneLabor.commonResearch))],
            ["Combined resource bill", ...get(t => formatResources(t.investment.cost))],
            ["Combined bill after scarcity weights", ...get(t => formatResources(t.investment.weightedCost))],
            ["60-second army investment", ...get(t => weightedLabor(t.investment.labor))],
            ["Spare unit capacity within 60 seconds", ...get(t => number(t.production.spareUnitCapacity))],
            ["Training / purchase order", ...get(t => seconds(t.production.secondsPerOrder))],
            ["Queue time with resources ready", ...get(t => seconds(t.startingArmy.trainingSeconds))],
        ]));
        body.append(node("p", "The combined bill is evaluated together so coproducts can serve multiple components; standalone work figures may sum to more than the headline. Farm wood and reseeding downtime are included. Initial batch surplus covers casualties before new orders are purchased. Buildings and upgrades are charged once; replacement work excludes them. Extra units are not added to combat."));
        const replacement = node("div", undefined, "army-replacements");
        for (const [index, name] of names.entries()) {
            const item = node("p"); item.append(node("strong", `${name}: `));
            const value = node("span"); value.id = `armyReplacement${index + 1}`; item.append(value); replacement.append(item);
        }
        body.append(replacement);
        const comparison = context.researchComparison;
        body.append(node("h3", "Military upgrade comparison"));
        body.append(node("p", "Research time is summed queue workload. Compare common technologies for speed; exclusive packages remain separate."));
        body.append(table(["Research investment", ...names], [
            ["Common upgrades", ...comparison.common.map(t => `${t.technologyCount} technologies`)],
            ["Common upfront cost", ...comparison.common.map(t => formatResources(t.upfront))],
            ["Common completion refunds", ...comparison.common.map(t => formatResources(t.refund))],
            ["Common net cost", ...comparison.common.map(t => formatResources(t.net))],
            ["Common workload", ...comparison.common.map(t => seconds(t.workloadSeconds))],
            ["Exclusive upfront cost", ...comparison.exclusive.map(t => formatResources(t.upfront))],
            ["Exclusive completion refunds", ...comparison.exclusive.map(t => formatResources(t.refund))],
            ["Exclusive net cost", ...comparison.exclusive.map(t => formatResources(t.net))],
            ["Exclusive research workload", ...comparison.exclusive.map(t => seconds(t.workloadSeconds))],
            ["Full military upfront cost", ...get(t => formatResources(t.research.military.totals.upfront))],
            ["Full military completion refunds", ...get(t => formatResources(t.research.military.totals.refund))],
            ["Full military net cost", ...get(t => formatResources(t.research.military.totals.net))],
            ["Full military workload", ...get(t => seconds(t.research.military.totals.workloadSeconds))],
            ["Additional military research buildings", ...get(t => formatResources(t.research.infrastructure.additionalCost))],
        ]));
        const delta = comparison.commonWorkloadDifferenceSeconds;
        if (comparison.commonIds.length) body.append(node("p", `Common net cost difference (Team A minus Team B): ${formatResources(comparison.commonCostDifference)}. Positive amounts cost Team A more; negative amounts cost Team A less.`));
        if (Number.isFinite(delta) && comparison.commonIds.length) {
            body.append(node("p", delta === 0 ? "Common upgrades have equal research workload."
                : `${delta < 0 ? "Team A" : "Team B"} needs ${seconds(Math.abs(delta))} less workload for common upgrades.`));
        }
        for (const [index, team] of context.teams.entries()) {
            const details = node("details", undefined, "army-team-details");
            details.append(node("summary", `${names[index]} — technologies, bonuses and assumptions`));
            if (team.pricing.conditionalContext) details.append(node("p", team.pricing.conditionalContext));
            details.append(node("p", `${formatResources(team.pricing.purchaseCost)} per purchase; ${team.pricing.unitsPerPurchase} unit(s) per order.`));
            if (team.economy.pastureModel) {
                const model = team.economy.pastureModel;
                details.append(node("p", model.description));
                details.append(node("p", "Uses a published Hand Cart lifecycle average as a post-Imperial estimate."));
                const reference = node("a", "Pasture rate reference");
                reference.href = model.reference.url;
                details.append(reference);
            }
            if (team.economy.blockers.length) {
                details.append(node("p", "Villager work is unavailable while these mechanics await modeling or validation:"));
                const list = node("ul");
                for (const blocker of team.economy.blockers) list.append(node("li", blocker.detail));
                details.append(list);
            }
            if (team.startingArmy.labor) {
                details.append(table(["Gathering activity", "Army villager-minutes (unweighted)"],
                    Object.entries(team.startingArmy.labor.workByActivity).map(([job, time]) => [job, number(time / 60)])));
                details.append(node("p", `Uncredited resource surplus: ${formatResources(team.startingArmy.labor.surplus)}.`));
            }
            for (const [key, label] of [["military", "Combat upgrades and training unlocks"], ["production", "Production upgrades"], ["economicSetup", "Economic setup"]]) {
                const pkg = team.research[key];
                details.append(node("h4", label));
                details.append(node("p", `Upfront ${formatResources(pkg.totals.upfront)}; refunds ${formatResources(pkg.totals.refund)}; net ${formatResources(pkg.totals.net)}. ${seconds(pkg.totals.workloadSeconds)} summed workload.`));
                details.append(table(["Technology", "Upfront", "Refund", "Time", "Building"], pkg.technologies.map(t => [
                    `${t.name}${t.automaticFree ? " (free, instant)" : ""}${t.variableCost ? " (variable)" : ""}`,
                    formatResources(t.upfront), formatResources(t.refund), seconds(t.seconds),
                    t.automaticFree ? "Automatic" : t.building?.name || "—",
                ])));
                for (const t of pkg.technologies) {
                    if (!t.automaticFree && t.baseSeconds > 0 && Math.abs(t.seconds - t.baseSeconds) > .01) {
                        details.append(node("p", `${t.name}: ${seconds(t.seconds)} research workload versus ${seconds(t.baseSeconds)} base time.`));
                    }
                    if (t.advantage) details.append(node("p", `${t.name}: ${t.advantage}`));
                    if (t.effectSummary) details.append(node("p", `${t.name}: ${t.effectSummary}`));
                    if (t.completionUnitRewards?.length) details.append(node("p", `${t.name}: grants villagers on completion; no resource rebate credited.`));
                    if (t.variableCost) {
                        details.append(node("p", `${t.name}: ${formatResources(t.variableCost.base)} + ${formatResources(t.variableCost.perVillager)} per converted villager. Engine validation pending.`));
                        const label = node("label", "Converted villagers ");
                        const input = node("input"); input.type = "number"; input.min = "0"; input.max = "1000"; input.step = "1";
                        input.value = populations[index] === null ? "" : String(populations[index]);
                        input.addEventListener("change", () => {
                            if (!input.checkValidity()) { input.reportValidity(); return; }
                            populations[index] = input.value === "" ? null : Number(input.value);
                            requestContext();
                        });
                        label.append(input); details.append(label);
                    }
                }
            }
            details.append(node("h4", "Research infrastructure"));
            details.append(table(["Building", "Cost", "Included in production investment"],
                team.research.allInfrastructure.buildings.map(b => [b.name, formatResources(b.cost), b.alreadyAvailable ? "Yes" : "No"])));
            details.append(node("p", `Additional research infrastructure for all packages: ${formatResources(team.research.allInfrastructure.additionalCost)}. Each building is counted once, separately from production investment.`));
            details.append(node("h4", "Production routes and modifiers"));
            if (team.investment.status === "unresolved_labor") details.append(node("p", "Building selection uses provisional weighted resource prices while the labor model is unresolved; no headline score is available."));
            if (team.investment.status === "unresolved_common_research_cost") details.append(node("p", "The common upgrade package has an unresolved variable cost; the displayed bill is a subtotal and no headline score is available."));
            for (const route of team.alternativeRoutes) {
                details.append(node("p", `${route.name}: ${formatResources(route.cost)} each, ${seconds(route.secondsPerOrder)} per order; ${productionNote(route)}; total ${formatResources(route.investmentCost)}. Combined investment via this route: ${team.investment.status === "modeled" ? weightedLabor(route.combinedLabor) : "Unavailable"}.`));
                for (const modifier of route.modifiers) details.append(node("p", `${modifier.effect_name}: ${modifier.target} (${number(modifier.before)} → ${number(modifier.after)}).`));
            }
            details.append(node("h4", "Economic effects"));
            const effects = node("ul");
            for (const effect of team.economy.effects) effects.append(node("li", `${effect.name}: ${effect.description}`));
            details.append(effects);
            details.append(node("p", `Unavailable economic technologies: ${team.economy.missingTechnologies.map(t => t.name).join(", ") || "none"}. Missing upgrades are not research-speed bonuses.`));
            body.append(details);
        }
        const assumptions = node("ul");
        for (const assumption of context.assumptions) assumptions.append(node("li", assumption));
        body.append(assumptions, node("p", `Source: ${context.source.origin}; ${context.source.game_patch}. Context ${context.contextVersion.slice(0, 12)}.`, "army-provenance"));
    }

    async function requestContext() {
        const ticket = requests.begin();
        const selected = config;
        setText("armyEconomicsStatus", "Loading army economics…");
        try {
            if (!selected?.armyContextVersion) throw new Error("Army economics is awaiting compatible, validated data");
            const data = await requestJson("/api/v3/army-context", {method: "POST", signal: ticket.signal, body: {
                teams: selected.teams.map(t => ({civ: t.civ, unit_slug: t.unit_slug, mode: t.mode, count: t.count})),
                army: {mode: "explicit"}, engagement_mode: "direct", seed: selected.seed,
                contextVersion: selected.armyContextVersion, convertedVillagers: populations,
            }});
            if (!ticket.isCurrent() || selected !== config) return;
            if (data.schemaVersion !== 3 || data.trainingWindowSeconds !== 60) throw new Error("Army economics version changed; reload the page");
            if (data.teams.some((t, i) => t.count !== selected.teams[i].count || t.mechanicsHash !== selected.teams[i].mechanics_hash)) {
                throw new Error("Army context changed; select the matchup again");
            }
            context = data;
            setText("armyEconomicsStatus", data.status === "review"
                ? "Review estimates · controlled game validation pending. Unresolved labor is withheld."
                : data.status === "estimate"
                    ? "Post-Imperial army economics · estimated gathering rates; in-game measurements deferred."
                    : "Post-Imperial army economics");
            renderDetails(); renderLive();
        } catch (error) {
            if (!ticket.isCurrent()) return;
            context = null;
            document.getElementById("armyEconomicsBody").replaceChildren();
            for (const n of [1, 2]) for (const field of SUMMARY_FIELDS) setText(`eco${n}${field}`, "—");
            setText("armyEconomicsStatus", error.message);
        }
    }

    function load(newConfig) {
        if (!enabled) return;
        clear(); config = newConfig;
        document.getElementById("armyEconomics").hidden = false;
        document.querySelectorAll(".army-summary").forEach(el => { el.hidden = false; });
        for (const n of [1, 2]) for (const field of SUMMARY_FIELDS) setText(`eco${n}${field}`, "—");
        document.getElementById("armyEconomicsBody").replaceChildren();
        requestContext();
    }
    return {clear, load, renderLive, resetLosses: () => { tracker.reset(); renderLive(); },
        consume: (snapshot, unitIndex) => { if (enabled) tracker.consume(snapshot, unitIndex); }};
}
