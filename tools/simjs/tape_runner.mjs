// Replays the tape corpus (real recorded in-game fights) through the EXTRACTED
// engine and emits one record per fight for aoe2x/validation/tape_rig_js.py to
// insert into data/validation/tape_runs.db.
//
//     node tools/simjs/tape_runner.mjs --scales tape,equal_count --seeds 5 > out.json
//
// Deliberate constraints:
//   * imports buildFight (NOT runFight) -- runFight's `final` shape is frozen by
//     parity_check.mjs; this file needs different columns, so it drives its own
//     tick loop over the same spawn path;
//   * ZERO count arithmetic. Counts come from data/validation/tape_plan.json,
//     which Python computed with the recorder's own rule;
//   * seeds are 1..N. makeRng(0) === makeRng(1) (rng.js `(seed>>>0) || 1`), so a
//     0-based range silently double-counts a seed;
//   * integer tick budget, matching headless.mjs and the golden capture.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../..");

export function loadTapeDicts() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/validation/tape_combat_dicts.json"), "utf8"));
}

export function loadTapePlan() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/validation/tape_plan.json"), "utf8")).rows;
}

// hp% denominator is the WHOLE starting team including corpses, mirroring
// simulation_real.total_max_hp. maxHp mutates at runtime (aura/transform/
// dismount), so sum the live objects rather than count * dict.hp.
function hpPct(team) {
    let cur = 0, max = 0;
    for (const u of team) {
        max += u.maxHp;
        if (u.state !== "dead") cur += u.currentHp;
    }
    return max > 0 ? cur / max : 0;
}

export function runTapeFight({ dicts, plan_row, scale, seed, maxSeconds = MAX_SECONDS }) {
    const [n1, n2] = plan_row.counts[scale];
    const row = {
        civ1: plan_row.subject_civ, slug1: plan_row.subject_slug, n1,
        civ2: plan_row.opp_civ, slug2: plan_row.opp_slug, n2,
    };
    const sim = buildFight({ dicts, row, seed });

    const maxTicks = Math.round(maxSeconds * 60);
    const t0 = process.hrtime.bigint();
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
    }
    const wall_ms = Number(process.hrtime.bigint() - t0) / 1e6;

    const hp1 = hpPct(sim.team1);
    const hp2 = hpPct(sim.team2);
    const alive = (team) => team.filter((u) => u.state !== "dead").length;

    // sim.winner === null means the cap was hit with both sides alive. The JS
    // engine declines to break that tie; adjudicate by HP% so the agreement
    // figure is comparable with simulation_real's cap rule, and keep
    // end_reason='time_cap' as the marker that this row was adjudicated.
    let winner = sim.winner;
    let end_reason = "eliminated";
    if (winner === null) {
        end_reason = "time_cap";
        winner = hp1 > hp2 ? 1 : hp2 > hp1 ? 2 : 0;
    }

    return {
        winner,
        end_reason,
        game_time_s: sim.battleTime,
        team1_hp_pct: hp1,
        team1_survivors: alive(sim.team1),
        team2_hp_pct: hp2,
        team2_survivors: alive(sim.team2),
        signed_score: (hp1 - hp2) * 100.0,
        wall_ms,
    };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const argv = process.argv.slice(2);
    const flag = (name, dflt) => {
        const i = argv.indexOf(name);
        return i >= 0 && i + 1 < argv.length ? argv[i + 1] : dflt;
    };
    const scales = flag("--scales", "tape,equal_count").split(",").map((s) => s.trim()).filter(Boolean);
    const nSeeds = Number(flag("--seeds", "5"));
    const maxSeconds = Number(flag("--max-seconds", String(MAX_SECONDS)));

    const dicts = loadTapeDicts();
    const plan = loadTapePlan();
    const out = [];
    for (const pr of plan) {
        for (const scale of scales) {
            if (!pr.counts[scale]) throw new Error(`plan row ${pr.plan_id} has no scale "${scale}"`);
            for (let seed = 1; seed <= nSeeds; seed++) {
                const r = runTapeFight({ dicts, plan_row: pr, scale, seed, maxSeconds });
                out.push({ plan_id: pr.plan_id, scale, seed, n1: pr.counts[scale][0],
                           n2: pr.counts[scale][1], ...r });
            }
        }
    }
    process.stdout.write(JSON.stringify(out));
}
