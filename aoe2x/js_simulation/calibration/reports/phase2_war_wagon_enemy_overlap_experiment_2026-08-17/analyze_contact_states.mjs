import { readFile, writeFile } from "node:fs/promises";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
} from "../../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const OUTPUT = new URL("contact_state_analysis.json", import.meta.url);
const ARCHIVE_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const MATCHUPS = Object.freeze([
  Object.freeze({
    rowId: "elite_war_wagon_vs_paladin",
    tapeRoot: new URL("../phase2_war_wagon_diagnosis_2026-08-17/tape/", import.meta.url),
  }),
  Object.freeze({
    rowId: "elite_war_wagon_vs_champion",
    tapeRoot: new URL("tape/", import.meta.url),
  }),
]);

const truth = await loadPhase2Batch1Truth(ROOT);
if (truth.archive?.zip_sha256 !== ARCHIVE_SHA256) {
  throw new Error(`unexpected authorized archive hash ${truth.archive?.zip_sha256}`);
}
const context = await loadPhase2Batch1Context(ROOT, truth);
const matchups = [];
for (const spec of MATCHUPS) {
  const row = truth.rows.find(({ id }) => id === spec.rowId);
  if (!row) throw new Error(`missing Phase 2 truth row ${spec.rowId}`);
  const runs = [];
  for (const run of row.runs) {
    const trace = new URL(`${run.tag}.tape_trace.jsonl`, spec.tapeRoot);
    runs.push(analyzeTrace(
      await readFile(trace, "utf8"),
      row,
      context,
      run.tag,
    ));
  }
  matchups.push(Object.freeze({
    rowId: row.id,
    matchup: row.matchup,
    ratio: `${row.side2.count}v${row.side3.count}`,
    runs: Object.freeze(runs),
    pooled: pool(runs),
  }));
}

const result = Object.freeze({
  generatedAt: new Date().toISOString(),
  source: Object.freeze({ archive: truth.archive, archiveSha256: ARCHIVE_SHA256 }),
  definitions: Object.freeze({
    overlap: "Chebyshev separation below sourced summed collision half-extents",
    moving: "center displacement greater than 1e-7 tiles from the preceding tape frame",
    attacking: "decoded action_state equals 7",
    directTarget: "opponent target_id equals this War Wagon's canonical reference ID",
    episode: "consecutive decoded frames in which the same canonical pair overlaps",
  }),
  matchups: Object.freeze(matchups),
});
await writeFile(OUTPUT, `${JSON.stringify(result, null, 2)}\n`, "utf8");


function analyzeTrace(text, row, selectedContext, tag) {
  const roster = row.runs[0].starting_units;
  const wagonIds = new Set(roster.filter(({ owner }) => owner === 2).map(({ id }) => id));
  const opponentIds = new Set(roster.filter(({ owner }) => owner === 3).map(({ id }) => id));
  const extent = selectedContext.mechanicsByMaster.get(row.side2.master).collision_size_tiles.x
    + selectedContext.mechanicsByMaster.get(row.side3.master).collision_size_tiles.x;
  const accumulator = createAccumulator();
  const previousById = new Map();
  let frameTime = null;
  let frame = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (!wagonIds.has(raw.id) && !opponentIds.has(raw.id)) continue;
    if (frameTime !== null && raw.t_ms !== frameTime) {
      observeFrame(accumulator, frameTime, frame, wagonIds, opponentIds, extent);
      frame = [];
    }
    frameTime = raw.t_ms;
    const previous = previousById.get(raw.id);
    const moving = previous !== undefined && Math.hypot(
      raw.x - previous.x,
      raw.y - previous.y,
    ) > 1e-7;
    const unit = Object.freeze({
      id: raw.id,
      x: raw.x,
      y: raw.y,
      hp: raw.hp ?? 0,
      moving,
      attacking: raw.action_state === 7,
      targetId: Number.isSafeInteger(raw.target_id) && raw.target_id >= 0
        ? raw.target_id : null,
    });
    previousById.set(raw.id, unit);
    frame.push(unit);
  }
  if (frameTime !== null) {
    observeFrame(accumulator, frameTime, frame, wagonIds, opponentIds, extent);
  }
  finishEpisodes(accumulator);
  return finalize(accumulator, tag);
}


function createAccumulator() {
  return {
    pairObservations: 0,
    overlappingPairObservations: 0,
    categories: new Map(),
    depths: [],
    activeEpisodes: new Map(),
    episodes: [],
    lastTime: null,
  };
}


function observeFrame(accumulator, time, units, wagonIds, opponentIds, extent) {
  const wagons = units.filter(({ id, hp }) => hp > 0 && wagonIds.has(id));
  const opponents = units.filter(({ id, hp }) => hp > 0 && opponentIds.has(id));
  const presentOverlap = new Set();
  for (const wagon of wagons) {
    for (const opponent of opponents) {
      const directTarget = opponent.targetId === wagon.id;
      const category = [
        opponent.moving ? "opponent-moving" : "opponent-stopped",
        wagon.moving ? "wagon-moving" : "wagon-stopped",
        opponent.attacking ? "opponent-attacking" : "opponent-not-attacking",
        directTarget ? "direct-target" : "other-wagon",
      ].join("|");
      const bucket = accumulator.categories.get(category)
        ?? { pairObservations: 0, overlapObservations: 0, depths: [] };
      bucket.pairObservations += 1;
      accumulator.pairObservations += 1;
      const depth = extent - Math.max(
        Math.abs(wagon.x - opponent.x),
        Math.abs(wagon.y - opponent.y),
      );
      if (depth > 1e-9) {
        const pair = `${wagon.id}:${opponent.id}`;
        presentOverlap.add(pair);
        bucket.overlapObservations += 1;
        bucket.depths.push(depth);
        accumulator.overlappingPairObservations += 1;
        accumulator.depths.push(depth);
        const active = accumulator.activeEpisodes.get(pair);
        if (active) {
          active.lastTime = time;
          active.frames += 1;
          active.maximumDepth = Math.max(active.maximumDepth, depth);
        } else {
          accumulator.activeEpisodes.set(pair, {
            startTime: time,
            lastTime: time,
            frames: 1,
            maximumDepth: depth,
            startCategory: category,
          });
        }
      }
      accumulator.categories.set(category, bucket);
    }
  }
  for (const [pair, episode] of accumulator.activeEpisodes) {
    if (presentOverlap.has(pair)) continue;
    accumulator.episodes.push(closeEpisode(episode));
    accumulator.activeEpisodes.delete(pair);
  }
  accumulator.lastTime = time;
}


function finishEpisodes(accumulator) {
  for (const episode of accumulator.activeEpisodes.values()) {
    accumulator.episodes.push(closeEpisode(episode));
  }
  accumulator.activeEpisodes.clear();
}


function closeEpisode(episode) {
  return Object.freeze({
    durationSeconds: (episode.lastTime - episode.startTime) / 1000,
    frames: episode.frames,
    maximumDepth: episode.maximumDepth,
    startCategory: episode.startCategory,
  });
}


function finalize(accumulator, tag) {
  return Object.freeze({
    tag,
    pairObservations: accumulator.pairObservations,
    overlappingPairObservations: accumulator.overlappingPairObservations,
    overlappingPairObservationShare: ratio(
      accumulator.overlappingPairObservations,
      accumulator.pairObservations,
    ),
    depthTiles: quantiles(accumulator.depths),
    episodeCount: accumulator.episodes.length,
    episodeDurationSeconds: quantiles(
      accumulator.episodes.map(({ durationSeconds }) => durationSeconds),
    ),
    episodeMaximumDepthTiles: quantiles(
      accumulator.episodes.map(({ maximumDepth }) => maximumDepth),
    ),
    categories: categoryRows(accumulator.categories),
  });
}


function pool(runs) {
  const categories = new Map();
  const depths = [];
  const episodeDurations = [];
  const episodeDepths = [];
  let pairObservations = 0;
  let overlappingPairObservations = 0;
  for (const run of runs) {
    pairObservations += run.pairObservations;
    overlappingPairObservations += run.overlappingPairObservations;
    for (const row of run.categories) {
      const bucket = categories.get(row.category)
        ?? { pairObservations: 0, overlapObservations: 0, depths: [] };
      bucket.pairObservations += row.pairObservations;
      bucket.overlapObservations += row.overlapObservations;
      categories.set(row.category, bucket);
    }
    if (run.depthTiles.median !== null) depths.push(run.depthTiles.median);
    if (run.episodeDurationSeconds.median !== null) {
      episodeDurations.push(run.episodeDurationSeconds.median);
    }
    if (run.episodeMaximumDepthTiles.median !== null) {
      episodeDepths.push(run.episodeMaximumDepthTiles.median);
    }
  }
  return Object.freeze({
    pairObservations,
    overlappingPairObservations,
    overlappingPairObservationShare: ratio(overlappingPairObservations, pairObservations),
    repeatMedianDepthTiles: quantiles(depths),
    repeatMedianEpisodeDurationSeconds: quantiles(episodeDurations),
    repeatMedianEpisodeMaximumDepthTiles: quantiles(episodeDepths),
    categories: categoryRows(categories),
  });
}


function categoryRows(categories) {
  return Object.freeze([...categories.entries()]
    .map(([category, bucket]) => Object.freeze({
      category,
      pairObservations: bucket.pairObservations,
      overlapObservations: bucket.overlapObservations,
      overlapRate: ratio(bucket.overlapObservations, bucket.pairObservations),
      shareOfAllOverlap: null,
      depthTiles: quantiles(bucket.depths),
    }))
    .map((row, _index, rows) => Object.freeze({
      ...row,
      shareOfAllOverlap: ratio(
        row.overlapObservations,
        rows.reduce((total, entry) => total + entry.overlapObservations, 0),
      ),
    }))
    .filter(({ overlapObservations }) => overlapObservations > 0)
    .sort((left, right) => right.overlapObservations - left.overlapObservations));
}


function quantiles(values) {
  const sorted = [...values].sort((left, right) => left - right);
  if (!sorted.length) return Object.freeze({ min: null, median: null, p90: null, max: null });
  const at = (fraction) => sorted[Math.floor((sorted.length - 1) * fraction)];
  return Object.freeze({
    min: round(at(0)),
    median: round(at(0.5)),
    p90: round(at(0.9)),
    max: round(at(1)),
  });
}


function ratio(numerator, denominator) {
  return denominator ? round(numerator / denominator) : null;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
