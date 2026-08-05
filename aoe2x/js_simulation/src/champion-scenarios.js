import { createUnitState } from "./combat/unit-state.js";


const CHAMPION_MASTER = 567;
const SUPPORTED_RATIOS = new Set(["1v1", "2v1", "2v3", "5v3", "6v3"]);


function requiredObject(value, name) {
  if (!value || typeof value !== "object") throw new TypeError(`${name} is required`);
  return value;
}


function formationByReference(formation) {
  requiredObject(formation, "validated formation");
  if (formation.validation?.valid !== true || formation.validation.conflicts?.length !== 0) {
    throw new Error("locked formation contains placement conflicts");
  }
  if (!formation.source?.sha256) throw new Error("locked formation source hash is required");

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


function createScenarioUnit(start, formationUnits, mechanics, references) {
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
  });
}


export function createChampionScenario({ ratio, formation, truth, mechanics } = {}) {
  const starts = canonicalStartPositions(truth, ratio);
  requiredObject(mechanics, "Champion mechanics");
  if (mechanics.unit_master !== CHAMPION_MASTER) {
    throw new RangeError(`Champion mechanics must use master ${CHAMPION_MASTER}`);
  }

  const formationUnits = formationByReference(formation);
  const references = new Set();
  const units = starts.map((start) => createScenarioUnit(start, formationUnits, mechanics, references));

  return Object.freeze({
    ratio,
    units: Object.freeze(units),
    mapHash: formation.source.sha256,
  });
}
