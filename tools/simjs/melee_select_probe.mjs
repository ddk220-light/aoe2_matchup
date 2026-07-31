// E14 Step 1 (engine side): WHY does a melee unit change target, and how many
// of its allies are on the same victim when it does?
//
// The damage streams say WHAT happened; they cannot say what the engine's
// intent was. This probe wraps BattleUnit.findTarget on a live fight and
// attributes every re-acquisition to its cause, using only state the engine
// already tracks:
//
//   INITIAL   -- the unit had never had a target (first frame of the fight).
//   DEAD      -- its target had just died; update()'s dead-target branch.
//   CHURN     -- E13's maybeMeleeChurn nulled the target after a swing.
//   BLOCKED   -- the stuck bar (battle_unit.js:1859) blacklisted the target
//                and nulled it. THIS is the one that can move a unit OFF a
//                living, reachable victim onto a different one.
//
// It also samples, every 0.5 s, how many living enemies are inside melee
// contact of at least one unit (contact slots) and the distribution of
// attackers per victim by INTENT (u.target), which the damage stream can only
// see once a swing lands.
//
//     node tools/simjs/melee_select_probe.mjs champion__vs__paladin [seed]
//     node tools/simjs/melee_select_probe.mjs --all
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import { BattleUnit } from "../../apps/website/static/js/engine/battle_unit.js";
import { loadManifest, loadCalibDicts, loadCalibSpawns } from "./calib_runner.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../..");

const MELEE = new Set([
    "champion", "halberdier", "paladin", "heavy_camel", "hussar",
    "elite_steppe", "elite_elephant",
]);

function spawnsForFight(spawns, fight) {
    const e = spawns[fight.tag];
    return { 1: e[String(fight.side1.owner)], 2: e[String(fight.side2.owner)] };
}

export function probe(fight, dicts, spawns, seed = 1) {
    const positions = spawnsForFight(spawns, fight);
    const row = {
        civ1: fight.side1.civ, slug1: fight.side1.slug, n1: fight.side1.count,
        civ2: fight.side2.civ, slug2: fight.side2.slug, n2: fight.side2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });

    // cause tagging: the ONLY writers of `target = null` outside findTarget are
    // maybeMeleeChurn and the stuck bar, so we shadow both and leave a marker.
    const orig = BattleUnit.prototype.findTarget;
    const origChurn = BattleUnit.prototype.maybeMeleeChurn;
    const counts = { 1: {}, 2: {} };
    const bump = (u, k) => {
        const c = counts[u.team];
        c[k] = (c[k] || 0) + 1;
    };
    BattleUnit.prototype.maybeMeleeChurn = function (victim) {
        const before = this.target;
        origChurn.call(this, victim);
        if (before && this.target === null) this._e14cause = "CHURN";
    };
    const blockDist = { 1: [], 2: [] };
    BattleUnit.prototype.findTarget = function (enemies) {
        const prev = this._e14prev;
        let cause = this._e14cause;
        if (!cause) {
            if (!prev) cause = "INITIAL";
            else if (prev.state === "dead") cause = "DEAD";
            else cause = "BLOCKED";
        }
        if (cause === "BLOCKED" && prev && !this.isRanged()) {
            // how far past its own reach was it when the bar fired? <= 0 means
            // it was standing IN contact and simply had no swing slot.
            const reach = this.attackRange + this.radius + prev.radius;
            blockDist[this.team].push(this.distanceTo(prev) - reach);
        }
        const r = orig.call(this, enemies);
        // did the re-pick actually MOVE the unit to a different victim?
        const moved = prev && r && r !== prev ? "-switch" : "-same";
        bump(this, cause + (cause === "INITIAL" ? "" : moved));
        this._e14cause = null;
        this._e14prev = r;
        return r;
    };
    for (const u of [...sim.team1, ...sim.team2]) {
        u._e14prev = null;
        u._e14cause = null;
    }

    // per-team INTENT concentration samples
    const samples = { 1: [], 2: [] };
    const contact = { 1: [], 2: [] };
    let next = 0;
    const maxTicks = Math.round(MAX_SECONDS * 60);
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        if (sim.battleTime >= next) {
            next += 0.5;
            for (const [team, mine, foes] of [
                [1, sim.team1, sim.team2], [2, sim.team2, sim.team1],
            ]) {
                const alive = mine.filter((u) => u.state !== "dead");
                if (!alive.length) continue;
                const per = new Map();
                let inContact = 0;
                for (const u of alive) {
                    if (!u.target || u.target.state === "dead") continue;
                    per.set(u.target, (per.get(u.target) || 0) + 1);
                    const d = u.distanceTo(u.target);
                    if (d <= u.attackRange + u.radius + u.target.radius + 1e-9) {
                        inContact++;
                    }
                }
                if (per.size) {
                    samples[team].push(
                        [...per.values()].reduce((a, b) => a + b, 0) / per.size);
                    contact[team].push(inContact / alive.length);
                }
                void foes;
            }
        }
    }
    BattleUnit.prototype.findTarget = orig;
    BattleUnit.prototype.maybeMeleeChurn = origChurn;

    const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
    return {
        run_id: fight.run_id,
        duration: sim.battleTime,
        sides: [1, 2].map((t) => ({
            team: t,
            slug: t === 1 ? fight.side1.slug : fight.side2.slug,
            count: t === 1 ? fight.side1.count : fight.side2.count,
            causes: counts[t],
            intent_attackers_per_victim: mean(samples[t]),
            contact_fraction: mean(contact[t]),
            block_excess_tiles: blockDist[t].length ? {
                n: blockDist[t].length,
                median: blockDist[t].slice().sort((a, b) => a - b)[
                    Math.floor(blockDist[t].length / 2)],
                p90: blockDist[t].slice().sort((a, b) => a - b)[
                    Math.min(blockDist[t].length - 1,
                        Math.floor(0.9 * blockDist[t].length))],
                within_half_tile: blockDist[t].filter((d) => d <= 0.5).length,
            } : null,
        })),
    };
}

const argv = process.argv.slice(2);
const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest();
const wanted = argv[0] === "--all"
    ? fights.filter((f) => MELEE.has(f.side1.slug) && MELEE.has(f.side2.slug))
    : fights.filter((f) => f.run_id === argv[0]);
const seed = Number(argv[1] || 1);

const totals = {};
for (const f of wanted) {
    const r = probe(f, dicts, spawns, seed);
    for (const s of r.sides) {
        const keys = Object.keys(s.causes).sort();
        console.log(
            `${r.run_id.padEnd(32)} ${s.slug.padEnd(14)} n=${String(s.count).padStart(2)} ` +
            `apv(intent)=${(s.intent_attackers_per_victim ?? 0).toFixed(2)} ` +
            `contact=${(s.contact_fraction ?? 0).toFixed(2)}  ` +
            (s.block_excess_tiles
                ? `blockExcess med=${s.block_excess_tiles.median.toFixed(2)}t ` +
                  `p90=${s.block_excess_tiles.p90.toFixed(2)}t ` +
                  `<=0.5t ${s.block_excess_tiles.within_half_tile}/${s.block_excess_tiles.n}  `
                : "") +
            keys.map((k) => `${k}=${s.causes[k]}`).join(" "));
        for (const k of keys) totals[k] = (totals[k] || 0) + s.causes[k];
    }
}
console.log("\nTOTAL retarget causes across probed sides:");
const grand = Object.values(totals).reduce((a, b) => a + b, 0);
for (const k of Object.keys(totals).sort()) {
    console.log(`  ${k.padEnd(20)} ${String(totals[k]).padStart(7)}  ` +
        `${(100 * totals[k] / grand).toFixed(1)}%`);
}
void REPO; void readFileSync;
