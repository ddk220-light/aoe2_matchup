/* ==========================================================================
   AoE2 Unit Analyzer - Civ Analysis Page Logic
   Depends on: constants.js (ICON_BASE, NAME_TO_ICON, CIV_EMBLEM_BASE, getIconUrl)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- Constants ---- */
const COLUMN_DEFS = {
    cavalry: ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    ranged: ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    infantry: ["militia", "spear", "shock_infantry"],
    siege: ["ram", "bombard_cannon", "trebuchet", "cannon_galleon"],
    navy: ["galleon", "fire", "hulk", "demo"],
};

const COLUMN_LABELS = {
    cavalry: "Cavalry",
    ranged: "Ranged",
    infantry: "Infantry",
    siege: "Siege",
    navy: "Navy",
};

const LINE_NAMES = {
    light_cav: "Light Cavalry",
    knight: "Knight Line",
    camel: "Camel Line",
    steppe_lancer: "Steppe Lancer",
    elephant: "Battle Elephant",
    skirmisher: "Skirmisher",
    archer: "Archer Line",
    cav_archer: "Cavalry Archer",
    gunpowder: "Gunpowder",
    scorpion: "Scorpion",
    militia: "Militia Line",
    spear: "Spear Line",
    shock_infantry: "Shock Infantry",
    ram: "Rams",
    bombard_cannon: "Bombard Cannon",
    trebuchet: "Trebuchet",
    cannon_galleon: "Cannon Galleon",
    galleon: "Galleon Line",
    fire: "Fire Ship Line",
    hulk: "Hulk Line",
    demo: "Demo Ship Line",
};

const COLUMN_ORDER = ["cavalry", "ranged", "infantry", "siege", "navy"];

const STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", label: "Signature" },
    strong: { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", label: "Strong" },
    average: { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", label: "Average" },
    weak: { bg: "rgba(230, 126, 34, 0.15)", text: "#e67e22", label: "Weak" },
    poor: { bg: "rgba(231, 76, 60, 0.15)", text: "#e74c3c", label: "Poor" },
};

const SUMMARY_TEMPLATES = {
    multi_flexible: "This civ is strong across {areas}, so it can pursue flexible strategies and adapt to any opponent.",
    one_area_strong: "This civ is strongest in {primary_strength}, so it must leverage that advantage to win.",
    none_exceptional: "This civ doesn't scale exceptionally in late game. Focus on doing early damage and maintaining a lead.",
};

/* ---- DOM refs ---- */
const stepLabel = document.getElementById("step-label");
const civGrid = document.getElementById("civ-grid");
const resultsEl = document.getElementById("results");

let selectedCiv = null;

/* ---- Build civ grid ---- */
CIVS.forEach(function (name) {
    var slug = name.toLowerCase();
    var card = document.createElement("div");
    card.className = "civ-card";
    card.dataset.civ = name;
    var img = document.createElement("img");
    img.className = "civ-emblem";
    img.src = CIV_EMBLEM_BASE + slug + ".png";
    img.alt = name;
    img.loading = "lazy";
    var label = document.createElement("span");
    label.className = "civ-card-name";
    label.textContent = name;
    card.appendChild(img);
    card.appendChild(label);
    card.addEventListener("click", function () { onCivClick(name); });
    civGrid.appendChild(card);
});

/* ---- Civ click handler ---- */
function onCivClick(name) {
    if (selectedCiv === name) {
        /* Deselect */
        selectedCiv = null;
        stepLabel.textContent = "Click a civilization to analyze";
        stepLabel.className = "step-label step-civ1";
        resultsEl.className = "results-container";
        resultsEl.innerHTML = "";
    } else {
        selectedCiv = name;
        stepLabel.textContent = "Showing analysis for " + name;
        stepLabel.className = "step-label step-selected";
        loadAnalysis(name);
    }
    updateGrid();
}

function updateGrid() {
    civGrid.querySelectorAll(".civ-card").forEach(function (card) {
        var name = card.dataset.civ;
        card.classList.remove("selected-civ1", "disabled");
        if (name === selectedCiv) {
            card.classList.add("selected-civ1");
        }
    });
}

/* ---- Load analysis from API ---- */
async function loadAnalysis(civName) {
    resultsEl.className = "results-container visible";
    resultsEl.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><div>Loading analysis\u2026</div></div>';

    try {
        var data = await apiGet("/api/civ-power-units/" + encodeURIComponent(civName));
        resultsEl.innerHTML = renderAnalysis(civName, data);
    } catch (e) {
        resultsEl.innerHTML = '<div class="no-data">Error: ' + escapeHtml(e.message) + '</div>';
    }
    resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

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
    var strongColumns = summary.strong_columns || [];
    var html = '';

    /* Hero: emblem + name + strategic description side-by-side */
    html += '<div class="analysis-hero">';
    html += '<img src="' + emblemUrl + '" class="analysis-emblem" alt="' + escapeHtml(civName) + '">';
    html += '<div class="analysis-hero-body">';
    html += '<h2 class="analysis-civ-name">' + escapeHtml(civName) + '</h2>';
    html += renderStrategicSummaryInline(summary, strategicDescription);
    html += '</div>';
    html += '</div>';

    /* Role columns grid — 4 columns with per-line sections */
    html += '<div class="role-columns">';

    for (var i = 0; i < COLUMN_ORDER.length; i++) {
        var colKey = COLUMN_ORDER[i];
        var lineSlugs = COLUMN_DEFS[colKey];
        var colData = powerUnits[colKey] || {};
        var colLabel = COLUMN_LABELS[colKey];

        /* Check if column has any strong/signature line */
        var colHasSig = false;
        var colIsStrong = strongColumns.indexOf(colKey) !== -1;
        for (var k = 0; k < lineSlugs.length; k++) {
            var entries = colData[lineSlugs[k]];
            if (entries && entries.length > 0 && entries[0].is_signature) colHasSig = true;
        }

        var colClass = "role-column";
        if (colIsStrong) colClass += " col-strong";
        if (colHasSig) colClass += " has-signature";

        html += '<div class="' + colClass + '">';
        html += '<div class="role-header">' + escapeHtml(colLabel) + '</div>';

        /* Render each unit line */
        for (var j = 0; j < lineSlugs.length; j++) {
            var lineSlug = lineSlugs[j];
            var lineEntries = colData[lineSlug];
            var lineName = LINE_NAMES[lineSlug] || slugToName(lineSlug);

            html += '<div class="line-section">';
            html += '<div class="line-label">' + escapeHtml(lineName) + '</div>';

            if (lineEntries && lineEntries.length > 0) {
                var isMulti = lineEntries.length > 1;
                html += '<div class="unit-wrap' + (isMulti ? ' multi-unit' : '') + '">';
                for (var u = 0; u < lineEntries.length; u++) {
                    html += renderUnitBadge(lineEntries[u]);
                }
                html += '</div>';
            } else {
                html += '<div class="line-unavailable">\u2014</div>';
            }
            html += '</div>';
        }

        html += '</div>';
    }

    html += '</div>'; /* end role-columns */
    return html;
}

/* ---- Unit badge renderer ---- */
function renderUnitBadge(unit) {
    var name = unit.unit_name || slugToName(unit.unit_slug);
    var iconUrl = getIconUrl(name);
    var isNavy = (unit.strength === null || unit.strength === undefined) && !unit.percentile;
    var strength = STRENGTH_COLORS[unit.strength] || STRENGTH_COLORS.average;
    var isSig = unit.is_signature && !isNavy;
    var badgeClass = "unit-badge" + (isSig ? " signature" : "") + (isNavy ? " no-strength" : "");
    var iconSize = isSig ? "signature-icon" : "unit-badge-icon";

    var borderColor = isNavy ? "var(--text-muted)" : strength.text;
    var html = '<div class="' + badgeClass + '" style="border-left-color: ' + borderColor + '">';

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

    /* Info block (name + score) */
    html += '<div class="unit-badge-info">';
    html += '<span class="unit-badge-name">' + escapeHtml(name) + '</span>';
    if (unit.percentile != null) {
        html += '<span class="unit-badge-rank rank-' + (unit.strength || 'average') + '">' + unit.percentile.toFixed(0) + 'th pctl \u00b7 ' + strength.label + '</span>';
    }
    html += '</div>';

    html += '</div>';
    return html;
}

/* ---- Tooltip renderer ---- */
function renderTooltip(unit, name) {
    var bonusAbilities = unit.bonus_abilities || [];
    var specialEffects = unit.special_effects || [];
    var missingTechs = unit.missing_techs || [];
    var strength = STRENGTH_COLORS[unit.strength] || STRENGTH_COLORS.average;

    /* Only show tooltip if there is special info or a score */
    var hasContent = bonusAbilities.length > 0 || specialEffects.length > 0 || missingTechs.length > 0 || unit.score != null;
    if (!hasContent) return "";

    var html = '<div class="unit-badge-tooltip">';

    /* Green: bonus abilities */
    for (var i = 0; i < bonusAbilities.length; i++) {
        html += '<div class="tooltip-bonus">\u2726 ' + escapeHtml(bonusAbilities[i]) + '</div>';
    }

    /* Green: special effects */
    for (var i = 0; i < specialEffects.length; i++) {
        html += '<div class="tooltip-bonus">\u2726 ' + escapeHtml(specialEffects[i]) + '</div>';
    }

    /* Red: missing techs */
    for (var i = 0; i < missingTechs.length; i++) {
        html += '<div class="tooltip-missing">\u2717 Missing: ' + escapeHtml(missingTechs[i]) + '</div>';
    }

    /* Score line */
    if (unit.score != null) {
        html += '<div class="tooltip-rank">Score: ' + unit.score.toFixed(1) + ' \u00b7 ' + strength.label + '</div>';
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
