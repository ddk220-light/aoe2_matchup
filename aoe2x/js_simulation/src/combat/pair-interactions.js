import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
const VALID_CONTACT_RESERVATION_KINDS = new Set([
  "allied-transit",
  "ranged-ingress",
  "enemy-transit",
  "engagement-contact",
  "shallow-contact",
  "releasing",
]);
const VALID_SNAPSHOT_OPTIONS = new Set(["contactReservations"]);


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function requireExtent(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  if (value < 0) throw new RangeError(`${name} must be nonnegative`);
  return value;
}


function requireBoolean(value, name) {
  if (typeof value !== "boolean") throw new TypeError(`${name} must be a boolean`);
  return value;
}


function validateCanonicalPairKey(key, name) {
  if (typeof key !== "string") throw new TypeError(`${name} key must be a string`);
  const match = /^(\d+):(\d+)$/.exec(key);
  if (!match) throw new TypeError(`${name} key must be canonical`);
  const left = Number(match[1]);
  const right = Number(match[2]);
  requireReferenceId(left, `${name} left reference ID`);
  requireReferenceId(right, `${name} right reference ID`);
  if (left >= right || dynamicPairKey(left, right) !== key) {
    throw new TypeError(`${name} key must be canonical`);
  }
}


function normalizeContactReservations(value) {
  if (!(value instanceof Map)) throw new TypeError("contact reservations must be a Map");
  const result = new Map();
  for (const [key, reservation] of value) {
    validateCanonicalPairKey(key, "contact reservation");
    if (!reservation || typeof reservation !== "object" || Array.isArray(reservation)) {
      throw new TypeError("contact reservation must be an object");
    }
    const leftId = requireReferenceId(reservation.leftId, "contact left ID");
    const rightId = requireReferenceId(reservation.rightId, "contact right ID");
    if (dynamicPairKey(leftId, rightId) !== key) {
      throw new TypeError("contact reservation IDs must match its pair key");
    }
    const kind = reservation.kind;
    if (!VALID_CONTACT_RESERVATION_KINDS.has(kind)) {
      throw new RangeError(`unknown contact reservation kind ${kind}`);
    }
    const collisionExtent = requireExtent(
      reservation.collisionExtent,
      "contact collision extent",
    );
    const attackSurfaceExtent = requireExtent(
      reservation.attackSurfaceExtent,
      "contact attack surface extent",
    );
    if (collisionExtent > attackSurfaceExtent + EPSILON) {
      throw new RangeError("contact collision extent cannot exceed its attack surface extent");
    }
    const initiatorId = reservation.initiatorId === null
      ? null
      : requireReferenceId(reservation.initiatorId, "contact initiator ID");
    const targetId = reservation.targetId === null
      ? null
      : requireReferenceId(reservation.targetId, "contact target ID");
    if (!Number.isSafeInteger(reservation.acquiredTick) || reservation.acquiredTick < 0) {
      throw new TypeError("contact acquired tick must be a nonnegative safe integer");
    }
    result.set(key, Object.freeze({
      leftId,
      rightId,
      kind,
      collisionExtent,
      attackSurfaceExtent,
      pathObstructs: requireBoolean(reservation.pathObstructs, "contact pathObstructs"),
      mayDeepen: requireBoolean(reservation.mayDeepen, "contact mayDeepen"),
      initiatorId,
      targetId,
      acquiredTick: reservation.acquiredTick,
    }));
  }
  return result;
}


function interaction(kind, collisionExtent, pathObstructs,
  attackSurfaceExtent, mayDeepen, reason) {
  return Object.freeze({
    kind,
    collisionExtent,
    pathObstructs,
    attackSurfaceExtent,
    mayDeepen,
    reason,
  });
}


function sourceUnit(body) {
  return body?.unit ?? body;
}


function bodyRadius(body) {
  return Number.isFinite(body?.radius) ? body.radius : collisionRadius(sourceUnit(body));
}


export function dynamicPairKey(leftId, rightId) {
  requireReferenceId(leftId, "left reference ID");
  requireReferenceId(rightId, "right reference ID");
  if (leftId === rightId) throw new RangeError("a dynamic pair requires two references");
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}


export function createPairInteractionSnapshot(options = {}) {
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    throw new TypeError("pair interaction options must be an object");
  }
  for (const name of Object.keys(options)) {
    if (!VALID_SNAPSHOT_OPTIONS.has(name)) {
      throw new RangeError(`unknown pair interaction option ${name}`);
    }
  }
  return Object.freeze({
    contactReservations: normalizeContactReservations(
      options.contactReservations ?? new Map(),
    ),
  });
}


export function resolvePairInteraction(left, right,
  snapshot = createPairInteractionSnapshot()) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("pair interaction snapshot is required");
  }
  const leftUnit = sourceUnit(left);
  const rightUnit = sourceUnit(right);
  const extent = bodyRadius(left) + bodyRadius(right);
  // A formation order assigns every member of the cohort its own destination.
  // The authorized tapes show those ordered allies reforming through one
  // another (including center crossings) instead of treating arrived members
  // as walls. This interaction belongs above inherited reservations: an old
  // release surface must not block a later shared formation order. As soon as
  // either order ends, the unified reservation state publishes the pair's
  // current overlap as monotonically releasing geometry.
  if (leftUnit.owner === rightUnit.owner
      && leftUnit.moveOrder !== undefined && leftUnit.moveOrder !== null
      && rightUnit.moveOrder !== undefined && rightUnit.moveOrder !== null) {
    return interaction(
      "formation-transit",
      0,
      false,
      extent,
      true,
      "shared-allied-formation-order",
    );
  }
  const reservation = snapshot.contactReservations?.get(
    dynamicPairKey(left.referenceId, right.referenceId),
  );
  if (reservation) {
    return interaction(
      reservation.kind,
      reservation.collisionExtent,
      reservation.pathObstructs,
      reservation.attackSurfaceExtent,
      reservation.mayDeepen,
      "unified-contact-reservation",
    );
  }
  return interaction(
    "hard",
    extent,
    true,
    extent,
    false,
    leftUnit.owner === rightUnit.owner
      ? "hard-allied-contact" : "hard-enemy-contact",
  );
}
