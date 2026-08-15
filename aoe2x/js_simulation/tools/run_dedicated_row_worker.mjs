import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runDedicatedGoldenSuite } from "./run_dedicated_ranged_melee_suite.mjs";


export async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 2 || argv[0] !== "--row-id" || !argv[1]) {
    throw new Error("usage: run_dedicated_row_worker.mjs --row-id ROW_ID");
  }
  const rowId = argv[1];
  const report = await runDedicatedGoldenSuite({
    rowIds: [rowId],
    onProgress: ({ completed, total, ratio }) => {
      process.stderr.write(`[${completed}/${total}] ${rowId} ${ratio}\n`);
    },
  });
  process.stdout.write(JSON.stringify(report));
  return report;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
