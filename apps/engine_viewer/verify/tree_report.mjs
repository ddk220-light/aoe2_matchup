// Per-tree harvest report from the SIM, for side-by-side comparison with the
// gRPC capture's per-tree truth. Usage: node verify/tree_report.mjs [scenario]
import { readFileSync } from "node:fs";
import { createGame, step } from "../public/engine.js";

const scenName = process.argv[2] || "camp300";
const dir = new URL(`../data/${scenName}/`, import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));

const g = createGame(scen);
const seed = new Map();
for (const e of g.ents.values()) if (e.type === "tree") seed.set(e.id, e.wood);

const first = new Map(), low = new Map(seed), emptied = new Map();
let next = 0;
while (g.t < scen.duration + 1 && !g.ended) {
  step(g);
  if (g.t < next) continue;
  next = g.t + 0.5;
  for (const [id, s0] of seed) {
    const e = g.ents.get(id);
    const w = e ? e.wood : 0;
    if (!first.has(id) && w < s0 - 0.3) first.set(id, +g.t.toFixed(1));
    if (w < low.get(id)) low.set(id, w);
    if (!emptied.has(id) && first.has(id) && w <= 0) emptied.set(id, +g.t.toFixed(1));
  }
}

console.log(`SIM per-tree harvest (${scenName}):`);
let total = 0;
const rows = [...first.entries()].sort((a, b) => a[1] - b[1]);
for (const [id, ft] of rows) {
  const e = scen.entities.find((x) => x.id === id);
  const taken = seed.get(id) - low.get(id);
  total += taken;
  console.log(`  tree ${id} (${e.x},${e.y}) seed=${seed.get(id)}`
    + `  first=${ft}s  taken=${taken.toFixed(1)}`
    + `  emptied=${emptied.get(id) ?? "-"}`);
}
console.log(`total taken: ${total.toFixed(1)}`);
