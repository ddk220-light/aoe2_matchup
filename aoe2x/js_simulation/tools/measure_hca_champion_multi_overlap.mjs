import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";


const TRACE_ROOT = new URL(
  "../calibration/analysis/hca_champion_first_engagement/", import.meta.url,
);
const FIXTURE_URL = new URL(
  "../calibration/fixtures/hcavarcher_vs_champion_kiting_basics.json", import.meta.url,
);
const RATIOS = ["5v10", "10v5", "15v20", "20v15", "20v20"];
const THRESHOLDS = [0.40, 0.32, 0.20, 0.10];
const CHAMPION_MASTER = 567;
const EPSILON = 1e-9;


function groupFrames(rows, lastDeathSeconds) {
  const byTime = new Map();
  for (const row of rows) {
    const t = row.t_ms / 1000;
    if (t > lastDeathSeconds + EPSILON) continue;
    if (row.owner !== 3 || row.master !== CHAMPION_MASTER || !(row.hp > 0)) continue;
    if (!byTime.has(row.t_ms)) byTime.set(row.t_ms, []);
    byTime.get(row.t_ms).push({
      id: row.id,
      x: row.x,
      y: row.y,
      state: row.state,
    });
  }
  return [...byTime.entries()]
    .sort(([left], [right]) => left - right)
    .map(([tMs, units]) => ({ tMs, units }));
}


function chebyshev(left, right) {
  return Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
}


// For axis-aligned square obstruction, a set of units mutually overlaps when
// its x span and y span are both below the contact threshold. Enumerating the
// possible minimum x/y coordinates finds the exact largest overlap clique.
function maximumClique(units, threshold) {
  let best = [];
  for (const xAnchor of units) {
    for (const yAnchor of units) {
      const candidates = units.filter((unit) => (
        unit.x >= xAnchor.x - EPSILON
          && unit.x - xAnchor.x < threshold - EPSILON
          && unit.y >= yAnchor.y - EPSILON
          && unit.y - yAnchor.y < threshold - EPSILON
      ));
      if (candidates.length > best.length) best = candidates;
    }
  }
  return best;
}


function maximumConnectedComponent(units, threshold) {
  const unseen = new Set(units.map(({ id }) => id));
  const byId = new Map(units.map((unit) => [unit.id, unit]));
  let best = [];
  while (unseen.size) {
    const first = unseen.values().next().value;
    unseen.delete(first);
    const queue = [first];
    const component = [];
    while (queue.length) {
      const id = queue.shift();
      const unit = byId.get(id);
      component.push(unit);
      for (const otherId of [...unseen]) {
        if (chebyshev(unit, byId.get(otherId)) < threshold - EPSILON) {
          unseen.delete(otherId);
          queue.push(otherId);
        }
      }
    }
    if (component.length > best.length) best = component;
  }
  return best;
}


function motionLabels(frame, previous, clique) {
  const previousById = new Map((previous?.units ?? []).map((unit) => [unit.id, unit]));
  return clique.map((unit) => {
    const before = previousById.get(unit.id);
    const moving = Boolean(before && Math.hypot(unit.x - before.x, unit.y - before.y) > 1e-5);
    return { id: unit.id, moving, state: unit.state, x: unit.x, y: unit.y };
  });
}


function analyzeRun(frames) {
  const thresholds = Object.fromEntries(THRESHOLDS.map((threshold) => [threshold, {
    maximumClique: 0,
    maximumConnectedComponent: 0,
    framesAtLeast2: 0,
    framesAtLeast3: 0,
    framesAtLeast4: 0,
    tripleFramesByMovingCount: { 0: 0, 1: 0, 2: 0, 3: 0 },
    tripleEpisodeDurationsSeconds: [],
    deepestExample: null,
    activeTripleStartMs: null,
    activeTripleLastMs: null,
  }]));

  function finishTripleEpisode(stats) {
    if (stats.activeTripleStartMs === null) return;
    stats.tripleEpisodeDurationsSeconds.push(
      (stats.activeTripleLastMs - stats.activeTripleStartMs) / 1000,
    );
    stats.activeTripleStartMs = null;
    stats.activeTripleLastMs = null;
  }

  for (let index = 0; index < frames.length; index += 1) {
    const frame = frames[index];
    for (const threshold of THRESHOLDS) {
      const clique = maximumClique(frame.units, threshold);
      const connected = maximumConnectedComponent(frame.units, threshold);
      const stats = thresholds[threshold];
      if (clique.length >= 2) stats.framesAtLeast2 += 1;
      if (clique.length >= 3) stats.framesAtLeast3 += 1;
      if (clique.length >= 4) stats.framesAtLeast4 += 1;
      if (clique.length >= 3) {
        const labels = motionLabels(frame, frames[index - 1], clique);
        const movingCount = labels.filter(({ moving }) => moving).length;
        stats.tripleFramesByMovingCount[movingCount] += 1;
        if (stats.activeTripleStartMs === null) stats.activeTripleStartMs = frame.tMs;
        stats.activeTripleLastMs = frame.tMs;
      } else {
        finishTripleEpisode(stats);
      }
      if (clique.length > stats.maximumClique) {
        stats.maximumClique = clique.length;
        stats.deepestExample = {
          tSeconds: frame.tMs / 1000,
          units: motionLabels(frame, frames[index - 1], clique),
        };
      }
      stats.maximumConnectedComponent = Math.max(
        stats.maximumConnectedComponent, connected.length,
      );
    }
  }
  for (const threshold of THRESHOLDS) {
    const stats = thresholds[threshold];
    finishTripleEpisode(stats);
    delete stats.activeTripleStartMs;
    delete stats.activeTripleLastMs;
  }
  return { frameCount: frames.length, thresholds };
}


function parseJsonLines(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}


function poolRuns(runs) {
  const frameCount = runs.reduce((sum, run) => sum + run.frameCount, 0);
  const thresholds = {};
  for (const threshold of THRESHOLDS) {
    const values = runs.map((run) => run.thresholds[threshold]);
    const maxValue = Math.max(...values.map(({ maximumClique }) => maximumClique));
    const exampleRunIndex = values.findIndex(({ maximumClique }) => maximumClique === maxValue);
    const episodeDurations = values.flatMap(({ tripleEpisodeDurationsSeconds }) => (
      tripleEpisodeDurationsSeconds
    ));
    const sortedDurations = [...episodeDurations].sort((left, right) => left - right);
    const medianDuration = sortedDurations.length
      ? sortedDurations[Math.floor(sortedDurations.length / 2)] : null;
    thresholds[threshold] = {
      maximumClique: maxValue,
      maximumConnectedComponent: Math.max(
        ...values.map(({ maximumConnectedComponent }) => maximumConnectedComponent),
      ),
      framesAtLeast2: values.reduce((sum, value) => sum + value.framesAtLeast2, 0),
      framesAtLeast3: values.reduce((sum, value) => sum + value.framesAtLeast3, 0),
      framesAtLeast4: values.reduce((sum, value) => sum + value.framesAtLeast4, 0),
      shareFramesAtLeast2: values.reduce((sum, value) => sum + value.framesAtLeast2, 0) / frameCount,
      shareFramesAtLeast3: values.reduce((sum, value) => sum + value.framesAtLeast3, 0) / frameCount,
      shareFramesAtLeast4: values.reduce((sum, value) => sum + value.framesAtLeast4, 0) / frameCount,
      tripleFramesByMovingCount: Object.fromEntries([0, 1, 2, 3].map((movingCount) => [
        movingCount,
        values.reduce((sum, value) => (
          sum + value.tripleFramesByMovingCount[movingCount]
        ), 0),
      ])),
      tripleEpisodes: episodeDurations.length,
      medianTripleEpisodeSeconds: medianDuration,
      maximumTripleEpisodeSeconds: episodeDurations.length
        ? Math.max(...episodeDurations) : null,
      maximumExample: {
        tag: runs[exampleRunIndex].tag,
        ...values[exampleRunIndex].deepestExample,
      },
    };
  }
  return { runs: runs.length, frameCount, thresholds };
}


const fixture = JSON.parse(await readFile(FIXTURE_URL, "utf8"));
const report = {
  source: {
    archive: "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip",
    zipSha256: "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5",
    definitions: {
      clique: "Every Champion pair is closer than the threshold in Chebyshev distance.",
      connectedComponent: "Champions are joined by a chain of pair contacts; not every pair must overlap.",
    },
  },
  ratios: {},
};

const allRuns = [];
for (const ratio of RATIOS) {
  const runs = [];
  for (const fixtureRun of fixture.ratios[ratio].runs) {
    const trace = parseJsonLines(await readFile(
      new URL(`${fixtureRun.tag}.tape_trace.jsonl`, TRACE_ROOT), "utf8",
    ));
    const analysis = analyzeRun(groupFrames(trace, fixtureRun.lastDeathSeconds));
    runs.push({ tag: fixtureRun.tag, ...analysis });
  }
  allRuns.push(...runs);
  report.ratios[ratio] = poolRuns(runs);
}
report.aggregate = poolRuns(allRuns);

console.log(JSON.stringify(report, null, 2));
