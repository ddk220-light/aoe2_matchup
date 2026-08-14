import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { createMapServer } from "../../server.mjs";


const ROOT = new URL("./", import.meta.url);
const FIXTURE_URL = new URL(
  "../fixtures/hcavarcher_vs_champion_kiting_basics.json",
  ROOT,
);
const PROJECT_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const RATIOS = ["5v10", "10v5", "15v20", "20v15", "20v20"];
const CONTACT_TILES = 0.40;
const EPSILON = 1e-9;
const HCA_HP = 80;
const CHAMPION_HP = 70;


function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}


function range(values) {
  return {
    minimum: Math.min(...values),
    maximum: Math.max(...values),
  };
}


function round(value, digits = 6) {
  if (value === null || value === undefined) return value;
  return Number(value.toFixed(digits));
}


function chebyshev(left, right) {
  return Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
}


function graphComponents(units, threshold) {
  const unseen = new Set(units.map(({ id }) => id));
  const byId = new Map(units.map((unit) => [unit.id, unit]));
  const components = [];
  while (unseen.size) {
    const first = unseen.values().next().value;
    unseen.delete(first);
    const queue = [first];
    const component = [];
    while (queue.length) {
      const id = queue.shift();
      component.push(id);
      const unit = byId.get(id);
      for (const otherId of [...unseen]) {
        if (chebyshev(unit, byId.get(otherId)) < threshold - EPSILON) {
          unseen.delete(otherId);
          queue.push(otherId);
        }
      }
    }
    components.push(component);
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


function frameContactSummary(run) {
  let frames = 0;
  let compactTripleFrames = 0;
  let cliqueFourFrames = 0;
  let connectedFourFrames = 0;
  let maximumClique = 0;
  let maximumComponent = 0;
  let activeTripleStart = null;
  let activeTripleEnd = null;
  let longestTripleSeconds = 0;

  for (const snapshot of run.snapshots) {
    const champions = [];
    let rangedAlive = 0;
    for (const unit of snapshot.units) {
      if (!unit[5]) continue;
      const meta = run.unitIndex[unit[0]];
      if (meta.owner === 3 && meta.master === 567) {
        champions.push({ id: unit[0], x: unit[1], y: unit[2] });
      }
      if (meta.owner === 2 && meta.master === 474) rangedAlive += 1;
    }
    if (!champions.length || !rangedAlive) continue;
    frames += 1;
    const clique = maximumCliqueSize(champions, CONTACT_TILES);
    const largestComponent = Math.max(
      ...graphComponents(champions, CONTACT_TILES).map(({ length }) => length),
      0,
    );
    maximumClique = Math.max(maximumClique, clique);
    maximumComponent = Math.max(maximumComponent, largestComponent);
    if (clique >= 3) {
      compactTripleFrames += 1;
      if (activeTripleStart === null) activeTripleStart = snapshot.tick;
      activeTripleEnd = snapshot.tick;
    } else if (activeTripleStart !== null) {
      longestTripleSeconds = Math.max(
        longestTripleSeconds,
        (activeTripleEnd - activeTripleStart) / 60,
      );
      activeTripleStart = null;
      activeTripleEnd = null;
    }
    if (clique >= 4) cliqueFourFrames += 1;
    if (largestComponent >= 4) connectedFourFrames += 1;
  }
  if (activeTripleStart !== null) {
    longestTripleSeconds = Math.max(
      longestTripleSeconds,
      (activeTripleEnd - activeTripleStart) / 60,
    );
  }
  return {
    analyzedFrames: frames,
    compactTripleFrameShare: frames ? round(compactTripleFrames / frames) : null,
    cliqueFourFrameShare: frames ? round(cliqueFourFrames / frames) : null,
    connectedFourFrameShare: frames ? round(connectedFourFrames / frames) : null,
    maximumClique,
    maximumComponent,
    longestCompactTripleSeconds: round(longestTripleSeconds),
  };
}


function startingHpByOwner(run) {
  const result = { 2: 0, 3: 0 };
  for (const meta of Object.values(run.unitIndex)) {
    result[meta.owner] += meta.maxHp;
  }
  return result;
}


function finalSurvivors(run) {
  const final = run.snapshots.at(-1);
  return final.units.filter((unit) => unit[5] && run.unitIndex[unit[0]].owner === run.winnerOwner).length;
}


function score(owner, hp, startingHp) {
  if (owner === null) return 0;
  const magnitude = (hp / startingHp[owner]) * 100;
  return owner === 2 ? magnitude : -magnitude;
}


function tapeSummary(fixtureRuns, startingHp) {
  const owners = [...new Set(fixtureRuns.map(({ winnerOwner }) => winnerOwner))];
  if (owners.length !== 1) {
    throw new Error(`Tape repeats disagree on winner: ${owners.join(", ")}`);
  }
  const winnerHp = fixtureRuns.map((run) => run.winnerHp);
  const durationSeconds = fixtureRuns.map((run) => run.lastDeathSeconds);
  const survivors = fixtureRuns.map((run) => run.survivors);
  const signedScores = fixtureRuns.map((run) => (
    score(run.winnerOwner, run.winnerHp, startingHp)
  ));
  return {
    repeats: fixtureRuns.length,
    winnerOwner: owners[0],
    winnerHp: { median: median(winnerHp), ...range(winnerHp) },
    durationSeconds: {
      median: round(median(durationSeconds)),
      ...range(durationSeconds),
    },
    survivors: { median: median(survivors), ...range(survivors) },
    signedOutcomeScorePoints: {
      median: round(median(signedScores)),
      ...range(signedScores),
    },
  };
}


async function fetchRun(port, ratio) {
  const [n2, n3] = ratio.split("v").map(Number);
  const url = new URL(`http://127.0.0.1:${port}/api/ranged-vs-melee-kiting`);
  url.searchParams.set("ranged", "heavy_cav_archer");
  url.searchParams.set("melee", "champion");
  url.searchParams.set("navigation", "cohesive");
  url.searchParams.set("n2", String(n2));
  url.searchParams.set("n3", String(n3));
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(`${ratio}: ${body.error ?? `Viewer returned ${response.status}`}`);
  }
  if (body.contactSteeringMode !== "preventive-contact-graph") {
    throw new Error(`${ratio} did not enable preventive contact steering`);
  }
  if (body.side2.count !== n2 || body.side3.count !== n3) {
    throw new Error(`${ratio} returned the wrong side counts`);
  }
  return body;
}


const fixture = JSON.parse(await readFile(FIXTURE_URL, "utf8"));
if (fixture.archive !== "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip") {
  throw new Error(`Unexpected tape archive ${fixture.archive}`);
}

const server = createMapServer({ root: PROJECT_ROOT });
server.listen(0, "127.0.0.1");
await once(server, "listening");

const rows = [];
try {
  for (const ratio of RATIOS) {
    const [n2, n3] = ratio.split("v").map(Number);
    const startingHp = { 2: n2 * HCA_HP, 3: n3 * CHAMPION_HP };
    const tape = tapeSummary(fixture.ratios[ratio].runs, startingHp);
    let run;
    try {
      run = await fetchRun(server.address().port, ratio);
    } catch (error) {
      rows.push({
        ratio,
        counts: { heavyCavalryArchers: n2, champions: n3 },
        startingHp,
        tape,
        simulation: null,
        failure: String(error?.message ?? error),
        delta: null,
      });
      continue;
    }
    const observedStartingHp = startingHpByOwner(run);
    if (observedStartingHp[2] !== startingHp[2] || observedStartingHp[3] !== startingHp[3]) {
      throw new Error(`${ratio} returned unexpected starting HP totals`);
    }
    const simulation = {
      winnerOwner: run.winnerOwner,
      winnerHp: run.winnerHp,
      durationSeconds: round(run.ticks / 60),
      survivors: finalSurvivors(run),
      signedOutcomeScorePoints: round(score(run.winnerOwner, run.winnerHp, startingHp)),
      ticks: run.ticks,
      contactSteeringMode: run.contactSteeringMode,
      contactSteering: run.contactSteeringSummary,
      crowding: frameContactSummary(run),
    };
    rows.push({
      ratio,
      counts: { heavyCavalryArchers: run.side2.count, champions: run.side3.count },
      startingHp,
      tape,
      simulation,
      delta: {
        winnerMatches: simulation.winnerOwner === tape.winnerOwner,
        signedOutcomeScorePoints: round(
          simulation.signedOutcomeScorePoints - tape.signedOutcomeScorePoints.median,
        ),
        winnerHp: round(simulation.winnerHp - tape.winnerHp.median),
        durationSeconds: round(simulation.durationSeconds - tape.durationSeconds.median),
        durationPercent: round(
          ((simulation.durationSeconds / tape.durationSeconds.median) - 1) * 100,
        ),
        survivors: round(simulation.survivors - tape.survivors.median),
        withinTapeWinnerHpRange:
          simulation.winnerHp >= tape.winnerHp.minimum
          && simulation.winnerHp <= tape.winnerHp.maximum,
        withinTapeDurationRange:
          simulation.durationSeconds >= tape.durationSeconds.minimum
          && simulation.durationSeconds <= tape.durationSeconds.maximum,
        withinTapeSurvivorRange:
          simulation.survivors >= tape.survivors.minimum
          && simulation.survivors <= tape.survivors.maximum,
      },
    });
  }
} finally {
  server.close();
  await once(server, "close");
}

const completedRows = rows.filter(({ simulation }) => simulation !== null);
const absoluteOutcomeDeltas = completedRows.map(
  ({ delta }) => Math.abs(delta.signedOutcomeScorePoints),
);
const absoluteDurationPercents = completedRows.map(({ delta }) => Math.abs(delta.durationPercent));
const report = {
  schemaVersion: 1,
  generatedOn: "2026-08-13",
  source: {
    archive: fixture.archive,
    zipSha256: "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5",
    fixture: "calibration/fixtures/hcavarcher_vs_champion_kiting_basics.json",
    tapeRepeatsPerRatio: 5,
  },
  engine: {
    endpoint: "/api/ranged-vs-melee-kiting",
    ranged: "heavy_cav_archer",
    melee: "champion",
    navigation: "cohesive",
    contactSteering: "preventive-contact-graph",
    simulationRunsPerRatio: 1,
    deterministic: true,
  },
  metricDefinitions: {
    signedOutcomeScorePoints:
      "Winner remaining HP divided by that side's starting HP, in percentage points; owner 2/HCA is positive and owner 3/Champion is negative.",
    contact:
      "Champion center separation below 0.40 tiles on both axes (Chebyshev distance).",
    compactTriple:
      "At least three living Champions form a mutual-contact clique while both sides remain alive.",
  },
  rows,
  summary: {
    ratios: rows.length,
    completedRatios: completedRows.length,
    failedRatios: rows.length - completedRows.length,
    correctWinners: completedRows.filter(({ delta }) => delta.winnerMatches).length,
    withinTapeWinnerHpRange: completedRows.filter(
      ({ delta }) => delta.withinTapeWinnerHpRange,
    ).length,
    withinTapeDurationRange: completedRows.filter(
      ({ delta }) => delta.withinTapeDurationRange,
    ).length,
    withinTapeSurvivorRange: completedRows.filter(
      ({ delta }) => delta.withinTapeSurvivorRange,
    ).length,
    medianAbsoluteOutcomeDeltaPoints: round(median(absoluteOutcomeDeltas)),
    meanAbsoluteOutcomeDeltaPoints: round(
      absoluteOutcomeDeltas.reduce((sum, value) => sum + value, 0) / completedRows.length,
    ),
    meanAbsoluteDurationPercent: round(
      absoluteDurationPercents.reduce((sum, value) => sum + value, 0) / completedRows.length,
    ),
  },
};

console.log(JSON.stringify(report, null, 2));
