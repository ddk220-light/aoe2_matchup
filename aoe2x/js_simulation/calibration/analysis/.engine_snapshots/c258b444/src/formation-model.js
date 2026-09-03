const EXPECTED_SOURCE_SHA256 = "f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4";


function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}


export function validateFormationFixture(data) {
  if (!data || data.schema_version !== 1) {
    throw new Error("golden formation fixture must use schema version 1");
  }
  if (data.source?.sha256 !== EXPECTED_SOURCE_SHA256) {
    throw new Error("golden formation source hash does not match");
  }
  const references = new Set();
  for (const playerId of [2, 3]) {
    const side = data.sides?.[String(playerId)];
    if (!Array.isArray(side) || side.length !== 21) {
      throw new Error(`golden formation must contain exactly 21 units for player ${playerId}`);
    }
    for (const unit of side) {
      if (unit.player_id !== playerId) {
        throw new Error(`formation unit ${unit.reference_id} has the wrong player`);
      }
      if (references.has(unit.reference_id)) {
        throw new Error(`duplicate formation reference ${unit.reference_id}`);
      }
      references.add(unit.reference_id);
    }
  }
  if (data.validation?.valid !== true || data.validation.conflicts?.length !== 0) {
    throw new Error("golden formation fixture contains placement conflicts");
  }
  return deepFreeze(data);
}


export function formationUnits(fixture) {
  return Object.freeze([
    ...fixture.sides["2"],
    ...fixture.sides["3"],
  ]);
}
