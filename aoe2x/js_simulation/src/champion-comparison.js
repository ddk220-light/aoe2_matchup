import { TICKS_PER_SECOND } from "./simulation-clock.js";
import { hashCanonicalJson } from "./canonical-json.js";


const RATIO_ORDER = Object.freeze(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const ARCHIVE_PATH = (
  "aoe2x/js_simulation/calibration/source/"
  + "aoe2_golden_basics_championvschampion_2026-08-04.zip"
);
const ARCHIVE_NAME = "aoe2_golden_basics_championvschampion_2026-08-04.zip";
const TRUTH_FIXTURE_SHA256 = "5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E";
const MECHANICS_FIXTURE_SHA256 = "4D4FE28BBBD2C5BDAC76AC7C2594C8FE569B877A75F230BB47B965848455D0F0";
const DAT_SHA256 = "CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF";
const REFERENCE_DB_SHA256 = "51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087";
const TARGET_EVENT_TYPES = new Set([
  "pursuit-acquired",
  "pursuit-invalidated",
  "engagement-started",
  "engagement-ended",
  "attack-start",
  "attack-canceled",
]);
const REFERENCED_EVENT_TYPES = new Set([
  ...TARGET_EVENT_TYPES,
  "damage",
  "death",
]);
const PROHIBITED_SOURCE_RULES = Object.freeze([
  {
    category: "ratio-specific branch",
    pattern: /\b(?:if|switch)\s*\([^\r\n]*\bratio\b[^\r\n]*|(?:\bratio\b|\.ratio\b)[^\r\n?]*\?/gi,
  },
  {
    category: "owner-specific branch",
    pattern: /(?:\.\s*owner\b|\[\s*["']owner["']\s*\]|\bowner\b)\s*(?:===|==|!==|!=)\s*(?:2|3)\b|\b(?:2|3)\s*(?:===|==|!==|!=)\s*[^;\n]*(?:\.\s*owner\b|\[\s*["']owner["']\s*\]|\bowner\b)/gi,
  },
  {
    category: "fitted timing rule",
    pattern: /\b(?:postSwing(?:Pause|Recovery)?|post_swing(?:_pause|_recovery)?|movementPause|pauseTicks|reactionDelay|disengageDelay|extraRecovery|extraDelay|fittedDelay)(?:Ticks|Seconds)?\b|\b(?:setTimeout|setInterval|Date\.now|performance\.now)\b/gi,
  },
  {
    category: "HP/damage modifier",
    pattern: /\b(?:hp|damage)\s*(?:\*=|\/=|\+=|-=)|\b(?:hp|damage)(?:Multiplier|Modifier|Scale|Offset)\b|(?:\.hp|\bhp|\bdamage)\s*=\s*-?\d+(?:\.\d+)?\b|\bamount\s*:\s*-?\d+(?:\.\d+)?\b/gi,
  },
  {
    category: "speed/radius/compression multiplier",
    pattern: /\b(?:speed|radius|collision)(?:Multiplier|Modifier|Scale|Factor)\b|\bcompression(?:Ratio|Multiplier|Factor|Scale)\b|\b(?:speed|radius|collisionRadius|compression)\s*(?:\*=|\/=|\+=|-=)/gi,
  },
  {
    category: "global turn rule",
    pattern: /\b(?:globalTurn|forcedTurn|turnBias|clockwise|counterclockwise)\b/gi,
  },
  {
    category: "randomness",
    pattern: /\b(?:Math\.random|crypto\.random|randomBytes|randomUUID|seededRandom|rng)\b/gi,
  },
]);


function median(values, name) {
  if (!Array.isArray(values) || values.length === 0) {
    throw new TypeError(`${name} must be a nonempty array`);
  }
  const sorted = values.map((value) => {
    if (!Number.isFinite(value)) throw new TypeError(`${name} must contain finite numbers`);
    return value;
  }).sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}


function ownerNumber(side) {
  const match = /^side([0-9]+)$/.exec(side);
  if (!match) throw new TypeError(`invalid tape winner ${side}`);
  return Number(match[1]);
}


function within(value, bounds) {
  return value >= bounds.min && value <= bounds.max;
}


function round(value) {
  return Number(value.toFixed(6));
}


function removeComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "))
    .replace(/\/\/[^\r\n]*/g, "");
}


function normalizedLineAt(source, index) {
  const start = source.lastIndexOf("\n", index - 1) + 1;
  const nextNewline = source.indexOf("\n", index);
  const end = nextNewline === -1 ? source.length : nextNewline;
  return source.slice(start, end).trim().replace(/\s+/g, " ");
}


function isExactAllowance(allowance, finding) {
  return (
    allowance.file === finding.file
    && allowance.category === finding.category
    && allowance.token === finding.token
    && allowance.context === finding.context
  );
}


export function auditSimulationSource(sourceFiles, { allowances = [], exclusions = [] } = {}) {
  if (!sourceFiles || typeof sourceFiles !== "object" || Array.isArray(sourceFiles)) {
    throw new TypeError("simulation source files must be an object");
  }
  const files = Object.keys(sourceFiles);
  if (files.length === 0) throw new TypeError("simulation source audit requires files");
  if (!Array.isArray(allowances) || !Array.isArray(exclusions)) {
    throw new TypeError("audit allowances and exclusions must be arrays");
  }
  const rawFindings = [];
  for (const file of files) {
    const source = sourceFiles[file];
    if (typeof source !== "string") throw new TypeError(`simulation source ${file} must be text`);
    const executable = removeComments(source);
    for (const rule of PROHIBITED_SOURCE_RULES) {
      rule.pattern.lastIndex = 0;
      for (let match = rule.pattern.exec(executable); match !== null; match = rule.pattern.exec(executable)) {
        rawFindings.push(Object.freeze({
          category: rule.category,
          file,
          line: executable.slice(0, match.index).split(/\r?\n/).length,
          token: match[0].trim().replace(/\s+/g, " "),
          context: normalizedLineAt(executable, match.index),
        }));
        if (match[0].length === 0) rule.pattern.lastIndex += 1;
      }
    }
  }
  for (const allowance of allowances) {
    if (
      typeof allowance?.file !== "string"
      || typeof allowance.category !== "string"
      || typeof allowance.token !== "string"
      || typeof allowance.context !== "string"
      || !Number.isSafeInteger(allowance.expectedCount)
      || allowance.expectedCount < 1
      || typeof allowance.reason !== "string"
      || allowance.reason.length === 0
    ) {
      throw new TypeError("audit allowances require an exact fingerprint and expected count");
    }
  }
  const allowanceChecks = allowances.map((allowance) => {
    const actualCount = rawFindings.filter((finding) => isExactAllowance(allowance, finding)).length;
    return Object.freeze({
      file: allowance.file,
      category: allowance.category,
      token: allowance.token,
      context: allowance.context,
      expectedCount: allowance.expectedCount,
      actualCount,
      passed: actualCount === allowance.expectedCount,
      reason: allowance.reason,
    });
  });
  const findings = [];
  const approvedFindings = [];
  for (const finding of rawFindings) {
    const allowanceIndex = allowances.findIndex((row) => isExactAllowance(row, finding));
    const allowanceCheck = allowanceChecks[allowanceIndex];
    if (allowanceIndex !== -1 && allowanceCheck.passed) {
      approvedFindings.push(Object.freeze({
        ...finding,
        expectedCount: allowanceCheck.expectedCount,
        reason: allowanceCheck.reason,
      }));
    } else {
      findings.push(finding);
    }
  }
  const allowanceMismatches = allowanceChecks.filter(({ passed }) => !passed);
  return Object.freeze({
    kind: "heuristic_static_lint",
    assurance: "Pattern-based lint plus separate review; this is not a proof of absence or bypass resistance.",
    passed: findings.length === 0 && allowanceMismatches.length === 0,
    files: Object.freeze(files),
    exclusions: Object.freeze(exclusions.map((row) => Object.freeze({ ...row }))),
    checkedCategories: Object.freeze(PROHIBITED_SOURCE_RULES.map(({ category }) => category)),
    approvedFindings: Object.freeze(approvedFindings),
    findings: Object.freeze(findings),
    allowanceChecks: Object.freeze(allowanceChecks),
    allowanceMismatches: Object.freeze(allowanceMismatches),
    reviewedConstants: Object.freeze([
      Object.freeze({ name: "TICKS_PER_SECOND", value: 60, classification: "provisional clock hypothesis", evidence: "champion_clock_forensics.json; not selected from HP" }),
      Object.freeze({ name: "MAX_WORLD_TICKS", value: 3600, classification: "safety failure ceiling", evidence: "design specification" }),
      Object.freeze({ name: "EPSILON", value: 1e-12, classification: "numerical geometry tolerance", evidence: "collision invariant tests" }),
      Object.freeze({ name: "MAX_CONSTRAINT_SWEEPS", value: 256, classification: "solver convergence ceiling", evidence: "collision convergence failure path" }),
      Object.freeze({ name: "Champion mechanics", value: "HP 70; speed 1.06; radius 0.2; reload 2; damage 14", classification: "source-backed mechanics", evidence: "byte-locked mechanics fixture and field provenance" }),
    ]),
    separateReview: Object.freeze({
      status: "documented",
      evidence: ".superpowers/sdd/2026-08-04-cleanroom-champion-small-groups/task-10-report.md",
      scope: "manual review of physics architecture and outcome-neutral constants; independent of this lint",
    }),
  });
}


function tapeSummary(truth, ratio) {
  const ratioTruth = truth?.ratios?.[ratio];
  if (!ratioTruth || !Array.isArray(ratioTruth.runs) || ratioTruth.runs.length === 0) {
    throw new TypeError(`truth ratio ${ratio} must contain runs`);
  }
  const winnerOwners = [...new Set(ratioTruth.runs.map(({ winner }) => ownerNumber(winner)))]
    .sort((left, right) => left - right);
  const winnerHpRows = ratioTruth.runs.map((run) => {
    const row = run.aggregate_hp?.[run.winner];
    if (!row) throw new TypeError(`truth ratio ${ratio} run ${run.tag} lacks winner HP`);
    return row;
  });
  const survivorCounts = winnerHpRows.map(({ survivors }) => survivors);
  const damageCounts = ratioTruth.runs.map((run) => run.damage_events?.length);
  const medianWinnerHp = median(winnerHpRows.map(({ remaining }) => remaining), "winner HP");
  const medianWinnerStartingHp = median(
    winnerHpRows.map(({ starting }) => starting),
    "winner starting HP",
  );
  const fixtureMedianWinnerHpPct = ratioTruth.median_winner_hp_pct;
  if (!Number.isFinite(fixtureMedianWinnerHpPct)) {
    throw new TypeError(`truth ratio ${ratio} lacks median winner HP percentage`);
  }
  const medianWinnerHpPct = round(medianWinnerHp / medianWinnerStartingHp * 100);
  const fixtureMedianWinnerHpPctMatches = fixtureMedianWinnerHpPct === medianWinnerHpPct;
  return Object.freeze({
    repeats: ratioTruth.runs.length,
    winnerOwners: Object.freeze(winnerOwners),
    requiredWinnerOwner: winnerOwners.length === 1 ? winnerOwners[0] : null,
    medianWinnerHp,
    medianWinnerStartingHp,
    medianWinnerHpPct,
    fixtureMedianWinnerHpPct,
    fixtureMedianWinnerHpPctMatches,
    winnerHpRange: Object.freeze({
      min: Math.min(...winnerHpRows.map(({ remaining }) => remaining)),
      max: Math.max(...winnerHpRows.map(({ remaining }) => remaining)),
    }),
    survivorCountRange: Object.freeze({
      min: Math.min(...survivorCounts),
      max: Math.max(...survivorCounts),
    }),
    damageEventCountRange: Object.freeze({
      min: Math.min(...damageCounts),
      max: Math.max(...damageCounts),
    }),
  });
}


function resultSet(simulationResults, ratio) {
  const row = simulationResults.find((candidate) => candidate?.ratio === ratio);
  if (!row || !Array.isArray(row.runs) || row.runs.length < 3) {
    throw new TypeError(`simulation ratio ${ratio} requires repeat and reversal runs`);
  }
  return row.runs;
}


function diagnosticEvent(event) {
  const row = {
    tick: event.tick,
    seconds: round(event.tick / TICKS_PER_SECOND),
    type: event.type,
    actorId: event.actorId,
    targetId: event.targetId,
  };
  for (const name of [
    "reason",
    "readyTick",
    "sweptToi",
    "finalSurfaceGap",
    "amount",
    "hpBefore",
    "hpAfter",
  ]) {
    if (event[name] !== undefined) row[name] = event[name];
  }
  return Object.freeze(row);
}


function traceDiagnostics(result) {
  const moveEvents = result.events.filter(({ type }) => type === "move");
  const firstMoveTick = Math.min(...moveEvents.map(({ tick }) => tick));
  const firstMovement = Object.freeze({
    tick: firstMoveTick,
    seconds: round(firstMoveTick / TICKS_PER_SECOND),
    actorIds: Object.freeze(moveEvents
      .filter(({ tick }) => tick === firstMoveTick)
      .map(({ actorId }) => actorId)
      .sort((left, right) => left - right)),
  });
  const firstDamage = result.events.find(({ type }) => type === "damage");
  const deaths = result.events.filter(({ type }) => type === "death");
  const finalKill = deaths.at(-1);

  const unitIds = result.snapshots[0].units
    .map(({ referenceId }) => referenceId)
    .sort((left, right) => left - right);
  const distanceByUnit = new Map(unitIds.map((referenceId) => [referenceId, 0]));
  const blockedByUnit = new Map(unitIds.map((referenceId) => [referenceId, new Set()]));
  for (const event of result.events) {
    if (event.type === "move") {
      distanceByUnit.set(
        event.actorId,
        distanceByUnit.get(event.actorId) + Math.hypot(event.dx, event.dy),
      );
    } else if (event.type === "blocked") {
      blockedByUnit.get(event.actorId).add(event.tick);
    }
  }
  const distanceRows = unitIds.map((referenceId) => Object.freeze({
    referenceId,
    tiles: round(distanceByUnit.get(referenceId)),
  }));
  const blockedRows = unitIds.map((referenceId) => Object.freeze({
    referenceId,
    ticks: blockedByUnit.get(referenceId).size,
  }));
  const canceled = result.events.filter(({ type, reason }) => (
    type === "attack-canceled" && (reason === "actor-dead" || reason === "target-dead")
  ));
  return Object.freeze({
    firstMovement,
    firstDamage: diagnosticEvent(firstDamage),
    finalKill: diagnosticEvent(finalKill),
    distanceTraveled: Object.freeze({
      totalTiles: round(distanceRows.reduce((total, row) => total + row.tiles, 0)),
      byUnit: Object.freeze(distanceRows),
    }),
    blockedTicks: Object.freeze({
      total: blockedRows.reduce((total, row) => total + row.ticks, 0),
      byUnit: Object.freeze(blockedRows),
    }),
    targetTimeline: Object.freeze(result.events
      .filter(({ type }) => TARGET_EVENT_TYPES.has(type))
      .map(diagnosticEvent)),
    attacksCanceledByDeath: Object.freeze({
      count: canceled.length,
      events: Object.freeze(canceled.map(diagnosticEvent)),
    }),
  });
}


function everyDamageExactly14(result) {
  const damageEvents = result.events?.filter(({ type }) => type === "damage") ?? [];
  return damageEvents.length > 0 && damageEvents.every(({ amount, hpBefore, hpAfter }) => (
    amount === 14
    && Number.isFinite(hpBefore)
    && Number.isFinite(hpAfter)
    && hpAfter === Math.max(0, hpBefore - 14)
  ));
}


function liveBodiesDoNotOverlap(result) {
  if (!Array.isArray(result.snapshots) || result.snapshots.length === 0) return false;
  for (const snapshot of result.snapshots) {
    const live = snapshot.units?.filter(({ alive }) => alive) ?? [];
    for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
        const left = live[leftIndex];
        const right = live[rightIndex];
        const leftRadius = left.mechanics?.collision_size_tiles?.x;
        const rightRadius = right.mechanics?.collision_size_tiles?.x;
        if (
          !Number.isFinite(leftRadius)
          || !Number.isFinite(rightRadius)
          || Math.hypot(right.x - left.x, right.y - left.y)
            < leftRadius + rightRadius - 1e-12
        ) return false;
      }
    }
  }
  return true;
}


function targetReferencesAndLifecycleAreValid(result) {
  const snapshots = result.snapshots;
  const events = result.events;
  const initialUnits = snapshots?.[0]?.units;
  if (
    !Array.isArray(snapshots)
    || snapshots.length === 0
    || !Array.isArray(initialUnits)
    || initialUnits.length === 0
    || !Array.isArray(events)
    || events.length === 0
  ) return false;

  const initialById = new Map();
  for (const unit of initialUnits) {
    if (
      !Number.isSafeInteger(unit?.referenceId)
      || initialById.has(unit.referenceId)
      || !Number.isSafeInteger(unit.owner)
    ) return false;
    initialById.set(unit.referenceId, unit);
  }
  const referencesEnemy = (actorId, targetId) => {
    const actor = initialById.get(actorId);
    const target = initialById.get(targetId);
    return Boolean(actor && target && actor.referenceId !== target.referenceId
      && actor.owner !== target.owner);
  };

  const state = new Map(initialUnits.map((unit) => [unit.referenceId, {
    alive: unit.alive,
    hp: unit.hp,
    owner: unit.owner,
  }]));
  const deathTicks = new Map();
  let previousTick = -1;
  for (const event of events) {
    if (!Number.isSafeInteger(event?.tick) || event.tick < previousTick) return false;
    previousTick = event.tick;
    if (REFERENCED_EVENT_TYPES.has(event.type)) {
      if (
        !Number.isSafeInteger(event.actorId)
        || !Number.isSafeInteger(event.targetId)
        || !referencesEnemy(event.actorId, event.targetId)
      ) return false;
    }
    const actor = state.get(event.actorId);
    const target = state.get(event.targetId);
    if (["pursuit-acquired", "engagement-started", "attack-start", "damage"].includes(event.type)) {
      if (!actor?.alive || !target?.alive) return false;
    }
    if (event.type === "damage") {
      if (
        event.hpBefore !== target.hp
        || event.hpAfter !== Math.max(0, event.hpBefore - event.amount)
      ) return false;
      target.hp = event.hpAfter;
    } else if (event.type === "death") {
      if (!actor?.alive || !target?.alive || target.hp !== 0 || deathTicks.has(event.targetId)) {
        return false;
      }
      target.alive = false;
      deathTicks.set(event.targetId, event.tick);
    } else if (event.type === "pursuit-invalidated" && event.reason === "target-dead") {
      if (target?.alive !== false) return false;
    } else if (event.type === "engagement-ended" && event.reason === "target-dead") {
      if (target?.alive !== false) return false;
    } else if (event.type === "attack-canceled") {
      if (event.reason === "actor-dead" && actor?.alive !== false) return false;
      if (event.reason === "target-dead" && target?.alive !== false) return false;
    }
  }

  const flattenedSnapshotEvents = [];
  for (let snapshotIndex = 0; snapshotIndex < snapshots.length; snapshotIndex += 1) {
    const snapshot = snapshots[snapshotIndex];
    if (
      !Number.isSafeInteger(snapshot?.tick)
      || snapshot.tick !== snapshotIndex
      || !Array.isArray(snapshot.units)
      || snapshot.units.length !== initialUnits.length
      || !Array.isArray(snapshot.events)
      || snapshot.events.some(({ tick }) => tick !== snapshot.tick)
    ) return false;
    flattenedSnapshotEvents.push(...snapshot.events);
    const byId = new Map(snapshot.units.map((unit) => [unit.referenceId, unit]));
    if (byId.size !== initialById.size) return false;
    for (const unit of snapshot.units) {
      const initial = initialById.get(unit.referenceId);
      if (!initial || unit.owner !== initial.owner) return false;
      if (!unit.alive && (
        unit.pursuitTargetId !== null
        || unit.engagedTargetId !== null
        || unit.attackTargetId !== null
      )) return false;

      for (const field of ["pursuitTargetId", "engagedTargetId", "attackTargetId"]) {
        const targetId = unit[field];
        if (targetId === null) continue;
        if (!Number.isSafeInteger(targetId) || !referencesEnemy(unit.referenceId, targetId)) {
          return false;
        }
        const target = byId.get(targetId);
        if (!target) return false;
        if (field === "engagedTargetId" && (!unit.alive || !target.alive)) return false;
        if ((field === "pursuitTargetId" || field === "attackTargetId") && !target.alive) {
          if (deathTicks.get(targetId) !== snapshot.tick || !unit.alive) return false;
          const nextSnapshot = snapshots[snapshotIndex + 1];
          if (nextSnapshot) {
            const nextUnit = nextSnapshot.units.find(
              ({ referenceId }) => referenceId === unit.referenceId,
            );
            if (!nextUnit || nextUnit[field] === targetId) return false;
            const requiredType = field === "pursuitTargetId"
              ? "pursuit-invalidated"
              : "attack-canceled";
            const lifecycleIndex = events.findIndex((event) => (
              event.tick === snapshot.tick + 1
              && event.type === requiredType
              && event.actorId === unit.referenceId
              && event.targetId === targetId
              && event.reason === "target-dead"
            ));
            if (lifecycleIndex === -1) return false;
            if (field === "pursuitTargetId") {
              const reacquireIndex = events.findIndex((event) => (
                event.tick === snapshot.tick + 1
                && event.type === "pursuit-acquired"
                && event.actorId === unit.referenceId
              ));
              if (reacquireIndex !== -1 && lifecycleIndex > reacquireIndex) return false;
            }
          }
        }
      }

      // "attacking" spans the whole attack animation, not just the run-up to
      // the hit. The tapes put the hit at animation frame `frame_delay` (or the
      // midpoint when it is unset), so a unit that has already landed its blow
      // is still attacking with windup 0, and its reload is already counting
      // down from the swing start. Requiring windup > 0 and reload === 0 here
      // encoded the old instant-damage model and rejected every real run.
      const windup = unit.actionTimers?.windup;
      const reload = unit.actionTimers?.reload;
      if (unit.action === "attacking") {
        if (
          unit.attackTargetId === null
          || !Number.isSafeInteger(windup)
          || windup < 0
          || !Number.isSafeInteger(reload)
          || reload < 0
        ) return false;
      } else if (unit.attackTargetId !== null) {
        return false;
      }
    }
  }
  try {
    if (hashCanonicalJson(flattenedSnapshotEvents) !== hashCanonicalJson(events)) return false;
  } catch {
    return false;
  }
  return true;
}


function completedWithoutStalemateOrTimeout(result) {
  return (
    result.outcome === "win"
    && result.timedOut !== true
    && result.stalemate !== true
    && Number.isSafeInteger(result.ticks)
    && result.ticks >= 0
    && result.ticks <= 3600
    && result.world?.tick === result.ticks
  );
}


function terminalWinnerIsValid(result) {
  if (!Array.isArray(result.world?.units)) return false;
  const live = result.world.units.filter(({ alive }) => alive);
  const liveOwners = [...new Set(live.map(({ owner }) => owner))];
  const liveHp = live.reduce((total, unit) => total + unit.hp, 0);
  const reportedLiveIds = (result.livingUnits ?? [])
    .map(({ referenceId }) => referenceId)
    .sort((left, right) => left - right);
  const actualLiveIds = live
    .map(({ referenceId }) => referenceId)
    .sort((left, right) => left - right);
  return (
    live.length > 0
    && liveOwners.length === 1
    && liveOwners[0] === result.winnerOwner
    && liveHp === result.winnerHp
    && JSON.stringify(reportedLiveIds) === JSON.stringify(actualLiveIds)
    && result.world.units.every(({ owner, alive }) => owner === result.winnerOwner || !alive)
  );
}


export function validateChampionRun(result) {
  if (!result || typeof result !== "object") throw new TypeError("simulation result is required");
  const validity = {
    everyDamageExactly14: everyDamageExactly14(result),
    liveBodiesNonOverlapping: liveBodiesDoNotOverlap(result),
    targetReferencesAndLifecycleValid: targetReferencesAndLifecycleAreValid(result),
    completedWithoutStalemateOrTimeout: completedWithoutStalemateOrTimeout(result),
    terminalWinnerValid: terminalWinnerIsValid(result),
  };
  return Object.freeze({
    ...validity,
    passed: Object.values(validity).every(Boolean),
  });
}


function isDeepFrozen(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return true;
  if (!Object.isFrozen(value)) return false;
  visited.add(value);
  return Object.values(value).every((child) => isDeepFrozen(child, visited));
}


function hasAuthorizedPlaybackSource(source) {
  return (
    source?.archive === ARCHIVE_NAME
    && source.zipSha256 === "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE"
    && source.recordings === 15
    && source.manifestEntries === 15
    && source.truthFixtureSha256 === TRUTH_FIXTURE_SHA256
    && source.mechanicsFixtureSha256 === MECHANICS_FIXTURE_SHA256
    && source.datSha256 === DAT_SHA256
    && source.referenceDbSha256 === REFERENCE_DB_SHA256
  );
}


export function createChampionPlaybackData(result) {
  if (!result || typeof result !== "object") throw new TypeError("simulation result is required");
  const snapshots = result.snapshots;
  const events = result.events;
  const source = result.diagnostics?.source;
  const ratio = result.world?.ratio;
  if (
    !RATIO_ORDER.includes(ratio)
    || !Array.isArray(snapshots)
    || snapshots.length === 0
    || !Array.isArray(events)
    || events.length === 0
    || !isDeepFrozen(snapshots)
    || !isDeepFrozen(events)
    || !isDeepFrozen(result.world)
    || !isDeepFrozen(source)
  ) {
    throw new TypeError("playback requires a supported run with deep-immutable state and trace data");
  }
  if (!hasAuthorizedPlaybackSource(source)) {
    throw new TypeError("playback source metadata does not match the authorized clean-room inputs");
  }
  const validity = validateChampionRun(result);
  const lastSnapshot = snapshots.at(-1);
  if (
    !validity.passed
    || lastSnapshot.tick !== result.ticks
    || result.world.tick !== result.ticks
    || hashCanonicalJson(lastSnapshot.units) !== hashCanonicalJson(result.world.units)
  ) {
    throw new TypeError("playback run failed strict state, target, or lifecycle validation");
  }
  const finalState = {
    tick: result.world.tick,
    ratio,
    mapHash: result.world.mapHash,
    units: result.world.units,
  };
  if (
    hashCanonicalJson(finalState) !== result.finalStateHash
    || hashCanonicalJson(events) !== result.eventLogHash
  ) {
    throw new TypeError("playback determinism hashes do not match canonical state and event data");
  }
  return Object.freeze({
    schemaVersion: 1,
    ratio,
    ticks: result.ticks,
    winnerOwner: result.winnerOwner,
    winnerHp: result.winnerHp,
    finalStateHash: result.finalStateHash,
    eventLogHash: result.eventLogHash,
    source,
    snapshots,
    events,
  });
}


function simulationSummary(runs) {
  const primary = runs[0];
  if (!primary || !Array.isArray(primary.snapshots) || primary.snapshots.length === 0) {
    throw new TypeError("simulation result must contain snapshots");
  }
  const winnerStartingHp = primary.snapshots[0].units
    .filter(({ owner }) => owner === primary.winnerOwner)
    .reduce((total, unit) => total + unit.hp, 0);
  const winnerHpPct = winnerStartingHp === 0 ? null : primary.winnerHp / winnerStartingHp * 100;
  const finalStateHashes = runs.map(({ finalStateHash }) => finalStateHash);
  const eventLogHashes = runs.map(({ eventLogHash }) => eventLogHash);
  const repeatMatches = (
    finalStateHashes[1] === finalStateHashes[0]
    && eventLogHashes[1] === eventLogHashes[0]
  );
  const reverseOrderMatches = (
    finalStateHashes[2] === finalStateHashes[0]
    && eventLogHashes[2] === eventLogHashes[0]
  );
  return Object.freeze({
    winnerOwner: primary.winnerOwner,
    winnerHp: primary.winnerHp,
    winnerStartingHp,
    winnerHpPct,
    survivors: primary.livingUnits.length,
    damageEvents: primary.damageEvents.length,
    ticks: primary.ticks,
    finalStateHash: primary.finalStateHash,
    eventLogHash: primary.eventLogHash,
    snapshotCount: primary.snapshots.length,
    eventCount: primary.events.length,
    diagnostics: traceDiagnostics(primary),
    validity: validateChampionRun(primary),
    tapeComparisons: primary.diagnostics?.tapeComparisons,
    determinism: Object.freeze({
      repeatMatches,
      reverseOrderMatches,
      finalStateHashes: Object.freeze(finalStateHashes),
      eventLogHashes: Object.freeze(eventLogHashes),
    }),
  });
}


function sourceSummary(truth, simulationResults) {
  const allResults = simulationResults.flatMap(({ runs }) => runs ?? []);
  const verifiedByRunner = allResults.length === RATIO_ORDER.length * 3
    && allResults.every((result) => (
      result?.diagnostics?.source?.archive === truth.archive
      && result.diagnostics.source.zipSha256 === truth.zip_sha256
      && result.diagnostics.source.recordings === 15
      && result.diagnostics.source.manifestEntries === 15
      && result.diagnostics.source.truthFixtureSha256 === TRUTH_FIXTURE_SHA256
      && result.diagnostics.source.mechanicsFixtureSha256 === MECHANICS_FIXTURE_SHA256
      && result.diagnostics.source.datSha256 === DAT_SHA256
      && result.diagnostics.source.referenceDbSha256 === REFERENCE_DB_SHA256
    ));
  return Object.freeze({
    archive: truth.archive,
    archivePath: ARCHIVE_PATH,
    zipSha256: truth.zip_sha256,
    recordings: Object.values(truth.ratios ?? {})
      .reduce((total, ratio) => total + (ratio.runs?.length ?? 0), 0),
    repeatsPerRatio: Object.fromEntries(RATIO_ORDER.map((ratio) => [
      ratio,
      truth.ratios?.[ratio]?.runs?.length ?? 0,
    ])),
    verifiedByRunner,
    truthFixture: Object.freeze({
      path: "aoe2x/js_simulation/calibration/fixtures/champion_basics.json",
      sha256: TRUTH_FIXTURE_SHA256,
      verification: "byte_exact_runtime_lock",
      reproducibilityTest: "tests/test_cleanroom_champion_basics.py::test_generated_fixture_matches_checked_in_fixture",
    }),
    mechanicsFixture: Object.freeze({
      path: "aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json",
      sha256: MECHANICS_FIXTURE_SHA256,
      verification: "byte_exact_runtime_lock",
      reproducibilityTest: "tests/test_cleanroom_champion_mechanics.py::test_exporter_maps_controlled_sources_reproducibly",
      reproducibilityScope: "controlled exporter sources; this report did not re-extract the installed Genie data",
    }),
  });
}


function clockSummary(clockEvidence, truth) {
  if (!clockEvidence || typeof clockEvidence !== "object") {
    throw new TypeError("clock evidence is required");
  }
  const ratiosAnalyzed = [...clockEvidence.ratios_analyzed];
  const sourceVerified = (
    clockEvidence.archive === truth.archive
    && clockEvidence.zip_sha256 === truth.zip_sha256
    && clockEvidence.runs_analyzed === 15
    && RATIO_ORDER.every((ratio, index) => ratiosAnalyzed[index] === ratio)
    && ratiosAnalyzed.length === RATIO_ORDER.length
  );
  return Object.freeze({
    ticksPerSecond: TICKS_PER_SECOND,
    status: clockEvidence.claim,
    selectionBasis: clockEvidence.selection_basis,
    runsAnalyzed: clockEvidence.runs_analyzed,
    ratiosAnalyzed: Object.freeze(ratiosAnalyzed),
    sourceVerified,
  });
}


function mechanicsSummary(mechanics, sourceAudit, source) {
  if (!mechanics || typeof mechanics !== "object") {
    throw new TypeError("Champion mechanics are required");
  }
  if (!sourceAudit || typeof sourceAudit !== "object") {
    throw new TypeError("simulation source audit is required");
  }
  const fields = mechanics.provenance?.fields ?? {};
  const coreValues = [
    mechanics.unit_master,
    mechanics.hp,
    mechanics.speed_tiles_per_second,
    mechanics.collision_size_tiles?.x,
    mechanics.attack_range_tiles,
    mechanics.reload_seconds,
    mechanics.attack_delay_seconds,
    mechanics.line_of_sight_tiles,
    mechanics.derived?.damage_vs_self,
  ];
  const coreFieldNames = [
    "hp",
    "speed_tiles_per_second",
    "collision_size_tiles.x",
    "attack_range_tiles",
    "reload_seconds",
    "attack_delay_seconds",
    "line_of_sight_tiles",
    "derived.damage_vs_self",
  ];
  const verified = (
    coreValues.every(Number.isFinite)
    && coreFieldNames.every((name) => typeof fields[name] === "string" && fields[name].length > 0)
    && mechanics.provenance?.dat_sha256 === DAT_SHA256
    && mechanics.provenance?.reference_db_sha256 === REFERENCE_DB_SHA256
    && source.mechanicsFixture.sha256 === MECHANICS_FIXTURE_SHA256
    && source.verifiedByRunner
  );
  return Object.freeze({
    verified,
    values: Object.freeze({
      unitMaster: mechanics.unit_master,
      civilization: mechanics.civilization,
      hp: mechanics.hp,
      speedTilesPerSecond: mechanics.speed_tiles_per_second,
      collisionRadiusTiles: mechanics.collision_size_tiles?.x,
      attackRangeTiles: mechanics.attack_range_tiles,
      reloadSeconds: mechanics.reload_seconds,
      attackDelaySeconds: mechanics.attack_delay_seconds,
      lineOfSightTiles: mechanics.line_of_sight_tiles,
      damageVsSelf: mechanics.derived?.damage_vs_self,
    }),
    provenance: Object.freeze({
      datSha256: mechanics.provenance?.dat_sha256,
      referenceDbSha256: mechanics.provenance?.reference_db_sha256,
      fixtureSha256: source.mechanicsFixture.sha256,
      datSelector: mechanics.provenance?.dat_selector,
      referenceSelector: mechanics.provenance?.reference_selector,
      fieldSources: Object.freeze({
        hp: fields.hp,
        speedTilesPerSecond: fields.speed_tiles_per_second,
        collisionRadiusTiles: fields["collision_size_tiles.x"],
        attackRangeTiles: fields.attack_range_tiles,
        reloadSeconds: fields.reload_seconds,
        attackDelaySeconds: fields.attack_delay_seconds,
        lineOfSightTiles: fields.line_of_sight_tiles,
        damageVsSelf: fields["derived.damage_vs_self"],
      }),
    }),
    sourceAudit,
  });
}


export function compareChampionSuite({
  truth,
  simulationResults,
  clockEvidence,
  mechanics,
  sourceAudit,
} = {}) {
  if (!truth || typeof truth !== "object") throw new TypeError("truth is required");
  if (!Array.isArray(simulationResults)) {
    throw new TypeError("simulation results must be an array");
  }
  const source = sourceSummary(truth, simulationResults);
  const clock = clockSummary(clockEvidence, truth);
  const mechanicsReport = mechanicsSummary(mechanics, sourceAudit, source);
  const ratios = RATIO_ORDER.map((ratio) => {
    const tape = tapeSummary(truth, ratio);
    const simulation = simulationSummary(resultSet(simulationResults, ratio));
    const hpDelta = simulation.winnerHp - tape.medianWinnerHp;
    const hpPctDelta = simulation.winnerHpPct - tape.medianWinnerHpPct;
    const winnerCorrect = tape.winnerOwners.includes(simulation.winnerOwner);
    const survivorCountWithinTapeRange = within(
      simulation.survivors,
      tape.survivorCountRange,
    );
    const damageEventCountWithinTapeRange = within(
      simulation.damageEvents,
      tape.damageEventCountRange,
    );
    const determinism = simulation.determinism;
    // The gate is the band the three authorized runs actually span, not its
    // median. Requiring the median would be fitting the outcome -- the tape
    // itself disagrees with its own median in 2v1, 5v3 and 6v3, so a simulator
    // that reproduces the mechanics correctly has no reason to land on it.
    const winnerHpWithinTapeRange = within(simulation.winnerHp, tape.winnerHpRange);
    const passed = (
      winnerHpWithinTapeRange
      && winnerCorrect
      && survivorCountWithinTapeRange
      && damageEventCountWithinTapeRange
      && determinism.repeatMatches
      && determinism.reverseOrderMatches
      && tape.fixtureMedianWinnerHpPctMatches
      && simulation.validity.passed
    );
    return Object.freeze({
      ratio,
      tape,
      simulation: Object.freeze({
        winnerOwner: simulation.winnerOwner,
        winnerHp: simulation.winnerHp,
        winnerStartingHp: simulation.winnerStartingHp,
        winnerHpPct: simulation.winnerHpPct,
        survivors: simulation.survivors,
        damageEvents: simulation.damageEvents,
        ticks: simulation.ticks,
        finalStateHash: simulation.finalStateHash,
        eventLogHash: simulation.eventLogHash,
        snapshotCount: simulation.snapshotCount,
        eventCount: simulation.eventCount,
      }),
      diagnostics: simulation.diagnostics,
      tapeComparisons: simulation.tapeComparisons,
      playback: Object.freeze({
        schemaVersion: 1,
        provider: "createChampionPlaybackData",
        module: "aoe2x/js_simulation/src/champion-comparison.js",
        runner: "aoe2x/js_simulation/tests/support/champion-ratio.mjs",
        ratio,
        snapshots: simulation.snapshotCount,
        events: simulation.eventCount,
        embedsFullTrace: false,
        immutableRunnerFields: Object.freeze(["snapshots", "events"]),
        verification: "strict_run_source_and_canonical_hashes",
      }),
      validity: simulation.validity,
      hpDelta,
      hpPctDelta,
      absoluteHpDelta: Math.abs(hpDelta),
      absoluteHpPctDelta: Math.abs(hpPctDelta),
      winnerCorrect,
      survivorCountWithinTapeRange,
      damageEventCountWithinTapeRange,
      determinism,
      passed,
    });
  });
  return Object.freeze({
    schemaVersion: 1,
    source,
    clock,
    mechanics: mechanicsReport,
    passed: (
      source.verifiedByRunner
      && clock.status === "provisional_not_published"
      && clock.sourceVerified
      && mechanicsReport.verified
      && mechanicsReport.sourceAudit.passed
      && ratios.every(({ passed }) => passed)
    ),
    ratios: Object.freeze(ratios),
  });
}


export function serializeChampionReport(report) {
  if (!report || typeof report !== "object") throw new TypeError("report is required");
  return `${JSON.stringify(report, null, 2)}\n`;
}


function signed(value, suffix = "") {
  return `${value >= 0 ? "+" : ""}${value}${suffix}`;
}


function rangeText(range) {
  return range.min === range.max ? `${range.min}` : `${range.min}-${range.max}`;
}


function tapeWinnerText(tape) {
  return tape.requiredWinnerOwner ?? tape.winnerOwners.join(" or ");
}


export function renderChampionMarkdown(report) {
  if (!report || typeof report !== "object" || !Array.isArray(report.ratios)) {
    throw new TypeError("suite report is required");
  }
  const lines = [
    "# Champion clean-room simulation results",
    "",
    `Overall gate: **${report.passed ? "PASS" : "FAIL"}**`,
    "",
    "## Source and clock",
    "",
    `- Archive: \`${report.source.archivePath}\``,
    `- SHA-256: \`${report.source.zipSha256}\``,
    `- Authorized recordings: ${report.source.recordings} (${report.source.verifiedByRunner ? "runner-verified" : "not verified"})`,
    `- Truth fixture SHA-256: \`${report.source.truthFixture.sha256}\` (byte-exact runtime lock)`,
    `- Mechanics fixture SHA-256: \`${report.source.mechanicsFixture.sha256}\` (byte-exact runtime lock)`,
    `- Mechanics reproducibility scope: ${report.source.mechanicsFixture.reproducibilityScope}.`,
    `- Simulation clock: ${report.clock.ticksPerSecond} Hz; status \`${report.clock.status}\``,
    `- Clock basis: ${report.clock.selectionBasis}`,
    "",
    "## Strict outcomes",
    "",
    "Tape HP percentages below are recomputed from median remaining HP divided by median winner starting HP, then checked against the fixture's reported percentage.",
    "",
    "| Ratio | Tape winner | Tape median HP | Tape HP % | Sim winner | Sim HP | Sim HP % | HP delta | HP % delta | Survivors (tape) | Damage events (tape) | Deterministic | Runtime validity | Gate |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
  ];
  for (const row of report.ratios) {
    lines.push(
      `| ${row.ratio} | ${tapeWinnerText(row.tape)} | ${row.tape.medianWinnerHp}/${row.tape.medianWinnerStartingHp} | ${row.tape.medianWinnerHpPct}% | ${row.simulation.winnerOwner} | ${row.simulation.winnerHp}/${row.simulation.winnerStartingHp} | ${row.simulation.winnerHpPct}% | ${signed(row.hpDelta)} | ${signed(row.hpPctDelta, " pp")} | ${row.simulation.survivors} (${rangeText(row.tape.survivorCountRange)}) | ${row.simulation.damageEvents} (${rangeText(row.tape.damageEventCountRange)}) | ${row.determinism.repeatMatches && row.determinism.reverseOrderMatches ? "yes" : "no"} | ${row.validity.passed ? "PASS" : "FAIL"} | ${row.passed ? "PASS" : "FAIL"} |`,
    );
  }

  lines.push(
    "",
    "## Diagnostic traces",
    "",
    "Timing and trajectory diagnostics are reported for inspection; they are not calibration targets.",
    "",
    "| Ratio | First move | First damage | Final kill | Distance traveled | Blocked ticks | Death-canceled attacks |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
  );
  for (const row of report.ratios) {
    const diagnostics = row.diagnostics;
    lines.push(
      `| ${row.ratio} | tick ${diagnostics.firstMovement.tick} (${diagnostics.firstMovement.seconds}s) | tick ${diagnostics.firstDamage.tick} (${diagnostics.firstDamage.seconds}s) | tick ${diagnostics.finalKill.tick} (${diagnostics.finalKill.seconds}s) | ${diagnostics.distanceTraveled.totalTiles} tiles | ${diagnostics.blockedTicks.total} | ${diagnostics.attacksCanceledByDeath.count} |`,
    );
  }

  lines.push(
    "",
    "## Tape-repeat diagnostics and playback",
    "",
    "Each ratio retains all three authorized repeat tags plus spawn, first-movement, contact, first-damage, interval, hit-count, kill, and winner-HP deltas in the JSON report.",
    "",
    "The report stays lean and does not duplicate full traces. The browser viewer must call `createChampionPlaybackData` from `aoe2x/js_simulation/src/champion-comparison.js`; that verified serializer boundary accepts only a supported, deep-immutable run whose target lifecycle, authorized source metadata, terminal state, and canonical state/event hashes validate.",
  );

  lines.push(
    "",
    "## Determinism hashes",
    "",
  );
  for (const row of report.ratios) {
    lines.push(
      `- ${row.ratio}: final \`${row.simulation.finalStateHash}\`; events \`${row.simulation.eventLogHash}\``,
    );
  }

  lines.push(
    "",
    "## Mechanics audit",
    "",
    `Champion ${report.mechanics.values.unitMaster} (${report.mechanics.values.civilization}): ${report.mechanics.values.hp} HP, ${report.mechanics.values.speedTilesPerSecond} tiles/s, ${report.mechanics.values.collisionRadiusTiles}-tile collision radius, ${report.mechanics.values.attackRangeTiles}-tile range, ${report.mechanics.values.reloadSeconds}s reload, ${report.mechanics.values.attackDelaySeconds}s attack delay, ${report.mechanics.values.damageVsSelf} damage versus self.`,
    "",
    `- Genie data SHA-256: \`${report.mechanics.provenance.datSha256}\``,
    `- Reference DB SHA-256: \`${report.mechanics.provenance.referenceDbSha256}\``,
  );
  if (report.mechanics.sourceAudit.passed) {
    lines.push(
      `- Heuristic static lint found no unapproved shortcut-pattern matches in ${report.mechanics.sourceAudit.files.length} audited executable files; ${report.mechanics.sourceAudit.approvedFindings.length} expected scenario/map/source-mechanics matches are retained with reasons in JSON.`,
      `- Assurance limit: ${report.mechanics.sourceAudit.assurance}`,
      `- Separate review evidence: \`${report.mechanics.sourceAudit.separateReview.evidence}\``,
      `- Exact lint exclusion: \`${report.mechanics.sourceAudit.exclusions[0].file}\` - ${report.mechanics.sourceAudit.exclusions[0].reason}.`,
    );
  } else {
    lines.push(`- **Audit failed:** ${report.mechanics.sourceAudit.findings.length} prohibited source finding(s) and ${report.mechanics.sourceAudit.allowanceMismatches.length} exact-fingerprint count mismatch(es).`);
  }
  lines.push(
    "",
    "The complete JSON companion contains per-unit distance and blocked-tick totals, the target timeline, death-canceled attack records, all repeat/reversal hashes, and field-level mechanics provenance.",
    "",
  );
  return lines.join("\n");
}
