import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";


const REPOSITORY_ROOT = resolve(fileURLToPath(new URL("../../../../", import.meta.url)));
const ENGINE_PREFIX = "aoe2x/js_simulation/";


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


const [commit, outputArgument] = process.argv.slice(2);
if (!commit || !outputArgument) {
  throw new Error("usage: node materialize_engine_snapshot.mjs COMMIT OUTPUT_DIR");
}
const outputDirectory = resolve(outputArgument);
const files = gitText(
  "ls-tree",
  "-r",
  "--name-only",
  commit,
  "--",
  `${ENGINE_PREFIX}src`,
  `${ENGINE_PREFIX}package.json`,
).trim().split(/\r?\n/u).filter(Boolean);
if (!files.some((path) => path === `${ENGINE_PREFIX}src/combat/world.js`)) {
  throw new Error(`commit ${commit} does not contain the JS simulation engine`);
}

for (const repositoryPath of files) {
  const relativePath = repositoryPath.slice(ENGINE_PREFIX.length);
  const destination = resolve(outputDirectory, relativePath);
  await mkdir(dirname(destination), { recursive: true });
  await writeFile(destination, gitBlob("show", `${commit}:${repositoryPath}`));
}
process.stdout.write(`${JSON.stringify({ commit, outputDirectory, files: files.length })}\n`);

