import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const { createUnitState } = await import(pathToFileURL(ROOT + "src/combat/unit-state.js").href);
const { createWorld, runWorld } = await import(pathToFileURL(ROOT + "src/combat/world.js").href);
const MECH = {
  567: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/champion_chinese_imperial.json", "utf8")),
  569: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/paladin_spanish_imperial.json", "utf8")),
};
const out = [];
for (const arg of process.argv.slice(2)) {
  const [dir, tag] = arg.split(":");
  const lines = readFileSync(`${dir}/${tag}.tape_trace.jsonl`, "utf8").trim().split("\n").map(JSON.parse)
    .filter((r) => MECH[r.master]);
  const t0 = Math.min(...lines.map((r) => r.t_ms));
  const first = new Map();
  for (const r of lines) if (r.t_ms === t0 && !first.has(r.id)) first.set(r.id, r);
  const roster = [...first.values()].sort((a, b) => a.id - b.id);
  try {
    const units = roster.map((u, i) => createUnitState({
      referenceId: u.id, owner: u.owner, x: u.x, y: u.y, facing: 0,
      mechanics: MECH[u.master], acquisitionRank: i, acquisitionCount: roster.length,
    }));
    const r = runWorld(createWorld({ ratio: tag.split("_")[0], units }));
    const live = r.world.units.filter((u) => u.alive);
    out.push({ tag, winnerOwner: live[0]?.owner ?? null, winnerHp: live.reduce((s, u) => s + u.hp, 0),
      survivors: live.length, hits: r.events.filter((e) => e.type === "damage").length,
      seconds: +(r.ticks / 60).toFixed(2) });
  } catch (e) { out.push({ tag, error: String(e.message ?? e).slice(0, 70) }); }
  console.log(JSON.stringify(out.at(-1)));
}
writeFileSync("int_sim_summary.json", JSON.stringify(out, null, 1));
