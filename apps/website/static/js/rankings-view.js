function buildRankingScoreHoverHtml(row) {
    const score = row.ranking_score;
    const breakdown = RankingsV3Model.buildBreakdown(row);
    let html = `<div class="hc-title">${row.unit_name || row.unit_slug} — Score</div>`;
    html += `<div class="ranking-score-summary">`;
    html += `<span class="ranking-score-value" style="color:${scoreColor(score)}">${score == null ? "—" : Number(score).toFixed(1)}</span>`;
    if (row.ranking_rank != null) html += `<span>#${row.ranking_rank} in line</span>`;
    if (row.ranking_median_delta != null) {
        const delta = Number(row.ranking_median_delta);
        html += `<span>${delta >= 0 ? "+" : ""}${delta.toFixed(1)} vs median</span>`;
    }
    html += `</div>`;

    if (breakdown.roles.length) {
        html += `<div class="ranking-breakdown-label">Role scores</div>`;
        html += `<div class="ranking-role-grid">`;
        for (const role of breakdown.roles) {
            html += `<span><strong>${role.label}</strong>${Number(role.score).toFixed(1)}</span>`;
        }
        html += `</div>`;
    }

    if (breakdown.yardsticks.length) {
        html += `<div class="ranking-breakdown-label">Equal-resource yardsticks</div>`;
        html += `<div class="ranking-yardstick-grid">`;
        for (const yardstick of breakdown.yardsticks) {
            html += `<span>${yardstick.label}</span><strong style="color:${scoreColor(yardstick.score)}">${Number(yardstick.score).toFixed(1)}</strong>`;
        }
        html += `</div>`;
        html += `<div class="hc-note">Simulation V3 · five seeded runs · 27-unit cap · food, wood, and gold weighted 1:1:1.</div>`;
    } else {
        html += `<div class="hc-note">This line uses its published cost-based score. Detailed V3 yardsticks will appear when that campaign is available.</div>`;
    }
    return html;
}

function buildScoreHoverHtml(row, scoreKey, dataKey) {
    dataKey = dataKey || scoreKey;
    if (scoreKey === "ranking_score") return buildRankingScoreHoverHtml(row);
    const info = SCORE_BREAKDOWN[scoreKey];
    if (!info) {
        // Composite score hover cards.
        // `parts` show the component values stored in the DB (already
        // post-processed by their own speed-weighting). `formula` describes
        // how the displayed Score is computed from those components and
        // what additional weighting is applied — the math will NOT add up
        // by simple weighted-sum of `parts`, because the score is
        // re-normalized to 0-100 after each weighting step. The note line
        // explains what extra weighting/normalization happens.
        const composites = {
            militia_value: {
                title: "Overall Score",
                formula: "0.75 \u00d7 General Combat + 0.10 \u00d7 Anti-Cav + 0.15 \u00d7 Anti-Trash",
                note: "Final score is then multiplied by movement speed and re-normalized 0-100 across the entire infantry pool (militia, spear, shock).",
                parts: [
                    { key: "general_combat", label: "General Combat" },
                    { key: "anti_cav", label: "Anti-Cav" },
                    { key: "anti_trash", label: "Anti-Trash" },
                ],
            },
            ranged_effectiveness: {
                title: "Ranged Effectiveness Score",
                formula: "0.70 \u00d7 General Combat + 0.30 \u00d7 Anti-Archer",
                note: "Components are speed-weighted (pool) before combining; final score is then multiplied by attack range and re-normalized 0-100 across all ranged units (archer, skirmisher, cav archer, scorpion, gunpowder).",
                parts: [
                    { key: "general_combat", label: "General Combat (speed-weighted)" },
                    { key: "anti_archer", label: "Anti-Archer (speed-weighted)" },
                ],
            },
            stable_effectiveness: {
                title: "Stable Effectiveness",
                formula: "0.70 \u00d7 General Combat + 0.30 \u00d7 Anti-Cav",
                note: "Final score is multiplied by movement speed and re-normalized 0-100 globally across all stable units (knight, light cav, camel, steppe lancer, elephant).",
                parts: [
                    { key: "general_combat", label: "General Combat" },
                    { key: "anti_cav", label: "Anti-Cav" },
                ],
            },
        };
        const comp = composites[scoreKey];
        if (comp) {
            let html = `<div class="hc-title">${comp.title}</div>`;
            html += `<div class="hc-formula">${comp.formula}</div>`;
            for (const p of comp.parts) {
                const v = row[p.key];
                const vs =
                    v !== undefined && v > -999
                        ? v.toFixed(1)
                        : "\u2014";
                html += `<div class="hc-row"><span>${p.label}</span><span style="color:${scoreColor(v)}">${vs}</span></div>`;
            }
            const total = row[dataKey];
            html += `<div class="hc-row total"><span>Score</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "\u2014"}</span></div>`;
            if (comp.note) {
                html += `<div class="hc-note" style="margin-top:6px;font-size:0.85em;opacity:0.75;line-height:1.3">${comp.note}</div>`;
            }
            return html;
        }
        return "";
    }
    let html = `<div class="hc-title">${info.title}</div>`;
    if (info.subs === "siege_breakdown") {
        html += `<div class="hc-formula">${info.formula}</div>`;
        html += _buildSiegeBreakdownHtml(row);
        const total = row[dataKey];
        html += `<div class="hc-row total"><span>Score</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "—"}</span></div>`;
        return html;
    }
    html += `<div class="hc-formula">${info.formula}</div>`;
    for (const sub of info.subs) {
        const v = row[sub.key];
        const vs =
            v !== undefined && v > -999 ? v.toFixed(1) : "\u2014";
        html += `<div class="hc-row"><span>${sub.label}</span><span style="color:${scoreColor(v)}">${vs}</span></div>`;
        if (sub.civ && sub.slug) {
            const simUrl = buildSimUrl(
                row.civ_name,
                row.unit_slug,
                sub.civ,
                sub.slug,
                sub.mode,
                sub.res,
                sub.count,
            );
            html += `<a class="hc-sim-link" href="${simUrl}" target="_blank">Run in Battle Sim \u2192</a>`;
        }
    }
    const total = row[dataKey];
    html += `<div class="hc-row total"><span>Result</span><span style="color:${scoreColor(total)}">${total !== undefined ? total.toFixed(1) : "\u2014"}</span></div>`;
    return html;
}
