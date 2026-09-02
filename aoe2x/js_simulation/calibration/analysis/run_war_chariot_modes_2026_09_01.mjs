// Exercise both War Chariot weapon forms on the captured ranged-vs-ranged
// roster. Focus Fire has a preserved live run; Barrage is simulation-only
// until a scenario capture explicitly switches to unit form 1980.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../../src/arena-physics-map.js";
import { runFight } from "../../src/fight.js";


const ROOT = new URL("../../", import.meta.url);
const OUTPUT = new URL(
  "../reports/requested_unique_effects_2026-09-01/war_chariot_modes_five_seed.json",
  import.meta.url,
);
const [formations, mapFixture] = await Promise.all([
  readFile(new URL("../../fixtures/current_ranged_golden_formations.json", import.meta.url),
    "utf8").then(JSON.parse),
  readFile(new URL("../../fixtures/golden_map.json", import.meta.url), "utf8")
    .then(JSON.parse),
]);
const formation = formations.families.ranged_vs_ranged;
const placementByOwner = Object.fromEntries([2, 3].map((owner) => [
  owner,
  formation.sides[String(owner)].map(({ position }) => ({
    x: position.x,
    y: position.y,
  })),
]));
const map = buildArenaPhysicsMap(mapFixture);
const modes = [
  { slug: "war_chariot_shu", mode: "focus_fire", liveCapture: true },
  { slug: "war_chariot_shu_barrage", mode: "barrage", liveCapture: false },
];
const rows = [];
for (const mode of modes) {
  const runs = [];
  for (let openingSeed = 0; openingSeed < 5; openingSeed += 1) {
    const run = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
      side2Slug: mode.slug,
      n2: 12,
      side3Slug: "arbalester",
      n3: 27,
      map,
      placementByOwner,
      diplomacyByOwner: formation.initial_diplomacy,
      triggers: formation.triggers,
      preserveOwnerOrientation: true,
      disableAiOrders: true,
      disableKiting: true,
      openingSeed,
      retainSnapshots: false,
    });
    const startingHp = run.startingHpByOwner[run.winnerOwner];
    runs.push({
      openingSeed,
      winnerOwner: run.winnerOwner,
      winnerHp: run.winnerHp,
      signedRemainingHpPercent: (run.winnerOwner === 2 ? 1 : -1)
        * run.winnerHp / startingHp * 100,
      ticks: run.ticks,
    });
    process.stderr.write(
      `${mode.mode} seed ${openingSeed}: P${run.winnerOwner} ${run.winnerHp} HP\n`,
    );
  }
  rows.push({
    ...mode,
    side2Count: 12,
    side3Slug: "arbalester",
    side3Count: 27,
    runs,
    meanSignedRemainingHpPercent: runs.reduce(
      (total, run) => total + run.signedRemainingHpPercent, 0,
    ) / runs.length,
  });
}
const report = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  source: {
    formation: fileURLToPath(new URL(
      "../../fixtures/current_ranged_golden_formations.json", import.meta.url)),
    map: fileURLToPath(new URL("../../fixtures/golden_map.json", import.meta.url)),
    focusFireLiveFrames: fileURLToPath(new URL(
      "../live_observations/requested_roster_vs_arb_paladin_1x_2026-08-31/"
      + "war_chariot_shu_vs_arbalester/run_001/raw recordings/"
      + "war_chariot_shu_vs_arbalester.frames.bin",
      import.meta.url,
    )),
    barrageLiveFrames: null,
  },
  note: "The preserved live scenario used Focus Fire (unit 1962); Barrage (1980) is simulation-only.",
  rows,
};
await mkdir(new URL("../reports/requested_unique_effects_2026-09-01/", import.meta.url), {
  recursive: true,
});
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${fileURLToPath(OUTPUT)}\n`);
