// Asymmetric matchup: Champion (owner 2) vs Paladin (owner 3), per-unit
// mechanics, run on the tape's own start positions.
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const SP = "C:/Users/ddk22/AppData/Local/Temp/claude/" +
  "D--AI-aoe2-matchup/1bb1b353-ae0a-4383-b95f-37a4f05b5e52/scratchpad/cvp_trace/";

const { createUnitState } = await import(pathToFileURL(ROOT + "src/combat/unit-state.js").href);
const { createWorld, runWorld } = await import(pathToFileURL(ROOT + "src/combat/world.js").href);

const MECH = {
  567: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/champion_chinese_imperial.json", "utf8")),
  569: JSON.parse(readFileSync(ROOT + "fixtures/unit_stats/paladin_spanish_imperial.json", "utf8")),
};

const RATIOS = ["1v1", "1v2", "2v1", "2v3", "3v2", "3v5", "3v6", "5v3", "6v3"];
const TAGS = RATIOS.flatMap((r) => [r, `${r}_r2`, `${r}_r3`]);

function spawn(tag) {
  const lines = readFileSync(`${SP}${tag}.tape_trace.jsonl`, "utf8").trim().split("\n");
  const first = new Map();
  let t0 = null;
  for (const line of lines) {
    const row = JSON.parse(line);
    if (!MECH[row.master]) continue;
    if (t0 === null) t0 = row.t_ms;
    if (row.t_ms !== t0) break;
    first.set(row.id, row);
  }
  return [...first.values()].sort((a, b) => a.id - b.id);
}

const out = [];
for (const tag of TAGS) {
  let row;
  try {
    const roster = spawn(tag);
    const units = roster.map((u, i) => createUnitState({
      referenceId: u.id, owner: u.owner, x: u.x, y: u.y, facing: 0,
      mechanics: MECH[u.master],
      acquisitionRank: i, acquisitionCount: roster.length,
    }));
    const result = runWorld(createWorld({ ratio: tag.split("_")[0], units }));
    const living = result.world.units.filter((u) => u.alive);
    const deaths = result.events.filter((e) => e.type === "death")
      .map((e) => +(e.tick / 60).toFixed(3));
    row = {
      tag, seconds: +(result.ticks / 60).toFixed(3),
      winnerOwner: living.length ? living[0].owner : null,
      survivors: living.length,
      winnerHp: living.reduce((s, u) => s + u.hp, 0),
      hits: result.events.filter((e) => e.type === "damage").length,
      firstDeath: deaths[0] ?? null, lastDeath: deaths[deaths.length - 1] ?? null,
    };
  } catch (e) {
    row = { tag, error: String(e.message ?? e) };
  }
  out.push(row);
  console.log(JSON.stringify(row));
}
writeFileSync(`${SP}cvp_sim_summary.json`, JSON.stringify(out, null, 1));
