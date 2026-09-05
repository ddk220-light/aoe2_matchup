export function createTeamState() {
const RELIC_MAX = 0;
return {
    1: {
        civ: null,
        age: "Imperial",
        unitSlug: null,
        unitName: null,
        civData: null,
        relics: RELIC_MAX,
        startKills: 0,
    },
    2: {
        civ: null,
        age: "Imperial",
        unitSlug: null,
        unitName: null,
        civData: null,
        relics: RELIC_MAX,
        startKills: 0,
    },
};


}
export function readBattleOptions(teamState, seed) {
    const s1 = teamState[1];
    const s2 = teamState[2];
    const armyMode = document.querySelector(
        'input[name="armyMode"]:checked',
    )?.value || "resources";
    const teams = [
        { civ: s1.civ, unit_slug: s1.unitSlug, age: s1.age },
        { civ: s2.civ, unit_slug: s2.unitSlug, age: s2.age },
    ];
    let army;
    if (armyMode === "resources") {
        const budgets = ["team1Resources", "team2Resources"].map((id) => {
            const input = document.getElementById(id);
            const value = Math.max(1, parseInt(input.value, 10) || 5000);
            input.value = String(value);
            return value;
        });
        army = {
            mode: "resource_budgets",
            budgets,
            weights: { food: 1, wood: 1, gold: 1 },
            cap: 27,
        };
    } else {
        const counts = ["team1Count", "team2Count"].map((id) => {
            const input = document.getElementById(id);
            const value = Math.min(27, Math.max(1,
                parseInt(input.value, 10) || 27));
            input.value = String(value);
            return value;
        });
        teams[0].count = counts[0];
        teams[1].count = counts[1];
        army = { mode: "explicit", cap: 27 };
    }
    return {
        teams,
        army,
        engagement_mode: document.getElementById("rangedBuffer")?.checked
            ? "ranged_buffer"
            : "direct",
        seed,
    };
}
