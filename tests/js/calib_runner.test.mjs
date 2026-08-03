// tools/simjs/calib_runner.mjs drives the engine over every recorded
// calibration fight (calibration/fixtures/manifest.json), 20 seeds per fight,
// with sim.eventLog turned on, remapping the engine's own team numbers
// (1|2) to the REAL in-game owner numbers the manifest/tapes use (2|3 in
// today's corpus) so aoe2x/calibration/extract.py can score sim events
// exactly like tape events.
//
// These tests use tiny inline combat dicts (same fixture shape as
// tests/js/engine/event_log.test.mjs) rather than the DB-derived
// calibration/fixtures/combat_dicts.json, so they do not depend on
// dump_calib_dicts.py having been run yet.
import { test } from "node:test";
import assert from "node:assert/strict";
import { runCalibFight } from "../../tools/simjs/calib_runner.mjs";

const ARCHER = { hp: 40, attack: 6, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 0, outline_size: 0.2, accuracy: 100,
    unit_name: "Archer", cost_food: 0, cost_wood: 25, cost_gold: 45, hp_regen: 0 };
const MELEE = { hp: 100, attack: 10, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 1.2, melee_armor: 0, pierce_armor: 0, outline_size: 0.3, accuracy: 100,
    unit_name: "Melee", cost_food: 60, cost_wood: 0, cost_gold: 20, hp_regen: 0 };

const dicts = { "Britons|archer": ARCHER, "Franks|melee_unit": MELEE };

// Mirrors a manifest fight entry: side1/side2 are STRUCTURAL slots (team 1 /
// team 2 for buildFight); `owner` is the real in-game owner number, which in
// today's corpus is always 2 for side1 and 3 for side2.
const fight = {
    run_id: "test_fight", tag: "test_fight", matchup: "test_fight",
    duration_s: 12.3,
    side1: { owner: 2, unit_name: "Archer", civ: "Britons", slug: "archer", count: 6 },
    side2: { owner: 3, unit_name: "Melee", civ: "Franks", slug: "melee_unit", count: 6 },
};

test("runCalibFight returns a tape-shaped record with every required field", () => {
    const r = runCalibFight({ dicts, fight, seed: 1, maxSeconds: 120 });

    for (const k of ["run_id", "seed", "duration_s", "winner", "sides", "damage", "missiles"]) {
        assert.ok(k in r, `missing top-level field: ${k}`);
    }
    assert.equal(r.run_id, "test_fight");
    assert.equal(r.seed, 1);

    assert.ok(Array.isArray(r.damage) && r.damage.length > 0, "expected damage events");
    assert.ok(Array.isArray(r.missiles) && r.missiles.length > 0, "expected missile events");

    for (const e of r.damage) {
        for (const k of ["t", "attacker", "victim", "damage", "victim_hp_after",
                         "kill", "attacker_owner", "victim_owner"]) {
            assert.ok(e[k] !== undefined, `damage event missing ${k}`);
        }
    }
    for (const m of r.missiles) {
        assert.ok(m.id !== undefined, "missile event missing id");
        assert.ok(m.owner !== undefined, "missile event missing owner");
    }
});

test("sides is keyed by the REAL owner number, not the structural team slot", () => {
    const r = runCalibFight({ dicts, fight, seed: 1, maxSeconds: 120 });

    assert.deepEqual(Object.keys(r.sides).sort(), ["2", "3"]);
    assert.equal(r.sides["2"].owner, 2);
    assert.equal(r.sides["3"].owner, 3);
    assert.equal(r.sides["2"].start_count, 6);
    assert.equal(r.sides["3"].start_count, 6);
    assert.ok(Number.isInteger(r.sides["2"].survivors));
    assert.ok(Number.isInteger(r.sides["3"].survivors));
    assert.ok(r.sides["2"].hp_remaining >= 0);
    assert.ok(r.sides["3"].hp_remaining >= 0);

    // Every damage/missile event's owner field must also be a real owner
    // number (2/3), never the engine's raw team number (1/2) -- team 2 and
    // owner 2 would be indistinguishable if this regressed, so also check
    // the events actually reference BOTH real owners.
    const owners = new Set();
    for (const e of r.damage) {
        assert.ok([2, 3].includes(e.attacker_owner), `attacker_owner ${e.attacker_owner} not a real owner`);
        assert.ok([2, 3].includes(e.victim_owner), `victim_owner ${e.victim_owner} not a real owner`);
        owners.add(e.attacker_owner);
    }
    assert.deepEqual([...owners].sort(), [2, 3], "both real owners must appear as attackers");
    for (const m of r.missiles) {
        assert.ok([2, 3].includes(m.owner), `missile owner ${m.owner} not a real owner`);
    }
});

test("two runs at the same seed are identical", () => {
    const a = runCalibFight({ dicts, fight, seed: 5, maxSeconds: 120 });
    const b = runCalibFight({ dicts, fight, seed: 5, maxSeconds: 120 });
    assert.deepEqual(a.damage, b.damage);
    assert.deepEqual(a.missiles, b.missiles);
    assert.deepEqual(a.sides, b.sides);
    assert.equal(a.duration_s, b.duration_s);
    assert.equal(a.winner, b.winner);
});

test("seed 1 and seed 20 differ", () => {
    const a = runCalibFight({ dicts, fight, seed: 1, maxSeconds: 120 });
    const b = runCalibFight({ dicts, fight, seed: 20, maxSeconds: 120 });
    assert.notDeepEqual(a.damage, b.damage);
});

// Fix round 1 (code review): `winner` alone is a landmine -- it's the raw
// engine team number (1|2), NOT the real owner, and in today's corpus
// side1.owner is always 2. A consumer naively doing
// `sides[String(winner)]` when engine team 2 (side2) wins looks up
// sides["2"], which is side1 -- the LOSER -- with no error. This fixture
// makes team 2 (side2, real owner 3) the overwhelming, deterministic
// winner so the trap and its fix can both be demonstrated concretely.
const lopsidedFight = {
    run_id: "lopsided_fight", tag: "lopsided_fight", matchup: "lopsided_fight",
    side1: { owner: 2, unit_name: "Archer", civ: "Britons", slug: "archer", count: 2 },
    side2: { owner: 3, unit_name: "Melee", civ: "Franks", slug: "melee_unit", count: 10 },
};

test("winner_owner is in recording-owner space and correctly identifies the winner", () => {
    const r = runCalibFight({ dicts, fight: lopsidedFight, seed: 1, maxSeconds: 120 });

    assert.equal(r.winner, 2, "fixture must be lopsided enough for engine team 2 to win");
    assert.equal(r.winner_owner, 3, "winner_owner must be side2's real owner (3), not the raw team number (2)");

    // The exact trap the reviewer flagged: naively indexing `sides` with the
    // raw `winner` value returns the WRONG (losing) side here, because
    // side1's real owner happens to equal team 2's raw number.
    const trapSide = r.sides[String(r.winner)];
    const correctSide = r.sides[String(r.winner_owner)];
    assert.notEqual(trapSide, correctSide, "raw winner must NOT safely index sides");
    assert.equal(trapSide.civ, "Britons", "the trap silently returns the LOSING side");
    assert.equal(correctSide.civ, "Franks");
    assert.equal(correctSide.slug, "melee_unit");
    assert.ok(correctSide.survivors > 0, "winner_owner's side must have survivors");
});

test("winner_owner mirrors winner through the owner mapping, null on draw/timeout", () => {
    for (const seed of [1, 2, 3, 4, 5]) {
        const r = runCalibFight({ dicts, fight, seed, maxSeconds: 120 });
        if (r.winner === 1) assert.equal(r.winner_owner, fight.side1.owner);
        else if (r.winner === 2) assert.equal(r.winner_owner, fight.side2.owner);
        else assert.equal(r.winner_owner, null, `winner ${r.winner} (draw/timeout) must map to null`);
    }
});

// Fix round 2 (re-review): winner_owner must be a TABLE LOOKUP through the
// same `ownerOf` map used for events (`ownerOf[sim.winner] ?? null`), not a
// second, independently-hardcoded ternary that could drift from it. Force
// the actual timeout/draw branch (rather than only asserting it
// conditionally, if it happens to occur) with maxSeconds: 0 --
// Math.round(0 * 60) === 0, so the tick loop never runs and sim.winner
// stays at its constructor default of `null` (see sim.js:73/230): a
// deterministic "hit the cap with both sides alive" case with zero
// simulation needed. `ownerOf` only has keys "1"/"2", so looking it up with
// `null` misses the table and `?? null` must turn that miss into an
// explicit null -- proving the table has no stray 0/null key that could
// accidentally resolve to a real owner.
test("winner_owner is null for an actual timeout/draw (table lookup, not a hardcoded branch)", () => {
    const r = runCalibFight({ dicts, fight, seed: 1, maxSeconds: 0 });
    assert.equal(r.winner, null, "zero ticks must leave sim.winner at its null default");
    assert.equal(r.winner_owner, null);
});

test("a same-owner manifest entry raises rather than silently collapsing sides", () => {
    const brokenFight = {
        run_id: "broken_same_owner", tag: "broken_same_owner", matchup: "broken_same_owner",
        side1: { owner: 2, unit_name: "Archer", civ: "Britons", slug: "archer", count: 5 },
        side2: { owner: 2, unit_name: "Melee", civ: "Franks", slug: "melee_unit", count: 5 },
    };
    assert.throws(
        () => runCalibFight({ dicts, fight: brokenFight, seed: 1, maxSeconds: 120 }),
        /owner/i,
    );
});
