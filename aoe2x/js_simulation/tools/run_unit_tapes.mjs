// Run the clean-room engine on the Paladin, using the Paladin tape's own
// starting positions. Nothing here is Champion-specific.
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const SP = "C:/Users/ddk22/AppData/Local/Temp/claude/" +
  "D--AI-aoe2-matchup/1bb1b353-ae0a-4383-b95f-37a4f05b5e52/scratchpad/pal_trace/";

const { createUnitState } = await import(pathToFileURL(ROOT + "src/combat/unit-state.js").href);
const { createWorld, runWorld } = await import(pathToFileURL(ROOT + "src/combat/world.js").href);

const mechanics = JSON.parse(
  readFileSync(ROOT + "fixtures/unit_stats/paladin_spanish_imperial.json", "utf8"),
);

const RATIOS = ["1v1", "2v1", "2v3", "5v3", "6v3"];
const TAGS = RATIOS.flatMap((r) => [r, `${r}_r2`, `${r}_r3`]);

function startPositions(tag) {
  // first frame of the decoded tape trace = the authoritative spawn layout
  const lines = readFileSync(`${SP}${tag}.tape_trace.jsonl`, "utf8").trim().split("\n");
  const first = new Map();
  let t0 = null;
  for (const line of lines) {
    const row = JSON.parse(line);
    if (row.master !== 569) continue;
    if (t0 === null) t0 = row.t_ms;
    if (row.t_ms !== t0) break;
    first.set(row.id, row);
  }
  return [...first.values()].sort((a, b) => a.id - b.id);
}

const out = [];
for (const tag of TAGS) {
  const spawn = startPositions(tag);
  let result, error = null;
  try {
    const units = spawn.map((u, i) => createUnitState({
      referenceId: u.id,
      owner: u.owner,
      x: u.x,
      y: u.y,
      facing: 0,
      mechanics,
      acquisitionRank: i, acquisitionCount: spawn.length,
    }));
    const world = createWorld({ ratio: tag.split("_")[0], units });
    result = runWorld(world);
  } catch (e) {
    error = String(e.message ?? e);
  }
  if (error) {
    out.push({ tag, error });
    console.log(JSON.stringify({ tag, error }));
    continue;
  }
  const living = result.world.units.filter((u) => u.alive);
  const deaths = result.events
    .filter((e) => e.type === "death")
    .map((e) => +(e.tick / 60).toFixed(3));
  const damage = result.events.filter((e) => e.type === "damage");
  const row = {
    tag,
    ticks: result.ticks,
    seconds: +(result.ticks / 60).toFixed(3),
    survivors: living.length,
    winnerOwner: living.length ? living[0].owner : null,
    winnerHp: living.reduce((s, u) => s + u.hp, 0),
    hits: damage.length,
    deaths,
    firstDeath: deaths[0] ?? null,
    lastDeath: deaths[deaths.length - 1] ?? null,
  };
  out.push(row);
  console.log(JSON.stringify(row));
  // per-tick trace for geometry comparison
  const rows = [];
  for (const snap of result.snapshots) {
    for (const u of snap.units) {
      rows.push({
        t_ms: Math.round((snap.tick / 60) * 1000), id: u.referenceId,
        owner: u.owner, x: u.x, y: u.y, hp: u.hp, alive: u.alive,
        action: u.action, engaged: u.engagedTargetId ?? null,
      });
    }
  }
  writeFileSync(`${SP}${tag}.sim_trace.jsonl`,
    rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
}
writeFileSync(`${SP}pal_sim_summary.json`, JSON.stringify(out, null, 1));
