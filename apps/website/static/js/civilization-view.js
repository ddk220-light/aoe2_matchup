/* ---- Helpers ---- */
// escapeHtml is provided globally by constants.js.

function slugToName(slug) {
    if (!slug) return "";
    return slug.split("_").map(function (w) {
        return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(" ");
}

/* ---- Main render ---- */
function renderAnalysis(civName, data) {
    var powerUnits = data.power_units || {};
    var summary = data.strategic_summary || {};
    var strategicDescription = data.strategic_description || "";
    var civSlug = civName.toLowerCase();
    var emblemUrl = CIV_EMBLEM_BASE + civSlug + ".png";
    var html = '';

    /* Hero: emblem + name + strategic description side-by-side */
    html += '<div class="analysis-hero">';
    html += '<img src="' + emblemUrl + '" class="analysis-emblem" alt="' + escapeHtml(civName) + '">';
    html += '<div class="analysis-hero-body">';
    html += '<h2 class="analysis-civ-name">' + escapeHtml(civName) + '</h2>';
    html += renderStrategicSummaryInline(summary, strategicDescription);
    html += renderCivDeepLinks(civName);
    html += '</div>';
    html += '</div>';

    /* Group the available units by their production building. Generic unit
       lines map directly to their normal building; unique units default to the
       Castle unless constants.js records an explicit alternate building. */
    var buildings = groupUnitsByBuilding(powerUnits);

    /* Building cards stay detailed on desktop and become compact, tappable
       unit grids on mobile. */
    html += '<div class="role-columns">';
    for (var i = 0; i < BUILDING_ORDER_CIV.length; i++) {
        var buildingKey = BUILDING_ORDER_CIV[i];
        var buildingUnits = buildings[buildingKey] || [];
        if (!buildingUnits.length) continue;
        html += '<div class="role-column">';
        html += '<div class="role-header">' + escapeHtml(BUILDING_LABELS[buildingKey]) + '</div>';
        html += '<div class="building-unit-grid">';
        for (var u = 0; u < buildingUnits.length; u++) {
            html += renderUnitBadge(buildingUnits[u].unit, buildingUnits[u].column);
        }
        html += '</div>';
        html += '</div>';
    }

    html += '</div>'; /* end role-columns */
    return html;
}

function renderCivDeepLinks(civName) {
    var encodedCiv = encodeURIComponent(civName);
    var wikiCiv = encodeURIComponent(civName.replace(/ /g, "_"));
    var techTreeUrl = "https://aoe2techtree.net/#" + encodedCiv;
    var wikiUrl = "https://ageofempires.fandom.com/wiki/" + wikiCiv;
    return '<div class="civ-deep-links" aria-label="More about ' + escapeHtml(civName) + '">'
        + '<a class="civ-deep-link" href="' + techTreeUrl + '" target="_blank" rel="nofollow noopener">'
        + 'Open Tech Tree <span aria-hidden="true">↗</span></a>'
        + '<a class="civ-deep-link" href="' + wikiUrl + '" target="_blank" rel="nofollow noopener">'
        + 'Open Wiki <span aria-hidden="true">↗</span></a>'
        + '</div>';
}

function buildingForUnit(unit, column, lineSlug) {
    var name = unit.unit_name || slugToName(unit.unit_slug);
    if (unit.is_unique) {
        var override = (typeof UNIQUE_BUILDING !== "undefined") ? UNIQUE_BUILDING[name] : null;
        if (override) return override.toLowerCase().replace(/ /g, "_");
        if (column === "navy" || lineSlug === "cannon_galleon") return "dock";
        return "castle";
    }
    if (column === "infantry") return "barracks";
    if (column === "cavalry") return "stable";
    if (column === "navy" || lineSlug === "cannon_galleon") return "dock";
    if (lineSlug === "trebuchet") return "castle";
    if (column === "siege" || lineSlug === "scorpion") return "siege_workshop";
    return "archery_range";
}

function groupUnitsByBuilding(powerUnits) {
    var grouped = {};
    for (var c = 0; c < COLUMN_ORDER.length; c++) {
        var column = COLUMN_ORDER[c];
        var lines = powerUnits[column] || {};
        var lineSlugs = Object.keys(lines);
        for (var l = 0; l < lineSlugs.length; l++) {
            var lineSlug = lineSlugs[l];
            var entries = lines[lineSlug] || [];
            for (var u = 0; u < entries.length; u++) {
                var building = buildingForUnit(entries[u], column, lineSlug);
                if (!grouped[building]) grouped[building] = [];
                grouped[building].push({ unit: entries[u], column: column });
            }
        }
    }
    return grouped;
}

/* ---- Unit badge renderer ---- */
function renderUnitBadge(unit, colKey) {
    var name = unit.unit_name || slugToName(unit.unit_slug);
    // Use the transparent in-game sprite whenever the unit has one — hasSprite() now
    // includes off-shape (tall/wide) units, not just square ones, so signature units
    // like Elite Skirmisher / Elite Leitis get the `.sprite` treatment too. Spriteless
    // units (naval) fall back to the boxed portrait. The `.sprite` class drives the CSS,
    // where a fixed box + object-fit: contain keeps every aspect ratio inside the badge.
    var useSprite = typeof hasSprite === "function" && hasSprite(name);
    var iconUrl = useSprite ? spriteFor(name) : getIconUrl(name);
    // The backend grades each unit into one of six tiers (see TIER_META). A few
    // stat-only naval/siege fallbacks carry no score and so no tier — those fall
    // back to a plain, edge-less badge.
    var tier = unit.tier || null;
    var meta = TIER_META[tier] || null;
    // Gold star / ring / enlarged icon track the Signature tier exactly, so the
    // emphasis always matches the SIGNATURE pill.
    var isSig = tier === "signature";
    // Tier edge is driven by the .is-tier-<tier> CSS class (tamed color-mix
    // tokens), not an inline neon colour — keeps it theme-aware and de-neoned.
    var badgeClass = "unit-badge" + (isSig ? " signature" : "") +
        (meta ? " is-tier-" + tier : " no-strength");
    var iconSize = (isSig ? "signature-icon" : "unit-badge-icon") + (useSprite ? " sprite" : "");

    var html = '<div class="' + badgeClass + '" data-anim-name="' + escapeHtml(name) + '">';

    /* Tooltip */
    html += renderTooltip(unit, name);

    /* Signature star */
    if (isSig) {
        html += '<span class="signature-star">\u2605</span>';
    }

    /* Icon */
    if (iconUrl) {
        html += '<img src="' + iconUrl + '" class="' + iconSize + '" alt="' + escapeHtml(name) + '" onerror="this.style.display=\'none\'">';
    } else {
        html += '<div class="' + iconSize + ' icon-placeholder"></div>';
    }

    /* Info block (name + tier) */
    html += '<div class="unit-badge-info">';
    html += '<span class="unit-badge-name">' + escapeHtml(name) + '</span>';
    if (meta) {
        html += '<span class="unit-badge-rank tier-' + tier + '">' + meta.label + '</span>';
    }
    html += '</div>';

    html += '</div>';
    return html;
}

/* Stat rows shown in the card, in display order. higherBetter drives the
   advantage/disadvantage colour vs the line baseline (lower reload = faster). */
const STAT_ROWS = [
    { key: "hp", label: "HP", higherBetter: true },
    { key: "attack", label: "Attack", higherBetter: true },
    { key: "reload_time", label: "Attack speed", higherBetter: false, suffix: "s" },
    { key: "range", label: "Range", higherBetter: true, rangedOnly: true },
    { key: "melee_armor", label: "Melee armor", higherBetter: true },
    { key: "pierce_armor", label: "Pierce armor", higherBetter: true },
];

function fmtStat(v, suffix) {
    if (v == null) return "—";
    /* whole numbers stay integers; reload-style values keep one decimal */
    var s = (Math.abs(v - Math.round(v)) < 0.05) ? String(Math.round(v)) : v.toFixed(1);
    return suffix ? s + suffix : s;
}

/* One stat row, with an advantage/disadvantage marker vs the generic baseline.
   When `baseline` is null (unique units — nothing to compare) only the value shows. */
function renderStatRow(row, stats, baseline) {
    var val = stats[row.key];
    if (val == null) return "";
    var cmp = "";
    var base = baseline ? baseline[row.key] : null;
    if (base != null && Math.abs(val - base) >= 0.05) {
        var better = row.higherBetter ? (val > base) : (val < base);
        cmp = '<span class="tt-stat-cmp ' + (better ? "tt-better" : "tt-worse") + '">'
            + (better ? "▲" : "▼")
            + ' <span class="tt-stat-base">vs ' + fmtStat(base, row.suffix) + '</span></span>';
    }
    return '<div class="tt-stat-row">'
        + '<span class="tt-stat-label">' + row.label + '</span>'
        + '<span class="tt-stat-val">' + fmtStat(val, row.suffix) + '</span>'
        + cmp + '</div>';
}

/* ---- Tooltip renderer ---- */
function renderTooltip(unit, name) {
    var bonusAbilities = unit.bonus_abilities || [];
    var specialEffects = unit.special_effects || [];
    var missingTechs = unit.missing_techs || [];
    var meta = TIER_META[unit.tier] || null;
    var stats = unit.stats || null;
    var isUnique = !!unit.is_unique;
    /* Generic units compare against the line's typical fully-upgraded version;
       unique units have no shared counterpart, so no baseline / "missing". */
    var baseline = (!isUnique && unit.stat_baseline) ? unit.stat_baseline : null;

    var hasContent = meta || stats || bonusAbilities.length || specialEffects.length
        || missingTechs.length || unit.score != null;
    if (!hasContent) return "";

    var useSprite = typeof hasSprite === "function" && hasSprite(name);
    var iconUrl = useSprite ? spriteFor(name) : getIconUrl(name);

    var html = '<div class="unit-badge-tooltip">';

    /* Close button — only visible when the tooltip is tap-pinned / shown as a
       bottom-sheet on touch (CSS hides it for the desktop hover bubble). */
    html += '<button type="button" class="unit-badge-tooltip-close" aria-label="Close">×</button>';

    /* Header: big icon + name + tier. The high-res unit sprite gets the large
       treatment; the fallback game icon stays smaller so it isn't upscaled. */
    html += '<div class="tt-head' + (useSprite ? ' tt-head--sprite' : '') + '">';
    html += '<img class="tt-icon anim-slot' + (useSprite ? ' tt-icon--sprite' : '') + '" src="' + iconUrl
        + '" alt="' + escapeHtml(name) + '" onerror="this.style.display=\'none\'">';
    html += '<div class="tt-head-text"><div class="tt-name">' + escapeHtml(name) + '</div>';
    if (meta) {
        html += '<span class="tooltip-tier tier-' + unit.tier + '">' + meta.label + '</span>';
    }
    html += '</div></div>';

    if (meta) {
        html += '<div class="tooltip-tier-hint">' + escapeHtml(meta.hint) + '</div>';
    }

    /* Stats grid (with vs-generic comparison for non-unique units). */
    if (stats) {
        var rows = "";
        for (var s = 0; s < STAT_ROWS.length; s++) {
            var srow = STAT_ROWS[s];
            if (srow.rangedOnly && !(stats.is_ranged || stats.range > 0)) continue;
            rows += renderStatRow(srow, stats, baseline);
        }
        if (rows) {
            html += '<div class="tt-stats">' + rows + '</div>';
            if (baseline) {
                html += '<div class="tt-stats-note">▲ / ▼ vs a typical fully-upgraded '
                    + (LINE_NAMES[unit.line_slug] || "unit").toLowerCase() + '</div>';
            }
        }
    }

    /* Green: bonus abilities */
    for (var i = 0; i < bonusAbilities.length; i++) {
        html += '<div class="tooltip-bonus">\u2726 ' + escapeHtml(bonusAbilities[i]) + '</div>';
    }

    /* Green: special effects */
    for (var i = 0; i < specialEffects.length; i++) {
        html += '<div class="tooltip-bonus">\u2726 ' + escapeHtml(specialEffects[i]) + '</div>';
    }

    /* Red: upgrades this civ is missing \u2014 only meaningful for shared units
       (a unique unit has no generic counterpart to fall short of). */
    if (!isUnique) {
        for (var i = 0; i < missingTechs.length; i++) {
            html += '<div class="tooltip-missing">\u2717 Missing: ' + escapeHtml(missingTechs[i]) + '</div>';
        }
    }

    /* Raw effectiveness score \u2014 a faint footer for the curious (the tier above
       is the headline; this is the underlying number it was graded from). */
    if (unit.score != null) {
        html += '<div class="tooltip-rank">Effectiveness score: ' + unit.score.toFixed(1) + ' / 100</div>';
    }

    html += '</div>';
    return html;
}

/* ---- Strategic summary renderer (inline, for hero section) ---- */
function renderStrategicSummaryInline(summary, strategicDescription) {
    if (!strategicDescription && (!summary || !summary.summary_key)) return "";

    var html = '';

    /* Main strategic description paragraph */
    if (strategicDescription) {
        html += '<div class="analysis-hero-narrative">' + escapeHtml(strategicDescription) + '</div>';
    } else {
        /* Fallback to old template if no description generated */
        var template = SUMMARY_TEMPLATES[summary.summary_key];
        if (template) {
            var strongColumns = summary.strong_columns || [];
            var primaryStrength = summary.primary_strength
                ? (COLUMN_LABELS[summary.primary_strength] || summary.primary_strength)
                : "";
            var areasText = strongColumns.map(function (a) {
                return COLUMN_LABELS[a] || a;
            }).join(", ");
            var narrativeText = template
                .replace("{areas}", areasText)
                .replace("{primary_strength}", primaryStrength);
            html += '<div class="analysis-hero-narrative">' + escapeHtml(narrativeText) + '</div>';
        }
    }

    return html;
}
