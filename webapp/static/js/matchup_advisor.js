/* ==========================================================================
   AoE2 Unit Analyzer - Matchup Advisor Logic
   Depends on: constants.js (ICON_BASE, NAME_TO_ICON, CIV_EMBLEM_BASE, getIconUrl)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- Constants ---- */
const MA_COLUMN_DEFS = {
    cavalry: ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    ranged: ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    infantry: ["militia", "spear", "shock_infantry"],
    siege: ["ram", "bombard_cannon", "trebuchet"],
};

const MA_COLUMN_LABELS = {
    cavalry: "Cavalry",
    ranged: "Ranged",
    infantry: "Infantry",
    siege: "Siege",
};

const MA_LINE_NAMES = {
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
};

const MA_COLUMN_ORDER = ["cavalry", "ranged", "infantry", "siege"];

// Siege lines only show percentile — no sim overlays.
const MA_SIEGE_LINES = new Set(["ram", "bombard_cannon", "trebuchet"]);

const MA_STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", bar: "#c9a84c" },
    strong:    { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", bar: "#2ecc71" },
    average:   { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", bar: "rgba(255,255,255,0.3)" },
    weak:      { bg: "rgba(230, 126, 34, 0.15)", text: "#e67e22", bar: "#e67e22" },
    poor:      { bg: "rgba(231, 76, 60, 0.15)", text: "#e74c3c", bar: "#e74c3c" },
};

/* ---- State ---- */
let civLeft = null;
let civRight = null;
let activeSlot = "left";
let currentAge = "imperial";
let simData = null;
let simRequestId = 0;

/* ---- DOM refs ---- */
const slotLeft = document.getElementById("slot-left");
const slotRight = document.getElementById("slot-right");
const civGrid = document.getElementById("civ-grid");
const controls = document.getElementById("controls");
const resultsEl = document.getElementById("results");

/* ---- Init ---- */
(function init() {
    buildCivGrid();
    attachSlotHandlers();
    attachAgeHandlers();
})();

function buildCivGrid() {
    civGrid.innerHTML = "";
    CIVS.forEach((name) => {
        const card = document.createElement("div");
        card.className = "ma-civ-card";
        card.dataset.civ = name;

        const img = document.createElement("img");
        img.src = CIV_EMBLEM_BASE + name.toLowerCase() + ".png";
        img.className = "ma-civ-emblem";
        img.alt = name;
        img.loading = "lazy";

        const label = document.createElement("span");
        label.className = "ma-civ-card-name";
        label.textContent = name;

        card.appendChild(img);
        card.appendChild(label);
        card.addEventListener("click", () => onCivClick(name));
        civGrid.appendChild(card);
    });
}

function attachSlotHandlers() {
    slotLeft.addEventListener("click", () => {
        if (civLeft) {
            civLeft = null;
            activeSlot = "left";
            updateUI();
            clearResults();
        } else {
            activeSlot = "left";
            updateUI();
        }
    });
    slotRight.addEventListener("click", () => {
        if (civRight) {
            civRight = null;
            activeSlot = "right";
            updateUI();
            clearResults();
        } else {
            activeSlot = "right";
            updateUI();
        }
    });
}

function attachAgeHandlers() {
    document.querySelectorAll(".ma-age-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            if (btn.dataset.age === currentAge) return;
            currentAge = btn.dataset.age;
            document.querySelectorAll(".ma-age-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            if (civLeft && civRight) loadComparison();
        });
    });
}

/* ---- Civ Selection ---- */
function onCivClick(name) {
    // Toggle off if already selected
    if (name === civLeft) {
        civLeft = null;
        activeSlot = "left";
        updateUI();
        clearResults();
        return;
    }
    if (name === civRight) {
        civRight = null;
        activeSlot = "right";
        updateUI();
        clearResults();
        return;
    }

    // Assign to active slot
    if (activeSlot === "left") {
        civLeft = name;
        activeSlot = civRight ? "left" : "right";
    } else {
        civRight = name;
        activeSlot = civLeft ? "right" : "left";
    }

    updateUI();
    if (civLeft && civRight) loadComparison();
}

function updateUI() {
    // Update slots
    renderSlot(slotLeft, civLeft, "Your Civ", "left");
    renderSlot(slotRight, civRight, "Opponent", "right");

    // Highlight active slot
    slotLeft.classList.toggle("active", activeSlot === "left" && !civLeft);
    slotRight.classList.toggle("active", activeSlot === "right" && !civRight);

    // Update grid card highlights
    civGrid.querySelectorAll(".ma-civ-card").forEach((card) => {
        card.classList.remove("selected-left", "selected-right");
        if (card.dataset.civ === civLeft) card.classList.add("selected-left");
        if (card.dataset.civ === civRight) card.classList.add("selected-right");
    });

    // Show/hide controls
    controls.style.display = (civLeft && civRight) ? "" : "none";
}

function renderSlot(slotEl, civName, placeholder, side) {
    slotEl.innerHTML = "";
    slotEl.classList.remove("filled");
    if (civName) {
        slotEl.classList.add("filled");
        const img = document.createElement("img");
        img.src = CIV_EMBLEM_BASE + civName.toLowerCase() + ".png";
        img.className = "ma-slot-emblem";
        img.alt = civName;
        const label = document.createElement("span");
        label.className = "ma-slot-name";
        label.textContent = civName;
        slotEl.appendChild(img);
        slotEl.appendChild(label);
    } else {
        const span = document.createElement("span");
        span.className = "ma-slot-placeholder";
        span.textContent = placeholder;
        slotEl.appendChild(span);
    }
}

function clearResults() {
    resultsEl.innerHTML = "";
    controls.style.display = "none";
    simData = null;
}

/* ---- Data Loading ---- */
async function loadComparison() {
    resultsEl.innerHTML = '<div class="ma-loading"><div class="spinner"></div>Loading comparison...</div>';

    try {
        const [respL, respR] = await Promise.all([
            fetch(`/api/civ-power-units/${encodeURIComponent(civLeft)}?age=${currentAge}`),
            fetch(`/api/civ-power-units/${encodeURIComponent(civRight)}?age=${currentAge}`),
        ]);

        if (!respL.ok || !respR.ok) {
            resultsEl.innerHTML = '<div class="ma-loading">Error loading data.</div>';
            return;
        }

        const dataL = await respL.json();
        const dataR = await respR.json();
        renderComparison(dataL, dataR);
        // Fire background sim fetch
        loadSims();
    } catch (e) {
        resultsEl.innerHTML = '<div class="ma-loading">Error loading data.</div>';
    }
}

async function loadSims() {
    const myId = ++simRequestId;
    try {
        const resp = await fetch("/api/matchup-sims", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                civ_left: civLeft,
                civ_right: civRight,
                age: currentAge,
            }),
        });
        if (!resp.ok || myId !== simRequestId) return;
        simData = await resp.json();
        renderSimOverlays();
    } catch (e) {
        // Silently fail — sim overlay is non-critical
    }
}

function _renderIconRow(row, slugs, labelText, labelClass, iconClass) {
    row.innerHTML = "";
    if (!slugs || slugs.length === 0) return;
    const label = document.createElement("span");
    label.className = "ma-beats-label " + labelClass;
    label.textContent = labelText;
    row.appendChild(label);

    const iconWrap = document.createElement("div");
    iconWrap.className = "ma-beats-icons";
    slugs.forEach((oppSlug) => {
        const oppName = simData.name_map[oppSlug] || oppSlug;
        const iconUrl = getIconUrl(oppName);
        if (!iconUrl) return;
        const icon = document.createElement("img");
        icon.className = "ma-beats-icon " + iconClass;
        icon.src = iconUrl;
        icon.alt = oppName;
        icon.title = oppName;
        iconWrap.appendChild(icon);
    });
    row.appendChild(iconWrap);
}

function renderSimOverlays() {
    if (!simData) return;
    // Render "Beats" row (wins both v30 + 3k)
    document.querySelectorAll(".ma-beats-row").forEach((row) => {
        const slug = row.dataset.unitSlug;
        const side = row.dataset.side;
        const sideData = simData[side];
        if (!sideData || !sideData[slug]) {
            row.innerHTML = "";
            return;
        }
        const { wins, highlighted } = sideData[slug];
        if (!wins || wins.length === 0) {
            row.innerHTML = "";
            return;
        }
        row.innerHTML = "";
        const label = document.createElement("span");
        label.className = "ma-beats-label";
        label.textContent = "Beats:";
        row.appendChild(label);

        const iconWrap = document.createElement("div");
        iconWrap.className = "ma-beats-icons";
        const highlightSet = new Set(highlighted || []);

        wins.forEach((oppSlug) => {
            const oppName = simData.name_map[oppSlug] || oppSlug;
            const iconUrl = getIconUrl(oppName);
            if (!iconUrl) return;
            const icon = document.createElement("img");
            icon.className = "ma-beats-icon";
            if (highlightSet.has(oppSlug)) {
                icon.classList.add("exclusive");
            }
            icon.src = iconUrl;
            icon.alt = oppName;
            icon.title = oppName;
            iconWrap.appendChild(icon);
        });
        row.appendChild(iconWrap);
    });

    // Render pop wins, eco wins, losses rows
    document.querySelectorAll(".ma-pop-wins-row").forEach((row) => {
        const slug = row.dataset.unitSlug;
        const side = row.dataset.side;
        const d = simData[side] && simData[side][slug];
        _renderIconRow(row, d && d.pop_wins, "Pop:", "ma-label-pop", "pop-win");
    });
    document.querySelectorAll(".ma-eco-wins-row").forEach((row) => {
        const slug = row.dataset.unitSlug;
        const side = row.dataset.side;
        const d = simData[side] && simData[side][slug];
        _renderIconRow(row, d && d.eco_wins, "Eco:", "ma-label-eco", "eco-win");
    });
    document.querySelectorAll(".ma-losses-row").forEach((row) => {
        const slug = row.dataset.unitSlug;
        const side = row.dataset.side;
        const d = simData[side] && simData[side][slug];
        _renderIconRow(row, d && d.losses, "Loses:", "ma-label-loss", "loss");
    });

    // Remove remaining spinners
    document.querySelectorAll(".ma-beats-spinner").forEach((s) => s.remove());
}

/* ---- Rendering ---- */
function renderComparison(dataL, dataR) {
    resultsEl.innerHTML = "";
    const puL = dataL.power_units || {};
    const puR = dataR.power_units || {};

    const wrapper = document.createElement("div");
    wrapper.className = "ma-sections";

    MA_COLUMN_ORDER.forEach((colKey) => {
        const section = document.createElement("div");
        section.className = "ma-section";

        const header = document.createElement("div");
        header.className = "ma-section-header";
        header.textContent = MA_COLUMN_LABELS[colKey];
        section.appendChild(header);

        const body = document.createElement("div");
        body.className = "ma-section-body";

        const lines = MA_COLUMN_DEFS[colKey];
        const colL = puL[colKey] || {};
        const colR = puR[colKey] || {};

        lines.forEach((lineSlug) => {
            const entriesL = colL[lineSlug] || null;
            const entriesR = colR[lineSlug] || null;

            // Skip if neither civ has this line
            if (!entriesL && !entriesR) return;

            const row = buildRow(lineSlug, entriesL, entriesR);
            body.appendChild(row);
        });

        section.appendChild(body);
        wrapper.appendChild(section);
    });

    resultsEl.appendChild(wrapper);
}

function buildRow(lineSlug, entriesL, entriesR) {
    const container = document.createElement("div");

    // Line label
    const label = document.createElement("span");
    label.className = "ma-row-label";
    label.textContent = MA_LINE_NAMES[lineSlug] || lineSlug;
    container.appendChild(label);

    const row = document.createElement("div");
    row.className = "ma-row";

    const topL = entriesL ? entriesL[0] : null;
    const topR = entriesR ? entriesR[0] : null;

    // Determine winner
    const pctL = topL ? topL.percentile : -1;
    const pctR = topR ? topR.percentile : -1;
    const winnerSide = pctL > pctR ? "left" : pctR > pctL ? "right" : null;

    const sideL = buildUnitSide(topL, civLeft, winnerSide === "left");
    const sideR = buildUnitSide(topR, civRight, winnerSide === "right");

    row.appendChild(sideL);
    row.appendChild(sideR);
    container.appendChild(row);

    // Extra units (if line has multiple units, e.g., unique + generic)
    const maxExtra = Math.max(
        entriesL ? entriesL.length - 1 : 0,
        entriesR ? entriesR.length - 1 : 0
    );
    for (let i = 1; i <= maxExtra; i++) {
        const extraRow = document.createElement("div");
        extraRow.className = "ma-row ma-extra-unit";
        const eL = entriesL && entriesL[i] ? entriesL[i] : null;
        const eR = entriesR && entriesR[i] ? entriesR[i] : null;
        const ePctL = eL ? eL.percentile : -1;
        const ePctR = eR ? eR.percentile : -1;
        const eWinner = ePctL > ePctR ? "left" : ePctR > ePctL ? "right" : null;
        extraRow.appendChild(buildUnitSide(eL, civLeft, eWinner === "left"));
        extraRow.appendChild(buildUnitSide(eR, civRight, eWinner === "right"));
        container.appendChild(extraRow);
    }

    return container;
}

function buildUnitSide(entry, civName, isWinner) {
    const side = document.createElement("div");
    side.className = "ma-unit-side";

    if (!entry) {
        side.classList.add("na");
        const na = document.createElement("span");
        na.className = "ma-na-text";
        na.textContent = "N/A";
        side.appendChild(na);
        return side;
    }

    if (isWinner) side.classList.add("winner");

    const sc = MA_STRENGTH_COLORS[entry.strength] || MA_STRENGTH_COLORS.average;

    // Name row: emblem + icon + name
    const nameRow = document.createElement("div");
    nameRow.className = "ma-unit-name-row";

    const emblem = document.createElement("img");
    emblem.src = CIV_EMBLEM_BASE + civName.toLowerCase() + ".png";
    emblem.className = "ma-unit-emblem";
    emblem.alt = civName;

    const icon = document.createElement("img");
    icon.className = "ma-unit-icon";
    const iconUrl = getIconUrl(entry.unit_name);
    if (iconUrl) {
        icon.src = iconUrl;
    }
    icon.alt = entry.unit_name;

    const name = document.createElement("span");
    name.className = "ma-unit-name";
    name.textContent = entry.unit_name;

    nameRow.appendChild(emblem);
    nameRow.appendChild(icon);
    nameRow.appendChild(name);
    side.appendChild(nameRow);

    // Percentile bar
    const barRow = document.createElement("div");
    barRow.className = "ma-bar-row";

    const bar = document.createElement("div");
    bar.className = "ma-bar";
    const fill = document.createElement("div");
    fill.className = "ma-bar-fill";
    fill.style.width = entry.percentile + "%";
    fill.style.background = sc.bar;
    bar.appendChild(fill);

    const pctLabel = document.createElement("span");
    pctLabel.className = "ma-percentile";
    pctLabel.style.color = sc.text;
    pctLabel.textContent = Math.round(entry.percentile) + "%";

    barRow.appendChild(bar);
    barRow.appendChild(pctLabel);
    side.appendChild(barRow);

    // Strength label
    const strength = document.createElement("div");
    strength.className = "ma-strength";
    strength.style.color = sc.text;
    strength.textContent = sc.bar === "#c9a84c" ? "Signature" :
        entry.strength.charAt(0).toUpperCase() + entry.strength.slice(1);
    side.appendChild(strength);

    // Sim overlay rows — skip for siege lines (percentile only)
    if (!MA_SIEGE_LINES.has(entry.line_slug)) {
        const sideName = civName === civLeft ? "left" : "right";

        // Beats row (wins both v30 + 3k)
        const beatsRow = document.createElement("div");
        beatsRow.className = "ma-beats-row";
        beatsRow.dataset.unitSlug = entry.unit_slug;
        beatsRow.dataset.side = sideName;
        // Show spinner while waiting for sim data
        const spinner = document.createElement("div");
        spinner.className = "ma-beats-spinner";
        beatsRow.appendChild(spinner);
        side.appendChild(beatsRow);

        // Pop wins row (v30 wins that were draw overall)
        const popRow = document.createElement("div");
        popRow.className = "ma-sim-row ma-pop-wins-row";
        popRow.dataset.unitSlug = entry.unit_slug;
        popRow.dataset.side = sideName;
        side.appendChild(popRow);

        // Eco wins row (3k wins that were draw overall)
        const ecoRow = document.createElement("div");
        ecoRow.className = "ma-sim-row ma-eco-wins-row";
        ecoRow.dataset.unitSlug = entry.unit_slug;
        ecoRow.dataset.side = sideName;
        side.appendChild(ecoRow);

        // Losses row
        const lossRow = document.createElement("div");
        lossRow.className = "ma-sim-row ma-losses-row";
        lossRow.dataset.unitSlug = entry.unit_slug;
        lossRow.dataset.side = sideName;
        side.appendChild(lossRow);
    }

    return side;
}
