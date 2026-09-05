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
    siege: ["ram", "mangonel", "bombard_cannon", "trebuchet", "cannon_galleon"],
    navy: ["galleon", "fire", "hulk", "demo"],
};

const BUILDING_LABELS = {
    barracks: "Barracks",
    archery_range: "Archery Range",
    stable: "Stable",
    castle: "Castle",
    siege_workshop: "Siege Workshop",
    dock: "Dock",
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
    mangonel: "Mangonel Line",
    bombard_cannon: "Bombard Cannon",
    trebuchet: "Trebuchet",
    cannon_galleon: "Cannon Galleon",
    galleon: "Galleon Line",
    fire: "Fire Ship Line",
    hulk: "Hulk Line",
    demo: "Demo Ship Line",
};

const COLUMN_ORDER = ["cavalry", "ranged", "infantry", "siege", "navy"];
const BUILDING_ORDER_CIV = [
    "barracks", "archery_range", "stable", "castle", "siege_workshop", "dock"
];

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
const civilizationData = import("./shared/page-data.js").then(m => m.createPageData());

/* ---- Build/enhance civ grid ----
   The template supplies real links so the picker remains useful without JS and
   search engines can discover each civilization without a duplicate summary.
   JS enhances those links into the in-page selector. */
CIVS.forEach(function (name) {
    var slug = name.toLowerCase();
    var card = Array.from(civGrid.querySelectorAll(".civ-card")).find(function (candidate) {
        return candidate.dataset.civ === name;
    });
    if (!card) {
        card = document.createElement("a");
        card.className = "civ-card";
        card.dataset.civ = name;
        card.href = "/civilizations/" + slug;
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
        civGrid.appendChild(card);
    }
    card.addEventListener("click", function (event) {
        event.preventDefault();
        onCivClick(name);
    });
});

/* ---- Per-civ landing page preselect (set by civ_detail.html) ---- */
if (window.PRESELECT_CIV && CIVS.indexOf(window.PRESELECT_CIV) !== -1) {
    onCivClick(window.PRESELECT_CIV);
}

/* ---- Civ click handler ---- */
function onCivClick(name) {
    if (selectedCiv === name) {
        /* Keep the selected analysis open; a second tap is a convenient way to
           return to it after browsing the picker at the bottom of the page. */
        resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
    } else {
        selectedCiv = name;
        stepLabel.textContent = "Choose another civilization";
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
            card.setAttribute("aria-current", "page");
        } else {
            card.removeAttribute("aria-current");
        }
    });
}

/* ---- Load analysis from API ---- */
async function loadAnalysis(civName) {
    resetPinnedTooltips();
    resultsEl.className = "results-container visible";
    const bootstrap = window.CIV_ANALYSIS?.civ_name === civName ? window.CIV_ANALYSIS : null;
    if (!bootstrap) resultsEl.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><div>Loading analysis…</div></div>';

    try {
        var data = await (await civilizationData).select("/api/civ-power-units/" + encodeURIComponent(civName), bootstrap);
        if (!data || selectedCiv !== civName) return;
        resultsEl.innerHTML = renderAnalysis(civName, data);
    } catch (e) {
        if (e.name === "AbortError" || selectedCiv !== civName) return;
        resultsEl.innerHTML = '<div class="no-data">Error: ' + escapeHtml(e.message) + '</div>';
    }
    resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ==========================================================================
   Tap-to-pin tooltips (touch + viewport-safe)
   The unit tooltips are CSS hover bubbles on desktop, but hover doesn't exist
   on touch, so the breakdown is unreachable there. This adds a tap/click that
   pins a badge's tooltip (toggling a `.pinned` class the CSS reveals), with a
   visible × close and outside-tap / Escape dismiss. Only one tooltip is pinned
   at a time. To focus the selection we highlight the pinned card and fade the
   rest (a `.tooltip-focus` class on #results) rather than laying a full-screen
   overlay over the cards — the results grid sits inside transformed containers
   (animation wrappers), so an overlay would paint on top of and dim the very
   card it's meant to spotlight, and swallow taps on the open sheet.
   Uses event delegation on #results so it survives every re-render.
   ========================================================================== */
(function () {
    if (!resultsEl) return;

    var pinnedTooltip = null;
    var pinnedBadge = null;

    function unpin() {
        if (pinnedTooltip) {
            pinnedTooltip.classList.remove("pinned");
            pinnedTooltip = null;
        }
        if (pinnedBadge) {
            pinnedBadge.classList.remove("tooltip-pinned");
            pinnedBadge = null;
        }
        resultsEl.classList.remove("tooltip-focus");
    }

    function pin(tooltip) {
        if (pinnedTooltip === tooltip) {
            unpin();
            return;
        }
        unpin();
        tooltip.classList.add("pinned");
        pinnedTooltip = tooltip;
        /* Highlight the owning card and fade the rest so the selected unit
           stands out instead of every card looking the same (or dimmed). */
        pinnedBadge = tooltip.closest(".unit-badge");
        if (pinnedBadge) pinnedBadge.classList.add("tooltip-pinned");
        resultsEl.classList.add("tooltip-focus");
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
       pinned tooltip node; this lets those paths clear our reference + focus
       state so nothing dangles. */
    resultsEl.addEventListener("unit-tooltip-reset", unpin);
})();

/* Fired before #results is re-rendered so the pinned-tooltip controller can
   tear down cleanly (see loadAnalysis / onCivClick). */
function resetPinnedTooltips() {
    if (resultsEl) {
        resultsEl.dispatchEvent(new CustomEvent("unit-tooltip-reset"));
    }
}
