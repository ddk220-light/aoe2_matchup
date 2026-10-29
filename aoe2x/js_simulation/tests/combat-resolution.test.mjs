import assert from "node:assert/strict";
import test from "node:test";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld, runWorld } from "../src/combat/world.js";
import { orderReadyAttacks } from "../src/combat/attacks.js";
import { runHeadlessJob } from "../node/run-job.mjs";

const db = new DatabaseSync(fileURLToPath(new URL(
  "../../../data/golden/aoe2_reference_simulation.db", import.meta.url)), { readOnly: true });
const rows = db.prepare("SELECT u.civ_name,u.unit_slug,m.mechanics_json FROM ref_units u "
  + "JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id WHERE m.is_default=1").all();
db.close();
function profile(civ, slug) {
  return JSON.parse(rows.find(row => row.civ_name === civ && row.unit_slug === slug).mechanics_json);
}
const champion = profile("Spanish", "champion");
const idle = { ...champion, speed_tiles_per_second: 0, attack_delay_seconds: 1000,
  attack_animation: { seconds: 1000 } };
const spawn = (id, owner, x, mechanics = idle, hp = mechanics.hp) => ({
  ...createUnitState({ referenceId: id, owner, x, y: 5, facing: 0, mechanics,
    acquisitionRank: 0, acquisitionCount: 1,
    actionTimers: { acquire: 0, reload: 0, windup: 0, swing: 0 } }), hp,
});
const dead = unit => ({ ...unit, hp: 0, alive: false, action: "dead" });
const changeUnit = (world, id, change) => ({ ...world,
  units: world.units.map(unit => unit.referenceId === id ? change(unit) : unit),
});
function advance(world, ticks) {
  for (let i = 0; i < ticks; i++) world = stepWorld(world);
  return world;
}
function launch(civ = "Varangians", slug = "elite_varangian_guard", overrides = {}) {
  const shooter = { ...profile(civ, slug), speed_tiles_per_second: 0,
    reload_seconds: 1000, ...overrides };
  let world = createWorld({ ratio: "charge-flight", openingSeed: 0,
    units: [spawn(1, 2, 4, shooter), spawn(2, 3, 6)] });
  while (!world.projectiles.some(p => p.kind === "charge") && world.tick < 120) {
    world = stepWorld(world);
  }
  assert.ok(world.projectiles.some(p => p.kind === "charge"), "a real charge was released");
  return world;
}
function aftermath(hp = 10) {
  const world = createWorld({ ratio: "aftermath", units: [
    spawn(1, 2, 4), spawn(2, 3, 6, idle, hp),
  ] });
  return changeUnit(world, 1, dead);
}

test("same-tick lethal melee attacks are seeded, repeatable and do not always favor lower IDs", () => {
  const fast = { ...champion, speed_tiles_per_second: 0, attack_delay_seconds: 0,
    attack_animation: { seconds: 0.1 }, reload_seconds: 1000 };
  const duel = (seed, reverse = false) => {
    const units = [spawn(1, 2, 4, fast, 1), spawn(2, 3, 4.4, fast, 1)];
    return runWorld(createWorld({ ratio: "tie", openingSeed: seed,
      units: reverse ? units.reverse() : units }), { maxTicks: 3 });
  };
  let lowIdWins = 0;
  for (let seed = 0; seed < 256; seed++) {
    const result = duel(seed);
    assert.equal(result.outcome, "win");
    assert.equal(result.ticks, 1);
    lowIdWins += result.winner === 2 ? 1 : 0;
    if (seed < 8) assert.deepEqual(result.events, duel(seed, true).events);
  }
  assert.ok(lowIdWins > 80 && lowIdWins < 176, `lower ID won ${lowIdWins}/256`);
});

test("attack ordering preserves damage-tick chronology and input arrays", () => {
  const attacks = [
    { readyTick: 5, actorId: 3, targetId: 1 },
    { readyTick: 4, actorId: 1, targetId: 2 },
    { readyTick: 4, actorId: 2, targetId: 1 },
  ];
  const copy = structuredClone(attacks);
  const result = orderReadyAttacks(attacks, { seed: 123 });
  assert.deepEqual(result.map(a => a.readyTick), [4, 4, 5]);
  assert.deepEqual(result, orderReadyAttacks([...attacks].reverse(), { seed: 123 }));
  assert.deepEqual(attacks, copy);
});

test("a charged projectile hits a stationary target along its physical path", () => {
  const initial = launch();
  const shot = initial.projectiles.find(p => p.kind === "charge");
  assert.equal(shot.x, 4, "no flight time passes on the release tick");
  const final = advance(initial, shot.arrivalTick - initial.tick);
  const hit = final.eventLog.find(e => e.kind === "charge-projectile" && e.type === "damage");
  assert.ok(hit.tick > shot.firedTick && hit.tick <= shot.arrivalTick);
  assert.equal(hit.amount, shot.amount);
  assert.equal(final.units[1].hp, idle.hp - shot.amount);
});

test("a charged projectile misses a target that leaves its path and expires at its fixed aim", () => {
  for (const destination of [{ x: 6, y: 8 }, { x: 8, y: 5 }]) {
    let world = launch();
    const shot = world.projectiles[0];
    world = changeUnit(world, 2, unit => ({ ...unit, ...destination }));
    world = advance(world, shot.arrivalTick - world.tick + 2);
    assert.equal(world.units[1].hp, idle.hp);
    assert.equal(world.projectiles.length, 0);
    assert.equal(world.eventLog.some(e => e.kind === "charge-projectile"), false);
  }
});

test("charge collision sweeps the whole segment, including fast shots and approaching targets", () => {
  const guard = profile("Varangians", "elite_varangian_guard");
  let world = launch(undefined, undefined, { charge: { ...guard.charge,
    projectile_speed_tiles_per_second: 600 } });
  world = changeUnit(world, 2, unit => ({ ...unit, x: 5,
    mechanics: { ...unit.mechanics, collision_size_tiles: { x: 0.01, y: 0.01 } } }));
  world = stepWorld(world);
  assert.ok(world.units[1].hp < idle.hp, "the target between the step endpoints is hit");
  assert.equal(world.projectiles.length, 0);
});

test("charge damage and Bolas slow require an actual impact", () => {
  for (const dodge of [false, true]) {
    let world = launch("Mapuche", "elite_bolas_rider_mapuche");
    const shot = world.projectiles.find(p => p.kind === "charge");
    if (dodge) world = changeUnit(world, 2, unit => ({ ...unit, y: 8 }));
    world = advance(world, shot.arrivalTick - world.tick + 2);
    assert.equal(world.eventLog.some(e => e.kind === "charge-projectile"), !dodge);
    assert.equal(world.units[1].specialState.slowUntilTick > world.tick, !dodge);
  }
});

test("Fire Lancer physical charges retain armor bypass and their three-projectile volley", () => {
  let world = launch("Chinese", "elite_fire_lancer");
  const shots = world.projectiles.filter(p => p.kind === "charge");
  assert.equal(shots.length, 3);
  world = advance(world, shots[0].arrivalTick - world.tick);
  const hits = world.eventLog.filter(e => e.type === "damage" && e.kind === "charge-projectile");
  assert.equal(hits.length, 3);
  assert.ok(hits.every(e => e.amount === 3));
});

test("already-fired charge can kill the last survivor after its shooter dies, producing a draw", () => {
  for (const retainSnapshots of [true, false]) {
    let world = changeUnit(launch(), 1, dead);
    world = changeUnit(world, 2, unit => ({ ...unit, hp: 1 }));
    const result = runWorld(world, { maxTicks: 60, retainSnapshots });
    assert.equal(result.outcome, "draw");
    assert.equal(result.winner, null);
    assert.ok(result.ticks > world.tick);
    assert.equal(result.world.units.some(u => u.alive), false);
    assert.ok(result.events.some(e => e.kind === "charge-projectile"));
  }
});

test("a nonlethal final projectile is included in winner HP", () => {
  const world = changeUnit(launch(), 1, dead);
  const amount = world.projectiles[0].amount;
  const result = runWorld(world, { maxTicks: 60 });
  assert.equal(result.outcome, "win");
  assert.equal(result.winner, 3);
  assert.equal(result.world.units[1].hp, idle.hp - amount);
});

test("DoT settles through its final damage tick, whether lethal or nonlethal", () => {
  for (const hp of [3, 10]) {
    let world = aftermath(hp);
    world = changeUnit(world, 2, unit => ({ ...unit, specialState: {
      ...unit.specialState, bleedStacks: [{ actorId: 1, damagePerSecond: 60, untilTick: 5 }],
    } }));
    const result = runWorld(world, { maxTicks: 20 });
    assert.equal(result.outcome, hp === 3 ? "draw" : "win");
    assert.equal(result.ticks, Math.min(hp, 5));
    assert.equal(result.world.units[1].hp, Math.max(0, hp - 5));
  }
});

test("delayed explosions and friendly-fire siege shots can change the final outcome", () => {
  for (const kind of ["delayed-impact-explosion", "shell"]) {
    let world = aftermath(1);
    world = { ...world, projectiles: [{ kind, actorId: 1,
      actorOwner: kind === "shell" ? 3 : 2, actorMechanics: idle,
      targetId: 2, aimX: 6, aimY: 5, blastRadius: 1,
      meleeAttack: 20, firedTick: 0, arrivalTick: 5, index: 0 }] };
    const result = runWorld(world, { maxTicks: 20 });
    assert.equal(result.outcome, "draw");
    assert.equal(result.ticks, 5);
  }
});

test("hostile ground damage settles but harmless allied hazards do not delay victory", () => {
  for (const actorOwner of [2, 3]) {
    const world = { ...aftermath(), hazards: [{ actorId: 1, actorOwner,
      x: 6, y: 5, radiusTiles: 1, damagePerSecond: 60,
      startTick: 0, endTick: 5, stacks: false }] };
    const result = runWorld(world, { maxTicks: 20 });
    assert.equal(result.outcome, "win");
    assert.equal(result.ticks, actorOwner === 2 ? 4 : 0);
    assert.equal(result.world.units[1].hp, actorOwner === 2 ? 6 : 10);
  }
});

test("shots whose targets died do not delay a win or give survivors extra regeneration", () => {
  const world = changeUnit(launch(), 2, dead);
  const result = runWorld(world, { maxTicks: 60 });
  assert.equal(result.outcome, "win");
  assert.equal(result.winner, 2);
  assert.equal(result.ticks, world.tick);
});

test("ordinary arrows with zero splash radius cannot delay victory by hurting allies", () => {
  let world = createWorld({ ratio: "harmless-arrow", units: [
    spawn(1, 2, 4), spawn(2, 3, 6), spawn(3, 2, 5),
  ] });
  world = changeUnit(world, 2, dead);
  world = { ...world, projectiles: [{ kind: "ranged", actorId: 1, actorOwner: 2,
    originalTargetId: 2, targetId: 2, hitMode: 0,
    impactSplashRadius: 0, impactSplashFriendlyFireFraction: 1 }] };
  const result = runWorld(world, { maxTicks: 0 });
  assert.equal(result.outcome, "win");
  assert.equal(result.ticks, 0);
});

test("all-dead worlds return a draw and time limits return a distinct timeout with no winner", () => {
  const allDead = changeUnit(aftermath(), 2, dead);
  assert.equal(runWorld(allDead, { maxTicks: 0 }).outcome, "draw");
  const initial = createWorld({ ratio: "stalemate", units: [spawn(1, 2, 4), spawn(2, 3, 6)] });
  for (const retainSnapshots of [true, false]) {
    const result = runWorld(initial, { maxTicks: 3, retainSnapshots });
    assert.equal(result.outcome, "timeout");
    assert.equal(result.winner, null);
    assert.equal(result.ticks, 3);
    assert.equal(result.world.units.filter(u => u.alive).length, 2);
    assert.equal(result.snapshots.length, retainSnapshots ? 4 : 0);
  }
  assert.equal(runWorld(initial, { maxTicks: 0 }).outcome, "timeout");
  assert.throws(() => runWorld(initial, { maxTicks: 9001 }), /must not exceed/);
});

test("a time limit reached with unresolved projectiles is a timeout, not a premature win", () => {
  const world = changeUnit(launch(), 1, dead);
  for (const retainSnapshots of [true, false]) {
    const result = runWorld(world, { maxTicks: 1, retainSnapshots });
    assert.equal(result.outcome, "timeout");
    assert.equal(result.winner, null);
    assert.equal(result.ticks, world.tick + 1);
    assert.equal(result.world.units.filter(u => u.alive).length, 1);
  }
});

test("retained and compact runs produce the same result and events from the same seed", () => {
  const full = runWorld(changeUnit(launch("Mapuche", "elite_bolas_rider_mapuche"), 1, dead),
    { maxTicks: 60 });
  const compact = runWorld(changeUnit(launch("Mapuche", "elite_bolas_rider_mapuche"), 1, dead),
    { maxTicks: 60, retainSnapshots: false });
  assert.equal(full.outcome, compact.outcome);
  assert.equal(full.winner, compact.winner);
  assert.equal(full.ticks, compact.ticks);
  assert.deepEqual(full.events, compact.events);
  assert.deepEqual(full.world.units, compact.world.units);
});

test("a projectile accuracy roll does not mutate the previous world's random state", () => {
  const shooter = { ...profile("Wei", "xianbei_raider_wei"), speed_tiles_per_second: 0 };
  let world = createWorld({ ratio: "rng-state", openingSeed: 17,
    units: [spawn(1, 2, 4, shooter), spawn(2, 3, 6)] });
  let drew = false;
  for (let i = 0; i < 120; i++) {
    const before = world.shotRng.state;
    const next = stepWorld(world);
    assert.equal(world.shotRng.state, before);
    if (next.shotRng.state !== before) {
      drew = true;
      break;
    }
    world = next;
  }
  assert.equal(drew, true, "the test must reach a real accuracy draw");
});

test("Node job transports a real timeout through runFight without fabricating a winner", async () => {
  const result = await runHeadlessJob({ seed: 17, teams: [
    { count: 1, mechanics: idle }, { count: 1, mechanics: idle },
  ], disableAiOrders: true, disableKiting: true });
  assert.equal(result.outcome, "timeout");
  assert.equal(result.winnerOwner, null);
  assert.equal(result.winnerHp, 0);
  assert.equal(result.ticks, 9000);
  assert.equal(result.remainingByOwner[2].units, 1);
  assert.equal(result.remainingByOwner[3].units, 1);
});

test("Node job transports a mutual-kill draw distinctly from a timeout", async () => {
  const reflecting = { ...champion, hp: 1, effects: {
    ...champion.effects, damage_reflect_percent: 1,
  } };
  const result = await runHeadlessJob({ seed: 17, teams: [
    { count: 1, mechanics: reflecting }, { count: 1, mechanics: reflecting },
  ], disableAiOrders: true, disableKiting: true });
  assert.equal(result.outcome, "draw");
  assert.equal(result.winnerOwner, null);
  assert.equal(result.winnerHp, 0);
  assert.equal(result.remainingByOwner[2].units, 0);
  assert.equal(result.remainingByOwner[3].units, 0);
  assert.ok(result.ticks < 9000);
});
