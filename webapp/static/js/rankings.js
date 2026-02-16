/* ==========================================================================
   AoE2 Unit Analyzer - Rankings Page JavaScript
   Depends on: constants.js (ENABLED_CIVS, CIV_EMBLEM_BASE, ICON_BASE,
               ICON_BASE_FALLBACK, NAME_TO_ICON)
   ========================================================================== */

// Unit lines definition (mirrors backend UNIT_LINES)
const UNIT_LINES = {
    infantry: {
        name: "Infantry Effectiveness",
        building: "Barracks",
        castle: "Long Swordsman",
        imperial: "Champion",
        hasUnique: true,
        subLines: ["militia", "spear", "shock_infantry"],
    },
    archery: {
        name: "Ranged Effectiveness",
        building: "Archery Range",
        castle: "Crossbowman",
        imperial: "Arbalester",
        hasUnique: true,
        subLines: ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"],
    },
    stable: {
        name: "Stable Effectiveness",
        building: "Stable",
        castle: null,
        imperial: "Paladin",
        hasUnique: true,
        subLines: ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
    },
    siege: {
        name: "Anti-Building Effectiveness",
        building: "Siege Workshop",
        castle: "Battering Ram",
        imperial: "Trebuchet",
        hasUnique: true,
        subLines: ["ram", "trebuchet", "bombard_cannon"],
    },
};

function iconUrl(id) {
    return ICON_BASE + id + ".png";
}
function unitIconUrl(name) {
    const id = NAME_TO_ICON[name];
    return id ? iconUrl(id) : "";
}

// ===== STATE =====
let currentAge = "Imperial";
let currentLine = null;
let currentData = null;
let sortColumn = "civ_name";
let enabledLines = new Set();
let sortDir = "asc";
let currentEnriched = [];
let pinnedCell = null;
const statChainCache = {};

// ===== SCORE BREAKDOWN CONFIG =====
const SCORE_BREAKDOWN = {
    general_combat: {
        title: "General Combat",
        formula: "Average of 6 normalized matchups (3 \u00d7 30v30 + 3 \u00d7 3K res)",
        subs: [
            { key: "gc_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "gc_30v30_vs_arb", label: "vs Arbalester (30v30)", civ: "Chinese", slug: "arbalester", mode: "count", count: 30 },
            { key: "gc_30v30_vs_champ", label: "vs Champion (30v30)", civ: "Chinese", slug: "champion", mode: "count", count: 30 },
            { key: "gc_3k_vs_paladin", label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_arb", label: "vs Arbalester (3K res)", civ: "Chinese", slug: "arbalester", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_champ", label: "vs Champion (3K res)", civ: "Chinese", slug: "champion", mode: "resources", res: 3000 },
        ],
    },
    anti_cav: {
        title: "Anti-Cav",
        formula: "Average of 6 normalized matchups (3 \u00d7 30v30 + 3 \u00d7 3K res)",
        subs: [
            { key: "gc_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "ac_30v30_vs_elephant", label: "vs War Elephant (30v30)", civ: "Persians", slug: "elite_war_elephant_persians", mode: "count", count: 30 },
            { key: "ac_30v30_vs_hussar", label: "vs Hussar (30v30)", civ: "Spanish", slug: "hussar", mode: "count", count: 30 },
            { key: "gc_3k_vs_paladin", label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
            { key: "ac_3k_vs_elephant", label: "vs War Elephant (3K res)", civ: "Persians", slug: "elite_war_elephant_persians", mode: "resources", res: 3000 },
            { key: "ac_3k_vs_hussar", label: "vs Hussar (3K res)", civ: "Spanish", slug: "hussar", mode: "resources", res: 3000 },
        ],
    },
    raid_building: {
        title: "Anti-Building",
        formula: "Avg N_min to destroy TC and Castle (normalized, inverted)",
        subs: [
            {
                key: "raid_vs_tc_nmin",
                label: "vs Town Center",
                mode: "nmin",
            },
            {
                key: "raid_vs_castle_nmin",
                label: "vs Castle",
                mode: "nmin",
            },
        ],
    },
    // Archery score breakdowns
    general_combat: {
        title: "General Combat Score",
        formula: "Normalized avg of 6 matchups (3 \u00d7 30v30 + 3 \u00d7 3K res)",
        subs: [
            { key: "gc_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "gc_30v30_vs_arb", label: "vs Arbalester (30v30)", civ: "Chinese", slug: "arbalester", mode: "count", count: 30 },
            { key: "gc_30v30_vs_champ", label: "vs Champion (30v30)", civ: "Chinese", slug: "champion", mode: "count", count: 30 },
            { key: "gc_3k_vs_paladin", label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_arb", label: "vs Arbalester (3K res)", civ: "Chinese", slug: "arbalester", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_champ", label: "vs Champion (3K res)", civ: "Chinese", slug: "champion", mode: "resources", res: 3000 },
        ],
    },
    anti_archer: {
        title: "Anti-Archer Score",
        formula: "Normalized avg of 6 matchups (3 \u00d7 30v30 + 3 \u00d7 3K res)",
        subs: [
            { key: "aa_30v30_vs_arb", label: "vs Arbalester (30v30)", civ: "Chinese", slug: "arbalester", mode: "count", count: 30 },
            { key: "aa_30v30_vs_ca", label: "vs Cav Archer (30v30)", civ: "Chinese", slug: "heavy_cav_archer", mode: "count", count: 30 },
            { key: "aa_30v30_vs_ele_archer", label: "vs Ele Archer (30v30)", civ: "Gurjaras", slug: "elite_ele_archer", mode: "count", count: 30 },
            { key: "aa_3k_vs_arb", label: "vs Arbalester (3K res)", civ: "Chinese", slug: "arbalester", mode: "resources", res: 3000 },
            { key: "aa_3k_vs_ca", label: "vs Cav Archer (3K res)", civ: "Chinese", slug: "heavy_cav_archer", mode: "resources", res: 3000 },
            { key: "aa_3k_vs_ele_archer", label: "vs Ele Archer (3K res)", civ: "Gurjaras", slug: "elite_ele_archer", mode: "resources", res: 3000 },
        ],
    },
    // Stable score breakdowns
    general_combat_stable: {
        title: "General Combat",
        formula: "Average of 6 normalized matchups (30v30 + 3K res each)",
        subs: [
            { key: "gc_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "gc_30v30_vs_arb", label: "vs Arbalester (30v30)", civ: "Chinese", slug: "arbalester", mode: "count", count: 30 },
            { key: "gc_30v30_vs_champ", label: "vs Champion (30v30)", civ: "Chinese", slug: "champion", mode: "count", count: 30 },
            { key: "gc_3k_vs_paladin", label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_arb", label: "vs Arbalester (3K res)", civ: "Chinese", slug: "arbalester", mode: "resources", res: 3000 },
            { key: "gc_3k_vs_champ", label: "vs Champion (3K res)", civ: "Chinese", slug: "champion", mode: "resources", res: 3000 },
        ],
    },
    anti_cav_stable: {
        title: "Anti-Cav",
        formula: "Average of 6 normalized matchups (30v30 + 3K res each)",
        subs: [
            { key: "gc_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "gc_3k_vs_paladin", label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
            { key: "ac_30v30_vs_heavy_camel", label: "vs Heavy Camel (30v30)", civ: "Turks", slug: "heavy_camel", mode: "count", count: 30 },
            { key: "ac_30v30_vs_elephant", label: "vs Battle Elephant (30v30)", civ: "Vietnamese", slug: "elite_elephant", mode: "count", count: 30 },
            { key: "ac_3k_vs_heavy_camel", label: "vs Heavy Camel (3K res)", civ: "Turks", slug: "heavy_camel", mode: "resources", res: 3000 },
            { key: "ac_3k_vs_elephant", label: "vs Battle Elephant (3K res)", civ: "Vietnamese", slug: "elite_elephant", mode: "resources", res: 3000 },
        ],
    },
};

const SCORE_KEYS = new Set([
    "militia_value",
    "general_combat",
    "anti_cav",
    "raid_building",
    // Infantry 30v30 + 3K scores
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_elephant",
    "ac_30v30_vs_hussar",
    "ac_3k_vs_elephant",
    "ac_3k_vs_hussar",
    // Archery scores
    "ranged_effectiveness",
    "anti_archer",
    "aa_30v30_vs_arb",
    "aa_30v30_vs_ca",
    "aa_30v30_vs_ele_archer",
    "aa_3k_vs_arb",
    "aa_3k_vs_ca",
    "aa_3k_vs_ele_archer",
    // Stable scores
    "stable_effectiveness",
    "ac_30v30_vs_heavy_camel",
    "ac_3k_vs_heavy_camel",
]);
const STAT_KEYS = new Set([
    "final_hp",
    "final_attack",
    "final_melee_armor",
    "final_pierce_armor",
    "dps",
    "total_cost",
    "total_upgrade_cost",
]);

// ===== HOVER CARD MANAGER =====
function getHoverCardEl() {
    let el = document.getElementById("hoverCard");
    if (!el) {
        el = document.createElement("div");
        el.id = "hoverCard";
        el.className = "hover-card";
        document.body.appendChild(el);
    }
    return el;
}

function positionHoverCard(targetEl) {
    const hc = getHoverCardEl();
    const rect = targetEl.getBoundingClientRect();
    const hcRect = hc.getBoundingClientRect();
    let top = rect.top - hcRect.height - 8;
    let left = rect.left + rect.width / 2 - hcRect.width / 2;
    if (top < 4) top = rect.bottom + 8;
    if (left < 4) left = 4;
    if (left + hcRect.width > window.innerWidth - 4)
        left = window.innerWidth - hcRect.width - 4;
    hc.style.top = top + "px";
    hc.style.left = left + "px";
}

function showHoverCard(targetEl, html) {
    if (pinnedCell) return;
    const hc = getHoverCardEl();
    hc.innerHTML = html;
    hc.classList.add("visible");
    hc.classList.remove("pinned");
    positionHoverCard(targetEl);
}

function hideHoverCard() {
    if (pinnedCell) return;
    const hc = getHoverCardEl();
    hc.classList.remove("visible");
}

function pinHoverCard(targetEl, html) {
    const hc = getHoverCardEl();
    if (pinnedCell === targetEl) {
        unpinHoverCard();
        return;
    }
    pinnedCell = targetEl;
    hc.innerHTML =
        `<span class="hc-close" onclick="unpinHoverCard()">&times;</span>` +
        html;
    hc.classList.add("visible", "pinned");
    positionHoverCard(targetEl);
}

function unpinHoverCard() {
    pinnedCell = null;
    const hc = getHoverCardEl();
    hc.classList.remove("visible", "pinned");
}

document.addEventListener("click", (e) => {
    if (!pinnedCell) return;
    const hc = getHoverCardEl();
    if (hc.contains(e.target)) return;
    if (e.target.closest("td.hc-cell")) return;
    unpinHoverCard();
});

// ===== HOVER CARD BUILDERS =====
function scoreColor(v) {
    if (v === undefined || v === null || v <= -999)
        return "var(--text-muted)";
    if (v >= 60) return "#6fbf6f";
    if (v >= 40) return "#9fbf6f";
    if (v >= 20) return "var(--text)";
    if (v >= 0) return "#bf9f6f";
    return "#bf6f6f";
}

function buildSimUrl(
    unitCiv,
    unitSlug,
    oppCiv,
    oppSlug,
    mode,
    res,
    count,
) {
    let url = `/?civ1=${encodeURIComponent(unitCiv)}&unit1=${encodeURIComponent(unitSlug)}&civ2=${encodeURIComponent(oppCiv)}&unit2=${encodeURIComponent(oppSlug)}`;
    if (mode === "resources")
        url += `&mode=resources&resources=${res}`;
    else if (mode === "count")
        url += `&mode=count&count1=${count}&count2=${count}`;
    return url;
}

function buildScoreHoverHtml(row, scoreKey, dataKey) {
    dataKey = dataKey || scoreKey;
    const info = SCORE_BREAKDOWN[scoreKey];
    if (!info) {
        // Composite score hover cards
        const composites = {
            militia_value: {
                title: "Overall Score",
                parts: [
                    {
                        key: "general_combat",
                        label: "General Combat",
                        weight: "50%",
                    },
                    {
                        key: "anti_cav",
                        label: "Anti-Cav",
                        weight: "30%",
                    },
                    {
                        key: "raid_building",
                        label: "Anti-Building",
                        weight: "20%",
                    },
                ],
            },
            ranged_effectiveness: {
                title: "Ranged Effectiveness Score",
                parts: [
                    {
                        key: "general_combat",
                        label: "General Combat",
                        weight: "70%",
                    },
                    {
                        key: "anti_archer",
                        label: "Anti-Archer",
                        weight: "30%",
                    },
                ],
            },
            stable_effectiveness: {
                title: "Stable Effectiveness",
                parts: [
                    {
                        key: "general_combat",
                        label: "General Combat",
                        weight: "70%",
                    },
                    {
                        key: "anti_cav",
                        label: "Anti-Cav",
                        weight: "30%",
                    },
                ],
            },
        };
        const comp = composites[scoreKey];
        if (comp) {
            let html = `<div class="hc-title">${comp.title}</div>`;
            html += `<div class="hc-formula">Weighted: ${comp.parts.map((p) => p.weight + " " + p.label).join(" + ")}</div>`;
            for (const p of comp.parts) {
                const v = row[p.key];
                const vs =
                    v !== undefined && v > -999
                        ? v.toFixed(1)
                        : "\u2014";
                html += `<div class="hc-row"><span>${p.label} (\u00d7${p.weight})</span><span style="color:${scoreColor(v)}">${vs}</span></div>`;
            }
            const total = row[dataKey];
            html += `<div class="hc-row total"><span>Score</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "\u2014"}</span></div>`;
            return html;
        }
        return "";
    }
    let html = `<div class="hc-title">${info.title}</div>`;
    html += `<div class="hc-formula">${info.formula}</div>`;
    for (const sub of info.subs) {
        const v = row[sub.key];
        const vs =
            v !== undefined && v > -999 ? v.toFixed(1) : "\u2014";
        html += `<div class="hc-row"><span>${sub.label}</span><span style="color:${scoreColor(v)}">${vs}</span></div>`;
        if (sub.civ && sub.slug) {
            const simUrl = buildSimUrl(
                row.civ_name,
                row.unit_slug,
                sub.civ,
                sub.slug,
                sub.mode,
                sub.res,
                sub.count,
            );
            html += `<a class="hc-sim-link" href="${simUrl}" target="_blank">Run in Battle Sim \u2192</a>`;
        }
    }
    const total = row[dataKey];
    html += `<div class="hc-row total"><span>Result</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "\u2014"}</span></div>`;
    return html;
}

async function getStatChain(refUnitId) {
    if (statChainCache[refUnitId]) return statChainCache[refUnitId];
    const resp = await fetch(`/api/ref/stat-chain/${refUnitId}`);
    const data = await resp.json();
    statChainCache[refUnitId] = data;
    return data;
}

const STAT_CHAIN_MAP = {
    final_hp: "hp",
    final_attack: "attack",
    final_melee_armor: "melee_armor",
    final_pierce_armor: "pierce_armor",
    dps: "attack",
};

function buildStatHoverHtml(row, statKey, chainData) {
    if (statKey === "total_cost") {
        let html = `<div class="hc-title">Unit Cost Breakdown</div>`;
        const f = row.final_cost_food || 0,
            w = row.final_cost_wood || 0,
            g = row.final_cost_gold || 0;
        if (f)
            html += `<div class="hc-row"><span>Food</span><span>${f}</span></div>`;
        if (w)
            html += `<div class="hc-row"><span>Wood</span><span>${w}</span></div>`;
        if (g)
            html += `<div class="hc-row"><span>Gold</span><span>${g}</span></div>`;
        html += `<div class="hc-row total"><span>Total</span><span>${row.total_cost}</span></div>`;
        return html;
    }

    if (statKey === "total_upgrade_cost") {
        let html = `<div class="hc-title">Upgrade Cost Breakdown</div>`;
        const f = row.upgrade_cost_food || 0,
            w = row.upgrade_cost_wood || 0,
            g = row.upgrade_cost_gold || 0;
        if (f)
            html += `<div class="hc-row"><span>Food</span><span>${f}</span></div>`;
        if (w)
            html += `<div class="hc-row"><span>Wood</span><span>${w}</span></div>`;
        if (g)
            html += `<div class="hc-row"><span>Gold</span><span>${g}</span></div>`;
        html += `<div class="hc-row total"><span>Total</span><span>${row.total_upgrade_cost}</span></div>`;
        return html;
    }

    const chain = chainData.stat_chain || [];
    if (!chain.length) return `<div class="hc-title">No data</div>`;

    if (statKey === "dps") {
        let html = `<div class="hc-title">DPS Breakdown</div>`;
        html += `<div class="hc-formula">Attack \u00f7 Reload Time</div>`;
        for (let i = 0; i < chain.length; i++) {
            const step = chain[i];
            const atk = step.attack || 0;
            const rld = step.reload_time || 1;
            const dps = rld > 0 ? atk / rld : 0;
            if (i === 0) {
                const hl =
                    step.tech_type === "civ_bonus" ||
                    step.tech_type === "unique_tech"
                        ? " highlight"
                        : "";
                html += `<div class="hc-row${hl}"><span>${step.tech_name}</span><span>${dps.toFixed(2)}</span></div>`;
            } else {
                const prev = chain[i - 1];
                const prevAtk = prev.attack || 0;
                const prevRld = prev.reload_time || 1;
                if (atk !== prevAtk || rld !== prevRld) {
                    const hl =
                        step.tech_type === "civ_bonus" ||
                        step.tech_type === "unique_tech"
                            ? " highlight"
                            : "";
                    const delta =
                        dps - (prevRld > 0 ? prevAtk / prevRld : 0);
                    const sign = delta >= 0 ? "+" : "";
                    html += `<div class="hc-row${hl}"><span>${step.tech_name}</span><span>${dps.toFixed(2)} (${sign}${delta.toFixed(2)})</span></div>`;
                }
            }
        }
        const finalDps = row.dps || 0;
        html += `<div class="hc-row total"><span>Final DPS</span><span>${finalDps.toFixed(2)}</span></div>`;
        return html;
    }

    // Standard stat (hp, attack, melee_armor, pierce_armor)
    const chainKey = STAT_CHAIN_MAP[statKey] || statKey;
    const label =
        {
            final_hp: "HP",
            final_attack: "Attack",
            final_melee_armor: "Melee Armor",
            final_pierce_armor: "Pierce Armor",
        }[statKey] || statKey;
    let html = `<div class="hc-title">${label} Breakdown</div>`;
    for (let i = 0; i < chain.length; i++) {
        const step = chain[i];
        const val = step[chainKey];
        if (i === 0) {
            const hl =
                step.tech_type === "civ_bonus" ||
                step.tech_type === "unique_tech"
                    ? " highlight"
                    : "";
            html += `<div class="hc-row${hl}"><span>${step.tech_name}</span><span>${val}</span></div>`;
        } else {
            const prev = chain[i - 1];
            const prevVal = prev[chainKey];
            if (val !== prevVal) {
                const delta = val - prevVal;
                const sign = delta >= 0 ? "+" : "";
                const hl =
                    step.tech_type === "civ_bonus" ||
                    step.tech_type === "unique_tech"
                        ? " highlight"
                        : "";
                html += `<div class="hc-row${hl}"><span>${step.tech_name}</span><span>${sign}${delta} \u2192 ${val}</span></div>`;
            }
        }
    }
    html += `<div class="hc-row total"><span>Final</span><span>${row[statKey]}</span></div>`;
    return html;
}

// ===== HOVER HANDLERS =====
function resolveBreakdownKey(key) {
    if (currentLine === "stable" && key === "general_combat") return "general_combat_stable";
    if (currentLine === "stable" && key === "anti_cav") return "anti_cav_stable";
    return key;
}

function onScoreCellEnter(e, rowIdx, key) {
    const row = currentEnriched[rowIdx];
    if (!row) return;
    showHoverCard(e.currentTarget, buildScoreHoverHtml(row, resolveBreakdownKey(key), key));
}

function onScoreCellLeave() {
    hideHoverCard();
}

function onScoreCellClick(e, rowIdx, key) {
    const row = currentEnriched[rowIdx];
    if (!row) return;
    pinHoverCard(e.currentTarget, buildScoreHoverHtml(row, resolveBreakdownKey(key), key));
}

async function onStatCellEnter(e, rowIdx, key) {
    const row = currentEnriched[rowIdx];
    if (!row) return;
    if (key === "total_cost" || key === "total_upgrade_cost") {
        showHoverCard(
            e.currentTarget,
            buildStatHoverHtml(row, key, {}),
        );
        return;
    }
    const td = e.currentTarget;
    showHoverCard(td, `<div class="hc-loading">Loading...</div>`);
    const chain = await getStatChain(row.id);
    if (!pinnedCell)
        showHoverCard(td, buildStatHoverHtml(row, key, chain));
}

function onStatCellLeave() {
    hideHoverCard();
}

async function onStatCellClick(e, rowIdx, key) {
    const row = currentEnriched[rowIdx];
    if (!row) return;
    if (key === "total_cost" || key === "total_upgrade_cost") {
        pinHoverCard(
            e.currentTarget,
            buildStatHoverHtml(row, key, {}),
        );
        return;
    }
    const td = e.currentTarget;
    pinHoverCard(td, `<div class="hc-loading">Loading...</div>`);
    const chain = await getStatChain(row.id);
    pinHoverCard(td, buildStatHoverHtml(row, key, chain));
}

// ===== RENDERING =====
function toggleLine(slug) {
    if (enabledLines.has(slug)) {
        enabledLines.delete(slug);
    } else {
        enabledLines.add(slug);
    }
    renderTable();
}

function setAge(age) {
    // Stable is Imperial-only
    if (currentLine === "stable" && age === "Castle") return;
    currentAge = age;
    document.querySelectorAll(".age-btn").forEach((btn) => {
        btn.classList.toggle(
            "active",
            btn.textContent.includes(age),
        );
    });
    renderLineSelector();
    if (currentData) renderTable();
}

function renderLineSelector() {
    const container = document.getElementById("lineSelector");
    let html = '<div class="tab-bar">';
    const entries = Object.entries(UNIT_LINES);
    let lastBuilding = null;

    for (const [slug, line] of entries) {
        // Add separator between different buildings
        if (lastBuilding && line.building !== lastBuilding) {
            html += '<div class="tab-separator"></div>';
        }
        lastBuilding = line.building;

        const displayName =
            currentAge === "Castle"
                ? line.castle
                : line.imperial;
        const hasCastle = line.castle !== null;
        const unavailable =
            currentAge === "Castle" && !hasCastle;
        const iUrl = unitIconUrl(displayName || line.imperial);
        const activeClass =
            currentLine === slug ? " active" : "";
        const unavailClass = unavailable ? " unavailable" : "";

        html += `<button class="unit-tab${activeClass}${unavailClass}" onclick="selectLine('${slug}')">
            <img src="${iUrl}" alt="${line.name}" onerror="if(!this.dataset.tried){this.dataset.tried='1';const id=NAME_TO_ICON[this.alt];if(id)this.src=ICON_BASE_FALLBACK+id+'.png';else this.style.display='none'}else{this.style.display='none'}" />
            ${line.name}
        </button>`;
    }
    html += '</div>';
    container.innerHTML = html;
}

const INFANTRY_SLUGS = new Set([
    "militia",
    "spear",
    "shock_infantry",
    "infantry",
]);

const ARCHERY_SLUGS = new Set([
    "archer",
    "skirmisher",
    "cav_archer",
    "scorpion",
    "gunpowder",
    "archery",
]);

const SIEGE_SLUGS = new Set([
    "siege",
]);

async function selectLine(slug) {
    currentLine = slug;
    unpinHoverCard();

    // Force Imperial age for stable (no Castle age data)
    if (slug === "stable") {
        currentAge = "Imperial";
        document.querySelectorAll(".age-btn").forEach((btn) => {
            btn.classList.toggle(
                "active",
                btn.textContent.includes("Imperial"),
            );
        });
    }

    // Highlight active tab
    document
        .querySelectorAll(".unit-tab")
        .forEach((c) => c.classList.remove("active"));
    const tabs = document.querySelectorAll(".unit-tab");
    tabs.forEach((c) => {
        if (c.getAttribute("onclick")?.includes(`'${slug}'`))
            c.classList.add("active");
    });

    const resp = await fetch(`/api/ref/unit-line/${slug}`);
    currentData = await resp.json();
    // Enable all sub-lines by default
    const lineInfo = UNIT_LINES[slug];
    enabledLines = new Set(lineInfo?.subLines || []);
    sortColumn =
        slug === "stable"
            ? "stable_effectiveness"
            : INFANTRY_SLUGS.has(slug)
                ? "militia_value"
                : ARCHERY_SLUGS.has(slug)
                    ? "ranged_effectiveness"
                    : SIEGE_SLUGS.has(slug)
                        ? "anti_building_score"
                        : "pes";
    sortDir = "desc";
    renderTable();
}

const LINE_LABELS = {
    militia: "Militia",
    spear: "Spear",
    shock_infantry: "Shock",
    archer: "Archer",
    skirmisher: "Skirm",
    cav_archer: "Cav Archer",
    knight: "Knight",
    light_cav: "Light Cav",
    camel: "Camel",
    steppe_lancer: "Steppe",
    elephant: "Elephant",
    ram: "Ram",
    mangonel: "Mangonel",
    scorpion: "Scorpion",
    gunpowder: "Gunpowder",
    trebuchet: "Trebuchet",
    bombard_cannon: "Bombard Cannon",
};

function renderTable() {
    const container = document.getElementById("tableContainer");
    if (!currentData) {
        container.innerHTML = "";
        return;
    }

    const ageKey = currentAge === "Castle" ? "castle" : "imperial";
    const rows = currentData[ageKey] || [];

    if (rows.length === 0) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:20px;">No units available in ${currentAge} Age for this line.</p>`;
        return;
    }

    // Compute derived fields
    const enriched = rows.map((r) => {
        const dps =
            r.final_reload_time > 0
                ? Math.round(
                      (r.final_attack / r.final_reload_time) * 10,
                  ) / 10
                : 0;
        const totalCost =
            (r.final_cost_food || 0) +
            (r.final_cost_wood || 0) +
            (r.final_cost_gold || 0);
        const totalArmor =
            1 +
            (r.final_melee_armor || 0) +
            (r.final_pierce_armor || 0);
        // PES: Pop Efficient Score (all 30v30 fixed-count battles)
        const pesWeights = [
            [r.score_30v30, 0.25],
            [r.pop_vs_champ, 0.25],
            [r.pop_vs_paladin, 0.25],
            [r.pop_vs_arb, 0.25],
        ];
        let pesSum = 0,
            pesTotal = 0;
        for (const [s, w] of pesWeights) {
            if (s > -999) {
                pesSum += s * w;
                pesTotal += w;
            }
        }
        const pes =
            pesTotal > 0
                ? Math.round((pesSum / pesTotal) * 10) / 10
                : -999;

        // RES: Resource Efficient Score (resource-based battles)
        const resWeights = [
            [r.score_3k, 0.2],
            [r.score_5k, 0.15],
            [r.vs_champ, 0.217],
            [r.vs_paladin, 0.217],
            [r.vs_arb, 0.217],
        ];
        let resSum = 0,
            resTotal = 0;
        for (const [s, w] of resWeights) {
            if (s > -999) {
                resSum += s * w;
                resTotal += w;
            }
        }
        const res =
            resTotal > 0
                ? Math.round((resSum / resTotal) * 10) / 10
                : -999;

        return {
            ...r,
            dps,
            pes,
            res,
            total_cost: totalCost,
            total_upgrade_cost:
                (r.upgrade_cost_food || 0) +
                (r.upgrade_cost_wood || 0) +
                (r.upgrade_cost_gold || 0),
            dps_per_cost:
                totalCost > 0
                    ? Math.round((dps / totalCost) * 1000) / 1000
                    : 0,
            ehp_per_cost:
                totalCost > 0
                    ? Math.round(
                          ((r.final_hp * totalArmor) / totalCost) *
                              10,
                      ) / 10
                    : 0,
        };
    });

    // Apply civ filter
    const civFilter =
        document
            .getElementById("civFilterInput")
            ?.value?.toLowerCase() || "";
    let filtered = civFilter
        ? enriched.filter((r) =>
              r.civ_name.toLowerCase().includes(civFilter),
          )
        : enriched;
    // Filter by enabled sub-lines
    if (enabledLines.size > 0) {
        filtered = filtered.filter((r) =>
            !r.line_slug || enabledLines.has(r.line_slug),
        );
    }

    // Sort
    filtered.sort((a, b) => {
        let va = a[sortColumn],
            vb = b[sortColumn];
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va < vb) return sortDir === "asc" ? -1 : 1;
        if (va > vb) return sortDir === "asc" ? 1 : -1;
        // Secondary sort: standard before unique
        if (a.is_unique !== b.is_unique)
            return a.is_unique ? 1 : -1;
        return 0;
    });

    // Store for hover handlers
    currentEnriched = filtered;

    // Compute medians for color coding (exclude unique units for baseline)
    const isInfantry = INFANTRY_SLUGS.has(currentLine);

    const defaultStatCols = [
        "pes",
        "res",
        "score_30v30",
        "pop_vs_champ",
        "pop_vs_paladin",
        "pop_vs_arb",
        "score_3k",
        "score_5k",
        "vs_champ",
        "vs_paladin",
        "vs_arb",
        "dps_per_cost",
        "ehp_per_cost",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
        "final_range",
    ];
    const infantryStatCols = [
        "militia_value",
        "general_combat",
        "anti_cav",
        "raid_building",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
    ];
    const archeryStatCols = [
        "ranged_effectiveness",
        "general_combat",
        "anti_archer",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
        "final_range",
    ];
    const siegeStatCols = [
        "anti_building_score",
        "time_to_kill",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
        "final_range",
    ];
    const stableStatCols = [
        "stable_effectiveness",
        "general_combat",
        "anti_cav",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
    ];
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isSiege = SIEGE_SLUGS.has(currentLine);
    const statCols =
        currentLine === "stable"
            ? stableStatCols
            : isSiege
                ? siegeStatCols
                : isInfantry
                    ? infantryStatCols
                    : isArchery
                        ? archeryStatCols
                        : defaultStatCols;

    const medians = {};
    for (const col of statCols) {
        const vals = filtered
            .filter(
                (r) =>
                    !r.is_unique &&
                    r[col] !== undefined &&
                    r[col] > -999,
            )
            .map((r) => r[col])
            .sort((a, b) => a - b);
        medians[col] =
            vals.length > 0 ? vals[Math.floor(vals.length / 2)] : 0;
    }

    const LOWER_IS_BETTER = new Set(["time_to_kill"]);
    function valClass(col, val) {
        const med = medians[col];
        if (med === undefined || val === med) return "";
        if (LOWER_IS_BETTER.has(col)) {
            return val < med ? "val-high" : "val-low";
        }
        return val > med ? "val-high" : "val-low";
    }

    const defaultColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        { key: "pes", label: "PES" },
        { key: "res", label: "RES" },
        { key: "score_30v30", label: "30v30" },
        { key: "pop_vs_champ", label: "30vChp" },
        { key: "pop_vs_paladin", label: "30vPal" },
        { key: "pop_vs_arb", label: "30vArb" },
        { key: "score_3k", label: "3K Res" },
        { key: "score_5k", label: "5K+Upg" },
        { key: "vs_champ", label: "vChamp" },
        { key: "vs_paladin", label: "vPala" },
        { key: "vs_arb", label: "vArb" },
        { key: "dps_per_cost", label: "DPS/Cost" },
        { key: "ehp_per_cost", label: "EHP/Cost" },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "final_range", label: "Range" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
    ];
    const infantryColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        ...(currentLine === "infantry"
            ? [{ key: "line_slug", label: "Line" }]
            : []),
        {
            key: "militia_value",
            label: "Score",
            info: "50% General Combat + 30% Anti-Cav + 20% Anti-Building",
        },
        {
            key: "general_combat",
            label: "General Combat",
            info: "Avg of 6 normalized matchups (30v30 + 3K res): vs Spanish Paladin, Chinese Arbalester, Chinese Champion",
        },
        {
            key: "anti_cav",
            label: "Anti-Cav",
            info: "Avg of 6 normalized matchups (30v30 + 3K res): vs Spanish Paladin, Persian War Elephant, Spanish Hussar",
        },
        {
            key: "raid_building",
            label: "Anti-Building",
            info: "Avg N_min to destroy Town Center and Castle (normalized 0\u2013100, inverted)",
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
    const archeryColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        ...(currentLine === "archery"
            ? [{ key: "line_slug", label: "Line" }]
            : []),
        {
            key: "ranged_effectiveness",
            label: "Score",
            info: "Weighted aggregate: 70% General Combat + 30% Anti-Archer",
        },
        {
            key: "general_combat",
            label: "General",
            info: "Normalized avg of 30v30 and 3K res fights vs Spanish Paladin, Chinese Arbalester, Chinese Champion",
        },
        {
            key: "anti_archer",
            label: "Anti-Archer",
            info: "Normalized avg of 30v30 and 3K res fights vs Chinese Arb, Chinese Cav Archer, Gurjaras Elephant Archer",
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "final_range", label: "Range" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
    const siegeColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        { key: "line_slug", label: "Line" },
        {
            key: "anti_building_score",
            label: "Score",
            info: "1K resources vs fully upgraded Spanish Castle. Higher = kills faster (normalized 0\u2013100)",
        },
        {
            key: "time_to_kill",
            label: "TTK (s)",
            info: "Time in seconds to destroy a fully upgraded Spanish Castle with 1K weighted resources of units",
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "final_range", label: "Range" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
    const stableColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        { key: "line_slug", label: "Line" },
        {
            key: "stable_effectiveness",
            label: "Score",
            info: "70% General Combat + 30% Anti-Cav (normalized benchmarks)",
        },
        {
            key: "general_combat",
            label: "General Combat",
            info: "Avg of 6 normalized matchups (30v30 + 3K res vs Spanish Paladin, Chinese Arb, Chinese Champion)",
        },
        {
            key: "anti_cav",
            label: "Anti-Cav",
            info: "Avg of 6 normalized matchups (30v30 + 3K res vs Spanish Paladin, Turks Heavy Camel, Vietnamese Battle Elephant)",
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed (raw)" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
    const columns =
        currentLine === "stable"
            ? stableColumns
            : isSiege
                ? siegeColumns
                : isInfantry
                    ? infantryColumns
                    : isArchery
                        ? archeryColumns
                        : defaultColumns;

    const lineInfo = UNIT_LINES[currentLine];
    const titleIcon = unitIconUrl(
        currentAge === "Castle"
            ? lineInfo?.castle || lineInfo?.imperial
            : lineInfo?.imperial,
    );

    let html = `<div class="civ-filter-wrap">
        <input type="text" id="civFilterInput" placeholder="Filter by civilization..." value="${civFilter}" oninput="renderTable()" />`;
    if (lineInfo?.subLines && lineInfo.subLines.length > 1) {
        html += `<div class="line-filters"><span class="line-filters-label">Lines:</span>`;
        for (const sl of lineInfo.subLines) {
            const checked = enabledLines.has(sl) ? "checked" : "";
            const label = LINE_LABELS[sl] || sl;
            html += `<label class="line-checkbox"><input type="checkbox" ${checked} onchange="toggleLine('${sl}')">${label}</label>`;
        }
        html += `</div>`;
    }
    html += `</div>`;

    html += `<div class="table-title">
        <img src="${titleIcon}" alt="" onerror="this.style.display='none'" />
        ${currentData.line_name} — ${currentAge} Age (${filtered.length} units)
    </div>`;

    html += '<table class="stats-table"><thead><tr>';
    for (const col of columns) {
        const isSorted = sortColumn === col.key;
        const arrow = isSorted
            ? sortDir === "asc"
                ? "\u25B2"
                : "\u25BC"
            : "\u25B4";
        const infoHtml = col.info
            ? `<span class="info-icon" title="${col.info}">\u24D8</span>`
            : "";
        html += `<th class="${isSorted ? "sorted" : ""}" onclick="sortBy('${col.key}')">
            ${col.label}${infoHtml}<span class="sort-arrow">${arrow}</span>
        </th>`;
    }
    html += "</tr></thead><tbody>";

    // Format helpers
    function fmtCell(col, row, rowIdx) {
        const k = col.key;
        const v = row[k];
        if (k === "civ_name") {
            const civImg = `${CIV_EMBLEM_BASE}${v.toLowerCase()}.png`;
            return `<td><div class="civ-cell">
                <img src="${civImg}" alt="${v}" onerror="this.style.display='none'" />
                ${v}
            </div></td>`;
        }
        if (k === "unit_name") {
            const unitImg = unitIconUrl(v);
            return `<td><div class="unit-cell">
                <img src="${unitImg}" alt="${v}" onerror="if(!this.dataset.tried){this.dataset.tried='1';const id=NAME_TO_ICON[this.alt];if(id)this.src=ICON_BASE_FALLBACK+id+'.png';else this.style.display='none'}else{this.style.display='none'}" />
                ${v}${row.is_unique ? " *" : ""}
            </div></td>`;
        }
        if (k === "line_slug") {
            return `<td>${LINE_LABELS[v] || v}</td>`;
        }
        if (k === "special_abilities") {
            return `<td style="white-space:normal;max-width:200px;font-size:0.7rem">${v || "\u2014"}</td>`;
        }
        // Numeric columns with color coding
        if (v === undefined || v === null || v <= -999) {
            return `<td>\u2014</td>`;
        }

        const cls = valClass(k, v);
        const isScore = SCORE_KEYS.has(k);
        const isStat = STAT_KEYS.has(k);
        const hcClass = isScore || isStat ? " hc-cell" : "";

        let formatted;
        if (k === "dps_per_cost") formatted = v.toFixed(3);
        else if (k === "final_speed") formatted = v.toFixed(2);
        else if (
            k === "dps" ||
            k === "ehp_per_cost" ||
            SCORE_KEYS.has(k)
        )
            formatted = v.toFixed(1);
        else if (k === "total_cost" || k === "total_upgrade_cost")
            formatted = Math.round(v);
        else if (typeof v === "number" && v === Math.floor(v))
            formatted = Math.round(v);
        else formatted = typeof v === "number" ? v.toFixed(1) : v;

        if (isScore) {
            return `<td class="${cls}${hcClass}" onmouseenter="onScoreCellEnter(event,${rowIdx},'${k}')" onmouseleave="onScoreCellLeave()" onclick="onScoreCellClick(event,${rowIdx},'${k}')">${formatted}</td>`;
        }
        if (isStat) {
            return `<td class="${cls}${hcClass}" onmouseenter="onStatCellEnter(event,${rowIdx},'${k}')" onmouseleave="onStatCellLeave()" onclick="onStatCellClick(event,${rowIdx},'${k}')">${formatted}</td>`;
        }
        return `<td class="${cls}">${formatted}</td>`;
    }

    for (let i = 0; i < filtered.length; i++) {
        const row = filtered[i];
        const rowClass = row.is_unique ? "unique-row" : "";
        html += `<tr class="${rowClass}">`;
        for (const col of columns) {
            html += fmtCell(col, row, i);
        }
        html += "</tr>";
    }

    html += "</tbody></table>";
    container.innerHTML = html;

    // Restore focus to filter input if it was active
    if (civFilter) {
        const inp = document.getElementById("civFilterInput");
        if (inp) {
            inp.focus();
            inp.selectionStart = inp.selectionEnd =
                inp.value.length;
        }
    }
}

function sortBy(column) {
    if (sortColumn === column) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
        sortColumn = column;
        sortDir =
            column === "civ_name" || column === "unit_name"
                ? "asc"
                : "desc";
    }
    renderTable();
}

// ===== INIT =====
renderLineSelector();
selectLine("infantry");
