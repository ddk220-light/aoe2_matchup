// Capture the current engine output for every recorded matchup ratio, so the
// config-pinning change can be proven output-neutral. Run this BEFORE editing
// experiments.js / ai-orders.js, with the calibrated flags set.
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { matchupNames, matchupPlayback, matchupRatios } from "../src/matchup-playback.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

const rows = [];
for (const name of matchupNames()) {
  for (const ratio of await matchupRatios(root, name)) {
    const playback = await matchupPlayback(root, name, ratio);
    rows.push({
      name,
      ratio,
      ticks: playback.ticks,
      winnerOwner: playback.winnerOwner,
      winnerHp: playback.winnerHp,
      finalStateHash: playback.finalStateHash,
      eventLogHash: playback.eventLogHash,
    });
  }
}
rows.sort((a, b) => (a.name === b.name ? a.ratio.localeCompare(b.ratio) : a.name.localeCompare(b.name)));
writeFileSync(
  path.join(here, "..", "tests", "fixtures", "config_baseline.json"),
  `${JSON.stringify({ schemaVersion: 1, rows }, null, 2)}\n`,
);
console.log(`captured ${rows.length} ratios`);
