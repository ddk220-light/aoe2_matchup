import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  auditSimulationSource,
  compareChampionSuite,
  renderChampionMarkdown,
  serializeChampionReport,
} from "../src/champion-comparison.js";
import { runChampionRatio } from "../tests/support/champion-ratio.mjs";


const RATIOS = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const ROOT_URL = new URL("../", import.meta.url);
const AUTHORIZED_TRUTH_URL = new URL(
  "calibration/fixtures/champion_basics.json",
  ROOT_URL,
);
const CLOCK_URL = new URL(
  "calibration/reports/champion_clock_forensics.json",
  ROOT_URL,
);
const MECHANICS_URL = new URL(
  "fixtures/unit_stats/champion_chinese_imperial.json",
  ROOT_URL,
);
const PHYSICS_SOURCE_PATHS = Object.freeze([
  "src/champion-scenarios.js",
  "src/formation-model.js",
  "src/map-model.js",
  "src/simulation-clock.js",
  "src/canonical-json.js",
  "src/combat/attacks.js",
  "src/combat/collision.js",
  "src/combat/local-avoidance.js",
  "src/combat/movement.js",
  "src/combat/targeting.js",
  "src/combat/unit-state.js",
  "src/combat/world.js",
  "tests/support/champion-ratio.mjs",
]);
const SOURCE_AUDIT_OPTIONS = Object.freeze({
  allowances: Object.freeze([
    Object.freeze({
      file: "src/champion-scenarios.js",
      category: "ratio-specific branch",
      token: "if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {",
      context: "if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {",
      expectedCount: 1,
      reason: "locked ratio inventory and roster validation select starting state; they do not alter combat physics",
    }),
    Object.freeze({
      file: "src/champion-scenarios.js",
      category: "owner-specific branch",
      token: "owner === 2",
      context: "2: units.filter(({ owner }) => owner === 2).map(({ referenceId }) => referenceId),",
      expectedCount: 1,
      reason: "locked roster metadata groups scenario units without altering combat physics",
    }),
    Object.freeze({
      file: "src/champion-scenarios.js",
      category: "owner-specific branch",
      token: "owner === 3",
      context: "3: units.filter(({ owner }) => owner === 3).map(({ referenceId }) => referenceId),",
      expectedCount: 1,
      reason: "locked roster metadata groups scenario units without altering combat physics",
    }),
    ...Object.freeze([
      "if (!['default', 'counterclockwise'].includes(orientation)) {",
      "if (orientation === \"counterclockwise\") return { x: y, y: mapWidth - x };",
      "if (orientation === \"counterclockwise\") return { x: mapWidth - y, y: x };",
      "const viewedA = orientation === \"counterclockwise\"",
      "const viewedB = orientation === \"counterclockwise\"",
    ].map((context) => Object.freeze({
      file: "src/map-model.js",
      category: "global turn rule",
      token: "counterclockwise",
      context,
      expectedCount: 1,
      reason: "counterclockwise is the locked map-view coordinate transform, not a unit steering rule",
    }))),
    Object.freeze({
      file: "src/combat/attacks.js",
      category: "HP/damage modifier",
      token: "damage +=",
      context: "damage += Math.max(0, requireFinite(attack, `attack class ${classId}`) - armor);",
      expectedCount: 1,
      reason: "source-backed matching armor-class bonuses are accumulated before the AoE minimum-damage rule",
    }),
    Object.freeze({
      file: "tests/support/champion-ratio.mjs",
      category: "ratio-specific branch",
      token: "if (fixture.ratios?.[ratio]?.runs?.length !== repeatCount) {",
      context: "if (fixture.ratios?.[ratio]?.runs?.length !== repeatCount) {",
      expectedCount: 1,
      reason: "authorized ratio inventory and fixture validation select scenarios; they do not alter combat physics",
    }),
  ]),
  exclusions: Object.freeze([
    Object.freeze({
      file: "src/champion-comparison.js",
      reason: "reporting and static-lint implementation is self-referential and does not advance simulation physics",
    }),
  ]),
});


async function loadJson(url) {
  return JSON.parse(await readFile(url, "utf8"));
}


function requireAuthorizedTruth(url) {
  if (resolve(fileURLToPath(url)) !== resolve(fileURLToPath(AUTHORIZED_TRUTH_URL))) {
    throw new Error(
      "the Champion suite may read only the authorized project-local clean-room truth fixture",
    );
  }
}


export async function buildChampionReport({ truthUrl = AUTHORIZED_TRUTH_URL } = {}) {
  requireAuthorizedTruth(truthUrl);
  const [truth, clockEvidence, mechanics, physicsRows] = await Promise.all([
    loadJson(truthUrl),
    loadJson(CLOCK_URL),
    loadJson(MECHANICS_URL),
    Promise.all(PHYSICS_SOURCE_PATHS.map(async (path) => [
      path,
      await readFile(new URL(path, ROOT_URL), "utf8"),
    ])),
  ]);
  const simulationResults = RATIOS.map((ratio) => ({
    ratio,
    runs: [
      runChampionRatio(ratio),
      runChampionRatio(ratio),
      runChampionRatio(ratio, { reverseUnits: true }),
    ],
  }));
  return compareChampionSuite({
    truth,
    simulationResults,
    clockEvidence,
    mechanics,
    sourceAudit: auditSimulationSource(
      Object.fromEntries(physicsRows),
      SOURCE_AUDIT_OPTIONS,
    ),
  });
}


function parentDirectory(pathOrUrl) {
  return pathOrUrl instanceof URL
    ? new URL(".", pathOrUrl)
    : dirname(resolve(pathOrUrl));
}


export async function writeChampionReport({ report, outputJson, outputMarkdown } = {}) {
  if (!outputJson || !outputMarkdown) {
    throw new TypeError("both JSON and Markdown output paths are required");
  }
  await Promise.all([
    mkdir(parentDirectory(outputJson), { recursive: true }),
    mkdir(parentDirectory(outputMarkdown), { recursive: true }),
  ]);
  await Promise.all([
    writeFile(outputJson, serializeChampionReport(report), "utf8"),
    writeFile(outputMarkdown, renderChampionMarkdown(report), "utf8"),
  ]);
}


function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!["--truth", "--output-json", "--output-md"].includes(flag) || !value) {
      throw new Error(
        "usage: run_champion_suite.mjs --truth <fixture> --output-json <file> --output-md <file>",
      );
    }
    if (values[flag] !== undefined) throw new Error(`duplicate argument ${flag}`);
    values[flag] = value;
  }
  for (const flag of ["--truth", "--output-json", "--output-md"]) {
    if (values[flag] === undefined) throw new Error(`missing required argument ${flag}`);
  }
  return values;
}


export async function main(argv = process.argv.slice(2)) {
  const values = parseArguments(argv);
  const report = await buildChampionReport({
    truthUrl: pathToFileURL(resolve(values["--truth"])),
  });
  await writeChampionReport({
    report,
    outputJson: resolve(values["--output-json"]),
    outputMarkdown: resolve(values["--output-md"]),
  });
  if (!report.passed) process.exitCode = 1;
  return report;
}


if (
  process.argv[1]
  && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))
) {
  await main();
}
