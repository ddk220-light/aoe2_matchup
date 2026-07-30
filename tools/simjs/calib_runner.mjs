// Drives the JS battle engine over every recorded calibration fight
// (data/calibration/manifest.json), 20 seeds per fight, with sim.eventLog
// turned on, and writes one tape-shaped event file per (fight, seed) to
// D:/AI/aoe2_golden/simruns/<run_id>/seed-<n>.json for
// aoe2x/calibration/extract.py (the SAME extractor tape events go through)
// to score.
//
//     python tools/simjs/dump_calib_dicts.py     # (re)build combat dicts first
//     node tools/simjs/calib_runner.mjs --seeds 20
//
// Deliberate constraints (mirroring tape_runner.mjs / headless.mjs):
//   * imports buildFight (NOT runFight) -- runFight's `final` shape is frozen
//     for parity_check.mjs; this file drives its own tick loop with
//     sim.eventLog enabled instead. headless.mjs itself is never modified;
//   * ZERO count arithmetic -- counts come straight from each manifest
//     fight's side1.count/side2.count (the real recorded army sizes), never
//     a cost rule (three incompatible ones exist elsewhere in this repo);
//   * seeds are 1..N, never 0-based (rng.js's `(seed >>> 0) || 1` aliases
//     seed 0 to seed 1, which would silently double-count a seed);
//   * integer tick budget (Math.round(maxSeconds * 60)), matching
//     headless.mjs and the 600s cap used across the rest of the toolchain.
//
// Owner remapping: buildFight always plays the manifest's side1 as engine
// team 1 and side2 as engine team 2 (structural slots), but the REAL in-game
// owner is each side's own `owner` field (2/3 in today's corpus -- see the
// manifest's module docs). sim.eventLog's attacker_owner/victim_owner (and
// each missile's owner) are the engine's raw team numbers, so this file
// remaps team 1 -> side1.owner and team 2 -> side2.owner before writing
// anything to disk. That is what lets extract.py's `composition` (keyed
// "side<owner>") score sim events exactly like tape events, without the
// scorer having to know about engine-internal team numbering at all.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../..");
const DEFAULT_OUT_DIR = "D:/AI/aoe2_golden/simruns";

export function loadManifest() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/calibration/manifest.json"), "utf8")).fights;
}

export function loadCalibDicts() {
    return JSON.parse(readFileSync(
        path.join(REPO, "data/calibration/combat_dicts.json"), "utf8"));
}

function sideSummary(team, side) {
    const alive = team.filter((u) => u.state !== "dead");
    return {
        owner: side.owner,
        unit_name: side.unit_name,
        civ: side.civ,
        slug: side.slug,
        start_count: side.count,
        survivors: alive.length,
        hp_remaining: alive.reduce((sum, u) => sum + u.currentHp, 0),
    };
}

// Run one manifest fight at one seed. Returns the tape-shaped record the
// extractor and Task 5's scorer need: {run_id, seed, duration_s, winner,
// sides (keyed by REAL owner number), damage, missiles}.
// `arena` is createSimulation's opt-in battlefield field and DEFAULTS TO NULL —
// the plain rectangle every recorded corpus run has ever used. Passing
// "golden" is an A/B measurement tool, never the scoring configuration: the
// manifest's expected outcomes were all scored on the rectangle, so a run with
// an arena is not comparable to them.
export function runCalibFight({
    dicts,
    fight,
    seed,
    maxSeconds = MAX_SECONDS,
    arena = null,
}) {
    const s1 = fight.side1, s2 = fight.side2;
    // Guard against a same-owner manifest entry: if s1.owner === s2.owner,
    // `sides` would silently collapse to one key and BOTH teams' events
    // would remap to that one owner -- total, silent corruption. Fail loudly
    // with both values instead of ever writing a corrupted file.
    if (s1.owner === s2.owner) {
        throw new Error(
            `runCalibFight: fight "${fight.run_id}" has side1.owner === side2.owner ` +
            `(both ${s1.owner}) -- cannot distinguish sides, refusing to run`,
        );
    }
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena });
    sim.eventLog = { damage: [], missiles: [] };

    const maxTicks = Math.round(maxSeconds * 60);
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
    }

    // team 1 -> side1's real owner, team 2 -> side2's real owner (see the
    // module-level comment on why this remap has to happen here).
    const ownerOf = { 1: s1.owner, 2: s2.owner };

    const damage = sim.eventLog.damage.map((e) => ({
        ...e,
        attacker_owner: ownerOf[e.attacker_owner],
        victim_owner: ownerOf[e.victim_owner],
    }));
    const missiles = sim.eventLog.missiles.map((m) => ({
        ...m,
        owner: ownerOf[m.owner],
    }));

    return {
        run_id: fight.run_id,
        tag: fight.tag,
        matchup: fight.matchup,
        seed,
        duration_s: sim.battleTime,
        // `winner` is in ENGINE TEAM space, `winner_owner` is in RECORDING
        // OWNER space -- these are NOT interchangeable, do not mix them up.
        // winner: raw engine value, never coerced (same discipline as
        // headless.mjs's final.winner): 1 | 2 (structural team slot) | 0
        // (mutual annihilation) | null (hit the tick cap with both sides
        // alive). Kept for provenance; not consumed by extract_card.
        winner: sim.winner,
        // winner_owner: the SAME outcome translated through the SAME
        // `ownerOf` table used above for event remapping (not a second,
        // independently-hardcoded map that could drift from it), so a
        // consumer can safely do `sides[String(winner_owner)]` to get the
        // winning side. `ownerOf` only has keys 1 and 2, so a draw
        // (winner 0) or timeout (winner null) both miss the table and
        // `?? null` turns that lookup miss into an explicit null -- a
        // consumer indexing `sides[String(winner)]` instead would silently
        // read the WRONG side whenever winner (team number) collides with
        // the other side's owner number (e.g. winner===2 meaning "team 2
        // won" while owner 2 is side1 -- exactly today's corpus, where
        // side1.owner is always 2).
        winner_owner: ownerOf[sim.winner] ?? null,
        sides: {
            [String(s1.owner)]: sideSummary(sim.team1, s1),
            [String(s2.owner)]: sideSummary(sim.team2, s2),
        },
        damage,
        missiles,
    };
}

// ---- CLI: run every manifest fight x N seeds, writing files to disk -------
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const argv = process.argv.slice(2);
    const flag = (name, dflt) => {
        const i = argv.indexOf(name);
        return i >= 0 && i + 1 < argv.length ? argv[i + 1] : dflt;
    };
    const nSeeds = Number(flag("--seeds", "20"));
    const maxSeconds = Number(flag("--max-seconds", String(MAX_SECONDS)));
    const outDir = flag("--out-dir", DEFAULT_OUT_DIR);
    // --arena golden runs the corpus on the recording arena instead of the
    // plain rectangle. MEASUREMENT ONLY, and never the default: the manifest's
    // expected outcomes were scored on the rectangle, so an arena run tells you
    // how the battlefield shifts results, not whether the engine is right.
    const arenaArg = flag("--arena", "");
    const arena = arenaArg === "golden" ? "golden" : null;

    const dicts = loadCalibDicts();
    const fights = loadManifest();

    const t0 = process.hrtime.bigint();
    let nFiles = 0, nDamage = 0, nMissiles = 0;
    for (const fight of fights) {
        const dir = path.join(outDir, fight.run_id);
        mkdirSync(dir, { recursive: true });
        const fightT0 = process.hrtime.bigint();
        for (let seed = 1; seed <= nSeeds; seed++) {
            const record = runCalibFight({ dicts, fight, seed, maxSeconds, arena });
            nDamage += record.damage.length;
            nMissiles += record.missiles.length;
            writeFileSync(path.join(dir, `seed-${seed}.json`), JSON.stringify(record));
            nFiles++;
        }
        const fightWallS = Number(process.hrtime.bigint() - fightT0) / 1e9;
        console.log(`  ${fight.run_id} (${nSeeds} seeds, ${fightWallS.toFixed(1)}s)`);
    }
    const wallS = Number(process.hrtime.bigint() - t0) / 1e9;
    console.log(`arena: ${arena || "plain (default)"}`);
    console.log(`wrote ${nFiles} files (${fights.length} fights x ${nSeeds} seeds) -> ${outDir}`);
    console.log(`damage events: ${nDamage}, missile events: ${nMissiles}`);
    console.log(`wall time: ${wallS.toFixed(1)}s`);
}
