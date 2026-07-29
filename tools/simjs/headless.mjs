// Headless fight runner over the EXTRACTED engine (apps/website/static/js/engine/).
//
// This is the counterpart of legacy_harness.cjs's runFightCaptured(): same inputs
// (a frozen combat_dicts.json + one panel_spec row + a seed), same output shape, so
// parity_check.mjs can compare the two byte for byte. Where that harness loads the
// whole page bundle into a vm and stubs a DOM, this file just imports the engine —
// no canvas, no document, no renderer. That contrast IS the test: if the extraction
// dropped or reordered anything, the two disagree.
//
//     import { runFight } from "./headless.mjs";
//     const { snapshots, final } = runFight({ dicts, row, seed, maxSeconds: 600 });
//
// It also runs as a CLI for debugging one fight out of the panel:
//
//     node tools/simjs/headless.mjs <rowId> <seed> [maxSeconds]
//
// THE GOLDEN DEFINES THE FORMAT. Every mechanical detail below is mirrored from
// legacy_harness.cjs (lines 706-791) and must not be "improved":
//   * snapshot cadence — tick 0 after both teams spawn and before any update(),
//     then after every 60th update(), plus one final snapshot when the fight ends
//     off that cadence;
//   * unit tuple [team, idx, x, y, hp, state], every team-1 unit in array order
//     then every team-2 unit, dead units included so indices stay stable;
//   * an INTEGER TICK BUDGET (round(maxSeconds * 60)) — because THE CAPTURE USED
//     ONE. That is the whole reason; it needs no other.
//     To be precise about what this is NOT: at 600 s the integer budget and the
//     engine's float form in runToEnd() (`battleTime < maxSeconds - 1e-9`) AGREE.
//     battleTime accumulates to 599.999999999783 after 36000 ticks, which is
//     already >= 600 - 1e-9 (= 599.999999999), so runToEnd(600) also stops at
//     exactly 36000 ticks. Swapping this loop for runToEnd would not change a
//     single panel row today.
//     The float form is nonetheless fragile: the accumulated drift grows with the
//     budget and eventually crosses the 1e-9 epsilon — the first budget at which
//     the two forms disagree is maxSeconds = 1462, and 628 of the integer budgets
//     in 1..3000 disagree. So the integer budget is the form that stays correct if
//     the cap ever moves, and it is the form the golden was recorded with;
//   * final.winner is sim.winner RAW: 1 | 2 | 0 (mutual annihilation) | null (the
//     cap was hit with both sides alive). Never coerce the null;
//   * final.hp1/hp2 sum currentHp over LIVING units only;
//   * no rounding anywhere — full double precision, exactly as captured.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createSimulation } from "../../apps/website/static/js/engine/index.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const STEP = 1 / 60;
export const MAX_SECONDS = 600;

// Snapshot of the whole battlefield at `tick` completed update() calls.
function snapshot(sim, tick) {
    const units = [];
    for (let i = 0; i < sim.team1.length; i++) {
        const u = sim.team1[i];
        units.push([1, i, u.x, u.y, u.currentHp, u.state]);
    }
    for (let i = 0; i < sim.team2.length; i++) {
        const u = sim.team2[i];
        units.push([2, i, u.x, u.y, u.currentHp, u.state]);
    }
    return { tick, units };
}

// Build the spawned-but-unstepped simulation for one panel row + seed. Split out of
// runFight so a debugging session can drive the ticks itself (see bisect() below).
export function buildFight({ dicts, row, seed }) {
    const dictFor = (civ, slug) => {
        const cd = dicts[`${civ}|${slug}`];
        if (!cd) {
            throw new Error(
                `no combat dict for "${civ}|${slug}" — re-run dump_combat_dicts.py`,
            );
        }
        return cd;
    };
    // Team order matters: the spawn jitter draws one rng value per team-1 unit in
    // index order and then one per team-2 unit (see scenario.js's DRAW ORDER note).
    return createSimulation({
        teams: [
            {
                combatDict: dictFor(row.civ1, row.slug1),
                slug: row.slug1,
                civ: row.civ1,
                count: row.n1,
            },
            {
                combatDict: dictFor(row.civ2, row.slug2),
                slug: row.slug2,
                civ: row.civ2,
                count: row.n2,
            },
        ],
        seed,
    });
}

// Run one fight to completion, recording the golden's snapshot trajectory.
// `onTick(sim, tick)` is an optional debugging hook (per-tick stateHash logging);
// it must not mutate the sim, and the capture never used one.
export function runFight({ dicts, row, seed, maxSeconds = MAX_SECONDS, onTick }) {
    const sim = buildFight({ dicts, row, seed });

    const maxTicks = Math.round(maxSeconds * 60);
    const snapshots = [snapshot(sim, 0)];
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        if (onTick) onTick(sim, ticks);
        if (ticks % 60 === 0) snapshots.push(snapshot(sim, ticks));
    }
    if (ticks % 60 !== 0) snapshots.push(snapshot(sim, ticks));

    const living = (tm) => sim[tm].filter((u) => u.state !== "dead");
    const living1 = living("team1");
    const living2 = living("team2");
    return {
        snapshots,
        final: {
            winner: sim.winner, // 1 | 2 | 0 (mutual) | null (hit the time cap)
            time: sim.battleTime,
            alive1: living1.length,
            alive2: living2.length,
            hp1: living1.reduce((s, u) => s + u.currentHp, 0),
            hp2: living2.reduce((s, u) => s + u.currentHp, 0),
        },
    };
}

// Convenience for the CLI and for parity_check.mjs: the frozen combat dicts.
export function loadDicts() {
    return JSON.parse(
        readFileSync(path.join(HERE, "golden/combat_dicts.json"), "utf8"),
    );
}

export function loadSpec() {
    return JSON.parse(
        readFileSync(path.join(HERE, "golden/panel_spec.json"), "utf8"),
    );
}

// ---- CLI: run a single panel row and print its outcome -----------------------
// pathToFileURL, not string concatenation: on Windows argv[1] is "D:\…", whose
// file URL is "file:///D:/…" (three slashes) — a hand-built "file://" + path
// never matches and the CLI would silently do nothing.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const [rowId, seedArg, maxArg] = process.argv.slice(2);
    if (!rowId || !seedArg) {
        console.error("usage: node tools/simjs/headless.mjs <rowId> <seed> [maxSeconds]");
        process.exit(2);
    }
    const row = loadSpec().find((r) => r.id === rowId);
    if (!row) {
        console.error(`no panel row with id "${rowId}"`);
        process.exit(2);
    }
    const r = runFight({
        dicts: loadDicts(),
        row,
        seed: Number(seedArg),
        maxSeconds: maxArg ? Number(maxArg) : MAX_SECONDS,
    });
    console.log(
        `${row.id} seed ${seedArg}: winner=${r.final.winner} ` +
        `t=${r.final.time.toFixed(1)} alive=${r.final.alive1}/${r.final.alive2} ` +
        `hp=${r.final.hp1}/${r.final.hp2} snaps=${r.snapshots.length}`,
    );
}
