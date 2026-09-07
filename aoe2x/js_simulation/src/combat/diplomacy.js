export const DIPLOMACY = Object.freeze({
  ALLY: 0,
  NEUTRAL: 1,
  ENEMY: 3,
});


const VALID_DIPLOMACY = new Set(Object.values(DIPLOMACY));


function requireOwner(value, name = "owner") {
  if (!Number.isSafeInteger(value)) {
    throw new TypeError(`${name} must be a safe integer`);
  }
  return value;
}


export function createDiplomacyByOwner(owners, supplied = undefined) {
  const ordered = [...new Set(owners.map((owner) => requireOwner(owner)))].sort(
    (left, right) => left - right,
  );
  if (ordered.length === 0) throw new RangeError("diplomacy requires at least one owner");
  if (supplied !== undefined
      && (!supplied || typeof supplied !== "object" || Array.isArray(supplied))) {
    throw new TypeError("diplomacy by owner must be an object");
  }

  const result = {};
  for (const owner of ordered) {
    const suppliedRow = supplied?.[owner] ?? supplied?.[String(owner)];
    if (supplied !== undefined
        && (!suppliedRow || typeof suppliedRow !== "object" || Array.isArray(suppliedRow))) {
      throw new TypeError(`diplomacy owner ${owner} must be an object`);
    }
    const row = {};
    for (const target of ordered) {
      if (target === owner) continue;
      const value = supplied === undefined
        ? DIPLOMACY.ENEMY
        : suppliedRow[target] ?? suppliedRow[String(target)];
      if (!VALID_DIPLOMACY.has(value)) {
        throw new RangeError(
          `diplomacy ${owner}->${target} must be ally (0), neutral (1), or enemy (3)`,
        );
      }
      row[target] = value;
    }
    result[owner] = Object.freeze(row);
  }
  return Object.freeze(result);
}


export function changeDiplomacy(diplomacyByOwner, sourceOwner, targetOwner, value, {
  mutual = false,
} = {}) {
  requireOwner(sourceOwner, "diplomacy source owner");
  requireOwner(targetOwner, "diplomacy target owner");
  if (sourceOwner === targetOwner) throw new RangeError("self diplomacy cannot change");
  if (!VALID_DIPLOMACY.has(value)) {
    throw new RangeError("diplomacy value must be ally (0), neutral (1), or enemy (3)");
  }
  if (typeof mutual !== "boolean") throw new TypeError("mutual diplomacy must be boolean");
  if (!diplomacyByOwner?.[sourceOwner] || !diplomacyByOwner?.[targetOwner]) {
    throw new RangeError("diplomacy change must identify scenario owners");
  }

  const result = Object.fromEntries(Object.entries(diplomacyByOwner).map(([owner, row]) => (
    [owner, { ...row }]
  )));
  result[sourceOwner][targetOwner] = value;
  if (mutual) result[targetOwner][sourceOwner] = value;
  return Object.freeze(Object.fromEntries(Object.entries(result).map(([owner, row]) => (
    [owner, Object.freeze(row)]
  ))));
}


export function withDiplomacy(unit, diplomacyByOwner) {
  const relationByOwner = diplomacyByOwner?.[unit.owner]
    ?? diplomacyByOwner?.[String(unit.owner)];
  if (!relationByOwner) {
    throw new RangeError(`diplomacy is missing owner ${unit.owner}`);
  }
  return { ...unit, relationByOwner };
}


export function relationFrom(source, target) {
  if (source.owner === target.owner) return DIPLOMACY.ALLY;
  const explicit = source.relationByOwner?.[target.owner]
    ?? source.relationByOwner?.[String(target.owner)];
  // Worlds created before first-class diplomacy remain ordinary two-sided
  // fights: distinct owners are enemies. createWorld decorates every new unit,
  // but this fallback keeps standalone geometry/targeting callers compatible.
  return explicit ?? DIPLOMACY.ENEMY;
}


export function isHostile(source, target) {
  return source.referenceId !== target.referenceId
    && relationFrom(source, target) === DIPLOMACY.ENEMY;
}


export function areOpponents(left, right) {
  return isHostile(left, right) || isHostile(right, left);
}


export function areAllies(left, right) {
  return relationFrom(left, right) === DIPLOMACY.ALLY
    && relationFrom(right, left) === DIPLOMACY.ALLY;
}
