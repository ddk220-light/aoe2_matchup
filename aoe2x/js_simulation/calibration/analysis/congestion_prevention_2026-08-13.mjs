import { readFile } from "node:fs/promises";
import { once } from "node:events";
import { fileURLToPath } from "node:url";

import { createMapServer } from "../../server.mjs";


const ROOT = new URL("./", import.meta.url);
const HCA_ROOT = new URL("hca_champion_first_engagement/", ROOT);
const HC_ROOT = new URL("hand_cannoneer_escape/", ROOT);
const HCA_FIXTURE_URL = new URL(
  "../fixtures/hcavarcher_vs_champion_kiting_basics.json", ROOT,
);
const CHAMPION_MASTER = 567;
const HCA_MASTER = 474;
const HAND_CANNONEER_MASTER = 5;
const CONTACT = 0.40;
const DEEP_CONTACT = 0.32;
const EPSILON = 1e-9;


function parseJsonLines(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}


function chebyshev(left, right) {
  return Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
}


function euclidean(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}


function percentile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, q * (sorted.length - 1)));
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  const weight = index - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}


function graphComponents(units, threshold) {
  const byId = new Map(units.map((unit) => [unit.id, unit]));
  const unseen = new Set(byId.keys());
  const components = [];
  while (unseen.size) {
    const first = unseen.values().next().value;
    unseen.delete(first);
    const queue = [first];
    const ids = [];
    while (queue.length) {
      const id = queue.shift();
      ids.push(id);
      const unit = byId.get(id);
      for (const otherId of [...unseen]) {
        if (chebyshev(unit, byId.get(otherId)) < threshold - EPSILON) {
          unseen.delete(otherId);
          queue.push(otherId);
        }
      }
    }
    components.push(ids);
  }
  return components;
}


function maximumCliqueSize(units, threshold) {
  let best = 0;
  for (const xAnchor of units) {
    for (const yAnchor of units) {
      const count = units.filter((unit) => (
        unit.x >= xAnchor.x - EPSILON
          && unit.x - xAnchor.x < threshold - EPSILON
          && unit.y >= yAnchor.y - EPSILON
          && unit.y - yAnchor.y < threshold - EPSILON
      )).length;
      best = Math.max(best, count);
    }
  }
  return best;
}


function neighborIds(unit, units, threshold) {
  return units
    .filter((other) => other.id !== unit.id && chebyshev(unit, other) < threshold - EPSILON)
    .map(({ id }) => id);
}


function groupFrames(rows, rangedMaster, lastDeathSeconds = Infinity) {
  const byTime = new Map();
  for (const row of rows) {
    if (row.t_ms / 1000 > lastDeathSeconds + EPSILON || !(row.hp > 0)) continue;
    if (!byTime.has(row.t_ms)) byTime.set(row.t_ms, { melee: [], ranged: [] });
    const frame = byTime.get(row.t_ms);
    const unit = { id: row.id, x: row.x, y: row.y, state: row.state };
    if (row.owner === 3 && row.master === CHAMPION_MASTER) frame.melee.push(unit);
    if (row.owner === 2 && row.master === rangedMaster) frame.ranged.push(unit);
  }
  return [...byTime.entries()]
    .sort(([left], [right]) => left - right)
    .map(([tMs, units]) => ({ tMs, ...units }))
    .filter(({ melee, ranged }) => melee.length && ranged.length);
}


function findNearest(unit, targets) {
  let best = null;
  let bestDistance = Infinity;
  for (const target of targets) {
    const distance = euclidean(unit, target);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = target;
    }
  }
  return { target: best, distance: bestDistance };
}


function corridorState(unit, target, allies, horizon) {
  const dx = target.x - unit.x;
  const dy = target.y - unit.y;
  const length = Math.hypot(dx, dy);
  if (!(length > EPSILON)) return { occupied: false };
  const ux = dx / length;
  const uy = dy / length;
  for (const ally of allies) {
    if (ally.id === unit.id) continue;
    const rx = ally.x - unit.x;
    const ry = ally.y - unit.y;
    const forward = rx * ux + ry * uy;
    const lateral = Math.abs(rx * uy - ry * ux);
    if (
      forward > EPSILON
      && forward <= horizon + EPSILON
      && lateral < CONTACT - EPSILON
      && chebyshev(unit, ally) >= CONTACT - EPSILON
    ) {
      return { occupied: true };
    }
  }
  return { occupied: false };
}


function motionSample(unit, previous, target, dtSeconds) {
  const dx = unit.x - previous.x;
  const dy = unit.y - previous.y;
  const speed = Math.hypot(dx, dy) / dtSeconds;
  const tx = target.x - unit.x;
  const ty = target.y - unit.y;
  const distance = Math.hypot(tx, ty);
  if (!(distance > EPSILON)) {
    return { speed, forwardSpeed: 0, lateralSpeed: 0, lateralShare: 0 };
  }
  const ux = tx / distance;
  const uy = ty / distance;
  const forwardSpeed = (dx * ux + dy * uy) / dtSeconds;
  const lateralSpeed = Math.abs(dx * uy - dy * ux) / dtSeconds;
  return {
    speed,
    forwardSpeed,
    lateralSpeed,
    lateralShare: speed > 1e-5 ? lateralSpeed / speed : 0,
  };
}


function makeMotionBucket() {
  return {
    samples: 0,
    stopped: 0,
    speeds: [],
    forwardSpeeds: [],
    lateralSpeeds: [],
    lateralSharesMoving: [],
  };
}


function summarizeMotion(bucket) {
  return {
    samples: bucket.samples,
    stoppedShare: bucket.samples ? bucket.stopped / bucket.samples : null,
    medianSpeed: percentile(bucket.speeds, 0.5),
    medianForwardSpeed: percentile(bucket.forwardSpeeds, 0.5),
    medianLateralSpeed: percentile(bucket.lateralSpeeds, 0.5),
    medianLateralShareMoving: percentile(bucket.lateralSharesMoving, 0.5),
    p75LateralShareMoving: percentile(bucket.lateralSharesMoving, 0.75),
  };
}


function addMotion(bucket, sample) {
  bucket.samples += 1;
  bucket.speeds.push(sample.speed);
  bucket.forwardSpeeds.push(sample.forwardSpeed);
  bucket.lateralSpeeds.push(sample.lateralSpeed);
  if (sample.speed <= 1e-5) bucket.stopped += 1;
  else bucket.lateralSharesMoving.push(sample.lateralShare);
}


function analyzeAdmissions(previous, current, threshold) {
  const previousComponents = graphComponents(previous.melee, threshold);
  const previousComponentSize = new Map();
  for (const component of previousComponents) {
    for (const id of component) previousComponentSize.set(id, component.length);
  }
  const previousById = new Map(previous.melee.map((unit) => [unit.id, unit]));
  const result = [];
  for (const unit of current.melee) {
    const before = previousById.get(unit.id);
    if (!before) continue;
    const previousNeighbors = neighborIds(before, previous.melee, threshold);
    if (previousNeighbors.length) continue;
    const currentNeighbors = neighborIds(unit, current.melee, threshold);
    if (!currentNeighbors.length) continue;
    const contactsWithExistingGroup = currentNeighbors.filter((id) => (
      (previousComponentSize.get(id) ?? 1) >= 2
    ));
    if (!contactsWithExistingGroup.length) continue;
    result.push({
      contacts: contactsWithExistingGroup.length,
      kind: contactsWithExistingGroup.length === 1 ? "edge" : "multi",
    });
  }
  return result;
}


function pairKey(leftId, rightId) {
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}


function contactEdgeBirths(previous, current, threshold) {
  const previousById = new Map(previous.melee.map((unit) => [unit.id, unit]));
  const previousContacts = new Set();
  for (let leftIndex = 0; leftIndex < previous.melee.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < previous.melee.length; rightIndex += 1) {
      const left = previous.melee[leftIndex];
      const right = previous.melee[rightIndex];
      if (chebyshev(left, right) < threshold - EPSILON) {
        previousContacts.add(pairKey(left.id, right.id));
      }
    }
  }
  const previousComponentId = new Map();
  graphComponents(previous.melee, threshold).forEach((component, componentId) => {
    for (const id of component) previousComponentId.set(id, componentId);
  });
  const currentNeighbors = new Map(current.melee.map((unit) => [
    unit.id,
    new Set(neighborIds(unit, current.melee, threshold)),
  ]));
  const counts = { newEdges: 0, internalClosureEdges: 0, triangleClosureEdges: 0 };
  for (let leftIndex = 0; leftIndex < current.melee.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < current.melee.length; rightIndex += 1) {
      const left = current.melee[leftIndex];
      const right = current.melee[rightIndex];
      if (!previousById.has(left.id) || !previousById.has(right.id)) continue;
      if (chebyshev(left, right) >= threshold - EPSILON) continue;
      if (previousContacts.has(pairKey(left.id, right.id))) continue;
      counts.newEdges += 1;
      if (previousComponentId.get(left.id) === previousComponentId.get(right.id)) {
        counts.internalClosureEdges += 1;
      }
      const leftNeighbors = currentNeighbors.get(left.id);
      const rightNeighbors = currentNeighbors.get(right.id);
      if ([...leftNeighbors].some((id) => id !== right.id && rightNeighbors.has(id))) {
        counts.triangleClosureEdges += 1;
      }
    }
  }
  return counts;
}


function analyzeRun(frames, horizons = [0.8, 1.2]) {
  const maximumCliques = { [CONTACT]: 0, [DEEP_CONTACT]: 0 };
  const maximumComponents = { [CONTACT]: 0, [DEEP_CONTACT]: 0 };
  const framesWithClique3 = { [CONTACT]: 0, [DEEP_CONTACT]: 0 };
  const framesWithClique4 = { [CONTACT]: 0, [DEEP_CONTACT]: 0 };
  const framesWithComponent4 = { [CONTACT]: 0, [DEEP_CONTACT]: 0 };
  const admissions = {
    [CONTACT]: { edge: 0, multi: 0 },
    [DEEP_CONTACT]: { edge: 0, multi: 0 },
  };
  const edgeBirths = {
    [CONTACT]: { newEdges: 0, internalClosureEdges: 0, triangleClosureEdges: 0 },
    [DEEP_CONTACT]: { newEdges: 0, internalClosureEdges: 0, triangleClosureEdges: 0 },
  };
  const clique3Episodes = { [CONTACT]: [], [DEEP_CONTACT]: [] };
  const activeClique3 = { [CONTACT]: null, [DEEP_CONTACT]: null };
  const corridor = Object.fromEntries(horizons.map((horizon) => [horizon, {
    open: makeMotionBucket(),
    occupied: makeMotionBucket(),
  }]));
  const nearestTargetShares = [];

  for (let index = 0; index < frames.length; index += 1) {
    const frame = frames[index];
    for (const threshold of [CONTACT, DEEP_CONTACT]) {
      const clique = maximumCliqueSize(frame.melee, threshold);
      const components = graphComponents(frame.melee, threshold);
      const largest = Math.max(...components.map(({ length }) => length), 0);
      maximumCliques[threshold] = Math.max(maximumCliques[threshold], clique);
      maximumComponents[threshold] = Math.max(maximumComponents[threshold], largest);
      if (clique >= 3) framesWithClique3[threshold] += 1;
      if (clique >= 4) framesWithClique4[threshold] += 1;
      if (largest >= 4) framesWithComponent4[threshold] += 1;
      if (clique >= 3) {
        if (activeClique3[threshold] === null) {
          activeClique3[threshold] = { startMs: frame.tMs, lastMs: frame.tMs };
        } else {
          activeClique3[threshold].lastMs = frame.tMs;
        }
      } else if (activeClique3[threshold] !== null) {
        const episode = activeClique3[threshold];
        clique3Episodes[threshold].push((episode.lastMs - episode.startMs) / 1000);
        activeClique3[threshold] = null;
      }
      if (index) {
        for (const admission of analyzeAdmissions(frames[index - 1], frame, threshold)) {
          admissions[threshold][admission.kind] += 1;
        }
        const births = contactEdgeBirths(frames[index - 1], frame, threshold);
        for (const key of Object.keys(births)) edgeBirths[threshold][key] += births[key];
      }
    }

    if (!index) continue;
    const previous = frames[index - 1];
    const dtSeconds = (frame.tMs - previous.tMs) / 1000;
    if (!(dtSeconds > 0 && dtSeconds <= 0.05)) continue;
    const previousById = new Map(previous.melee.map((unit) => [unit.id, unit]));
    const nearestCounts = new Map();
    for (const unit of frame.melee) {
      const before = previousById.get(unit.id);
      if (!before) continue;
      const nearest = findNearest(unit, frame.ranged);
      if (!nearest.target) continue;
      const sample = motionSample(unit, before, nearest.target, dtSeconds);
      if (sample.speed > 1e-5) {
        nearestCounts.set(nearest.target.id, (nearestCounts.get(nearest.target.id) ?? 0) + 1);
      }
      for (const horizon of horizons) {
        const { occupied } = corridorState(unit, nearest.target, frame.melee, horizon);
        addMotion(corridor[horizon][occupied ? "occupied" : "open"], sample);
      }
    }
    const moving = [...nearestCounts.values()].reduce((sum, value) => sum + value, 0);
    if (moving) {
      nearestTargetShares.push({
        distinct: nearestCounts.size,
        largestShare: Math.max(...nearestCounts.values()) / moving,
      });
    }
  }

  const summarizedAdmissions = {};
  for (const threshold of [CONTACT, DEEP_CONTACT]) {
    const counts = admissions[threshold];
    const total = counts.edge + counts.multi;
    summarizedAdmissions[threshold] = {
      ...counts,
      total,
      edgeShare: total ? counts.edge / total : null,
    };
  }
  for (const threshold of [CONTACT, DEEP_CONTACT]) {
    if (activeClique3[threshold] !== null) {
      const episode = activeClique3[threshold];
      clique3Episodes[threshold].push((episode.lastMs - episode.startMs) / 1000);
    }
  }
  return {
    frameCount: frames.length,
    initialCounts: {
      melee: frames[0]?.melee.length ?? 0,
      ranged: frames[0]?.ranged.length ?? 0,
    },
    thresholds: Object.fromEntries([CONTACT, DEEP_CONTACT].map((threshold) => [threshold, {
      maximumClique: maximumCliques[threshold],
      maximumConnectedComponent: maximumComponents[threshold],
      shareFramesCliqueAtLeast3: framesWithClique3[threshold] / frames.length,
      shareFramesCliqueAtLeast4: framesWithClique4[threshold] / frames.length,
      shareFramesComponentAtLeast4: framesWithComponent4[threshold] / frames.length,
      admissions: summarizedAdmissions[threshold],
      contactEdgeBirths: {
        ...edgeBirths[threshold],
        internalClosureShare: edgeBirths[threshold].newEdges
          ? edgeBirths[threshold].internalClosureEdges / edgeBirths[threshold].newEdges : null,
        triangleClosureShare: edgeBirths[threshold].newEdges
          ? edgeBirths[threshold].triangleClosureEdges / edgeBirths[threshold].newEdges : null,
      },
      clique3Episodes: {
        count: clique3Episodes[threshold].length,
        medianSeconds: percentile(clique3Episodes[threshold], 0.5),
        p95Seconds: percentile(clique3Episodes[threshold], 0.95),
        maximumSeconds: clique3Episodes[threshold].length
          ? Math.max(...clique3Episodes[threshold]) : null,
      },
    }])),
    corridor: Object.fromEntries(horizons.map((horizon) => [horizon, {
      open: summarizeMotion(corridor[horizon].open),
      occupied: summarizeMotion(corridor[horizon].occupied),
    }])),
    nearestTargetProxy: {
      medianDistinctTargetsAmongMoving: percentile(
        nearestTargetShares.map(({ distinct }) => distinct), 0.5,
      ),
      medianLargestTargetShare: percentile(
        nearestTargetShares.map(({ largestShare }) => largestShare), 0.5,
      ),
    },
  };
}


function poolRuns(runs) {
  const frameCount = runs.reduce((sum, run) => sum + run.frameCount, 0);
  const pooled = {
    runs: runs.length,
    frameCount,
    thresholds: {},
    corridor: {},
    nearestTargetProxy: {
      medianDistinctTargetsAmongMoving: percentile(
        runs.map((run) => run.nearestTargetProxy.medianDistinctTargetsAmongMoving), 0.5,
      ),
      medianLargestTargetShare: percentile(
        runs.map((run) => run.nearestTargetProxy.medianLargestTargetShare), 0.5,
      ),
    },
  };
  for (const threshold of [CONTACT, DEEP_CONTACT]) {
    const edge = runs.reduce((sum, run) => sum + run.thresholds[threshold].admissions.edge, 0);
    const multi = runs.reduce((sum, run) => sum + run.thresholds[threshold].admissions.multi, 0);
    const total = edge + multi;
    const birthKeys = ["newEdges", "internalClosureEdges", "triangleClosureEdges"];
    const births = Object.fromEntries(birthKeys.map((key) => [
      key,
      runs.reduce((sum, run) => sum + run.thresholds[threshold].contactEdgeBirths[key], 0),
    ]));
    const episodeMedians = runs
      .map((run) => run.thresholds[threshold].clique3Episodes.medianSeconds)
      .filter((value) => value !== null);
    pooled.thresholds[threshold] = {
      maximumClique: Math.max(...runs.map((run) => run.thresholds[threshold].maximumClique)),
      maximumConnectedComponent: Math.max(
        ...runs.map((run) => run.thresholds[threshold].maximumConnectedComponent),
      ),
      shareFramesCliqueAtLeast3: runs.reduce((sum, run) => (
        sum + run.thresholds[threshold].shareFramesCliqueAtLeast3 * run.frameCount
      ), 0) / frameCount,
      shareFramesCliqueAtLeast4: runs.reduce((sum, run) => (
        sum + run.thresholds[threshold].shareFramesCliqueAtLeast4 * run.frameCount
      ), 0) / frameCount,
      shareFramesComponentAtLeast4: runs.reduce((sum, run) => (
        sum + run.thresholds[threshold].shareFramesComponentAtLeast4 * run.frameCount
      ), 0) / frameCount,
      admissions: { edge, multi, total, edgeShare: total ? edge / total : null },
      contactEdgeBirths: {
        ...births,
        internalClosureShare: births.newEdges
          ? births.internalClosureEdges / births.newEdges : null,
        triangleClosureShare: births.newEdges
          ? births.triangleClosureEdges / births.newEdges : null,
      },
      clique3Episodes: {
        count: runs.reduce(
          (sum, run) => sum + run.thresholds[threshold].clique3Episodes.count, 0,
        ),
        medianRunMedianSeconds: percentile(episodeMedians, 0.5),
        maximumSeconds: Math.max(
          ...runs.map((run) => run.thresholds[threshold].clique3Episodes.maximumSeconds ?? 0),
        ),
      },
    };
  }
  for (const horizon of [0.8, 1.2]) {
    pooled.corridor[horizon] = {};
    for (const kind of ["open", "occupied"]) {
      const values = runs.map((run) => run.corridor[horizon][kind]);
      pooled.corridor[horizon][kind] = {
        samples: values.reduce((sum, value) => sum + value.samples, 0),
        stoppedShareMedianOfRuns: percentile(values.map(({ stoppedShare }) => stoppedShare), 0.5),
        medianSpeedMedianOfRuns: percentile(values.map(({ medianSpeed }) => medianSpeed), 0.5),
        medianForwardSpeedMedianOfRuns: percentile(
          values.map(({ medianForwardSpeed }) => medianForwardSpeed), 0.5,
        ),
        medianLateralSpeedMedianOfRuns: percentile(
          values.map(({ medianLateralSpeed }) => medianLateralSpeed), 0.5,
        ),
        medianLateralShareMovingMedianOfRuns: percentile(
          values.map(({ medianLateralShareMoving }) => medianLateralShareMoving), 0.5,
        ),
      };
    }
  }
  return pooled;
}


async function currentSimulation5v10() {
  const server = createMapServer({ root: fileURLToPath(new URL("../../", import.meta.url)) });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const response = await fetch(
      `http://127.0.0.1:${server.address().port}/api/ranged-vs-melee-kiting`
        + "?ranged=heavy_cav_archer&melee=champion&navigation=cohesive&n2=5&n3=10",
    );
    const run = await response.json();
    if (!response.ok) throw new Error(run.error ?? `Viewer returned ${response.status}`);
    const frames = run.snapshots.map((snapshot) => {
      const melee = [];
      const ranged = [];
      for (const unit of snapshot.units) {
        const meta = run.unitIndex[unit[0]];
        if (!unit[5]) continue;
        const row = { id: unit[0], x: unit[1], y: unit[2], state: unit[6] };
        if (meta.owner === 3 && meta.master === CHAMPION_MASTER) melee.push(row);
        if (meta.owner === 2 && meta.master === HCA_MASTER) ranged.push(row);
      }
      return { tMs: (snapshot.tick / 60) * 1000, melee, ranged };
    }).filter(({ melee, ranged }) => melee.length && ranged.length);
    const analysis = analyzeRun(frames);
    if (analysis.initialCounts.melee !== 10 || analysis.initialCounts.ranged !== 5) {
      throw new Error("Current simulation did not start with 5 HCA and 10 Champions");
    }
    return {
      ...analysis,
      outcome: {
        ticks: run.ticks,
        durationSeconds: run.ticks / 60,
        winnerOwner: run.winnerOwner,
        winnerHp: run.winnerHp,
      },
    };
  } finally {
    server.close();
    await once(server, "close");
  }
}


const hcaFixture = JSON.parse(await readFile(HCA_FIXTURE_URL, "utf8"));
const hcaRuns = [];
for (const ratio of ["5v10", "10v5", "15v20", "20v15", "20v20"]) {
  for (const fixtureRun of hcaFixture.ratios[ratio].runs) {
    const rows = parseJsonLines(await readFile(
      new URL(`${fixtureRun.tag}.tape_trace.jsonl`, HCA_ROOT), "utf8",
    ));
    const analysis = analyzeRun(groupFrames(rows, HCA_MASTER, fixtureRun.lastDeathSeconds));
    hcaRuns.push({ cohort: "hca_vs_champion", ratio, tag: fixtureRun.tag, ...analysis });
  }
}

const hcRuns = [];
for (const tag of [
  "champion__vs__hand_cannoneer",
  "champion__vs__hand_cannoneer_r2",
  "champion__vs__hand_cannoneer_r3",
]) {
  const rows = parseJsonLines(await readFile(
    new URL(`${tag}.tape_trace.jsonl`, HC_ROOT), "utf8",
  ));
  const analysis = analyzeRun(groupFrames(rows, HAND_CANNONEER_MASTER));
  hcRuns.push({ cohort: "hand_cannoneer_vs_champion", ratio: "14v21", tag, ...analysis });
}

const currentSim = await currentSimulation5v10();

const report = {
  generatedOn: "2026-08-13",
  definitions: {
    contact: "Chebyshev center separation below 0.40 tiles.",
    deepContact: "Chebyshev center separation below 0.32 tiles.",
    clique: "All members mutually contact every other member.",
    component: "Members are linked by a chain of contacts; it may be elongated.",
    edgeAdmission: "A previously isolated Champion first touches exactly one member of an already-existing contact component.",
    multiAdmission: "A previously isolated Champion first touches two or more members of an already-existing contact component in the same sampled frame.",
    occupiedCorridor: "Before allied contact, another Champion is within one collision width laterally and the stated horizon forward toward the nearest ranged unit.",
    nearestTargetProxy: "Nearest ranged identity, not the unobserved internal target id.",
  },
  sources: [
    {
      archive: "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip",
      zipSha256: "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5",
      runs: hcaRuns.length,
    },
    {
      archive: "aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip",
      zipSha256: "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D",
      runs: hcRuns.length,
    },
  ],
  cohorts: {
    hca_vs_champion: poolRuns(hcaRuns),
    hand_cannoneer_vs_champion: poolRuns(hcRuns),
  },
  currentSimulation5v10: currentSim,
  hcaRatios: Object.fromEntries(
    ["5v10", "10v5", "15v20", "20v15", "20v20"].map((ratio) => [
      ratio,
      poolRuns(hcaRuns.filter((run) => run.ratio === ratio)),
    ]),
  ),
  runs: [...hcaRuns, ...hcRuns],
};

if (report.cohorts.hca_vs_champion.runs !== 25) throw new Error("Expected 25 HCA runs");
if (report.cohorts.hand_cannoneer_vs_champion.runs !== 3) {
  throw new Error("Expected 3 Hand Cannoneer control runs");
}
if (report.cohorts.hca_vs_champion.thresholds[CONTACT].maximumClique < 2) {
  throw new Error("Contact metric did not observe any allied contact");
}

console.log(JSON.stringify(report, null, 2));
