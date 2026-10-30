// Browser integration of the preserved Railway rankings interactions.
import {buildTable,buildLineSelector,UNIT_LINES,LINE_LABELS,SCORE_KEYS,STAT_KEYS,rankingRowKey,compactProgressiveBonuses} from "./render.mjs";
import {RankingsV3Model} from "./model.mjs";
import {createPageData} from "./page-data.mjs";
const config = JSON.parse(document.getElementById("ranking-config").textContent);
const bootstrap = JSON.parse(document.getElementById("ranking-bootstrap").textContent);
const rankingsData = createPageData();
// The published animations are requested only on hover or row selection.
document.addEventListener('mouseover', event => {
    const image = event.target.closest?.('img[data-anim-name]');
    if (!image || image.contains(event.relatedTarget)) return;
    const url = config.media[image.dataset.animName]?.animation;
    if (!url) return;
    image.dataset.staticSrc ??= image.getAttribute('src');
    image.src = url;
});
document.addEventListener('mouseout', event => {
    const image = event.target.closest?.('img[data-anim-name]');
    if (image && !image.contains(event.relatedTarget) && image.dataset.staticSrc !== undefined) image.src = image.dataset.staticSrc;
});
const RankingsScoreMethod = (() => {
    const METHODS = config.methods?.methods || {};

    function getMethod(category) {
        return METHODS[category] || null;
    }

    function buildHtml(category) {
        const method = getMethod(category);
        if (!method) return "";

        const matchupRows = method.formula
            .map(
                ([weight, matchup]) =>
                    `<div class="score-method-row"><strong>${weight}</strong><span>${matchup}</span></div>`,
            )
            .join("");
        const adjustment = method.adjustment
            ? `<div class="score-method-adjustment">${method.adjustment}</div>`
            : "";

        return `<div class="hc-title">${method.title}: how it is calculated</div>
            <div class="score-method-label">Battle setting</div>
            <div class="score-method-setting">${method.setting}</div>
            <div class="score-method-label">Matchups and weights</div>
            <div class="score-method-rows">${matchupRows}</div>
            ${adjustment}
            <div class="score-method-label">From battle result to score</div>
            <div class="score-method-setting">${method.result}</div>
            <div class="hc-note score-method-note">${method.finish} Higher is better.</div>`;
    }

    return { buildHtml, getMethod };
})();
function buildRankingScoreHoverHtml(row) {
    const score = row.ranking_score;
    const breakdown = RankingsV3Model.buildBreakdown(row);
    let html = `<div class="hc-title">${row.unit_name || row.unit_slug} — Score</div>`;
    html += `<div class="ranking-score-summary">`;
    html += `<span class="ranking-score-value" style="color:${scoreColor(score)}">${score == null ? "—" : Number(score).toFixed(1)}</span>`;
    if (row.ranking_rank != null) html += `<span>#${row.ranking_rank} in line</span>`;
    if (row.ranking_median_delta != null) {
        const delta = Number(row.ranking_median_delta);
        html += `<span>${delta >= 0 ? "+" : ""}${delta.toFixed(1)} vs median</span>`;
    }
    html += `</div>`;

    if (breakdown.roles.length) {
        html += `<div class="ranking-breakdown-label">Role scores</div>`;
        html += `<div class="ranking-role-grid">`;
        for (const role of breakdown.roles) {
            html += `<span><strong>${role.label}</strong>${Number(role.score).toFixed(1)}</span>`;
        }
        html += `</div>`;
    }

    if (breakdown.yardsticks.length) {
        html += `<div class="ranking-breakdown-label">Opponent scores</div>`;
        html += `<div class="ranking-yardstick-grid">`;
        for (const yardstick of breakdown.yardsticks) {
            html += `<span>${yardstick.label}</span><strong style="color:${scoreColor(yardstick.score)}">${Number(yardstick.score).toFixed(1)}</strong>`;
        }
        html += `</div>`;
        html += `<div class="hc-note">Simulation V3 · 3 runs, extended to 10 when outcomes differ · 27 units on the cheaper side · population and cost balanced · food/wood/gold weights 1/0.9/1.1.</div>`;
    } else {
        html += `<div class="hc-note">This line uses its published cost-based score. Detailed V3 yardsticks will appear when that campaign is available.</div>`;
    }
    return html;
}

function buildScoreHoverHtml(row, scoreKey, dataKey) {
    dataKey = dataKey || scoreKey;
    if (scoreKey === "ranking_score") return buildRankingScoreHoverHtml(row);
    const info = SCORE_BREAKDOWN[scoreKey];
    if (!info) {
        // Composite score hover cards.
        // `parts` show the component values stored in the DB (already
        // post-processed by their own speed-weighting). `formula` describes
        // how the displayed Score is computed from those components and
        // what additional weighting is applied — the math will NOT add up
        // by simple weighted-sum of `parts`, because the score is
        // re-normalized to 0-100 after each weighting step. The note line
        // explains what extra weighting/normalization happens.
        const composites = {
            militia_value: {
                title: "Overall Score",
                formula: "0.75 \u00d7 General Combat + 0.10 \u00d7 Anti-Cav + 0.15 \u00d7 Anti-Trash",
                note: "Final score is then multiplied by movement speed and re-normalized 0-100 across the entire infantry pool (militia, spear, shock).",
                parts: [
                    { key: "general_combat", label: "General Combat" },
                    { key: "anti_cav", label: "Anti-Cav" },
                    { key: "anti_trash", label: "Anti-Trash" },
                ],
            },
            ranged_effectiveness: {
                title: "Ranged Effectiveness Score",
                formula: "0.70 \u00d7 General Combat + 0.30 \u00d7 Anti-Archer",
                note: "Components are speed-weighted (pool) before combining; final score is then multiplied by attack range and re-normalized 0-100 across all ranged units (archer, skirmisher, cav archer, scorpion, gunpowder).",
                parts: [
                    { key: "general_combat", label: "General Combat (speed-weighted)" },
                    { key: "anti_archer", label: "Anti-Archer (speed-weighted)" },
                ],
            },
            stable_effectiveness: {
                title: "Stable Effectiveness",
                formula: "0.70 \u00d7 General Combat + 0.30 \u00d7 Anti-Cav",
                note: "Final score is multiplied by movement speed and re-normalized 0-100 globally across all stable units (knight, light cav, camel, steppe lancer, elephant).",
                parts: [
                    { key: "general_combat", label: "General Combat" },
                    { key: "anti_cav", label: "Anti-Cav" },
                ],
            },
        };
        const comp = composites[scoreKey];
        if (comp) {
            let html = `<div class="hc-title">${comp.title}</div>`;
            html += `<div class="hc-formula">${comp.formula}</div>`;
            for (const p of comp.parts) {
                const v = row[p.key];
                const vs =
                    v !== undefined && v > -999
                        ? v.toFixed(1)
                        : "\u2014";
                html += `<div class="hc-row"><span>${p.label}</span><span style="color:${scoreColor(v)}">${vs}</span></div>`;
            }
            const total = row[dataKey];
            html += `<div class="hc-row total"><span>Score</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "\u2014"}</span></div>`;
            if (comp.note) {
                html += `<div class="hc-note" style="margin-top:6px;font-size:0.85em;opacity:0.75;line-height:1.3">${comp.note}</div>`;
            }
            return html;
        }
        return "";
    }
    let html = `<div class="hc-title">${info.title}</div>`;
    if (info.subs === "siege_breakdown") {
        html += `<div class="hc-formula">${info.formula}</div>`;
        html += _buildSiegeBreakdownHtml(row);
        const total = row[dataKey];
        html += `<div class="hc-row total"><span>Score</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "—"}</span></div>`;
        return html;
    }
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
// ===== STATE =====
let currentAge = "Imperial";
let currentLine = null;
let currentData = null;
let sortColumn = "civ_name";
let enabledLines = new Set();
let sortDir = "asc";
let currentEnriched = [];
let pinnedCell = null;
let activeStatCell = null;
let selectedRankingRowKey = null;
const statChainCache = {};

// Per-group expansion state - fully transient, resets on page load.
// Groups are: "GC", "AC", "AT", "AA", "Special".
const expandedGroups = new Set();

function toggleGroup(group) {
    if (expandedGroups.has(group)) expandedGroups.delete(group);
    else expandedGroups.add(group);
    renderTable();
}

function expandAll() {
    expandedGroups.add("GC");
    expandedGroups.add("AC");
    expandedGroups.add("AT");
    expandedGroups.add("AA");
    expandedGroups.add("Special");
    renderTable();
}

function collapseAll() {
    expandedGroups.clear();
    renderTable();
}

function isExpanded(group) {
    return expandedGroups.has(group);
}


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
        formula: "Avg of 2 normalized matchups (vs Paladin at 30v30 + 3K res)",
        subs: [
            { key: "ac_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "ac_3k_vs_paladin",    label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
        ],
    },
    anti_trash: {
        title: "Anti-Trash",
        formula: "Average of 6 normalized matchups (3 \u00d7 30v30 + 3 \u00d7 3K res)",
        subs: [
            { key: "at_30v30_vs_halb",        label: "vs Halberdier (30v30)",       civ: "Spanish", slug: "halberdier",      mode: "count", count: 30 },
            { key: "at_30v30_vs_hussar",       label: "vs Hussar (30v30)",           civ: "Spanish", slug: "hussar",          mode: "count", count: 30 },
            { key: "at_30v30_vs_elite_skirm",  label: "vs Elite Skirmisher (30v30)", civ: "Spanish", slug: "imp_elite_skirm", mode: "count", count: 30 },
            { key: "at_3k_vs_halb",            label: "vs Halberdier (3K res)",      civ: "Spanish", slug: "halberdier",      mode: "resources", res: 3000 },
            { key: "at_3k_vs_hussar",          label: "vs Hussar (3K res)",          civ: "Spanish", slug: "hussar",          mode: "resources", res: 3000 },
            { key: "at_3k_vs_elite_skirm",     label: "vs Elite Skirmisher (3K res)", civ: "Spanish", slug: "imp_elite_skirm", mode: "resources", res: 3000 },
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
    anti_archer: {
        title: "Anti-Archer Score",
        formula: "Avg of 2 normalized matchups (vs Arbalester at 30v30 + 3K res)",
        subs: [
            { key: "aa_30v30_vs_arb", label: "vs Arbalester (30v30)", civ: "Chinese", slug: "arbalester", mode: "count", count: 30 },
            { key: "aa_3k_vs_arb",    label: "vs Arbalester (3K res)", civ: "Chinese", slug: "arbalester", mode: "resources", res: 3000 },
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
        formula: "Avg of 2 normalized matchups (vs Paladin at 30v30 + 3K res)",
        subs: [
            { key: "ac_30v30_vs_paladin", label: "vs Paladin (30v30)", civ: "Spanish", slug: "paladin", mode: "count", count: 30 },
            { key: "ac_3k_vs_paladin",    label: "vs Paladin (3K res)", civ: "Spanish", slug: "paladin", mode: "resources", res: 3000 },
        ],
    },
    // Siege score breakdowns
    anti_building_score: {
        title: "Anti-Building Score",
        formula: "Avg effective TTK across 3 Imperial castles (Persian / Teuton / Byzantine) × 2 modes (fixed-count + 5K res), normalized globally across all siege units of the same age. No speed weighting (siege pre-positions at range; rams are armored).",
        subs: "siege_breakdown",   // sentinel: use custom siege hover renderer
    },
    naval_effectiveness: {
        title: "Naval Effectiveness",
        formula: "Average of vs_galleon + vs_fire + vs_hulk (each = avg 30v30 + 3K res), speed-weighted per sub-line",
        subs: [
            { key: "vs_galleon_30v30", label: "vs Galleon (30v30)",   civ: "Britons",   slug: "galleon", mode: "count", count: 30 },
            { key: "vs_galleon_3k",    label: "vs Galleon (3K res)",   civ: "Britons",   slug: "galleon", mode: "resources", res: 3000 },
            { key: "vs_fire_30v30",    label: "vs Fire Ship (30v30)",  civ: "Britons",   slug: "fire",    mode: "count", count: 30 },
            { key: "vs_fire_3k",       label: "vs Fire Ship (3K res)", civ: "Britons",   slug: "fire",    mode: "resources", res: 3000 },
            { key: "vs_hulk_30v30",    label: "vs Hulk (30v30)",       civ: "Sicilians", slug: "hulk",    mode: "count", count: 30 },
            { key: "vs_hulk_3k",       label: "vs Hulk (3K res)",      civ: "Sicilians", slug: "hulk",    mode: "resources", res: 3000 },
        ],
    },
};

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

// Phones (<=480px) render the PINNED card as a CSS bottom-sheet. JS must not
// write inline top/left there or it would override the sheet positioning.
function isPhoneViewport() {
    return (
        typeof window.matchMedia === "function" &&
        window.matchMedia("(max-width: 480px)").matches
    );
}

function positionHoverCard(targetEl) {
    const hc = getHoverCardEl();
    // On phones, a pinned card is a bottom sheet (CSS-positioned). Clear any
    // stale inline coords so the stylesheet rules take effect, then bail.
    if (isPhoneViewport() && hc.classList.contains("pinned")) {
        hc.style.top = "";
        hc.style.left = "";
        return;
    }
    const rect = targetEl.getBoundingClientRect();
    const hcRect = hc.getBoundingClientRect();
    let top = rect.top - hcRect.height - 8;
    let left = rect.left + rect.width / 2 - hcRect.width / 2;
    if (top < 4) top = rect.bottom + 8;
    // Clamp the bottom edge too: a tall breakdown opened low on the page would
    // otherwise run off the bottom of the viewport (the card has no fixed
    // height). Keep it fully on-screen, scrolling internally if needed.
    if (top + hcRect.height > window.innerHeight - 4)
        top = Math.max(4, window.innerHeight - hcRect.height - 4);
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
    if (pinnedCell && typeof pinnedCell.setAttribute === "function") {
        pinnedCell.setAttribute("aria-expanded", "false");
    }
    pinnedCell = null;
    const hc = getHoverCardEl();
    hc.classList.remove("visible", "pinned");
}

// Swap the content of an already-pinned card WITHOUT toggling it. Used to fill
// in async breakdowns (e.g. stat chain) after a tap pins a "Loading…" card —
// re-calling pinHoverCard(sameEl) would treat it as a second tap and close it,
// which on touch (no preceding hover to warm the cache) hid the card entirely.
function updatePinnedCard(targetEl, html) {
    if (pinnedCell !== targetEl) return;
    const hc = getHoverCardEl();
    hc.innerHTML =
        `<span class="hc-close" onclick="unpinHoverCard()">&times;</span>` +
        html;
    positionHoverCard(targetEl);
}

document.addEventListener("click", (e) => {
    if (!pinnedCell) return;
    const hc = getHoverCardEl();
    if (hc.contains(e.target)) return;
    if (e.target.closest("td.hc-cell")) return;
    if (e.target.closest("[data-info-pin]")) return;  // its own handler manages it
    unpinHoverCard();
});

// Touch reachability for native title= tooltips. The `.info-icon` (column help)
// and `.special-cell` lines carry their full text in title=, which is invisible
// on touch (no hover). On coarse pointers, surface that text via the shared
// pinned card (a bottom sheet at <=480px). Desktop keeps the native tooltip.
function pinTitleText(targetEl, title) {
    const safe = String(title)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    pinHoverCard(targetEl, `<div class="hc-title">Details</div>
        <div style="white-space:pre-line;line-height:1.4">${safe}</div>`);
}

function _isCoarsePointer() {
    return (
        typeof window.matchMedia === "function" &&
        window.matchMedia("(hover: none), (pointer: coarse)").matches
    );
}

document.addEventListener(
    "click",
    (e) => {
        if (!_isCoarsePointer()) return;
        // Column info icon: explicit, always tappable.
        const icon = e.target.closest(".info-icon[title]");
        if (icon) {
            e.stopPropagation();
            icon.setAttribute("data-info-pin", "");
            pinTitleText(icon, icon.getAttribute("title"));
            return;
        }
        // A truncated Special-column line: its title holds the full text.
        const sp = e.target.closest(".special-cell [title]");
        if (sp && sp.getAttribute("title")) {
            e.stopPropagation();
            sp.setAttribute("data-info-pin", "");
            pinTitleText(sp, sp.getAttribute("title"));
        }
    },
    true,  // capture: run before the outside-tap dismiss handler above
);

function scoreMethodCategory() {
    if (INFANTRY_SLUGS.has(currentLine)) return "infantry";
    if (ARCHERY_SLUGS.has(currentLine)) return "archery";
    if (
        currentLine === "stable" ||
        (UNIT_LINES.stable?.subLines || []).includes(currentLine)
    ) return "stable";
    if (SIEGE_SLUGS.has(currentLine)) return "siege";
    if (NAVAL_SLUGS.has(currentLine)) return "naval";
    return null;
}

function onScoreMethodInfoClick(event) {
    event.preventDefault();
    event.stopPropagation();
    const button = event.currentTarget;
    const category = scoreMethodCategory();
    const html =
        typeof RankingsScoreMethod !== "undefined"
            ? RankingsScoreMethod.buildHtml(category)
            : "";
    if (!html) return;
    pinHoverCard(button, html);
    button.setAttribute(
        "aria-expanded",
        pinnedCell === button ? "true" : "false",
    );
}

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

function _buildSiegeBreakdownHtml(row) {
    const castles = [
        { name: "vs Persian",   prefix: "ab_persian" },
        { name: "vs Teuton",    prefix: "ab_teuton" },
        { name: "vs Byzantine", prefix: "ab_byzantine" },
    ];
    const modes = [
        { suffix: "5u", label: "Fixed" },
        { suffix: "5k", label: "5K res" },
    ];

    // Header row
    let html = `<div class="hc-row hc-siege-header">`;
    html += `<span></span>`;
    for (const m of modes) {
        html += `<span>${m.label}</span>`;
    }
    html += `</div>`;

    // One row per castle
    for (const castle of castles) {
        html += `<div class="hc-row">`;
        html += `<span>${castle.name}</span>`;
        for (const mode of modes) {
            const ttk = row[`${castle.prefix}_${mode.suffix}_ttk`];
            const dmg = row[`${castle.prefix}_${mode.suffix}_dmg`];
            let cell;
            if (dmg === undefined || ttk === undefined) {
                cell = "—";
            } else if (dmg >= 0.999) {
                cell = `${Math.round(ttk)}s`;
            } else {
                const pct = Math.round(dmg * 100);
                cell = `✗ ${pct}%`;
            }
            html += `<span>${cell}</span>`;
        }
        html += `</div>`;
    }
    return html;
}

async function getStatChain(refUnitId, source = "reference") {
    const cacheKey = `${source}:${refUnitId}`;
    if (statChainCache[cacheKey]) return statChainCache[cacheKey];
    try {
        const data = await rankingsData.detail(`/api/ref/stat-chain/${refUnitId}?source=${encodeURIComponent(source)}`);
        statChainCache[cacheKey] = data;
        return data;
    } catch (e) {
        console.error("Failed to load stat chain for unit", refUnitId, e);
        statChainCache[cacheKey] = {};   // tombstone: degrade once, don't retry on every hover
        return {};
    }
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
    activeStatCell = e.currentTarget;
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
    const chain = await getStatChain(row.id, row.stat_chain_source);
    if (!pinnedCell && activeStatCell === td && td.isConnected)
        showHoverCard(td, buildStatHoverHtml(row, key, chain));
}

function onStatCellLeave() {
    activeStatCell = null;
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
    const chain = await getStatChain(row.id, row.stat_chain_source);
    // Update in place — don't re-call pinHoverCard, which would toggle this
    // same cell's card closed (and on touch there's no warm cache to dodge it).
    updatePinnedCard(td, buildStatHoverHtml(row, key, chain));
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
    "cannon_galleon",
]);

const NAVAL_SLUGS = new Set([
    "galleon",
    "fire",
    "hulk",
    "naval",
]);

async function selectLine(slug) {
    activeStatCell = null;
    currentLine = slug;
    selectedRankingRowKey = null;
    unpinHoverCard();

    // Highlight active tab
    document
        .querySelectorAll(".unit-tab")
        .forEach((c) => c.classList.remove("active"));
    const tabs = document.querySelectorAll(".unit-tab");
    tabs.forEach((c) => {
        if (c.getAttribute("onclick")?.includes(`'${slug}'`))
            c.classList.add("active");
    });

    let data;
    try { data = await rankingsData.select(config.files[slug], slug === "infantry" ? bootstrap : undefined); }
    catch (error) {
        if (error.name === "AbortError" || currentLine !== slug) return;
        document.getElementById("tableContainer").textContent = "Could not load rankings. Please select a tab to retry.";
        return;
    }
    if (!data || currentLine !== slug) return;
    currentData = data;
    // Enable all sub-lines by default
    const lineInfo = UNIT_LINES[slug];
    enabledLines = new Set(lineInfo?.subLines || []);
    sortColumn = "ranking_score";
    sortDir = "desc";
    renderTable();
    // Keep the address bar shareable (/units?line=<slug>) without polluting
    // browser history. The default tab keeps the clean /units URL.
    if (window.history && history.replaceState) {
        const url = new URL(location.href);
        if (slug === "infantry") url.searchParams.delete("line"); else url.searchParams.set("line", slug);
        url.searchParams.delete("unit");
        history.replaceState(null, "", url.pathname + url.search);
    }
}

function renderTable() {
    activeStatCell = null;
    const container = document.getElementById("tableContainer");
    const civFilter = document.getElementById("civFilterInput")?.value?.toLowerCase() || "";
    const rendered = buildTable({currentData,currentLine,currentAge,sortColumn,sortDir,enabledLines,expandedGroups,selectedRankingRowKey,civFilter,media:config.media});
    currentEnriched = rendered.rows;
    container.innerHTML = rendered.html;
    const selectRenderedRow = (tr) => {
        const key = tr?.dataset.rankingKey;
        if (!key) return;
        selectedRankingRowKey = selectedRankingRowKey === key ? null : key;
        renderTable();
    };
    const tableBody = container.querySelector("tbody");
    if (tableBody) {
        tableBody.addEventListener("click", (event) => {
            if (event.target.closest("a, button, input, label, .hc-cell")) return;
            selectRenderedRow(event.target.closest("tr[data-ranking-key]"));
        });
        tableBody.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            const tr = event.target.closest("tr[data-ranking-key]");
            if (!tr) return;
            event.preventDefault();
            selectRenderedRow(tr);
        });
    }

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

// ===== CSV EXPORT =====
function exportCSV() {
    if (!currentEnriched || currentEnriched.length === 0) {
        console.warn("exportCSV: no data to export");
        return;
    }
    try {

    // Sort by the one published final score to compute display rank.
    const primaryScore = "ranking_score";
    const ranked = [...currentEnriched].sort((a, b) => {
        const va = a[primaryScore] ?? -999;
        const vb = b[primaryScore] ?? -999;
        return vb - va;
    });
    const rankMap = new Map();
    ranked.forEach((row, i) => rankMap.set(row, i + 1));

    const csvColumns = RankingsV3Model.buildCsvColumns();

    // Build CSV content
    const headers = csvColumns.map(c => c.label);
    const csvRows = [headers.join(",")];

    for (const row of currentEnriched) {
        const vals = csvColumns.map(col => {
            if (col.key === "_rank") return rankMap.get(row) ?? "";
            if (col.key === "is_unique") return row.is_unique ? "Yes" : "No";
            if (col.key === "line_slug") return LINE_LABELS[row.line_slug] || row.line_slug || "";
            const v = row[col.key];
            if (v === undefined || v === null || v <= -999) return "";
            if (typeof v === "string") {
                return `"${v.replace(/"/g, '""')}"`;
            }
            return typeof v === "number" ? v : v;
        });
        csvRows.push(vals.join(","));
    }

    // Trigger download
    const csvContent = csvRows.join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const lineName = currentLine || "units";
    const age = currentAge.toLowerCase();
    a.href = url;
    a.download = `${lineName}_${age}_rankings.csv`;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
    } catch (err) {
        console.error("exportCSV error:", err);
        alert("CSV export failed: " + err.message);
    }
}

// ===== INIT =====
Object.assign(window, {selectLine, renderTable, sortBy, toggleLine, toggleGroup, expandAll, collapseAll, exportCSV,
    onScoreMethodInfoClick, onScoreCellEnter, onScoreCellLeave, onScoreCellClick, onStatCellEnter, onStatCellLeave, onStatCellClick});
function renderLineSelector() {document.getElementById("lineSelector").innerHTML = buildLineSelector(currentLine,currentAge,config.media);}
renderLineSelector();

/* ---- Deep-link boot: /units?line=<line>&unit=<slug> ----
   Selects the tab from the URL and highlights + scrolls to the unit's rows.
   Falls back to the default tab for missing/unknown params. */
async function initFromURL() {
    const params = new URLSearchParams(window.location.search);
    const requestedLine = params.get("line");
    const lineParam = ({shock_infantry: "militia", elephant: "knight", steppe_lancer: "knight"})[requestedLine] || requestedLine;
    const unitParam = params.get("unit");
    // Valid deep-link lines: the 5 group tabs, their sub-lines (dedicated
    // filtered tables without a tab of their own), and mangonel (backend-only
    // line absent from the JS tab structure).
    const validLines = new Set(Object.keys(UNIT_LINES));
    Object.values(UNIT_LINES).forEach(function (l) {
        (l.subLines || []).forEach(function (x) { validLines.add(x); });
    });
    validLines.add("mangonel");
    const startLine = (lineParam && validLines.has(lineParam)) ? lineParam : "infantry";
    await selectLine(startLine);
    if (unitParam) {
        highlightUnitRows(unitParam);
        // selectLine's URL sync drops &unit=; restore it so the landed
        // deep link stays shareable as-is.
        if (window.history && history.replaceState) {
            const url = new URL(location.href);
            url.searchParams.set("line", startLine); url.searchParams.set("unit", unitParam);
            history.replaceState(null, "", url.pathname + url.search);
        }
    }
}
initFromURL();
window.addEventListener("popstate", initFromURL);

function highlightUnitRows(unitSlug) {
    const want = unitSlug.toLowerCase();
    let first = null;
    document.querySelectorAll("#tableContainer tr[data-unit-slug]").forEach(function (tr) {
        const s = (tr.dataset.unitSlug || "").toLowerCase();
        if (s === want || s === "elite_" + want || s.indexOf(want) !== -1) {
            tr.classList.add("row-deeplink-highlight");
            if (!first) first = tr;
        }
    });
    if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
}
