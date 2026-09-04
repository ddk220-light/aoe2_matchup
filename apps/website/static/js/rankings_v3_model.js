(function (root, factory) {
    const model = factory();
    if (typeof module === "object" && module.exports) module.exports = model;
    root.RankingsV3Model = model;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const SPECIAL_COLUMNS = [
        { key: "dps", label: "DPS", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_hp", label: "HP", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_attack", label: "Atk", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "armor_combined", label: "M/P Arm", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_range", label: "Range", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_speed", label: "Speed", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "special_abilities", label: "Special", expandable: "Special" },
    ];

    function buildTableColumns({ showLine = false } = {}) {
        return [
            { key: "civ_name", label: "Civ" },
            { key: "unit_name", label: "Unit" },
            ...(showLine ? [{ key: "line_slug", label: "Line" }] : []),
            {
                key: "ranking_score",
                label: "Score",
                info: "Equal-resource combat score. Higher is better.",
            },
            { key: "ranking_rank", label: "Rank", info: "Rank within this unit line." },
            {
                key: "ranking_median_delta",
                label: "vs Median",
                info: "Score difference from the median unit in this line.",
            },
            { key: "total_cost", label: "Cost" },
            ...SPECIAL_COLUMNS,
        ];
    }

    function buildBreakdown(row) {
        const breakdown = (row && row.ranking_breakdown) || {};
        const roles = breakdown.roles || {};
        return {
            roles: ["GC", "AC", "AT", "AA"]
                .filter((label) => roles[label] !== undefined && roles[label] !== null)
                .map((label) => ({ label, score: roles[label] })),
            yardsticks: Array.isArray(breakdown.yardsticks)
                ? breakdown.yardsticks.filter((item) => item && item.score !== undefined && item.score !== null)
                : [],
        };
    }

    function enrichRankingFields(row) {
        const breakdown = buildBreakdown(row);
        const enriched = { ...row };
        for (const role of breakdown.roles) {
            enriched[`ranking_role_${role.label.toLowerCase()}`] = role.score;
        }
        for (const yardstick of breakdown.yardsticks) {
            enriched[`ranking_vs_${yardstick.key}`] = yardstick.score;
        }
        return enriched;
    }

    function buildCsvColumns() {
        return [
            { key: "_rank", label: "Display Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "line_slug", label: "Line" },
            { key: "is_unique", label: "Is Unique" },
            { key: "ranking_score_type", label: "Score Type" },
            { key: "ranking_score", label: "Score" },
            { key: "ranking_rank", label: "Line Rank" },
            { key: "ranking_median_delta", label: "vs Median" },
            { key: "ranking_role_gc", label: "GC" },
            { key: "ranking_role_ac", label: "AC" },
            { key: "ranking_role_at", label: "AT" },
            { key: "ranking_role_aa", label: "AA" },
            { key: "ranking_vs_champion", label: "vs Champion" },
            { key: "ranking_vs_paladin", label: "vs Paladin" },
            { key: "ranking_vs_arbalester", label: "vs Arbalester" },
            { key: "ranking_vs_halberdier", label: "vs Halberdier" },
            { key: "ranking_vs_elite_skirmisher", label: "vs Elite Skirmisher" },
            { key: "ranking_vs_hussar", label: "vs Hussar" },
            { key: "total_cost", label: "Total Cost" },
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_range", label: "Range" },
            { key: "final_speed", label: "Speed" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
            { key: "special_abilities", label: "Special" },
        ];
    }

    return {
        buildBreakdown,
        buildCsvColumns,
        buildTableColumns,
        enrichRankingFields,
    };
});
