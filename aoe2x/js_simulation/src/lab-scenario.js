// Canonical golden-scenario inputs used by both AOE2 Lab simulation workers
// and artifact playback. This module contains scenario facts only: map,
// first-N placement cells, patrols, P4, diplomacy, and triggers. Combat
// outcomes remain entirely inside the generic engine.
import { buildArenaPhysicsMap } from "./arena-physics-map.js";
import {
  formationOpeningPatrol,
  validateFormationFixture,
} from "./formation-model.js";
import { resolveFamily } from "./placement.js";
import { unitBySlug } from "./unit-registry.js";


export const GOLDEN_SCENARIO_SHA256 = Object.freeze({
  melee_vs_melee: "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e",
  ranged_vs_ranged: "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
  ranged_vs_melee: "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
  melee_vs_ranged: "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
});


export function isRangedClass(unitClass) {
  return unitClass === "mobile_ranged" || unitClass === "siege_ranged";
}


export function scenarioFamilyFor(side2, side3) {
  const ranged2 = isRangedClass(side2.class);
  const ranged3 = isRangedClass(side3.class);
  if (!ranged2 && !ranged3) return "melee_vs_melee";
  if (ranged2 && ranged3) return "ranged_vs_ranged";
  return ranged2 ? "ranged_vs_melee" : "melee_vs_ranged";
}


function cells(rows, owner) {
  if (!Array.isArray(rows) || rows.length !== 27) {
    throw new Error(`golden ${owner} side must contain exactly 27 cells`);
  }
  return Object.freeze(rows.map((row) => {
    if ((row.player_id ?? owner) !== owner
        || !Number.isFinite(row.position?.x) || !Number.isFinite(row.position?.y)) {
      throw new Error(`invalid golden placement for Player ${owner}`);
    }
    return Object.freeze({ x: row.position.x, y: row.position.y });
  }));
}


function victoryTeams(family) {
  if (family === "ranged_vs_melee") {
    return Object.freeze([
      Object.freeze({ winnerOwner: 2, owners: Object.freeze([2, 4]) }),
      Object.freeze({ winnerOwner: 3, owners: Object.freeze([3]) }),
    ]);
  }
  if (family === "melee_vs_ranged") {
    return Object.freeze([
      Object.freeze({ winnerOwner: 2, owners: Object.freeze([2]) }),
      Object.freeze({ winnerOwner: 3, owners: Object.freeze([3, 4]) }),
    ]);
  }
  return Object.freeze([
    Object.freeze({ winnerOwner: 2, owners: Object.freeze([2]) }),
    Object.freeze({ winnerOwner: 3, owners: Object.freeze([3]) }),
  ]);
}


function resolveUnit(unitOrSlug) {
  return typeof unitOrSlug === "string" ? unitBySlug(unitOrSlug) : unitOrSlug;
}


export async function loadLabScenario(root, side2Unit, side3Unit, {
  includeBuffer = true,
} = {}) {
  const side2 = resolveUnit(side2Unit);
  const side3 = resolveUnit(side3Unit);
  if (!side2 || !side3) throw new RangeError("both units must be registered");
  const family = scenarioFamilyFor(side2, side3);
  const { readFile } = await import("node:fs/promises");
  const [mapFixture, placement] = await Promise.all([
    readFile(new URL("fixtures/golden_map.json", root), "utf8").then(JSON.parse),
    family === "melee_vs_melee"
      ? loadMeleePlacement(root)
      : loadRangedPlacement(root, family, { includeBuffer }),
  ]);
  return Object.freeze({
    family,
    engineFamily: resolveFamily({ side2Class: side2.class, side3Class: side3.class }),
    map: buildArenaPhysicsMap(mapFixture),
    ...placement,
  });
}


async function loadMeleePlacement(root) {
  const { readFile } = await import("node:fs/promises");
  const fixture = validateFormationFixture(JSON.parse(await readFile(
    new URL("fixtures/golden_formation_27v27.json", root), "utf8",
  )));
  if (fixture.source?.sha256 !== GOLDEN_SCENARIO_SHA256.melee_vs_melee) {
    throw new Error("melee golden formation source hash does not match")
  }
  return Object.freeze({
    placementByOwner: Object.freeze({
      2: cells(fixture.sides["2"], 2),
      3: cells(fixture.sides["3"], 3),
    }),
    openingPatrolByOwner: formationOpeningPatrol(fixture),
    placementSource: "current-melee-golden",
    goldenSha256: fixture.source.sha256,
  });
}


async function loadRangedPlacement(root, family, { includeBuffer = true } = {}) {
  const { readFile } = await import("node:fs/promises");
  const fixture = JSON.parse(await readFile(
    new URL("fixtures/current_ranged_golden_formations.json", root), "utf8",
  ));
  const selected = fixture.schema_version === 1 ? fixture.families?.[family] : null;
  if (!selected || selected.source?.sha256 !== GOLDEN_SCENARIO_SHA256[family]) {
    throw new Error(`${family} golden formation source hash does not match`);
  }
  const placementByOwner = Object.freeze({
    2: cells(selected.sides?.["2"], 2),
    3: cells(selected.sides?.["3"], 3),
  });
  const mixed = family === "ranged_vs_melee" || family === "melee_vs_ranged";
  const p4Rows = selected.sides?.["4"] ?? [];
  if ((mixed && p4Rows.length !== 9) || (!mixed && p4Rows.length !== 0)) {
    throw new Error(`${family} golden has the wrong Player 4 roster`);
  }
  const p4Cells = Object.freeze(p4Rows.map((row) => {
    if (row.player_id !== 4 || row.unit_const !== 448
        || !Number.isFinite(row.position?.x) || !Number.isFinite(row.position?.y)) {
      throw new Error(`${family} golden has an invalid Player 4 unit`);
    }
    return Object.freeze({ x: row.position.x, y: row.position.y });
  }));
  const expectedTriggers = mixed ? 2 : 1;
  if (!Array.isArray(selected.triggers) || selected.triggers.length !== expectedTriggers) {
    throw new Error(`${family} golden has the wrong trigger set`);
  }
  const directTrigger = Object.freeze({
    ...selected.triggers[0],
    effects: Object.freeze(selected.triggers[0].effects.filter(({ owner }) => owner !== 4)),
  });
  const directDiplomacy = Object.freeze({
    2: Object.freeze({ 3: 3 }),
    3: Object.freeze({ 2: 3 }),
  });
  return Object.freeze({
    placementByOwner,
    ...(mixed && includeBuffer ? {
      auxiliaryArmiesByOwner: Object.freeze({
        4: Object.freeze({ slug: "scout_cavalry", cells: p4Cells }),
      }),
    } : {}),
    diplomacyByOwner: mixed && !includeBuffer
      ? directDiplomacy
      : Object.freeze(selected.initial_diplomacy),
    triggers: mixed && !includeBuffer
      ? Object.freeze([directTrigger])
      : Object.freeze(selected.triggers),
    victoryTeams: mixed && !includeBuffer
      ? victoryTeams("direct")
      : victoryTeams(family),
    preserveOwnerOrientation: true,
    placementSource: "current-ranged-golden",
    goldenSha256: selected.source.sha256,
  });
}
