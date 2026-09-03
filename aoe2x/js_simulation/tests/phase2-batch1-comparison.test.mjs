import assert from "node:assert/strict";
import test from "node:test";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  runPhase2Batch1Sample,
  scenarioFromPhase2Batch1Row,
} from "../src/phase2-batch1-comparison.js";
import {
  runPhase2Batch1Suite,
  runSchedule,
} from "../tools/run_phase2_batch1_suite.mjs";
import {
  mergePhase2Batch1RowReports,
  validatePhase2Batch1RowReport,
} from "../tools/run_recoverable_phase2_batch1.mjs";
import { TICKS_PER_SECOND } from "../src/simulation-clock.js";
import { collisionRadius, isWithinReach } from "../src/combat/targeting.js";


const ROOT = new URL("../", import.meta.url);


function firstFourWayOverlap(units) {
  const overlaps = (left, right) => Math.max(
    Math.abs(left.x - right.x),
    Math.abs(left.y - right.y),
  ) < collisionRadius(left) * left.mechanics.min_collision_size_multiplier
    + collisionRadius(right) * right.mechanics.min_collision_size_multiplier
    - (left.mechanics.speed_tiles_per_second
      + right.mechanics.speed_tiles_per_second) / TICKS_PER_SECOND
    - 1e-12;
  for (let a = 0; a < units.length; a += 1) {
    for (let b = a + 1; b < units.length; b += 1) {
      if (!overlaps(units[a], units[b])) continue;
      for (let c = b + 1; c < units.length; c += 1) {
        if (!overlaps(units[a], units[c]) || !overlaps(units[b], units[c])) continue;
        for (let d = c + 1; d < units.length; d += 1) {
          if ([a, b, c].every((index) => overlaps(units[index], units[d]))) {
            return [units[a], units[b], units[c], units[d]]
              .map(({ referenceId }) => referenceId);
          }
        }
      }
    }
  }
  return null;
}


test("Phase 2 schedule uses five stable samples and at most fifteen knife-edge samples", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const schedule = runSchedule(truth.rows);
  assert.equal(schedule.filter(({ tape }) => tape.volatile).length, 120);
  assert.equal(schedule.filter(({ tape }) => !tape.volatile).length, 560);
  assert.equal(schedule.length, 680);
  assert.throws(
    () => runSchedule(truth.rows, { samples: 5, volatileSamples: 16 }),
    /capped at 15 samples/,
  );
});


test("tape-normalized melee-versus-ranged rows keep the ranged kiter on owner 2", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_woad_raider_vs_arbalester");
  assert.equal(row.side2.slug, "arbalester");
  assert.equal(row.side3.slug, "elite_woad_raider");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex: 0, seed: 20260817, context });
  assert.equal(scenario.kiteOwner, 2);
  assert.equal(scenario.kiteNavigation, "cohesive");
  assert.equal(scenario.kiteProfile.firstBeatTick, 120);
  assert.equal(scenario.kiteProfile.openingVolleyTick, 1);
  assert.equal(scenario.kiteMeleeOpeningOrder, "attack-move-all");
  assert.equal(scenario.kiteChaseDwellTicks, 0);
  assert.equal(scenario.preventiveContactSteering, true);
});


test("Phase 2 melee chasers use persistent pursuit routing outside the viewer", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const boyarRow = truth.rows.find(({ id }) => id === "elite_boyar_vs_heavy_cav_archer");
  const rangedRow = truth.rows.find(({ id }) => id === "elite_longbowman_vs_arbalester");
  const boyarScenario = scenarioFromPhase2Batch1Row({
    row: boyarRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const rangedScenario = scenarioFromPhase2Batch1Row({
    row: rangedRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });

  assert.equal(boyarScenario.persistentMeleePursuitRouting, true);
  assert.equal(rangedScenario.persistentMeleePursuitRouting, undefined);
});


test("Janissary-Elephant melee pursuit never loses a chase step to dynamic congestion", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const truth = await loadPhase2Batch1Truth(ROOT);
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const row = truth.rows.find(({ id }) => id === "elite_janissary_vs_elite_elephant");
  const scenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const elephantIds = new Set(scenario.units
    .filter(({ owner }) => owner === 3)
    .map(({ referenceId }) => referenceId));
  let world = createWorld(scenario);

  for (let elapsed = 0; elapsed < 5000; elapsed += 1) {
    const beforeById = new Map(world.units.map((unit) => [unit.referenceId, unit]));
    let next;
    try {
      next = stepWorld(world);
    } catch (error) {
      error.message = `tick ${world.tick + 1}: ${error.message}`;
      throw error;
    }
    const afterById = new Map(next.units.map((unit) => [unit.referenceId, unit]));
    for (const referenceId of elephantIds) {
      const before = beforeById.get(referenceId);
      const after = afterById.get(referenceId);
      const target = beforeById.get(before?.pursuitTargetId);
      const targetAfter = afterById.get(before?.pursuitTargetId);
      if (!before?.alive || !after?.alive || !target?.alive || !targetAfter?.alive
          || before.action === "attacking" || isWithinReach(before, target)) continue;
      if (after.engagedTargetId === target.referenceId || isWithinReach(after, targetAfter)) {
        continue;
      }
      const displacement = Math.hypot(after.x - before.x, after.y - before.y);
      const fullStep = before.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
      assert.ok(
        displacement >= fullStep * 0.9,
        `elephant ${referenceId} was effectively stalled at tick ${next.tick}: `
          + `${displacement} < ${fullStep * 0.9}`,
      );
      // Direction is intentionally not asserted here: a hard enemy body, map
      // corner, or four-ally decongestion escape may require a lateral/outward
      // tick. The invariant is continuous sourced-speed motion plus the hard
      // four-body limit below; pursuit recomputes the shortest route next tick.
    }
    const fourWay = firstFourWayOverlap(next.units.filter((unit) => (
      unit.alive && elephantIds.has(unit.referenceId)
    )));
    assert.equal(
      fourWay,
      null,
      `four elephants form a deep pile at tick ${next.tick}: ${fourWay?.join(", ")}; `
        + `positions=${JSON.stringify(next.units.filter(({ referenceId }) => (
          fourWay?.includes(referenceId)
        )).map((unit) => ({
          referenceId: unit.referenceId,
          x: unit.x,
          y: unit.y,
          radius: collisionRadius(unit),
          floor: unit.mechanics.min_collision_size_multiplier,
          pursuitTargetId: unit.pursuitTargetId,
        })))}; `
        + `blocked=${JSON.stringify(next.events.filter((event) => (
          event.type === "blocked" && fourWay?.includes(event.actorId)
        )))}`,
    );
    world = next;
    if (new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner)).size <= 1) {
      break;
    }
  }
  assert.equal(
    new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner)).size,
    1,
    "the exact reproduction must resolve within 5,000 ticks",
  );
});


test("Phase 2 ranged-melee rows begin with the recorded opening volley", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const context = await loadPhase2Batch1Context(ROOT, truth);
  for (const [rowId, recurringFirstBeat] of [
    ["elite_janissary_vs_champion", 240],
    ["elite_conquistador_vs_champion", 200],
    ["elite_longbowman_vs_champion", 120],
  ]) {
    const row = truth.rows.find(({ id }) => id === rowId);
    const scenario = scenarioFromPhase2Batch1Row({
      row,
      sampleIndex: 0,
      seed: 20260817,
      context,
    });
    assert.equal(scenario.kiteProfile.firstBeatTick, recurringFirstBeat, rowId);
    assert.equal(scenario.kiteProfile.openingVolleyTick, 1, rowId);
    assert.equal(scenario.kiteProfile.openingVolley, "close_to_fire", rowId);
  }
});


test("melee-versus-melee rows request generic steering without selecting owners", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_keshik_vs_champion");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex: 0, seed: 20260817, context });

  assert.equal(scenario.preventiveContactSteering, true);
});


test("swapping melee player numbers leaves the physical trajectory unchanged", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_keshik_vs_champion");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const originalScenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const swappedScenario = Object.freeze({
    ...originalScenario,
    units: Object.freeze(originalScenario.units.map((unit) => Object.freeze({
      ...unit,
      owner: unit.owner === 2 ? 3 : 2,
    }))),
  });
  let original = createWorld(originalScenario);
  let swapped = createWorld(swappedScenario);
  for (let tick = 0; tick < 300; tick += 1) {
    original = stepWorld(original);
    swapped = stepWorld(swapped);
  }
  const physicalState = (world) => world.units.map(({
    owner,
    relationByOwner,
    ...unit
  }) => unit);
  const canonicalEvents = (world) => [...world.eventLog]
    .toSorted((left, right) => left.id.localeCompare(right.id));

  assert.deepEqual(physicalState(swapped), physicalState(original));
  assert.deepEqual(canonicalEvents(swapped), canonicalEvents(original));
});


test("ranged-versus-ranged rows reproduce the ordered owner-2 shoot-and-move side", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_longbowman_vs_arbalester");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex: 0, seed: 20260817, context });
  const world = stepWorld(createWorld(scenario));
  const owner2 = world.units.filter(({ owner }) => owner === 2);
  const owner3 = world.units.filter(({ owner }) => owner === 3);
  const targetLoads = [...owner2.reduce((loads, unit) => {
    loads.set(unit.pursuitTargetId, (loads.get(unit.pursuitTargetId) ?? 0) + 1);
    return loads;
  }, new Map()).values()].sort((left, right) => left - right);

  assert.equal(scenario.openingAttackOwners, undefined);
  assert.equal(scenario.kiteOwner, 2);
  assert.equal(scenario.kiteOpponentMode, "ordinary-ranged");
  assert.equal(scenario.kiteProfile.openingVolleyTick, 1);
  assert.equal(scenario.kiteProfile.firstBeatTick, 120);
  assert.deepEqual(scenario.kiteProfile.preMoveTicks, [80]);
  assert.deepEqual(scenario.kiteProfile.moveOffsetTicks, [40]);
  assert.equal(owner2.every(({ pursuitTargetId }) => Number.isSafeInteger(pursuitTargetId)), true);
  assert.equal(owner3.every(({ pursuitTargetId }) => pursuitTargetId === null), true);
  assert.deepEqual(targetLoads, [6, 14]);
  assert.equal(
    world.eventLog.filter(({ type }) => type === "ai-order").length,
    owner2.length,
  );
});


test("a shorter-range subject remains in ordinary ranged-versus-ranged combat", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_gbeto_vs_heavy_cav_archer");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });

  assert.equal(row.subject_slug, "elite_gbeto");
  assert.equal(row.side3.slug, "elite_gbeto");
  assert.equal(scenario.kiteOwner, undefined);
  assert.equal(scenario.kiteOpponentMode, undefined);
  assert.equal(scenario.rangedTargetPressureOwner, 3);
  assert.equal("rangedOpportunityRetargetOwner" in scenario, false);
  assert.equal("rangedWindupRetargetOwner" in scenario, false);
});


test("ordinary ranged ingress lets a rear Conquistador cross a front ally's collision extent", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_conquistador_vs_arbalester");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  let world = createWorld(scenario);
  let minimumSeparation = Number.POSITIVE_INFINITY;
  let observedIngress = false;

  for (let tick = 0; tick < 1800; tick += 1) {
    world = stepWorld(world);
    observedIngress ||= [...world.contactReservationState.reservations.values()]
      .some(({ kind }) => kind === "ranged-ingress");
    const conquistadors = world.units.filter(({ owner, alive }) => owner === 2 && alive);
    for (let left = 0; left < conquistadors.length; left += 1) {
      for (let right = left + 1; right < conquistadors.length; right += 1) {
        minimumSeparation = Math.min(
          minimumSeparation,
          Math.max(
            Math.abs(conquistadors[left].x - conquistadors[right].x),
            Math.abs(conquistadors[left].y - conquistadors[right].y),
          ),
        );
      }
    }
  }

  assert.equal(observedIngress, true, "the ordinary ranged approach never acquired ingress");
  assert.ok(
    minimumSeparation < 0.5 - 1e-9,
    `Conquistador collision boxes never crossed: minimum separation ${minimumSeparation}`,
  );
});


test("Phase 2 keeps the War Wagon formation and attack-move policy", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const warWagonRow = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_paladin");
  const championRow = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_champion");
  const boyarRow = truth.rows.find(({ id }) => id === "elite_boyar_vs_paladin");
  const warWagonScenario = scenarioFromPhase2Batch1Row({
    row: warWagonRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const boyarScenario = scenarioFromPhase2Batch1Row({
    row: boyarRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const championScenario = scenarioFromPhase2Batch1Row({
    row: championRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });

  assert.equal(warWagonScenario.kiteProfile.formationSpacingTiles, 0.6);
  assert.equal(warWagonScenario.attackMoveStickyPursuit, true);
  assert.equal(warWagonScenario.attackMoveTargetPressureTiles, 0.5);
  assert.equal(championScenario.kiteProfile.formationSpacingTiles, 0.6);
  assert.equal(championScenario.attackMoveTargetPressureTiles, 0.4);
  assert.equal(boyarScenario.attackMoveStickyPursuit, undefined);
});


test("one Phase 2 sample runs from the exact golden starting roster", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_boyar_vs_champion");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const sample = runPhase2Batch1Sample({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  assert.equal(sample.rowId, row.id);
  assert.equal(sample.sampleIndex, 0);
  assert.ok(["win", "timeout"].includes(sample.outcome));
  assert.ok(sample.outcome === "timeout" || Number.isFinite(sample.score));
});


test("recoverable row reports preserve the five/fifteen sample policy and knife-edge label", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const rowIds = ["elite_longbowman_vs_champion", "elite_woad_raider_vs_paladin"];
  const reports = [];
  for (const rowId of rowIds) {
    reports.push(await runPhase2Batch1Suite({
      truth,
      context: {},
      rowIds: [rowId],
      runImpl: ({ row, sampleIndex, seed }) => ({
        rowId: row.id,
        sampleIndex,
        seed,
        outcome: "win",
        winnerOwner: row.runs[0].winner_owner,
        winnerHp: row.runs[0].winner_hp,
        score: row.runs[0].signed_score,
        ticks: 1,
      }),
    }));
  }
  assert.equal(validatePhase2Batch1RowReport(reports[0], rowIds[0]), true);
  assert.equal(validatePhase2Batch1RowReport(reports[1], rowIds[1]), true);
  const merged = mergePhase2Batch1RowReports(reports, rowIds);
  assert.equal(merged.schedule.stableRows, 1);
  assert.equal(merged.schedule.volatileRows, 1);
  assert.equal(merged.schedule.totalRuns, 20);
  assert.equal(merged.summary.knifeEdgeRows, 1);
  assert.equal(merged.rows.find(({ id }) => id === rowIds[1]).tapeClassification, "knife-edge");
});
