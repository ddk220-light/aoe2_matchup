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

    // Compute best combo ease for each side (to pass to opponent)
    function _bestComboEase(topUnits, side, unitsBySlug, oppGoldSlugs) {
        if (topUnits.length === 0) return null;
        const item = topUnits[0];
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const bestSidekick = sidekicks.length > 0 ? sidekicks[0] : null;
        const goldPartner = _computeGoldCombo(item, side, unitsBySlug, oppGoldSlugs);
        const sidekickGap = bestSidekick ? _computeComboGap(item.slug, bestSidekick.slug, side, oppGoldSlugs) : null;
        const goldGap = goldPartner ? _computeComboGap(item.slug, goldPartner.slug, side, oppGoldSlugs) : null;
        const soloGap = _computeComboGap(item.slug, null, side, oppGoldSlugs);

        let bestPartner = null;
        let bestGap = soloGap;
        if (sidekickGap && sidekickGap.gap.length <= bestGap.gap.length) { bestPartner = bestSidekick; bestGap = sidekickGap; }
        if (goldGap && goldGap.gap.length < bestGap.gap.length) { bestPartner = goldPartner; bestGap = goldGap; }

        const subs = _avgEaseSubs(item, bestPartner);
        const hasCastle = !!(
            (item.entry.ease && item.entry.ease.is_castle_unit) ||
            (bestPartner && bestPartner.entry.ease && bestPartner.entry.ease.is_castle_unit)
        );
        return { subs, hasCastle };
    }

    const leftBestEase = _bestComboEase(leftTop, "left", leftBySlug, rightGoldSlugs);
    const rightBestEase = _bestComboEase(rightTop, "right", rightBySlug, leftGoldSlugs);

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
    const leftCol = _buildTopColumn(leftTop, civLeft, rightGoldSlugs, "left", leftBySlug, rightBestEase);
    body.appendChild(leftCol);

    // Right side
    const rightCol = _buildTopColumn(rightTop, civRight, leftGoldSlugs, "right", rightBySlug, leftBestEase);
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

    const topIsGold = !!(topItem.entry.stats && topItem.entry.stats.cost_gold > 0);

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
        const isGold = !!(entry.stats && entry.stats.cost_gold > 0);
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

function _computeComboGap(topSlug, partnerSlug, side, oppGoldSlugs) {
    /**Compute categorized gap for a combo (top unit + partner).
     * For each opponent gold unit, find the best result from either unit.
     * Returns { covered: number, total: number, gap: [{slug, category}] }
     *
     * Categories:
     *   "loss" — neither unit wins either sim
     *   "pop"  — best result is pop-only win (30v30 win, 3k loss)
     *   "eco"  — best result is eco-only win (3k win, 30v30 loss)
     *
     * Cross-coverage: if one unit has pop_win and other has eco_win
     * against the same opponent, that opponent is covered (not in gap).
     */
    const sideData = simData[side];
    if (!sideData) return { covered: 0, total: oppGoldSlugs.size, gap: [] };

    const topD = sideData[topSlug] || {};
    const partD = partnerSlug ? (sideData[partnerSlug] || {}) : {};

    const topWins = new Set(topD.wins || []);
    const topPop = new Set(topD.pop_wins || []);
    const topEco = new Set(topD.eco_wins || []);

    const partWins = new Set(partD.wins || []);
    const partPop = new Set(partD.pop_wins || []);
    const partEco = new Set(partD.eco_wins || []);

    let covered = 0;
    const gap = [];

    for (const oppSlug of oppGoldSlugs) {
        // Full win by either unit
        if (topWins.has(oppSlug) || partWins.has(oppSlug)) {
            covered++;
            continue;
        }

        // Cross-coverage: one has pop, other has eco
        const anyPop = topPop.has(oppSlug) || partPop.has(oppSlug);
        const anyEco = topEco.has(oppSlug) || partEco.has(oppSlug);
        if (anyPop && anyEco) {
            covered++;
            continue;
        }

        // Partial — in the gap
        if (anyPop) {
            gap.push({ slug: oppSlug, category: "pop" });
        } else if (anyEco) {
            gap.push({ slug: oppSlug, category: "eco" });
        } else {
            gap.push({ slug: oppSlug, category: "loss" });
        }
    }

    return { covered, total: oppGoldSlugs.size, gap };
}

function _computeGoldCombo(topItem, side, unitsBySlug, oppGoldSlugs) {
    /**Find the best gold unit partner for a top unit.
     * Same scoring as sidekicks but partner must be gold (not opposite cost type).
     * Used when no gold+trash sidekick can fully cover.**/
    const sideData = simData[side];
    if (!sideData) return null;

    // Top unit's weaknesses: losses + draws (opponent gold slugs)
    const topLosses = new Set((topItem.losses || []).filter((s) => oppGoldSlugs.has(s)));
    const topDraws = new Set([
        ...(topItem.goldPopWins || []),
        ...(topItem.goldEcoWins || []),
    ]);
    const allWeaknesses = new Set([...topLosses, ...topDraws]);

    if (allWeaknesses.size === 0) return null;

    // Score each gold unit as partner
    const ranked = [];
    for (const slug of Object.keys(sideData)) {
        const entry = unitsBySlug[slug];
        if (!entry) continue;
        if (slug === topItem.slug) continue;

        // Partner must be gold
        const isGold = !!(entry.stats && entry.stats.cost_gold > 0);
        if (!isGold) continue;

        const d = sideData[slug];
        const pWins = new Set(d.wins || []);
        const pDraws = new Set([...(d.pop_wins || []), ...(d.eco_wins || [])]);

        let score = 0;
        const covered = [];

        for (const opp of topLosses) {
            if (pWins.has(opp)) { score += 3; covered.push(opp); }
            else if (pDraws.has(opp)) { score += 2; covered.push(opp); }
        }
        for (const opp of topDraws) {
            if (pWins.has(opp)) { score += 2; covered.push(opp); }
            else if (pDraws.has(opp)) { score += 1; covered.push(opp); }
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

    return ranked.length > 0 ? ranked[0] : null;
}

function _avgEase(topItem, partner) {
    /**Compute average ease_score for a combo (top unit + optional partner).**/
    const topEase = topItem.entry.ease ? topItem.entry.ease.score : 0;
    if (!partner) return topEase;
    const partnerEase = partner.entry.ease ? partner.entry.ease.score : 0;
    return (topEase + partnerEase) / 2;
}

function _avgEaseSubs(topItem, partner) {
    /**Compute average ease sub_scores for a combo. Returns sub_scores dict or null.**/
    const topSubs = topItem.entry.ease ? topItem.entry.ease.sub_scores : null;
    if (!partner) return topSubs;
    const partSubs = partner.entry.ease ? partner.entry.ease.sub_scores : null;
    if (!topSubs && !partSubs) return null;
    if (!topSubs) return partSubs;
    if (!partSubs) return topSubs;
    const result = {};
    for (const key of Object.keys(topSubs)) {
        result[key] = (topSubs[key] + (partSubs[key] || 0)) / 2;
    }
    return result;
}

function _computeCombatContext(gapResult) {
    /**Generate combat context statement from gap categories.
     * Returns string or null (for zero-gap or all-loss gaps).**/
    if (gapResult.gap.length === 0) return null;

    const categories = new Set(gapResult.gap.map((g) => g.category));
    const hasLoss = categories.has("loss");
    const hasPop = categories.has("pop");
    const hasEco = categories.has("eco");

    // If all gaps are complete losses, flag it
    if (hasLoss && !hasPop && !hasEco) return "Doesn't win outright";

    if (hasPop && !hasEco && !hasLoss) {
        return "Loses on pop efficiency, but trades better on eco";
    }
    if (hasEco && !hasPop && !hasLoss) {
        return "Less eco-efficient, but more pop-efficient";
    }
    // Mixed
    if (hasPop && hasEco) {
        return "Mixed results \u2014 pop-efficient vs some, eco-efficient vs others";
    }
    // Pop or eco with some losses
    if (hasPop) return "Loses on pop efficiency, but trades better on eco";
    if (hasEco) return "Less eco-efficient, but more pop-efficient";
    return null;
}

function _computeEaseStatement(mySubs, oppSubs, myHasCastle, oppHasCastle) {
    /**Generate ease comparison statement.
     * @param mySubs    — my combo's average sub_scores dict
     * @param oppSubs   — opponent's best combo's average sub_scores dict
     * @param myHasCastle  — boolean, does my combo include a castle unit?
     * @param oppHasCastle — boolean, does opponent's combo include a castle unit?
     * Returns { text: string, isUpside: boolean } or null.**/
    if (!mySubs || !oppSubs) return null;

    const THRESHOLD = 0.15;
    const factors = [];

    // Castle: always include if asymmetric
    if (myHasCastle && !oppHasCastle) {
        factors.push({ key: "not_castle", delta: -(mySubs.not_castle - oppSubs.not_castle), text: "needs a Castle" });
    }

    // Creation time (higher = faster train = better)
    const ctDelta = mySubs.creation_time - oppSubs.creation_time;
    if (Math.abs(ctDelta) >= THRESHOLD) {
        factors.push({ key: "creation_time", delta: ctDelta, text: ctDelta > 0 ? "trains faster" : "slower to train" });
    }

    // Upgrade cost (higher = cheaper = better)
    const ucDelta = mySubs.upgrade_cost - oppSubs.upgrade_cost;
    if (Math.abs(ucDelta) >= THRESHOLD) {
        factors.push({ key: "upgrade_cost", delta: ucDelta, text: ucDelta > 0 ? "cheaper upgrades" : "costlier upgrades" });
    }

    // Castle unique tech: only if asymmetric
    if (!myHasCastle || !oppHasCastle) {
        const utDelta = mySubs.no_castle_ut - oppSubs.no_castle_ut;
        if (Math.abs(utDelta) >= THRESHOLD) {
            factors.push({ key: "no_castle_ut", delta: utDelta, text: utDelta > 0 ? "no Castle tech needed" : "needs a Castle unique tech" });
        }
    }

    // Speed (higher = faster = better)
    const spDelta = mySubs.speed - oppSubs.speed;
    if (Math.abs(spDelta) >= THRESHOLD) {
        factors.push({ key: "speed", delta: spDelta, text: spDelta > 0 ? "faster on the field" : "slower on the field" });
    }

    if (factors.length === 0) return null;

    // Sort by absolute delta descending, take top 3
    factors.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    const top = factors.slice(0, 3);

    // Determine overall direction: positive factors = easier, negative = harder
    const avgDelta = top.reduce((sum, f) => sum + f.delta, 0) / top.length;
    const isUpside = avgDelta >= 0;

    const factorTexts = top.map((f) => f.text).join(" and ");
    let text;
    if (isUpside) {
        text = "Easier to mass \u2014 " + factorTexts;
    } else {
        text = "Harder to get going \u2014 " + factorTexts;
    }

    return { text, isUpside };
}

function _buildComboCard(topItem, partner, partnerType, civName, gapResult, oppBestEase) {
    /**Build a unified combo card.
     * @param topItem     — top unit object from _computeTopUnits
     * @param partner     — partner object (from _computeSidekicks or _computeGoldCombo), or null for solo
     * @param partnerType — "trash" | "gold" | null (solo)
     * @param civName     — civ name string
     * @param gapResult   — pre-computed result from _computeComboGap
     */
    const card = document.createElement("div");
    card.className = "ma-gold-combo-card";

    // Header
    const header = document.createElement("div");
    header.className = "ma-gold-combo-header";
    if (partnerType === "trash") {
        header.textContent = "Best Combo";
    } else if (partnerType === "gold") {
        header.textContent = "Gold Combo";
    } else {
        header.textContent = topItem.entry.unit_name;
    }
    card.appendChild(header);

    // Unit pair row
    const pairRow = document.createElement("div");
    pairRow.className = "ma-gold-combo-pair";

    // Civ emblem
    const emblem = document.createElement("img");
    emblem.src = CIV_EMBLEM_BASE + civName.toLowerCase() + ".png";
    emblem.className = "ma-unit-emblem";
    emblem.alt = civName;
    pairRow.appendChild(emblem);

    // Top unit icon + name
    const icon1 = document.createElement("img");
    icon1.className = "ma-unit-icon";
    const url1 = getIconUrl(topItem.entry.unit_name);
    if (url1) icon1.src = url1;
    icon1.alt = topItem.entry.unit_name;
    pairRow.appendChild(icon1);

    const name1 = document.createElement("span");
    name1.className = "ma-gold-combo-name";
    name1.textContent = topItem.entry.unit_name;
    pairRow.appendChild(name1);

    // Partner (if present)
    if (partner) {
        const plus = document.createElement("span");
        plus.className = "ma-gold-combo-plus";
        plus.textContent = "+";
        pairRow.appendChild(plus);

        const icon2 = document.createElement("img");
        icon2.className = "ma-unit-icon";
        const url2 = getIconUrl(partner.entry.unit_name);
        if (url2) icon2.src = url2;
        icon2.alt = partner.entry.unit_name;
        pairRow.appendChild(icon2);

        const name2 = document.createElement("span");
        name2.className = "ma-gold-combo-name";
        name2.textContent = partner.entry.unit_name;
        pairRow.appendChild(name2);
    }

    card.appendChild(pairRow);

    // Summary
    const summary = document.createElement("div");
    summary.className = "ma-gold-combo-summary";
    const verb = partner ? "Together handle" : "Handles";
    summary.innerHTML = verb + " <strong>" + gapResult.covered + "</strong> of " + gapResult.total + " opponent gold units";
    card.appendChild(summary);

    // Gap row (only if there are gap opponents)
    if (gapResult.gap.length > 0) {
        const gapRow = document.createElement("div");
        gapRow.className = "ma-combo-gap-row";

        const gapLabel = document.createElement("span");
        gapLabel.className = "ma-beats-label ma-label-loss";
        gapLabel.textContent = "Can't beat:";
        gapRow.appendChild(gapLabel);

        const gapIcons = document.createElement("div");
        gapIcons.className = "ma-beats-icons";

        // Sort: complete losses first, then pop, then eco
        const categoryOrder = { loss: 0, pop: 1, eco: 2 };
        gapResult.gap.sort((a, b) => categoryOrder[a.category] - categoryOrder[b.category]);

        gapResult.gap.forEach(({ slug, category }) => {
            const oppName = simData.name_map[slug] || slug;
            const url = getIconUrl(oppName);
            if (!url) return;
            const img = document.createElement("img");
            img.className = "ma-gap-icon gap-" + category;
            img.src = url;
            img.alt = oppName;
            img.title = oppName + (category === "loss" ? " (complete loss)" : category === "pop" ? " (pop win only)" : " (eco win only)");
            gapIcons.appendChild(img);
        });

        gapRow.appendChild(gapIcons);
        card.appendChild(gapRow);
    }

    // Ease + combat context statements (only for combos with gaps)
    if (gapResult.gap.length > 0) {
        const mySubs = _avgEaseSubs(topItem, partner);
        const myHasCastle = !!(
            (topItem.entry.ease && topItem.entry.ease.is_castle_unit) ||
            (partner && partner.entry.ease && partner.entry.ease.is_castle_unit)
        );

        const combatCtx = _computeCombatContext(gapResult);
        const easeStmt = oppBestEase
            ? _computeEaseStatement(mySubs, oppBestEase.subs, myHasCastle, oppBestEase.hasCastle)
            : null;

        if (combatCtx || easeStmt) {
            const stmtDiv = document.createElement("div");
            let text = "";

            if (combatCtx && easeStmt) {
                // "Doesn't win outright" + downside → join with " and " (lowercase)
                // Other combat context + ease → join with ". "
                if (combatCtx === "Doesn't win outright" && !easeStmt.isUpside) {
                    text = combatCtx + " and " + easeStmt.text.toLowerCase();
                } else {
                    text = combatCtx + ". " + easeStmt.text;
                }
            } else if (combatCtx) {
                text = combatCtx;
            } else if (easeStmt) {
                text = easeStmt.text;
            }

            if (text) {
                const cssClass = easeStmt
                    ? (easeStmt.isUpside ? "ma-ease-upside" : "ma-ease-downside")
                    : "ma-ease-neutral";
                stmtDiv.className = "ma-ease-statement " + cssClass;
                stmtDiv.textContent = text + ".";
                card.appendChild(stmtDiv);
            }
        }
    }

    return card;
}

function _buildTopColumn(topUnits, civName, oppGoldSlugs, side, unitsBySlug, oppBestEase) {
    const col = document.createElement("div");
    col.className = "ma-top-col ma-top-col-" + side;

    if (topUnits.length === 0) {
        const empty = document.createElement("div");
        empty.className = "ma-top-empty";
        empty.textContent = "No gold unit wins";
        col.appendChild(empty);
        return col;
    }

    // For each top unit, find the best partner and render a combo card
    let cards = [];
    for (const item of topUnits) {
        // Try trash sidekick (best one only)
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const bestSidekick = sidekicks.length > 0 ? sidekicks[0] : null;

        // Try gold combo
        const goldPartner = _computeGoldCombo(item, side, unitsBySlug, oppGoldSlugs);

        // Compute gaps for each option
        const sidekickGap = bestSidekick
            ? _computeComboGap(item.slug, bestSidekick.slug, side, oppGoldSlugs)
            : null;
        const goldGap = goldPartner
            ? _computeComboGap(item.slug, goldPartner.slug, side, oppGoldSlugs)
            : null;
        const soloGap = _computeComboGap(item.slug, null, side, oppGoldSlugs);

        // Pick the best option: smallest gap, prefer sidekick on tie
        let bestPartner = null;
        let bestType = null;
        let bestGap = soloGap;

        if (sidekickGap && sidekickGap.gap.length <= bestGap.gap.length) {
            bestPartner = bestSidekick;
            bestType = "trash";
            bestGap = sidekickGap;
        }
        if (goldGap && goldGap.gap.length < bestGap.gap.length) {
            bestPartner = goldPartner;
            bestType = "gold";
            bestGap = goldGap;
        }

        cards.push({ item, partner: bestPartner, type: bestType, gapSize: bestGap.gap.length, gapResult: bestGap });
    }

    // Deduplicate: drop cards with the same unit pair in swapped roles
    const seenPairs = new Set();
    cards = cards.filter((c) => {
        if (!c.partner) return true;
        const key = [c.item.slug, c.partner.slug].sort().join("|");
        if (seenPairs.has(key)) return false;
        seenPairs.add(key);
        return true;
    });

    // If any card has zero gap, filter to only zero-gap cards
    const anyPerfect = cards.some((c) => c.gapSize === 0);
    let filtered = anyPerfect ? cards.filter((c) => c.gapSize === 0) : cards;

    // Sort: smallest gap first, then highest ease score
    filtered.sort((a, b) => {
        if (a.gapSize !== b.gapSize) return a.gapSize - b.gapSize;
        return _avgEase(b.item, b.partner) - _avgEase(a.item, a.partner);
    });

    filtered.forEach(({ item, partner, type, gapResult }) => {
        const card = _buildComboCard(item, partner, type, civName, gapResult, oppBestEase);
        col.appendChild(card);
    });

    return col;
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
