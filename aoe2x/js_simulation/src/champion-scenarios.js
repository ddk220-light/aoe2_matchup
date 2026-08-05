import { createUnitState } from "./combat/unit-state.js";


const CHAMPION_MASTER = 567;
const CHAMPION_HP = 70;
const LOCKED_SOURCE_HASH = "f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4";
const SUPPORTED_RATIOS = new Set(["1v1", "2v1", "2v3", "5v3", "6v3"]);
const LOCKED_ROSTERS = {
  "1v1": { 2: [1628], 3: [1699] },
  "2v1": { 2: [1628, 1629], 3: [1699] },
  "2v3": { 2: [1628, 1629], 3: [1699, 1700, 1701] },
  "5v3": { 2: [1628, 1629, 1630, 1631, 1632], 3: [1699, 1700, 1701] },
  "6v3": { 2: [1628, 1629, 1630, 1631, 1632, 1633], 3: [1699, 1700, 1701] },
};


function requiredObject(value, name) {
  if (!value || typeof value !== "object") throw new TypeError(`${name} is required`);
  return value;
}


function formationByReference(formation) {
  requiredObject(formation, "validated formation");
  if (formation.validation?.valid !== true || formation.validation.conflicts?.length !== 0) {
    throw new Error("locked formation contains placement conflicts");
  }
  if (formation.source?.sha256 !== LOCKED_SOURCE_HASH) {
    throw new Error("locked formation source hash does not match");
  }

  const units = [
    ...(formation.sides?.["2"] ?? []),
    ...(formation.sides?.["3"] ?? []),
  ];
  const byReference = new Map();
  for (const unit of units) {
    if (byReference.has(unit.reference_id)) {
      throw new Error(`duplicate formation reference ${unit.reference_id}`);
    }
    byReference.set(unit.reference_id, unit);
  }
  return byReference;
}


function canonicalStartPositions(truth, ratio) {
  requiredObject(truth, "Champion truth");
  if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {
    throw new RangeError(`unknown ratio ${ratio}`);
  }
  const ratioTruth = truth.ratios[ratio];
  const positions = ratioTruth.canonical_start_positions ?? ratioTruth.runs?.[0]?.starting_units?.map(
    ({ id, x, y }) => [id, x, y],
  );
  if (!Array.isArray(positions)) {
    throw new TypeError(`ratio ${ratio} must provide canonical start positions`);
  }
  return positions;
}


function createScenarioUnit(start, formationUnits, mechanics, references, rank, count) {
  if (!Array.isArray(start) || start.length !== 3) {
    throw new TypeError("canonical start position must be [referenceId, x, y]");
  }
  const [referenceId, x, y] = start;
  if (!Number.isSafeInteger(referenceId)) {
    throw new TypeError("scenario reference ID must be a safe integer");
  }
  if (references.has(referenceId)) {
    throw new Error(`duplicate scenario reference ${referenceId}`);
  }
  references.add(referenceId);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new TypeError(`position for scenario reference ${referenceId} must be finite`);
  }

  const placement = formationUnits.get(referenceId);
  if (!placement) throw new RangeError(`scenario reference ${referenceId} is absent from locked formation`);
  return createUnitState({
    referenceId,
    owner: placement.player_id,
    x,
    y,
    facing: placement.rotation,
    mechanics,
    // Engine reaction lag is staggered across the roster, not shared; see
    // acquisitionDelaySeconds in combat/targeting.js.
    acquisitionRank: rank,
    acquisitionCount: count,
  });
}


function validateLockedRoster(ratio, units) {
  const expected = LOCKED_ROSTERS[ratio];
  const actual = {
    2: units.filter(({ owner }) => owner === 2).map(({ referenceId }) => referenceId),
    3: units.filter(({ owner }) => owner === 3).map(({ referenceId }) => referenceId),
  };
  if (actual[2].length !== expected[2].length || actual[3].length !== expected[3].length) {
    throw new Error(
      `ratio ${ratio} must contain ${expected[2].length} owner 2 and ${expected[3].length} owner 3`,
    );
  }
  const expectedReferences = [...expected[2], ...expected[3]];
  if (units.some(({ referenceId }, index) => referenceId !== expectedReferences[index])) {
    throw new Error(`ratio ${ratio} must use its locked references`);
  }
}


export function createChampionScenario({ ratio, formation, truth, mechanics } = {}) {
  const starts = canonicalStartPositions(truth, ratio);
  requiredObject(mechanics, "Champion mechanics");
  if (mechanics.unit_master !== CHAMPION_MASTER) {
    throw new RangeError(`Champion mechanics must use master ${CHAMPION_MASTER}`);
  }
  if (mechanics.hp !== CHAMPION_HP) {
    throw new RangeError(`Champion mechanics must use ${CHAMPION_HP} HP`);
  }

  const formationUnits = formationByReference(formation);
  const references = new Set();
  const units = starts.map((start, index) => createScenarioUnit(
    start, formationUnits, mechanics, references, index, starts.length,
  ));
  validateLockedRoster(ratio, units);

  return Object.freeze({
    ratio,
    units: Object.freeze(units),
    mapHash: formation.source.sha256,
  });
}
