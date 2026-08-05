import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createChampionPlaybackData } from "./src/champion-comparison.js";
import { TICKS_PER_SECOND } from "./src/simulation-clock.js";
import { runChampionRatio } from "./tests/support/champion-ratio.mjs";


const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
]);

const CHAMPION_RATIOS = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const championDataByRoot = new Map();
const championPlaybackByRatio = new Map();


function publicFile(root, pathname) {
  if (pathname === "/") return path.join(root, "viewer", "index.html");
  if (pathname === "/api/map") return path.join(root, "fixtures", "golden_map.json");
  if (pathname === "/api/formation") {
    return path.join(root, "fixtures", "golden_formation_21v21.json");
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
