import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const SP = "./cvp_trace/";
const { createUnitState } = await import(pathToFileURL(ROOT + "src/combat/unit-state.js").href);
const { createWorld, runWorld } = await import(pathToFileURL(ROOT + "src/combat/world.js").href);
const MECH = {
  567: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/champion_chinese_imperial.json", "utf8")),
  569: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/paladin_spanish_imperial.json", "utf8")),
};
const tag = process.argv[2] || "6v3";
const lines = readFileSync(`${SP}${tag}.tape_trace.jsonl`, "utf8").trim().split("\n").map(JSON.parse)
  .filter((r) => MECH[r.master]);
const byId = new Map();
for (const r of lines) { if (!byId.has(r.id)) byId.set(r.id, []); byId.get(r.id).push(r); }
const spawn = [], acquireAt = new Map(), tapeTarget = new Map();
let t0 = Math.min(...lines.map((r) => r.t_ms));
for (const [id, ser] of byId) {
  ser.sort((a, b) => a.t_ms - b.t_ms);
  spawn.push(ser.find((r) => r.t_ms === t0) ?? ser[0]);
  const a = ser.find((r) => r.target_id !== null && r.target_id !== undefined && r.target_id !== -1);
  if (a) { acquireAt.set(id, a.t_ms / 1000); tapeTarget.set(id, a.target_id); }
}
spawn.sort((a, b) => a.id - b.id);
console.log("tape acquisition schedule:",
  [...acquireAt.entries()].sort((x, y) => x[1] - y[1]).map(([id, t]) => `${id}@${t.toFixed(2)}`).join(" "));

for (const mode of ["baseline", "tape-acquisition"]) {
  const units = spawn.map((u, i) => {
    const opts = {
      referenceId: u.id, owner: u.owner, x: u.x, y: u.y, facing: 0, mechanics: MECH[u.master],
      acquisitionRank: i, acquisitionCount: spawn.length,
    };
    if (mode === "tape-acquisition") {
      const t = acquireAt.get(u.id);
      opts.actionTimers = { windup: 0, reload: 0, swing: 0, acquire: Math.round(t * 60) };
    }
    return createUnitState(opts);
  });
  const r = runWorld(createWorld({ ratio: tag.split("_")[0], units }));
  const live = r.world.units.filter((u) => u.alive);
  const deaths = r.events.filter((e) => e.type === "death")
    .map((e) => `${e.targetId}@${(e.tick / 60).toFixed(2)}`);
  console.log(`\n${mode}: winner P${live[0]?.owner} hp ${live.reduce((s, u) => s + u.hp, 0)} `
    + `survivors ${live.length} hits ${r.events.filter((e) => e.type === "damage").length}`);
  console.log("   deaths:", deaths.join(" "));
  const firstTargets = {};
  for (const s of r.snapshots) for (const u of s.units)
    if (u.pursuitTargetId !== null && firstTargets[u.referenceId] === undefined)
      firstTargets[u.referenceId] = u.pursuitTargetId;
  console.log("   first targets:", JSON.stringify(firstTargets));
}
console.log("\n   TAPE first targets:", JSON.stringify(Object.fromEntries([...tapeTarget].sort((a,b)=>a[0]-b[0]))));
