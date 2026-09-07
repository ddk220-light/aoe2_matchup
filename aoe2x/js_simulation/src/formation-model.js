const UNITS_PER_SIDE_BY_SOURCE = Object.freeze({
  // Original Champion-vs-Champion clean-room fixture.
  f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4: 21,
  // Current melee golden scenario.
  "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e": 27,
});
const CURRENT_MELEE_SOURCE_SHA256 =
  "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e";


function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}


export function validateFormationFixture(data) {
  if (!data || data.schema_version !== 1) {
    throw new Error("golden formation fixture must use schema version 1");
  }
  const expectedUnitsPerSide = UNITS_PER_SIDE_BY_SOURCE[data.source?.sha256];
  if (expectedUnitsPerSide === undefined) {
    throw new Error("golden formation source hash does not match");
  }
  const references = new Set();
  for (const playerId of [2, 3]) {
    const side = data.sides?.[String(playerId)];
    if (!Array.isArray(side) || side.length !== expectedUnitsPerSide) {
      throw new Error(
        `golden formation must contain exactly ${expectedUnitsPerSide} units `
        + `for player ${playerId}`,
      );
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
  if (data.source.sha256 === CURRENT_MELEE_SOURCE_SHA256) {
    if (data.opening_patrol?.effect_id !== 19) {
      throw new Error("current melee formation must record its patrol trigger");
    }
    for (const playerId of [2, 3]) {
      const patrol = data.opening_patrol.by_owner?.[String(playerId)];
      if (!Number.isFinite(patrol?.x) || !Number.isFinite(patrol?.y)) {
        throw new Error(`current melee formation needs player ${playerId} patrol coordinates`);
      }
      if (patrol.x < 0 || patrol.x >= data.map.width
          || patrol.y < 0 || patrol.y >= data.map.height) {
        throw new Error(`player ${playerId} patrol destination is outside the map`);
      }
    }
  }
  if (data.validation?.valid !== true || data.validation.conflicts?.length !== 0) {
    throw new Error("golden formation fixture contains placement conflicts");
  }
  return deepFreeze(data);
}


export function formationOpeningPatrol(fixture) {
  const validated = validateFormationFixture(fixture);
  if (!validated.opening_patrol) return null;
  return Object.freeze(Object.fromEntries([2, 3].map((owner) => {
    const patrol = validated.opening_patrol.by_owner[String(owner)];
    return [owner, Object.freeze({ x: patrol.x, y: patrol.y })];
  })));
}


export function formationUnits(fixture) {
  return Object.freeze([
    ...fixture.sides["2"],
    ...fixture.sides["3"],
  ]);
}
