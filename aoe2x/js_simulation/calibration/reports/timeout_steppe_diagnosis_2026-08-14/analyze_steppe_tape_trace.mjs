import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

import { loadDedicatedGoldenCorpus } from "../../../src/dedicated-golden-corpus.js";

const reportDir = path.dirname(fileURLToPath(import.meta.url));
const tracePath = path.join(reportDir, "tape", "20v20.tape_trace.jsonl");
const corpus = await loadDedicatedGoldenCorpus(new URL("../../../", import.meta.url));
const matchup = corpus.matchups.find(({ id }) => id === "heavy_cav_archer_vs_elite_steppe");
const row = matchup.ratios.find(({ ratio }) => ratio === "20v20");
const run = row.runs[0];
const ownerById = new Map(run.starting_units.map(({ id, owner }) => [id, owner]));
const initialIds = new Set(run.starting_units.map(({ id }) => id));

function round(value, digits = 3) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function summarize(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const median = sorted.length % 2
    ? sorted[(sorted.length - 1) / 2]
    : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
  return {
    count: sorted.length,
    min: round(sorted[0]),
    median: round(median),
    max: round(sorted.at(-1)),
  };
}

const previousById = new Map();
const previousActionStateById = new Map();
const attacks = { 2: [], 3: [] };
const firstHpLossMs = { 2: null, 3: null };
const visibleDamageByAttacker = { 2: 0, 3: 0 };
const movement = {
  2: { steps: 0, moving: 0, distance: 0 },
  3: { steps: 0, moving: 0, distance: 0 },
};
let currentTime = null;
let currentRows = [];

function processFrame() {
  if (currentTime === null) return;
  const byId = new Map(currentRows.map((unit) => [unit.id, unit]));
  for (const unit of currentRows) {
    if (!initialIds.has(unit.id)) continue;
    const owner = ownerById.get(unit.id);
    const previousAction = previousActionStateById.get(unit.id);
    if (unit.action_state === 7 && previousAction !== 7) {
      const target = byId.get(unit.target_id);
      const centerDistance = target
        ? Math.hypot(target.x - unit.x, target.y - unit.y)
        : null;
      const chebyshevDistance = target
        ? Math.max(Math.abs(target.x - unit.x), Math.abs(target.y - unit.y))
        : null;
      attacks[owner].push({
        tMs: currentTime,
        actorId: unit.id,
        targetId: unit.target_id,
        centerDistance,
        chebyshevDistance,
      });
    }
    previousActionStateById.set(unit.id, unit.action_state ?? null);

    const previous = previousById.get(unit.id);
    if (previous) {
      const distance = Math.hypot(unit.x - previous.x, unit.y - previous.y);
      movement[owner].steps += 1;
      movement[owner].distance += distance;
      if (distance > 1e-5) movement[owner].moving += 1;
      if (unit.hp < previous.hp - 1e-9) {
        const attackerOwner = owner === 2 ? 3 : 2;
        visibleDamageByAttacker[attackerOwner] += previous.hp - unit.hp;
        if (firstHpLossMs[owner] === null) firstHpLossMs[owner] = currentTime;
      }
    }
    previousById.set(unit.id, unit);
  }
}

const input = readline.createInterface({
  input: fs.createReadStream(tracePath),
  crlfDelay: Infinity,
});
for await (const line of input) {
  if (!line.trim()) continue;
  const unit = JSON.parse(line);
  if (currentTime !== null && unit.t_ms !== currentTime) {
    processFrame();
    currentRows = [];
  }
  currentTime = unit.t_ms;
  currentRows.push(unit);
}
processFrame();

const output = {
  source: path.relative(process.cwd(), tracePath).replaceAll("\\", "/"),
  archive: matchup.archive,
  zipSha256: matchup.zipSha256,
  ratio: row.ratio,
  repeat: run.repeat,
  tapeOutcome: {
    winnerOwner: run.winner_owner,
    winnerHp: run.winner_hp,
    signedScore: run.signed_score,
  },
  firstHpLossSeconds: {
    owner2Hca: round(firstHpLossMs[2] / 1000),
    owner3Steppe: round(firstHpLossMs[3] / 1000),
  },
  attackActionEntries: {
    owner2Hca: attacks[2].length,
    owner3Steppe: attacks[3].length,
    uniqueHcaAttackers: new Set(attacks[2].map(({ actorId }) => actorId)).size,
    uniqueSteppeAttackers: new Set(attacks[3].map(({ actorId }) => actorId)).size,
    firstSteppeAttackSeconds: round(attacks[3][0].tMs / 1000),
    steppeCenterDistance: summarize(attacks[3]
      .map(({ centerDistance }) => centerDistance)
      .filter(Number.isFinite)),
    steppeChebyshevDistance: summarize(attacks[3]
      .map(({ chebyshevDistance }) => chebyshevDistance)
      .filter(Number.isFinite)),
  },
  visibleHpDropDamage: {
    hcaToSteppe: round(visibleDamageByAttacker[2]),
    steppeToHca: round(visibleDamageByAttacker[3]),
    note: "Excludes lethal hits because dead units disappear before an hp=0 row.",
  },
  movement: {
    owner2Hca: {
      movingStepShare: round(movement[2].moving / movement[2].steps, 4),
      distanceTiles: round(movement[2].distance),
    },
    owner3Steppe: {
      movingStepShare: round(movement[3].moving / movement[3].steps, 4),
      distanceTiles: round(movement[3].distance),
    },
  },
};

const outputPath = path.join(reportDir, "steppe_tape_trace_analysis.json");
fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
