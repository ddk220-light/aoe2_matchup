/* ==========================================================================
   AoE2 Unit Analyzer - Matchup Advisor Page Logic
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
const LINE_TO_RANKINGS = {
    stable: "stable",
    archer: "archery",
    cav_archer: "archery",
    scorpion: "archery",
    gunpowder: "archery",
    skirmisher: "archery",
    militia: "infantry",
    shock_infantry: "infantry",
    spear: "infantry",
    siege: "siege",
};
const STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", label: "Signature" },
    strong: { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", label: "Strong" },
    average: { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", label: "Average" },
    weak: { bg: "rgba(231, 76, 60, 0.15)", text: "#e74c3c", label: "Weak" },
};

/* ---- Civ selector ---- */
const analyzeBtn = document.getElementById("analyze-btn");
const stepLabel = document.getElementById("step-label");
const pickCiv1 = document.getElementById("pick-civ1");
const pickCiv2 = document.getElementById("pick-civ2");
const civGrid = document.getElementById("civ-grid");
const resultsEl = document.getElementById("results");

let selectedCiv1 = null, selectedCiv2 = null;

CIVS.forEach(name => {
    const slug = name.toLowerCase();
    const card = document.createElement("div");
    card.className = "civ-card";
    card.dataset.civ = name;
    const img = document.createElement("img");
    img.className = "civ-emblem"; img.src = CIV_EMBLEM_BASE + slug + ".png"; img.alt = name; img.loading = "lazy";
    const label = document.createElement("span");
    label.className = "civ-card-name"; label.textContent = name;
    card.appendChild(img); card.appendChild(label);
    card.addEventListener("click", () => onCivClick(name));
    civGrid.appendChild(card);
});

function onCivClick(name) {
    if (!selectedCiv1) {
        selectedCiv1 = name; pickCiv1.textContent = name;
        stepLabel.textContent = "Click a civilization to select Civ 2";
        stepLabel.className = "step-label step-civ2";
    } else if (!selectedCiv2) {
        if (name === selectedCiv1) return;
        selectedCiv2 = name; pickCiv2.textContent = name;
        stepLabel.textContent = "Click a selected civ to deselect";
        stepLabel.className = "step-label step-civ1";
    } else {
        if (name === selectedCiv1) {
            selectedCiv1 = selectedCiv2; selectedCiv2 = null;
            pickCiv1.textContent = selectedCiv1; pickCiv2.textContent = "\u2014";
            stepLabel.textContent = "Click a civilization to select Civ 2";
            stepLabel.className = "step-label step-civ2";
        } else if (name === selectedCiv2) {
            selectedCiv2 = null; pickCiv2.textContent = "\u2014";
            stepLabel.textContent = "Click a civilization to select Civ 2";
            stepLabel.className = "step-label step-civ2";
        }
    }
    updateGrid();
}

function updateGrid() {
    civGrid.querySelectorAll(".civ-card").forEach(card => {
        const name = card.dataset.civ;
        card.classList.remove("selected-civ1", "selected-civ2", "disabled");
        if (name === selectedCiv1) card.classList.add("selected-civ1");
        else if (name === selectedCiv2) card.classList.add("selected-civ2");
        else if (selectedCiv1 && selectedCiv2) card.classList.add("disabled");
    });
    analyzeBtn.disabled = !selectedCiv1 || !selectedCiv2;
}

/* ---- Helper: format a cost string ---- */
function formatCost(stats) {
    if (!stats) return "";
    const parts = [];
    if (stats.cost_food) parts.push(`${Math.round(stats.cost_food)}F`);
    if (stats.cost_wood) parts.push(`${Math.round(stats.cost_wood)}W`);
    if (stats.cost_gold) parts.push(`${Math.round(stats.cost_gold)}G`);
    return parts.join(" ");
}

/* ---- Helper: slug to display name ---- */
function slugToName(slug) {
    if (!slug) return "";
    return slug.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

/* ---- Unit cell renderer ---- */
function unitCellHtml(entry, civColor) {
    if (!entry) {
        return `<div class="unit-cell empty"><span class="no-unit-dash">\u2014</span></div>`;
    }

    const name = entry.unit_name || slugToName(entry.unit_slug);
    const iconUrl = getIconUrl(name);
    const strength = STRENGTH_COLORS[entry.strength] || STRENGTH_COLORS.average;
    const rankingsLine = LINE_TO_RANKINGS[entry.line_slug] || entry.line_slug;
    const rankText = entry.rank ? `#${entry.rank}` : "";
    const s = entry.stats || {};

    const iconHtml = iconUrl
        ? `<img src="${iconUrl}" class="unit-icon" width="36" height="36" alt="${name}" onerror="this.style.display='none'">`
        : "";

    const costStr = formatCost(s);
    const deltaSign = entry.median_delta >= 0 ? "+" : "";
    const deltaColor = entry.median_delta >= 0 ? "#2ecc71" : "#e74c3c";

    return `<div class="unit-cell" style="border-left: 3px solid ${civColor}">
        <a href="/?line=${encodeURIComponent(rankingsLine)}" class="unit-link">
            ${iconHtml}
            <span class="unit-cell-name">${name}</span>
        </a>
        <div class="unit-cell-meta">
            <span class="strength-badge" style="background:${strength.bg};color:${strength.text}">${strength.label}</span>
            <span class="rank-text">${rankText}</span>
        </div>
        <div class="unit-tooltip">
            <div class="tooltip-header">${name}</div>
            <div class="tooltip-stats">
                <span>HP ${Math.round(s.hp || 0)}</span>
                <span>Atk ${Math.round(s.attack || 0)}</span>
                <span>MA ${Math.round(s.melee_armor || 0)}</span>
                <span>PA ${Math.round(s.pierce_armor || 0)}</span>
                <span>Spd ${(s.speed || 0).toFixed(2)}</span>
                ${s.range ? `<span>Rng ${Math.round(s.range)}</span>` : ""}
            </div>
            <div class="tooltip-cost">${costStr}</div>
            <div class="tooltip-score">
                Score ${(entry.score || 0).toFixed(1)}
                <span style="color:${deltaColor}">(${deltaSign}${(entry.median_delta || 0).toFixed(1)})</span>
            </div>
        </div>
    </div>`;
}

/* ---- Power units grid renderer ---- */
function renderPowerUnits(c1Data, c2Data, name1, name2) {
    const civ1Color = "var(--civ1)";
    const civ2Color = "var(--civ2)";

    let html = `
        <div class="matchup-header">
            <h2><span class="civ1-color">${name1}</span>
            <span style="color:var(--text-muted)">vs</span>
            <span class="civ2-color">${name2}</span></h2>
        </div>
        <div class="power-grid">
            <div class="power-grid-header">
                <div class="role-col">Role</div>
                <div class="civ-col civ1-color">${name1}</div>
                <div class="civ-col civ2-color">${name2}</div>
            </div>`;

    for (const role of ROLE_ORDER) {
        const c1Entry = (c1Data.power_units || {})[role] || null;
        const c2Entry = (c2Data.power_units || {})[role] || null;
        const roleLabel = ROLE_LABELS[role] || role;

        html += `
            <div class="power-grid-row">
                <div class="role-col">${roleLabel}</div>
                <div class="civ-col">${unitCellHtml(c1Entry, civ1Color)}</div>
                <div class="civ-col">${unitCellHtml(c2Entry, civ2Color)}</div>
            </div>`;
    }

    html += `</div>`;
    html += `<div id="recommendations-section"></div>`;

    return html;
}

/* ---- Recommendations renderer (Phase B) ---- */
function renderRecommendations(data) {
    const section = document.getElementById("recommendations-section");
    if (!section || data.error) return;

    const comps = data.recommended_compositions || [];
    if (comps.length === 0) {
        section.innerHTML = `<div class="recs-section visible"><div class="no-data">No composition recommendations available.</div></div>`;
        return;
    }

    let cardsHtml = "";
    for (const comp of comps) {
        const goldName = comp.gold_unit
            ? (slugToName(comp.gold_unit.unit_slug))
            : "None";
        const trashName = comp.trash_unit
            ? (slugToName(comp.trash_unit.unit_slug))
            : "None";
        const goldIcon = getIconUrl(goldName);
        const trashIcon = getIconUrl(trashName);

        const goldIconHtml = goldIcon
            ? `<img src="${goldIcon}" class="unit-icon" width="32" height="32" alt="${goldName}" onerror="this.style.display='none'">`
            : "";
        const trashIconHtml = trashIcon
            ? `<img src="${trashIcon}" class="unit-icon" width="32" height="32" alt="${trashName}" onerror="this.style.display='none'">`
            : "";

        const scores = comp.scores || {};

        cardsHtml += `
            <div class="rec-card">
                <div class="rec-card-rank">#${comp.rank}</div>
                <div class="rec-card-units">
                    <div class="rec-unit gold-unit">
                        ${goldIconHtml}
                        <span class="rec-unit-name">${goldName}</span>
                        <span class="rec-unit-tag gold-tag">Gold</span>
                    </div>
                    <span class="rec-plus">+</span>
                    <div class="rec-unit trash-unit">
                        ${trashIconHtml}
                        <span class="rec-unit-name">${trashName}</span>
                        <span class="rec-unit-tag trash-tag">Trash</span>
                    </div>
                </div>
                ${comp.reasoning ? `<div class="rec-reasoning">${comp.reasoning}</div>` : ""}
                <div class="rec-scores">
                    <span>Res Eff: ${(scores.resource_efficiency || 0).toFixed(1)}</span>
                    <span>Pop Eff: ${(scores.pop_efficiency || 0).toFixed(1)}</span>
                    <span>Composite: ${(scores.composite || 0).toFixed(1)}</span>
                </div>
            </div>`;
    }

    section.innerHTML = `
        <div class="recs-section">
            <div class="recs-header">Recommended Compositions for ${data.civ_a} vs ${data.civ_b}</div>
            <div class="recs-cards">${cardsHtml}</div>
        </div>`;

    // Trigger fade-in animation
    requestAnimationFrame(() => {
        const el = section.querySelector(".recs-section");
        if (el) el.classList.add("visible");
    });
}

/* ---- Analyze button handler ---- */
analyzeBtn.addEventListener("click", async () => {
    const c1 = selectedCiv1, c2 = selectedCiv2;
    if (!c1 || !c2 || c1 === c2) return;
    analyzeBtn.disabled = true;
    resultsEl.className = "results-container visible";
    resultsEl.innerHTML = `<div class="loading-spinner"><div class="spinner"></div><div>Loading power units...</div></div>`;

    try {
        const [r1, r2] = await Promise.all([
            fetch(`/api/civ-power-units/${encodeURIComponent(c1)}`).then(r => r.json()),
            fetch(`/api/civ-power-units/${encodeURIComponent(c2)}`).then(r => r.json()),
        ]);
        if (r1.error || r2.error) throw new Error(r1.error || r2.error);

        resultsEl.innerHTML = renderPowerUnits(r1, r2, c1, c2);

        // Phase B: matchup recommendations in background
        fetch(`/api/matchup-recommendations/${encodeURIComponent(c1)}/${encodeURIComponent(c2)}`)
            .then(r => r.json())
            .then(data => renderRecommendations(data))
            .catch(() => {});
    } catch (e) {
        resultsEl.innerHTML = `<div class="no-data">Error: ${e.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});
