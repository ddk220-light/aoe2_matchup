// Role: engine — the scenario builder: turns two team specs into a fully spawned,
// ready-to-step Simulation.
//
// This is simulate.js's `setupTeam` (lines 2376-2469) with the page-side pieces
// removed and nothing else changed:
//   * the HTTP round trip is gone — the caller hands in a combat dict (the exact
//     JSON shape /api/ref/combat-unit returns), and it is DEEP-COPIED here so the
//     relic transform can never mutate the caller's object (the legacy code got
//     this for free: every request parsed a fresh payload);
//   * the three sprite-assignment lines (2456-2458) are gone — sprites belong to
//     the renderer (`static/js/sim_renderer.js`);
//   * the unseeded jitter draw became `sim.rng.next()` — seeded and replayable.
// The relic-delta transform, the radius/spacing/start-position math, the
// construction order and the startKills clamp are byte-identical to the legacy.
//
// DRAW ORDER IS LOAD-BEARING: the legacy page awaits setupTeam(1, …) and then
// setupTeam(2, …), and each draws its jitter INSIDE the per-unit loop. So the rng
// stream is: one draw per team-1 unit in index order, then one per team-2 unit.
// The golden panel (tools/simjs/golden/panel.json) was captured with exactly that
// order — reordering the loops would silently shift every spawn position.

import { RELIC_MAX, RELIC_BONUS_UNITS } from "./constants.js";
import { BattleUnit } from "./battle_unit.js";
import { makeRng } from "./rng.js";
import { Simulation } from "./sim.js";

// One team's worth of spawning. `spec` is { combatDict, slug, civ, count,
// relics?, startKills? } — the headless equivalent of setupTeam's
// (unitSlug, civName, count, opts) arguments.
function setupTeam(sim, teamNum, spec) {
    const unitSlug = spec.slug;
    const civName = spec.civ;
    const count = spec.count;
    // Fresh copy per team: the relic transform below writes into `stats`, and the
    // caller's dict (often a shared, reused fixture) must come back untouched.
    const stats = JSON.parse(JSON.stringify(spec.combatDict));

    // Lithuanian relic picker: the served stats bake in all RELIC_MAX
    // relics (+1 base melee attack each), so apply the user-picked delta
    // to both the flat attack and the base-melee armor class ("4").
    const relics =
        spec.relics != null ? spec.relics : RELIC_MAX;
    if (
        relics !== RELIC_MAX &&
        civName === "Lithuanians" &&
        RELIC_BONUS_UNITS.has(unitSlug)
    ) {
        const delta = relics - RELIC_MAX;
        stats.attack = Math.max(0, (stats.attack || 0) + delta);
        if (stats.attacks_json) {
            const atk = JSON.parse(stats.attacks_json);
            if (atk["4"] != null)
                atk["4"] = Math.max(0, atk["4"] + delta);
            stats.attacks_json = JSON.stringify(atk);
        }
    }

    const team = [];
    const outlineSize = stats.outline_size || 0.2;
    const unitRadius = Math.round(
        10 + Math.min(outlineSize, 1.0) * 20,
    );
    const startX =
        teamNum === 1
            ? 30 + unitRadius
            : sim.W - 30 - unitRadius;
    const minSpacing = unitRadius * 2.2;
    const naturalSpacing =
        count > 1
            ? (sim.H - 2 * unitRadius) /
              (count - 1)
            : 0;
    const spacing = Math.max(naturalSpacing, minSpacing);
    const totalHeight = (count - 1) * spacing;
    const startY =
        count > 1
            ? Math.max(
                  unitRadius,
                  (sim.H - totalHeight) / 2,
              )
            : sim.H / 2;

    for (let i = 0; i < count; i++) {
        const unit = new BattleUnit(
            `${teamNum}-${i}`,
            teamNum,
            stats,
            unitSlug,
            civName,
            sim,
        );
        unit.x = startX + (sim.rng.next() - 0.5) * 10;
        unit.y = startY + i * spacing;
        // Starting-kills picker: pre-load the per-kill snowball counter
        // (capped at attackBonusPerKill, same as kills earned in-battle).
        if (spec.startKills > 0 && unit.attackBonusPerKill > 0) {
            unit.killBonusAttack = Math.min(
                unit.attackBonusPerKill,
                spec.startKills,
            );
        }
        team.push(unit);
    }

    if (teamNum === 1) {
        sim.team1 = team;
        sim.team1Stats = stats;
    } else {
        sim.team2 = team;
        sim.team2Stats = stats;
    }
}

// The engine's single public entry point: build a seeded Simulation with both
// teams spawned. `teams` is [team1Spec, team2Spec] (see setupTeam above).
export function createSimulation({ mapW = 900, mapH = 600, teams, seed }) {
    if (!Array.isArray(teams) || teams.length !== 2) {
        throw new Error("createSimulation needs exactly two team specs");
    }
    const sim = new Simulation(mapW, mapH, makeRng(seed));
    // Order matters — see the DRAW ORDER note at the top of this file.
    setupTeam(sim, 1, teams[0]);
    setupTeam(sim, 2, teams[1]);
    return sim;
}
