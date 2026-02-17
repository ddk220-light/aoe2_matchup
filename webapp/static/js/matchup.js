/* ==========================================================================
   AoE2 Unit Analyzer - Civ Analysis Page Logic
   Depends on: constants.js (ICON_BASE, NAME_TO_ICON, CIV_EMBLEM_BASE, getIconUrl)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- Constants ---- */
const ROLE_ORDER = ["cavalry", "ranged", "infantry", "anti_cavalry", "trash", "siege"];
const ROLE_LABELS = {
    cavalry: "Cavalry",
    ranged: "Ranged",
    infantry: "Infantry",
    anti_cavalry: "Anti-Cavalry",
    trash: "Trash",
    siege: "Siege",
};
const STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", label: "Signature" },
    strong: { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", label: "Strong" },
    average: { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", label: "Average" },
    weak: { bg: "rgba(231, 76, 60, 0.15)", text: "#e74c3c", label: "Weak" },
};

const NARRATIVES = {
    cavalry: {
        cav_all_strong: "This civ has good cavalry, and can be a good option for mobility.",
        cav_one_strong: "This civ's mobility is centered around {best_unit}.",
        cav_strong_slow: "The cavalry is strong, but lacks mobility.",
        cav_trash_only: "Mobility is only available late game with trash units.",
        cav_none: "Cavalry line is not a strong suite for this civ.",
    },
    ranged: {
        ranged_strong: "This civ has strong ranged options, so pushing a single position can be very effective.",
        ranged_one_strong: "Ranged options are limited, but {best_unit} stands out.",
        ranged_none: "Ranged units are not a strength for this civ.",
    },
    infantry: {
        inf_strong: "This civ has strong infantry that can help push with siege.",
        inf_one_strong: "Infantry options center around {best_unit} for frontline pressure.",
        inf_none: "Infantry is not a strong area for this civ.",
    },
    anti_cavalry: {
        anticav_strong: "Strong anti-cavalry options give this civ tools to shut down enemy cavalry.",
        anticav_one_strong: "{best_unit} provides solid anti-cavalry capability.",
        anticav_weak: "Anti-cavalry is a weakness \u2014 be cautious against cavalry-heavy opponents.",
    },
    trash: {
        trash_strong: "Trash units are above average, giving staying power in long games.",
        trash_weak: "Trash units are below average \u2014 gold-heavy strategies may be needed.",
    },
    siege: {
        siege_strong: "Strong siege options for pushing fortified positions.",
        siege_one_strong: "{best_unit} is a notable siege option.",
        siege_weak: "Siege is not a strength \u2014 consider alternative push strategies.",
    },
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
        var response = await fetch("/api/civ-power-units/" + encodeURIComponent(civName));
        if (!response.ok) {
            throw new Error("Failed to load " + civName + " (" + response.status + ")");
        }
        var data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        resultsEl.innerHTML = renderAnalysis(civName, data);
    } catch (e) {
        resultsEl.innerHTML = '<div class="no-data">Error: ' + escapeHtml(e.message) + '</div>';
    }
}

/* ---- Helpers ---- */
function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

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
    var civSlug = civName.toLowerCase();
    var emblemUrl = CIV_EMBLEM_BASE + civSlug + ".png";

    var html = '';

    /* Analysis header */
    html += '<div class="analysis-header">';
    html += '<img src="' + emblemUrl + '" class="analysis-emblem" alt="' + escapeHtml(civName) + '">';
    html += '<h2 class="analysis-civ-name">' + escapeHtml(civName) + '</h2>';
    html += '</div>';

    /* Role sections */
    for (var i = 0; i < ROLE_ORDER.length; i++) {
        var role = ROLE_ORDER[i];
        var roleData = powerUnits[role];
        if (!roleData) continue;

        var roleLabel = ROLE_LABELS[role] || role;
        var hasSig = roleData.has_signature;
        var sectionClass = "role-section" + (hasSig ? " has-signature" : "");

        html += '<div class="' + sectionClass + '">';

        /* Role header */
        html += '<div class="role-header">' + escapeHtml(roleLabel) + '</div>';

        /* Narrative */
        var narrativeText = getNarrative(role, roleData);
        if (narrativeText) {
            html += '<div class="role-narrative">' + escapeHtml(narrativeText) + '</div>';
        }

        /* Unit badges */
        var allUnits = roleData.all_units || [];
        if (allUnits.length > 0) {
            html += '<div class="unit-badges">';
            for (var j = 0; j < allUnits.length; j++) {
                html += renderUnitBadge(allUnits[j]);
            }
            html += '</div>';
        }

        html += '</div>';
    }

    /* Strategic summary */
    html += renderStrategicSummary(summary);

    return html;
}

/* ---- Narrative lookup ---- */
function getNarrative(role, roleData) {
    var key = roleData.narrative_key;
    if (!key) return null;
    var templates = NARRATIVES[role];
    if (!templates) return null;
    var template = templates[key];
    if (!template) return null;

    /* Substitute {best_unit} with the display name of the best unit */
    var bestUnitName = roleData.unit_name || slugToName(roleData.best_unit || "");
    return template.replace("{best_unit}", bestUnitName);
}

/* ---- Unit badge renderer ---- */
function renderUnitBadge(unit) {
    var name = unit.unit_name || slugToName(unit.unit_slug);
    var iconUrl = getIconUrl(name);
    var strength = STRENGTH_COLORS[unit.strength] || STRENGTH_COLORS.average;
    var isSig = unit.is_signature;
    var badgeClass = "unit-badge" + (isSig ? " signature" : "");
    var iconSize = isSig ? "signature-icon" : "unit-badge-icon";

    var html = '<div class="' + badgeClass + '" style="border-color: ' + strength.text + '">';

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

    /* Name */
    html += '<span class="unit-badge-name">' + escapeHtml(name) + '</span>';

    /* Rank */
    if (unit.rank) {
        html += '<span class="unit-badge-rank" style="color: ' + strength.text + '">#' + unit.rank + ' ' + strength.label + '</span>';
    }

    html += '</div>';
    return html;
}

/* ---- Tooltip renderer ---- */
function renderTooltip(unit, name) {
    var bonusAbilities = unit.bonus_abilities || [];
    var specialEffects = unit.special_effects || [];
    var missingTechs = unit.missing_techs || [];
    var strength = STRENGTH_COLORS[unit.strength] || STRENGTH_COLORS.average;

    /* Only show tooltip if there is special info */
    var hasContent = bonusAbilities.length > 0 || specialEffects.length > 0 || missingTechs.length > 0;
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

    /* Rank line */
    if (unit.rank) {
        html += '<div class="tooltip-rank">#' + unit.rank + ' \u00b7 ' + strength.label + '</div>';
    }

    html += '</div>';
    return html;
}

/* ---- Strategic summary renderer ---- */
function renderStrategicSummary(summary) {
    if (!summary || !summary.summary_key) return "";

    var template = SUMMARY_TEMPLATES[summary.summary_key];
    if (!template) return "";

    /* Build substitution values */
    var strongAreas = summary.strong_areas || [];
    var weakAreas = summary.weak_areas || [];
    var primaryStrength = summary.primary_strength
        ? (ROLE_LABELS[summary.primary_strength] || summary.primary_strength)
        : "";

    /* Format areas list for {areas} substitution */
    var areasText = strongAreas.map(function (a) {
        return ROLE_LABELS[a] || a;
    }).join(", ");

    var narrativeText = template
        .replace("{areas}", areasText)
        .replace("{primary_strength}", primaryStrength);

    var html = '<div class="strategic-summary">';
    html += '<div class="strategic-summary-header">Strategic Identity</div>';
    html += '<div class="strategic-summary-text">' + escapeHtml(narrativeText) + '</div>';

    /* Strength pills */
    if (strongAreas.length > 0) {
        html += '<div class="pill-row">';
        html += '<span class="pill-label">Strengths:</span>';
        for (var i = 0; i < strongAreas.length; i++) {
            var label = ROLE_LABELS[strongAreas[i]] || strongAreas[i];
            html += '<span class="pill pill-strong">' + escapeHtml(label) + '</span>';
        }
        html += '</div>';
    }

    /* Weakness pills */
    if (weakAreas.length > 0) {
        html += '<div class="pill-row">';
        html += '<span class="pill-label">Weaknesses:</span>';
        for (var i = 0; i < weakAreas.length; i++) {
            var label = ROLE_LABELS[weakAreas[i]] || weakAreas[i];
            html += '<span class="pill pill-weak">' + escapeHtml(label) + '</span>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}
