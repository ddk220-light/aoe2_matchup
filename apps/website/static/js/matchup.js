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

/* Player-facing tier ladder (best -> worst). The backend stamps `unit.tier`;
   these supply the human label + a one-line hint for the tooltip. Border edges
   and pill colours are driven by the .is-tier-<tier> / .tier-<tier> CSS classes
   (theme-aware design tokens), so colour follows the theme. See best_units.py
   (_classify_tier) for how each tier's limits are set per unit line. */
const TIER_META = {
    signature:   { label: "Signature",   hint: "Civ-defining: clearly the best version of this unit, and part of the civ's identity." },
    good:        { label: "Good",        hint: "A clearly above-average version of this unit." },
    generic:     { label: "Generic",     hint: "A standard version — the same as most civs, nothing special." },
    bad:         { label: "Bad",         hint: "A clearly below-average version of this unit." },
    situational: { label: "Situational", hint: "Weak overall, but still worth building for its niche (countering a specific unit)." },
    worst:       { label: "Worst",       hint: "Among the weakest in the game — this civ effectively never builds it." },
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
        resetPinnedTooltips();
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
    resetPinnedTooltips();
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
    var html = '';

    /* Hero: emblem + name + strategic description side-by-side */
    html += '<div class="analysis-hero">';
    html += '<img src="' + emblemUrl + '" class="analysis-emblem" alt="' + escapeHtml(civName) + '">';
    html += '<div class="analysis-hero-body">';
    html += '<h2 class="analysis-civ-name">' + escapeHtml(civName) + '</h2>';
    html += renderStrategicSummaryInline(summary, strategicDescription);
    html += '</div>';
    html += '</div>';

    /* Role columns grid — uniform columns; only the lines/columns this civ
       actually has are rendered. Strength is shown per-unit, not per-column. */
    html += '<div class="role-columns">';

    for (var i = 0; i < COLUMN_ORDER.length; i++) {
        var colKey = COLUMN_ORDER[i];
        var lineSlugs = COLUMN_DEFS[colKey];
        var colData = powerUnits[colKey] || {};
        var colLabel = COLUMN_LABELS[colKey];

        /* Build only the lines that are present for this civ. A line the civ
           lacks is skipped entirely (no "\u2014" placeholder). */
        var linesHtml = '';
        for (var j = 0; j < lineSlugs.length; j++) {
            var lineSlug = lineSlugs[j];
            var lineEntries = colData[lineSlug];
            if (!lineEntries || lineEntries.length === 0) continue;

            var lineName = LINE_NAMES[lineSlug] || slugToName(lineSlug);
            linesHtml += '<div class="line-section">';
            linesHtml += '<div class="line-label">' + escapeHtml(lineName) + '</div>';

            var isMulti = lineEntries.length > 1;
            linesHtml += '<div class="unit-wrap' + (isMulti ? ' multi-unit' : '') + '">';
            for (var u = 0; u < lineEntries.length; u++) {
                linesHtml += renderUnitBadge(lineEntries[u], colKey);
            }
            linesHtml += '</div>';
            linesHtml += '</div>';
        }

        /* A column with nothing in it for this civ is dropped altogether. */
        if (!linesHtml) continue;

        html += '<div class="role-column">';
        html += '<div class="role-header">' + escapeHtml(colLabel) + '</div>';
        html += linesHtml;
        html += '</div>';
    }

    html += '</div>'; /* end role-columns */
    return html;
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

    var html = '<div class="' + badgeClass + '">';

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

/* ---- Tooltip renderer ---- */
function renderTooltip(unit, name) {
    var bonusAbilities = unit.bonus_abilities || [];
    var specialEffects = unit.special_effects || [];
    var missingTechs = unit.missing_techs || [];
    var meta = TIER_META[unit.tier] || null;

    /* Only show tooltip if there is a tier, special info, or a score */
    var hasContent = meta || bonusAbilities.length > 0 || specialEffects.length > 0 || missingTechs.length > 0 || unit.score != null;
    if (!hasContent) return "";

    var html = '<div class="unit-badge-tooltip">';

    /* Close button — only visible when the tooltip is tap-pinned / shown as a
       bottom-sheet on touch (CSS hides it for the desktop hover bubble). */
    html += '<button type="button" class="unit-badge-tooltip-close" aria-label="Close">×</button>';

    /* Tier header: the label + what it means for this unit line */
    if (meta) {
        html += '<div class="tooltip-tier tier-' + unit.tier + '">' + meta.label + '</div>';
        html += '<div class="tooltip-tier-hint">' + escapeHtml(meta.hint) + '</div>';
    }

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

/* ==========================================================================
   Tap-to-pin tooltips (touch + viewport-safe)
   The unit tooltips are CSS hover bubbles on desktop, but hover doesn't exist
   on touch, so the breakdown is unreachable there. This adds a tap/click that
   pins a badge's tooltip (toggling a `.pinned` class the CSS reveals), with a
   visible × close, outside-tap / Escape dismiss, and a dimmed backdrop that on
   phones (<=480px, where the pinned tooltip becomes a bottom-sheet) gives a
   tap-target to close it. Only one tooltip is pinned at a time.
   Uses event delegation on #results so it survives every re-render.
   ========================================================================== */
(function () {
    if (!resultsEl) return;

    var PHONE_MQ = window.matchMedia ? window.matchMedia("(max-width: 480px)") : null;
    var pinnedTooltip = null;
    var backdrop = null;

    function ensureBackdrop() {
        if (backdrop) return backdrop;
        backdrop = document.createElement("div");
        backdrop.className = "unit-tooltip-backdrop";
        backdrop.addEventListener("click", unpin);
        document.body.appendChild(backdrop);
        return backdrop;
    }

    function isPhone() {
        return PHONE_MQ ? PHONE_MQ.matches : window.innerWidth <= 480;
    }

    function unpin() {
        if (pinnedTooltip) {
            pinnedTooltip.classList.remove("pinned");
            pinnedTooltip = null;
        }
        if (backdrop) backdrop.classList.remove("active");
    }

    function pin(tooltip) {
        if (pinnedTooltip === tooltip) {
            unpin();
            return;
        }
        unpin();
        tooltip.classList.add("pinned");
        pinnedTooltip = tooltip;
        /* Phone bottom-sheet gets a dimmed backdrop to tap-dismiss. */
        if (isPhone()) {
            ensureBackdrop().classList.add("active");
        }
    }

    /* Tap / click on a badge toggles its pinned tooltip. */
    resultsEl.addEventListener("click", function (e) {
        /* Close button inside a pinned tooltip. */
        if (e.target.closest(".unit-badge-tooltip-close")) {
            e.preventDefault();
            e.stopPropagation();
            unpin();
            return;
        }

        var badge = e.target.closest(".unit-badge");
        if (!badge) return;

        var tooltip = badge.querySelector(".unit-badge-tooltip");
        if (!tooltip) return; /* badge with no special info -> no tooltip */

        /* Don't swallow taps that land inside an already-pinned tooltip
           (e.g. selecting text or scrolling the sheet). */
        if (pinnedTooltip === tooltip && e.target.closest(".unit-badge-tooltip")) {
            return;
        }

        e.stopPropagation();
        pin(tooltip);
    });

    /* Outside tap anywhere on the document dismisses the pinned tooltip. */
    document.addEventListener("click", function (e) {
        if (!pinnedTooltip) return;
        if (e.target.closest(".unit-badge-tooltip")) return; /* tap inside sheet */
        if (e.target.closest(".unit-badge")) return;         /* handled above */
        unpin();
    });

    /* Escape closes it. */
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && pinnedTooltip) unpin();
    });

    /* A re-render (selecting a different civ, or deselecting) destroys the
       pinned tooltip node; this lets those paths clear our reference + backdrop
       so nothing dangles. */
    resultsEl.addEventListener("unit-tooltip-reset", unpin);
})();

/* Fired before #results is re-rendered so the pinned-tooltip controller can
   tear down cleanly (see loadAnalysis / onCivClick). */
function resetPinnedTooltips() {
    if (resultsEl) {
        resultsEl.dispatchEvent(new CustomEvent("unit-tooltip-reset"));
    }
}
