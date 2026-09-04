const assert = require("node:assert/strict");
const test = require("node:test");

const model = require("../apps/website/static/js/rankings_v3_model.js");

test("the rankings table uses one uniform final-score column set", () => {
    const aggregate = model.buildTableColumns({ showLine: true });
    const individual = model.buildTableColumns({ showLine: false });

    assert.deepEqual(
        aggregate.map((column) => column.key),
        [
            "civ_name",
            "unit_name",
            "line_slug",
            "ranking_score",
            "ranking_rank",
            "ranking_median_delta",
            "total_cost",
            "dps",
            "final_hp",
            "final_attack",
            "armor_combined",
            "final_range",
            "final_speed",
            "special_abilities",
        ],
    );
    assert.deepEqual(
        individual.map((column) => column.key),
        aggregate.filter((column) => column.key !== "line_slug").map((column) => column.key),
    );
    assert.equal(aggregate.find((column) => column.key === "ranking_score").label, "Score");
});

test("the V3 breakdown exposes role and six yardstick results", () => {
    const row = {
        ranking_breakdown: {
            roles: { GC: 86.4, AC: 64.3, AT: 90.6, AA: 60.8 },
            yardsticks: [
                { key: "champion", label: "Champion", score: 86.5 },
                { key: "paladin", label: "Paladin", score: 64.3 },
                { key: "arbalester", label: "Arbalester", score: 60.8 },
                { key: "halberdier", label: "Halberdier", score: 95.6 },
                { key: "elite_skirmisher", label: "Elite Skirmisher", score: 94.0 },
                { key: "hussar", label: "Hussar", score: 79.2 },
            ],
        },
    };

    const breakdown = model.buildBreakdown(row);

    assert.deepEqual(breakdown.roles.map((item) => item.label), ["GC", "AC", "AT", "AA"]);
    assert.deepEqual(
        breakdown.yardsticks.map((item) => item.label),
        ["Champion", "Paladin", "Arbalester", "Halberdier", "Elite Skirmisher", "Hussar"],
    );
});

test("CSV export keeps one cost-based score and the V3 details", () => {
    const keys = model.buildCsvColumns().map((column) => column.key);

    assert.deepEqual(keys.slice(0, 9), [
        "_rank",
        "civ_name",
        "unit_name",
        "line_slug",
        "is_unique",
        "ranking_score_type",
        "ranking_score",
        "ranking_rank",
        "ranking_median_delta",
    ]);
    assert(keys.includes("ranking_role_gc"));
    assert(keys.includes("ranking_vs_paladin"));
    assert(!keys.some((key) => key.startsWith("pool_")));
});
