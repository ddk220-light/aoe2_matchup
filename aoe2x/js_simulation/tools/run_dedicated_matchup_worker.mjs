import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runDedicatedGoldenSuite } from "./run_dedicated_ranged_melee_suite.mjs";


export async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 2 || argv[0] !== "--matchup-id" || !argv[1]) {
    throw new Error("usage: run_dedicated_matchup_worker.mjs --matchup-id MATCHUP_ID");
  }
  const matchupId = argv[1];
  let lastReported = 0;
  const report = await runDedicatedGoldenSuite({
    matchupIds: [matchupId],
    onProgress: ({ completed, total, ratio }) => {
      if (completed === total || completed - lastReported >= 5) {
        lastReported = completed;
        process.stderr.write(`[${completed}/${total}] ${matchupId} ${ratio}\n`);
      }
    },
  });
  process.stdout.write(JSON.stringify(report));
  return report;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
