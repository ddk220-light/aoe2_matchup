// Captures golden/panel.json from the UNMODIFIED simulate.js via legacy_harness.cjs.
// Refuses to run if simulate.js differs from git HEAD.
//
//     node tools/simjs/parity_capture.mjs [outPath]
//
// outPath (default golden/panel.json) exists so a re-capture can be written somewhere
// else and diffed against the committed golden BEFORE overwriting it — the capture is
// deterministic, so appending rows to panel_spec.json must leave every previously
// captured fight byte-identical, and that is worth proving rather than assuming.
// A sibling <outPath minus .json>.meta.json records provenance (see writeMeta below).
//
// The output is the immutable parity baseline for the engine extraction: every later
// step must reproduce it bit for bit. Re-running this after simulate.js changes would
// silently redefine "correct", so treat golden/panel.json as write-once.
//
// Output schema (see legacy_harness.cjs runFightCaptured for the full contract):
//   [ { id, civ1, slug1, n1, civ2, slug2, n2, seed,
//       snapshots: [ { tick, units: [[team, idx, x, y, hp, state], …] }, … ],
//       final: { winner, time, alive1, alive2, hp1, hp2 } }, … ]
import { execSync } from "node:child_process";
import { createWriteStream, readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { once } from "node:events";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const require = createRequire(import.meta.url);

// Compare against HEAD (not just the worktree) so a STAGED edit can't slip through.
try {
    execSync("git diff --quiet HEAD -- apps/website/static/js/simulate.js", { cwd: ROOT });
} catch {
    console.error("simulate.js is dirty — capture must run against HEAD");
    process.exit(1);
}

const harness = require("./legacy_harness.cjs");
const spec = JSON.parse(readFileSync(path.join(HERE, "golden/panel_spec.json"), "utf8"));
const dicts = JSON.parse(readFileSync(path.join(HERE, "golden/combat_dicts.json"), "utf8"));
const SEEDS = [1, 2, 3, 4, 5];
const MAX_SECONDS = 600;
const dest = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(HERE, "golden/panel.json");
const metaDest = dest.replace(/\.json$/, "") + ".meta.json";

// Streamed rather than accumulated: a stalemate row can carry 600 snapshots x 70 units,
// so holding all 140 fights in memory before stringifying is needlessly heavy. The bytes
// written are exactly what JSON.stringify(results) would produce.
const out = createWriteStream(dest);
const write = (s) => out.write(s) || once(out, "drain");

const started = Date.now();
let n = 0;
let capped = 0;
await write("[");
for (const row of spec) {
    for (const seed of SEEDS) {
        const r = await harness.runFightCaptured(dicts, row, seed, MAX_SECONDS);
        await write((n ? "," : "") + JSON.stringify({ ...row, seed, ...r }));
        n++;
        if (r.final.winner === null) capped++;
        console.log(
            `${row.id} seed ${seed}: winner=${r.final.winner} t=${r.final.time.toFixed(1)} ` +
            `alive=${r.final.alive1}/${r.final.alive2} snaps=${r.snapshots.length}`,
        );
    }
}
await write("]");
out.end();
await once(out, "finish");

const secs = (Date.now() - started) / 1000;

// Provenance sidecar. Without it, panel.json is 20 MB of numbers with no way to tell WHICH
// simulate.js produced them — staleness would be undetectable. Deliberately a separate file
// so the panel stays a plain array (its schema is what later tasks parse).
// capturedAt is the git commit date of HEAD, not the wall clock: a re-capture from the same
// tree must produce an identical meta file, and wall-clock time would break that.
const git = (cmd) => execSync(cmd, { cwd: ROOT }).toString().trim();
writeFileSync(metaDest, JSON.stringify({
    simulateJsBlobSha: git("git hash-object apps/website/static/js/simulate.js"),
    captureCommit: git("git rev-parse HEAD"),
    capturedAt: git("git log -1 --format=%cI HEAD"),
    seeds: SEEDS,
    maxSeconds: MAX_SECONDS,
    rowCount: spec.length,
    fightCount: n,
}, null, 2) + "\n");

console.log(
    `captured ${n} fights in ${secs.toFixed(1)}s -> ${dest} ` +
    `(${(statSync(dest).size / 1e6).toFixed(1)} MB, ${capped} hit the ${MAX_SECONDS}s cap)`,
);
console.log(`provenance -> ${metaDest}`);
