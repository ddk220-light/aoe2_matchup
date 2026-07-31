// E14 off-switch proof: with MELEE_QUEUE_TILES = 0 the engine must reproduce
// the shipped E13 run files bit for bit. Compares sha1 of the whole record
// (damage stream included), not just the summary.
//
//     node tools/simjs/e14_identity.mjs [refDir] [nSeeds]
import { readFileSync } from "node:fs";
import crypto from "node:crypto";
import {
    runCalibFight, loadManifest, loadCalibDicts, loadCalibSpawns,
} from "./calib_runner.mjs";

const REF = process.argv[2] || "D:/AI/aoe2_golden/simruns_e13_F028";
const NSEEDS = Number(process.argv[3] || 3);
const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest();
const h = (o) => crypto.createHash("sha1").update(JSON.stringify(o)).digest("hex");

let same = 0, diff = 0, n = 0;
for (const f of fights) {
    const e = spawns[f.tag];
    const positions = { 1: e[String(f.side1.owner)], 2: e[String(f.side2.owner)] };
    for (let seed = 1; seed <= NSEEDS; seed++) {
        const rec = runCalibFight({ dicts, fight: f, seed, arena: "tapebox", positions });
        const ref = JSON.parse(readFileSync(`${REF}/${f.run_id}/seed-${seed}.json`, "utf8"));
        n++;
        if (h(rec) === h(ref)) same++;
        else {
            diff++;
            if (diff <= 10) console.log("DIFF", f.run_id, "seed", seed);
        }
    }
}
console.log(`identical ${same}/${n}, differing ${diff}  (ref ${REF})`);
process.exit(diff ? 1 : 0);
