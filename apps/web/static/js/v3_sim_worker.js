import { runFight } from "/v3-runtime/src/fight.js";
import { buildArenaPhysicsMap } from "/v3-runtime/src/arena-physics-map.js";
import {
  unitDescriptorFromMechanics,
  validateMechanicsProfile,
} from "/v3-runtime/src/mechanics-schema.js";

const ENGINE_ROOT = new URL("/v3-runtime/", self.location.origin);
const SNAPSHOT_STRIDE = 2;
const MESSAGE_BATCH_SIZE = 12;

function requireBattleConfig(config) {
  if (!config || config.schemaVersion !== 1 || config.engineVersion !== "simulationv3") {
    throw new TypeError("worker requires a simulationv3 battle config");
  }
  if (!Array.isArray(config.teams) || config.teams.length !== 2) {
    throw new TypeError("battle config must contain exactly two teams");
  }
  for (const team of config.teams) {
    validateMechanicsProfile(team.mechanics);
    if (!Number.isSafeInteger(team.count) || team.count < 1) {
      throw new RangeError("battle config team counts must be positive integers");
    }
  }
  return config;
}

function fightOptions(config, onSnapshot) {
  const [side2, side3] = config.teams;
  const scenario = config.scenario;
  if (!scenario?.mapFixture?.map) {
    throw new TypeError("battle config is missing its Golden Arena map");
  }
  return {
    side2Slug: side2.mechanics.unit_slug,
    n2: side2.count,
    side3Slug: side3.mechanics.unit_slug,
    n3: side3.count,
    map: buildArenaPhysicsMap(scenario.mapFixture),
    placementByOwner: scenario.placementByOwner,
    openingPatrolByOwner: scenario.openingPatrolByOwner,
    placementSource: scenario.goldenSha256,
    preserveOwnerOrientation: scenario.preserveOwnerOrientation === true,
    auxiliaryArmiesByOwner: scenario.auxiliaryArmiesByOwner,
    diplomacyByOwner: scenario.diplomacyByOwner,
    triggers: scenario.triggers,
    victoryTeams: scenario.victoryTeams,
    openingSeed: config.seed,
    // Golden scenarios supply the patrol and diplomacy orders. The legacy
    // free-form AI/kiting controllers must not run on top of those orders.
    disableAiOrders: true,
    disableKiting: true,
    retainSnapshots: false,
    onSnapshot,
    mechanicsBySide: {
      2: side2.mechanics,
      3: side3.mechanics,
    },
    unitDescriptorBySide: {
      2: unitDescriptorFromMechanics(side2.mechanics),
      3: unitDescriptorFromMechanics(side3.mechanics),
    },
    displayCivBySide: { 2: side2.civ, 3: side3.civ },
  };
}

self.onmessage = async ({ data }) => {
  const runId = data?.runId;
  try {
    const config = requireBattleConfig(data?.config);
    const batch = [];
    let lastPublishedTick = -1;
    let lastSnapshot = null;
    const flush = () => {
      if (batch.length === 0) return;
      self.postMessage({ type: "snapshots", runId, snapshots: batch.splice(0) });
    };
    self.postMessage({ type: "started", runId });
    const result = await runFight(ENGINE_ROOT, fightOptions(config, (snapshot) => {
      lastSnapshot = snapshot;
      if (snapshot.tick !== 0 && snapshot.tick % SNAPSHOT_STRIDE !== 0
          && snapshot.events.length === 0) return;
      batch.push(snapshot);
      lastPublishedTick = snapshot.tick;
      if (batch.length >= MESSAGE_BATCH_SIZE) flush();
    }));
    if (lastSnapshot && lastSnapshot.tick !== lastPublishedTick) batch.push(lastSnapshot);
    flush();
    self.postMessage({ type: "complete", runId, result });
  } catch (error) {
    self.postMessage({
      type: "error",
      runId,
      error: String(error?.message ?? error),
      stack: String(error?.stack ?? ""),
    });
  }
};
