// Reproducible timing comparison for the authorized 5 HCA vs 10 Champion tapes.
// Reads only decoded frames.bin traces and one in-process current-engine replay.
import { once } from "node:events";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { createMapServer } from "../server.mjs";


const ROOT = fileURLToPath(new URL("..", import.meta.url));
const TRACE_ROOT = new URL(
  "../calibration/analysis/hca_champion_first_engagement/", import.meta.url,
);
const REPORT_ROOT = new URL("../calibration/reports/", import.meta.url);
const FIXTURE_URL = new URL(
  "../calibration/fixtures/hcavarcher_vs_champion_kiting_basics.json", import.meta.url,
);
const RATIOS = ["5v10", "10v5", "15v20", "20v15", "20v20"];
const HCA_MASTER = 474;
const CHAMPION_MASTER = 567;
const HCA_RELEASE_SECONDS = 0.8969999328255653;
const CHAMPION_DAMAGE = 13;
const EPSILON = 1e-5;
const CHAMPION_FULL_ALLY_EXTENT = 0.4;


function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


function quantile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * q;
  const lower = Math.floor(index);
  const fraction = index - lower;
  return sorted[lower] + (sorted[lower + 1] - sorted[lower]) * (fraction || 0);
}


function summarize(values) {
  const finite = values.filter(Number.isFinite);
  return {
    n: finite.length,
    mean: finite.length ? finite.reduce((sum, value) => sum + value, 0) / finite.length : null,
    median: median(finite),
    p01: quantile(finite, 0.01),
    p05: quantile(finite, 0.05),
    p25: quantile(finite, 0.25),
    p75: quantile(finite, 0.75),
    p95: quantile(finite, 0.95),
    p99: quantile(finite, 0.99),
    min: finite.length ? Math.min(...finite) : null,
    max: finite.length ? Math.max(...finite) : null,
  };
}


function summarizeSeparations(values) {
  const summary = summarize(values);
  const finite = values.filter(Number.isFinite);
  return {
    ...summary,
    shareBelow032: finite.length ? finite.filter((value) => value < 0.32 - EPSILON).length / finite.length : null,
    shareBelow020: finite.length ? finite.filter((value) => value < 0.20 - EPSILON).length / finite.length : null,
    shareBelow010: finite.length ? finite.filter((value) => value < 0.10 - EPSILON).length / finite.length : null,
  };
}


function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}


function groupFrames(rows) {
  const grouped = new Map();
  for (const row of rows) {
    if (!grouped.has(row.t)) grouped.set(row.t, []);
    grouped.get(row.t).push(row);
  }
  return [...grouped].sort(([left], [right]) => left - right).map(([t, units]) => ({
    t,
    units: new Map(units.map((unit) => [unit.id, unit])),
  }));
}


function buildSeries(frames) {
  const byId = new Map();
  for (const frame of frames) {
    for (const unit of frame.units.values()) {
      if (!byId.has(unit.id)) byId.set(unit.id, []);
      byId.get(unit.id).push({ ...unit, t: frame.t });
    }
  }
  return byId;
}


function nearestEnemy(frame, unit, enemyOwner) {
  let nearest = Infinity;
  for (const enemy of frame.units.values()) {
    if (enemy.owner !== enemyOwner || !enemy.alive) continue;
    nearest = Math.min(nearest, distance(unit, enemy));
  }
  return Number.isFinite(nearest) ? nearest : null;
}


function frameAtOrAfter(frames, time) {
  let low = 0;
  let high = frames.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (frames[middle].t < time) low = middle + 1;
    else high = middle;
  }
  return frames[low];
}


function damageFromHp(seriesById, targetOwner) {
  const events = [];
  for (const series of seriesById.values()) {
    if (series[0]?.owner !== targetOwner) continue;
    for (let index = 1; index < series.length; index += 1) {
      const before = series[index - 1].hp;
      const after = series[index].hp;
      if (Number.isFinite(before) && Number.isFinite(after) && after < before) {
        events.push({ t: series[index].t, targetId: series[index].id, amount: before - after });
      }
    }
  }
  return events;
}


function championOverlap(frames) {
  const categoryTotals = { bothMoving: 0, oneMoving: 0, bothStopped: 0 };
  const categoryOverlaps = { bothMoving: 0, oneMoving: 0, bothStopped: 0 };
  const motionSeparations = { bothMoving: [], oneMoving: [], bothStopped: [] };
  const attackSeparations = { bothAttackCycle: [], oneAttackCycle: [], neitherAttackCycle: [] };
  const movingPastStoppedAttackerSeparations = [];
  const separations = [];
  const overlapFrames = [];
  const deepestObservations = [];
  const episodes = [];
  const active = new Map();

  function finish(key) {
    const rows = active.get(key);
    if (!rows?.length) return;
    const projectionTracks = new Map();
    for (const row of rows) {
      if (!row.mover || !row.stopper || !row.target) continue;
      const targetDx = row.target.x - row.stopper.x;
      const targetDy = row.target.y - row.stopper.y;
      const targetLength = Math.hypot(targetDx, targetDy);
      if (targetLength <= EPSILON) continue;
      const projection = (
        (row.mover.x - row.stopper.x) * targetDx
          + (row.mover.y - row.stopper.y) * targetDy
      ) / targetLength;
      const trackKey = `${row.mover.id}:${row.stopper.id}:${row.target.id}`;
      if (!projectionTracks.has(trackKey)) projectionTracks.set(trackKey, []);
      projectionTracks.get(trackKey).push(projection);
    }
    const passThrough = [...projectionTracks.values()].some((values) => (
      Math.min(...values) < -0.01 && Math.max(...values) > 0.01
    ));
    episodes.push({
      pair: key,
      start: rows[0].t,
      end: rows.at(-1).t,
      duration: rows.at(-1).t - rows[0].t,
      minSeparation: Math.min(...rows.map(({ separation }) => separation)),
      oneMovingThroughStoppedAttacker: rows.some(({ stoppedAttacking }) => stoppedAttacking),
      movingChampionPursuingHca: rows.some(({ mover, target }) => (
        mover && target && target.owner === 2
      )),
      passThrough,
    });
    active.delete(key);
  }

  for (let frameIndex = 0; frameIndex < frames.length; frameIndex += 1) {
    const frame = frames[frameIndex];
    const previous = frames[frameIndex - 1];
    const champions = [...frame.units.values()].filter(({ owner, alive }) => owner === 3 && alive);
    const overlappedKeys = new Set();
    for (let leftIndex = 0; leftIndex < champions.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < champions.length; rightIndex += 1) {
        const left = champions[leftIndex];
        const right = champions[rightIndex];
        const leftPrevious = previous?.units.get(left.id);
        const rightPrevious = previous?.units.get(right.id);
        const leftMoving = Boolean(leftPrevious && distance(left, leftPrevious) > EPSILON);
        const rightMoving = Boolean(rightPrevious && distance(right, rightPrevious) > EPSILON);
        const category = leftMoving && rightMoving
          ? "bothMoving" : leftMoving || rightMoving ? "oneMoving" : "bothStopped";
        const leftAttackCycle = left.actionState === 6 || left.actionState === 7
          || left.action === "attacking" || left.action === "reload";
        const rightAttackCycle = right.actionState === 6 || right.actionState === 7
          || right.action === "attacking" || right.action === "reload";
        const attackCategory = leftAttackCycle && rightAttackCycle
          ? "bothAttackCycle"
          : leftAttackCycle || rightAttackCycle ? "oneAttackCycle" : "neitherAttackCycle";
        categoryTotals[category] += 1;
        const separation = Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
        if (separation >= CHAMPION_FULL_ALLY_EXTENT - 1e-9) continue;
        categoryOverlaps[category] += 1;
        separations.push(separation);
        motionSeparations[category].push(separation);
        attackSeparations[attackCategory].push(separation);
        const key = left.id < right.id ? `${left.id}:${right.id}` : `${right.id}:${left.id}`;
        overlappedKeys.add(key);
        const mover = leftMoving !== rightMoving ? (leftMoving ? left : right) : null;
        const stopper = mover ? (leftMoving ? right : left) : null;
        const targetId = mover?.targetId;
        const target = Number.isFinite(targetId) ? frame.units.get(targetId) : null;
        const stoppedAttacking = Boolean(stopper && (
          stopper.actionState === 6 || stopper.actionState === 7
            || stopper.action === "attacking" || stopper.action === "reload"
        ));
        if (mover && stoppedAttacking) movingPastStoppedAttackerSeparations.push(separation);
        deepestObservations.push({
          t: frame.t,
          pair: key,
          separation,
          motionCategory: category,
          attackCategory,
          left: { id: left.id, moving: leftMoving, actionState: left.actionState, action: left.action },
          right: { id: right.id, moving: rightMoving, actionState: right.actionState, action: right.action },
        });
        const row = {
          t: frame.t,
          separation,
          category,
          mover,
          stopper,
          target,
          stoppedAttacking,
        };
        overlapFrames.push(row);
        if (!active.has(key)) active.set(key, []);
        active.get(key).push(row);
      }
    }
    for (const key of [...active.keys()]) {
      if (!overlappedKeys.has(key)) finish(key);
    }
  }
  for (const key of [...active.keys()]) finish(key);

  const overlapCount = Object.values(categoryOverlaps).reduce((sum, value) => sum + value, 0);
  const deepest = (rows) => rows.reduce((best, row) => (
    best === null || row.separation < best.separation ? row : best
  ), null);
  return {
    fullExtentTiles: CHAMPION_FULL_ALLY_EXTENT,
    pairFrames: Object.fromEntries(Object.keys(categoryTotals).map((category) => [category, {
      total: categoryTotals[category],
      overlapped: categoryOverlaps[category],
      overlapRate: categoryTotals[category]
        ? categoryOverlaps[category] / categoryTotals[category] : null,
    }])),
    overlapComposition: Object.fromEntries(Object.keys(categoryOverlaps).map((category) => [
      category,
      overlapCount ? categoryOverlaps[category] / overlapCount : null,
    ])),
    separationTiles: summarizeSeparations(separations),
    separationByMotionTiles: Object.fromEntries(Object.entries(motionSeparations).map(
      ([category, values]) => [category, summarizeSeparations(values)],
    )),
    separationByAttackPhaseTiles: Object.fromEntries(Object.entries(attackSeparations).map(
      ([category, values]) => [category, summarizeSeparations(values)],
    )),
    movingPastStoppedAttackerSeparationTiles: summarizeSeparations(
      movingPastStoppedAttackerSeparations,
    ),
    deepestObservations: deepestObservations
      .sort((left, right) => left.separation - right.separation || left.t - right.t)
      .slice(0, 10),
    deepestByMotion: Object.fromEntries(Object.keys(motionSeparations).map((category) => [
      category, deepest(deepestObservations.filter((row) => row.motionCategory === category)),
    ])),
    deepestByAttackPhase: Object.fromEntries(Object.keys(attackSeparations).map((category) => [
      category, deepest(deepestObservations.filter((row) => row.attackCategory === category)),
    ])),
    deepestMovingPastStoppedAttacker: deepest(deepestObservations.filter((row) => (
      row.motionCategory === "oneMoving"
        && ((row.left.moving && (row.right.actionState === 6 || row.right.actionState === 7
          || row.right.action === "attacking" || row.right.action === "reload"))
        || (row.right.moving && (row.left.actionState === 6 || row.left.actionState === 7
          || row.left.action === "attacking" || row.left.action === "reload")))
    ))),
    _separationSamples: {
      motion: motionSeparations,
      attack: attackSeparations,
      movingPastStoppedAttacker: movingPastStoppedAttackerSeparations,
    },
    episodes: {
      count: episodes.length,
      durationSeconds: summarize(episodes.map(({ duration }) => duration)),
      minSeparationTiles: summarize(episodes.map(({ minSeparation }) => minSeparation)),
      oneMovingThroughStoppedAttacker: episodes.filter(
        ({ oneMovingThroughStoppedAttacker }) => oneMovingThroughStoppedAttacker,
      ).length,
      movingChampionPursuingHca: episodes.filter(
        ({ movingChampionPursuingHca }) => movingChampionPursuingHca,
      ).length,
      passThrough: episodes.filter(({ passThrough }) => passThrough).length,
    },
  };
}


function analyzeRun({ source, tag, frames, shotStarts, damageEvents, outcome }) {
  const seriesById = buildSeries(frames);
  const frameByTime = new Map(frames.map((frame) => [frame.t, frame]));
  const hcaIds = [...seriesById].filter(([, series]) => (
    series[0]?.owner === 2 && series[0]?.master === HCA_MASTER
  )).map(([id]) => id);
  const shotsById = new Map(hcaIds.map((id) => [id, []]));
  for (const shot of shotStarts) {
    if (shotsById.has(shot.actorId)) shotsById.get(shot.actorId).push(shot);
  }

  const shotRows = [];
  const stopEpisodes = new Map();
  for (const id of hcaIds) {
    const series = seriesById.get(id);
    const moves = series.map((row, index) => (
      index > 0 && distance(row, series[index - 1]) > EPSILON
    ));
    const indexAtTime = new Map(series.map((row, index) => [row.t, index]));
    const shots = shotsById.get(id).sort((left, right) => left.t - right.t);
    for (let shotIndex = 0; shotIndex < shots.length; shotIndex += 1) {
      const shot = shots[shotIndex];
      let index = indexAtTime.get(shot.t);
      if (index === undefined) {
        index = series.findIndex((row) => row.t >= shot.t);
      }
      if (index < 0) continue;
      let lastMoveIndex = -1;
      for (let cursor = index; cursor > 0; cursor -= 1) {
        if (moves[cursor]) {
          lastMoveIndex = cursor;
          break;
        }
      }
      let nextMoveIndex = -1;
      for (let cursor = index + 1; cursor < series.length; cursor += 1) {
        if (moves[cursor]) {
          nextMoveIndex = cursor;
          break;
        }
      }
      const previousShot = shots[shotIndex - 1];
      let pathSincePreviousShot = 0;
      let movingSincePreviousShot = 0;
      if (previousShot) {
        for (let cursor = 1; cursor <= index; cursor += 1) {
          if (series[cursor].t <= previousShot.t || series[cursor].t > shot.t) continue;
          const step = distance(series[cursor], series[cursor - 1]);
          if (step > EPSILON) {
            pathSincePreviousShot += step;
            movingSincePreviousShot += series[cursor].t - series[cursor - 1].t;
          }
        }
      }
      const frame = frameByTime.get(series[index].t) ?? frameAtOrAfter(frames, series[index].t);
      const unit = frame.units.get(id);
      const releaseTime = shot.releaseTime ?? shot.t + HCA_RELEASE_SECONDS;
      const releaseFrame = frameAtOrAfter(frames, releaseTime);
      const releaseUnit = releaseFrame?.units.get(id);
      const nextMoveTime = nextMoveIndex >= 0 ? series[nextMoveIndex].t : null;
      const completed = nextMoveTime === null || nextMoveTime + 0.03 >= releaseTime;
      const row = {
        id,
        t: shot.t,
        recurrent: lastMoveIndex >= 0,
        completed,
        cadence: previousShot ? shot.t - previousShot.t : null,
        pathSincePreviousShot: previousShot ? pathSincePreviousShot : null,
        movingSincePreviousShot: previousShot ? movingSincePreviousShot : null,
        arrivalToAttackStart: lastMoveIndex >= 0 ? shot.t - series[lastMoveIndex].t : null,
        attackStartToMove: nextMoveTime === null ? null : nextMoveTime - shot.t,
        releaseToMove: nextMoveTime === null ? null : nextMoveTime - releaseTime,
        nearestChampionAtAttackStart: unit ? nearestEnemy(frame, unit, 3) : null,
        nearestChampionAtRelease: releaseUnit ? nearestEnemy(releaseFrame, releaseUnit, 3) : null,
      };
      shotRows.push(row);
      if (lastMoveIndex >= 0) {
        const key = `${id}:${lastMoveIndex}:${nextMoveIndex}`;
        if (!stopEpisodes.has(key)) {
          const start = series[lastMoveIndex].t;
          const end = nextMoveTime ?? series.at(-1).t;
          const hits = damageEvents.filter((event) => (
            event.targetId === id && event.t >= start && event.t < end
          ));
          stopEpisodes.set(key, {
            id,
            start,
            end,
            duration: end - start,
            shotCount: 0,
            hitFrames: hits.length,
            hitEquivalents: hits.reduce((total, hit) => total + hit.amount, 0) / CHAMPION_DAMAGE,
          });
        }
        stopEpisodes.get(key).shotCount += 1;
      }
    }
  }

  const recurrent = shotRows.filter(({ recurrent, completed }) => recurrent && completed);
  const episodes = [...stopEpisodes.values()];
  const totalHcaDamage = damageEvents.filter(({ targetId }) => hcaIds.includes(targetId))
    .reduce((total, event) => total + event.amount, 0);
  return {
    source,
    tag,
    outcome,
    counts: {
      hca: hcaIds.length,
      attackStarts: shotRows.length,
      recurrentCompletedAttackStarts: recurrent.length,
      stopEpisodes: episodes.length,
    },
    shotCycle: {
      cadenceSeconds: summarize(recurrent.map(({ cadence }) => cadence)),
      pathTilesBetweenAttackStarts: summarize(
        recurrent.map(({ pathSincePreviousShot }) => pathSincePreviousShot),
      ),
      movingSecondsBetweenAttackStarts: summarize(
        recurrent.map(({ movingSincePreviousShot }) => movingSincePreviousShot),
      ),
      arrivalToAttackStartSeconds: summarize(
        recurrent.map(({ arrivalToAttackStart }) => arrivalToAttackStart),
      ),
      attackStartToMoveSeconds: summarize(recurrent.map(({ attackStartToMove }) => attackStartToMove)),
      releaseToMoveSeconds: summarize(recurrent.map(({ releaseToMove }) => releaseToMove)),
      nearestChampionAtAttackStartTiles: summarize(
        recurrent.map(({ nearestChampionAtAttackStart }) => nearestChampionAtAttackStart),
      ),
      nearestChampionAtReleaseTiles: summarize(
        recurrent.map(({ nearestChampionAtRelease }) => nearestChampionAtRelease),
      ),
    },
    stopExposure: {
      durationSeconds: summarize(episodes.map(({ duration }) => duration)),
      championHitEquivalents: summarize(episodes.map(({ hitEquivalents }) => hitEquivalents)),
      shareWithAnyChampionHit: episodes.length
        ? episodes.filter(({ hitEquivalents }) => hitEquivalents > 0).length / episodes.length : null,
      shareWithMultipleChampionHits: episodes.length
        ? episodes.filter(({ hitEquivalents }) => hitEquivalents >= 1.5).length / episodes.length : null,
      totalHcaDamage,
      totalChampionHitEquivalents: totalHcaDamage / CHAMPION_DAMAGE,
    },
    championAlliedOverlap: championOverlap(frames),
  };
}


async function loadTape(tag, fixtureRun) {
  const text = await readFile(new URL(`${tag}.tape_trace.jsonl`, TRACE_ROOT), "utf8");
  const raw = text.trim().split(/\r?\n/).map(JSON.parse).filter((row) => (
    row.master === HCA_MASTER || row.master === CHAMPION_MASTER
  ));
  const rows = raw.map((row) => ({
    id: row.id,
    master: row.master,
    owner: row.owner,
    t: row.t_ms / 1000,
    x: row.x,
    y: row.y,
    hp: row.hp,
    alive: (row.hp ?? 0) > 0,
    actionState: row.action_state,
    targetId: row.target_id,
  }));
  const frames = groupFrames(rows).filter(({ t }) => t <= fixtureRun.lastDeathSeconds + EPSILON);
  const seriesById = buildSeries(frames);
  const shotStarts = [];
  for (const [id, series] of seriesById) {
    if (series[0]?.master !== HCA_MASTER) continue;
    for (let index = 1; index < series.length; index += 1) {
      if (series[index].actionState === 7 && series[index - 1].actionState !== 7) {
        shotStarts.push({ actorId: id, t: series[index].t });
      }
    }
  }
  const damageEvents = damageFromHp(seriesById, 2);
  return analyzeRun({
    source: "tape",
    tag,
    frames,
    shotStarts,
    damageEvents,
    outcome: {
      durationSeconds: fixtureRun.lastDeathSeconds,
      winnerOwner: fixtureRun.winnerOwner,
      winnerHp: fixtureRun.winnerHp,
      survivors: fixtureRun.survivors,
    },
  });
}


async function currentSimulation(ratio, canonicalStartUnits) {
  const [count2, count3] = ratio.split("v").map(Number);
  const server = createMapServer({ root: ROOT });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const response = await fetch(
      `http://127.0.0.1:${server.address().port}/api/ranged-vs-melee-kiting`
        + `?ranged=heavy_cav_archer&melee=champion&navigation=cohesive&n2=${count2}&n3=${count3}`,
    );
    const run = await response.json();
    if (!response.ok) throw new Error(run.error ?? `viewer returned ${response.status}`);
    const frames = run.snapshots.map((snapshot) => ({
      t: snapshot.tick / 60,
      units: new Map(snapshot.units.map((unit) => {
        const meta = run.unitIndex[unit[0]];
        return [unit[0], {
          id: unit[0],
          master: meta.master,
          owner: meta.owner,
          x: unit[1],
          y: unit[2],
          hp: unit[4],
          alive: Boolean(unit[5]),
          action: unit[6],
          targetId: unit[7] ?? unit[8] ?? unit[9],
        }];
      })),
    }));
    const positionKey = ({ owner, x, y }) => `${owner}:${x.toFixed(6)}:${y.toFixed(6)}`;
    const expectedPositions = canonicalStartUnits.map((unit) => positionKey({
      owner: Number(unit.owner ?? unit[1]),
      x: Number(unit.x ?? unit[3]),
      y: Number(unit.y ?? unit[4]),
    })).sort();
    const actualPositions = [...frames[0].units.values()].map(positionKey).sort();
    if (JSON.stringify(actualPositions) !== JSON.stringify(expectedPositions)) {
      throw new Error(`current ${ratio} simulation did not use its canonical tape placement`);
    }
    const events = run.snapshots.flatMap(({ events }) => events);
    const shotStarts = events.filter(({ type, actorId }) => (
      type === "attack-start" && run.unitIndex[actorId]?.owner === 2
    )).map((event) => ({
      actorId: event.actorId,
      t: event.tick / 60,
      releaseTime: event.readyTick / 60,
    }));
    const damageEvents = events.filter(({ type, actorId, targetId }) => (
      type === "damage"
        && run.unitIndex[actorId]?.owner === 3
        && run.unitIndex[targetId]?.owner === 2
    )).map((event) => ({
      t: event.tick / 60,
      targetId: event.targetId,
      amount: event.amount,
    }));
    const survivors = Object.entries(run.unitIndex).filter(([id, meta]) => {
      if (meta.owner !== run.winnerOwner) return false;
      return frames.at(-1).units.get(Number(id))?.alive;
    }).length;
    const analyzed = analyzeRun({
      source: "sim",
      tag: `current-exact-placement-${ratio}`,
      frames,
      shotStarts,
      damageEvents,
      outcome: {
        durationSeconds: run.ticks / 60,
        winnerOwner: run.winnerOwner,
        winnerHp: run.winnerHp,
        survivors,
      },
    });
    analyzed.placement = { source: "dedicated-tape-ratio", exact: true };
    return analyzed;
  } finally {
    server.close();
    await once(server, "close");
  }
}


function pooledTape(tapes) {
  const metric = (path) => tapes.flatMap((run) => {
    let value = run;
    for (const key of path) value = value[key];
    return value;
  });
  const outcome = (key) => summarize(tapes.map((run) => run.outcome[key]));
  return {
    runs: tapes.length,
    outcome: {
      durationSeconds: outcome("durationSeconds"),
      winnerHp: outcome("winnerHp"),
      survivors: outcome("survivors"),
    },
    // Pool each run's raw-like distribution through weighted moments is not
    // possible after summarization. Medians below summarize run medians, while
    // shares and counts are weighted explicitly.
    shotCycleRunMedians: Object.fromEntries([
      "cadenceSeconds",
      "pathTilesBetweenAttackStarts",
      "movingSecondsBetweenAttackStarts",
      "arrivalToAttackStartSeconds",
      "attackStartToMoveSeconds",
      "releaseToMoveSeconds",
      "nearestChampionAtAttackStartTiles",
      "nearestChampionAtReleaseTiles",
    ].map((key) => [key, summarize(tapes.map((run) => run.shotCycle[key].median))])),
    stopExposureRunMedians: {
      durationSeconds: summarize(tapes.map((run) => run.stopExposure.durationSeconds.median)),
      championHitEquivalents: summarize(
        tapes.map((run) => run.stopExposure.championHitEquivalents.median),
      ),
      shareWithAnyChampionHit: summarize(
        tapes.map((run) => run.stopExposure.shareWithAnyChampionHit),
      ),
      shareWithMultipleChampionHits: summarize(
        tapes.map((run) => run.stopExposure.shareWithMultipleChampionHits),
      ),
      totalChampionHitEquivalents: summarize(
        tapes.map((run) => run.stopExposure.totalChampionHitEquivalents),
      ),
    },
    championAlliedOverlapRunMedians: {
      bothMovingOverlapRate: summarize(tapes.map(
        (run) => run.championAlliedOverlap.pairFrames.bothMoving.overlapRate,
      )),
      oneMovingOverlapRate: summarize(tapes.map(
        (run) => run.championAlliedOverlap.pairFrames.oneMoving.overlapRate,
      )),
      bothStoppedOverlapRate: summarize(tapes.map(
        (run) => run.championAlliedOverlap.pairFrames.bothStopped.overlapRate,
      )),
      separationTiles: summarize(tapes.map(
        (run) => run.championAlliedOverlap.separationTiles.median,
      )),
      passThroughEpisodes: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.passThrough,
      )),
      movingThroughStoppedAttackerEpisodes: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.oneMovingThroughStoppedAttacker,
      )),
      episodeRatePerFightSecond: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.count / run.outcome.durationSeconds,
      )),
      passThroughRatePerFightSecond: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.passThrough / run.outcome.durationSeconds,
      )),
      movingThroughStoppedAttackerRatePerFightSecond: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.oneMovingThroughStoppedAttacker
          / run.outcome.durationSeconds,
      )),
      episodeDurationSeconds: summarize(tapes.map(
        (run) => run.championAlliedOverlap.episodes.durationSeconds.median,
      )),
    },
    championAlliedOverlapExtremes: {
      byMotion: Object.fromEntries(["bothMoving", "oneMoving", "bothStopped"].map(
        (category) => [category, summarizeSeparations(tapes.flatMap(
          (run) => run.championAlliedOverlap._separationSamples.motion[category],
        ))],
      )),
      runMinimumByMotion: Object.fromEntries(["bothMoving", "oneMoving", "bothStopped"].map(
        (category) => [category, summarize(tapes.map(
          (run) => run.championAlliedOverlap.separationByMotionTiles[category].min,
        ))],
      )),
      byAttackPhase: Object.fromEntries([
        "bothAttackCycle", "oneAttackCycle", "neitherAttackCycle",
      ].map((category) => [category, summarizeSeparations(tapes.flatMap(
        (run) => run.championAlliedOverlap._separationSamples.attack[category],
      ))])),
      runMinimumByAttackPhase: Object.fromEntries([
        "bothAttackCycle", "oneAttackCycle", "neitherAttackCycle",
      ].map((category) => [category, summarize(tapes.map(
        (run) => run.championAlliedOverlap.separationByAttackPhaseTiles[category].min,
      ))])),
      movingPastStoppedAttacker: summarizeSeparations(tapes.flatMap(
        (run) => run.championAlliedOverlap._separationSamples.movingPastStoppedAttacker,
      )),
      deepestObservations: tapes.flatMap((run) => (
        run.championAlliedOverlap.deepestObservations.map((row) => ({ tag: run.tag, ...row }))
      )).sort((left, right) => left.separation - right.separation || left.t - right.t).slice(0, 15),
    },
    runDetails: tapes,
  };
}


function fmt(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}


function markdown(report) {
  const tape = report.tape;
  const sim = report.sim;
  const tm = tape.shotCycleRunMedians;
  const to = tape.championAlliedOverlapRunMedians;
  const so = sim.championAlliedOverlap;
  const te = tape.championAlliedOverlapExtremes;
  const extremeRows = [
    ["Both moving", te.byMotion.bothMoving, so.separationByMotionTiles.bothMoving],
    ["One moving, one stopped", te.byMotion.oneMoving, so.separationByMotionTiles.oneMoving],
    ["Both stopped", te.byMotion.bothStopped, so.separationByMotionTiles.bothStopped],
    ["Both in swing/reload", te.byAttackPhase.bothAttackCycle,
      so.separationByAttackPhaseTiles.bothAttackCycle],
    ["Exactly one in swing/reload", te.byAttackPhase.oneAttackCycle,
      so.separationByAttackPhaseTiles.oneAttackCycle],
    ["Neither in swing/reload", te.byAttackPhase.neitherAttackCycle,
      so.separationByAttackPhaseTiles.neitherAttackCycle],
    ["Moving past stopped swing/reload ally", te.movingPastStoppedAttacker,
      so.movingPastStoppedAttackerSeparationTiles],
  ];
  const rows = [
    ["Path between recurrent attack starts", "tiles", tm.pathTilesBetweenAttackStarts.median,
      sim.shotCycle.pathTilesBetweenAttackStarts.median],
    ["Time moving between attack starts", "s", tm.movingSecondsBetweenAttackStarts.median,
      sim.shotCycle.movingSecondsBetweenAttackStarts.median],
    ["Arrival/stop → attack animation starts", "s", tm.arrivalToAttackStartSeconds.median,
      sim.shotCycle.arrivalToAttackStartSeconds.median],
    ["Attack animation starts → next movement", "s", tm.attackStartToMoveSeconds.median,
      sim.shotCycle.attackStartToMoveSeconds.median],
    ["Projectile release → next movement", "s", tm.releaseToMoveSeconds.median,
      sim.shotCycle.releaseToMoveSeconds.median],
    ["Nearest Champion when attack animation starts", "tiles",
      tm.nearestChampionAtAttackStartTiles.median,
      sim.shotCycle.nearestChampionAtAttackStartTiles.median],
    ["Nearest Champion at projectile release", "tiles",
      tm.nearestChampionAtReleaseTiles.median,
      sim.shotCycle.nearestChampionAtReleaseTiles.median],
  ];
  return `# HCA versus Champion kite-cycle diagnostic\n\n`
    + `Authorized source: \`${report.source.archive}\`  \n`
    + `SHA-256: \`${report.source.zipSha256}\`  \n`
    + `Comparison: five tape repeats of 5 HCA vs 10 Champions against one deterministic current-engine run with exact tape placement.\n\n`
    + `## Finding\n\n`
    + `The HCA move leg and firing timing are already very close to tape. Champion overlap is bimodal: most tape overlap is shallow, but a repeatable deep tail lets pursuing allies pass almost through the same center. The current simulation instead clamps ordinary allied entry at 0.32/0.36 tiles and leaves those contacts compressed for longer. Tape Champions create roughly twice as many brief overlap/pass-through episodes per fight-second.\n\n`
    + `## Recurrent firing-cycle evidence\n\n`
    + `| Metric | Unit | Tape median of run medians | Current sim median | Sim − tape |\n`
    + `|---|---:|---:|---:|---:|\n`
    + rows.map(([label, unit, tapeValue, simValue]) => (
      `| ${label} | ${unit} | ${fmt(tapeValue)} | ${fmt(simValue)} | ${fmt(simValue - tapeValue, 2)} |`
    )).join("\n")
    + `\n\n## Champion allied-overlap evidence\n\n`
    + `A pair is counted as overlapping when its Chebyshev center separation is below the two full 0.20-tile radii (0.40 tiles). A pass-through requires a moving Champion to cross from behind to ahead of the stopped ally along its current HCA target line while the pair overlaps.\n\n`
    + `| Metric | Tape median across five runs | Current sim | Sim / tape |\n`
    + `|---|---:|---:|---:|\n`
    + `| Pair-frame overlap rate, both moving | ${fmt(100 * to.bothMovingOverlapRate.median, 1)}% | ${fmt(100 * so.pairFrames.bothMoving.overlapRate, 1)}% | ${fmt(so.pairFrames.bothMoving.overlapRate / to.bothMovingOverlapRate.median)}x |\n`
    + `| Pair-frame overlap rate, one moving | ${fmt(100 * to.oneMovingOverlapRate.median, 1)}% | ${fmt(100 * so.pairFrames.oneMoving.overlapRate, 1)}% | ${fmt(so.pairFrames.oneMoving.overlapRate / to.oneMovingOverlapRate.median)}x |\n`
    + `| Pair-frame overlap rate, both stopped | ${fmt(100 * to.bothStoppedOverlapRate.median, 1)}% | ${fmt(100 * so.pairFrames.bothStopped.overlapRate, 1)}% | ${fmt(so.pairFrames.bothStopped.overlapRate / to.bothStoppedOverlapRate.median)}x |\n`
    + `| Median separation while overlapped | ${fmt(to.separationTiles.median, 3)} tiles | ${fmt(so.separationTiles.median, 3)} tiles | ${fmt(so.separationTiles.median / to.separationTiles.median)}x |\n`
    + `| All overlap episodes / fight-second | ${fmt(to.episodeRatePerFightSecond.median)} | ${fmt(so.episodes.count / sim.outcome.durationSeconds)} | ${fmt((so.episodes.count / sim.outcome.durationSeconds) / to.episodeRatePerFightSecond.median)}x |\n`
    + `| Pass-through episodes / fight-second | ${fmt(to.passThroughRatePerFightSecond.median)} | ${fmt(so.episodes.passThrough / sim.outcome.durationSeconds)} | ${fmt((so.episodes.passThrough / sim.outcome.durationSeconds) / to.passThroughRatePerFightSecond.median)}x |\n`
    + `| Moving through stopped attacker / fight-second | ${fmt(to.movingThroughStoppedAttackerRatePerFightSecond.median)} | ${fmt(so.episodes.oneMovingThroughStoppedAttacker / sim.outcome.durationSeconds)} | ${fmt((so.episodes.oneMovingThroughStoppedAttacker / sim.outcome.durationSeconds) / to.movingThroughStoppedAttackerRatePerFightSecond.median)}x |\n`
    + `| Median overlap-episode duration | ${fmt(to.episodeDurationSeconds.median, 3)} s | ${fmt(so.episodes.durationSeconds.median, 3)} s | ${fmt(so.episodes.durationSeconds.median / to.episodeDurationSeconds.median)}x |\n`
    + `\n### Closest observed allied separations\n\n`
    + `Smaller separation means deeper overlap. The literal minimum is the single deepest sampled frame; p01 is a more robust description of repeatable deep overlap. All rows include only overlapping pair-frames below 0.40 tiles.\n\n`
    + `| Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |\n`
    + `|---|---:|---:|---:|---:|---:|---:|---:|---:|\n`
    + extremeRows.map(([label, tapeValues, simValues]) => (
      `| ${label} | ${fmt(tapeValues.min, 3)} | ${fmt(tapeValues.p01, 3)} | ${fmt(tapeValues.p05, 3)} | ${fmt(tapeValues.median, 3)} | ${fmt(simValues.min, 3)} | ${fmt(simValues.p01, 3)} | ${fmt(simValues.p05, 3)} | ${fmt(simValues.median, 3)} |`
    )).join("\n")
    + `\n\n| Pair condition | Tape below 0.32 | Tape below 0.20 | Tape below 0.10 | Sim below 0.32 |\n`
    + `|---|---:|---:|---:|---:|\n`
    + extremeRows.map(([label, tapeValues, simValues]) => (
      `| ${label} | ${fmt(100 * tapeValues.shareBelow032, 2)}% | ${fmt(100 * tapeValues.shareBelow020, 2)}% | ${fmt(100 * tapeValues.shareBelow010, 2)}% | ${fmt(100 * simValues.shareBelow032, 2)}% |`
    )).join("\n")
    + `\n\n## Stop exposure\n\n`
    + `| Metric | Tape median across runs | Current sim |\n`
    + `|---|---:|---:|\n`
    + `| Stops receiving ≥1 Champion hit | ${fmt(100 * tape.stopExposureRunMedians.shareWithAnyChampionHit.median, 1)}% | ${fmt(100 * sim.stopExposure.shareWithAnyChampionHit, 1)}% |\n`
    + `| Stops receiving multiple Champion hits | ${fmt(100 * tape.stopExposureRunMedians.shareWithMultipleChampionHits.median, 1)}% | ${fmt(100 * sim.stopExposure.shareWithMultipleChampionHits, 1)}% |\n`
    + `| Champion hit-equivalents over the fight | ${fmt(tape.stopExposureRunMedians.totalChampionHitEquivalents.median, 1)} | ${fmt(sim.stopExposure.totalChampionHitEquivalents, 1)} |\n`
    + `\n## Outcome context\n\n`
    + `| Metric | Tape median | Current sim |\n`
    + `|---|---:|---:|\n`
    + `| Champion HP remaining | ${fmt(tape.outcome.winnerHp.median, 0)} | ${fmt(sim.outcome.winnerHp, 0)} |\n`
    + `| Champion survivors | ${fmt(tape.outcome.survivors.median, 0)} | ${fmt(sim.outcome.survivors, 0)} |\n`
    + `| Duration | ${fmt(tape.outcome.durationSeconds.median, 2)} s | ${fmt(sim.outcome.durationSeconds, 2)} s |\n`
    + `\n## Interpretation and caveats\n\n`
    + `- Tape overlap happens in all three states: both Champions moving, one moving past a stopped ally, and both stopped after crowding. The most gameplay-relevant case is a pursuing Champion entering the footprint of a friendly Champion that has stopped to attack or reload, then continuing toward the HCA.\n`
    + `- The engine's collision solver already shrinks moving allied collision extents, but it hard-floors entry at 0.32/0.36 tiles while local avoidance plans around the ally's full 0.40-tile combined extent. The tape's sub-0.32 tail means merely aligning avoidance to 0.32/0.36 will improve flow but cannot reproduce every observed pass-through.\n`
    + `- The 0.897 s HCA attack delay is present in both sources; the current engine uses 54 ticks, matching the DAT-derived value.\n`
    + `- The comparison does not prove a single causal fix. Arrival-to-attack behavior, formation translation, and Champion contact conversion can interact.\n`
    + `- Tape timing is measured from decoded action-state transitions; sim timing is measured from attack-start/readyTick events. Those are the closest observable equivalents.\n`
    + `- The browser process on port 5011 was stale during the user's observation; this report runs the current module in-process and verifies the exact five HCA starting cells.\n`;
}


function suiteMarkdown(report) {
  const flowRows = [];
  const motionRows = [];
  const phaseRows = [];
  const deepRows = [];
  const exposureRows = [];
  const outcomeRows = [];
  for (const ratio of RATIOS) {
    const { tape, sim } = report.ratios[ratio];
    const to = tape.championAlliedOverlapRunMedians;
    const te = tape.championAlliedOverlapExtremes;
    const so = sim.championAlliedOverlap;
    const [hcaCount, championCount] = ratio.split("v").map(Number);
    flowRows.push([
      ratio,
      championCount,
      to.episodeRatePerFightSecond.median,
      so.episodes.count / sim.outcome.durationSeconds,
      to.passThroughRatePerFightSecond.median,
      so.episodes.passThrough / sim.outcome.durationSeconds,
      to.episodeDurationSeconds.median,
      so.episodes.durationSeconds.median,
    ]);
    for (const [label, tapeValues, simValues] of [
      ["both moving", te.byMotion.bothMoving, so.separationByMotionTiles.bothMoving],
      ["one moving", te.byMotion.oneMoving, so.separationByMotionTiles.oneMoving],
      ["both stopped", te.byMotion.bothStopped, so.separationByMotionTiles.bothStopped],
    ]) {
      motionRows.push([
        ratio, label,
        tapeValues.min, tapeValues.p01, tapeValues.p05, tapeValues.median,
        simValues.min, simValues.p01, simValues.p05, simValues.median,
      ]);
    }
    for (const [label, tapeValues, simValues] of [
      ["both swing/reload", te.byAttackPhase.bothAttackCycle,
        so.separationByAttackPhaseTiles.bothAttackCycle],
      ["one swing/reload", te.byAttackPhase.oneAttackCycle,
        so.separationByAttackPhaseTiles.oneAttackCycle],
      ["neither swing/reload", te.byAttackPhase.neitherAttackCycle,
        so.separationByAttackPhaseTiles.neitherAttackCycle],
      ["moving past stopped attacker", te.movingPastStoppedAttacker,
        so.movingPastStoppedAttackerSeparationTiles],
    ]) {
      phaseRows.push([
        ratio, label,
        tapeValues.min, tapeValues.p01, tapeValues.p05, tapeValues.median,
        simValues.min, simValues.p01, simValues.p05, simValues.median,
      ]);
    }
    for (const [label, tapeValues, simValues] of [
      ["both moving", te.byMotion.bothMoving, so.separationByMotionTiles.bothMoving],
      ["one moving", te.byMotion.oneMoving, so.separationByMotionTiles.oneMoving],
      ["both stopped", te.byMotion.bothStopped, so.separationByMotionTiles.bothStopped],
      ["moving past stopped attacker", te.movingPastStoppedAttacker,
        so.movingPastStoppedAttackerSeparationTiles],
    ]) {
      deepRows.push([
        ratio, label,
        tapeValues.shareBelow032, tapeValues.shareBelow020, tapeValues.shareBelow010,
        simValues.shareBelow032, simValues.shareBelow020, simValues.shareBelow010,
      ]);
    }
    exposureRows.push([
      ratio,
      tape.shotCycleRunMedians.nearestChampionAtAttackStartTiles.median,
      sim.shotCycle.nearestChampionAtAttackStartTiles.median,
      tape.shotCycleRunMedians.nearestChampionAtReleaseTiles.median,
      sim.shotCycle.nearestChampionAtReleaseTiles.median,
      tape.stopExposureRunMedians.shareWithAnyChampionHit.median,
      sim.stopExposure.shareWithAnyChampionHit,
      tape.stopExposureRunMedians.shareWithMultipleChampionHits.median,
      sim.stopExposure.shareWithMultipleChampionHits,
    ]);
    outcomeRows.push([
      ratio,
      `${hcaCount} / ${championCount}`,
      tape.outcome.durationSeconds.median,
      sim.outcome.durationSeconds,
      tape.outcome.winnerHp.median,
      sim.outcome.winnerHp,
      tape.outcome.survivors.median,
      sim.outcome.survivors,
    ]);
  }

  const aggregateTape = report.aggregate.tape.championAlliedOverlapExtremes;
  const aggregateSim = report.aggregate.sim.championAlliedOverlapExtremes;
  const aggregateRows = [
    ["both moving", aggregateTape.byMotion.bothMoving, aggregateSim.byMotion.bothMoving],
    ["one moving", aggregateTape.byMotion.oneMoving, aggregateSim.byMotion.oneMoving],
    ["both stopped", aggregateTape.byMotion.bothStopped, aggregateSim.byMotion.bothStopped],
    ["both swing/reload", aggregateTape.byAttackPhase.bothAttackCycle,
      aggregateSim.byAttackPhase.bothAttackCycle],
    ["one swing/reload", aggregateTape.byAttackPhase.oneAttackCycle,
      aggregateSim.byAttackPhase.oneAttackCycle],
    ["neither swing/reload", aggregateTape.byAttackPhase.neitherAttackCycle,
      aggregateSim.byAttackPhase.neitherAttackCycle],
    ["moving past stopped attacker", aggregateTape.movingPastStoppedAttacker,
      aggregateSim.movingPastStoppedAttacker],
  ];

  return `# HCA versus Champion allied-overlap suite\n\n`
    + `Authorized source: \`${report.source.archive}\`  \n`
    + `SHA-256: \`${report.source.zipSha256}\`  \n`
    + `Scope: 25 tape recordings: five ratios × five repeats, compared with one current deterministic exact-placement simulation per ratio. Ratio notation is HCA count v Champion count.\n\n`
    + `## Technical summary\n\n`
    + `Deep friendly pass-through is not confined to 5v10. Every ratio contains Champion pairs below the current engine's 0.32-tile floor. Across all 25 tapes, the closest both-moving separation is ${fmt(aggregateTape.byMotion.bothMoving.min, 3)} tiles and the robust p01 is ${fmt(aggregateTape.byMotion.bothMoving.p01, 3)}; the five current simulations never go below ${fmt(aggregateSim.byMotion.bothMoving.min, 3)}. The depth and frequency grow with Champion crowd size, but the mechanism also appears in the five-Champion 10v5 fight.\n\n`
    + `## Deep overlap appears in every ratio\n\n`
    + `Smaller separation means deeper overlap. The literal minimum is the deepest sampled frame; p01 and p05 show the repeatable tail rather than relying on one frame. Only pair-frames below the normal 0.40-tile allied contact extent are included.\n\n`
    + `| Ratio | Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |\n`
    + `|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n`
    + motionRows.map((row) => `| ${row[0]} | ${row[1]} | ${fmt(row[2], 3)} | ${fmt(row[3], 3)} | ${fmt(row[4], 3)} | ${fmt(row[5], 3)} | ${fmt(row[6], 3)} | ${fmt(row[7], 3)} | ${fmt(row[8], 3)} | ${fmt(row[9], 3)} |`).join("\n")
    + `\n\n## Attack-state cuts show penetration is usually inherited from movement\n\n`
    + `Both-attacking pairs can remain deeply overlapped, but the moving and one-attacker cuts usually reach the deepest separations. This supports a movement-created overlap that can persist after a unit stops, rather than an attack animation independently making allies intangible.\n\n`
    + `| Ratio | Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |\n`
    + `|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n`
    + phaseRows.map((row) => `| ${row[0]} | ${row[1]} | ${fmt(row[2], 3)} | ${fmt(row[3], 3)} | ${fmt(row[4], 3)} | ${fmt(row[5], 3)} | ${fmt(row[6], 3)} | ${fmt(row[7], 3)} | ${fmt(row[8], 3)} | ${fmt(row[9], 3)} |`).join("\n")
    + `\n\n## Deep-tail frequency, not only the extreme\n\n`
    + `The sub-0.32 shares quantify how often tape positions exceed the engine's ordinary moving/moving compression. Sub-0.20 and sub-0.10 expose the much deeper pass-through tail.\n\n`
    + `| Ratio | Pair condition | Tape <0.32 | Tape <0.20 | Tape <0.10 | Sim <0.32 | Sim <0.20 | Sim <0.10 |\n`
    + `|---|---|---:|---:|---:|---:|---:|---:|\n`
    + deepRows.map((row) => `| ${row[0]} | ${row[1]} | ${fmt(100 * row[2], 2)}% | ${fmt(100 * row[3], 2)}% | ${fmt(100 * row[4], 2)}% | ${fmt(100 * row[5], 2)}% | ${fmt(100 * row[6], 2)}% | ${fmt(100 * row[7], 2)}% |`).join("\n")
    + `\n\n## Tape crowd flow turns over faster\n\n`
    + `Raw overlap frequency alone is misleading: current simulations can spend many frames compressed at their hard floor. Tape generally produces more distinct, shorter interactions and more confirmed pass-throughs per fight-second.\n\n`
    + `| Ratio | Champions | Tape episodes/s | Sim episodes/s | Tape pass-through/s | Sim pass-through/s | Tape median episode | Sim median episode |\n`
    + `|---|---:|---:|---:|---:|---:|---:|---:|\n`
    + flowRows.map((row) => `| ${row[0]} | ${row[1]} | ${fmt(row[2])} | ${fmt(row[3])} | ${fmt(row[4])} | ${fmt(row[5])} | ${fmt(row[6], 3)} s | ${fmt(row[7], 3)} s |`).join("\n")
    + `\n\n## Contact conversion varies by ratio\n\n`
    + `Nearest-Champion distance is measured when the HCA begins its attack animation and when the projectile releases. Stop exposure is the share of HCA stopping episodes that receive melee hits.\n\n`
    + `| Ratio | Tape distance at start | Sim | Tape distance at release | Sim | Tape stops hit | Sim | Tape stops multi-hit | Sim |\n`
    + `|---|---:|---:|---:|---:|---:|---:|---:|---:|\n`
    + exposureRows.map((row) => `| ${row[0]} | ${fmt(row[1])} | ${fmt(row[2])} | ${fmt(row[3])} | ${fmt(row[4])} | ${fmt(100 * row[5], 1)}% | ${fmt(100 * row[6], 1)}% | ${fmt(100 * row[7], 1)}% | ${fmt(100 * row[8], 1)}% |`).join("\n")
    + `\n\n## All-ratio pooled separation distribution\n\n`
    + `Pooling is used only for the collision distribution, not for battle outcomes, because the five ratios have different force sizes and winners.\n\n`
    + `| Pair condition | Tape n | Tape min | Tape p01 | Tape p05 | Tape median | Tape <0.32 | Sim n | Sim min | Sim p01 | Sim p05 | Sim median | Sim <0.32 |\n`
    + `|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n`
    + aggregateRows.map(([label, tapeValues, simValues]) => `| ${label} | ${tapeValues.n} | ${fmt(tapeValues.min, 3)} | ${fmt(tapeValues.p01, 3)} | ${fmt(tapeValues.p05, 3)} | ${fmt(tapeValues.median, 3)} | ${fmt(100 * tapeValues.shareBelow032, 2)}% | ${simValues.n} | ${fmt(simValues.min, 3)} | ${fmt(simValues.p01, 3)} | ${fmt(simValues.p05, 3)} | ${fmt(simValues.median, 3)} | ${fmt(100 * simValues.shareBelow032, 2)}% |`).join("\n")
    + `\n\n## Outcome context\n\n`
    + `| Ratio | HCA / Champion | Tape median duration | Sim duration | Tape winner HP | Sim winner HP | Tape survivors | Sim survivors |\n`
    + `|---|---|---:|---:|---:|---:|---:|---:|\n`
    + outcomeRows.map((row) => `| ${row[0]} | ${row[1]} | ${fmt(row[2])} s | ${fmt(row[3])} s | ${fmt(row[4], 0)} | ${fmt(row[5], 0)} | ${fmt(row[6], 0)} | ${fmt(row[7], 0)} |`).join("\n")
    + `\n\n## Scope, definitions, and limitations\n\n`
    + `- Champion overlap uses Chebyshev center separation because Genie obstruction is an axis-aligned box. Normal full contact is 0.40 tiles.\n`
    + `- Moving/stopped is inferred from consecutive decoded positions. Swing/reload is tape action state 7/6 and the equivalent current-engine action.\n`
    + `- A pass-through requires the moving Champion to cross from behind to ahead of the friendly blocker along its currently targeted HCA line while the pair overlaps. Target changes can make this conservative.\n`
    + `- Each tape ratio has five repeats; each simulation ratio has one deterministic exact-placement run. The simulation distribution therefore measures the present deterministic engine, not seed variance.\n`
    + `- The tape trace continues after the last death, but all per-second rates use the fixture's verified last-death time.\n\n`
    + `## Recommended next step\n\n`
    + `Test a general allied-transit rule behind an experiment flag: dynamic DAT-derived obstruction for ordinary movement, plus order-coherent pass-through for actively moving allies, while retaining full enemy and obstacle collision and preventing stopped units from initiating new penetration. Validate first against these per-ratio depth, turnover, and HCA-contact measures before considering a default engine change.\n`;
}


const fixture = JSON.parse(await readFile(FIXTURE_URL, "utf8"));
const allTapes = [];
const allSims = [];
const ratios = {};
for (const ratio of RATIOS) {
  const fixtureRuns = fixture.ratios[ratio].runs;
  const tapes = await Promise.all(fixtureRuns.map((run) => loadTape(run.tag, run)));
  const sim = await currentSimulation(ratio, fixture.ratios[ratio].canonicalStartUnits);
  allTapes.push(...tapes);
  allSims.push(sim);
  ratios[ratio] = { tape: pooledTape(tapes), sim };
}
const aggregateTape = pooledTape(allTapes);
const aggregateSim = pooledTape(allSims);
delete aggregateTape.runDetails;
delete aggregateSim.runDetails;
for (const run of allTapes) delete run.championAlliedOverlap._separationSamples;
for (const run of allSims) delete run.championAlliedOverlap._separationSamples;
const report = {
  schemaVersion: 2,
  generatedAt: new Date().toISOString(),
  source: {
    archive: "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip",
    zipSha256: "EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5",
    ratios: RATIOS,
    tapeRuns: allTapes.length,
    simulationRuns: allSims.length,
  },
  ratios,
  aggregate: { tape: aggregateTape, sim: aggregateSim },
};
await writeFile(
  new URL("hca_champion_overlap_suite_2026-08-13.json", REPORT_ROOT),
  `${JSON.stringify(report, null, 2)}\n`,
);
await writeFile(
  new URL("hca_champion_overlap_suite_2026-08-13.md", REPORT_ROOT),
  suiteMarkdown(report),
);
console.log(suiteMarkdown(report));
