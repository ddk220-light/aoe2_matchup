import { createServer } from "node:http";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createChampionPlaybackData } from "./src/champion-comparison.js";
import { buildArenaPhysicsMap } from "./src/arena-physics-map.js";
import {
  formationOpeningPatrol,
  validateFormationFixture,
} from "./src/formation-model.js";
import { KITE_OBSERVATION_MATCHUPS } from "./src/kiting-observation-matchups.js";
import {
  FIGHT_SIDE_CAP,
  runFight,
  runHandCannoneerChampionKiting,
  runKitingObservation,
  runSoloRangedMovement,
} from "./src/fight.js";
import { FAMILIES, resolveFamily, sideCapacity } from "./src/placement.js";
import { TICKS_PER_SECOND } from "./src/simulation-clock.js";
import {
  matchupNames,
  matchupPlayback,
  matchupRatios,
  matchupTruth,
  syntheticMatchupPlayback,
} from "./src/matchup-playback.js";
import {
  SOLO_MOVEMENT_UNIT_SLUGS,
  UNIT_REGISTRY,
  unitBySlug,
} from "./src/unit-registry.js";
import {
  loadPhase2WrongWinnerCatalogue,
  runPhase2WrongWinnerPlayback,
} from "./src/phase2-wrong-winner-review.js";


const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".webp", "image/webp"],
]);

const CHAMPION_RATIOS = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const championDataByRoot = new Map();
const championPlaybackByRatio = new Map();
const catalogueByRoot = new Map();
const arenaMapByRoot = new Map();
const legacyArenaMapByRoot = new Map();
const meleeFormationByRoot = new Map();
const rangedFormationByRootAndFamily = new Map();
const problemPlaybackByRootAndId = new Map();
const LIVE_MELEE_OBSERVATIONS = Object.freeze({
  "champion|halberdier": Object.freeze({
    side2Count: 23,
    side3Count: 27,
    directory: "spanish_champion_vs_halberdier_5x_2026-08-28",
    civs: Object.freeze({ 2: "Spanish", 3: "Spanish" }),
  }),
  "champion|paladin": Object.freeze({
    side2Count: 27,
    side3Count: 16,
    directory: "spanish_champion_vs_paladin_5x_2026-08-28",
    civs: Object.freeze({ 2: "Spanish", 3: "Spanish" }),
  }),
  "paladin|elite_elephant": Object.freeze({
    side2Count: 27,
    side3Count: 21,
    directory: "spanish_paladin_vs_burmese_elephant_5x_2026-08-28",
    civs: Object.freeze({ 2: "Spanish", 3: "Burmese" }),
  }),
});
const LIVE_RANGED_OBSERVATIONS = Object.freeze({
  "arbalester|hand_cannoneer": Object.freeze({
    family: "ranged_vs_ranged", side2Count: 27, side3Count: 19,
    civs: Object.freeze({ 2: "Chinese", 3: "Spanish" }),
  }),
  "arbalester|heavy_cav_archer": Object.freeze({
    family: "ranged_vs_ranged", side2Count: 27, side3Count: 18,
    civs: Object.freeze({ 2: "Chinese", 3: "Saracens" }),
  }),
  "heavy_scorpion|hand_cannoneer": Object.freeze({
    family: "ranged_vs_ranged", side2Count: 17, side3Count: 27,
    civs: Object.freeze({ 2: "Chinese", 3: "Spanish" }),
  }),
  "heavy_scorpion|heavy_cav_archer": Object.freeze({
    family: "ranged_vs_ranged", side2Count: 18, side3Count: 27,
    civs: Object.freeze({ 2: "Chinese", 3: "Saracens" }),
  }),
  "arbalester|paladin": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 14,
    civs: Object.freeze({ 2: "Chinese", 3: "Spanish" }),
  }),
  "paladin|arbalester": Object.freeze({
    family: "melee_vs_ranged", side2Count: 14, side3Count: 27,
    civs: Object.freeze({ 2: "Spanish", 3: "Chinese" }),
  }),
  "arbalester|elite_steppe": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 17,
    civs: Object.freeze({ 2: "Chinese", 3: "Cumans" }),
  }),
  "arbalester|hussar": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 23,
    civs: Object.freeze({ 2: "Chinese", 3: "Spanish" }),
  }),
  "arbalester|champion": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 27,
    civs: Object.freeze({ 2: "Chinese", 3: "Chinese" }),
  }),
  "heavy_cav_archer|paladin": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 20,
    civs: Object.freeze({ 2: "Saracens", 3: "Spanish" }),
  }),
  "heavy_cav_archer|elite_steppe": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 24,
    civs: Object.freeze({ 2: "Saracens", 3: "Cumans" }),
  }),
  "heavy_cav_archer|hussar": Object.freeze({
    family: "ranged_vs_melee", side2Count: 21, side3Count: 27,
    civs: Object.freeze({ 2: "Saracens", 3: "Spanish" }),
  }),
  "heavy_cav_archer|champion": Object.freeze({
    family: "ranged_vs_melee", side2Count: 18, side3Count: 27,
    civs: Object.freeze({ 2: "Saracens", 3: "Chinese" }),
  }),
  "hand_cannoneer|paladin": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 19,
    civs: Object.freeze({ 2: "Spanish", 3: "Spanish" }),
  }),
  "hand_cannoneer|elite_steppe": Object.freeze({
    family: "ranged_vs_melee", side2Count: 27, side3Count: 23,
    civs: Object.freeze({ 2: "Spanish", 3: "Cumans" }),
  }),
  "hand_cannoneer|hussar": Object.freeze({
    family: "ranged_vs_melee", side2Count: 22, side3Count: 27,
    civs: Object.freeze({ 2: "Spanish", 3: "Spanish" }),
  }),
  "hand_cannoneer|champion": Object.freeze({
    family: "ranged_vs_melee", side2Count: 19, side3Count: 27,
    civs: Object.freeze({ 2: "Spanish", 3: "Chinese" }),
  }),
});
const RANGED_GOLDEN_SHA256 = Object.freeze({
  ranged_vs_ranged: "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
  ranged_vs_melee: "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
  melee_vs_ranged: "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
});


function publicFile(root, pathname) {
  if (pathname === "/") return path.join(root, "viewer", "index.html");
  if (pathname === "/reports/completed-engine"
      || pathname === "/reports/completed-engine/") {
    return path.join(
      root,
      "calibration",
      "reports",
      "completed_engine_2026-09-01",
      "report.html",
    );
  }
  if (pathname === "/api/map") return path.join(root, "fixtures", "golden_map.json");
  if (pathname === "/api/formation") {
    return path.join(root, "fixtures", "golden_formation_27v27.json");
  }

  // Presentation-only reuse of the website's current Battle Simulation
  // treatment. The allowlist deliberately excludes simulate.js, its engine,
  // and lab harnesses: this local page can share CSS/icons without importing
  // any production simulation behavior.
  const sharedFile = new Map([
    ["/static/css/base.css", ["css", "base.css"]],
    ["/static/css/simulate.css", ["css", "simulate.css"]],
    ["/static/js/constants.js", ["js", "constants.js"]],
    ["/static/js/unit_sprites.js", ["js", "unit_sprites.js"]],
  ]).get(pathname);
  const websiteStatic = path.resolve(root, "..", "..", "apps", "website", "static");
  if (sharedFile) return path.join(websiteStatic, ...sharedFile);
  const imageMatch = pathname.match(/^\/static\/img\/(.+)$/);
  if (imageMatch) {
    let relative;
    try {
      relative = decodeURIComponent(imageMatch[1]);
    } catch {
      return null;
    }
    if (!relative || relative.includes("\\") || relative.split("/").includes("..")) return null;
    const imageRoot = path.join(websiteStatic, "img");
    const candidate = path.resolve(imageRoot, relative);
    return candidate.startsWith(`${imageRoot}${path.sep}`) ? candidate : null;
  }

  const match = pathname.match(/^\/(viewer|src)\/(.+)$/);
  if (!match) return null;
  let relative;
  try {
    relative = decodeURIComponent(match[2]);
  } catch {
    return null;
  }
  if (!relative || relative.includes("\\") || relative.split("/").includes("..")) {
    return null;
  }
  const publicRoot = path.resolve(root, match[1]);
  const candidate = path.resolve(publicRoot, relative);
  return candidate.startsWith(`${publicRoot}${path.sep}`) ? candidate : null;
}


function send(response, status, body, contentType = "text/plain; charset=utf-8") {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Length": body.byteLength,
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
  });
  response.end(body);
}


function sendJson(response, status, value) {
  send(
    response,
    status,
    Buffer.from(`${JSON.stringify(value)}\n`),
    "application/json; charset=utf-8",
  );
}


function winnerOwner(winner) {
  const match = /^side([23])$/.exec(winner);
  if (!match) throw new TypeError(`invalid Champion tape winner: ${winner}`);
  return Number(match[1]);
}


function summarizeTapeRun(run, repeat) {
  const winningSide = run.summary.sides[run.winner];
  return Object.freeze({
    repeat,
    tag: run.tag,
    winnerOwner: winnerOwner(run.winner),
    winnerHp: run.aggregate_hp[run.winner].remaining,
    winnerStartingHp: run.aggregate_hp[run.winner].starting,
    survivors: winningSide.survivors,
    damageEvents: run.damage_events.length,
    durationSeconds: run.metadata.duration_s,
  });
}


async function loadChampionData(root) {
  if (!championDataByRoot.has(root)) {
    championDataByRoot.set(root, Promise.all([
      readFile(path.join(root, "calibration", "source", "source_of_truth.json"), "utf8"),
      readFile(path.join(root, "calibration", "fixtures", "champion_basics.json"), "utf8"),
      readFile(path.join(root, "fixtures", "unit_stats", "champion_chinese_imperial.json"), "utf8"),
    ]).then(([sourceBody, truthBody, mechanicsBody]) => {
      const source = JSON.parse(sourceBody);
      const truth = JSON.parse(truthBody);
      const mechanics = JSON.parse(mechanicsBody);
      return Object.freeze({
        truth: Object.freeze({
          schemaVersion: 1,
          archive: Object.freeze({
            filename: source.archive,
            sha256: source.sha256,
            recordings: source.recordings,
          }),
          ratios: Object.freeze(CHAMPION_RATIOS.map((ratio) => Object.freeze({
            ratio,
            medianWinnerHpPct: truth.ratios[ratio].median_winner_hp_pct,
            repeats: Object.freeze(truth.ratios[ratio].runs.map(
              (run, index) => summarizeTapeRun(run, index + 1),
            )),
          }))),
        }),
        mechanics: Object.freeze({
          schemaVersion: 1,
          unit: "Chinese Imperial Champion",
          unitMaster: mechanics.unit_master,
          hp: mechanics.hp,
          damageVsSelf: mechanics.derived.damage_vs_self,
          speedTilesPerSecond: mechanics.speed_tiles_per_second,
          lineOfSightTiles: mechanics.line_of_sight_tiles,
          collisionRadiusTiles: mechanics.collision_size_tiles.x,
          attackRangeTiles: mechanics.attack_range_tiles,
          reloadSeconds: mechanics.reload_seconds,
          attackDelaySeconds: mechanics.attack_delay_seconds,
          clockTicksPerSecond: TICKS_PER_SECOND,
          provenance: mechanics.provenance,
        }),
      });
    }));
  }
  return championDataByRoot.get(root);
}


function resultSelection(url) {
  const keys = [...url.searchParams.keys()];
  if (keys.length !== 2 || !keys.includes("ratio") || !keys.includes("repeat")) return null;
  const ratioValues = url.searchParams.getAll("ratio");
  const repeatValues = url.searchParams.getAll("repeat");
  if (ratioValues.length !== 1 || repeatValues.length !== 1) return null;
  const ratio = ratioValues[0];
  const repeatText = repeatValues[0];
  if (!CHAMPION_RATIOS.includes(ratio) || !/^[1-3]$/.test(repeatText)) return null;
  return { ratio, repeat: Number(repeatText) };
}


async function championPlayback(ratio) {
  if (!championPlaybackByRatio.has(ratio)) {
    championPlaybackByRatio.set(ratio, import("./tests/support/champion-ratio.mjs")
      .then(({ runChampionRatio }) => createChampionPlaybackData(runChampionRatio(ratio))));
  }
  return await championPlaybackByRatio.get(ratio);
}


function fightSelection(url) {
  const slug2 = url.searchParams.get("side2");
  const slug3 = url.searchParams.get("side3");
  const raw2 = url.searchParams.get("n2");
  const raw3 = url.searchParams.get("n3");
  const rawBudget = url.searchParams.get("budget");
  if (!slug2 || !slug3) return null;
  // Both counts omitted -> derive them from the purchase rule. One without the
  // other is a malformed request, not a half-derived fight.
  if (raw2 === null && raw3 === null) {
    if (rawBudget === null) return { side2Slug: slug2, side3Slug: slug3 };
    if (!/^[1-9]\d{2,4}$/.test(rawBudget)) return null;
    const budget = Number(rawBudget);
    if (budget > 20000) return null;
    return { side2Slug: slug2, side3Slug: slug3, budget };
  }
  if (rawBudget !== null) return null;
  if (!/^\d{1,2}$/.test(raw2 ?? "") || !/^\d{1,2}$/.test(raw3 ?? "")) return null;
  return { side2Slug: slug2, n2: Number(raw2), side3Slug: slug3, n3: Number(raw3) };
}


export function kitingObservationSelection(url) {
  const allowedKeys = new Set([
    "ranged", "melee", "navigation", "n2", "n3",
  ]);
  const keys = [...url.searchParams.keys()];
  if (keys.some((key) => !allowedKeys.has(key))
      || [...allowedKeys].some((key) => url.searchParams.getAll(key).length > 1)) return null;

  const rangedSlug = url.searchParams.get("ranged") ?? "hand_cannoneer";
  const meleeSlug = url.searchParams.get("melee") ?? "champion";
  const navigation = url.searchParams.get("navigation") ?? "cohesive";
  const matchup = KITE_OBSERVATION_MATCHUPS.find((row) => (
    row.rangedSlug === rangedSlug && row.meleeSlug === meleeSlug
  ));
  if (!matchup || !["baseline", "per-unit-grid", "cohesive"].includes(navigation)) return null;

  const raw2 = url.searchParams.get("n2");
  const raw3 = url.searchParams.get("n3");
  if (raw2 === null && raw3 === null) {
    return { rangedSlug, meleeSlug, navigation };
  }
  if ((raw2 === null) !== (raw3 === null)
      || !/^(?:[1-9]|1\d|2[01])$/.test(raw2)
      || !/^(?:[1-9]|1\d|2[01])$/.test(raw3)) return null;

  const ranged = UNIT_REGISTRY.find(({ slug }) => slug === rangedSlug);
  const melee = UNIT_REGISTRY.find(({ slug }) => slug === meleeSlug);
  const family = resolveFamily({ side2Class: ranged.class, side3Class: melee.class });
  const n2 = Number(raw2);
  const n3 = Number(raw3);
  if (n2 > sideCapacity(2, family) || n3 > sideCapacity(3, family)) return null;
  return { rangedSlug, meleeSlug, navigation, n2, n3 };
}


async function loadViewerCatalogue(root) {
  if (!catalogueByRoot.has(root)) {
    catalogueByRoot.set(root, readFile(
      path.join(root, "fixtures", "viewer_unit_catalogue.json"), "utf8",
    ).then((body) => {
      const catalogue = JSON.parse(body);
      const matches = new Map();
      for (const civilization of catalogue.civilizations ?? []) {
        for (const unit of civilization.units ?? []) {
          const key = `${civilization.name}\u0000${unit.name}`;
          if (matches.has(key)) throw new Error(`duplicate viewer catalogue row ${key}`);
          matches.set(key, unit);
        }
      }
      const enabled = UNIT_REGISTRY.map((unit) => {
        const name = unit.catalogueName ?? unit.label;
        const row = matches.get(`${unit.civ}\u0000${name}`);
        if (!row) throw new Error(`viewer catalogue has no row for ${unit.civ} / ${name}`);
        return Object.freeze({
          catalogueKey: row.catalogueKey,
          engineSlug: unit.slug,
          civ: unit.civ,
          name,
          class: unit.class,
          baseCost: unit.baseCost,
        });
      });
      return Object.freeze({ ...catalogue, enabled: Object.freeze(enabled) });
    }));
  }
  return catalogueByRoot.get(root);
}


async function loadArenaPhysicsMap(root) {
  if (!arenaMapByRoot.has(root)) {
    arenaMapByRoot.set(root, readFile(
      path.join(root, "fixtures", "golden_map.json"), "utf8",
    ).then((body) => {
      const fixture = JSON.parse(body);
      return buildArenaPhysicsMap(fixture);
    }));
  }
  return arenaMapByRoot.get(root);
}


async function loadLegacyArenaPhysicsMap(root) {
  if (!legacyArenaMapByRoot.has(root)) {
    legacyArenaMapByRoot.set(root, readFile(
      path.join(root, "fixtures", "golden_map_legacy.json"), "utf8",
    ).then((body) => buildArenaPhysicsMap(JSON.parse(body))));
  }
  return legacyArenaMapByRoot.get(root);
}


async function loadMeleeFormation(root) {
  if (!meleeFormationByRoot.has(root)) {
    meleeFormationByRoot.set(root, readFile(
      path.join(root, "fixtures", "golden_formation_27v27.json"), "utf8",
    ).then((body) => {
      const fixture = validateFormationFixture(JSON.parse(body));
      return Object.freeze({
        2: Object.freeze(fixture.sides["2"].map(({ position }) => Object.freeze({
          x: position.x,
          y: position.y,
        }))),
        3: Object.freeze(fixture.sides["3"].map(({ position }) => Object.freeze({
          x: position.x,
          y: position.y,
        }))),
        openingPatrolByOwner: formationOpeningPatrol(fixture),
      });
    }));
  }
  return meleeFormationByRoot.get(root);
}


async function loadRangedFormation(root, family) {
  if (RANGED_GOLDEN_SHA256[family] === undefined) {
    throw new RangeError(`unknown current ranged golden family ${family}`);
  }
  const cacheKey = `${root}|${family}`;
  if (!rangedFormationByRootAndFamily.has(cacheKey)) {
    rangedFormationByRootAndFamily.set(cacheKey, readFile(
      path.join(root, "fixtures", "current_ranged_golden_formations.json"), "utf8",
    ).then((body) => {
      const fixture = JSON.parse(body);
      const selected = fixture.schema_version === 1 ? fixture.families?.[family] : null;
      if (!selected || selected.source?.sha256 !== RANGED_GOLDEN_SHA256[family]) {
        throw new Error(`current ${family} formation source hash does not match`);
      }
      const references = new Set();
      const placement = {};
      for (const owner of [2, 3]) {
        const rows = selected.sides?.[String(owner)];
        if (!Array.isArray(rows) || rows.length !== 27) {
          throw new Error(`current ${family} formation needs 27 player-${owner} slots`);
        }
        placement[owner] = Object.freeze(rows.map((row) => {
          if (row.player_id !== owner || references.has(row.reference_id)
              || !Number.isFinite(row.position?.x) || !Number.isFinite(row.position?.y)) {
            throw new Error(`invalid current ${family} formation unit ${row.reference_id}`);
          }
          references.add(row.reference_id);
          return Object.freeze({ x: row.position.x, y: row.position.y });
        }));
      }
      const auxiliaryRows = selected.sides?.["4"] ?? [];
      const auxiliaryCells = Object.freeze(auxiliaryRows.map((row) => {
        if (row.player_id !== 4 || row.unit_const !== 448
            || references.has(row.reference_id)
            || !Number.isFinite(row.position?.x) || !Number.isFinite(row.position?.y)) {
          throw new Error(`invalid current ${family} player-4 unit ${row.reference_id}`);
        }
        references.add(row.reference_id);
        return Object.freeze({ x: row.position.x, y: row.position.y });
      }));
      const mixed = family === "ranged_vs_melee" || family === "melee_vs_ranged";
      if ((mixed && auxiliaryCells.length !== 9) || (!mixed && auxiliaryCells.length !== 0)) {
        throw new Error(`current ${family} formation has the wrong Player 4 roster`);
      }
      if (!Array.isArray(selected.triggers) || selected.triggers.length !== (mixed ? 2 : 1)) {
        throw new Error(`current ${family} formation has the wrong trigger set`);
      }
      const victoryTeams = family === "ranged_vs_melee"
        ? Object.freeze([
          Object.freeze({ winnerOwner: 2, owners: Object.freeze([2, 4]) }),
          Object.freeze({ winnerOwner: 3, owners: Object.freeze([3]) }),
        ])
        : family === "melee_vs_ranged"
          ? Object.freeze([
            Object.freeze({ winnerOwner: 2, owners: Object.freeze([2]) }),
            Object.freeze({ winnerOwner: 3, owners: Object.freeze([3, 4]) }),
          ])
          : Object.freeze([
            Object.freeze({ winnerOwner: 2, owners: Object.freeze([2]) }),
            Object.freeze({ winnerOwner: 3, owners: Object.freeze([3]) }),
          ]);
      return Object.freeze({
        ...placement,
        ...(mixed ? {
          auxiliaryArmiesByOwner: Object.freeze({
            4: Object.freeze({ slug: "scout_cavalry", cells: auxiliaryCells }),
          }),
        } : {}),
        diplomacyByOwner: Object.freeze(selected.initial_diplomacy),
        triggers: Object.freeze(selected.triggers),
        victoryTeams,
        preserveOwnerOrientation: true,
        sourceSha256: selected.source.sha256,
      });
    }));
  }
  return rangedFormationByRootAndFamily.get(cacheKey);
}


async function meleePlacementFor(root, selection) {
  const side2 = unitBySlug(selection.side2Slug);
  const side3 = unitBySlug(selection.side3Slug);
  if (!side2 || !side3) return undefined;
  const family = resolveFamily({ side2Class: side2.class, side3Class: side3.class });
  return family === "waves" ? loadMeleeFormation(root) : undefined;
}


function currentRangedObservation(selection) {
  const observation = LIVE_RANGED_OBSERVATIONS[
    `${selection.side2Slug}|${selection.side3Slug}`
  ];
  if (!observation) return null;
  return selection.n2 === observation.side2Count && selection.n3 === observation.side3Count
    ? observation
    : null;
}


async function placementConfigFor(root, selection) {
  const ranged = currentRangedObservation(selection);
  if (ranged) {
    const placementByOwner = await loadRangedFormation(root, ranged.family);
    return Object.freeze({
      placementByOwner,
      ...(placementByOwner.auxiliaryArmiesByOwner
        ? { auxiliaryArmiesByOwner: placementByOwner.auxiliaryArmiesByOwner }
        : {}),
      diplomacyByOwner: placementByOwner.diplomacyByOwner,
      triggers: placementByOwner.triggers,
      victoryTeams: placementByOwner.victoryTeams,
      preserveOwnerOrientation: placementByOwner.preserveOwnerOrientation,
      placementSource: "current-ranged-golden",
    });
  }
  const placementByOwner = await meleePlacementFor(root, selection);
  if (!placementByOwner) return null;
  return Object.freeze({
    placementByOwner,
    openingPatrolByOwner: placementByOwner.openingPatrolByOwner,
    placementSource: "current-melee-golden",
  });
}


function liveObservationCivs(selection) {
  const ranged = currentRangedObservation(selection);
  if (ranged) return ranged.civs;
  return LIVE_MELEE_OBSERVATIONS[
    `${selection.side2Slug}|${selection.side3Slug}`
  ]?.civs;
}


async function liveObservationOpeningConfig(root, selection) {
  const ranged = currentRangedObservation(selection);
  if (ranged?.family === "ranged_vs_ranged") {
    return Object.freeze({
      disableAiOrders: true,
      disableKiting: true,
    });
  }
  if (ranged?.family === "ranged_vs_melee" || ranged?.family === "melee_vs_ranged") {
    return Object.freeze({
      disableAiOrders: true,
      disableKiting: true,
    });
  }
  const observation = LIVE_MELEE_OBSERVATIONS[
    `${selection.side2Slug}|${selection.side3Slug}`
  ];
  if (!observation) return null;
  const observedCounts = (selection.n2 === undefined && selection.n3 === undefined)
    || (selection.n2 === observation.side2Count && selection.n3 === observation.side3Count);
  if (!observedCounts) return null;
  return Object.freeze({
    // Exact formation and PATROL destination remain scenario inputs. Recorded
    // unit-by-unit waypoints and timing are intentionally not active engine
    // inputs: continuous behavior must emerge from the mechanics.
    disableAiOrders: true,
  });
}


async function loadCurrentProblemCatalogue(root) {
  const body = await readFile(path.join(
    root,
    "calibration",
    "reports",
    "completed_engine_2026-09-01",
    "viewer_problem_catalogue.json",
  ), "utf8");
  const catalogue = JSON.parse(body);
  if (catalogue.schemaVersion !== 2 || !Array.isArray(catalogue.rows)) {
    throw new Error("current problem-matchup catalogue has an unsupported schema");
  }
  if (catalogue.rows.length === 0) {
    throw new Error("current problem-matchup catalogue is empty");
  }
  const rows = catalogue.rows.map((row) => {
    if (!/^[a-z0-9]+(?:_[a-z0-9]+)*_vs_[a-z0-9]+(?:_[a-z0-9]+)*$/.test(row.id)) {
      throw new Error(`invalid current matchup id ${row.id}`);
    }
    const [side2Slug, side3Slug] = row.id.split("_vs_");
    const side2 = unitBySlug(side2Slug);
    const side3 = unitBySlug(side3Slug);
    if (!side2 || !side3) {
      throw new Error(`current matchup ${row.id} contains an unregistered unit`);
    }
    if (!Number.isSafeInteger(row.side2?.count) || row.side2.count < 1
        || !Number.isSafeInteger(row.side3?.count) || row.side3.count < 1
        || typeof row.side2?.civ !== "string" || typeof row.side3?.civ !== "string") {
      throw new Error(`current matchup ${row.id} has an invalid roster`);
    }
    if (!Number.isSafeInteger(row.representativeSeed) || row.representativeSeed < 0) {
      throw new Error(`current matchup ${row.id} lacks a representative completed seed`);
    }
    return Object.freeze({
      ...row,
      side2: Object.freeze({ ...row.side2, slug: side2Slug, label: side2.label }),
      side3: Object.freeze({ ...row.side3, slug: side3Slug, label: side3.label }),
      timeoutSeeds: Object.freeze([...row.timeoutSeeds]),
      wrongWinnerSeedNumbers: Object.freeze([...row.wrongWinnerSeedNumbers]),
    });
  });
  return Object.freeze({
    schemaVersion: catalogue.schemaVersion,
    generatedAt: catalogue.generatedAt,
    repositoryBase: catalogue.repositoryBase,
    comparisonResults: catalogue.comparisonResults,
    rows: Object.freeze(rows),
  });
}


async function runCurrentProblemMatchupPlayback(root, matchupId, openingSeed = undefined) {
  const catalogue = await loadCurrentProblemCatalogue(root);
  const row = catalogue.rows.find(({ id }) => id === matchupId);
  if (!row) throw new RangeError(`unknown current problem matchup ${matchupId}`);
  const selectedSeed = openingSeed ?? row.representativeSeed;
  const cacheKey = `${root}|${catalogue.generatedAt}|${matchupId}|${selectedSeed}`;
  if (!problemPlaybackByRootAndId.has(cacheKey)) {
    const pending = (async () => {
      const selection = Object.freeze({
        side2Slug: row.side2.slug,
        n2: row.side2.count,
        side3Slug: row.side3.slug,
        n3: row.side3.count,
      });
      let placement;
      if (row.family === "melee_vs_melee") {
        const melee = await loadMeleeFormation(root);
        placement = Object.freeze({
          placementByOwner: melee,
          openingPatrolByOwner: melee.openingPatrolByOwner,
          placementSource: "current-melee-golden",
        });
      } else {
        const ranged = await loadRangedFormation(root, row.family);
        placement = Object.freeze({
          placementByOwner: ranged,
          ...(ranged.auxiliaryArmiesByOwner
            ? { auxiliaryArmiesByOwner: ranged.auxiliaryArmiesByOwner }
            : {}),
          diplomacyByOwner: ranged.diplomacyByOwner,
          triggers: ranged.triggers,
          victoryTeams: ranged.victoryTeams,
          preserveOwnerOrientation: ranged.preserveOwnerOrientation,
          placementSource: "current-ranged-golden",
        });
      }
      const map = await loadArenaPhysicsMap(root);
      const fight = await runFight(pathToFileURL(path.join(root, "/")), {
        ...selection,
        map,
        ...placement,
        displayCivBySide: Object.freeze({ 2: row.side2.civ, 3: row.side3.civ }),
        disableAiOrders: true,
        disableKiting: true,
        openingSeed: selectedSeed,
      });
      const review = Object.freeze({
        ...row,
        representativeSeed: selectedSeed,
        representativeWinnerOwner: fight.winnerOwner,
        representativeWinnerHp: fight.winnerHp,
        representativeReason: openingSeed === undefined
          ? row.representativeReason : "explicit viewer seed",
        explicitSeed: openingSeed !== undefined,
      });
      return Object.freeze({
        ...fight,
        mode: "current-problem-matchup-review",
        review,
      });
    })();
    problemPlaybackByRootAndId.set(cacheKey, pending);
    pending.catch(() => problemPlaybackByRootAndId.delete(cacheKey));
  }
  return problemPlaybackByRootAndId.get(cacheKey);
}


async function handleFightApi({ request, response, root, url }) {
  if (!["/api/catalogue", "/api/units", "/api/fight", "/api/solo-hand-cannoneers",
    "/api/hand-cannoneer-vs-champion-kiting", "/api/ranged-vs-melee-kiting",
    "/api/phase2/wrong-winners", "/api/phase2/wrong-winner",
    "/api/problem-matchups", "/api/problem-matchup"]
    .includes(url.pathname)) return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "Fight diagnostics are read-only" });
    return true;
  }
  if (url.pathname === "/api/units") {
    const meleeFormation = await loadMeleeFormation(root);
    sendJson(response, 200, {
      schemaVersion: 1,
      // Capacity is per (owner, family) and asymmetric (a side-2 siege block
      // holds 16, not 21), so this is the only ceiling a picker can size its
      // inputs from -- there is no single scalar that is correct.
      capacityByFamily: Object.fromEntries(FAMILIES.map((family) => [
        family,
        family === "waves"
          ? { side2: meleeFormation[2].length, side3: meleeFormation[3].length }
          : { side2: sideCapacity(2, family), side3: sideCapacity(3, family) },
      ])),
      soloMovementSlugs: SOLO_MOVEMENT_UNIT_SLUGS,
      kitingObservationMatchups: KITE_OBSERVATION_MATCHUPS,
      units: UNIT_REGISTRY.map(({ slug, label, civ, class: unitClass, baseCost }) => ({
        slug, label, civ, class: unitClass, baseCost,
      })),
    });
    return true;
  }
  if (url.pathname === "/api/catalogue") {
    sendJson(response, 200, await loadViewerCatalogue(root));
    return true;
  }
  if (url.pathname === "/api/problem-matchups") {
    if ([...url.searchParams.keys()].length !== 0) {
      sendJson(response, 400, { error: "problem-matchup catalogue accepts no parameters" });
      return true;
    }
    try {
      sendJson(response, 200, await loadCurrentProblemCatalogue(root));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/problem-matchup") {
    const keys = [...url.searchParams.keys()];
    const matchupValues = url.searchParams.getAll("matchup");
    const seedValues = url.searchParams.getAll("seed");
    const seedValue = seedValues[0];
    const openingSeed = seedValue === undefined ? undefined : Number(seedValue);
    if (keys.some((key) => key !== "matchup" && key !== "seed")
        || matchupValues.length !== 1 || seedValues.length > 1
        || !/^[a-z0-9]+(?:_[a-z0-9]+)*_vs_[a-z0-9]+(?:_[a-z0-9]+)*$/.test(
          matchupValues[0],
        )
        || (seedValue !== undefined && (!/^(?:0|[1-9]\d*)$/.test(seedValue)
          || !Number.isSafeInteger(openingSeed)))) {
      sendJson(response, 400, {
        error: "problem playback requires one valid matchup and at most one non-negative seed",
      });
      return true;
    }
    try {
      sendJson(response, 200, await runCurrentProblemMatchupPlayback(
        root, matchupValues[0], openingSeed,
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/phase2/wrong-winners") {
    if ([...url.searchParams.keys()].length !== 0) {
      sendJson(response, 400, { error: "wrong-winner catalogue accepts no parameters" });
      return true;
    }
    try {
      sendJson(response, 200, await loadPhase2WrongWinnerCatalogue(
        pathToFileURL(path.join(root, "/")),
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/phase2/wrong-winner") {
    const keys = [...url.searchParams.keys()];
    const rowValues = url.searchParams.getAll("row");
    if (keys.length !== 1 || keys[0] !== "row" || rowValues.length !== 1
        || !/^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(rowValues[0])) {
      sendJson(response, 400, { error: "wrong-winner playback requires one valid row" });
      return true;
    }
    try {
      sendJson(response, 200, await runPhase2WrongWinnerPlayback(
        pathToFileURL(path.join(root, "/")),
        rowValues[0],
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/hand-cannoneer-vs-champion-kiting") {
    const keys = [...url.searchParams.keys()];
    if (keys.some((key) => key !== "navigation")
        || url.searchParams.getAll("navigation").length > 1) {
      sendJson(response, 400, { error: "kiting observation accepts only navigation" });
      return true;
    }
    try {
      const map = await loadLegacyArenaPhysicsMap(root);
      const navigation = url.searchParams.get("navigation") ?? "cohesive";
      sendJson(response, 200, await runHandCannoneerChampionKiting(
        pathToFileURL(path.join(root, "/")),
        { map, navigation },
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/ranged-vs-melee-kiting") {
    const selection = kitingObservationSelection(url);
    if (!selection) {
      sendJson(response, 400, {
        error: "invalid kiting observation setup",
      });
      return true;
    }
    try {
      const map = await loadLegacyArenaPhysicsMap(root);
      sendJson(response, 200, await runKitingObservation(
        pathToFileURL(path.join(root, "/")),
        {
          map,
          ...selection,
        },
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  if (url.pathname === "/api/solo-hand-cannoneers") {
    const keys = [...url.searchParams.keys()];
    if (keys.some((key) => key !== "navigation" && key !== "unit")
        || url.searchParams.getAll("navigation").length > 1
        || url.searchParams.getAll("unit").length > 1) {
      sendJson(response, 400, { error: "solo ranged movement accepts only unit and navigation" });
      return true;
    }
    try {
      const map = await loadLegacyArenaPhysicsMap(root);
      const navigation = url.searchParams.get("navigation") ?? "cohesive";
      const unitSlug = url.searchParams.get("unit") ?? "hand_cannoneer";
      sendJson(response, 200, await runSoloRangedMovement(
        pathToFileURL(path.join(root, "/")),
        { map, navigation, unitSlug },
      ));
    } catch (error) {
      sendJson(response, 400, { error: String(error?.message ?? error) });
    }
    return true;
  }
  const selection = fightSelection(url);
  if (!selection) {
    sendJson(response, 400, {
      error: "side2 and side3 must be unit slugs; give both n2 and n3 as integers "
        + `1-${FIGHT_SIDE_CAP}, or neither to derive them with an optional budget 100-20000`,
    });
    return true;
  }
  try {
    const placement = await placementConfigFor(root, selection);
    const map = placement
      ? await loadArenaPhysicsMap(root)
      : await loadLegacyArenaPhysicsMap(root);
    const displayCivBySide = liveObservationCivs(selection);
    const openingConfig = await liveObservationOpeningConfig(root, selection);
    sendJson(response, 200, await runFight(
      pathToFileURL(path.join(root, "/")),
      {
        ...selection,
        map,
        ...(placement ?? {}),
        ...(displayCivBySide ? { displayCivBySide } : {}),
        ...(openingConfig ?? {}),
      },
    ));
  } catch (error) {
    sendJson(response, 400, { error: String(error?.message ?? error) });
  }
  return true;
}


function validLabId(value) {
  return /^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(value ?? "");
}


async function loadLabJobs(labRoot) {
  const runsRoot = path.join(labRoot, "runs");
  let entries;
  try {
    entries = await readdir(runsRoot, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return Object.freeze({ schemaVersion: 1, jobs: [] });
    throw error;
  }
  const jobs = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !validLabId(entry.name)) continue;
    try {
      const manifest = JSON.parse(await readFile(
        path.join(runsRoot, entry.name, "manifest.json"), "utf8",
      ));
      const plan = JSON.parse(await readFile(
        path.join(runsRoot, entry.name, "plan.json"), "utf8",
      ));
      const requestedSeeds = manifest.simulation?.completedSeeds ?? [];
      if (manifest.jobId !== entry.name || plan.jobId !== entry.name
          || manifest.planHash !== plan.planHash || !Array.isArray(requestedSeeds)) continue;
      const seeds = [];
      for (const seed of [...new Set(requestedSeeds)].sort((left, right) => left - right)) {
        if (!Number.isSafeInteger(seed) || seed < 1) continue;
        const seedPath = path.join(
          runsRoot, entry.name, "simulation", "seeds",
          `seed_${String(seed).padStart(3, "0")}.json`,
        );
        try {
          if ((await stat(seedPath)).size > 0) seeds.push(seed);
        } catch (error) {
          if (error?.code !== "ENOENT") throw error;
        }
      }
      if (seeds.length === 0) continue;
      const viewerSeed = seeds.includes(manifest.comparison?.representativeSeed)
        ? manifest.comparison.representativeSeed : seeds[0];
      jobs.push(Object.freeze({
        jobId: entry.name,
        state: manifest.state,
        updatedAt: manifest.updatedAt,
        matchupId: plan.matchupId,
        planHash: plan.planHash,
        label: `${plan.side2.civ} ${plan.side2.label} vs ${plan.side3.civ} ${plan.side3.label}`,
        side2: plan.side2,
        side3: plan.side3,
        scenario: plan.scenario,
        balance: plan.balance,
        seeds: Object.freeze([...seeds].sort((left, right) => left - right)),
        viewerSeed,
        comparison: manifest.comparison ?? null,
      }));
    } catch (error) {
      if (error?.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error;
    }
  }
  jobs.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  return Object.freeze({ schemaVersion: 1, jobs: Object.freeze(jobs) });
}


async function handleLabApi({ request, response, labRoot, url }) {
  if (!url.pathname.startsWith("/api/lab/")) return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "AOE2 Lab artifacts are read-only" });
    return true;
  }
  if (url.pathname === "/api/lab/jobs") {
    if ([...url.searchParams.keys()].length !== 0) {
      sendJson(response, 400, { error: "lab job catalogue accepts no parameters" });
      return true;
    }
    sendJson(response, 200, await loadLabJobs(labRoot));
    return true;
  }
  if (url.pathname === "/api/lab/result") {
    const keys = [...url.searchParams.keys()];
    const job = url.searchParams.get("job");
    const seedText = url.searchParams.get("seed");
    const seed = Number(seedText);
    if (keys.some((key) => key !== "job" && key !== "seed")
        || url.searchParams.getAll("job").length !== 1
        || url.searchParams.getAll("seed").length !== 1
        || !validLabId(job)
        || !/^[1-9]\d*$/.test(seedText ?? "")
        || !Number.isSafeInteger(seed)) {
      sendJson(response, 400, { error: "lab result requires one valid job and positive seed" });
      return true;
    }
    const jobs = await loadLabJobs(labRoot);
    const selected = jobs.jobs.find(({ jobId }) => jobId === job);
    if (!selected || !selected.seeds.includes(seed)) {
      sendJson(response, 404, { error: "completed lab seed not found" });
      return true;
    }
    const resultPath = path.join(
      labRoot, "runs", job, "simulation", "seeds", `seed_${String(seed).padStart(3, "0")}.json`,
    );
    const result = JSON.parse(await readFile(resultPath, "utf8"));
    if (result.mode !== "aoe2-lab" || result.lab?.jobId !== job
        || result.lab?.planHash !== selected.planHash
        || result.lab?.scenarioFamily !== selected.scenario.family
        || result.lab?.goldenSha256 !== selected.scenario.goldenSha256
        || result.openingSeed !== seed) {
      sendJson(response, 409, { error: "lab seed artifact failed provenance validation" });
      return true;
    }
    sendJson(response, 200, result);
    return true;
  }
  sendJson(response, 404, { error: "not found" });
  return true;
}


async function handleMatchupApi({ request, response, root, url }) {
  if (!url.pathname.startsWith("/api/matchup/")) return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "Matchup diagnostics are read-only" });
    return true;
  }
  const rootUrl = pathToFileURL(path.join(root, "/"));
  if (url.pathname === "/api/matchup/list") {
    const names = matchupNames();
    const listed = [];
    for (const name of names) {
      listed.push({ name, ratios: await matchupRatios(rootUrl, name) });
    }
    sendJson(response, 200, { schemaVersion: 1, matchups: listed });
    return true;
  }
  if (url.pathname === "/api/matchup/result") {
    const name = url.searchParams.get("matchup");
    const ratio = url.searchParams.get("ratio");
    const repeatText = url.searchParams.get("repeat") ?? "1";
    if (!name || !matchupNames().includes(name) || !ratio || !/^[1-3]$/.test(repeatText)) {
      sendJson(response, 400, {
        error: `matchup must be one of ${matchupNames().join(", ")}, ratio must exist, repeat 1-3`,
      });
      return true;
    }
    let truth;
    try {
      truth = await matchupTruth(rootUrl, name);
    } catch {
      sendJson(response, 404, { error: "matchup fixture not found" });
      return true;
    }
    const ratioTruth = truth.ratios?.[ratio];
    const repeat = Number(repeatText);
    if (!ratioTruth) {
      // Free-form NvM ratio: no tape truth, synthesize the formation and run
      // the same deterministic engine. tapeDiagnostic is null by design.
      let playback;
      try {
        playback = await syntheticMatchupPlayback(rootUrl, name, ratio);
      } catch (error) {
        sendJson(response, 400, { error: String(error?.message ?? error) });
        return true;
      }
      sendJson(response, 200, {
        schemaVersion: 1,
        matchup: name,
        ratio,
        repeat,
        deterministic: true,
        synthetic: true,
        tapeDiagnostic: null,
        playback,
      });
      return true;
    }
    const run = ratioTruth.runs[repeat - 1];
    sendJson(response, 200, {
      schemaVersion: 1,
      matchup: name,
      ratio,
      repeat,
      deterministic: true,
      synthetic: false,
      tapeDiagnostic: run,
      playback: await matchupPlayback(rootUrl, name, ratio),
    });
    return true;
  }
  sendJson(response, 404, { error: "not found" });
  return true;
}


async function handleChampionApi({ request, response, root, url }) {
  if (!url.pathname.startsWith("/api/champion/")) return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "Champion diagnostics are read-only" });
    return true;
  }

  const data = await loadChampionData(root);
  if (url.pathname === "/api/champion/truth" && url.search === "") {
    sendJson(response, 200, data.truth);
    return true;
  }
  if (url.pathname === "/api/champion/mechanics" && url.search === "") {
    sendJson(response, 200, data.mechanics);
    return true;
  }
  if (url.pathname === "/api/champion/result") {
    const selected = resultSelection(url);
    if (!selected) {
      sendJson(response, 400, {
        error: "ratio must be one of 1v1, 2v1, 2v3, 5v3, 6v3 and repeat must be 1, 2, or 3",
      });
      return true;
    }
    const ratioTruth = data.truth.ratios.find(({ ratio }) => ratio === selected.ratio);
    sendJson(response, 200, {
      schemaVersion: 1,
      ...selected,
      deterministic: true,
      tapeDiagnostic: ratioTruth.repeats[selected.repeat - 1],
      playback: await championPlayback(selected.ratio),
    });
    return true;
  }
  sendJson(response, 404, { error: "not found" });
  return true;
}


export function createMapServer({ root, labRoot = undefined }) {
  const resolvedRoot = path.resolve(root);
  const resolvedLabRoot = path.resolve(
    labRoot ?? path.join(resolvedRoot, "calibration", "lab"),
  );
  return createServer(async (request, response) => {
    const url = new URL(request.url, "http://localhost");
    try {
      if (await handleFightApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleLabApi({ request, response, labRoot: resolvedLabRoot, url })) return;
      if (await handleMatchupApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleChampionApi({ request, response, root: resolvedRoot, url })) return;
    } catch (error) {
      console.error(error);
      sendJson(response, 500, { error: "Simulation diagnostics unavailable" });
      return;
    }
    const pathname = url.pathname;
    const file = publicFile(resolvedRoot, pathname);
    if (!file) {
      send(response, 404, Buffer.from("not found\n"));
      return;
    }

    try {
      const body = await readFile(file);
      const contentType = CONTENT_TYPES.get(path.extname(file).toLowerCase());
      if (!contentType) {
        send(response, 404, Buffer.from("not found\n"));
        return;
      }
      send(response, 200, body, contentType);
    } catch (error) {
      if (error?.code === "ENOENT" || error?.code === "EISDIR") {
        send(response, 404, Buffer.from("not found\n"));
        return;
      }
      send(response, 500, Buffer.from("server error\n"));
    }
  });
}


function parseArgs(argv) {
  const options = { host: "127.0.0.1", port: 5011, labRoot: undefined };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--host" && argv[index + 1]) {
      options.host = argv[index += 1];
    } else if (argv[index] === "--port" && argv[index + 1]) {
      options.port = Number(argv[index += 1]);
    } else if (argv[index] === "--lab-root" && argv[index + 1]) {
      options.labRoot = path.resolve(argv[index += 1]);
    } else {
      throw new Error(`unknown or incomplete option: ${argv[index]}`);
    }
  }
  if (!Number.isInteger(options.port) || options.port < 0 || options.port > 65535) {
    throw new Error("--port must be an integer from 0 through 65535");
  }
  return options;
}


const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain) {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const { host, port, labRoot } = parseArgs(process.argv.slice(2));
  const server = createMapServer({ root, labRoot });
  server.listen(port, host, () => {
    const address = server.address();
    console.log(`Golden Arena map inspector: http://${host}:${address.port}`);
  });
}
