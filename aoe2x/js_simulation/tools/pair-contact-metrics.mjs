const EPSILON = 1e-12;
const PERCENTILES = Object.freeze([
  ["p01", 0.01],
  ["p05", 0.05],
  ["median", 0.5],
  ["p95", 0.95],
  ["p99", 0.99],
]);

export function percentile(values, probability) {
  if (!Number.isFinite(probability) || probability < 0 || probability > 1) {
    throw new RangeError("percentile probability must be between zero and one");
  }
  if (!Array.isArray(values)) {
    throw new TypeError("percentile values must be an array");
  }
  if (values.length === 0) {
    return null;
  }
  const sorted = values.map((value) => {
    if (!Number.isFinite(value)) {
      throw new TypeError("percentile values must be finite");
    }
    return value;
  }).sort((left, right) => left - right);
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) {
    return cleanNumber(sorted[lower]);
  }
  const weight = index - lower;
  return cleanNumber(sorted[lower] * (1 - weight) + sorted[upper] * weight);
}

export function analyzePairContactFrames(frames) {
  validateFrames(frames);
  const sampleDurations = inferSampleDurations(frames);
  const populationAccumulators = new Map();
  const relationshipAccumulators = new Map();
  const activeWindows = new Map();
  let previousContacts = new Set();

  frames.forEach((frame, frameIndex) => {
    const live = frame.units
      .filter(({ hp }) => Number.isFinite(hp) && hp > 0)
      .slice()
      .sort(compareUnits);
    const currentContacts = new Set();
    const seenPairs = new Set();
    const relationshipFrameEdges = new Map();
    const relationshipFrameDeepEdges = new Map();
    const relationshipFrameUnits = new Map();
    const populationFrameEdges = new Map();
    const populationFrameDeepEdges = new Map();
    const populationFrameUnits = new Map();
    const relationshipsSeen = new Set();
    const populationsSeen = new Set();

    for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
        const left = live[leftIndex];
        const right = live[rightIndex];
        const pairKey = canonicalPairKey(left.id, right.id);
        const state = pairState(left, right);
        const geometry = pairGeometry(left, right);
        const overlapping = geometry.depth > EPSILON;
        const relationship = getAccumulator(
          relationshipAccumulators,
          state.relationship,
          createAccumulator,
        );

        seenPairs.add(pairKey);
        relationshipsSeen.add(state.relationship);
        observePairFrame(relationship, geometry, overlapping);

        if (overlapping) {
          currentContacts.add(pairKey);
          const phase = previousContacts.has(pairKey) ? "persisting" : "entering";
          const populationKey = populationKeyFor(state, phase);
          const population = getAccumulator(
            populationAccumulators,
            populationKey,
            createAccumulator,
          );
          observePairFrame(population, geometry, true);
          populationsSeen.add(populationKey);
          population.acquisitionCount += phase === "entering" ? 1 : 0;
          relationship.acquisitionCount += phase === "entering" ? 1 : 0;
          addFrameEdge(relationshipFrameEdges, state.relationship, left.id, right.id);
          addFrameEdge(populationFrameEdges, populationKey, left.id, right.id);
          addFrameUnits(relationshipFrameUnits, state.relationship, left, right);
          addFrameUnits(populationFrameUnits, populationKey, left, right);
          if (geometry.deep) {
            addFrameEdge(relationshipFrameDeepEdges, state.relationship, left.id, right.id);
            addFrameEdge(populationFrameDeepEdges, populationKey, left.id, right.id);
          }
          observeContactWindow(
            activeWindows,
            pairKey,
            state.relationship,
            sampleDurations[frameIndex],
          );
        } else if (previousContacts.has(pairKey)) {
          const populationKey = populationKeyFor(state, "leaving");
          const population = getAccumulator(
            populationAccumulators,
            populationKey,
            createAccumulator,
          );
          observePairFrame(population, geometry, false);
          populationsSeen.add(populationKey);
          population.releaseCount += 1;
          relationship.releaseCount += 1;
          finishContactWindow(activeWindows, pairKey, relationshipAccumulators);
        }
      }
    }

    for (const pairKey of activeWindows.keys()) {
      if (!seenPairs.has(pairKey)) {
        finishContactWindow(activeWindows, pairKey, relationshipAccumulators);
      }
    }
    for (const relationshipName of relationshipsSeen) {
      const accumulator = relationshipAccumulators.get(relationshipName);
      accumulator.frameCount += 1;
      updateGraphMetrics(
        accumulator,
        relationshipFrameEdges.get(relationshipName) ?? [],
        relationshipFrameDeepEdges.get(relationshipName) ?? [],
        relationshipFrameUnits.get(relationshipName) ?? new Map(),
      );
    }
    for (const populationKey of populationsSeen) {
      const accumulator = populationAccumulators.get(populationKey);
      accumulator.frameCount += 1;
      updateGraphMetrics(
        accumulator,
        populationFrameEdges.get(populationKey) ?? [],
        populationFrameDeepEdges.get(populationKey) ?? [],
        populationFrameUnits.get(populationKey) ?? new Map(),
      );
    }
    previousContacts = currentContacts;
  });

  for (const pairKey of [...activeWindows.keys()]) {
    finishContactWindow(activeWindows, pairKey, relationshipAccumulators);
  }

  return deepFreeze({
    populations: finishAccumulatorMap(populationAccumulators),
    relationships: finishAccumulatorMap(relationshipAccumulators),
  });
}

function validateFrames(frames) {
  if (!Array.isArray(frames)) {
    throw new TypeError("pair contact frames must be an array");
  }
  let previousTime = -Infinity;
  for (const frame of frames) {
    if (!frame || !Number.isFinite(frame.timeMs) || !Array.isArray(frame.units)) {
      throw new TypeError("each pair contact frame requires finite timeMs and a units array");
    }
    if (frame.timeMs <= previousTime) {
      throw new RangeError("pair contact frame times must increase strictly");
    }
    previousTime = frame.timeMs;
    const ids = new Set();
    for (const unit of frame.units) {
      validateUnit(unit);
      const idKey = typedId(unit.id);
      if (ids.has(idKey)) {
        throw new Error(`duplicate unit id in pair contact frame: ${String(unit.id)}`);
      }
      ids.add(idKey);
    }
  }
}

function validateUnit(unit) {
  if (!unit || unit.id === null || unit.id === undefined) {
    throw new TypeError("pair contact units require an id");
  }
  for (const field of ["x", "y", "radius", "hp"]) {
    if (!Number.isFinite(unit[field])) {
      throw new TypeError(`pair contact unit ${String(unit.id)} requires finite ${field}`);
    }
  }
  if (unit.radius < 0) {
    throw new RangeError("pair contact unit radius cannot be negative");
  }
}

function inferSampleDurations(frames) {
  if (frames.length < 2) {
    return frames.map(() => 0);
  }
  return frames.map((frame, index) => {
    if (index + 1 < frames.length) {
      return frames[index + 1].timeMs - frame.timeMs;
    }
    return frame.timeMs - frames[index - 1].timeMs;
  });
}

function pairState(left, right) {
  const relationship = left.owner !== right.owner
    ? "enemies"
    : (left.master === right.master ? "same-master-allies" : "mixed-master-allies");
  const moving = Number(Boolean(left.moving)) + Number(Boolean(right.moving));
  const attacking = Number(Boolean(left.attacking)) + Number(Boolean(right.attacking));
  return Object.freeze({
    relationship,
    motion: ["neither-moving", "one-moving", "both-moving"][moving],
    attack: ["neither-attacking", "one-attacking", "both-attacking"][attacking],
    intent: relationship === "enemies" ? enemyIntent(left, right) : "none",
  });
}

function enemyIntent(left, right) {
  return targets(left, right.id) || targets(right, left.id)
    ? "direct-target"
    : "corridor-contact";
}

function targets(unit, targetId) {
  return [unit.pursuitTargetId, unit.engagedTargetId, unit.attackTargetId]
    .some((candidate) => candidate !== null
      && candidate !== undefined
      && typedId(candidate) === typedId(targetId));
}

function pairGeometry(left, right) {
  const separation = Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
  const fullExtent = left.radius + right.radius;
  const movingFloor = collisionFloor(left) + collisionFloor(right);
  const depth = Math.max(0, fullExtent - separation);
  return Object.freeze({
    separation: cleanNumber(separation),
    fullExtent: cleanNumber(fullExtent),
    depth: cleanNumber(depth),
    normalizedDepth: fullExtent > EPSILON ? cleanNumber(depth / fullExtent) : 0,
    movingFloor: cleanNumber(movingFloor),
    deep: separation < movingFloor - EPSILON,
  });
}

function collisionFloor(unit) {
  const multiplier = unit.minCollisionMultiplier ?? 1;
  if (!Number.isFinite(multiplier) || multiplier <= 0 || multiplier > 1) {
    throw new RangeError(`unit ${String(unit.id)} has an invalid minimum collision multiplier`);
  }
  return unit.radius * multiplier;
}

function populationKeyFor(state, phase) {
  return [state.relationship, state.motion, state.attack, state.intent, phase].join("|");
}

function createAccumulator() {
  return {
    pairFrames: 0,
    overlapPairs: 0,
    frameCount: 0,
    framesWithOverlap: 0,
    acquisitionCount: 0,
    releaseCount: 0,
    separations: [],
    depths: [],
    normalizedDepths: [],
    contactWindowsMs: [],
    localNeighborCounts: [],
    componentSizes: [],
    deepLocalNeighborCounts: [],
    deepComponentSizes: [],
    attackingUnitCounts: [],
    contactUnitCounts: [],
    attackAccessRatios: [],
    targetLoads: [],
    maximumSimultaneousOverlappingPairs: 0,
    maximumLocalDegree: 0,
    maximumComponentSize: 0,
    maximumTriangles: 0,
    maximumFourCliques: 0,
    maximumDeepLocalDegree: 0,
    maximumDeepComponentSize: 0,
    maximumDeepTriangles: 0,
    maximumDeepFourCliques: 0,
  };
}

function observePairFrame(accumulator, geometry, overlapping) {
  accumulator.pairFrames += 1;
  if (!overlapping) {
    return;
  }
  accumulator.overlapPairs += 1;
  accumulator.separations.push(geometry.separation);
  accumulator.depths.push(geometry.depth);
  accumulator.normalizedDepths.push(geometry.normalizedDepth);
}

function observeContactWindow(activeWindows, pairKey, relationship, sampleDurationMs) {
  let window = activeWindows.get(pairKey);
  if (!window) {
    window = { relationship, durationMs: 0 };
    activeWindows.set(pairKey, window);
  }
  if (window.relationship !== relationship) {
    throw new Error(`pair relationship changed during contact window: ${pairKey}`);
  }
  window.durationMs += sampleDurationMs;
}

function finishContactWindow(activeWindows, pairKey, relationshipAccumulators) {
  const window = activeWindows.get(pairKey);
  if (!window) {
    return;
  }
  const accumulator = relationshipAccumulators.get(window.relationship);
  accumulator.contactWindowsMs.push(cleanNumber(window.durationMs));
  activeWindows.delete(pairKey);
}

function addFrameEdge(frameEdges, key, leftId, rightId) {
  const edges = getAccumulator(frameEdges, key, () => []);
  edges.push([typedId(leftId), typedId(rightId)]);
}

function addFrameUnits(frameUnits, key, left, right) {
  const units = getAccumulator(frameUnits, key, () => new Map());
  units.set(typedId(left.id), left);
  units.set(typedId(right.id), right);
}

function updateGraphMetrics(accumulator, edges, deepEdges, units) {
  if (edges.length === 0) {
    return;
  }
  accumulator.framesWithOverlap += 1;
  accumulator.maximumSimultaneousOverlappingPairs = Math.max(
    accumulator.maximumSimultaneousOverlappingPairs,
    edges.length,
  );
  const adjacency = new Map();
  for (const [left, right] of edges) {
    getAccumulator(adjacency, left, () => new Set()).add(right);
    getAccumulator(adjacency, right, () => new Set()).add(left);
  }
  for (const neighbors of adjacency.values()) {
    accumulator.localNeighborCounts.push(neighbors.size);
    accumulator.maximumLocalDegree = Math.max(
      accumulator.maximumLocalDegree,
      neighbors.size,
    );
  }
  const components = componentSizes(adjacency);
  accumulator.componentSizes.push(...components);
  accumulator.maximumComponentSize = Math.max(accumulator.maximumComponentSize, ...components);
  const { triangles, fourCliques } = countCliques(adjacency);
  accumulator.maximumTriangles = Math.max(accumulator.maximumTriangles, triangles);
  accumulator.maximumFourCliques = Math.max(accumulator.maximumFourCliques, fourCliques);
  observeAttackAccess(accumulator, units);

  if (deepEdges.length === 0) return;
  const deepAdjacency = new Map();
  for (const [left, right] of deepEdges) {
    getAccumulator(deepAdjacency, left, () => new Set()).add(right);
    getAccumulator(deepAdjacency, right, () => new Set()).add(left);
  }
  for (const neighbors of deepAdjacency.values()) {
    accumulator.deepLocalNeighborCounts.push(neighbors.size);
    accumulator.maximumDeepLocalDegree = Math.max(
      accumulator.maximumDeepLocalDegree,
      neighbors.size,
    );
  }
  const deepComponents = componentSizes(deepAdjacency);
  accumulator.deepComponentSizes.push(...deepComponents);
  accumulator.maximumDeepComponentSize = Math.max(
    accumulator.maximumDeepComponentSize,
    ...deepComponents,
  );
  const deepCliques = countCliques(deepAdjacency);
  accumulator.maximumDeepTriangles = Math.max(
    accumulator.maximumDeepTriangles,
    deepCliques.triangles,
  );
  accumulator.maximumDeepFourCliques = Math.max(
    accumulator.maximumDeepFourCliques,
    deepCliques.fourCliques,
  );
}

function observeAttackAccess(accumulator, units) {
  const contactUnits = [...units.values()];
  const attacking = contactUnits.filter(({ attacking }) => attacking);
  accumulator.contactUnitCounts.push(contactUnits.length);
  accumulator.attackingUnitCounts.push(attacking.length);
  accumulator.attackAccessRatios.push(cleanNumber(
    contactUnits.length > 0 ? attacking.length / contactUnits.length : 0,
  ));
  const targetLoads = new Map();
  for (const unit of attacking) {
    const targetId = unit.attackTargetId ?? unit.engagedTargetId ?? unit.pursuitTargetId;
    if (targetId === null || targetId === undefined) continue;
    const targetKey = typedId(targetId);
    targetLoads.set(targetKey, (targetLoads.get(targetKey) ?? 0) + 1);
  }
  accumulator.targetLoads.push(...targetLoads.values());
}

function componentSizes(adjacency) {
  const visited = new Set();
  const sizes = [];
  for (const start of adjacency.keys()) {
    if (visited.has(start)) {
      continue;
    }
    let size = 0;
    const pending = [start];
    visited.add(start);
    while (pending.length > 0) {
      const current = pending.pop();
      size += 1;
      for (const neighbor of adjacency.get(current) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          pending.push(neighbor);
        }
      }
    }
    sizes.push(size);
  }
  return sizes;
}

function countCliques(adjacency) {
  const nodes = [...adjacency.keys()].sort();
  let triangles = 0;
  let fourCliques = 0;
  for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
    const left = nodes[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
      const right = nodes[rightIndex];
      if (!adjacency.get(left).has(right)) {
        continue;
      }
      for (let thirdIndex = rightIndex + 1; thirdIndex < nodes.length; thirdIndex += 1) {
        const third = nodes[thirdIndex];
        if (!adjacency.get(left).has(third) || !adjacency.get(right).has(third)) {
          continue;
        }
        triangles += 1;
        for (let fourthIndex = thirdIndex + 1; fourthIndex < nodes.length; fourthIndex += 1) {
          const fourth = nodes[fourthIndex];
          if (adjacency.get(left).has(fourth)
              && adjacency.get(right).has(fourth)
              && adjacency.get(third).has(fourth)) {
            fourCliques += 1;
          }
        }
      }
    }
  }
  return { triangles, fourCliques };
}

function finishAccumulatorMap(accumulators) {
  return Object.fromEntries(
    [...accumulators.entries()]
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, accumulator]) => [key, finishAccumulator(accumulator)]),
  );
}

function finishAccumulator(accumulator) {
  return {
    pairFrames: accumulator.pairFrames,
    overlapPairs: accumulator.overlapPairs,
    overlapPairShare: accumulator.pairFrames > 0
      ? cleanNumber(accumulator.overlapPairs / accumulator.pairFrames)
      : 0,
    frameCount: accumulator.frameCount,
    framesWithOverlap: accumulator.framesWithOverlap,
    acquisitionCount: accumulator.acquisitionCount,
    releaseCount: accumulator.releaseCount,
    minimumSeparation: minimum(accumulator.separations),
    ...prefixedSummary("separation", accumulator.separations),
    maximumSeparation: maximum(accumulator.separations),
    minimumDepth: minimum(accumulator.depths),
    ...prefixedSummary("depth", accumulator.depths),
    medianDepth: percentile(accumulator.depths, 0.5),
    maximumDepth: maximum(accumulator.depths),
    minimumNormalizedDepth: minimum(accumulator.normalizedDepths),
    ...prefixedSummary("normalizedDepth", accumulator.normalizedDepths),
    maximumNormalizedDepth: maximum(accumulator.normalizedDepths),
    contactWindowMs: distribution(accumulator.contactWindowsMs),
    localNeighborCount: distribution(accumulator.localNeighborCounts),
    componentSize: distribution(accumulator.componentSizes),
    deepLocalNeighborCount: distribution(accumulator.deepLocalNeighborCounts),
    deepComponentSize: distribution(accumulator.deepComponentSizes),
    attackingUnitCount: distribution(accumulator.attackingUnitCounts),
    contactUnitCount: distribution(accumulator.contactUnitCounts),
    attackAccessRatio: distribution(accumulator.attackAccessRatios),
    targetLoad: distribution(accumulator.targetLoads),
    maximumSimultaneousOverlappingPairs: accumulator.maximumSimultaneousOverlappingPairs,
    maximumLocalDegree: accumulator.maximumLocalDegree,
    maximumComponentSize: accumulator.maximumComponentSize,
    maximumTriangles: accumulator.maximumTriangles,
    maximumFourCliques: accumulator.maximumFourCliques,
    maximumDeepLocalDegree: accumulator.maximumDeepLocalDegree,
    maximumDeepComponentSize: accumulator.maximumDeepComponentSize,
    maximumDeepTriangles: accumulator.maximumDeepTriangles,
    maximumDeepFourCliques: accumulator.maximumDeepFourCliques,
  };
}

function prefixedSummary(prefix, values) {
  return Object.fromEntries(PERCENTILES.map(([label, probability]) => [
    `${label}${prefix[0].toUpperCase()}${prefix.slice(1)}`,
    percentile(values, probability),
  ]));
}

function distribution(values) {
  return {
    count: values.length,
    minimum: minimum(values),
    ...Object.fromEntries(PERCENTILES.map(([label, probability]) => [
      label,
      percentile(values, probability),
    ])),
    maximum: maximum(values),
  };
}

function minimum(values) {
  return values.length > 0 ? cleanNumber(Math.min(...values)) : null;
}

function maximum(values) {
  return values.length > 0 ? cleanNumber(Math.max(...values)) : null;
}

function getAccumulator(map, key, factory) {
  if (!map.has(key)) {
    map.set(key, factory());
  }
  return map.get(key);
}

function compareUnits(left, right) {
  return typedId(left.id).localeCompare(typedId(right.id));
}

function canonicalPairKey(leftId, rightId) {
  return [typedId(leftId), typedId(rightId)].sort().join("\u0000");
}

function typedId(id) {
  return `${typeof id}:${String(id)}`;
}

function cleanNumber(value) {
  return Object.is(value, -0) ? 0 : Math.round(value * 1e12) / 1e12;
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  Object.freeze(value);
  for (const child of Object.values(value)) {
    deepFreeze(child);
  }
  return value;
}
