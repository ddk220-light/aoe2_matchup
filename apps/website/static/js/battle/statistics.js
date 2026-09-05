import { summarizeMatchup } from "/v3-runtime/src/combat/matchup-summary.js";
export function createStatisticsView({getBattle, setBattle, getPageSim, unitImages, unitIsSprite, setSimPhase}) {
// ===== LIVE STAT READOUT =====
function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function formatCombatMetric(value, suffix = "") {
    if (!Number.isFinite(value)) return "—";
    const rounded = Math.round(value * 10) / 10;
    return `${rounded.toFixed(Number.isInteger(rounded) ? 0 : 1)}${suffix}`;
}

function updateHealthBar(teamNum, hp, startingHp) {
    const fraction = startingHp > 0
        ? Math.max(0, Math.min(1, hp / startingHp))
        : 0;
    const fill = document.getElementById(`prog${teamNum}HealthFill`);
    const track = document.getElementById(`prog${teamNum}HealthTrack`);
    if (fill) fill.style.width = `${(fraction * 100).toFixed(2)}%`;
    if (track) {
        track.setAttribute("aria-valuenow", String(Math.round(fraction * 100)));
        track.setAttribute(
            "aria-valuetext",
            `${Math.round(hp)} of ${Math.round(startingHp)} HP remaining`,
        );
    }
}

function renderCallouts(teamNum, callouts) {
    const list = document.getElementById(`prog${teamNum}Callouts`);
    if (!list) return;
    list.replaceChildren();
    for (const text of callouts) {
        const item = document.createElement("li");
        item.textContent = text;
        list.append(item);
    }
    list.hidden = callouts.length === 0;
}

function unitCost(mechanics) {
    const cost = mechanics.cost;
    return cost.food + cost.wood + cost.gold;
}

function battleStatsFromConfig(config) {
    const [team1, team2] = config.teams;
    const team1Cost = unitCost(team1.mechanics);
    const team2Cost = unitCost(team2.mechanics);
    return {
        team1_civ: team1.civ,
        team1_unit: team1.unit_slug,
        team1_unit_name: team1.unit_name,
        team1_count: team1.count,
        team1_total_cost: team1Cost * team1.count,
        team1_unit_cost: team1Cost,
        team1_max_hp: team1.mechanics.hp,
        team1_start_hp: team1.mechanics.hp * team1.count,
        team2_civ: team2.civ,
        team2_unit: team2.unit_slug,
        team2_unit_name: team2.unit_name,
        team2_count: team2.count,
        team2_total_cost: team2Cost * team2.count,
        team2_unit_cost: team2Cost,
        team2_max_hp: team2.mechanics.hp,
        team2_start_hp: team2.mechanics.hp * team2.count,
        winner: null,
    };
}

function renderMatchupCards(config) {
    const pageSim = getPageSim();
    const [team1, team2] = config.teams;
    setBattle(battleStatsFromConfig(config));
    const summaries = [
        summarizeMatchup(team1.mechanics, team2.mechanics),
        summarizeMatchup(team2.mechanics, team1.mechanics),
    ];
    for (const [index, team] of [team1, team2].entries()) {
        const teamNum = index + 1;
        const summary = summaries[index];
        setText(`prog${teamNum}Name`, `${team.civ} ${team.unit_name}`);
        setText(`prog${teamNum}Damage`, formatCombatMetric(summary.damagePerHit));
        setText(`prog${teamNum}Dps`, formatCombatMetric(summary.damagePerSecond));
        setText(`prog${teamNum}Ttk`, formatCombatMetric(summary.timeToKillSeconds, "s"));
        const ttkMetric = document.getElementById(`prog${teamNum}TtkMetric`);
        if (ttkMetric) {
            ttkMetric.title = summary.timeToKillHelp;
            ttkMetric.setAttribute(
                "aria-label",
                `Time to kill ${formatCombatMetric(summary.timeToKillSeconds, " seconds")}. ${summary.timeToKillHelp}`,
            );
        }
        renderCallouts(teamNum, summary.callouts);
        const icon = document.getElementById(`prog${teamNum}Icon`);
        if (unitImages[teamNum]?.src && icon) {
            icon.src = unitImages[teamNum].src;
            icon.classList.toggle("sprite", !!unitIsSprite[teamNum]);
            icon.style.display = "";
        }
    }
    updateStats(null);
    setSimPhase(!!pageSim?.config);
}

function updateStats(snapshot, unitIndex = new Map()) {
    const currentBattle = getBattle();
    const rows = { 2: [], 3: [] };
    for (const unit of snapshot?.units || []) {
        if (unit.owner === 2 || unit.owner === 3) rows[unit.owner].push(unit);
    }
    const t1Alive = rows[2].filter((unit) => unit.alive);
    const t2Alive = rows[3].filter((unit) => unit.alive);
    const t1Hp = snapshot
        ? t1Alive.reduce((sum, unit) => sum + unit.hp, 0)
        : (currentBattle?.team1_start_hp || 0);
    const t2Hp = snapshot
        ? t2Alive.reduce((sum, unit) => sum + unit.hp, 0)
        : (currentBattle?.team2_start_hp || 0);
    const t1AliveCount = snapshot ? t1Alive.length : (currentBattle?.team1_count || 0);
    const t2AliveCount = snapshot ? t2Alive.length : (currentBattle?.team2_count || 0);
    const battleTime = (snapshot?.tick ?? 0) / 60;

    setText("battleTimer", `${battleTime.toFixed(1)}s`);

    setText("prog1Units",
        `${t1AliveCount} / ${rows[2].length || currentBattle?.team1_count || 0}`);
    setText("prog1Hp",
        `${Math.round(t1Hp)} / ${Math.round(currentBattle?.team1_start_hp || 0)}`);
    updateHealthBar(1, t1Hp, currentBattle?.team1_start_hp || 0);
    if (currentBattle) {
        setText("prog1Res", currentBattle.team1_total_cost);
        const lostFraction = currentBattle.team1_start_hp > 0
            ? 1 - t1Hp / currentBattle.team1_start_hp : 0;
        const t1Lost = Math.round(currentBattle.team1_total_cost * lostFraction);
        setText("prog1Lost", t1Lost);
    }

    setText("prog2Units",
        `${t2AliveCount} / ${rows[3].length || currentBattle?.team2_count || 0}`);
    setText("prog2Hp",
        `${Math.round(t2Hp)} / ${Math.round(currentBattle?.team2_start_hp || 0)}`);
    updateHealthBar(2, t2Hp, currentBattle?.team2_start_hp || 0);
    if (currentBattle) {
        setText("prog2Res", currentBattle.team2_total_cost);
        const lostFraction = currentBattle.team2_start_hp > 0
            ? 1 - t2Hp / currentBattle.team2_start_hp : 0;
        const t2Lost = Math.round(currentBattle.team2_total_cost * lostFraction);
        setText("prog2Lost", t2Lost);
    }
}


return {updateStats, renderMatchupCards};
}
