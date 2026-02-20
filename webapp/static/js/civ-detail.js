/* ==========================================================================
   AoE2 Unit Analyzer — Civ Detail Page
   Requires: constants.js (NAME_TO_ICON, ICON_BASE, UNIQUE_BUILDING)
   Requires: CIV_NAME global set in inline <script> tag
   ========================================================================== */

const PLACEHOLDER_ICON =
    "data:image/svg+xml," +
    encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><rect x="1" y="1" width="38" height="38" rx="6" stroke="#5a4228" stroke-width="2" fill="#2c1e10"/></svg>',
    );

function iconUrl(id) {
    return ICON_BASE + id + ".png";
}

function unitIconUrl(name) {
    const id = NAME_TO_ICON[name];
    if (!id) return "";
    return iconUrl(id);
}

// Building config
const BUILDING_ORDER = [
    "Barracks",
    "Archery Range",
    "Stable",
    "Castle",
    "Siege Workshop",
];
const BUILDING_ICONS = {
    Barracks: 12,
    "Archery Range": 87,
    Stable: 101,
    "Siege Workshop": 49,
    Castle: 82,
};
const CLASS_TO_BUILDING = {
    Infantry: "Barracks",
    Archer: "Archery Range",
    "Hand Cannoneer": "Archery Range",
    "Cavalry Archer": "Archery Range",
    Cavalry: "Stable",
    "Siege Weapon": "Siege Workshop",
    Ballista: "Siege Workshop",
    "Unpacked Siege Unit": "Castle",
};

// SVG stat icons (tiny inline)
const ICONS = {
    hp: '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M5 9L1.5 5.5C0 4 0 2 1.5 1.5S4 1 5 3C6 1 7.5 0 8.5 1.5S10 4 8.5 5.5L5 9z" fill="#c44"/></svg>',
    atk: '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 8L8 2M6 1h3v3" stroke="#c9a84c" stroke-width="1.2" fill="none"/></svg>',
    armor: '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M5 1L1 3v3c0 2 2 3 4 3s4-1 4-3V3L5 1z" stroke="#8a8" stroke-width="1" fill="none"/></svg>',
    range: '<svg width="10" height="10" viewBox="0 0 10 10"><circle cx="5" cy="5" r="3.5" stroke="#8ac" stroke-width="1" fill="none"/><circle cx="5" cy="5" r="1" fill="#8ac"/></svg>',
    speed: '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 2L7 5L3 8" stroke="#a8a" stroke-width="1.2" fill="none"/></svg>',
};

let civData = null;
let currentAge = "Imperial";

async function loadData() {
    try {
        const resp = await fetch(`/api/ref/civ/${CIV_NAME}`);
        if (!resp.ok) throw new Error("Failed to load");
        civData = await resp.json();
        document.getElementById("loading").style.display = "none";
        render();
    } catch (e) {
        document.getElementById("loading").textContent =
            "Error loading data: " + e.message;
    }
}

function setAge(age) {
    currentAge = age;
    document
        .querySelectorAll(".age-btn")
        .forEach((b) =>
            b.classList.toggle("active", b.dataset.age === age),
        );
    render();
}

function hasCivBonus(u) {
    // Check if unit has civ-specific bonuses (unique tech, civ bonus, team bonus)
    if (!u.stat_chain) return false;
    return u.stat_chain.some(
        (s) =>
            s.tech_type === "civ_bonus" ||
            s.tech_type === "unique_tech" ||
            s.tech_type === "team_bonus",
    );
}

function render() {
    const units = civData.units_by_age[currentAge] || [];
    const container = document.getElementById("units-container");
    const groups = {};
    for (const u of units) {
        let building =
            CLASS_TO_BUILDING[u.unit_class_name] || "Castle";
        if (u.unit_type === "unique")
            building = UNIQUE_BUILDING[u.unit_name] || "Castle";
        if (!groups[building]) groups[building] = [];
        groups[building].push(u);
    }
    let html = '<div class="buildings-grid">';
    for (const bldg of BUILDING_ORDER) {
        const bUnits = groups[bldg];
        if (!bUnits || bUnits.length === 0) continue;
        const bIconId = BUILDING_ICONS[bldg];
        html += `<div class="building-group">
    <div class="building-header">
        <img class="building-icon" src="${iconUrl(bIconId)}" alt="${bldg}" onerror="this.style.display='none'" />
        <h2>${bldg}</h2>
    </div>
    <div class="units-row">`;
        for (const u of bUnits) html += renderUnitCard(u);
        html += `</div></div>`;
    }
    html += "</div>";
    container.innerHTML = html;
}

function getMainAttack(u) {
    const fa = u.final_attacks || {};
    return u.is_ranged
        ? (fa["Base Pierce"] ?? u.final_stats.attack ?? 0)
        : (fa["Base Melee"] ?? u.final_stats.attack ?? 0);
}

function renderUnitCard(u) {
    const iUrl = unitIconUrl(u.unit_name);
    const civBonus = hasCivBonus(u);
    return `<div class="unit-card" onclick='openModal(${JSON.stringify(u.unit_slug)})'>
    ${civBonus ? '<span class="civ-star" title="Has civ bonus">&#9733;</span>' : ""}
    <img class="unit-icon" src="${iUrl}" alt="${u.unit_name}" onerror="this.src='${PLACEHOLDER_ICON}'"/>
    <div class="unit-name">${u.unit_name}</div>
</div>`;
}

// Get the primary attack class key for a unit (melee or pierce)
function getPrimaryAtkClass(u) {
    return u.is_ranged ? "3" : "4"; // 3=Base Pierce, 4=Base Melee
}

function getMainAtkFromJson(attacksJson, primaryClass) {
    if (!attacksJson) return 0;
    const parsed =
        typeof attacksJson === "string"
            ? JSON.parse(attacksJson)
            : attacksJson;
    return (
        parsed[primaryClass] ??
        Math.max(...Object.values(parsed), 0)
    );
}

function openModal(slug) {
    const units = civData.units_by_age[currentAge] || [];
    const u = units.find((x) => x.unit_slug === slug);
    if (!u) return;

    const iUrl = unitIconUrl(u.unit_name);
    const bs = u.base_stats;
    const fs = u.final_stats;
    const primaryAtkClass = getPrimaryAtkClass(u);

    let html = `<div class="modal-unit-header">
    <img class="modal-unit-icon" src="${iUrl}" alt="${u.unit_name}" onerror="this.style.display='none'" />
    <div class="modal-unit-info">
        <h3>${u.unit_name}</h3>
        <span class="class-badge">${u.unit_class_name}${u.unit_type === "unique" ? " — Unique" : ""}</span>
    </div>
</div>`;

    // Get base/final main attack from attacks data
    const baseMainAtk = u.is_ranged
        ? (u.base_attacks["Base Pierce"] ?? bs.attack ?? 0)
        : (u.base_attacks["Base Melee"] ?? bs.attack ?? 0);
    const finalMainAtk = getMainAttack(u);

    // Stat breakdown: "Final (base +X (tech) +Y (tech) ...)"
    html += `<div class="stat-section"><h4>Stats Breakdown</h4>`;
    const statDefs = [
        { key: "hp", label: "HP", chainCol: "hp" },
        {
            key: "attack",
            label: "Attack",
            chainCol: "attack",
            baseOverride: baseMainAtk,
            finalOverride: finalMainAtk,
            useAtkJson: true,
        },
        {
            key: "melee_armor",
            label: "Melee Armor",
            chainCol: "melee_armor",
        },
        {
            key: "pierce_armor",
            label: "Pierce Armor",
            chainCol: "pierce_armor",
        },
        { key: "range", label: "Range", chainCol: "range_val" },
        { key: "speed", label: "Speed", chainCol: "speed" },
        {
            key: "reload_time",
            label: "Reload Time",
            chainCol: "reload_time",
            lowerIsBetter: true,
        },
    ];
    for (const sd of statDefs) {
        const baseVal = sd.baseOverride ?? bs[sd.key] ?? 0;
        const finalVal = sd.finalOverride ?? fs[sd.key] ?? 0;
        if (
            baseVal === 0 &&
            finalVal === 0 &&
            sd.key !== "melee_armor" &&
            sd.key !== "pierce_armor"
        )
            continue;
        const changed = Math.abs(finalVal - baseVal) > 0.01;
        const chainStr = buildStatChain(
            u.stat_chain,
            sd.chainCol,
            sd.key,
            sd.useAtkJson ? primaryAtkClass : null,
            sd.lowerIsBetter,
        );
        html += `<div class="stat-row">
    <span class="stat-label">${sd.label}</span>
    <span class="stat-final-val${changed ? " improved" : ""}">${fmtStat(finalVal)}</span>
    ${chainStr ? `<span class="stat-chain">(${chainStr})</span>` : ""}
</div>`;
    }
    html += `</div>`;

    // Cost with chain
    html += `<div class="stat-section"><h4>Cost</h4>`;
    const costDefs = [
        { key: "cost_food", label: "Food", cls: "cost-food" },
        { key: "cost_wood", label: "Wood", cls: "cost-wood" },
        { key: "cost_gold", label: "Gold", cls: "cost-gold" },
    ];
    for (const cd of costDefs) {
        const baseVal = bs[cd.key] ?? 0;
        const finalVal = fs[cd.key] ?? 0;
        if (baseVal === 0 && finalVal === 0) continue;
        const costChain = buildStatChain(
            u.stat_chain,
            cd.key,
            cd.key,
            null,
            true,
        );
        const changed = Math.abs(finalVal - baseVal) > 0.01;
        html += `<div class="stat-row">
    <span class="stat-label">${cd.label}</span>
    <span class="stat-final-val${changed ? " improved" : ""}">${Math.round(finalVal)}</span>
    ${costChain ? `<span class="stat-chain">(${costChain})</span>` : ""}
</div>`;
    }
    // Train time with chain
    const baseTT = bs.train_time ?? 0;
    const finalTT = fs.train_time ?? 0;
    if (baseTT > 0 || finalTT > 0) {
        const ttChain = buildStatChain(
            u.stat_chain,
            "train_time",
            "train_time",
            null,
            true,
        );
        const ttChanged = Math.abs(finalTT - baseTT) > 0.01;
        html += `<div class="stat-row">
    <span class="stat-label">Train Time</span>
    <span class="stat-final-val${ttChanged ? " improved" : ""}">${fmtStat(finalTT)}s</span>
    ${ttChain ? `<span class="stat-chain">(${ttChain})</span>` : ""}
</div>`;
    }
    html += `</div>`;

    // Attack & Armor classes side by side
    html += `<div class="classes-grid">`;
    html += renderClassTable(
        "Attack Classes",
        u.final_attacks,
        u.base_attacks,
    );
    html += renderClassTable(
        "Armor Classes",
        u.final_armors,
        u.base_armors,
    );
    html += `</div>`;

    // Special effects
    if (u.special_effects && u.special_effects.length > 0) {
        html += `<div class="stat-section"><h4>Special Properties</h4>`;
        for (const se of u.special_effects) {
            html += `<div class="special-item">
        <span class="special-name">${se.property_name}</span>: ${se.property_value}
        <span class="special-desc">${se.description ? " — " + se.description : ""}</span>
    </div>`;
        }
        html += `</div>`;
    }

    // Projectiles
    if (u.projectiles && u.projectiles.length > 0) {
        html += `<div class="stat-section"><h4>Projectiles</h4>`;
        for (const p of u.projectiles) {
            const atkStr = p.attacks_json
                ? Object.entries(p.attacks_json)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")
                : "";
            html += `<div class="special-item">
        <span class="special-name">${p.projectile_type}</span>
        — Count: ${p.projectile_count}, Speed: ${p.projectile_speed}
        ${p.blast_radius ? `, Blast: ${p.blast_radius}` : ""}
        ${p.is_siege_projectile ? " (Siege)" : ""}
        ${atkStr ? `<br><span class="special-desc">Attacks: ${atkStr}</span>` : ""}
    </div>`;
        }
        html += `</div>`;
    }

    // Techs applied
    html += `<div class="stat-section"><h4>Technologies Applied</h4>`;
    for (const t of u.techs_applied) {
        const bldg =
            t.building && t.building !== "N/A"
                ? `<span style="color:var(--text-muted)">[${t.building}]</span> `
                : "";
        html += `<div style="font-size:0.8rem;padding:3px 0">
    ${bldg}<span style="color:var(--parchment)">${t.tech_name}</span>
    <span class="special-desc"> — ${t.effect_description}</span>
</div>`;
    }
    html += `</div>`;

    document.getElementById("modal-body").innerHTML = html;
    document.getElementById("modal-overlay").classList.add("open");
    document.body.style.overflow = "hidden";
}

function closeModal() {
    document
        .getElementById("modal-overlay")
        .classList.remove("open");
    document.body.style.overflow = "";
}

// Build inline stat chain: "base +X (Tech1) +Y (Tech2) ..."
function buildStatChain(
    chain,
    chainCol,
    statKey,
    atkClass,
    lowerIsBetter,
) {
    if (!chain || chain.length < 1) return "";
    // Get base value
    const first = chain[0];
    let baseVal;
    if (atkClass) {
        baseVal = getMainAtkFromJson(first.attacks_json, atkClass);
    } else {
        baseVal = first[chainCol] ?? 0;
    }

    let parts = [fmtStat(baseVal)];
    let anyChange = false;

    for (let i = 1; i < chain.length; i++) {
        const prev = chain[i - 1];
        const curr = chain[i];
        let prevVal, currVal;

        if (atkClass) {
            prevVal = getMainAtkFromJson(
                prev.attacks_json,
                atkClass,
            );
            currVal = getMainAtkFromJson(
                curr.attacks_json,
                atkClass,
            );
        } else {
            prevVal = prev[chainCol] ?? 0;
            currVal = curr[chainCol] ?? 0;
        }

        const diff = currVal - prevVal;
        if (Math.abs(diff) < 0.01) continue;
        anyChange = true;
        const sign = diff > 0 ? "+" : "";
        // For lowerIsBetter stats (reload, cost, train time), decrease is good
        const isGood = lowerIsBetter ? diff < 0 : diff > 0;
        const cls = isGood ? "positive" : "negative";
        const techName = curr.tech_name || "";
        const shortName = techName
            .replace(/^C-Bonus, /, "")
            .replace(/^Building Work Rate.*/, "Conscription");
        parts.push(
            `<span class="step ${cls}">${sign}${fmtStat(diff)}</span> <span class="step"><span class="tech-name">${shortName}</span></span>`,
        );
    }
    if (!anyChange) return "";
    return parts.join(" ");
}

function fmtStat(v) {
    if (v === null || v === undefined) return "0";
    const n = Number(v);
    return Number.isInteger(n)
        ? n.toString()
        : n.toFixed(2).replace(/\.?0+$/, "");
}

function renderClassTable(title, finalClasses, baseClasses) {
    const entries = Object.entries(finalClasses || {}).filter(
        ([k, v]) =>
            v !== 0 || (baseClasses && baseClasses[k] !== 0),
    );
    if (entries.length === 0) return "";
    let html = `<div class="stat-section"><h4>${title}</h4>
    <table class="class-table"><tr><th>Class</th><th style="text-align:right">Value</th></tr>`;
    for (const [cls, val] of entries.sort(
        (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
    )) {
        html += `<tr><td>${cls}</td><td class="val">${val}</td></tr>`;
    }
    html += `</table></div>`;
    return html;
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});

loadData();
