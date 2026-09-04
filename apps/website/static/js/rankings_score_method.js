(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.RankingsScoreMethod = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const V3_SETTING =
        "Full Imperial upgrades · equal resources · food, wood, and gold valued " +
        "1:1:1 · 27-unit cap · five seeded runs for every matchup.";
    const HP_RESULT =
        "A win records the winning army's remaining HP percentage; a loss records " +
        "the negative of the opponent's remaining HP percentage; a draw records 0. " +
        "The five seeded results are averaged.";

    const METHODS = {
        infantry: {
            title: "Infantry score",
            setting: V3_SETTING,
            formula: [
                ["75%", "Average of the Champion, Paladin, and Arbalester matchups"],
                ["10%", "Paladin matchup"],
                ["15%", "Average of the Halberdier, Elite Skirmisher, and Hussar matchups"],
            ],
            result: HP_RESULT,
            finish:
                "Each matchup group is normalized from 0–100 across all Infantry entries before the weights are applied. The weighted result is normalized once more to produce the displayed score.",
        },
        archery: {
            title: "Ranged score",
            setting: V3_SETTING,
            formula: [
                ["70%", "Average of the Champion, Paladin, and Arbalester matchups"],
                ["30%", "Arbalester matchup"],
            ],
            result: HP_RESULT,
            adjustment:
                "The weighted result is multiplied by movement speed and (range + 1).",
            finish:
                "Each matchup group is normalized from 0–100 across all Ranged entries before weighting. After the movement and range adjustment, the result is normalized again to produce the displayed score.",
        },
        stable: {
            title: "Stable score",
            setting: V3_SETTING,
            formula: [
                ["70%", "Average of the Champion, Paladin, and Arbalester matchups"],
                ["30%", "Paladin matchup"],
            ],
            result: HP_RESULT,
            adjustment: "The weighted result is multiplied by movement speed.",
            finish:
                "Each matchup group is normalized from 0–100 across all Stable entries before weighting. After the speed adjustment, the result is normalized again to produce the displayed score.",
        },
        siege: {
            title: "Siege score",
            setting:
                "Full Imperial upgrades · attacks against Persian, Byzantine, and Teuton Castles · both fixed-count and 5,000-resource tests.",
            formula: [
                ["40%", "Persian Castle results"],
                ["40%", "Byzantine Castle results"],
                ["20%", "Teuton Castle results"],
            ],
            adjustment:
                "Each Castle's weight is split equally between its fixed-count and 5,000-resource tests.",
            result:
                "Each test records the effective time needed to destroy the Castle. If the attackers lose, the Castle damage they completed is used to assign an effective time.",
            finish:
                "The result uses effective time to destroy the Castle; units that lose receive credit for partial Castle damage. Lower time is better, then results are normalized from 0–100 across all Siege entries of the same age. Movement speed is not added.",
        },
        naval: {
            title: "Naval score",
            setting:
                "Full Imperial upgrades · both 30 vs 30 and 3,000 equal-resource tests against every opponent.",
            formula: [
                ["33⅓%", "Britons Galleon matchup"],
                ["33⅓%", "Britons Fast Fire Ship matchup"],
                ["33⅓%", "Sicilians Carrack (Hulk-line) matchup"],
            ],
            adjustment:
                "For each opponent, the 30 vs 30 and 3,000-resource results are averaged. Movement speed is then applied.",
            result:
                "A win records the winning fleet's remaining HP percentage; a loss records the negative of the opponent's remaining HP percentage; a draw records 0.",
            finish:
                "The three opponent results are averaged equally and normalized from 0–100 within each Naval line.",
        },
    };

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
