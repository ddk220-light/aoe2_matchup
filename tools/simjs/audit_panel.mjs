// Structural audit of golden/panel.json — every invariant later tasks are allowed to rely on.
//
//     node --max-old-space-size=8192 tools/simjs/audit_panel.mjs [panel.json]
//
// Checks (exits non-zero on any failure):
//   * fight count == rows x seeds; exactly the 10 documented keys per fight
//   * snapshot cadence: tick 0, then i*60, plus one off-cadence final snapshot
//   * units.length == n1+n2 in EVERY snapshot (dead units are retained, indices stable)
//   * unit ordering: all team-1 in index order, then all team-2
//   * tuple shape [team, idx, x, y, hp, state] with the right types
//   * final.{alive1,alive2,hp1,hp2} recomputed from the last snapshot agree
//   * final.winner agrees with the alive counts; null only at the 600 s cap
//   * final.time ~= lastTick/60
//   * full double precision preserved (nothing rounded)
//   * file bytes === JSON.stringify(JSON.parse(bytes))
import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const P = process.argv[2] ? path.resolve(process.argv[2]) : path.join(HERE, "golden/panel.json");
const spec = JSON.parse(readFileSync(path.join(HERE, "golden/panel_spec.json"), "utf8"));
const raw = readFileSync(P, "utf8");
const panel = JSON.parse(raw);
const fail = [];
const ok = (c, m) => { if (!c) fail.push(m); };

ok(Array.isArray(panel), "top level is not an array");
ok(panel.length === spec.length * 5, `expected ${spec.length * 5} fights, got ${panel.length}`);

const STATES = new Set();
let totalSnaps = 0, totalUnitRows = 0, capped = 0, maxSnaps = 0;
const seedsSeen = new Set();
for (const f of panel) {
    ok(!!spec.find((r) => r.id === f.id), `unknown id ${f.id}`);
    for (const k of ["id", "civ1", "slug1", "n1", "civ2", "slug2", "n2", "seed", "snapshots", "final"]) {
        ok(k in f, `${f.id}/${f.seed}: missing key ${k}`);
    }
    ok(Object.keys(f).length === 10, `${f.id}/${f.seed}: unexpected keys ${Object.keys(f)}`);
    seedsSeen.add(f.seed);
    const n = f.n1 + f.n2;
    ok(f.snapshots[0].tick === 0, `${f.id}/${f.seed}: first snapshot tick != 0`);
    const lastTick = f.snapshots.at(-1).tick;
    for (let i = 0; i < f.snapshots.length; i++) {
        const s = f.snapshots[i];
        ok(Object.keys(s).length === 2 && "tick" in s && "units" in s, `${f.id}: snapshot keys`);
        ok(Number.isInteger(s.tick), `${f.id}: non-integer tick ${s.tick}`);
        ok(s.units.length === n, `${f.id} tick ${s.tick}: ${s.units.length} units, expected ${n}`);
        for (let j = 0; j < n; j++) {
            const u = s.units[j];
            ok(u.length === 6, `${f.id} tick ${s.tick}: tuple len ${u.length}`);
            ok(u[0] === (j < f.n1 ? 1 : 2) && u[1] === (j < f.n1 ? j : j - f.n1),
                `${f.id} tick ${s.tick}: order broken at ${j} -> ${u[0]},${u[1]}`);
            ok(typeof u[2] === "number" && typeof u[3] === "number" && typeof u[4] === "number",
                `${f.id} tick ${s.tick}: non-numeric x/y/hp`);
            ok(typeof u[5] === "string", `${f.id} tick ${s.tick}: non-string state`);
            STATES.add(u[5]);
        }
        if (i > 0 && i < f.snapshots.length - 1) {
            ok(s.tick === i * 60, `${f.id}: cadence break at i=${i} tick=${s.tick}`);
        }
        totalUnitRows += s.units.length;
    }
    ok(lastTick % 60 === 0 ? f.snapshots.length === lastTick / 60 + 1
                           : f.snapshots.length === Math.floor(lastTick / 60) + 2,
       `${f.id}/${f.seed}: snapshot count ${f.snapshots.length} vs lastTick ${lastTick}`);
    totalSnaps += f.snapshots.length;
    maxSnaps = Math.max(maxSnaps, f.snapshots.length);

    const fin = f.final;
    ok(Object.keys(fin).length === 6, `${f.id}: final keys ${Object.keys(fin)}`);
    ok([0, 1, 2, null].includes(fin.winner), `${f.id}: bad winner ${fin.winner}`);
    if (fin.winner === null) { capped++; ok(lastTick === 36000, `${f.id}: null winner but lastTick ${lastTick}`); }
    const last = f.snapshots.at(-1).units;
    const a1 = last.filter((u) => u[0] === 1 && u[5] !== "dead");
    const a2 = last.filter((u) => u[0] === 2 && u[5] !== "dead");
    ok(fin.alive1 === a1.length, `${f.id}: alive1 ${fin.alive1} vs snapshot ${a1.length}`);
    ok(fin.alive2 === a2.length, `${f.id}: alive2 ${fin.alive2} vs snapshot ${a2.length}`);
    ok(Math.abs(fin.hp1 - a1.reduce((s, u) => s + u[4], 0)) < 1e-9, `${f.id}: hp1 mismatch`);
    ok(Math.abs(fin.hp2 - a2.reduce((s, u) => s + u[4], 0)) < 1e-9, `${f.id}: hp2 mismatch`);
    if (fin.winner === 1) ok(a2.length === 0 && a1.length > 0, `${f.id}: winner 1 but ${a1.length}/${a2.length}`);
    if (fin.winner === 2) ok(a1.length === 0 && a2.length > 0, `${f.id}: winner 2 but ${a1.length}/${a2.length}`);
    if (fin.winner === 0) ok(a1.length === 0 && a2.length === 0, `${f.id}: winner 0 but ${a1.length}/${a2.length}`);
    ok(Math.abs(fin.time - lastTick / 60) < 1e-6, `${f.id}: time ${fin.time} vs ticks ${lastTick}`);
}

const longDecimals = raw.match(/\d+\.\d{15,}/g) || [];
ok(longDecimals.length > 1000, `suspiciously few full-precision numbers (${longDecimals.length})`);
ok(JSON.stringify(panel) === raw, "file bytes != JSON.stringify(parsed)");

const byWinner = { 1: 0, 2: 0, 0: 0, null: 0 };
for (const f of panel) byWinner[f.final.winner]++;
console.log(`panel              : ${P}`);
console.log(`fights             : ${panel.length}  (${spec.length} rows x seeds ${[...seedsSeen].sort().join(",")})`);
console.log(`snapshots          : ${totalSnaps}  (max ${maxSnaps} in one fight)`);
console.log(`unit rows          : ${totalUnitRows}`);
console.log(`hit the 600s cap   : ${capped}`);
console.log(`states observed    : ${[...STATES].sort().join(", ")}`);
console.log(`full-precision nums: ${longDecimals.length}`);
console.log(`file size          : ${(statSync(P).size / 1e6).toFixed(2)} MB`);
console.log(`winners            : team1 ${byWinner[1]}, team2 ${byWinner[2]}, mutual ${byWinner[0]}, capped ${byWinner.null}`);

if (fail.length) {
    console.log(`\nFAILURES (${fail.length}):`);
    for (const m of fail.slice(0, 30)) console.log("  " + m);
    process.exit(1);
}
console.log("\nALL CHECKS PASSED");
