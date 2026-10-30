// Adapted from the currently deployed rankings.js. SSR and browser use the same renderer, stable sort and row projection.
import {RankingsV3Model} from "./model.mjs";
const UNIT_LINES = {
    infantry: {
        name: "Infantry Effectiveness",
        shortName: "Infantry",
        building: "Barracks",
        castle: "Long Swordsman",
        imperial: "Champion",
        hasUnique: true,
        subLines: ["militia", "spear"],
    },
    archery: {
        name: "Ranged Effectiveness",
        shortName: "Ranged",
        building: "Archery Range",
        castle: "Crossbowman",
        imperial: "Arbalester",
        hasUnique: true,
        subLines: ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"],
    },
    stable: {
        name: "Stable Effectiveness",
        shortName: "Stable",
        building: "Stable",
        castle: "Knight",
        imperial: "Paladin",
        hasUnique: true,
        subLines: ["knight", "light_cav", "camel"],
    },
    siege: {
        name: "Anti-Building Effectiveness",
        shortName: "Siege",
        building: "Siege Workshop",
        castle: "Battering Ram",
        imperial: "Trebuchet",
        hasUnique: true,
        subLines: ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"],
    },
    naval: {
        name: "Naval Effectiveness",
        shortName: "Naval",
        building: "Dock",
        castle: "War Galley",
        imperial: "Galleon",
        hasUnique: true,
        subLines: ["galleon", "fire", "hulk"],
    },
};

function compactProgressiveBonuses(bonuses) {
    const parsed = (Array.isArray(bonuses) ? bonuses : []).map((value, index) => {
        const text = String(value);
        const match = text.match(/^(.*?)([+\-\u2212]\s*\d+(?:\.\d+)?)%(.*)$/);
        if (!match) return { text, index, progressionKey: null };

        const normalize = (part) =>
            part.trim().toLowerCase().replace(/\s+/g, " ");
        return {
            text,
            index,
            progressionKey: `${normalize(match[1])}|%|${normalize(match[3])}`,
        };
    });
    const finalIndexByProgression = new Map();
    parsed.forEach((item) => {
        if (item.progressionKey) {
            finalIndexByProgression.set(item.progressionKey, item.index);
        }
    });
    return parsed
        .filter(
            (item) =>
                !item.progressionKey ||
                finalIndexByProgression.get(item.progressionKey) === item.index,
        )
        .map((item) => item.text);
}

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
    "ac_30v30_vs_paladin",
    "ac_3k_vs_paladin",
    "anti_trash",
    "at_30v30_vs_halb",
    "at_30v30_vs_hussar",
    "at_30v30_vs_elite_skirm",
    "at_3k_vs_halb",
    "at_3k_vs_hussar",
    "at_3k_vs_elite_skirm",
    // Archery scores
    "ranged_effectiveness",
    "anti_archer",
    "aa_30v30_vs_arb",
    "aa_3k_vs_arb",
    // Stable scores
    "stable_effectiveness",
    // Siege scores
    "anti_building_score",
    "ab_persian_5u_ttk",   "ab_persian_5k_ttk",
    "ab_teuton_5u_ttk",    "ab_teuton_5k_ttk",
    "ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
    "ab_persian_5u_dmg",   "ab_persian_5k_dmg",
    "ab_teuton_5u_dmg",    "ab_teuton_5k_dmg",
    "ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
    // Naval scores
    "naval_effectiveness",
    "vs_galleon",
    "vs_fire",
    "ranking_score",
    "vs_hulk",
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
    galleon: "Galleon",
    fire: "Fire Ship",
    hulk: "Hulk",
    cannon_galleon: "Cannon Galleon",
};

function rankingRowKey(row) {
    return encodeURIComponent(
        `${row.civ_name || ""}::${row.unit_slug || row.unit_name || ""}`,
    );
}


const CIV_EMBLEM_BASE = "https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/";
export function escapeHtml(value) {return String(value).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
export function mediaHelpers(media) {return {
    hasSprite: name => Boolean(media[name]?.sprite), spriteFor: name => media[name]?.sprite || media[name]?.icon || "",
    unitIconUrl: name => media[name]?.icon || "", animFor: name => media[name]?.animation || null
};}
export {UNIT_LINES, LINE_LABELS, SCORE_KEYS, STAT_KEYS, rankingRowKey, compactProgressiveBonuses};
export function buildLineSelector(currentLine, currentAge="Imperial", media={}) {
    const {hasSprite, spriteFor, unitIconUrl} = mediaHelpers(media);
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
        const tabName = displayName || line.imperial;
        // Transparent in-game sprite when available; spriteless units (naval) keep the
        // small boxed portrait. The `sprite` class drives the no-crop CSS path.
        const tabUseSprite = typeof hasSprite === "function" && hasSprite(tabName);
        const iUrl = tabUseSprite ? spriteFor(tabName) : unitIconUrl(tabName);
        const tabImgClass = tabUseSprite ? "sprite" : "";
        const activeClass =
            currentLine === slug ? " active" : "";
        const unavailClass = unavailable ? " unavailable" : "";

        html += `<button class="unit-tab${activeClass}${unavailClass}" onclick="selectLine('${slug}')" aria-label="${line.name}" title="${line.name}">
            <img width="36" height="36" class="${tabImgClass}" src="${iUrl}" alt="${line.name}" data-anim-name="${tabName}" onerror="this.style.display='none'" />
            <span class="unit-tab-label unit-tab-label-desktop">${line.name}</span>
            <span class="unit-tab-label unit-tab-label-mobile">${line.shortName}</span>
        </button>`;
    }
    html += '</div>';
    return html;
}

export function buildTable({currentData, currentLine, currentAge="Imperial", sortColumn="ranking_score", sortDir="desc",
    enabledLines=new Set(), expandedGroups=new Set(), selectedRankingRowKey=null, civFilter="", media={}}) {
    const {hasSprite, spriteFor, unitIconUrl, animFor} = mediaHelpers(media);
    const isExpanded = group => expandedGroups.has(group);
    if (!currentData) {
        return {html:"", rows:[]};
    }

    const ageKey = currentAge === "Castle" ? "castle" : "imperial";
    const rows = currentData[ageKey] || [];

    if (rows.length === 0) {
        return {html:`<p style="color:var(--text-muted);text-align:center;padding:20px;">No units available in ${currentAge} Age for this line.</p>`, rows:[]};
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
        return RankingsV3Model.enrichRankingFields({
            ...r,
            dps,
            armor_combined: `${r.final_melee_armor || 0}/${r.final_pierce_armor || 0}`,
            armor_sort_key: r.final_melee_armor || 0,
            total_cost: totalCost,
            total_upgrade_cost:
                (r.upgrade_cost_food || 0) +
                (r.upgrade_cost_wood || 0) +
                (r.upgrade_cost_gold || 0),
        });
    });

    // Apply civ filter
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

    // Sort. Missing/sentinel values (undefined, null, -999) always sink to the
    // bottom regardless of direction — JS's `undefined < x` and `undefined > x`
    // both yield false, so without explicit handling they fix unsortable rows
    // in their original positions and corrupt the rest of the order.
    const _isMissing = (v) =>
        v === undefined || v === null || v === -999;
    filtered.sort((a, b) => {
        const sortKey = sortColumn === "armor_combined" ? "armor_sort_key" : sortColumn;
        let va = a[sortKey],
            vb = b[sortKey];
        const aMissing = _isMissing(va);
        const bMissing = _isMissing(vb);
        if (aMissing && bMissing) {
            if (a.is_unique !== b.is_unique)
                return a.is_unique ? 1 : -1;
            return 0;
        }
        if (aMissing) return 1;
        if (bMissing) return -1;
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


    // Compute medians for the uniform score + stat columns.
    const statCols = [
        "ranking_score",
        "ranking_median_delta",
        "total_cost",
        "dps",
        "final_hp",
        "final_attack",
        "final_speed",
        "final_range",
    ];

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

    const LOWER_IS_BETTER = new Set([]);
    function valClass(col, val) {
        const med = medians[col];
        if (med === undefined || val === med) return "";
        if (LOWER_IS_BETTER.has(col)) {
            return val < med ? "val-high" : "val-low";
        }
        return val > med ? "val-high" : "val-low";
    }

    const showLine = Boolean(UNIT_LINES[currentLine]?.subLines?.length);
    const columns = RankingsV3Model.buildTableColumns({ showLine });

    // Mobile deliberately presents one decision-focused view of every category:
    // unit identity, the category's primary score, and its special mechanics.
    // The desktop column model remains unchanged; these tags let responsive CSS
    // collapse the same semantic table without duplicating its data.
    const mobileScoreKey = [
        "ranking_score",
        "pool_score",
        "anti_building_score",
        "naval_effectiveness",
        "pes",
    ].find((key) => columns.some((col) => col.key === key));
    for (const col of columns) {
        if (col.key === "unit_name") col.mobileColumn = "unit";
        else if (col.key === mobileScoreKey) col.mobileColumn = "score";
        else if (col.key === "special_abilities") col.mobileColumn = "special";
    }

    // Qualify only repeated generic names on mobile. Unique-unit rows carry
    // their civilization in the unit itself and do not need redundant labels.
    const unitNameCounts = new Map();
    for (const row of filtered) {
        const nameKey = String(row.unit_name || "").trim().toLowerCase();
        unitNameCounts.set(nameKey, (unitNameCounts.get(nameKey) || 0) + 1);
    }

    const lineInfo = UNIT_LINES[currentLine];
    const titleName =
        currentAge === "Castle"
            ? lineInfo?.castle || lineInfo?.imperial
            : lineInfo?.imperial;
    const titleUseSprite =
        typeof hasSprite === "function" && hasSprite(titleName);
    const titleIcon = titleUseSprite ? spriteFor(titleName) : unitIconUrl(titleName);
    const titleImgClass = titleUseSprite ? "sprite" : "";

    const allExpanded = isExpanded("Special");
    const expandBtnLabel = allExpanded ? "▾ Collapse All" : "▸ Expand All";
    const expandBtnAction = allExpanded ? "collapseAll()" : "expandAll()";

    let html = `<div class="civ-filter-wrap">
        <input type="text" id="civFilterInput" placeholder="Filter by civilization..." value="${escapeHtml(civFilter)}" oninput="renderTable()" />
        <button class="export-btn" onclick="exportCSV()" title="Export current view as CSV">Export CSV</button>
        <button class="expand-btn" onclick="${expandBtnAction}">${expandBtnLabel}</button>`;
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
        ${titleIcon ? `<img class="${titleImgClass}" src="${titleIcon}" alt="" data-anim-name="${titleName}" width="32" height="32" />` : ""}
        <span class="table-title-desktop">${currentData.line_name} — ${currentAge} Age (${filtered.length} units)</span>
        <span class="table-title-mobile">${lineInfo?.shortName || currentData.line_name}</span>
    </div>`;

    html += '<table class="stats-table"><thead><tr>';
    for (const col of columns) {
        const isSorted = sortColumn === col.key;
        const arrow = isSorted
            ? sortDir === "asc"
                ? "\u25B2"
                : "\u25BC"
            : "\u25B4";
        const infoHtml = col.mobileColumn === "score"
            ? `<button type="button" class="score-method-info" data-info-pin aria-label="How this score is calculated" aria-expanded="false" title="How this score is calculated" onclick="onScoreMethodInfoClick(event)">i</button>`
            : col.info
                ? `<span class="info-icon" title="${col.info}">\u24D8</span>`
                : "";
        let chevronHtml = "";
        if (col.expandable && !col.hiddenWhenCollapsed) {
            const expanded = isExpanded(col.expandable);
            const ch = expanded ? "▾" : "▸";
            chevronHtml = `<span class="col-chevron" onclick="event.stopPropagation();toggleGroup('${col.expandable}')" title="${expanded ? "Collapse" : "Expand"}">${ch}</span>`;
        }
        const collapsedClass = (col.hiddenWhenCollapsed && !isExpanded(col.expandable))
            ? "col-expandable collapsed"
            : (col.hiddenWhenCollapsed ? "col-expandable" : "");
        const sortedClass = isSorted ? "sorted" : "";
        const cls = [collapsedClass, sortedClass].filter(Boolean).join(" ");
        const mobileColumnAttr = col.mobileColumn
            ? ` data-mobile-column="${col.mobileColumn}"`
            : "";
        const mobileScoreLabel = col.mobileColumn === "score"
            ? '<span class="mobile-score-label">Score</span>'
            : "";
        html += `<th class="${cls}" data-column="${col.key}"${mobileColumnAttr} onclick="sortBy('${col.key}')">
            <span class="desktop-column-label">${col.label}</span>${mobileScoreLabel}${infoHtml}${chevronHtml}<span class="sort-arrow">${arrow}</span>
        </th>`;
    }
    html += "</tr></thead><tbody>";

    // Format helpers
    function fmtCell(col, row, rowIdx) {
        const k = col.key;
        const v = row[k];
        const collapsed = col.hiddenWhenCollapsed && !isExpanded(col.expandable);
        const expandableClass = col.hiddenWhenCollapsed
            ? (collapsed ? "col-expandable collapsed" : "col-expandable")
            : "";
        const mobileColumnClass = col.mobileColumn
            ? ` mobile-column mobile-column-${col.mobileColumn}`
            : "";
        if (k === "civ_name") {
            const civImg = media.civilization_emblems?.[v] || `${CIV_EMBLEM_BASE}${v.toLowerCase()}.png`;
            return `<td class="${expandableClass}${mobileColumnClass}"><div class="civ-cell">
                <img loading="lazy" decoding="async" width="20" height="20" src="${civImg}" alt="${v}" onerror="this.style.display='none'" />
                ${v}
            </div></td>`;
        }
        if (k === "unit_name") {
            const cellUseSprite =
                typeof hasSprite === "function" && hasSprite(v);
            const unitImg = cellUseSprite ? spriteFor(v) : unitIconUrl(v);
            const selectedAnimation =
                selectedRankingRowKey === rankingRowKey(row) &&
                typeof animFor === "function"
                    ? animFor(v)
                    : null;
            const displayedUnitImg = selectedAnimation || unitImg;
            const cellImgClass = cellUseSprite ? "sprite" : "";
            const nameKey = String(v || "").trim().toLowerCase();
            const needsCivQualifier = !row.is_unique && (unitNameCounts.get(nameKey) || 0) > 1;
            const civImg = media.civilization_emblems?.[row.civ_name] || `${CIV_EMBLEM_BASE}${row.civ_name.toLowerCase()}.png`;
            const civQualifier = needsCivQualifier
                ? `<span class="mobile-civ-qualifier">(<img loading="lazy" decoding="async" width="20" height="20" src="${civImg}" alt="" onerror="this.style.display='none'" />${row.civ_name})</span>`
                : "";
            return `<td class="${expandableClass}${mobileColumnClass}"><div class="unit-cell">
                <img loading="lazy" decoding="async" width="36" height="36" class="${cellImgClass}" src="${displayedUnitImg}" alt="${v}" data-anim-name="${v}" onerror="this.style.display='none'" />
                <span class="unit-cell-copy"><span class="unit-cell-name">${v}${row.is_unique ? " *" : ""}</span>${civQualifier}</span>
            </div></td>`;
        }
        if (k === "line_slug") {
            return `<td class="${expandableClass}${mobileColumnClass}">${LINE_LABELS[v] || v}</td>`;
        }
        if (k === "special_abilities") {
            const effects = v || "";
            const missing = row.missing_techs || [];
            const bonuses = compactProgressiveBonuses(row.civ_bonus_techs || []);
            const lines = [];
            const esc = (s) =>
                String(s)
                    .replace(/&/g, "&amp;")
                    .replace(/"/g, "&quot;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;");
            if (effects) {
                lines.push(
                    `<div class="special-effects" title="${esc(effects)}">${effects}</div>`,
                );
            }
            if (bonuses.length > 0) {
                const text = bonuses.join(", ");
                lines.push(
                    `<div class="special-bonuses" title="${esc("\u2728 " + text)}">\u2728 ${text}</div>`,
                );
            }
            if (missing.length > 0) {
                const text = missing.join(", ");
                lines.push(
                    `<div class="special-missing" title="${esc("\u274c Missing: " + text)}">\u274c Missing: ${text}</div>`,
                );
            }
            if (lines.length === 0) lines.push("\u2014");
            return `<td class="special-cell ${expandableClass}${mobileColumnClass}">${lines.join("")}</td>`;
        }
        if (k.startsWith("role_line_")) {
            if (v === undefined || v === null) return `<td class="${expandableClass}">\u2014</td>`;
            return `<td class="${expandableClass}">${v.toFixed(1)}</td>`;
        }
        if (k === "armor_combined") {
            return `<td class="${expandableClass}">${v}</td>`;
        }
        // Numeric columns with color coding
        if (v === undefined || v === null || v <= -999) {
            return `<td class="${expandableClass}${mobileColumnClass}">\u2014</td>`;
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
            return `<td class="${cls}${hcClass} ${expandableClass}${mobileColumnClass}" onmouseenter="onScoreCellEnter(event,${rowIdx},'${k}')" onmouseleave="onScoreCellLeave()" onclick="onScoreCellClick(event,${rowIdx},'${k}')">${formatted}</td>`;
        }
        if (isStat) {
            return `<td class="${cls}${hcClass} ${expandableClass}${mobileColumnClass}" onmouseenter="onStatCellEnter(event,${rowIdx},'${k}')" onmouseleave="onStatCellLeave()" onclick="onStatCellClick(event,${rowIdx},'${k}')">${formatted}</td>`;
        }
        return `<td class="${cls} ${expandableClass}${mobileColumnClass}">${formatted}</td>`;
    }

    for (let i = 0; i < filtered.length; i++) {
        const row = filtered[i];
        const rowKey = rankingRowKey(row);
        const rowClasses = [
            row.is_unique ? "unique-row" : "",
            selectedRankingRowKey === rowKey ? "ranking-row-selected" : "",
        ].filter(Boolean).join(" ");
        html += `<tr class="${rowClasses}" data-unit-slug="${(row.unit_slug || "")}" data-ranking-key="${rowKey}" tabindex="0" aria-selected="${selectedRankingRowKey === rowKey}">`;
        for (const col of columns) {
            html += fmtCell(col, row, i);
        }
        html += "</tr>";
    }

    html += "</tbody></table>";
    return {html, rows:filtered};

}
