import { readFile, writeFile } from "node:fs/promises";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
} from "../../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const OUTPUT = new URL("target_distribution_analysis.json", import.meta.url);
const ARCHIVE_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const SAMPLE_SECONDS = Object.freeze([0.6, 1, 2, 3, 4, 5, 6, 8, 10, 15, 20]);
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
// Load context as the same clean-room manifest validation used by comparisons.
await loadPhase2Batch1Context(ROOT, truth);
const matchups = [];
for (const matchup of MATCHUPS) {
  const row = truth.rows.find(({ id }) => id === matchup.rowId);
  if (!row) throw new Error(`missing Phase 2 truth row ${matchup.rowId}`);
  const wagonIds = new Set(
    row.runs[0].starting_units.filter(({ owner }) => owner === 2).map(({ id }) => id),
  );
  const opponentIds = new Set(
    row.runs[0].starting_units.filter(({ owner }) => owner === 3).map(({ id }) => id),
  );
  const runs = [];
  for (const run of row.runs) {
    const trace = new URL(`${run.tag}.tape_trace.jsonl`, matchup.tapeRoot);
    runs.push(analyzeTrace(await readFile(trace, "utf8"), run.tag, wagonIds, opponentIds));
  }
  matchups.push(Object.freeze({
    rowId: row.id,
    matchup: row.matchup,
    runs: Object.freeze(runs),
  }));
}

await writeFile(OUTPUT, `${JSON.stringify(Object.freeze({
  generatedAt: new Date().toISOString(),
  source: Object.freeze({ archive: truth.archive, archiveSha256: ARCHIVE_SHA256 }),
  definitions: Object.freeze({
    assigned: "live canonical opponent whose decoded target_id names a live canonical War Wagon",
    distinctTargets: "number of live canonical War Wagons selected by at least one assigned Paladin",
    maximumTargetLoad: "largest number of assigned opponents selecting the same War Wagon",
  }),
  matchups: Object.freeze(matchups),
}), null, 2)}\n`, "utf8");


function analyzeTrace(text, tag, canonicalWagonIds, canonicalOpponentIds) {
  const frames = [];
  let frameTime = null;
  let frame = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (!canonicalWagonIds.has(raw.id) && !canonicalOpponentIds.has(raw.id)) continue;
    if (frameTime !== null && raw.t_ms !== frameTime) {
      frames.push(summarizeFrame(frameTime, frame, canonicalWagonIds, canonicalOpponentIds));
      frame = [];
    }
    frameTime = raw.t_ms;
    frame.push(raw);
  }
  if (frameTime !== null) {
    frames.push(summarizeFrame(frameTime, frame, canonicalWagonIds, canonicalOpponentIds));
  }
  const samples = SAMPLE_SECONDS.map((seconds) => (
    publicFrame(nearestFrame(frames, seconds * 1000))
  ));
  const active = frames.filter(({ assigned }) => assigned > 0);
  return Object.freeze({
    tag,
    firstAssigned: active[0] ? publicFrame(active[0]) : null,
    samples: Object.freeze(samples),
    targetPersistence: targetPersistence(frames),
    activeFrameSummary: Object.freeze({
      frameCount: active.length,
      assignedMedian: quantile(active.map(({ assigned }) => assigned), 0.5),
      distinctTargetsMedian: quantile(active.map(({ distinctTargets }) => distinctTargets), 0.5),
      distinctTargetsP10: quantile(active.map(({ distinctTargets }) => distinctTargets), 0.1),
      distinctTargetsP90: quantile(active.map(({ distinctTargets }) => distinctTargets), 0.9),
      maximumTargetLoadMedian: quantile(active.map(({ maximumTargetLoad }) => maximumTargetLoad), 0.5),
      maximumTargetLoadP90: quantile(active.map(({ maximumTargetLoad }) => maximumTargetLoad), 0.9),
    }),
  });
}


function summarizeFrame(tMs, units, canonicalWagonIds, canonicalOpponentIds) {
  const liveWagons = new Set(units.filter(({ id, hp }) => (
    canonicalWagonIds.has(id) && Number(hp) > 0
  )).map(({ id }) => id));
  const loadByTarget = new Map();
  let liveOpponents = 0;
  for (const unit of units) {
    if (!canonicalOpponentIds.has(unit.id) || Number(unit.hp) <= 0) continue;
    liveOpponents += 1;
    if (!liveWagons.has(unit.target_id)) continue;
    loadByTarget.set(unit.target_id, (loadByTarget.get(unit.target_id) ?? 0) + 1);
  }
  return Object.freeze({
    tMs,
    liveOpponents,
    liveWagons: liveWagons.size,
    assigned: [...loadByTarget.values()].reduce((sum, count) => sum + count, 0),
    distinctTargets: loadByTarget.size,
    maximumTargetLoad: Math.max(0, ...loadByTarget.values()),
    targetLoads: Object.freeze([...loadByTarget.entries()]
      .sort(([left], [right]) => left - right)
      .map(([targetId, count]) => Object.freeze({ targetId, count }))),
    targetByOpponent: new Map(units
      .filter(({ id, hp }) => canonicalOpponentIds.has(id) && Number(hp) > 0)
      .map(({ id, target_id: targetId }) => [
        id,
        liveWagons.has(targetId) ? targetId : null,
      ])),
  });
}


function publicFrame(frame) {
  const { targetByOpponent: _targetByOpponent, ...published } = frame;
  return Object.freeze(published);
}


function targetPersistence(frames) {
  const previousByOpponent = new Map();
  const startByOpponent = new Map();
  const tenures = [];
  let firstAcquisitions = 0;
  let liveTargetSwitches = 0;
  for (const frame of frames) {
    for (const [opponentId, targetId] of frame.targetByOpponent) {
      const previous = previousByOpponent.get(opponentId) ?? null;
      if (targetId === previous) continue;
      if (previous !== null) {
        const started = startByOpponent.get(opponentId);
        if (Number.isFinite(started)) tenures.push((frame.tMs - started) / 1000);
      }
      if (targetId !== null && previous === null) firstAcquisitions += 1;
      if (targetId !== null && previous !== null) liveTargetSwitches += 1;
      previousByOpponent.set(opponentId, targetId);
      if (targetId === null) startByOpponent.delete(opponentId);
      else startByOpponent.set(opponentId, frame.tMs);
    }
  }
  return Object.freeze({
    firstAcquisitions,
    liveTargetSwitches,
    liveTargetSwitchesPerOpponent: previousByOpponent.size === 0
      ? 0 : liveTargetSwitches / previousByOpponent.size,
    completedTenureSeconds: Object.freeze({
      count: tenures.length,
      median: quantile(tenures, 0.5),
      p10: quantile(tenures, 0.1),
      p90: quantile(tenures, 0.9),
    }),
  });
}


function nearestFrame(frames, targetMs) {
  let best = null;
  for (const frame of frames) {
    if (best === null || Math.abs(frame.tMs - targetMs) < Math.abs(best.tMs - targetMs)) {
      best = frame;
    }
  }
  return best;
}


function quantile(values, q) {
  if (values.length === 0) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const position = (ordered.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return ordered[lower];
  return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower);
}
