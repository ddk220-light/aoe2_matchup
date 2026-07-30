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

import { RELIC_MAX, RELIC_BONUS_UNITS, TILE_SIZE } from "./constants.js";
import { BattleUnit } from "./battle_unit.js";
import { makeRng } from "./rng.js";
import { Simulation } from "./sim.js";
import { makeArena } from "./arena.js";

// One team's worth of spawning. `spec` is { combatDict, slug, civ, count,
// relics?, startKills? } — the headless equivalent of setupTeam's
// (unitSlug, civName, count, opts) arguments.
//
// `anchorSide` is the golden arena's spawn corner for this team (0 = the
// diamond's left corner, 1 = its bottom corner), or null when there is no
// arena — in which case every line below runs exactly as it always has.
function setupTeam(sim, teamNum, spec, anchorSide = null) {
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

    // Golden arena: a tape-shaped blob in one corner wedge instead of the
    // full-height line above. Spacing is one tile (the recordings' rank
    // spacing) but never tighter than the collision floor, or the whole blob
    // would spend its first second exploding apart.
    const layout =
        anchorSide === null
            ? null
            : sim.arena.spawnLayout(
                  anchorSide,
                  count,
                  Math.max(TILE_SIZE, minSpacing),
              );

    for (let i = 0; i < count; i++) {
        const unit = new BattleUnit(
            `${teamNum}-${i}`,
            teamNum,
            stats,
            unitSlug,
            civName,
            sim,
        );
        // ONE rng draw per unit, here, in index order — with or without an
        // arena. That is the whole reason the jitter is drawn before the branch
        // rather than inside it: the golden panel and every calibration seed
        // depend on the exact draw stream (see the DRAW ORDER note above), and
        // an arena must not be able to shift it.
        const jitter = (sim.rng.next() - 0.5) * 10;
        if (layout) {
            const p = layout[i];
            // Ride the jitter along the blob's WIDTH axis, so it ruffles each
            // rank instead of smearing the ranks into each other.
            unit.x = p.x + jitter * p.wx;
            unit.y = p.y + jitter * p.wy;
            // Seed the facing toward the enemy corner. Without this every unit
            // starts at rest and the 0.3 velocity smoothing spends the first
            // half-second turning the whole army around.
            unit.vx = p.fx;
            unit.vy = p.fy;
            sim.arena.constrain(unit);
        } else {
            unit.x = startX + jitter;
            unit.y = startY + i * spacing;
        }
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

// Which of a fight's two sides should hold the diamond's LEFT corner. The
// longer-ranged side does, because it is the one that will kite: retreating
// from a threat on its lower-right sends it up the top-left edge and around the
// tree cluster CLOCKWISE, which is the sense the recording AI's square patrol
// runs and the sense BattleUnit.kiteSteering's tangential term already uses.
// Ties (and any missing stat) leave team 1 on the left — deterministic either
// way, and never a function of the rng.
function pickLeftCorner(teams) {
    const r1 = Number(teams[0].combatDict?.attack_range) || 0;
    const r2 = Number(teams[1].combatDict?.attack_range) || 0;
    return r2 > r1 ? 1 : 0;
}

// The engine's single public entry point: build a seeded Simulation with both
// teams spawned. `teams` is [team1Spec, team2Spec] (see setupTeam above).
//
// `arena` is OPT-IN and defaults to nothing: "golden" builds the recording
// arena (engine/arena.js) — a diamond play area with a central tree cluster and
// two adjacent-corner spawn blobs. Any other value, including the default,
// leaves sim.arena null and every unit on the historical full-height line
// inside the plain 900x600 rectangle, bit for bit.
export function createSimulation({
    mapW = 900,
    mapH = 600,
    teams,
    seed,
    arena = null,
}) {
    if (!Array.isArray(teams) || teams.length !== 2) {
        throw new Error("createSimulation needs exactly two team specs");
    }
    const sim = new Simulation(mapW, mapH, makeRng(seed));
    sim.arena = makeArena(arena, { mapW, mapH });
    const leftTeam = sim.arena ? pickLeftCorner(teams) : null;
    // Order matters — see the DRAW ORDER note at the top of this file.
    setupTeam(sim, 1, teams[0], sim.arena ? (leftTeam === 0 ? 0 : 1) : null);
    setupTeam(sim, 2, teams[1], sim.arena ? (leftTeam === 0 ? 1 : 0) : null);
    return sim;
}
