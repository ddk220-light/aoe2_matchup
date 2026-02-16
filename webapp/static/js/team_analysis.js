/* ==========================================================================
   AoE2 Unit Analyzer - Team Analysis Page Logic
   Depends on: constants.js (CIV_EMBLEM_BASE)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- State ---- */
const team1 = [];
const team2 = [];
const MAX_PER_TEAM = 4;

/* ---- DOM refs ---- */
const team1Slots = document.getElementById("team1-slots");
const team2Slots = document.getElementById("team2-slots");
const team1Grid = document.getElementById("team1-grid");
const team2Grid = document.getElementById("team2-grid");
const analyzeBtn = document.getElementById("analyze-btn");
const resultsEl = document.getElementById("results");

/* ---- Helpers ---- */
function civSlug(name) { return name.toLowerCase(); }
function civEmblemUrl(name) { return CIV_EMBLEM_BASE + civSlug(name) + ".png"; }

function formatUnitName(slug) {
    return slug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

/* ---- Render slots ---- */
function renderSlots(container, teamArr, teamColor) {
    container.innerHTML = "";
    for (let i = 0; i < MAX_PER_TEAM; i++) {
        const slot = document.createElement("div");
        const civ = teamArr[i];
        slot.className = "team-slot " + (civ ? "filled" : "empty");

        const img = document.createElement("img");
        img.className = "slot-emblem";
        img.src = civ ? civEmblemUrl(civ) : "";
        img.alt = civ || "Empty";
        if (!civ) img.style.visibility = "hidden";

        const label = document.createElement("span");
        label.className = "slot-label";
        label.textContent = civ || "Pick...";

        slot.appendChild(img);
        slot.appendChild(label);

        if (civ) {
            slot.addEventListener("click", () => {
                const idx = teamArr.indexOf(civ);
                if (idx !== -1) teamArr.splice(idx, 1);
                updateAll();
            });
        }
        container.appendChild(slot);
    }
}

/* ---- Render civ grids ---- */
function renderGrid(container, teamArr, otherArr) {
    container.innerHTML = "";
    CIVS.forEach(name => {
        const card = document.createElement("div");
        card.className = "civ-card";
        card.dataset.civ = name;

        const inThis = teamArr.includes(name);
        const inOther = otherArr.includes(name);
        const full = teamArr.length >= MAX_PER_TEAM;

        if (inThis) card.classList.add("selected");
        if (inOther || (full && !inThis)) card.classList.add("disabled");

        const img = document.createElement("img");
        img.className = "civ-emblem";
        img.src = civEmblemUrl(name);
        img.alt = name;
        img.loading = "lazy";

        const label = document.createElement("span");
        label.className = "civ-card-name";
        label.textContent = name;

        card.appendChild(img);
        card.appendChild(label);

        card.addEventListener("click", () => {
            if (inOther) return;
            if (inThis) {
                const idx = teamArr.indexOf(name);
                if (idx !== -1) teamArr.splice(idx, 1);
            } else if (!full) {
                teamArr.push(name);
            }
            updateAll();
        });

        container.appendChild(card);
    });
}

/* ---- Sync everything ---- */
function updateAll() {
    renderSlots(team1Slots, team1, "team1");
    renderSlots(team2Slots, team2, "team2");
    renderGrid(team1Grid, team1, team2);
    renderGrid(team2Grid, team2, team1);
    analyzeBtn.disabled = team1.length !== MAX_PER_TEAM || team2.length !== MAX_PER_TEAM;
    resultsEl.innerHTML = "";
}

/* ---- Initial render ---- */
updateAll();

/* ---- Analysis ---- */
analyzeBtn.addEventListener("click", async () => {
    resultsEl.innerHTML = '<div class="loading-indicator">Analyzing teams...</div>';
    analyzeBtn.disabled = true;

    const params = new URLSearchParams({
        team1: team1.join(","),
        team2: team2.join(","),
        stage: "cavalry",
    });

    try {
        const resp = await fetch("/api/team-analysis?" + params);
        if (!resp.ok) throw new Error("API error: " + resp.status);
        const data = await resp.json();
        renderResults(data);
    } catch (err) {
        resultsEl.innerHTML = `<div class="loading-indicator" style="color:var(--team1)">Error: ${err.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});

/* ---- Render results ---- */
function renderResults(data) {
    resultsEl.innerHTML = "";
    resultsEl.appendChild(buildStageCard(data));
}

function buildStageCard(data) {
    const card = document.createElement("div");
    card.className = "stage-card";

    // Header
    const header = document.createElement("div");
    header.className = "stage-header";

    const title = document.createElement("span");
    title.className = "stage-title";
    const stageLabels = { cavalry: "Cavalry Matchup", ranged: "Ranged Matchup", infantry: "Infantry Matchup" };
    title.textContent = stageLabels[data.stage] || data.stage;

    const adv = document.createElement("span");
    adv.className = "stage-advantage " + data.advantage;
    if (data.advantage === "team1") {
        adv.textContent = "Team 1 +" + data.advantage_margin.toFixed(1);
    } else if (data.advantage === "team2") {
        adv.textContent = "Team 2 +" + data.advantage_margin.toFixed(1);
    } else {
        adv.textContent = "Even";
    }

    header.appendChild(title);
    header.appendChild(adv);
    card.appendChild(header);

    // Columns
    const cols = document.createElement("div");
    cols.className = "stage-columns";
    cols.appendChild(buildTeamColumn("Team 1", "team1", data.team1));
    cols.appendChild(buildTeamColumn("Team 2", "team2", data.team2));
    card.appendChild(cols);

    // Footer — civs with no above-median units
    const t1Above = new Set(data.team1.above_median_units.map(u => u.civ));
    const t2Above = new Set(data.team2.above_median_units.map(u => u.civ));
    const t1Missing = data.team1.civs.filter(c => !t1Above.has(c));
    const t2Missing = data.team2.civs.filter(c => !t2Above.has(c));

    if (t1Missing.length || t2Missing.length) {
        const footer = document.createElement("div");
        footer.className = "stage-footer";
        const parts = [];
        if (t1Missing.length) parts.push("Team 1: " + t1Missing.join(", "));
        if (t2Missing.length) parts.push("Team 2: " + t2Missing.join(", "));
        footer.textContent = "No above-median cavalry: " + parts.join(" | ");
        card.appendChild(footer);
    }

    return card;
}

function buildTeamColumn(label, teamClass, teamData) {
    const col = document.createElement("div");

    const hdr = document.createElement("div");
    hdr.className = "stage-column-header " + teamClass;
    hdr.textContent = label + " (+" + teamData.total_delta.toFixed(1) + " total)";
    col.appendChild(hdr);

    if (teamData.above_median_units.length === 0) {
        const msg = document.createElement("div");
        msg.className = "no-units-msg";
        msg.textContent = "No above-median units in this category";
        col.appendChild(msg);
        return col;
    }

    teamData.above_median_units.forEach(unit => {
        const entry = document.createElement("div");
        entry.className = "unit-entry";

        const img = document.createElement("img");
        img.className = "civ-emblem";
        img.src = civEmblemUrl(unit.civ);
        img.alt = unit.civ;

        const info = document.createElement("div");
        info.className = "unit-entry-info";
        info.innerHTML = `<div class="unit-entry-name">${formatUnitName(unit.unit_slug)}</div>`
            + `<div class="unit-entry-civ">${unit.civ}</div>`;

        const stats = document.createElement("div");
        stats.className = "unit-entry-stats";
        stats.innerHTML = `<div class="unit-entry-score">${unit.score.toFixed(1)}</div>`
            + `<div class="unit-entry-meta">Rank #${unit.rank} | +${unit.median_delta.toFixed(1)}</div>`;

        entry.appendChild(img);
        entry.appendChild(info);
        entry.appendChild(stats);
        col.appendChild(entry);
    });

    return col;
}
