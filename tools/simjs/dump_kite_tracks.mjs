// E1 kite-orbit measurement: dump 10 Hz position tracks for every
// ranged-non-siege vs melee fight in the calibration manifest, at current
// SHIPPED engine defaults (no flag overrides), tapebox arena, tape spawns.
//
//     node tools/simjs/dump_kite_tracks.mjs --seeds 3 --out-dir <dir>
//
// MEASUREMENT ONLY. This file imports the exact loaders calib_runner.mjs uses
// and buildFight from headless.mjs; it reads sim state every 6th tick (60 Hz
// engine / 6 = 10 Hz) and never writes to it. No engine file is modified and
// no rule flag is touched, so the fights are bit-identical to what a default
// `node tools/simjs/calib_runner.mjs` run produces for the same (fight, seed).
//
// Output: one JSON per (fight, seed): <out-dir>/<tag>/seed-<n>.json
//   {
//     tag, run_id, seed, duration_s, winner,      // winner in ENGINE team space
//     kiter_team, kiter_slug, melee_slug,          // 1|2 (engine team space)
//     dt: 0.1,
//     units: [{team, id, idx}, ...],               // frame column order
//     frames: [[t, [[x,y,alive], ...]], ...],      // x,y in TILES (worldToTile)
//     missiles: [[t, fired_from, team], ...],      // per projectile created
//   }
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import {
    applyC3Spec,
    applyC4Spec,
    applyE1Spec,
    loadCalibDicts,
    loadCalibSpawns,
    loadManifest,
    spawnsForFight,
} from "./calib_runner.mjs";

// The three kiter unit lines this experiment measures. imp_elite_skirm is
// ranged too but out of scope (E1 brief); siege excluded; ranged-vs-ranged
// excluded by construction (other side must NOT be in RANGED_OR_SIEGE).
const KITERS = new Set(["hand_cannoneer", "arbalester", "heavy_cav_archer"]);
const RANGED_OR_SIEGE = new Set([
    "hand_cannoneer", "arbalester", "heavy_cav_archer", "imp_elite_skirm",
    "siege_onager", "heavy_scorpion",
]);

export function kiteCorpus(fights) {
    const out = [];
    for (const f of fights) {
        const s1 = f.side1.slug, s2 = f.side2.slug;
        const k1 = KITERS.has(s1), k2 = KITERS.has(s2);
        if (k1 === k2) continue; // neither, or archer-vs-archer
        const other = k1 ? s2 : s1;
        if (RANGED_OR_SIEGE.has(other)) continue; // siege or ranged-vs-ranged
        out.push({ fight: f, kiterSide: k1 ? 1 : 2 });
    }
    return out;
}

function sampleFrame(sim, t) {
    const row = [];
    for (const team of [sim.team1, sim.team2]) {
        for (const u of team) {
            const tc = sim.arena.worldToTile(u.x, u.y);
            row.push([
                Math.round(tc.tx * 1000) / 1000,
                Math.round(tc.ty * 1000) / 1000,
                u.state === "dead" ? 0 : 1,
            ]);
        }
    }
    return [Math.round(t * 1000) / 1000, row];
}

export function runKiteFight({ dicts, fight, kiterSide, seed, maxSeconds }) {
    const s1 = fight.side1, s2 = fight.side2;
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const spawns = loadCalibSpawns();
    const positions = spawnsForFight(spawns, fight);
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
    sim.eventLog = { damage: [], missiles: [] };

    const maxTicks = Math.round(maxSeconds * 60);
    const frames = [sampleFrame(sim, 0)];
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        if (ticks % 6 === 0) frames.push(sampleFrame(sim, ticks / 60));
    }
    if (ticks % 6 !== 0) frames.push(sampleFrame(sim, ticks / 60));

    const units = [];
    sim.team1.forEach((u, i) => units.push({ team: 1, id: u.id, idx: i }));
    sim.team2.forEach((u, i) => units.push({ team: 2, id: u.id, idx: i }));

    return {
        tag: fight.tag,
        run_id: fight.run_id,
        seed,
        duration_s: sim.battleTime,
        winner: sim.winner,
        kiter_team: kiterSide,
        kiter_slug: kiterSide === 1 ? s1.slug : s2.slug,
        melee_slug: kiterSide === 1 ? s2.slug : s1.slug,
        dt: 0.1,
        units,
        frames,
        missiles: sim.eventLog.missiles.map((m) => [
            Math.round(m.t * 1000) / 1000, m.fired_from, m.owner,
        ]),
    };
}

// ---- CLI --------------------------------------------------------------------
if (process.argv[1]
    && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const argv = process.argv.slice(2);
    const flag = (name, dflt) => {
        const i = argv.indexOf(name);
        return i >= 0 && i + 1 < argv.length ? argv[i + 1] : dflt;
    };
    const nSeeds = Number(flag("--seeds", "3"));
    const maxSeconds = Number(flag("--max-seconds", String(MAX_SECONDS)));
    const outDir = flag("--out-dir", null);
    if (!outDir) {
        console.error("usage: node tools/simjs/dump_kite_tracks.mjs --out-dir <dir> [--seeds 3] [--e1 <spec>] [--c3 <spec>] [--c4 <spec>] [--tags a,b]");
        process.exit(2);
    }
    // E1 rule flags — same spec grammar and the same applyE1Spec as
    // calib_runner.mjs, so a geometry dump and a scoreboard run configure the
    // engine identically. Absent flag = shipped defaults, as before.
    const e1Cfg = applyE1Spec(flag("--e1", null));
    if (e1Cfg) {
        const on = Object.entries(e1Cfg).filter(([, v]) => v).map(([k]) => k);
        console.log(`e1 rules: ${on.length ? on.join(", ") : "(none -- pre-E1 engine)"}`);
    }
    // C3 rule flag — same spec grammar and the same applyC3Spec as
    // calib_runner.mjs, so the C3 geometry re-run (--e1 orbitKite --c3
    // postSwingPlant) configures the engine exactly like the scoreboard run.
    const c3Cfg = applyC3Spec(flag("--c3", null));
    if (c3Cfg) {
        const on = Object.entries(c3Cfg).filter(([, v]) => v).map(([k]) => k);
        console.log(`c3 rules: ${on.length ? on.join(", ") : "(none -- pre-C3 engine)"}`);
    }
    // C4 rule flag — same spec grammar and the same applyC4Spec as
    // calib_runner.mjs, so the C4 geometry re-run (--e1 orbitKite --c3
    // postSwingPlant --c4 fleeDuringReload) configures the engine exactly
    // like the scoreboard run.
    const c4Cfg = applyC4Spec(flag("--c4", null));
    if (c4Cfg) {
        const on = Object.entries(c4Cfg).filter(([, v]) => v).map(([k]) => k);
        console.log(`c4 rules: ${on.length ? on.join(", ") : "(none -- pre-C4 engine)"}`);
    }
    // Optional tag subset (dev-loop economy: don't run 78 fights to iterate on 5).
    const tagsArg = flag("--tags", null);
    const wantedTags = tagsArg
        ? new Set(tagsArg.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean))
        : null;

    const dicts = loadCalibDicts();
    let corpus = kiteCorpus(loadManifest());
    if (wantedTags) {
        const have = new Set(corpus.map((c) => c.fight.tag));
        const unknown = [...wantedTags].filter((t) => !have.has(t)).sort();
        if (unknown.length) {
            console.error(`--tags: not in the kite corpus: ${unknown.join(", ")}`);
            process.exit(2);
        }
        corpus = corpus.filter((c) => wantedTags.has(c.fight.tag));
    }
    console.log(`kite corpus: ${corpus.length} fights x ${nSeeds} seeds`);

    const t0 = process.hrtime.bigint();
    let n = 0;
    for (const { fight, kiterSide } of corpus) {
        const dir = path.join(outDir, fight.tag);
        mkdirSync(dir, { recursive: true });
        for (let seed = 1; seed <= nSeeds; seed++) {
            const rec = runKiteFight({ dicts, fight, kiterSide, seed, maxSeconds });
            writeFileSync(path.join(dir, `seed-${seed}.json`), JSON.stringify(rec));
            n++;
        }
        console.log(`  ${fight.tag}`);
    }
    const wallS = Number(process.hrtime.bigint() - t0) / 1e9;
    console.log(`wrote ${n} track files -> ${outDir} (${wallS.toFixed(1)}s)`);
}
