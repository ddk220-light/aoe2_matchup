// Trace retarget decisions (who moved to which tree, from where, and why).
// Usage: node verify/trace_retargets.mjs [scenario]
import { readFileSync } from "node:fs";
import { createGame, step } from "../public/engine.js";

const scenName = process.argv[2] || "camp300";
const dir = new URL(`../data/${scenName}/`, import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));

const g = createGame(scen);
const treePos = new Map(scen.entities.filter((e) => e.type === "tree")
  .map((e) => [e.id, `(${e.x},${e.y})`]));

let seen = 0;
while (g.t < scen.duration + 1 && !g.ended) {
  step(g);
  while (seen < g.events.length) {
    const ev = g.events[seen++];
    if (ev.kind === "retarget") {
      // snapshot nearby tree availability at this moment
      const near = [...g.ents.values()]
        .filter((e) => e.type === "tree"
                && Math.hypot(e.x - ev.from[0], e.y - ev.from[1]) < 4)
        .map((e) => `${e.id}${treePos.get(e.id)}w=${e.wood.toFixed(0)}`
          + ` g=${e.gatherers}/${Math.min(e.spots ?? 4, 3)}`)
        .join("  ");
      console.log(`t=${ev.t.toFixed(1).padStart(6)}  vill #${ev.num} (${ev.eid})`
        + ` at ${ev.from} -> tree ${ev.tree} ${treePos.get(ev.tree)} d=${ev.d}`);
      console.log(`         nearby: ${near}`);
    } else if (["built", "tree_empty", "end"].includes(ev.kind)) {
      console.log(`t=${ev.t.toFixed(1).padStart(6)}  [${ev.kind}] ${ev.eid ?? ""}`);
    }
  }
}
