import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import { createChampionScenario } from "../../src/champion-scenarios.js";
import { createWorld, runWorld } from "../../src/combat/world.js";
import { validateFormationFixture } from "../../src/formation-model.js";
import { TICKS_PER_SECOND } from "../../src/simulation-clock.js";
import { hashCanonicalJson } from "../../src/canonical-json.js";


export { hashCanonicalJson };


const formationUrl = new URL("../../fixtures/golden_formation_21v21.json", import.meta.url);
const sourceArchiveUrl = new URL(
  "../../calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip",
  import.meta.url,
);
const sourceOfTruthUrl = new URL("../../calibration/source/source_of_truth.json", import.meta.url);
const truthUrl = new URL("../../calibration/fixtures/champion_basics.json", import.meta.url);
const manifestUrl = new URL("../../calibration/fixtures/manifest.json", import.meta.url);
const mechanicsUrl = new URL("../../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url);

const AUTHORIZED_ARCHIVE = "aoe2_golden_basics_championvschampion_2026-08-04.zip";
const AUTHORIZED_SHA256 = "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE";
const AUTHORIZED_TRUTH_FIXTURE_SHA256 = "5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E";
const AUTHORIZED_MECHANICS_FIXTURE_SHA256 = "1A01DC2CF4C81907AD0B40104487221B5AAF97094A98A2A764D0605DEE4CC1D5";
const AUTHORIZED_DAT_SHA256 = "CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF";
const AUTHORIZED_REFERENCE_DB_SHA256 = "51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087";
const AUTHORIZED_RATIOS = Object.freeze({
  "1v1": 3,
  "2v1": 3,
  "2v3": 3,
  "5v3": 3,
  "6v3": 3,
});
const FIRST_MOVE_SAMPLING_NOTE = (
  "Simulation first move is one 60 Hz tick; tape first move is the first changed " +
  "10 Hz sample. Absolute positions, times, and directions are reported; displacement " +
  "vectors are not compared."
);

const archiveBytes = await readFile(sourceArchiveUrl);
if (createHash("sha256").update(archiveBytes).digest("hex").toUpperCase() !== AUTHORIZED_SHA256) {
  throw new Error("invalid clean-room source: project-local archive SHA-256 does not match");
}
const [sourceOfTruth, manifest, formationData, truthBytes, mechanicsBytes] = await Promise.all([
  readFile(sourceOfTruthUrl, "utf8").then(JSON.parse),
  readFile(manifestUrl, "utf8").then(JSON.parse),
  readFile(formationUrl, "utf8").then(JSON.parse),
  readFile(truthUrl),
  readFile(mechanicsUrl),
]);
const truth = JSON.parse(truthBytes.toString("utf8"));
const mechanics = JSON.parse(mechanicsBytes.toString("utf8"));
const sourceVerification = verifyCleanroomSource({
  archiveBytes,
  sourceOfTruth,
  truthBytes,
  truth,
  manifest,
  mechanicsBytes,
  mechanics,
});
const formation = validateFormationFixture(formationData);


function invalidSource(reason) {
  throw new Error(`invalid clean-room source: ${reason}`);
}


export function verifyCleanroomSource({
  archiveBytes: bytes,
  sourceOfTruth: lock,
  truthBytes: fixtureBytes,
  truth: fixture,
  manifest: index,
  mechanicsBytes: statsBytes,
  mechanics: stats,
} = {}) {
  if (!bytes) invalidSource("project-local archive is required");
  const archiveHash = createHash("sha256").update(bytes).digest("hex").toUpperCase();
  if (archiveHash !== AUTHORIZED_SHA256) invalidSource("archive SHA-256 does not match");
  if (!fixtureBytes) invalidSource("truth fixture bytes are required");
  const truthFixtureHash = createHash("sha256")
    .update(fixtureBytes)
    .digest("hex")
    .toUpperCase();
  if (truthFixtureHash !== AUTHORIZED_TRUTH_FIXTURE_SHA256) {
    invalidSource("truth fixture SHA-256 does not match");
  }
  if (!statsBytes) invalidSource("mechanics fixture bytes are required");
  const mechanicsFixtureHash = createHash("sha256")
    .update(statsBytes)
    .digest("hex")
    .toUpperCase();
  if (mechanicsFixtureHash !== AUTHORIZED_MECHANICS_FIXTURE_SHA256) {
    invalidSource("mechanics fixture SHA-256 does not match");
  }
  let decodedTruth;
  let decodedMechanics;
  try {
    decodedTruth = JSON.parse(fixtureBytes.toString("utf8"));
    decodedMechanics = JSON.parse(statsBytes.toString("utf8"));
  } catch {
    invalidSource("locked fixture bytes must decode as JSON");
  }
  if (JSON.stringify(decodedTruth) !== JSON.stringify(fixture)) {
    invalidSource("truth object does not match locked fixture bytes");
  }
  if (JSON.stringify(decodedMechanics) !== JSON.stringify(stats)) {
    invalidSource("mechanics object does not match locked fixture bytes");
  }
  if (
    lock?.archive !== AUTHORIZED_ARCHIVE ||
    lock?.sha256 !== AUTHORIZED_SHA256 ||
    lock?.recordings !== 15
  ) invalidSource("source_of_truth.json does not match the authorization lock");

  const ratioNames = Object.keys(lock.ratios ?? {}).sort();
  const authorizedRatioNames = Object.keys(AUTHORIZED_RATIOS).sort();
  if (
    ratioNames.length !== authorizedRatioNames.length ||
    ratioNames.some((ratio, index) => (
      ratio !== authorizedRatioNames[index] || lock.ratios[ratio] !== AUTHORIZED_RATIOS[ratio]
    ))
  ) invalidSource("source_of_truth.json ratio inventory does not match");
  if (fixture?.archive !== AUTHORIZED_ARCHIVE || fixture?.zip_sha256 !== AUTHORIZED_SHA256) {
    invalidSource("Champion fixture does not name the authorized archive");
  }
  if (index?.archive !== AUTHORIZED_ARCHIVE || index?.zip_sha256 !== AUTHORIZED_SHA256) {
    invalidSource("manifest does not name the authorized archive");
  }
  if (!Array.isArray(index.runs) || index.runs.length !== lock.recordings) {
    invalidSource("manifest entry count does not match source_of_truth.json");
  }
  if (index.runs.some(({ zip_sha256: hash }) => hash !== AUTHORIZED_SHA256)) {
    invalidSource("manifest entry SHA-256 does not match");
  }
  for (const [ratio, repeatCount] of Object.entries(AUTHORIZED_RATIOS)) {
    if (fixture.ratios?.[ratio]?.runs?.length !== repeatCount) {
      invalidSource(`Champion fixture ratio ${ratio} does not match the authorized inventory`);
    }
  }
  if (
    stats?.provenance?.dat_sha256 !== AUTHORIZED_DAT_SHA256
    || stats?.provenance?.reference_db_sha256 !== AUTHORIZED_REFERENCE_DB_SHA256
  ) {
    invalidSource("mechanics fixture raw-source hashes do not match");
  }

  return Object.freeze({
    archive: AUTHORIZED_ARCHIVE,
    zipSha256: AUTHORIZED_SHA256,
    recordings: lock.recordings,
    manifestEntries: index.runs.length,
    truthFixtureSha256: truthFixtureHash,
    mechanicsFixtureSha256: mechanicsFixtureHash,
    datSha256: AUTHORIZED_DAT_SHA256,
    referenceDbSha256: AUTHORIZED_REFERENCE_DB_SHA256,
  });
}


function round(value) {
  return Number(value.toFixed(6));
}


function difference(left, right) {
  return Number.isFinite(left) && Number.isFinite(right) ? round(left - right) : null;
}


export function compareSameAttackerIntervals(simulationRows, tapeRows) {
  const simulationById = new Map(simulationRows.map((row) => [row.id, row.seconds]));
  const tapeById = new Map(tapeRows.map((row) => [row.id, row.seconds]));
  const attackerIds = [...new Set([
    ...simulationById.keys(),
    ...tapeById.keys(),
  ])].sort((left, right) => left - right);
  return attackerIds.map((id) => {
    const simulation = simulationById.get(id) ?? [];
    const tape = tapeById.get(id) ?? [];
    const length = Math.max(simulation.length, tape.length);
    return {
      id,
      seconds: Array.from(
        { length },
        (_, index) => difference(simulation[index], tape[index]),
      ),
    };
  });
}


function movementDirection(dx, dy) {
  return { x: Math.sign(dx), y: Math.sign(dy) };
}


function simulationTrace(result, damageEvents) {
  const starts = result.snapshots[0].units.map((unit) => ({
    id: unit.referenceId,
    owner: unit.owner,
    master: unit.unitMaster,
    x: unit.x,
    y: unit.y,
  }));
  const firstMoveById = new Map();
  for (const event of result.events) {
    if (event.type === "move" && !firstMoveById.has(event.actorId)) {
      firstMoveById.set(event.actorId, event);
    }
  }
  const firstMoves = starts.map(({ id }) => {
    const move = firstMoveById.get(id);
    if (!move) return { id, tick: null, seconds: null, x: null, y: null };
    const unit = result.snapshots[move.tick].units.find(({ referenceId }) => referenceId === id);
    return {
      id,
      tick: move.tick,
      seconds: round(move.tick / TICKS_PER_SECOND),
      x: unit.x,
      y: unit.y,
    };
  });
  const movementDirections = starts.map(({ id }) => {
    const move = firstMoveById.get(id);
    return {
      id,
      ...(move ? movementDirection(move.dx, move.dy) : { x: null, y: null }),
    };
  });

  const contactEvent = result.events.find(({ type }) => type === "engagement-started");
  let surfaceContact = null;
  if (contactEvent) {
    const snapshot = result.snapshots[contactEvent.tick];
    const actor = snapshot.units.find(({ referenceId }) => referenceId === contactEvent.actorId);
    const target = snapshot.units.find(({ referenceId }) => referenceId === contactEvent.targetId);
    const centerDistance = Math.hypot(target.x - actor.x, target.y - actor.y);
    surfaceContact = {
      tick: contactEvent.tick,
      seconds: round(contactEvent.tick / TICKS_PER_SECOND),
      pair: [contactEvent.actorId, contactEvent.targetId].sort((left, right) => left - right),
      centerDistance,
      surfaceGap: centerDistance
        - actor.mechanics.collision_size_tiles.x
        - target.mechanics.collision_size_tiles.x,
    };
  }

  const firstDamageEvent = damageEvents[0];
  const firstDamage = firstDamageEvent ? {
    tick: firstDamageEvent.tick,
    seconds: round(firstDamageEvent.tick / TICKS_PER_SECOND),
    actorId: firstDamageEvent.actorId,
    targetId: firstDamageEvent.targetId,
    amount: firstDamageEvent.amount,
    hpAfter: firstDamageEvent.hpAfter,
  } : null;
  const attackerIds = [...new Set(damageEvents.map(({ actorId }) => actorId))]
    .sort((left, right) => left - right);
  const sameAttackerIntervals = attackerIds.map((id) => {
    const ticks = damageEvents
      .filter(({ actorId }) => actorId === id)
      .map(({ tick }) => tick);
    return {
      id,
      ticks: ticks.slice(1).map((tick, index) => tick - ticks[index]),
      seconds: ticks.slice(1).map((tick, index) => round(
        (tick - ticks[index]) / TICKS_PER_SECOND,
      )),
    };
  });
  const killEvent = damageEvents.find(({ hpAfter }) => hpAfter === 0);
  const kill = killEvent ? {
    tick: killEvent.tick,
    seconds: round(killEvent.tick / TICKS_PER_SECOND),
    actorId: killEvent.actorId,
    targetId: killEvent.targetId,
    amount: killEvent.amount,
  } : null;
  const ownerById = new Map(starts.map(({ id, owner }) => [id, owner]));
  const hitsPerOwner = {};
  for (const event of damageEvents) {
    const owner = ownerById.get(event.actorId);
    hitsPerOwner[owner] = (hitsPerOwner[owner] ?? 0) + 1;
  }
  return {
    starts,
    firstMoves,
    movementDirections,
    surfaceContact,
    firstDamage,
    sameAttackerIntervals,
    kill,
    hitsPerOwner,
    winnerHp: result.world.units
      .filter(({ owner, alive }) => owner === result.winner && alive)
      .reduce((total, unit) => total + unit.hp, 0),
  };
}


function tapeElapsedSeconds(run, timestamp) {
  return round(timestamp - (run.metadata?.fight_t_start ?? 0));
}


function tapeSurfaceContact(run) {
  const firstDamageTime = run.damage_events[0]?.t ?? Number.POSITIVE_INFINITY;
  const state = new Map(run.starting_units.map((unit) => [unit.id, unit]));
  const samplesByTime = new Map();
  for (const sample of run.unit_samples) {
    if (sample.t > firstDamageTime) break;
    if (!samplesByTime.has(sample.t)) samplesByTime.set(sample.t, []);
    samplesByTime.get(sample.t).push(sample);
  }

  let closest = null;
  const radius = mechanics.collision_size_tiles.x;
  for (const [timestamp, samples] of samplesByTime) {
    for (const sample of samples) state.set(sample.id, sample);
    const units = [...state.values()].sort((left, right) => left.id - right.id);
    for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
        const left = units[leftIndex];
        const right = units[rightIndex];
        if (left.owner === right.owner) continue;
        const centerDistance = Math.hypot(right.x - left.x, right.y - left.y);
        if (closest && centerDistance >= closest.centerDistance - 1e-12) continue;
        closest = {
          t: timestamp,
          elapsedSeconds: tapeElapsedSeconds(run, timestamp),
          pair: [left.id, right.id],
          centerDistance,
          surfaceGap: centerDistance - radius * 2,
        };
      }
    }
  }
  return closest;
}


function tapeTrace(run) {
  const starts = run.starting_units.map(({ id, owner, master, x, y }) => ({
    id, owner, master, x, y,
  }));
  const firstMoves = starts.map((start) => {
    const sample = run.unit_samples.find((row) => (
      row.id === start.id && (row.x !== start.x || row.y !== start.y)
    ));
    if (!sample) {
      return {
        id: start.id,
        t: null,
        elapsedSeconds: null,
        x: null,
        y: null,
      };
    }
    return {
      id: start.id,
      t: sample.t,
      elapsedSeconds: tapeElapsedSeconds(run, sample.t),
      x: sample.x,
      y: sample.y,
    };
  });
  const startsById = new Map(starts.map((row) => [row.id, row]));
  const movementDirections = firstMoves.map(({ id, x, y }) => {
    const start = startsById.get(id);
    return {
      id,
      ...(Number.isFinite(x) && Number.isFinite(y)
        ? movementDirection(x - start.x, y - start.y)
        : { x: null, y: null }),
    };
  });
  const firstDamageEvent = run.damage_events[0];
  const firstDamage = firstDamageEvent ? {
    t: firstDamageEvent.t,
    elapsedSeconds: tapeElapsedSeconds(run, firstDamageEvent.t),
    provisionalTick: Math.round(tapeElapsedSeconds(run, firstDamageEvent.t) * TICKS_PER_SECOND),
    actorId: firstDamageEvent.attacker,
    targetId: firstDamageEvent.victim,
    amount: firstDamageEvent.damage,
    hpAfter: firstDamageEvent.victim_hp_after,
  } : null;
  const attackerIds = [...new Set(run.damage_events.map(({ attacker }) => attacker))]
    .sort((left, right) => left - right);
  const sameAttackerIntervals = attackerIds.map((id) => {
    const times = run.damage_events
      .filter(({ attacker }) => attacker === id)
      .map(({ t }) => t);
    return {
      id,
      seconds: times.slice(1).map((timestamp, index) => round(timestamp - times[index])),
    };
  });
  const killEvent = run.damage_events.find(({ kill }) => kill);
  const kill = killEvent ? {
    t: killEvent.t,
    elapsedSeconds: tapeElapsedSeconds(run, killEvent.t),
    provisionalTick: Math.round(tapeElapsedSeconds(run, killEvent.t) * TICKS_PER_SECOND),
    actorId: killEvent.attacker,
    targetId: killEvent.victim,
    amount: killEvent.damage,
  } : null;
  const hitsPerOwner = {};
  for (const event of run.damage_events) {
    hitsPerOwner[event.attacker_owner] = (hitsPerOwner[event.attacker_owner] ?? 0) + 1;
  }
  return {
    starts,
    firstMoves,
    movementDirections,
    surfaceContact: tapeSurfaceContact(run),
    firstDamage,
    sameAttackerIntervals,
    kill,
    hitsPerOwner,
    winnerHp: run.aggregate_hp[run.winner].remaining,
  };
}


function compareTrace(simulation, tape) {
  const startsById = new Map(tape.starts.map((row) => [row.id, row]));
  const firstMovesById = new Map(tape.firstMoves.map((row) => [row.id, row]));
  const directionsById = new Map(tape.movementDirections.map((row) => [row.id, row]));
  return {
    starts: simulation.starts.map((row) => {
      const expected = startsById.get(row.id);
      return {
        id: row.id,
        owner: difference(row.owner, expected?.owner),
        master: difference(row.master, expected?.master),
        x: difference(row.x, expected?.x),
        y: difference(row.y, expected?.y),
      };
    }),
    firstMoves: simulation.firstMoves.map((row) => {
      const expected = firstMovesById.get(row.id);
      return {
        id: row.id,
        seconds: difference(row.seconds, expected?.elapsedSeconds),
      };
    }),
    movementDirections: simulation.movementDirections.map((row) => {
      const expected = directionsById.get(row.id);
      return {
        id: row.id,
        xMatches: expected ? row.x === expected.x : null,
        yMatches: expected ? row.y === expected.y : null,
      };
    }),
    surfaceContact: {
      seconds: difference(
        simulation.surfaceContact?.seconds,
        tape.surfaceContact?.elapsedSeconds,
      ),
      ticks: difference(
        simulation.surfaceContact?.tick,
        tape.surfaceContact
          ? Math.round(tape.surfaceContact.elapsedSeconds * TICKS_PER_SECOND)
          : null,
      ),
      centerDistance: difference(
        simulation.surfaceContact?.centerDistance,
        tape.surfaceContact?.centerDistance,
      ),
      surfaceGap: difference(
        simulation.surfaceContact?.surfaceGap,
        tape.surfaceContact?.surfaceGap,
      ),
    },
    firstDamage: {
      seconds: difference(simulation.firstDamage?.seconds, tape.firstDamage?.elapsedSeconds),
      ticks: difference(simulation.firstDamage?.tick, tape.firstDamage?.provisionalTick),
      actorMatches: tape.firstDamage
        ? simulation.firstDamage?.actorId === tape.firstDamage.actorId
        : null,
      targetMatches: tape.firstDamage
        ? simulation.firstDamage?.targetId === tape.firstDamage.targetId
        : null,
      amount: difference(simulation.firstDamage?.amount, tape.firstDamage?.amount),
      hpAfter: difference(simulation.firstDamage?.hpAfter, tape.firstDamage?.hpAfter),
    },
    sameAttackerIntervals: compareSameAttackerIntervals(
      simulation.sameAttackerIntervals,
      tape.sameAttackerIntervals,
    ),
    kill: {
      seconds: difference(simulation.kill?.seconds, tape.kill?.elapsedSeconds),
      ticks: difference(simulation.kill?.tick, tape.kill?.provisionalTick),
      actorMatches: tape.kill ? simulation.kill?.actorId === tape.kill.actorId : null,
      targetMatches: tape.kill ? simulation.kill?.targetId === tape.kill.targetId : null,
      amount: difference(simulation.kill?.amount, tape.kill?.amount),
    },
    hitsPerOwner: Object.fromEntries(
      [...new Set([
        ...Object.keys(simulation.hitsPerOwner),
        ...Object.keys(tape.hitsPerOwner),
      ])].sort().map((owner) => [
        owner,
        (simulation.hitsPerOwner[owner] ?? 0) - (tape.hitsPerOwner[owner] ?? 0),
      ]),
    ),
    winnerHp: difference(simulation.winnerHp, tape.winnerHp),
  };
}


export function runChampionRatio(ratio, { reverseUnits = false } = {}) {
  const scenario = createChampionScenario({ ratio, formation, truth, mechanics });
  const orderedScenario = reverseUnits
    ? { ...scenario, units: [...scenario.units].reverse() }
    : scenario;
  const result = runWorld(createWorld(orderedScenario));
  const livingUnits = result.world.units.filter(({ alive }) => alive);
  const deadUnits = result.world.units.filter(({ alive }) => !alive);
  const winnerHp = livingUnits.reduce((total, unit) => total + unit.hp, 0);
  const damageEvents = Object.freeze(result.events.filter(({ type }) => type === "damage"));
  const trace = simulationTrace(result, damageEvents);
  const tapeComparisons = truth.ratios[ratio].runs.map((run) => {
    const tape = tapeTrace(run);
    return {
      tag: run.tag,
      simulation: trace,
      tape,
      deltas: compareTrace(trace, tape),
    };
  });
  const finalState = {
    tick: result.world.tick,
    ratio: result.world.ratio,
    mapHash: result.world.mapHash,
    units: result.world.units,
  };

  return Object.freeze({
    ...result,
    damageEvents,
    diagnostics: Object.freeze({
      source: sourceVerification,
      firstMoveSamplingNote: FIRST_MOVE_SAMPLING_NOTE,
      tapeComparisons: Object.freeze(tapeComparisons),
    }),
    eventLogHash: hashCanonicalJson(result.events),
    finalStateHash: hashCanonicalJson(finalState),
    livingUnits: Object.freeze(livingUnits),
    winnerOwner: result.winner,
    winnerHp,
    winner: livingUnits[0],
    loser: deadUnits[0],
  });
}
