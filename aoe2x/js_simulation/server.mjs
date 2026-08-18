import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createChampionPlaybackData } from "./src/champion-comparison.js";
import { buildArenaPhysicsMap } from "./src/arena-physics-map.js";
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
import { runChampionRatio } from "./tests/support/champion-ratio.mjs";
import {
  matchupNames,
  matchupPlayback,
  matchupRatios,
  matchupTruth,
  syntheticMatchupPlayback,
} from "./src/matchup-playback.js";
import { SOLO_MOVEMENT_UNIT_SLUGS, UNIT_REGISTRY } from "./src/unit-registry.js";


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


function publicFile(root, pathname) {
  if (pathname === "/") return path.join(root, "viewer", "index.html");
  if (pathname === "/api/map") return path.join(root, "fixtures", "golden_map.json");
  if (pathname === "/api/formation") {
    return path.join(root, "fixtures", "golden_formation_21v21.json");
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


function championPlayback(ratio) {
  if (!championPlaybackByRatio.has(ratio)) {
    championPlaybackByRatio.set(ratio, createChampionPlaybackData(runChampionRatio(ratio)));
  }
  return championPlaybackByRatio.get(ratio);
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
    "ranged", "melee", "navigation", "n2", "n3", "enemyTransit",
  ]);
  const keys = [...url.searchParams.keys()];
  if (keys.some((key) => !allowedKeys.has(key))
      || [...allowedKeys].some((key) => url.searchParams.getAll(key).length > 1)) return null;

  const rangedSlug = url.searchParams.get("ranged") ?? "hand_cannoneer";
  const meleeSlug = url.searchParams.get("melee") ?? "champion";
  const navigation = url.searchParams.get("navigation") ?? "cohesive";
  const enemyTransit = url.searchParams.get("enemyTransit");
  if (enemyTransit !== null && enemyTransit !== "pairwise") return null;
  const matchup = KITE_OBSERVATION_MATCHUPS.find((row) => (
    row.rangedSlug === rangedSlug && row.meleeSlug === meleeSlug
  ));
  if (!matchup || !["baseline", "per-unit-grid", "cohesive"].includes(navigation)) return null;

  const raw2 = url.searchParams.get("n2");
  const raw3 = url.searchParams.get("n3");
  const transitSelection = enemyTransit === "pairwise"
    ? { pairwiseEnemyTransit: true }
    : {};
  if (raw2 === null && raw3 === null) {
    return { rangedSlug, meleeSlug, navigation, ...transitSelection };
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
  return { rangedSlug, meleeSlug, navigation, n2, n3, ...transitSelection };
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


async function handleFightApi({ request, response, root, url }) {
  if (!["/api/catalogue", "/api/units", "/api/fight", "/api/solo-hand-cannoneers",
    "/api/hand-cannoneer-vs-champion-kiting", "/api/ranged-vs-melee-kiting"]
    .includes(url.pathname)) return false;
  if (request.method !== "GET") {
    sendJson(response, 405, { error: "Fight diagnostics are read-only" });
    return true;
  }
  if (url.pathname === "/api/units") {
    sendJson(response, 200, {
      schemaVersion: 1,
      // Capacity is per (owner, family) and asymmetric (a side-2 siege block
      // holds 16, not 21), so this is the only ceiling a picker can size its
      // inputs from -- there is no single scalar that is correct.
      capacityByFamily: Object.fromEntries(FAMILIES.map((family) => [
        family,
        { side2: sideCapacity(2, family), side3: sideCapacity(3, family) },
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
  if (url.pathname === "/api/hand-cannoneer-vs-champion-kiting") {
    const keys = [...url.searchParams.keys()];
    if (keys.some((key) => key !== "navigation")
        || url.searchParams.getAll("navigation").length > 1) {
      sendJson(response, 400, { error: "kiting observation accepts only navigation" });
      return true;
    }
    try {
      const map = await loadArenaPhysicsMap(root);
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
      const map = await loadArenaPhysicsMap(root);
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
      const map = await loadArenaPhysicsMap(root);
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
    const map = await loadArenaPhysicsMap(root);
    sendJson(response, 200, await runFight(
      pathToFileURL(path.join(root, "/")),
      { ...selection, map },
    ));
  } catch (error) {
    sendJson(response, 400, { error: String(error?.message ?? error) });
  }
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
      playback: championPlayback(selected.ratio),
    });
    return true;
  }
  sendJson(response, 404, { error: "not found" });
  return true;
}


export function createMapServer({ root }) {
  const resolvedRoot = path.resolve(root);
  return createServer(async (request, response) => {
    const url = new URL(request.url, "http://localhost");
    try {
      if (await handleFightApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleMatchupApi({ request, response, root: resolvedRoot, url })) return;
      if (await handleChampionApi({ request, response, root: resolvedRoot, url })) return;
    } catch (error) {
      console.error(error);
      sendJson(response, 500, { error: "Champion diagnostics unavailable" });
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
  const options = { host: "127.0.0.1", port: 5011 };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--host" && argv[index + 1]) {
      options.host = argv[index += 1];
    } else if (argv[index] === "--port" && argv[index + 1]) {
      options.port = Number(argv[index += 1]);
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
  const { host, port } = parseArgs(process.argv.slice(2));
  const server = createMapServer({ root });
  server.listen(port, host, () => {
    const address = server.address();
    console.log(`Golden Arena map inspector: http://${host}:${address.port}`);
  });
}
