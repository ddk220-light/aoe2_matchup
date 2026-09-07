import { runFight } from "../src/fight.js";
import { unitDescriptorFromMechanics, validateMechanicsProfile } from "../src/mechanics-schema.js";
import { loadLabScenario } from "../src/lab-scenario.js";

const ROOT = new URL("../", import.meta.url);

export async function runHeadlessJob(job) {
  if (!job || typeof job !== "object" || Array.isArray(job)) {
    throw new TypeError("job must be an object");
  }
  const teams = job.teams;
  if (!Array.isArray(teams) || teams.length !== 2) {
    throw new TypeError("job.teams must contain exactly two teams");
  }
  const [side2, side3] = teams;
  validateMechanicsProfile(side2.mechanics);
  validateMechanicsProfile(side3.mechanics);
  const explicitCounts = side2.count !== undefined || side3.count !== undefined;
  if (explicitCounts && (!Number.isSafeInteger(side2.count) || !Number.isSafeInteger(side3.count))) {
    throw new TypeError("both team counts must be integers");
  }
  const seed = job.seed ?? 0;
  if (!Number.isSafeInteger(seed) || seed < 0 || seed > 0xffffffff) {
    throw new RangeError("seed must be a uint32");
  }
  const descriptors = {
    2: unitDescriptorFromMechanics(side2.mechanics),
    3: unitDescriptorFromMechanics(side3.mechanics),
  };
  let scenario = job.engagementMode
    ? await loadLabScenario(ROOT, descriptors[2], descriptors[3], {
      includeBuffer: job.engagementMode === "ranged_buffer",
    })
    : (job.scenario ?? {});
  const suppliedAuxiliary = job.scenario?.auxiliaryArmiesByOwner;
  if (job.engagementMode === "ranged_buffer"
      && !suppliedAuxiliary?.[4]?.mechanics
      && !suppliedAuxiliary?.["4"]?.mechanics) {
    throw new TypeError(
      "ranged_buffer jobs require scenario.auxiliaryArmiesByOwner.4.mechanics",
    );
  }
  if (suppliedAuxiliary && scenario.auxiliaryArmiesByOwner) {
    scenario = {
      ...scenario,
      auxiliaryArmiesByOwner: Object.fromEntries(Object.entries(
        scenario.auxiliaryArmiesByOwner,
      ).map(([owner, specification]) => [owner, {
        ...specification,
        mechanics: suppliedAuxiliary[owner]?.mechanics,
      }])),
    };
  }
  const result = await runFight(ROOT, {
    ...scenario,
    side2Slug: side2.mechanics.unit_slug,
    side3Slug: side3.mechanics.unit_slug,
    ...(explicitCounts ? { n2: side2.count, n3: side3.count } : { budget: job.budget }),
    openingSeed: seed,
    preserveOwnerOrientation: job.preserveOwnerOrientation
      ?? scenario.preserveOwnerOrientation
      ?? false,
    disableAiOrders: job.disableAiOrders ?? Boolean(job.engagementMode),
    disableKiting: job.disableKiting ?? Boolean(job.engagementMode),
    retainSnapshots: job.retainSnapshots === true,
    mechanicsBySide: {
      2: side2.mechanics,
      3: side3.mechanics,
    },
    unitDescriptorBySide: descriptors,
  });
  return {
    jobId: job.jobId ?? null,
    seed,
    winnerOwner: result.winnerOwner,
    winnerHp: result.winnerHp,
    startingHpByOwner: result.startingHpByOwner,
    ticks: result.ticks,
    family: result.family,
    side2: result.side2,
    side3: result.side3,
    finalStateHash: result.finalStateHash,
    eventLogHash: result.eventLogHash,
    ...(job.retainSnapshots === true
      ? { unitIndex: result.unitIndex, snapshots: result.snapshots }
      : {}),
  };
}
