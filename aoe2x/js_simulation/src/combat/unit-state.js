const CHAMPION_MASTER = 567;
const CHAMPION_HP = 70;


function freezeTimers(timers) {
  const result = {};
  for (const [name, value] of Object.entries(timers)) {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new RangeError(`action timer ${name} must be a nonnegative safe integer`);
    }
    result[name] = value;
  }
  return Object.freeze(result);
}


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireSafeInteger(value, name) {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


export function createUnitState({
  referenceId,
  owner,
  x,
  y,
  facing,
  mechanics,
  actionTimers = { windup: 0, reload: 0 },
} = {}) {
  requireSafeInteger(referenceId, "reference ID");
  requireSafeInteger(owner, "owner");
  requireFinite(x, "x");
  requireFinite(y, "y");
  requireFinite(facing, "facing");
  if (!mechanics || typeof mechanics !== "object") {
    throw new TypeError("Champion mechanics are required");
  }

  const unitMaster = requireSafeInteger(mechanics.unit_master, "Champion mechanics unit master");
  if (unitMaster !== CHAMPION_MASTER) {
    throw new RangeError(`Champion mechanics must use master ${CHAMPION_MASTER}`);
  }
  const hp = requireFinite(mechanics.hp, "Champion mechanics hp");
  if (hp <= 0) throw new RangeError("Champion mechanics hp must be positive");
  if (hp !== CHAMPION_HP) {
    throw new RangeError(`Champion mechanics must use ${CHAMPION_HP} HP`);
  }

  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    facing,
    mechanics,
    unitMaster,
    hp,
    alive: true,
    targetId: null,
    action: "idle",
    actionTimers: freezeTimers(actionTimers),
  });
}
