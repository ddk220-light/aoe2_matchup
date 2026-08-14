import { createHash } from "node:crypto";
import { createReadStream, constants } from "node:fs";
import { copyFile, mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { DEDICATED_GOLDEN_MATCHUPS } from "../src/dedicated-golden-corpus.js";


const KNOWN_HASHES = new Map([
  ["aoe2_golden_kiting_arbalestervschampion_2026-08-06.zip", "7A661923102517825DC1D7BC49DF69FD5A365F69F1CC6E54805B798E3A68B0A3"],
  ["aoe2_golden_kiting_arbalestervselephant_2026-08-06.zip", "25B5C474F5731711017F90C26A174B87A84B3E8403C4B0886452D2DD25FFB74A"],
  ["aoe2_golden_kiting_arbalestervsfirelancer_2026-08-06.zip", "2993135C74E069273CFE689C398C0316DD02F29D01E95D20FB3F1D86C3B42D38"],
  ["aoe2_golden_kiting_arbalestervspaladin_2026-08-06.zip", "2049164F01A4E237AEABACBAA120837AE60A0E133AC0319C645210DA16717068"],
  ["aoe2_golden_kiting_arbalestervssteppe_2026-08-06.zip", "3F4D8F0B69AE82A874E28FD1A9B801C9B0DFB4F46A17B4692F4457ADB2CB9C34"],
  ["aoe2_golden_kiting_eliteskirmvschampion_2026-08-06.zip", "974A951AD0E9AE211A0BF40913EF6028187732404C6F8514E637C64B79D54716"],
  ["aoe2_golden_kiting_eliteskirmvselephant_2026-08-06.zip", "12984A63F05BDCFB3242C46CD45144D2E6B8D304C7AF15C951CBB41652095EB6"],
  ["aoe2_golden_kiting_eliteskirmvspaladin_2026-08-06.zip", "631C21349C4ECE89A9DB997C2AD8873CA98B04EC4DB89EACF9BAC65EEE589E1F"],
  ["aoe2_golden_kiting_eliteskirmvssteppe_2026-08-06.zip", "9500E4703ACB48273C83D71CE4313820BA92391EE80CAF2882F92AF12B46414B"],
  ["aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip", "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5"],
  ["aoe2_golden_kiting_hcavarchervselephant_2026-08-06.zip", "CB7D0D448D35C09013C028FBC5A38E6267D8BBA09B3DB02125E9BD3E746A3F90"],
  ["aoe2_golden_kiting_hcavarchervspaladin_2026-08-06.zip", "8902DE64B120E6302860F8F9B35B572523B29B4C0F305C65A7DA6D0C286F7968"],
  ["aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip", "74D83F2EBE0D7EE89AD76C50D68147D4D0B085FA0223B1CECB59FF83198C9373"],
  ["aoe2_golden_ranged_scorpionvschampion_2026-08-05.zip", "30235D984F503172123DFD2D4D24AB9AB513EE57A29C6825AF2252B7879B6EDB"],
  ["aoe2_golden_ranged_scorpionvspaladin_2026-08-05.zip", "32135C127DE9CB2A07C78E5323C3D13F9671803480F379B6627AAE638750708E"],
]);


const sourceDir = path.resolve(process.argv[2] ?? "");
if (!process.argv[2]) throw new Error("usage: node tools/intake_dedicated_ranged_melee_goldens.mjs <source-directory>");
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const destinationDir = path.join(projectRoot, "calibration", "source");
const manifestPath = path.join(destinationDir, "dedicated_ranged_melee_sources.json");

await mkdir(destinationDir, { recursive: true });
const entries = [];
for (const [index, expected] of DEDICATED_GOLDEN_MATCHUPS.entries()) {
  const source = path.join(sourceDir, expected.archive);
  const destination = path.join(destinationDir, expected.archive);
  const sourceStats = await stat(source);
  process.stdout.write(`[${index + 1}/17] hashing source ${expected.archive} (${gib(sourceStats.size)} GiB)\n`);
  const sourceHash = await sha256(source);
  const knownHash = KNOWN_HASHES.get(expected.archive);
  if (knownHash && sourceHash !== knownHash) {
    throw new Error(`external SHA-256 differs from recorded fixture: ${expected.archive}\nexpected ${knownHash}\nactual   ${sourceHash}`);
  }

  let copied = false;
  try {
    const destinationStats = await stat(destination);
    if (destinationStats.size !== sourceStats.size) {
      throw new Error(`existing destination has different size: ${destination}`);
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    process.stdout.write(`[${index + 1}/17] copying ${expected.archive}\n`);
    await copyFile(source, destination, constants.COPYFILE_EXCL);
    copied = true;
  }

  process.stdout.write(`[${index + 1}/17] verifying project-local copy${copied ? "" : " (already present)"}\n`);
  const destinationHash = await sha256(destination);
  if (destinationHash !== sourceHash) {
    throw new Error(`copied SHA-256 mismatch: ${expected.archive}\nsource ${sourceHash}\ncopy   ${destinationHash}`);
  }
  entries.push({
    archive: expected.archive,
    archive_path: `aoe2x/js_simulation/calibration/source/${expected.archive}`,
    zip_sha256: sourceHash,
    source_kind: "raw_frames_bin",
    authorized: true,
    authorized_source: source,
    authorized_on: "2026-08-14",
    bytes: sourceStats.size,
  });
  process.stdout.write(`[${index + 1}/17] verified ${sourceHash}\n`);
}

const manifest = {
  corpus: "dedicated_ranged_melee_goldens",
  archive_count: entries.length,
  ratio_count: entries.length * 5,
  tape_run_count: entries.length * 25,
  archives: entries,
};
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
process.stdout.write(`manifest ${manifestPath}\n`);


async function sha256(filename) {
  const hash = createHash("sha256");
  await new Promise((resolve, reject) => {
    const input = createReadStream(filename);
    input.on("data", (chunk) => hash.update(chunk));
    input.on("error", reject);
    input.on("end", resolve);
  });
  return hash.digest("hex").toUpperCase();
}


function gib(bytes) {
  return (bytes / 1024 / 1024 / 1024).toFixed(2);
}
