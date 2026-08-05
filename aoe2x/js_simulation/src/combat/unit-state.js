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
  const hp = requireFinite(mechanics.hp, "Champion mechanics hp");
  if (hp <= 0) throw new RangeError("Champion mechanics hp must be positive");

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
