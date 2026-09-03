import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";


const REPOSITORY_ROOT = resolve(fileURLToPath(new URL("../../../../", import.meta.url)));
const ENGINE_ROOT = resolve(REPOSITORY_ROOT, "aoe2x/js_simulation");
const HASH_ROOTS = Object.freeze([
  "src",
  "fixtures/golden_map.json",
  "fixtures/unit_stats",
  "calibration/source/phase2_source.json",
  "calibration/fixtures/phase2/batch1_truth.json",
  "tools/run_phase2_batch1_suite.mjs",
  "tools/run_phase2_batch1_worker.mjs",
  "tools/run_recoverable_phase2_batch1.mjs",
]);


function gitText(...args) {
  return execFileSync("git", args, {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
    windowsHide: true,
  });
}


function gitBlob(...args) {
  return execFileSync("git", args, {
    cwd: REPOSITORY_ROOT,
    encoding: "buffer",
    maxBuffer: 64 * 1024 * 1024,
    windowsHide: true,
  });
}


function listCommitFiles(commit) {
  const prefix = "aoe2x/js_simulation/";
  const paths = gitText("ls-tree", "-r", "--name-only", commit, "--", ...HASH_ROOTS.map(
    (path) => `${prefix}${path}`,
  )).trim().split(/\r?\n/u).filter(Boolean);
  return paths.toSorted((left, right) => {
    const leftAbsolute = resolve(REPOSITORY_ROOT, left).replaceAll("\\", "/");
    const rightAbsolute = resolve(REPOSITORY_ROOT, right).replaceAll("\\", "/");
    return leftAbsolute.localeCompare(rightAbsolute);
  });
}


function hashCommit(commit) {
  const hash = createHash("sha256");
  const files = listCommitFiles(commit);
  for (const repositoryPath of files) {
    const absolutePath = resolve(REPOSITORY_ROOT, repositoryPath);
    hash.update(absolutePath.replaceAll("\\", "/"));
    hash.update("\0");
    hash.update(gitBlob("show", `${commit}:${repositoryPath}`));
    hash.update("\0");
  }
  return { commit, files: files.length, signature: hash.digest("hex") };
}


const commits = process.argv.slice(2);
if (!commits.length) {
  throw new Error("usage: node identify_phase2_engine_snapshot.mjs COMMIT [COMMIT ...]");
}
process.stdout.write(`${JSON.stringify(commits.map(hashCommit), null, 2)}\n`);
