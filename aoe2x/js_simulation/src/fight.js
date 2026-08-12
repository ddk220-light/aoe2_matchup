// One fight, composed from the registry and the derived placement. Nothing
// here reads a recorded roster: this is the path a product request takes.
import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "./canonical-json.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld, stepWorld } from "./combat/world.js";
import {
  requireSoloNavigationVariant,
  SOLO_NAVIGATION_VARIANTS,
} from "./combat/solo-navigation.js";
import { deriveKiteProfile, kitePolicyFor } from "./combat/kite-timing.js";
import { placeArmy, resolveFamily, sideCapacity } from "./placement.js";
import { deriveCounts, PURCHASE_BUDGET } from "./purchase.js";
import { SOLO_MOVEMENT_UNIT_SLUGS, unitBySlug } from "./unit-registry.js";


// Capacity is per (owner, family); this is the largest any of them offers.
// Individual requests are bounded by the real per-(owner, family) capacity
// (see validateCount below), which is never larger than this.
export const FIGHT_SIDE_CAP = 21;

// Movement is fully observable from each snapshot's positions (every unit's
// x/y is already in the units array every tick), and at 60 Hz it is ~97% of
// the event log (measured: 71,469 of 73,810 events in an imp_elite_skirm vs
// halberdier 21v21 fight are move/blocked). Excluding them from the wire
// format is also a UX improvement, not just a size cut: it makes the
// viewer's event cursor step between hits instead of between movement ticks.
// eventLogHash below still hashes the full, unfiltered engine log, so this
// exclusion cannot hide a determinism regression.
const WIRE_EVENT_TYPES_EXCLUDED = Object.freeze(new Set(["move", "blocked"]));

const REFERENCE_BASE = { 2: 9000, 3: 9500 };
const MAX_TICKS = 9000;
const SOLO_MOVEMENT_TICKS = 3600;
const mechanicsCache = new Map();


async function loadMechanics(root, unit) {
  // Keyed on root as well as fixture: two callers pointed at different repo
  // roots (as the test suite and a running server both can be) must not
  // share a cache entry, matching the deliberately root-keyed
  // championDataByRoot in server.mjs.
  const key = `${root}|${unit.fixture}`;
  if (!mechanicsCache.has(key)) {
    mechanicsCache.set(key, JSON.parse(await readFile(
      new URL(`fixtures/unit_stats/${unit.fixture}`, root), "utf8")));
  }
  return mechanicsCache.get(key);
}


function requireUnit(slug) {
  const unit = unitBySlug(slug);
  if (!unit) throw new RangeError(`unknown unit ${slug}`);
  return unit;
}


// Placement capacity is per (owner, family) and asymmetric (a side-2 siege
// block holds only 16 cells; every other owner/family combination holds 21),
// so the global FIGHT_SIDE_CAP alone is not a valid bound for either side --
// deriveCounts can otherwise hand a side more units than its own placement
// block can seat, and an explicit n2/n3 can ask for the same thing directly.
//
// `owner` here is the INTERNAL owner the unit runs as, which for the two
// role-asymmetric families is not necessarily the dropdown the user picked it
// in -- so the offending unit is named too, or the message is unactionable.
function validateCount(count, capacity, family, owner, slug) {
  if (!Number.isSafeInteger(count) || count < 1 || count > capacity) {
    throw new RangeError(
      `count must be an integer 1-${capacity} for owner ${owner}'s ${family} `
      + `formation, got ${count} (${slug} runs as owner ${owner} in a ${family} fight)`);
  }
}


// Exactly one mobile-ranged side kites. That is the rule the archive follows in
// all 32 calibrated kiting matchups; siege never kites, and two mobile-ranged
// sides are the unmodelled ranged-vs-ranged case, which runs natively.
function kiteOwnerFor(side2, side3) {
  const two = side2.class === "mobile_ranged";
  const three = side3.class === "mobile_ranged";
  if (two === three) return null;
  return two ? 2 : 3;
}


// Two of the four spawn families are ROLE blocks, not side blocks: in the
// archive the kiter is owner 2 in 32 of 32 kiting matchups and the siege unit
// is owner 2 in 16 of 16 siege-vs-melee matchups, so `2@kite` and `2@siege`
// are the kiter's and the siege unit's own recorded footprints. Running the
// fight in dropdown order therefore puts, say, archers into the chasers'
// geometry the moment the user picks them second, and the fight changes
// materially (measured: 18 arbalesters vs 21 champions ran 2548 ticks / 430 HP
// one way and 2782 / 355 the other). Every asymmetric fight is run with the
// role unit as owner 2 -- the measured orientation -- and relabelled on the
// way out. `rvr` and `waves` have no role asymmetry and are left alone.
const ROLE_CLASS_BY_FAMILY = Object.freeze({
  kite: "mobile_ranged",
  siege: "siege_ranged",
});


// resolveFamily guarantees exactly one side carries the role class in these
// two families (two mobile-ranged or two siege-ranged sides both resolve to
// `rvr` instead), so "is the role unit the user's side 3?" is well defined.
function orientationNormalisedFor(family, side2, side3) {
  const roleClass = ROLE_CLASS_BY_FAMILY[family];
  if (roleClass === undefined) return false;
  return side3.class === roleClass;
}


// The recurring kiting cycle is mechanics, not a per-unit calibration row:
// reload and projectile-release delay are snapped onto the recorded 40-tick
// AI command grid. A small policy table retains only choices mechanics cannot
// answer (opening phase, bookkeeping top-up, formation behavior). The
// generated tape profiles remain regression oracles in tests.
function kiteProfileFor(unit, mechanics) {
  return deriveKiteProfile(mechanics, kitePolicyFor(unit.slug));
}


// Same key names and freezing the viewer's cursor and renderer already demand
// (tick === index, frozen units array, frozen events array). Only the per-unit
// record changes: a positional array instead of an object carrying the whole
// mechanics fixture, which was 85% of the payload. facing is included because
// it changes every tick (the renderer's direction arrow); the per-type fields
// the renderer also needs -- unit master, collision radius, attack range --
// do not change per tick, so they live once in unitIndex instead.
function slimSnapshot(snapshot) {
  return Object.freeze({
    tick: snapshot.tick,
    units: Object.freeze(snapshot.units.map((unit) => Object.freeze([
      unit.referenceId,
      unit.x,
      unit.y,
      unit.facing,
      unit.hp,
      unit.alive ? 1 : 0,
      unit.action,
      unit.pursuitTargetId,
      unit.engagedTargetId,
      unit.attackTargetId,
    ]))),
    events: Object.freeze(
      snapshot.events.filter((entry) => !WIRE_EVENT_TYPES_EXCLUDED.has(entry.type)),
    ),
    ...(snapshot.navigation ? { navigation: snapshot.navigation } : {}),
  });
}


function soloNavigationSummary(world, count) {
  const diagnostics = world.snapshots
    .map(({ navigation }) => navigation)
    .filter(Boolean);
  const final = diagnostics.at(-1);
  return Object.freeze({
    unitCount: count,
    totalAnchorDistance: final?.totalAnchorDistance ?? 0,
    maxReplans: diagnostics.reduce((maximum, row) => Math.max(maximum, row.replans), 0),
    maxCohesionRadius: diagnostics.reduce(
      (maximum, row) => Math.max(maximum, row.cohesionRadius), 0,
    ),
    maxSlotError: diagnostics.reduce((maximum, row) => Math.max(maximum, row.maxSlotError), 0),
    maxBlockedCount: diagnostics.reduce((maximum, row) => Math.max(maximum, row.blockedCount), 0),
  });
}


export async function runFight(root, { side2Slug, n2, side3Slug, n3, budget, map }) {
  // Counts are optional: omit BOTH and they come from the purchase rule, so
  // the formula lives in purchase.js and nowhere else. One given without the
  // other is a malformed request, not a half-derived fight -- the HTTP layer
  // already rejects that shape (server.mjs fightSelection); this guards the
  // module entry point the same way for any other caller.
  const n2Given = n2 !== undefined;
  const n3Given = n3 !== undefined;
  if (n2Given !== n3Given) {
    throw new RangeError("n2 and n3 must both be given, or both omitted to derive them");
  }
  const budgetGiven = budget !== undefined;
  if (budgetGiven && (!Number.isSafeInteger(budget) || budget < 100 || budget > 20000)) {
    throw new RangeError(`budget must be an integer 100-20000, got ${budget}`);
  }
  if (budgetGiven && n2Given) {
    throw new RangeError("budget cannot be combined with explicit counts");
  }
  const derivedCounts = !n2Given;
  const purchaseBudget = budgetGiven ? budget : PURCHASE_BUDGET;

  const side2 = requireUnit(side2Slug);
  const side3 = requireUnit(side3Slug);

  // Family (and therefore each side's placement capacity) depends only on
  // the two units' combat classes, never on the counts -- so it is resolved
  // before deriveCounts runs, and its capacities are fed into deriveCounts
  // as the ceiling on what the purchase rule may hand out.
  const family = resolveFamily({ side2Class: side2.class, side3Class: side3.class });

  // INTERNAL orientation. `inner2`/`inner3` are what the engine runs; `side2`
  // and `side3` stay the user's picks and are what the response reports.
  const orientationNormalised = orientationNormalisedFor(family, side2, side3);
  const inner2 = orientationNormalised ? side3 : side2;
  const inner3 = orientationNormalised ? side2 : side3;
  const capacity2 = sideCapacity(2, family);
  const capacity3 = sideCapacity(3, family);

  // Both the purchase rule and the capacity ceilings are applied in the
  // internal orientation, so the same pairing at the same counts derives the
  // same armies and passes (or fails) the same capacity check whichever
  // dropdown each unit was picked in.
  const derived = derivedCounts
    ? deriveCounts(inner2.slug, inner3.slug, {
      budget: purchaseBudget, capacityA: capacity2, capacityB: capacity3,
    })
    : null;
  const innerCount2 = derived ? derived.countA : (orientationNormalised ? n3 : n2);
  const innerCount3 = derived ? derived.countB : (orientationNormalised ? n2 : n3);
  validateCount(innerCount2, capacity2, family, 2, inner2.slug);
  validateCount(innerCount3, capacity3, family, 3, inner3.slug);
  const count2 = orientationNormalised ? innerCount3 : innerCount2;
  const count3 = orientationNormalised ? innerCount2 : innerCount3;

  const [mechanics2, mechanics3] = await Promise.all([
    loadMechanics(root, inner2),
    loadMechanics(root, inner3),
  ]);

  const roster = [
    ...placeArmy({ owner: 2, count: innerCount2, family })
      .map((cell, index) => ({ owner: 2, cell, index, unit: inner2, mechanics: mechanics2 })),
    ...placeArmy({ owner: 3, count: innerCount3, family })
      .map((cell, index) => ({ owner: 3, cell, index, unit: inner3, mechanics: mechanics3 })),
  ];

  const units = roster.map(({ owner, cell, index, mechanics }, rank) => createUnitState({
    referenceId: REFERENCE_BASE[owner] + index,
    owner,
    x: cell.x,
    y: cell.y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: roster.length,
  }));

  // Internally the kiter is owner 2 in every kite fight (that is what
  // normalising buys); `kiteOwner` below is the same fact stated in the
  // user's orientation, and the two agree because the response relabels
  // owners rather than renumbering units.
  const innerKiteOwner = kiteOwnerFor(inner2, inner3);
  const kiter = innerKiteOwner === 2 ? inner2 : inner3;
  const result = runWorld(createWorld({
    ratio: `${innerCount2}v${innerCount3}`,
    units,
    ...(map ? { map } : {}),
    ...(innerKiteOwner === null
      ? {}
      : {
        kiteOwner: innerKiteOwner,
        kiteProfile: kiteProfileFor(
          kiter,
          innerKiteOwner === 2 ? mechanics2 : mechanics3,
        ),
      }),
  }), { maxTicks: MAX_TICKS });

  // Owner relabelling. Reference ids stay exactly as the engine allocated
  // them -- the payload never promises an id block belongs to a side, and the
  // viewer resolves every id through unitIndex -- so a normalised fight is
  // reported by swapping the OWNER on each unitIndex row (and on winnerOwner
  // and kiteOwner) and nothing else. finalStateHash / eventLogHash are left on
  // the canonical internal run, which is what makes them equal for the two
  // dropdown orders of the same fight.
  const reportedOwner = orientationNormalised
    ? (owner) => (owner === 2 ? 3 : 2)
    : (owner) => owner;

  const live = result.world.units.filter(({ alive }) => alive);
  const unitIndex = {};
  for (const { owner, index, unit, mechanics } of roster) {
    unitIndex[REFERENCE_BASE[owner] + index] = Object.freeze({
      owner: reportedOwner(owner),
      slug: unit.slug,
      label: unit.label,
      maxHp: mechanics.hp,
      master: mechanics.unit_master,
      collisionRadius: mechanics.collision_size_tiles.x,
      attackRange: mechanics.attack_range_tiles,
    });
  }

  return Object.freeze({
    schemaVersion: 1,
    side2: Object.freeze({
      slug: side2.slug, label: side2.label, civ: side2.civ, count: count2, class: side2.class }),
    side3: Object.freeze({
      slug: side3.slug, label: side3.label, civ: side3.civ, count: count3, class: side3.class }),
    family,
    derivedCounts,
    budget: derivedCounts ? purchaseBudget : null,
    // True when the pair was run in the archive's measured orientation rather
    // than the user's pick order (the role unit always fights as owner 2).
    orientationNormalised,
    kiteOwner: innerKiteOwner === null ? null : reportedOwner(innerKiteOwner),
    ticks: result.ticks,
    winnerOwner: live.length ? reportedOwner(live[0].owner) : null,
    winnerHp: live.reduce((total, unit) => total + unit.hp, 0),
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio: `${innerCount2}v${innerCount3}`,
      units: result.world.units,
    }),
    // Hashes the full, unfiltered engine event log -- not the wire-slimmed
    // per-snapshot events below -- so dropping move/blocked from the payload
    // can never mask a change in what the engine actually did.
    eventLogHash: hashCanonicalJson(result.events),
    unitIndex: Object.freeze(unitIndex),
    snapshots: Object.freeze(result.snapshots.map(slimSnapshot)),
  });
}


export async function runSoloRangedMovement(root, {
  map,
  navigation = "cohesive",
  unitSlug = "hand_cannoneer",
} = {}) {
  requireSoloNavigationVariant(navigation);
  if (!SOLO_MOVEMENT_UNIT_SLUGS.includes(unitSlug)) {
    throw new RangeError(
      `solo movement unit must be one of ${SOLO_MOVEMENT_UNIT_SLUGS.join(", ")}, got ${unitSlug}`,
    );
  }
  const unit = requireUnit(unitSlug);
  const mechanics = await loadMechanics(root, unit);
  const count = 21;
  const owner = 2;
  const family = "kite";
  const roster = placeArmy({ owner, count, family }).map((cell, index) => ({
    owner, cell, index, unit, mechanics,
  }));
  const units = roster.map(({ cell, index }, rank) => createUnitState({
    referenceId: REFERENCE_BASE[owner] + index,
    owner,
    x: cell.x,
    y: cell.y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: roster.length,
  }));
  let world = createWorld({
    ratio: "21v0",
    units,
    ...(map ? { map } : {}),
    kiteOwner: owner,
    kiteProfile: kiteProfileFor(unit, mechanics),
    soloMovement: true,
    soloNavigation: navigation,
  });
  for (let tick = 0; tick < SOLO_MOVEMENT_TICKS; tick += 1) {
    world = stepWorld(world);
  }

  const unitIndex = {};
  for (const { index } of roster) {
    unitIndex[REFERENCE_BASE[owner] + index] = Object.freeze({
      owner,
      slug: unit.slug,
      label: unit.label,
      maxHp: mechanics.hp,
      master: mechanics.unit_master,
      collisionRadius: mechanics.collision_size_tiles.x,
      attackRange: mechanics.attack_range_tiles,
    });
  }
  return Object.freeze({
    schemaVersion: 1,
    mode: "solo-movement",
    navigationVariant: navigation,
    navigationOptions: SOLO_NAVIGATION_VARIANTS,
    navigationSummary: soloNavigationSummary(world, count),
    side2: Object.freeze({
      slug: unit.slug, label: unit.label, civ: unit.civ, count, class: unit.class,
    }),
    side3: Object.freeze({ slug: null, label: "No enemies", civ: "", count: 0, class: null }),
    family,
    derivedCounts: false,
    budget: null,
    orientationNormalised: false,
    kiteOwner: owner,
    ticks: world.tick,
    winnerOwner: null,
    winnerHp: world.units.reduce((total, current) => total + current.hp, 0),
    finalStateHash: hashCanonicalJson({ tick: world.tick, ratio: "21v0", units: world.units }),
    eventLogHash: hashCanonicalJson(world.eventLog),
    unitIndex: Object.freeze(unitIndex),
    snapshots: Object.freeze(world.snapshots.map(slimSnapshot)),
  });
}


// Retain the module-level legacy entry point for callers that intentionally
// request the original default lab without a unit selector.
export async function runSoloHandCannoneerMovement(root, options = {}) {
  return runSoloRangedMovement(root, { ...options, unitSlug: "hand_cannoneer" });
}
