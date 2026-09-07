// Browser/Node validation boundary for database-served V3 mechanics.
export const MECHANICS_SCHEMA_VERSION = 1;

const BEHAVIOR_CLASSES = new Set(["melee", "mobile_ranged", "siege_ranged"]);

function requireObject(value, label) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }
  return value;
}

function requireString(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new TypeError(`${label} must be a nonempty string`);
  }
}

function requireFinite(value, label, minimum = -Infinity) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum) {
    throw new TypeError(`${label} must be a finite number >= ${minimum}`);
  }
}

function validateClassMap(value, label) {
  requireObject(value, label);
  if (Object.keys(value).length === 0) throw new TypeError(`${label} must not be empty`);
  for (const [classId, amount] of Object.entries(value)) {
    if (!/^-?\d+$/.test(classId)) throw new TypeError(`${label}.${classId} is not a class id`);
    requireFinite(amount, `${label}.${classId}`);
  }
}

export function validateMechanicsProfile(value) {
  const profile = requireObject(value, "mechanics");
  if (profile.mechanics_schema_version !== MECHANICS_SCHEMA_VERSION) {
    throw new RangeError(
      `unsupported mechanics schema ${profile.mechanics_schema_version}; `
      + `expected ${MECHANICS_SCHEMA_VERSION}`,
    );
  }
  for (const key of ["unit_slug", "unit_name", "civilization", "age", "mode"]) {
    requireString(profile[key], key);
  }
  if (!Number.isSafeInteger(profile.unit_master) || profile.unit_master < 0) {
    throw new TypeError("unit_master must be a nonnegative integer");
  }
  if (!BEHAVIOR_CLASSES.has(profile.behavior_class)) {
    throw new RangeError(`invalid behavior_class ${profile.behavior_class}`);
  }
  for (const [key, minimum] of [
    ["hp", 1],
    ["speed_tiles_per_second", 0],
    ["attack_range_tiles", 0],
    ["reload_seconds", 0],
    ["attack_delay_seconds", 0],
    ["line_of_sight_tiles", 0],
    ["population_space", 0],
  ]) requireFinite(profile[key], key, minimum);
  validateClassMap(profile.attack_classes, "attack_classes");
  validateClassMap(profile.armor_classes, "armor_classes");
  const cost = requireObject(profile.cost, "cost");
  for (const resource of ["food", "wood", "gold"]) {
    requireFinite(cost[resource], `cost.${resource}`, 0);
  }
  const animation = requireObject(profile.attack_animation, "attack_animation");
  requireFinite(animation.seconds, "attack_animation.seconds", Number.MIN_VALUE);
  if (profile.attack_delay_seconds > animation.seconds) {
    throw new RangeError("attack delay exceeds attack animation");
  }
  for (const groupName of ["collision_size_tiles", "outline_size_tiles"]) {
    const group = requireObject(profile[groupName], groupName);
    requireFinite(group.x, `${groupName}.x`, 0);
    requireFinite(group.y, `${groupName}.y`, 0);
  }
  if (profile.ranged !== null) {
    const ranged = requireObject(profile.ranged, "ranged");
    for (const key of [
      "projectile_speed_tiles_per_second",
      "min_range_tiles",
      "accuracy_percent",
      "projectile_half_width_tiles",
    ]) requireFinite(ranged[key], `ranged.${key}`, 0);
    if (ranged.accuracy_percent > 100) {
      throw new RangeError("ranged accuracy exceeds 100 percent");
    }
    if (ranged.min_range_tiles > profile.attack_range_tiles) {
      throw new RangeError("minimum range exceeds attack range");
    }
  }
  if ("provenance" in profile || "mode_validation" in profile) {
    throw new TypeError("runtime mechanics must not contain calibration provenance");
  }
  return profile;
}

export function unitDescriptorFromMechanics(profile) {
  validateMechanicsProfile(profile);
  return Object.freeze({
    slug: profile.unit_slug,
    label: profile.unit_name,
    civ: profile.civilization,
    master: profile.unit_master,
    class: profile.behavior_class,
    ...(profile.behavior_family === undefined
      ? {}
      : { behaviorFamily: profile.behavior_family }),
    baseCost: Object.freeze({ ...profile.cost }),
  });
}
