import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const SP = "./cvp_trace/";
const { createUnitState } = await import(pathToFileURL(ROOT + "src/combat/unit-state.js").href);
const { createWorld, runWorld } = await import(pathToFileURL(ROOT + "src/combat/world.js").href);
const MECH = {
  567: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/champion_chinese_imperial.json", "utf8")),
  569: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/paladin_spanish_imperial.json", "utf8")),
};
for (const tag of process.argv.slice(2)) {
  const lines = readFileSync(`${SP}${tag}.tape_trace.jsonl`, "utf8").trim().split("\n");
  const first = new Map(); let t0 = null;
  for (const l of lines) { const r = JSON.parse(l); if (!MECH[r.master]) continue;
    if (t0 === null) t0 = r.t_ms; if (r.t_ms !== t0) break; first.set(r.id, r); }
  const roster = [...first.values()].sort((a,b)=>a.id-b.id);
  const units = roster.map((u,i)=>createUnitState({referenceId:u.id,owner:u.owner,x:u.x,y:u.y,facing:0,
    mechanics:MECH[u.master],acquisitionRank:i,acquisitionCount:roster.length}));
  const res = runWorld(createWorld({ratio:tag.split("_")[0],units}));
  const rows=[];
  for (const s of res.snapshots) for (const u of s.units)
    rows.push({t_ms:Math.round(s.tick/60*1000),id:u.referenceId,owner:u.owner,x:u.x,y:u.y,hp:u.hp,alive:u.alive,engaged:u.engagedTargetId??null});
  writeFileSync(`${SP}${tag}.sim_trace.jsonl`, rows.map(r=>JSON.stringify(r)).join("\n")+"\n");
  console.log(tag,"ticks",res.ticks);
}
