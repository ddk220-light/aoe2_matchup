import assert from "node:assert/strict";
import test from "node:test";

import { createKiteState, issueKiteOrders } from "../src/combat/ai-orders.js";
import { placeArmy } from "../src/placement.js";


const HC_PROFILE = Object.freeze({
  beatTicks: 240,
  firstBeatTick: 240,
  moveOffsetTicks: Object.freeze([40, 120, 200]),
  topupOffsetTicks: Object.freeze([]),
  preMoveTicks: Object.freeze([80, 160]),
});


test("kite state preserves a finite positive formation spacing", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    formationSpacingTiles: 0.35,
  });

  assert.equal(state.profile.formationSpacingTiles, 0.35);
});


test("kite state omits absent or invalid formation spacing", () => {
  assert.equal(createKiteState(2, HC_PROFILE).profile.formationSpacingTiles, undefined);
  for (const formationSpacingTiles of [0, -0.1, Number.NaN, Infinity, "0.35"]) {
    const state = createKiteState(2, { ...HC_PROFILE, formationSpacingTiles });
    assert.equal(state.profile.formationSpacingTiles, undefined);
  }
});


test("kite state preserves only translated-offset formation motion", () => {
  const translated = createKiteState(2, {
    ...HC_PROFILE,
    formationMotion: "translated_offsets",
  });
  const unsupported = createKiteState(2, {
    ...HC_PROFILE,
    formationMotion: "rubber_band",
  });

  assert.equal(translated.profile.formationMotion, "translated_offsets");
  assert.equal(unsupported.profile.formationMotion, undefined);
  assert.equal(createKiteState(2, HC_PROFILE).profile.formationMotion, undefined);
});


test("kite state preserves a separate scenario opening without shifting its beat", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    openingVolleyTick: 1,
    openingVolley: "close_to_fire",
  });

  assert.equal(state.profile.openingVolleyTick, 1);
  assert.equal(state.profile.firstBeatTick, 240);
  assert.equal(state.nextBeat, 240);
});


test("separate opening independently attacks each unit's nearest reachable target", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    openingVolleyTick: 1,
    openingVolley: "close_to_fire",
  });
  const makeUnit = (referenceId, owner, x, y) => ({
    referenceId,
    owner,
    alive: true,
    x,
    y,
    action: "idle",
    actionTimers: { acquire: 12, windup: 0, reload: 0, swing: 0 },
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    mechanics: owner === 2 ? {
      line_of_sight_tiles: 10,
      attack_range_tiles: 5,
      collision_size_tiles: { x: 0.2, y: 0.2 },
      outline_size_tiles: { x: 0.2, y: 0.2 },
      ranged: { min_range_tiles: 0 },
    } : {
      line_of_sight_tiles: 5,
      attack_range_tiles: 0,
      collision_size_tiles: { x: 0.2, y: 0.2 },
      outline_size_tiles: { x: 0.2, y: 0.2 },
    },
  });
  const kiters = [
    makeUnit(1, 2, 4, 4),
    makeUnit(2, 2, 9, 4),
    makeUnit(3, 2, 14, 1),
  ];
  const enemies = [
    makeUnit(10, 3, 5, 8),
    makeUnit(11, 3, 10, 8),
  ];
  const events = [];

  issueKiteOrders(
    state,
    [...kiters, ...enemies],
    { width: 16, height: 16 },
    1,
    events,
    (tick, type, actorId, targetId, extra = {}) => ({
      tick, type, actorId, targetId, ...extra,
    }),
  );

  assert.deepEqual(kiters.map(({ pursuitTargetId }) => pursuitTargetId), [10, 11, null]);
  assert.deepEqual(kiters.map(({ actionTimers }) => actionTimers.acquire), [0, 0, 12]);
  assert.deepEqual(events.map(({ type, actorId, targetId }) => ({
    type, actorId, targetId,
  })), [
    { type: "ai-order", actorId: 1, targetId: 10 },
    { type: "ai-order", actorId: 2, targetId: 11 },
  ]);
  assert.deepEqual(state.lastTargetIds, []);
  assert.equal(state.nextBeat, 240);
});


test("half-roster melee wave orders only the high half of the chaser roster", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    meleeWave: "half_roster",
  });
  const makeUnit = (referenceId, owner, x) => ({
    referenceId,
    owner,
    alive: true,
    x,
    y: owner === 2 ? 4 : 9,
    action: "idle",
    actionTimers: { acquire: 0, windup: 0, reload: 0, swing: 0 },
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
  });
  const kiters = [makeUnit(1, 2, 4), makeUnit(2, 2, 5)];
  const chasers = Array.from({ length: 6 }, (_, index) => makeUnit(10 + index, 3, index));

  issueKiteOrders(
    state,
    [...kiters, ...chasers],
    { width: 16, height: 16 },
    36,
    [],
    (tick, type, actorId, targetId, extra = {}) => ({
      tick, type, actorId, targetId, ...extra,
    }),
  );

  assert.equal(state.profile.meleeWave, "half_roster");
  assert.deepEqual([...state.meleeActive], [13, 14, 15]);
  assert.deepEqual(chasers.map(({ pursuitTargetId }) => pursuitTargetId), [
    null, null, null, 1, 2, 1,
  ]);
});


test("ordinary ranged opponents are not assigned the melee opening wave", () => {
  const state = createKiteState(2, HC_PROFILE);
  state.opponentMode = "ordinary-ranged";
  const makeUnit = (referenceId, owner, x) => ({
    referenceId,
    owner,
    alive: true,
    x,
    y: owner === 2 ? 4 : 9,
    action: "idle",
    actionTimers: { acquire: 0, windup: 0, reload: 0, swing: 0 },
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
  });
  const kiters = [makeUnit(1, 2, 4), makeUnit(2, 2, 5)];
  const opponents = [makeUnit(10, 3, 4), makeUnit(11, 3, 5)];
  const events = [];

  issueKiteOrders(
    state,
    [...kiters, ...opponents],
    { width: 16, height: 16 },
    36,
    events,
    (tick, type, actorId, targetId, extra = {}) => ({
      tick, type, actorId, targetId, ...extra,
    }),
  );

  assert.equal(state.meleeAssigned, false);
  assert.deepEqual(opponents.map(({ pursuitTargetId }) => pursuitTargetId), [null, null]);
  assert.deepEqual(events, []);
});


test("location-approach melee wave preserves static tape positions until LOS acquisition", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    meleeWave: "location_approach",
  });
  const makeUnit = (referenceId, owner, x) => ({
    referenceId,
    owner,
    alive: true,
    x,
    y: owner === 2 ? 4 : 12,
    action: "idle",
    actionTimers: { acquire: 0, windup: 0, reload: 0, swing: 0 },
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
  });
  const kiters = [makeUnit(1, 2, 4), makeUnit(2, 2, 5)];
  const chasers = Array.from({ length: 6 }, (_, index) => makeUnit(10 + index, 3, index));

  issueKiteOrders(
    state,
    [...kiters, ...chasers],
    { width: 16, height: 16 },
    36,
    [],
    (tick, type, actorId, targetId, extra = {}) => ({
      tick, type, actorId, targetId, ...extra,
    }),
  );

  assert.equal(state.profile.meleeWave, "location_approach");
  assert.deepEqual([...state.meleeApproach.entries()], [
    [14, { x: 4, y: 4 }],
    [15, { x: 5, y: 4 }],
  ]);
  assert.deepEqual([...state.meleeActive], []);
  assert.deepEqual(chasers.map(({ pursuitTargetId }) => pursuitTargetId), [
    null, null, null, null, null, null,
  ]);
});


test("translated-offset motion preserves the formation's relative destinations", () => {
  const state = createKiteState(2, {
    ...HC_PROFILE,
    formationMotion: "translated_offsets",
  });
  const units = [
    { referenceId: 1, owner: 2, alive: true, x: 7, y: 7, action: "idle" },
    { referenceId: 2, owner: 2, alive: true, x: 9, y: 7, action: "idle" },
    { referenceId: 3, owner: 3, alive: true, x: 8, y: 9, action: "idle" },
  ];

  issueKiteOrders(state, units, { width: 16, height: 16 }, 80, [], (
    tick, type, actorId, targetId, extra,
  ) => ({ tick, type, actorId, targetId, ...extra }));

  assert.ok(units[0].moveOrder);
  assert.ok(units[1].moveOrder);
  assert.equal(units[1].moveOrder.x - units[0].moveOrder.x, 2);
  assert.equal(units[1].moveOrder.y - units[0].moveOrder.y, 0);
});


test("default formation slots derive their spacing from the unit collision diameter", () => {
  const state = createKiteState(2, HC_PROFILE);
  const makeUnit = (referenceId, owner, x, y) => ({
    referenceId,
    owner,
    alive: true,
    x,
    y,
    action: "idle",
    mechanics: {
      collision_size_tiles: { x: 0.2, y: 0.2 },
    },
  });
  const units = [
    makeUnit(1, 2, 4, 4),
    makeUnit(2, 2, 5, 4),
    makeUnit(3, 2, 4, 5),
    makeUnit(4, 2, 5, 5),
    makeUnit(10, 3, 8, 10),
  ];

  issueKiteOrders(
    state,
    units,
    { width: 16, height: 16 },
    80,
    [],
    (tick, type, actorId, targetId, extra = {}) => ({
      tick, type, actorId, targetId, ...extra,
    }),
  );

  const destinations = units.slice(0, 4).map(({ moveOrder }) => moveOrder);
  const pairDistances = [];
  for (let left = 0; left < destinations.length; left += 1) {
    for (let right = left + 1; right < destinations.length; right += 1) {
      pairDistances.push(Math.hypot(
        destinations[left].x - destinations[right].x,
        destinations[left].y - destinations[right].y,
      ));
    }
  }
  assert.ok(Math.abs(Math.min(...pairDistances) - 0.4) < 1e-9);
});


test("kite state preserves only the supported closing-opening volley", () => {
  const closing = createKiteState(2, {
    ...HC_PROFILE,
    openingVolley: "close_to_fire",
  });
  const unsupported = createKiteState(2, {
    ...HC_PROFILE,
    openingVolley: "teleport_shot",
  });

  assert.equal(closing.profile.openingVolley, "close_to_fire");
  assert.equal(unsupported.profile.openingVolley, undefined);
  assert.equal(createKiteState(2, HC_PROFILE).profile.openingVolley, undefined);
});


test("kite state preserves only the supported persistent volley pursuit", () => {
  const closing = createKiteState(2, {
    ...HC_PROFILE,
    volleyPursuit: "close_to_fire",
  });
  const unsupported = createKiteState(2, {
    ...HC_PROFILE,
    volleyPursuit: "ignore_range",
  });

  assert.equal(closing.profile.volleyPursuit, "close_to_fire");
  assert.equal(unsupported.profile.volleyPursuit, undefined);
  assert.equal(createKiteState(2, HC_PROFILE).profile.volleyPursuit, undefined);
});


test("solo owner-2 Hand Cannoneers keep receiving the measured kite movement cadence", () => {
  const handCannoneerProfile = {
    beatTicks: 240,
    firstBeatTick: 12,
    formationMotion: "translated_offsets",
    moveOffsetTicks: [68, 148, 228],
    preMoveTicks: [],
    topupOffsetTicks: [],
    volleyPursuit: "close_to_fire",
  };
  const state = createKiteState(2, handCannoneerProfile, false, false, true);
  const units = placeArmy({ owner: 2, count: 21, family: "kite" })
    .map((cell, index) => ({
      referenceId: 9000 + index,
      owner: 2,
      alive: true,
      x: cell.x,
      y: cell.y,
      action: "idle",
      actionTimers: { acquire: 0, windup: 0, reload: 0, swing: 0 },
      pursuitTargetId: null,
      engagedTargetId: null,
      attackTargetId: null,
      avoidance: null,
    }));
  const events = [];
  const makeEvent = (tick, type, actorId, targetId, extra = {}) => ({
    tick, type, actorId, targetId, ...extra,
  });

  for (let tick = 1; tick <= 480; tick += 1) {
    issueKiteOrders(state, units, { width: 16, height: 16 }, tick, events, makeEvent);
  }

  const moveEvents = events.filter(({ type }) => type === "kite-move");
  assert.deepEqual([...new Set(moveEvents.map(({ tick }) => tick))], [80, 160, 240, 320, 400, 480]);
  assert.equal(moveEvents.length, 21 * 6);
  assert.equal(state.ringDirection, 1);
  assert.equal(units.every(({ moveOrder }) => Number.isFinite(moveOrder?.x)
    && Number.isFinite(moveOrder?.y)), true);
});
