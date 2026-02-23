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
let savedDataL = null;
let savedDataR = null;

/* ---- DOM refs ---- */
const slotLeft = document.getElementById("slot-left");
const slotRight = document.getElementById("slot-right");
const civGrid = document.getElementById("civ-grid");
const controls = document.getElementById("controls");
const topUnitsEl = document.getElementById("top-units");
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
    savedDataL = null;
    savedDataR = null;
    topUnitsEl.innerHTML = "";
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

    // Render top units summary
    renderTopUnits();
}

/* ---- Top Units Section ---- */

function _collectAllUnits(puData) {
    /**Collect all unit entries from power_units (flat list, skipping siege).**/
    const units = [];
    for (const colKey of ["cavalry", "ranged", "infantry"]) {
        const col = puData[colKey] || {};
        for (const lineSlug of Object.keys(col)) {
            const entries = col[lineSlug];
            if (!entries) continue;
            for (const entry of entries) {
                units.push(entry);
            }
        }
    }
    return units;
}

function _getGoldSlugs(units) {
    /**Return set of unit_slugs that cost gold > 0.**/
    const goldSlugs = new Set();
    for (const u of units) {
        if (u.stats && u.stats.cost_gold > 0) {
            goldSlugs.add(u.unit_slug);
        }
    }
    return goldSlugs;
}

function renderTopUnits() {
    topUnitsEl.innerHTML = "";
    if (!simData || !savedDataL || !savedDataR) return;

    const puL = savedDataL.power_units || {};
    const puR = savedDataR.power_units || {};

    const leftUnits = _collectAllUnits(puL);
    const rightUnits = _collectAllUnits(puR);

    // Gold slugs for each side (opponent's gold units)
    const leftGoldSlugs = _getGoldSlugs(leftUnits);
    const rightGoldSlugs = _getGoldSlugs(rightUnits);

    // Build lookup: slug -> entry (for percentile)
    const leftBySlug = {};
    leftUnits.forEach((u) => { leftBySlug[u.unit_slug] = u; });
    const rightBySlug = {};
    rightUnits.forEach((u) => { rightBySlug[u.unit_slug] = u; });

    // Compute top units for left side (beats most right gold units)
    const leftTop = _computeTopUnits("left", leftBySlug, rightGoldSlugs, "right", leftGoldSlugs);
    const rightTop = _computeTopUnits("right", rightBySlug, leftGoldSlugs, "left", rightGoldSlugs);

    if (leftTop.length === 0 && rightTop.length === 0) return;

    // Build section
    const section = document.createElement("div");
    section.className = "ma-top-units";

    const header = document.createElement("div");
    header.className = "ma-top-units-header";
    header.textContent = "Top Units";
    section.appendChild(header);

    const body = document.createElement("div");
    body.className = "ma-top-units-body";

    // Left side
    const leftCol = _buildTopColumn(leftTop, civLeft, rightGoldSlugs, "left", leftBySlug);
    body.appendChild(leftCol);

    // Right side
    const rightCol = _buildTopColumn(rightTop, civRight, leftGoldSlugs, "right", rightBySlug);
    body.appendChild(rightCol);

    section.appendChild(body);
    topUnitsEl.appendChild(section);
}

function _computeTopUnits(side, unitsBySlug, oppGoldSlugs, oppSide, myGoldSlugs) {
    /**Rank units by weighted score: wins=3pts, draws=1pt, each multiplied
     * by opponent unit's strength (how many of my gold units it beats).
     * Tiebreak by percentile.**/
    const sideData = simData[side];
    const oppData = simData[oppSide];
    if (!sideData || !oppData) return [];

    // Step 1: Compute opponent strength — how many of MY gold units each opp unit beats
    const oppStrength = {};
    for (const oppSlug of oppGoldSlugs) {
        const od = oppData[oppSlug];
        if (!od) { oppStrength[oppSlug] = 0; continue; }
        const oppWins = od.wins || [];
        oppStrength[oppSlug] = oppWins.filter((w) => myGoldSlugs.has(w)).length;
    }

    // Step 2: Score each of my units
    const ranked = [];
    for (const slug of Object.keys(sideData)) {
        const entry = unitsBySlug[slug];
        if (!entry) continue;

        const d = sideData[slug];
        const wins = d.wins || [];
        const popWins = d.pop_wins || [];
        const ecoWins = d.eco_wins || [];

        const goldWins = wins.filter((w) => oppGoldSlugs.has(w));
        const goldPopWins = popWins.filter((w) => oppGoldSlugs.has(w));
        const goldEcoWins = ecoWins.filter((w) => oppGoldSlugs.has(w));

        // Weighted score: 3 * strength for wins, 1 * strength for draws
        let score = 0;
        for (const w of goldWins) score += 3 * (oppStrength[w] || 0);
        for (const w of goldPopWins) score += 1 * (oppStrength[w] || 0);
        for (const w of goldEcoWins) score += 1 * (oppStrength[w] || 0);

        // Only include units with score > 0 or at least 1 gold win
        if (score === 0 && goldWins.length === 0) continue;

        ranked.push({
            slug,
            entry,
            goldWins,
            goldWinCount: goldWins.length,
            goldPopWins,
            goldEcoWins,
            percentile: entry.percentile || 0,
            losses: d.losses || [],
            score,
        });
    }

    // Sort: highest score first, then highest percentile
    ranked.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return b.percentile - a.percentile;
    });

    return ranked.slice(0, 2);
}

function _computeSidekicks(topItem, side, unitsBySlug, oppGoldSlugs) {
    /**Find the top 2 complementary sidekick units for a top unit.
     * Sidekick = opposite resource type (gold↔trash).
     * Scores against the top unit's losses and draws.**/
    const sideData = simData[side];
    if (!sideData) return [];

    const topIsGold = topItem.entry.stats && topItem.entry.stats.cost_gold > 0;

    // Top unit's weaknesses: losses + draws (opponent slugs)
    const topLosses = new Set((topItem.losses || []).filter((s) => oppGoldSlugs.has(s)));
    const topDraws = new Set([
        ...(topItem.goldPopWins || []),
        ...(topItem.goldEcoWins || []),
    ]);
    const allWeaknesses = new Set([...topLosses, ...topDraws]);

    if (allWeaknesses.size === 0) return [];

    // Score each candidate sidekick
    const ranked = [];
    for (const slug of Object.keys(sideData)) {
        const entry = unitsBySlug[slug];
        if (!entry) continue;
        if (slug === topItem.slug) continue;

        // Strict gold↔trash: sidekick must be opposite cost type
        const isGold = entry.stats && entry.stats.cost_gold > 0;
        if (isGold === topIsGold) continue;

        const d = sideData[slug];
        const skWins = new Set(d.wins || []);
        const skDraws = new Set([...(d.pop_wins || []), ...(d.eco_wins || [])]);

        let score = 0;
        const covered = [];

        for (const opp of topLosses) {
            if (skWins.has(opp)) { score += 3; covered.push(opp); }
            else if (skDraws.has(opp)) { score += 2; covered.push(opp); }
        }
        for (const opp of topDraws) {
            if (skWins.has(opp)) { score += 2; covered.push(opp); }
            else if (skDraws.has(opp)) { score += 1; covered.push(opp); }
        }

        if (score === 0) continue;

        const coveredSet = new Set(covered);
        const gap = [...allWeaknesses].filter((s) => !coveredSet.has(s));

        ranked.push({
            slug,
            entry,
            score,
            percentile: entry.percentile || 0,
            covered,
            gap,
            totalWeaknesses: allWeaknesses.size,
        });
    }

    ranked.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return b.percentile - a.percentile;
    });

    return ranked.slice(0, 2);
}

function _buildTopColumn(topUnits, civName, oppGoldSlugs, side, unitsBySlug) {
    const col = document.createElement("div");
    col.className = "ma-top-col ma-top-col-" + side;

    if (topUnits.length === 0) {
        const empty = document.createElement("div");
        empty.className = "ma-top-empty";
        empty.textContent = "No gold unit wins";
        col.appendChild(empty);
        return col;
    }

    topUnits.forEach((item) => {
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const card = _buildTopCard(item, civName, oppGoldSlugs, sidekicks);
        col.appendChild(card);
    });

    return col;
}

function _buildTopCard(item, civName, oppGoldSlugs, sidekicks) {
    const card = document.createElement("div");
    card.className = "ma-top-card";

    const sc = MA_STRENGTH_COLORS[item.entry.strength] || MA_STRENGTH_COLORS.average;

    // Name row: emblem + icon + name
    const nameRow = document.createElement("div");
    nameRow.className = "ma-unit-name-row";

    const emblem = document.createElement("img");
    emblem.src = CIV_EMBLEM_BASE + civName.toLowerCase() + ".png";
    emblem.className = "ma-unit-emblem";
    emblem.alt = civName;

    const icon = document.createElement("img");
    icon.className = "ma-unit-icon";
    const iconUrl = getIconUrl(item.entry.unit_name);
    if (iconUrl) icon.src = iconUrl;
    icon.alt = item.entry.unit_name;

    const name = document.createElement("span");
    name.className = "ma-unit-name";
    name.textContent = item.entry.unit_name;

    nameRow.appendChild(emblem);
    nameRow.appendChild(icon);
    nameRow.appendChild(name);
    card.appendChild(nameRow);

    // "Beats X of Y gold units" summary
    const totalOppGold = oppGoldSlugs.size;
    const summary = document.createElement("div");
    summary.className = "ma-top-summary";
    summary.innerHTML = "Beats <strong>" + item.goldWinCount + "</strong> of " + totalOppGold + " gold units";
    card.appendChild(summary);

    // Icons of beaten gold units
    if (item.goldWins.length > 0) {
        const beatsRow = document.createElement("div");
        beatsRow.className = "ma-top-beats-row";
        const beatsIcons = document.createElement("div");
        beatsIcons.className = "ma-beats-icons";
        item.goldWins.forEach((oppSlug) => {
            const oppName = simData.name_map[oppSlug] || oppSlug;
            const url = getIconUrl(oppName);
            if (!url) return;
            const img = document.createElement("img");
            img.className = "ma-beats-icon";
            img.src = url;
            img.alt = oppName;
            img.title = oppName;
            beatsIcons.appendChild(img);
        });
        beatsRow.appendChild(beatsIcons);
        card.appendChild(beatsRow);
    }

    // Gold unit losses callout
    const goldLosses = item.losses.filter((l) => oppGoldSlugs.has(l));
    if (goldLosses.length > 0) {
        const lossRow = document.createElement("div");
        lossRow.className = "ma-top-loss-row";
        const lossLabel = document.createElement("span");
        lossLabel.className = "ma-beats-label ma-label-loss";
        lossLabel.textContent = "Loses to:";
        lossRow.appendChild(lossLabel);

        const lossIcons = document.createElement("div");
        lossIcons.className = "ma-beats-icons";
        goldLosses.forEach((oppSlug) => {
            const oppName = simData.name_map[oppSlug] || oppSlug;
            const url = getIconUrl(oppName);
            if (!url) return;
            const img = document.createElement("img");
            img.className = "ma-beats-icon loss";
            img.src = url;
            img.alt = oppName;
            img.title = oppName;
            lossIcons.appendChild(img);
        });
        lossRow.appendChild(lossIcons);
        card.appendChild(lossRow);
    }

    // Sidekick sub-cards
    if (sidekicks && sidekicks.length > 0) {
        const skSection = document.createElement("div");
        skSection.className = "ma-sidekick-section";

        sidekicks.forEach((sk, idx) => {
            const skCard = document.createElement("div");
            skCard.className = "ma-sidekick-card";

            // Name row: label + icon + name
            const skNameRow = document.createElement("div");
            skNameRow.className = "ma-sidekick-name-row";

            const skLabel = document.createElement("span");
            skLabel.className = "ma-sidekick-label";
            skLabel.textContent = idx === 0 ? "Best Sidekick:" : "Alt Sidekick:";

            const skIcon = document.createElement("img");
            skIcon.className = "ma-unit-icon";
            const skIconUrl = getIconUrl(sk.entry.unit_name);
            if (skIconUrl) skIcon.src = skIconUrl;
            skIcon.alt = sk.entry.unit_name;

            const skName = document.createElement("span");
            skName.className = "ma-sidekick-name";
            skName.textContent = sk.entry.unit_name;

            skNameRow.appendChild(skLabel);
            skNameRow.appendChild(skIcon);
            skNameRow.appendChild(skName);
            skCard.appendChild(skNameRow);

            // Summary: "Covers X of Y weaknesses"
            const skSummary = document.createElement("div");
            skSummary.className = "ma-sidekick-summary";
            skSummary.innerHTML = "Covers <strong>" + sk.covered.length + "</strong> of " + sk.totalWeaknesses + " weaknesses";
            skCard.appendChild(skSummary);

            // Covered icons row
            if (sk.covered.length > 0) {
                const covRow = document.createElement("div");
                covRow.className = "ma-sidekick-covers-row";
                const covIcons = document.createElement("div");
                covIcons.className = "ma-beats-icons";
                sk.covered.forEach((oppSlug) => {
                    const oppName = simData.name_map[oppSlug] || oppSlug;
                    const url = getIconUrl(oppName);
                    if (!url) return;
                    const img = document.createElement("img");
                    img.className = "ma-beats-icon";
                    img.src = url;
                    img.alt = oppName;
                    img.title = oppName;
                    covIcons.appendChild(img);
                });
                covRow.appendChild(covIcons);
                skCard.appendChild(covRow);
            }

            // Gap icons row — "Neither can beat:"
            if (sk.gap.length > 0) {
                const gapRow = document.createElement("div");
                gapRow.className = "ma-sidekick-gap-row";
                const gapLabel = document.createElement("span");
                gapLabel.className = "ma-beats-label ma-label-gap";
                gapLabel.textContent = "Neither can beat:";
                gapRow.appendChild(gapLabel);

                const gapIcons = document.createElement("div");
                gapIcons.className = "ma-beats-icons";
                sk.gap.forEach((oppSlug) => {
                    const oppName = simData.name_map[oppSlug] || oppSlug;
                    const url = getIconUrl(oppName);
                    if (!url) return;
                    const img = document.createElement("img");
                    img.className = "ma-beats-icon loss";
                    img.src = url;
                    img.alt = oppName;
                    img.title = oppName;
                    gapIcons.appendChild(img);
                });
                gapRow.appendChild(gapIcons);
                skCard.appendChild(gapRow);
            }

            skSection.appendChild(skCard);
        });

        card.appendChild(skSection);
    }

    return card;
}

/* ---- Rendering ---- */
function renderComparison(dataL, dataR) {
    resultsEl.innerHTML = "";
    savedDataL = dataL;
    savedDataR = dataR;
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
