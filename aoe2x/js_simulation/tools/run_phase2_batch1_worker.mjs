import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runPhase2Batch1Suite } from "./run_phase2_batch1_suite.mjs";


export async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 2 || argv[0] !== "--row-id" || !argv[1]) {
    throw new Error("usage: run_phase2_batch1_worker.mjs --row-id ROW_ID");
  }
  const rowId = argv[1];
  const report = await runPhase2Batch1Suite({
    rowIds: [rowId],
    onProgress: ({ completed, total }) => {
      if (completed === total || completed % 5 === 0) {
        process.stderr.write(`[${completed}/${total}] ${rowId}\n`);
      }
    },
  });
  process.stdout.write(JSON.stringify(report));
  return report;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
