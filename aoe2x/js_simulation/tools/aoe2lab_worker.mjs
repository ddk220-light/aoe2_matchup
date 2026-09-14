// Stateless engine boundary for AOE2 Lab. `plan` accepts one JSON request on
// stdin. `run-seed` accepts a persisted plan and atomically writes one complete
// viewer playback. Multiple processes can therefore consume all CPU cores
// without sharing mutable engine state.
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { runFight } from "../src/fight.js";
import {
  GOLDEN_SCENARIO_SHA256,
  isRangedClass,
  loadLabScenario,
  scenarioFamilyFor,
} from "../src/lab-scenario.js";
import { resolveFamily } from "../src/placement.js";
import { unitBySlug } from "../src/unit-registry.js";
import { recordingUnitBySlug } from "../src/recording-unit-registry.js";
import { resolvePurchaseCost, COST_BASIS, COST_CATALOG_SHA256 } from "../src/recording-costs.js";


const SIM_ROOT = new URL("../", import.meta.url);


function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => (
      `${JSON.stringify(key)}:${canonical(value[key])}`
    )).join(",")}}`;
  }
  return JSON.stringify(value);
}


function hash(value) {
  return createHash("sha256").update(canonical(value)).digest("hex");
}


function requireInteger(value, name, minimum = 1, maximum = 27) {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new RangeError(`${name} must be an integer ${minimum}-${maximum}`);
  }
  return value;
}


function requireWeight(value, name) {
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    throw new RangeError(`${name} weight must be finite and between 0 and 100`);
  }
  return value;
}


function weightedCost(unit, weights) {
  return Object.entries(unit.effectiveCost).reduce(
    (total, [resource, amount]) => total + amount * weights[resource], 0,
  );
}


function deriveCounts(side2, side3, balance) {
  const mode = balance?.mode ?? "equal_resources";
  const cap = requireInteger(balance?.cap ?? 27, "balance cap");
  const weights = Object.freeze({
    food: requireWeight(balance?.weights?.food ?? 1, "food"),
    wood: requireWeight(balance?.weights?.wood ?? 1, "wood"),
    gold: requireWeight(balance?.weights?.gold ?? 1, "gold"),
  });
  const cost2 = weightedCost(side2, weights);
  const cost3 = weightedCost(side3, weights);
  const budget = balance?.maxResources ?? Infinity;
  if (budget !== Infinity && (!Number.isFinite(budget) || budget <= 0)) {
    throw new RangeError("maxResources must be positive and finite");
  }
  if (!(cost2 > 0) || !(cost3 > 0)) throw new RangeError("weighted unit costs must be positive");
  let n2;
  let n3;
  if (mode === "explicit") {
    n2 = requireInteger(balance.n2, "n2", 1, cap);
    n3 = requireInteger(balance.n3, "n3", 1, cap);
  } else if (mode === "equal_count") {
    n2 = n3 = requireInteger(balance.count ?? cap, "equal count", 1, cap);
  } else if (mode === "equal_resources") {
    if (cost2 <= cost3) {
      n2 = Math.min(cap, Math.floor(budget / cost2));
      n3 = Math.floor(n2 * cost2 / cost3);
    } else {
      n3 = Math.min(cap, Math.floor(budget / cost3));
      n2 = Math.floor(n3 * cost3 / cost2);
    }
  } else {
    throw new RangeError("balance mode must be equal_resources, equal_count, or explicit");
  }
  // Preserve legacy minimum-one rounding when no explicit budget was requested.
  if (budget === Infinity) { n2 = Math.max(1, n2); n3 = Math.max(1, n3); }
  if (n2 < 1 || n3 < 1 || n2 * cost2 > budget || n3 * cost3 > budget) {
    throw new RangeError("resource budget cannot fund both requested armies");
  }
  return Object.freeze({ mode, cap, weights, cost2, cost3, n2, n3 });
}


export function createLabPlan(request) {
  if (request?.schemaVersion !== 1) throw new TypeError("request schemaVersion must be 1");
  let side2 = recordingUnitBySlug(request.side2?.slug);
  let side3 = recordingUnitBySlug(request.side3?.slug);
  if (!side2 || !side3) {
    throw new RangeError(`unknown unit: ${request.side2?.slug ?? "?"} or ${request.side3?.slug ?? "?"}`);
  }
  side2 = {...side2, effectiveCost: resolvePurchaseCost(side2, request.side2.civ ?? side2.civ)};
  side3 = {...side3, effectiveCost: resolvePurchaseCost(side3, request.side3.civ ?? side3.civ)};
  const balance = deriveCounts(side2, side3, request.balance);
  const player4Buffer = request.scenario?.player4Buffer ?? "golden";
  if (!["golden", "none"].includes(player4Buffer)) throw new RangeError("player4Buffer must be golden or none");
  const family = request.scenario?.goldenFamily ?? scenarioFamilyFor(side2, side3);
  if (!Object.hasOwn(GOLDEN_SCENARIO_SHA256, family)) {
    throw new RangeError("goldenFamily must name an existing Golden scenario family");
  }
  if (family === "water" && balance.cap > 15) throw new RangeError("water template has 15 slots per side");
  const matchupId = `${side2.slug}_vs_${side3.slug}`;
  const base = {
    schemaVersion: 1,
    matchupId,
    side2: {
      slug: side2.slug,
      label: side2.label,
      civ: request.side2.civ ?? side2.civ,
      mechanicsCiv: side2.civ,
      class: side2.class,
      ranged: isRangedClass(side2.class),
      count: balance.n2,
      baseCost: side2.baseCost,
      effectiveCost: side2.effectiveCost,
      weightedCost: balance.cost2,
      armyWeightedResources: balance.n2 * balance.cost2,
    },
    side3: {
      slug: side3.slug,
      label: side3.label,
      civ: request.side3.civ ?? side3.civ,
      mechanicsCiv: side3.civ,
      class: side3.class,
      ranged: isRangedClass(side3.class),
      count: balance.n3,
      baseCost: side3.baseCost,
      effectiveCost: side3.effectiveCost,
      weightedCost: balance.cost3,
      armyWeightedResources: balance.n3 * balance.cost3,
    },
    balance: {
      costBasis: COST_BASIS,
      costCatalogSha256: COST_CATALOG_SHA256,
      mode: balance.mode,
      cap: balance.cap,
      weights: balance.weights,
      ...(request.balance?.maxResources !== undefined ? { maxResources: request.balance.maxResources } : {}),
      rounding: balance.mode === "equal_resources"
        ? "cheaper side capped; expensive side floored" : "none",
    },
    scenario: {
      family,
      goldenSha256: GOLDEN_SCENARIO_SHA256[family],
      placementRule: "first_n_units_in_player_order",
      hasPlayer4Gate: player4Buffer !== "none" && (family === "ranged_vs_melee" || family === "melee_vs_ranged"),
      ...(player4Buffer === "none" ? { player4Buffer: "none" } : {}),
      preserveOwnerOrientation: family !== "melee_vs_melee",
    },
    engineFamily: resolveFamily({ side2Class: side2.class, side3Class: side3.class }),
  };
  const planHash = hash(base);
  return Object.freeze({
    ...base,
    planHash,
    jobId: request.jobId ?? `${matchupId}_${planHash.slice(0, 8)}`,
  });
}


export async function runSeed(plan, seed) {
  if (plan?.scenario?.family === "water") throw new RangeError("water scenarios are recording-only; naval simulation is not supported");
  // The native ranged/ranged Golden already has no P4. An explicit no-buffer
  // request is identical there; mixed-template overrides still need fixtures.
  if (plan?.scenario?.player4Buffer === "none"
      && !(plan.scenario.family === "ranged_vs_ranged"
        && scenarioFamilyFor(plan.side2, plan.side3) === "ranged_vs_ranged")) {
    throw new RangeError("no-buffer recording plan requires a matching simulation scenario; do not compare using the default P4 screen");
  }
  if (plan?.schemaVersion !== 1 || typeof plan.planHash !== "string") {
    throw new TypeError("a persisted AOE2 Lab plan is required");
  }
  requireInteger(seed, "seed", 0, Number.MAX_SAFE_INTEGER);
  if (!unitBySlug(plan.side2.slug) || !unitBySlug(plan.side3.slug)) {
    throw new RangeError("recording-only unit has no calibrated simulation fixture; use recorder mode");
  }
  const scenario = await loadLabScenario(SIM_ROOT, plan.side2.slug, plan.side3.slug);
  if (scenario.family !== plan.scenario.family
      || scenario.goldenSha256 !== plan.scenario.goldenSha256) {
    throw new Error("plan/golden scenario provenance changed");
  }
  const result = await runFight(SIM_ROOT, {
    side2Slug: plan.side2.slug,
    n2: plan.side2.count,
    side3Slug: plan.side3.slug,
    n3: plan.side3.count,
    map: scenario.map,
    placementByOwner: scenario.placementByOwner,
    ...(scenario.openingPatrolByOwner
      ? { openingPatrolByOwner: scenario.openingPatrolByOwner } : {}),
    ...(scenario.auxiliaryArmiesByOwner
      ? { auxiliaryArmiesByOwner: scenario.auxiliaryArmiesByOwner } : {}),
    ...(scenario.diplomacyByOwner
      ? { diplomacyByOwner: scenario.diplomacyByOwner } : {}),
    ...(scenario.triggers ? { triggers: scenario.triggers } : {}),
    ...(scenario.victoryTeams ? { victoryTeams: scenario.victoryTeams } : {}),
    preserveOwnerOrientation: scenario.preserveOwnerOrientation ?? false,
    placementSource: scenario.placementSource,
    displayCivBySide: { 2: plan.side2.civ, 3: plan.side3.civ },
    disableAiOrders: true,
    disableKiting: true,
    openingSeed: seed,
    retainSnapshots: true,
  });
  return Object.freeze({
    ...result,
    mode: "aoe2-lab",
    lab: Object.freeze({
      schemaVersion: 1,
      jobId: plan.jobId,
      matchupId: plan.matchupId,
      planHash: plan.planHash,
      scenarioFamily: plan.scenario.family,
      goldenSha256: plan.scenario.goldenSha256,
    }),
  });
}


async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}


function option(argv, name) {
  const index = argv.indexOf(name);
  if (index === -1 || !argv[index + 1]) throw new Error(`missing ${name}`);
  return argv[index + 1];
}


async function atomicWrite(path, value) {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.tmp-${process.pid}-${Date.now()}`;
  await writeFile(temporary, `${JSON.stringify(value)}\n`, "utf8");
  await rename(temporary, path);
}


export async function main(argv = process.argv.slice(2)) {
  const command = argv[0];
  if (command === "plan" && argv.length === 1) {
    process.stdout.write(`${JSON.stringify(createLabPlan(JSON.parse(await readStdin())), null, 2)}\n`);
    return;
  }
  if (command === "run-seed") {
    const planPath = resolve(option(argv, "--plan"));
    const output = resolve(option(argv, "--output"));
    const seed = Number(option(argv, "--seed"));
    const plan = JSON.parse(await readFile(planPath, "utf8"));
    const result = await runSeed(plan, seed);
    await atomicWrite(output, result);
    process.stdout.write(`${JSON.stringify({
      seed,
      winnerOwner: result.winnerOwner,
      winnerHp: result.winnerHp,
      ticks: result.ticks,
      output,
    })}\n`);
    return;
  }
  throw new Error(
    "usage: aoe2lab_worker.mjs plan | run-seed --plan PLAN --seed N --output FILE",
  );
}


const isMain = process.argv[1]
  && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (isMain) await main();
