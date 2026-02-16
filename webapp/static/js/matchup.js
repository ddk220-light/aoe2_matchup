/* ==========================================================================
   AoE2 Unit Analyzer - Matchup Advisor Page Logic
   Depends on: constants.js (ICON_BASE, NAME_TO_ICON, CIV_EMBLEM_BASE, getIconUrl)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- Icon / badge helpers ---- */
function unitBadge(name, size) {
    size = size || "normal";
    const url = getIconUrl(name);
    const cls = size === "sm" ? "sm" : "";
    const px = size === "sm" ? 28 : 48;
    const img = url
        ? `<img src="${url}" class="unit-icon ${cls}" width="${px}" height="${px}" alt="${name}" onerror="this.style.display='none'">`
        : '';
    return `<span class="unit-badge">${img}<span class="unit-name ${cls}">${name}</span></span>`;
}

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

/* ---- Analysis flow ---- */
analyzeBtn.addEventListener("click", async () => {
    const c1 = selectedCiv1, c2 = selectedCiv2;
    if (!c1 || !c2 || c1 === c2) return;
    analyzeBtn.disabled = true;

    // Show skeleton immediately
    showSkeleton(c1, c2);

    try {
        // Fast call: phases 1-3
        const analysis = await fetch(
            `/api/matchup-advisor/analysis/${encodeURIComponent(c1)}/${encodeURIComponent(c2)}`
        ).then(r => { if (!r.ok) throw new Error("Analysis failed"); return r.json(); });

        renderAnalysis(analysis);

        // Slow call: phase 4 army (don't block)
        fetch(`/api/matchup-advisor/army/${encodeURIComponent(c1)}/${encodeURIComponent(c2)}`)
            .then(r => r.json())
            .then(army => renderArmy(army, analysis))
            .catch(e => {
                document.querySelectorAll(".army-loading").forEach(el => {
                    el.innerHTML = `<div class="no-data">Army simulation failed: ${e.message}</div>`;
                });
            });
    } catch (e) {
        resultsEl.innerHTML = `<div class="no-data">Error: ${e.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});

/* ---- Skeleton ---- */
function showSkeleton(c1, c2) {
    resultsEl.className = "results-container visible";
    resultsEl.innerHTML = `
        <div class="matchup-header">
            <h2><span class="civ1-color">${c1}</span> <span style="color:var(--text-muted)">vs</span> <span class="civ2-color">${c2}</span></h2>
        </div>
        <div class="loading-spinner">
            <div class="spinner"></div>
            <div>Running strategic analysis...</div>
        </div>`;
}

/* ---- Render phases 1-3 ---- */
function renderAnalysis(data) {
    const ages = Object.keys(data.ages);
    let tabsHtml = '';
    let contentsHtml = '';

    ages.forEach((ageKey, idx) => {
        const age = data.ages[ageKey];
        const active = idx === 0 ? " active" : "";
        tabsHtml += `<div class="age-tab${active}" onclick="switchAge('${ageKey}')">${age.age_name}</div>`;
        contentsHtml += `<div id="age-${ageKey}" class="age-content${active}">`;

        if (age.error) {
            contentsHtml += `<div class="no-data">${age.error}</div>`;
        } else {
            contentsHtml += renderAgeAnalysis(data, ageKey, age);
        }
        contentsHtml += `</div>`;
    });

    resultsEl.innerHTML = `
        <div class="matchup-header">
            <h2><span class="civ1-color">${data.civ1}</span> <span style="color:var(--text-muted)">vs</span> <span class="civ2-color">${data.civ2}</span></h2>
        </div>
        <div class="age-tab-bar">${tabsHtml}</div>
        ${contentsHtml}`;
}

function switchAge(ageKey) {
    document.querySelectorAll(".age-tab").forEach((t, i) => {
        t.classList.toggle("active", t.textContent.toLowerCase().includes(ageKey));
    });
    document.querySelectorAll(".age-content").forEach(c => {
        c.classList.toggle("active", c.id === "age-" + ageKey);
    });
}

function renderAgeAnalysis(data, ageKey, age) {
    let html = '';

    // --- 3-column analysis ---
    const p1 = age.phase1_mobile;
    const p2 = age.phase2_ranged;
    const bm = age.best_mobile;
    const bMelee = age.best_melee;

    const domCiv = p1.dominant_civ;
    const weakerCiv = domCiv === "civ1" ? "civ2" : "civ1";
    const domName = domCiv === "civ1" ? data.civ1 : data.civ2;
    const weakerName = weakerCiv === "civ1" ? data.civ1 : data.civ2;
    const domColor = domCiv === "civ1" ? "civ1-color" : "civ2-color";
    const weakerColor = weakerCiv === "civ1" ? "civ1-color" : "civ2-color";

    html += `<div class="analysis-columns">`;

    // Column 1: Mobile Dominance
    html += `<div class="analysis-col">`;
    html += `<div class="col-header">Mobile Control</div>`;
    if (domCiv && p1.dominant_unit) {
        html += `<div class="col-civ ${domColor}">${domName}</div>`;
        html += unitBadge(p1.dominant_unit.name);
        const hasBothMobile = p1.civ1_units.length > 0 && p1.civ2_units.length > 0;
        if (!hasBothMobile) {
            html += `<div class="col-detail">${weakerName} has no mobile units (speed &gt; 1.3)</div>`;
        } else {
            html += `<div class="col-detail">Wins/draws all mobile matchups</div>`;
        }
    } else {
        html += `<div class="no-unit">Neither civ has clear mobile advantage</div>`;
    }
    html += `</div>`;

    // Column 2: Ranged Power (show both civs' best ranged, highlight winner)
    html += `<div class="analysis-col">`;
    html += `<div class="col-header">Ranged Power</div>`;
    const rw = p2.ranged_winner;
    const c1r = p2.civ1_best_ranged;
    const c2r = p2.civ2_best_ranged;
    if (rw) {
        const rangedWinnerName = rw === "civ1" ? data.civ1 : data.civ2;
        const rangedWinnerColor = rw === "civ1" ? "civ1-color" : "civ2-color";
        const rangedUnit = rw === "civ1" ? c1r : c2r;
        html += `<div class="col-civ ${rangedWinnerColor}">${rangedWinnerName}</div>`;
        if (rangedUnit) html += unitBadge(rangedUnit.name);
        if (rw === domCiv) {
            html += `<div class="col-detail">${rangedWinnerName} dominates both mobile and ranged &mdash; ${weakerName} should focus on melee + siege</div>`;
        } else {
            html += `<div class="col-detail">Clear ranged advantage &mdash; beats all opponent ranged</div>`;
        }
    } else if (c1r || c2r) {
        html += `<div class="col-detail">Ranged is contested</div>`;
        if (c1r) {
            html += `<div style="margin-top:6px"><span class="civ1-color">${data.civ1}:</span> ${unitBadge(c1r.name, "sm")}</div>`;
        }
        if (c2r) {
            html += `<div style="margin-top:4px"><span class="civ2-color">${data.civ2}:</span> ${unitBadge(c2r.name, "sm")}</div>`;
        }
    } else {
        html += `<div class="no-unit">No ranged gold units available</div>`;
    }
    html += `</div>`;

    // Column 3: Best Melee
    html += `<div class="analysis-col">`;
    html += `<div class="col-header">Melee Anchor</div>`;
    // Show the weaker civ's best melee (for combo building), or if both useful show both
    const weakerMelee = bMelee[weakerCiv];
    const domMelee = bMelee[domCiv];
    if (weakerMelee) {
        html += `<div class="col-civ ${weakerColor}">${weakerName}</div>`;
        html += unitBadge(weakerMelee.name);
        html += `<div class="col-detail">Highest score against all ${domName} units</div>`;
    } else if (domMelee) {
        html += `<div class="col-civ ${domColor}">${domName}</div>`;
        html += unitBadge(domMelee.name);
        html += `<div class="col-detail">Best melee option for army combo</div>`;
    } else {
        html += `<div class="no-unit">No melee units available</div>`;
    }
    html += `</div>`;

    html += `</div>`; // end analysis-columns

    // --- Best combo placeholder (filled by renderArmy after sims) ---
    html += `<div id="best-combo-${ageKey}">
        <div class="combo-section-header">Best Army Combo</div>
        <div class="loading-spinner" style="padding:16px">
            <div class="spinner"></div>
            <div>Simulating army battles to find the best combo...</div>
        </div>
    </div>`;

    // --- Combos under consideration ---
    const p3 = age.phase3_combos;
    html += `<div class="combo-section-header" style="font-size:1rem;color:var(--text-muted);margin-top:20px">Combos Under Consideration</div>`;
    html += `<div class="alt-combos-grid">`;

    // Civ1 combos
    html += `<div>`;
    for (const c of p3.civ1) {
        html += `<div class="alt-combo-row civ1-alt">
            <span class="alt-label civ1-color">${data.civ1}:</span>
            ${unitBadge(c.primary.name, "sm")}
            <span class="combo-plus" style="font-size:0.85rem">+</span>
            ${unitBadge(c.secondary.name, "sm")}
        </div>`;
    }
    html += `</div>`;

    // Civ2 combos
    html += `<div>`;
    for (const c of p3.civ2) {
        html += `<div class="alt-combo-row civ2-alt">
            <span class="alt-label civ2-color">${data.civ2}:</span>
            ${unitBadge(c.primary.name, "sm")}
            <span class="combo-plus" style="font-size:0.85rem">+</span>
            ${unitBadge(c.secondary.name, "sm")}
        </div>`;
    }
    html += `</div>`;
    html += `</div>`; // end alt-combos-grid

    // --- Army section placeholder ---
    html += `<div class="army-section" id="army-${ageKey}">
        <div class="army-section-header">Army Battle Simulation</div>
        <div class="army-loading">
            <div class="loading-spinner">
                <div class="spinner"></div>
                <div>Running army simulations (5000 resources, testing splits)...</div>
            </div>
        </div>
    </div>`;

    return html;
}

/* ---- Render phase 4 (army) ---- */
function renderArmy(armyData, analysisData) {
    for (const ageKey of Object.keys(armyData.ages)) {
        const age = armyData.ages[ageKey];
        if (age.error) {
            const bc = document.getElementById("best-combo-" + ageKey);
            if (bc) bc.innerHTML = `<div class="combo-section-header">Best Army Combo</div><div class="no-data">${age.error}</div>`;
            const ac = document.getElementById("army-" + ageKey);
            if (ac) ac.innerHTML = `<div class="army-section-header">Army Battle Simulation</div><div class="no-data">${age.error}</div>`;
            continue;
        }

        const combos = age.combos;
        const best = age.best_combo;
        const counters = age.counters;
        const grid = age.combo_grid;

        // --- Fill best combo placeholder ---
        const bestComboEl = document.getElementById("best-combo-" + ageKey);
        if (bestComboEl) {
            let bhtml = `<div class="combo-section-header">Best Army Combo</div>`;
            bhtml += `<div class="combo-cards">`;

            const c1best = combos.civ1[best.civ1.combo_id];
            if (c1best) {
                bhtml += `<div class="combo-card civ1-card">
                    <div>
                        <div class="combo-civ-name civ1-color">${armyData.civ1}</div>
                        <div class="combo-units-row">
                            ${unitBadge(c1best.primary.name, "sm")}
                            <span class="combo-plus">+</span>
                            ${unitBadge(c1best.secondary.name, "sm")}
                        </div>
                        <div class="combo-reasoning">${best.civ1.wins}W ${best.civ1.losses}L ${best.civ1.draws}D &mdash; ${Math.round(c1best.best_split[0]*100)}/${Math.round(c1best.best_split[1]*100)} split</div>
                    </div>
                </div>`;
            }

            const c2best = combos.civ2[best.civ2.combo_id];
            if (c2best) {
                bhtml += `<div class="combo-card civ2-card">
                    <div>
                        <div class="combo-civ-name civ2-color">${armyData.civ2}</div>
                        <div class="combo-units-row">
                            ${unitBadge(c2best.primary.name, "sm")}
                            <span class="combo-plus">+</span>
                            ${unitBadge(c2best.secondary.name, "sm")}
                        </div>
                        <div class="combo-reasoning">${best.civ2.wins}W ${best.civ2.losses}L ${best.civ2.draws}D &mdash; ${Math.round(c2best.best_split[0]*100)}/${Math.round(c2best.best_split[1]*100)} split</div>
                    </div>
                </div>`;
            }

            bhtml += `</div>`;
            bestComboEl.innerHTML = bhtml;
        }

        // --- Fill army section ---
        const container = document.getElementById("army-" + ageKey);
        if (!container) continue;

        let html = `<div class="army-section-header">Army Battle Simulation</div>`;

        // Explanation
        html += `<div class="army-explanation">
            Each side gets <strong>5000 resources</strong> to build a mixed army of their 2-unit combo.
            We test 5 resource splits (70/30 to 30/70) for each side and simulate the battle.
            The best split for each combo is the one that wins or survives with the most HP across all opponent splits.
            Each combo pair is tested at 25 split combinations to find the optimal ratio.
        </div>`;

        // Per-civ best combo detail cards
        html += `<div class="army-best-results">`;

        const c1best = combos.civ1[best.civ1.combo_id];
        if (c1best) {
            html += `<div class="army-best-card civ1-card">
                <div class="best-civ-name civ1-color">${armyData.civ1}</div>
                <div class="best-combo-detail">
                    ${unitBadge(c1best.primary.name, "sm")}
                    <span class="combo-plus">+</span>
                    ${unitBadge(c1best.secondary.name, "sm")}
                </div>
                <div class="best-record">Record: ${best.civ1.wins}W ${best.civ1.losses}L ${best.civ1.draws}D across all opponent combos</div>
                <div class="best-split">Best split: ${Math.round(c1best.best_split[0]*100)}/${Math.round(c1best.best_split[1]*100)} resources</div>`;
            if (counters.civ1_countered_by) {
                const cb = counters.civ1_countered_by;
                html += `<div class="best-countered">Countered by: ${unitBadge(cb.primary, "sm")} + ${unitBadge(cb.secondary, "sm")}</div>`;
            }
            html += `</div>`;
        }

        const c2best = combos.civ2[best.civ2.combo_id];
        if (c2best) {
            html += `<div class="army-best-card civ2-card">
                <div class="best-civ-name civ2-color">${armyData.civ2}</div>
                <div class="best-combo-detail">
                    ${unitBadge(c2best.primary.name, "sm")}
                    <span class="combo-plus">+</span>
                    ${unitBadge(c2best.secondary.name, "sm")}
                </div>
                <div class="best-record">Record: ${best.civ2.wins}W ${best.civ2.losses}L ${best.civ2.draws}D across all opponent combos</div>
                <div class="best-split">Best split: ${Math.round(c2best.best_split[0]*100)}/${Math.round(c2best.best_split[1]*100)} resources</div>`;
            if (counters.civ2_countered_by) {
                const cb = counters.civ2_countered_by;
                html += `<div class="best-countered">Countered by: ${unitBadge(cb.primary, "sm")} + ${unitBadge(cb.secondary, "sm")}</div>`;
            }
            html += `</div>`;
        }

        html += `</div>`; // end army-best-results

        // Full grid (collapsible)
        if (grid.length > 0) {
            const gridId = "army-grid-" + ageKey;
            html += `<button class="army-grid-toggle" onclick="document.getElementById('${gridId}').style.display = document.getElementById('${gridId}').style.display === 'none' ? 'block' : 'none'">
                Show/Hide All ${grid.length} Matchup Results
            </button>`;
            html += `<div class="army-full-grid" id="${gridId}" style="display:none">`;
            for (const g of grid) {
                const c1c = combos.civ1[g.civ1_combo_id];
                const c2c = combos.civ2[g.civ2_combo_id];
                if (!c1c || !c2c) continue;
                const winCls = g.winner === "civ1" ? "civ1-win" : g.winner === "civ2" ? "civ2-win" : "draw-result";
                const winLabel = g.winner === "civ1" ? armyData.civ1 : g.winner === "civ2" ? armyData.civ2 : "Draw";
                html += `<div class="army-result-row">
                    <div class="combo-desc">
                        <span class="civ1-color">${c1c.primary.name}+${c1c.secondary.name}</span>
                        <span style="color:var(--text-dim)"> (${g.counts_civ1[0]}+${g.counts_civ1[1]}) vs </span>
                        <span class="civ2-color">${c2c.primary.name}+${c2c.secondary.name}</span>
                        <span style="color:var(--text-dim)"> (${g.counts_civ2[0]}+${g.counts_civ2[1]})</span>
                    </div>
                    <span class="army-winner ${winCls}">${winLabel}</span>
                </div>`;
            }
            html += `</div>`;
        }

        container.innerHTML = html;
    }
}
