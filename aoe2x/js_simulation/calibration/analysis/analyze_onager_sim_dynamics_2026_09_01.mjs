// Focused, reproducible Onager/PAL simulation diagnostics.  Live captures are
// referenced as validation evidence only; no capture value enters the fight.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../../src/arena-physics-map.js";
import { runFight } from "../../src/fight.js";


const ROOT = new URL("../../", import.meta.url);
const CAPTURE = new URL(
  "../live_observations/expanded_roster_5x_2026-08-31/",
  import.meta.url,
);
const OUTPUT = new URL(
  "../reports/onager_full_fix_2026-09-01/sim_dynamics/paladin.json",
  import.meta.url,
);
const MATCHUP_KEY = "siege_onager_vs_paladin";


function positionCells(side) {
  return side.map(({ position }) => ({ x: position.x, y: position.y }));
}


function moments(values) {
  if (values.length === 0) return { mean: null, min: null, max: null, stddev: null };
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return {
    mean,
    min: Math.min(...values),
    max: Math.max(...values),
    stddev: Math.sqrt(values.reduce(
      (sum, value) => sum + (value - mean) ** 2,
      0,
    ) / values.length),
  };
}


function ownerSummary(snapshot, unitIndex, owner) {
  const units = snapshot.units.filter((unit) => (
    unit[5] === 1 && unitIndex[unit[0]].owner === owner
  ));
  // The mixed golden patrol axis is (+x,-y).  Longitudinal and lateral are
  // normalized orthogonal coordinates, so their spans can be compared to the
  // decoded live formation without depending on map orientation.
  const longitudinal = units.map((unit) => (unit[1] - unit[2]) / Math.SQRT2);
  const lateral = units.map((unit) => (unit[1] + unit[2]) / Math.SQRT2);
  return {
    alive: units.length,
    hp: units.reduce((sum, unit) => sum + unit[4], 0),
    longitudinal: moments(longitudinal),
    lateral: moments(lateral),
    units: units.map((unit) => ({
      referenceId: unit[0],
      x: unit[1],
      y: unit[2],
      hp: unit[4],
      action: unit[6],
      pursuitTargetId: unit[7],
      engagedTargetId: unit[8],
      attackTargetId: unit[9],
    })),
  };
}


async function main() {
  const [capture, formations, mapFixture] = await Promise.all([
    readFile(new URL("capture_manifest.json", CAPTURE), "utf8").then(JSON.parse),
    readFile(new URL("../../fixtures/current_ranged_golden_formations.json", import.meta.url),
      "utf8").then(JSON.parse),
    readFile(new URL("../../fixtures/golden_map.json", import.meta.url), "utf8")
      .then(JSON.parse),
  ]);
  const matchup = capture.matchups[MATCHUP_KEY];
  const formation = formations.families[matchup.family];
  const placementByOwner = {
    2: positionCells(formation.sides["2"]),
    3: positionCells(formation.sides["3"]),
  };
  const auxiliaryArmiesByOwner = {
    4: { slug: "scout_cavalry", cells: positionCells(formation.sides["4"]) },
  };
  const runs = [];
  for (const openingSeed of [0, 1, 2, 3, 4]) {
    const fight = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
      side2Slug: matchup.side1.slug,
      n2: matchup.side1.count,
      side3Slug: matchup.side2.slug,
      n3: matchup.side2.count,
      map: buildArenaPhysicsMap(mapFixture),
      placementByOwner,
      auxiliaryArmiesByOwner,
      diplomacyByOwner: formation.initial_diplomacy,
      triggers: formation.triggers,
      victoryTeams: [
        { winnerOwner: 2, owners: [2, 4] },
        { winnerOwner: 3, owners: [3] },
      ],
      preserveOwnerOrientation: true,
      disableAiOrders: true,
      disableKiting: true,
      openingSeed,
      retainSnapshots: true,
    });
    const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
    const attacks = fight.snapshots.flatMap((snapshot) => {
      const byReference = new Map(snapshot.units.map((unit) => [unit[0], unit]));
      return snapshot.events.filter((entry) => (
        entry.type === "attack-start" && ownerOf(entry.actorId) === 2
      )).map((entry) => {
        const actor = byReference.get(entry.actorId);
        const target = byReference.get(entry.targetId);
        return {
          tick: snapshot.tick,
          actorId: entry.actorId,
          actorX: actor?.[1] ?? null,
          actorY: actor?.[2] ?? null,
          targetId: entry.targetId,
          targetOwner: ownerOf(entry.targetId),
          targetX: target?.[1] ?? null,
          targetY: target?.[2] ?? null,
        };
      });
    });
    runs.push({
      openingSeed,
      winnerOwner: fight.winnerOwner,
      winnerHp: fight.winnerHp,
      ticks: fight.ticks,
      perSecond: fight.snapshots.filter(({ tick }) => tick % 60 === 0).map((snapshot) => ({
        second: snapshot.tick / 60,
        2: ownerSummary(snapshot, fight.unitIndex, 2),
        3: ownerSummary(snapshot, fight.unitIndex, 3),
        4: ownerSummary(snapshot, fight.unitIndex, 4),
      })),
      attacks,
      events: fight.snapshots.flatMap(({ events }) => events),
    });
  }
  const report = {
    schemaVersion: 1,
    matchup: MATCHUP_KEY,
    liveFramesBin: capture.runs[MATCHUP_KEY].map(({ repeat }) => (
      `${fileURLToPath(CAPTURE)}${MATCHUP_KEY}\\run_${String(repeat).padStart(3, "0")}`
        + `\\raw recordings\\${MATCHUP_KEY}.frames.bin`
    )),
    runs,
  };
  const outputPath = fileURLToPath(OUTPUT);
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`);
  process.stdout.write(`${outputPath}\n`);
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
