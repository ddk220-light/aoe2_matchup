// Compare targeting structure in the two current ranged-vs-ranged simulations.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";


const ROOT = new URL("../", import.meta.url);
const OUTPUT = new URL(
  "../calibration/reports/ranged_matrix_current_engine_2026-08-29/"
    + "ranged_vs_ranged_targeting_diagnostics.json",
  import.meta.url,
);


function targetSummary(result) {
  const slots = new Map();
  for (const owner of [2, 3]) {
    Object.entries(result.unitIndex)
      .filter(([, row]) => row.owner === owner)
      .sort(([left], [right]) => Number(left) - Number(right))
      .forEach(([id], index) => slots.set(Number(id), index + 1));
  }
  const events = result.snapshots.flatMap(({ events }) => events);
  const firstAcquisition = new Map();
  for (const row of events.filter(({ type }) => type === "pursuit-acquired")) {
    if (!firstAcquisition.has(row.actorId)) firstAcquisition.set(row.actorId, row);
  }
  const acquisitionByOwner = {};
  for (const owner of [2, 3]) {
    const rows = [...firstAcquisition.values()].filter(
      ({ actorId }) => result.unitIndex[actorId]?.owner === owner,
    );
    const counts = new Map();
    for (const { targetId } of rows) {
      const slot = slots.get(targetId);
      counts.set(slot, (counts.get(slot) ?? 0) + 1);
    }
    acquisitionByOwner[owner] = {
      actors: rows.length,
      uniqueTargets: counts.size,
      targetLoads: [...counts.entries()]
        .map(([slot, count]) => ({ slot, count }))
        .sort((left, right) => right.count - left.count || left.slot - right.slot),
    };
  }
  const firstEventTickByOwner = (type, owner) => events
    .filter((row) => row.type === type && result.unitIndex[row.actorId]?.owner === owner)
    .reduce((minimum, row) => Math.min(minimum, row.tick), Infinity);
  const damage = events.filter(({ type }) => type === "damage");
  return {
    winnerOwner: result.winnerOwner,
    winnerHp: result.winnerHp,
    ticks: result.ticks,
    firstAcquisition: acquisitionByOwner,
    firstAttackTickByOwner: Object.fromEntries([2, 3].map((owner) => [
      owner, firstEventTickByOwner("attack-start", owner),
    ])),
    firstDamageTickByOwner: Object.fromEntries([2, 3].map((owner) => [
      owner, firstEventTickByOwner("damage", owner),
    ])),
    damageEventsByOwner: Object.fromEntries([2, 3].map((owner) => [
      owner,
      damage.filter(({ actorId }) => result.unitIndex[actorId]?.owner === owner).length,
    ])),
  };
}


async function main() {
  const [formations, mapFixture] = await Promise.all([
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8").then(JSON.parse),
  ]);
  const formation = formations.families.ranged_vs_ranged;
  const placementByOwner = Object.fromEntries([2, 3].map((owner) => [
    owner,
    formation.sides[owner].map(({ position }) => ({ x: position.x, y: position.y })),
  ]));
  const openingPatrolByOwner = Object.fromEntries(formation.opening_patrols.map(
    ({ owner, x, y }) => [owner, { x, y }],
  ));
  const map = buildArenaPhysicsMap(mapFixture);
  const matchups = [
    ["arbalester_vs_hand_cannoneer", "arbalester", 27, "hand_cannoneer", 19],
    ["arbalester_vs_heavy_cav_archer", "arbalester", 27, "heavy_cav_archer", 18],
  ];
  const variants = {
    baseline: {},
    pressure: { rangedTargetPressureOwner: 3 },
    pressure_windup: {
      rangedTargetPressureOwner: 3,
      rangedWindupRetargetOwner: 3,
    },
  };
  const report = {
    schemaVersion: 1,
    rangedOpportunityRetargeting: "generic-in-range-opportunity",
    variants,
    matchups: {},
  };
  for (const [key, side2Slug, n2, side3Slug, n3] of matchups) {
    report.matchups[key] = {};
    for (const [variant, options] of Object.entries(variants)) {
      const result = await runFight(ROOT, {
        side2Slug, n2, side3Slug, n3, map,
        placementByOwner,
        openingPatrolByOwner,
        disableAiOrders: true,
        ...options,
      });
      report.matchups[key][variant] = targetSummary(result);
      process.stderr.write(`${key}/${variant}: ${result.winnerOwner}/${result.winnerHp}\n`);
    }
  }
  await mkdir(new URL(".", OUTPUT), { recursive: true });
  await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  process.stdout.write(`${fileURLToPath(OUTPUT)}\n`);
}


await main();
