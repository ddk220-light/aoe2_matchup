(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.RankingsScoreMethod = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const METHODS = globalThis.RANKING_METHODS?.methods || {};

    function getMethod(category) {
        return METHODS[category] || null;
    }

    function buildHtml(category) {
        const method = getMethod(category);
        if (!method) return "";

        const matchupRows = method.formula
            .map(
                ([weight, matchup]) =>
                    `<div class="score-method-row"><strong>${weight}</strong><span>${matchup}</span></div>`,
            )
            .join("");
        const adjustment = method.adjustment
            ? `<div class="score-method-adjustment">${method.adjustment}</div>`
            : "";

        return `<div class="hc-title">${method.title}: how it is calculated</div>
            <div class="score-method-label">Battle setting</div>
            <div class="score-method-setting">${method.setting}</div>
            <div class="score-method-label">Matchups and weights</div>
            <div class="score-method-rows">${matchupRows}</div>
            ${adjustment}
            <div class="score-method-label">From battle result to score</div>
            <div class="score-method-setting">${method.result}</div>
            <div class="hc-note score-method-note">${method.finish} Higher is better.</div>`;
    }

    return { buildHtml, getMethod };
});
