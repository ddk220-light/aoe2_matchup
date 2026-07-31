// Phase D2 -- siege projectile / blast mechanics, measured in
// docs/calibration/d1_siege_forensics.md over the 25 scorpion/onager recordings.
//
// Four rules, four flags, one object (`D2`), and the same contract every rule
// object in this engine carries: all flags false == the pre-D2 engine, bit for
// bit. The last two tests in this file are that contract; the rest pin the
// rules' shapes against the numbers D1 measured.
//
// GROUND TRUTH USED HERE
//   S1  a bolt pays 1.00x to its aim target and exactly 0.500x -- unfloored --
//       to every other body within (that body's radius + the projectile's 0.1)
//       of its path, no cap (tape max 10 victims on one bolt), and it keeps
//       flying a near-constant 10.6 tiles from the muzzle, i.e. ~2.6 tiles past
//       its own maximum range, hitting bodies BEHIND the aim point (D1 §2.1-2.3).
//   S2a the blast falloff is linear from full at the body edge to zero at 1.667
//       tiles past it, not 1.500 (D1 §3.2, n=470).
//   S2b the stone's dat projectile_arc = 0.4 lengthens its flight by the
//       parabola's path-length ratio, 1.3338x (D1 §3.4).
//   S2c one shot is 1 stone + 9 fragments, each fragment dealing exactly 1
//       damage where it lands (D1 §3.1, ratio 9.000 in every recording).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    BattleUnit,
} from "../../../apps/website/static/js/engine/battle_unit.js";
import {
    Projectile,
    sweptDistanceSq,
} from "../../../apps/website/static/js/engine/projectile.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    D2,
    setD2,
    TILE_SIZE,
    BOLT_TOTAL_FLIGHT_TILES,
    BLAST_FALLOFF_ZERO_TILES,
    arcFlightFactor,
} from "../../../apps/website/static/js/engine/constants.js";
import { createSimulation } from "../../../apps/website/static/js/engine/scenario.js";

// ---- real combat dicts (data/calibration/combat_dicts.json) -----------------
const SCORPION_STATS = {
    hp: 60, attack: 15, attack_range: 8, attack_speed: 1 / 3.6,
    movement_speed: 0.65, melee_armor: 1, pierce_armor: 8,
    outline_size: 0.5, collision_size: 0.5,
    accuracy: 100, base_accuracy: 100, unit_name: "Heavy Scorpion",
    pass_through_percent: 0.4286, pass_through_count: 3,
    projectile_speed: 6, min_attack_range: 2, splash_radius: 0,
    attack_delay: 0.1, is_siege_projectile: 0,
    attacks_json: JSON.stringify({ 3: 15, 5: 10, 11: 7, 17: 2, 1: 2, 4: 0 }),
};

const HUSSAR_STATS = {
    hp: 95, attack: 12, attack_range: 0, attack_speed: 1 / 1.9,
    movement_speed: 1.5, melee_armor: 3, pierce_armor: 6,
    outline_size: 0.25, collision_size: 0.25,
    accuracy: 100, base_accuracy: 100, unit_name: "Hussar",
    armors_json: JSON.stringify({ 4: 3, 8: 0, 3: 6, 31: 0 }),
};

const ONAGER_STATS = {
    hp: 70, attack: 76, attack_range: 9, attack_speed: 1 / 6,
    movement_speed: 0.6, melee_armor: 0, pierce_armor: 8,
    outline_size: 0.5, collision_size: 0.5,
    accuracy: 100, base_accuracy: 100, unit_name: "Siege Onager",
    splash_radius: 1.5, projectile_speed: 3.5, min_attack_range: 3,
    is_siege_projectile: 1,
    attacks_json: JSON.stringify({ 4: 76 }),
};

const CHAMPION_STATS = {
    hp: 70, attack: 18, attack_range: 0, attack_speed: 0.5,
    movement_speed: 1.06, melee_armor: 4, pierce_armor: 5,
    outline_size: 0.2, collision_size: 0.2,
    accuracy: 100, base_accuracy: 100, unit_name: "Champion",
    armors_json: JSON.stringify({ 4: 4, 3: 5 }),
};

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

/** Fire one shot at `primary` and step every projectile until the list empties. */
function fireAndLand(sim, shooter, primary) {
    shooter.fireProjectile(primary);
    for (let i = 0; i < 20000 && sim.projectiles.length; i++) {
        for (const p of [...sim.projectiles]) p.update(1 / 60);
        sim.projectiles = sim.projectiles.filter((p) => !p.done);
    }
    assert.equal(sim.projectiles.length, 0, "projectile never terminated");
}

/** Run `fn` with exactly `on` D2 rules enabled, then restore the defaults. */
function withD2(on, fn) {
    const before = { ...D2 };
    try {
        setD2(Object.fromEntries(Object.keys(D2).map((k) => [k, on.includes(k)])));
        fn();
    } finally {
        setD2(before);
    }
}

// ===== S1 -- THE BOLT CORRIDOR ==============================================

test("S1: every collinear body past the muzzle takes exactly half, with no cap", () => {
    withD2(["boltCorridor"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        // Six hussars strung along +x. The aim target is the THIRD one, so two
        // sit in front of it and three behind -- the tape's median extra victim
        // sits 5.07 tiles PAST the body that took full damage.
        const line = [];
        for (let i = 0; i < 6; i++) {
            const h = new BattleUnit(`2-${i}`, 2, HUSSAR_STATS, "hussar", "Persians", sim);
            h.x = (2 + i * 1.2) * TILE_SIZE;
            h.y = 0;
            line.push(h);
        }
        const aim = line[2];
        scorp.x = 0; scorp.y = 0;
        sim.team1.push(scorp);
        sim.team2.push(...line);

        const full = scorp.getDamageAgainst(aim);
        assert.ok(full > 0, "the scorpion must actually damage a hussar");

        fireAndLand(sim, scorp, aim);

        assert.equal(aim.currentHp, 95 - full, "the aim target takes 1.00x");
        for (const h of line) {
            if (h === aim) continue;
            assert.equal(
                h.currentHp,
                95 - full * 0.5,
                `body at x=${h.x / TILE_SIZE} tiles must take exactly half, unfloored`,
            );
        }
        // Five extra victims on one bolt: the pre-D2 engine's ceiling was ONE.
        assert.equal(line.filter((h) => h.currentHp < 95).length, 6);
    });
});

test("S1: a body off the corridor is untouched; one just inside it is hit", () => {
    withD2(["boltCorridor"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        const grazed = new BattleUnit("2-1", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        const clear = new BattleUnit("2-2", 2, HUSSAR_STATS, "hussar", "Persians", sim);

        // Corridor half-width = victim radius (0.25 t) + projectile 0.1 t = 0.35.
        assert.equal(grazed.radius, 0.25 * TILE_SIZE);
        scorp.x = 0; scorp.y = 0;
        aim.x = 6 * TILE_SIZE; aim.y = 0;
        grazed.x = 3 * TILE_SIZE; grazed.y = 0.34 * TILE_SIZE;  // inside
        clear.x = 4 * TILE_SIZE; clear.y = 0.36 * TILE_SIZE;    // outside
        sim.team1.push(scorp);
        sim.team2.push(aim, grazed, clear);

        const full = scorp.getDamageAgainst(aim);
        fireAndLand(sim, scorp, aim);

        assert.equal(aim.currentHp, 95 - full);
        assert.equal(grazed.currentHp, 95 - full * 0.5, "0.34 tiles off the line is inside");
        assert.equal(clear.currentHp, 95, "0.36 tiles off the line is a clean miss");
    });
});

test("S1: the bolt overshoots its own range and hits what is behind the target", () => {
    withD2(["boltCorridor"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        // 9.5 tiles out: past the unit's own 8-tile range, inside the bolt's
        // measured 10.6-tile flight.
        const behind = new BattleUnit("2-1", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        // 11.0 tiles: past where the bolt stops.
        const beyond = new BattleUnit("2-2", 2, HUSSAR_STATS, "hussar", "Persians", sim);

        scorp.x = 0; scorp.y = 0;
        aim.x = 4 * TILE_SIZE; aim.y = 0;
        behind.x = 9.5 * TILE_SIZE; behind.y = 0;
        beyond.x = 11.0 * TILE_SIZE; beyond.y = 0;
        sim.team1.push(scorp);
        sim.team2.push(aim, behind, beyond);

        const full = scorp.getDamageAgainst(aim);
        fireAndLand(sim, scorp, aim);

        assert.equal(aim.currentHp, 95 - full, "aim target at 4 tiles: full");
        assert.equal(
            behind.currentHp,
            95 - full * 0.5,
            "5.5 tiles PAST the aim point and past the unit's 8-tile range: still half",
        );
        assert.equal(
            beyond.currentHp,
            95,
            `past BOLT_TOTAL_FLIGHT_TILES (${BOLT_TOTAL_FLIGHT_TILES}): untouched`,
        );
    });
});

test("S1: a body is paid at most once per bolt", () => {
    withD2(["boltCorridor"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        const passed = new BattleUnit("2-1", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        scorp.x = 0; scorp.y = 0;
        aim.x = 9 * TILE_SIZE; aim.y = 0;
        passed.x = 3 * TILE_SIZE; passed.y = 0;
        sim.team1.push(scorp);
        sim.team2.push(aim, passed);

        // Count the damage events landed on `passed`, not just its HP -- a body
        // straddling several ticks of the sweep must not be charged per tick.
        let events = 0;
        const orig = passed.takeDamage.bind(passed);
        passed.takeDamage = (...a) => { events++; return orig(...a); };

        fireAndLand(sim, scorp, aim);
        assert.equal(events, 1, "one bolt, one payment, however many ticks it spent overlapping");
    });
});

test("S1: friendly bodies are never swept (enemy-only, a deliberate absence)", () => {
    withD2(["boltCorridor"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const ally = new BattleUnit("1-1", 1, HUSSAR_STATS, "hussar", "Persians", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        scorp.x = 0; scorp.y = 0;
        ally.x = 3 * TILE_SIZE; ally.y = 0;
        aim.x = 7 * TILE_SIZE; aim.y = 0;
        sim.team1.push(scorp, ally);
        sim.team2.push(aim);

        fireAndLand(sim, scorp, aim);
        assert.equal(ally.currentHp, 95, "no friendly fire is implemented -- see D1 §3.3");
    });
});

test("S1 OFF: the legacy 1-victim floor(0.4286x) graze is exactly what still runs", () => {
    withD2([], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        const a = new BattleUnit("2-1", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        const b = new BattleUnit("2-2", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        scorp.x = 0; scorp.y = 0;
        aim.x = 5 * TILE_SIZE; aim.y = 0;
        a.x = 6 * TILE_SIZE; a.y = 0;
        b.x = 7 * TILE_SIZE; b.y = 0;
        sim.team1.push(scorp);
        sim.team2.push(aim, a, b);

        const full = scorp.getDamageAgainst(aim);
        fireAndLand(sim, scorp, aim);

        assert.equal(aim.currentHp, 95 - full);
        const hurt = [a, b].filter((h) => h.currentHp < 95);
        assert.equal(hurt.length, 1, "pre-D2: exactly one extra victim, ever");
        assert.equal(
            hurt[0].currentHp,
            95 - Math.max(1, Math.floor(full * 0.4286)),
            "pre-D2: floored 0.4286x, i.e. 0.333x of full against a hussar",
        );
    });
});

// ===== S2a -- THE BLAST ZERO POINT ==========================================

test("S2a: the falloff reaches zero at 1.667 tiles past the body edge, not 1.5", () => {
    const measure = (rules, distTiles) => {
        let hp = null;
        withD2(rules, () => {
            const sim = simStub(1);
            const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
            const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
            const victim = new BattleUnit("2-1", 2, CHAMPION_STATS, "champion", "Chinese", sim);
            onager.x = -300; onager.y = 0;
            primary.x = 0; primary.y = 0;
            victim.x = distTiles * TILE_SIZE; victim.y = 0;
            sim.team1.push(onager);
            sim.team2.push(primary, victim);
            fireAndLand(sim, onager, primary);
            hp = victim.currentHp;
        });
        return hp;
    };

    // Body radius 0.2 t. edge distance = dist - 0.2.
    // ON : frac = 1 - edge/1.667. OFF: frac = 1 - edge/1.5.
    const net = (() => {
        const sim = simStub(1);
        const o = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
        const c = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
        return o.getDamageAgainst(c);
    })();
    const expect = (distTiles, zeroTiles) => {
        const edge = Math.max(0, distTiles - 0.2);
        const frac = 1 - Math.min(1, edge / zeroTiles);
        return 70 - Math.max(1, Math.round(net * frac));
    };

    assert.equal(measure(["blastZeroPoint"], 1.0), expect(1.0, BLAST_FALLOFF_ZERO_TILES));
    assert.equal(measure([], 1.0), expect(1.0, 1.5));
    assert.ok(
        measure(["blastZeroPoint"], 1.0) < measure([], 1.0),
        "the longer ramp must pay every off-centre body MORE, not less (D1 residual +0.095)",
    );

    // The reach test has to move with the ramp: a body 1.6 tiles from the stone
    // is outside splash_radius + radius = 1.7... no, inside. Take 1.85 tiles,
    // which is outside 1.5 + 0.2 = 1.7 and inside 1.667 + 0.2 = 1.867. The tape
    // has 37 events past 1.75 tiles, furthest 2.05.
    assert.equal(measure([], 1.85), 70, "pre-D2: the disc stops dead at 1.7 tiles");
    assert.ok(measure(["blastZeroPoint"], 1.85) < 70, "D2: still paying at 1.85 tiles");
});

// ===== S2b -- THE ARC =======================================================

test("S2b: arcFlightFactor is the parabola's path-length ratio, 1 at arc 0", () => {
    assert.equal(arcFlightFactor(0), 1);
    assert.equal(arcFlightFactor(-1), 1);
    // k = 4*0.4 = 1.6:  sqrt(1+k^2)/2 + asinh(k)/(2k)
    const k = 1.6;
    const expected = Math.sqrt(1 + k * k) / 2 + Math.asinh(k) / (2 * k);
    assert.ok(Math.abs(arcFlightFactor(0.4) - expected) < 1e-12);
    assert.ok(
        Math.abs(arcFlightFactor(0.4) - 1.3338) < 1e-3,
        `arc 0.4 must lengthen the flight by ~1.3338x, got ${arcFlightFactor(0.4)}`,
    );
});

test("S2b: the stone spends arcFlightFactor(0.4) times longer in the air", () => {
    const flightTicks = (rules) => {
        let ticks = 0;
        withD2(rules, () => {
            const sim = simStub(1);
            const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
            const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
            onager.x = 0; onager.y = 0;
            primary.x = 6 * TILE_SIZE; primary.y = 0;
            sim.team1.push(onager);
            sim.team2.push(primary);
            onager.fireProjectile(primary);
            while (sim.projectiles.length && ticks < 20000) {
                for (const p of [...sim.projectiles]) p.update(1 / 60);
                sim.projectiles = sim.projectiles.filter((p) => !p.done);
                ticks++;
            }
        });
        return ticks;
    };
    const off = flightTicks([]);
    const on = flightTicks(["projectileArc"]);
    assert.ok(off > 0);
    assert.ok(
        Math.abs(on / off - arcFlightFactor(0.4)) < 0.02,
        `flight-time ratio ${on}/${off} = ${(on / off).toFixed(3)}, want ~1.334`,
    );
});

test("S2b: the scorpion bolt has dat arc 0.0 and is untouched by the rule", () => {
    withD2(["projectileArc"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        assert.equal(scorp.projectileArc, 0, "dat projectile 627 projectile_arc = 0.0");
    });
});

// ===== S2c -- THE DEBRIS ====================================================

test("S2c: one stone throws nine 1-damage fragments and nothing more", () => {
    withD2(["blastDebris"], () => {
        const sim = simStub(1);
        const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
        assert.equal(onager.secondaryProjectileCount, 9, "dat: 9 x master 369 per shot");
        const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
        onager.x = -300; onager.y = 0;
        primary.x = 0; primary.y = 0;
        // A wall of bodies packed over the whole scatter disc, so every one of
        // the nine fragments must find something.
        const crowd = [];
        for (let gx = -3; gx <= 3; gx++) {
            for (let gy = -3; gy <= 3; gy++) {
                const c = new BattleUnit(`2-${gx}_${gy}`, 2, CHAMPION_STATS, "champion", "Chinese", sim);
                c.x = gx * 0.3 * TILE_SIZE;
                c.y = gy * 0.3 * TILE_SIZE;
                c.currentHp = 10000;      // survive the blast so chips are visible
                c.maxHp = 10000;
                crowd.push(c);
            }
        }
        sim.team1.push(onager);
        sim.team2.push(primary, ...crowd);

        const chips = [];
        for (const c of crowd) {
            const orig = c.takeDamage.bind(c);
            c.takeDamage = (dmg, atk) => { chips.push(dmg); return orig(dmg, atk); };
        }
        fireAndLand(sim, onager, primary);
        const ones = chips.filter((d) => d === 1).length;
        assert.equal(ones, 9, `nine fragments, each for exactly 1 damage (got ${ones})`);
    });
});

test("S2c: the debris rule draws no randomness -- the rng stream is untouched", () => {
    const streamAfter = (rules) => {
        let v = null;
        withD2(rules, () => {
            const sim = simStub(7);
            const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
            const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
            onager.x = -300; onager.y = 0;
            primary.x = 0; primary.y = 0;
            primary.currentHp = 10000; primary.maxHp = 10000;
            sim.team1.push(onager);
            sim.team2.push(primary);
            fireAndLand(sim, onager, primary);
            v = sim.rng.next();
        });
        return v;
    };
    assert.equal(streamAfter(["blastDebris"]), streamAfter([]));
});

// ===== the corridor helper ==================================================

test("sweptDistanceSq is a point-to-SEGMENT distance, clamped at both ends", () => {
    // (0,0)-(10,0); a point beyond the far end measures to the endpoint.
    assert.equal(sweptDistanceSq(5, 3, 0, 0, 10, 0), 9);
    assert.equal(sweptDistanceSq(13, 4, 0, 0, 10, 0), 9 + 16);
    assert.equal(sweptDistanceSq(-3, 4, 0, 0, 10, 0), 9 + 16);
    // Degenerate segment: falls back to point distance.
    assert.equal(sweptDistanceSq(3, 4, 1, 1, 1, 1), 4 + 9);
});

// ===== THE OFF-SWITCH =======================================================

test("D2 defaults are all false -- the shipped engine is the pre-D2 engine", () => {
    for (const [k, v] of Object.entries(D2)) {
        assert.equal(v, false, `D2.${k} must ship off until the boards say otherwise`);
    }
});

test("setD2 rejects an unknown rule name", () => {
    assert.throws(() => setD2({ nope: true }), /unknown flag nope/);
});

test("no projectile carries a sweep descriptor with boltCorridor off", () => {
    withD2(["blastZeroPoint", "projectileArc", "blastDebris"], () => {
        const sim = simStub(1);
        const scorp = new BattleUnit("1-0", 1, SCORPION_STATS, "heavy_scorpion", "Japanese", sim);
        const aim = new BattleUnit("2-0", 2, HUSSAR_STATS, "hussar", "Persians", sim);
        scorp.x = 0; scorp.y = 0;
        aim.x = 5 * TILE_SIZE; aim.y = 0;
        sim.team1.push(scorp);
        sim.team2.push(aim);
        scorp.fireProjectile(aim);
        assert.equal(sim.projectiles.length, 1);
        assert.equal(
            sim.projectiles[0].sweep,
            null,
            "Projectile.updateSweeping must be structurally unreachable",
        );
    });
});

test("a plain Projectile still flies and terminates exactly as it always did", () => {
    let hits = 0;
    const p = new Projectile(0, 0, 100, 0, 60, 1, "arrow", () => hits++);
    assert.equal(p.sweep, null);
    for (let i = 0; i < 200 && !p.done; i++) p.update(1 / 60);
    assert.equal(hits, 1);
    assert.equal(p.x, 100);
    assert.equal(p.y, 0);
    assert.ok(p.done);
});

// ---- full-battle identity ---------------------------------------------------
// The claim that matters for the corpus: a fight with no pass-through and no
// blast unit in it is BYTE-IDENTICAL with every D2 rule on, and any fight at all
// is byte-identical with every D2 rule off. Both are checked by replaying the
// whole battle and comparing the engine's own state hash tick by tick.
function replayHash(spec, rules) {
    let out = null;
    withD2(rules, () => {
        const sim = createSimulation(spec);
        const hashes = [];
        for (let i = 0; i < 3000 && sim.running; i++) {
            sim.step(1 / 60);
            if (i % 25 === 0) hashes.push(sim.stateHash());
        }
        hashes.push(sim.stateHash());
        out = hashes.join(",");
    });
    return out;
}

const MELEE_FIGHT = {
    seed: 20260411,
    teams: [
        { count: 8, combatDict: CHAMPION_STATS, slug: "champion", civ: "Chinese" },
        { count: 6, combatDict: HUSSAR_STATS, slug: "hussar", civ: "Persians" },
    ],
};

const SIEGE_FIGHT = {
    seed: 20260411,
    teams: [
        { count: 5, combatDict: SCORPION_STATS, slug: "heavy_scorpion", civ: "Japanese" },
        { count: 9, combatDict: HUSSAR_STATS, slug: "hussar", civ: "Persians" },
    ],
};

const ALL = Object.keys(D2);

test("OFF-SWITCH: a siege fight is bit-identical with every D2 rule off", () => {
    const base = replayHash(SIEGE_FIGHT, []);
    // Same run, flags explicitly cleared through the setter rather than by
    // relying on the module defaults.
    assert.equal(replayHash(SIEGE_FIGHT, []), base);
    assert.notEqual(
        replayHash(SIEGE_FIGHT, ALL),
        base,
        "sanity: the rules must actually DO something on a siege fight",
    );
});

test("NON-SIEGE IDENTITY: a melee fight is bit-identical with every D2 rule ON", () => {
    assert.equal(
        replayHash(MELEE_FIGHT, ALL),
        replayHash(MELEE_FIGHT, []),
        "no pass-through unit, no blast unit -> no D2 statement can execute",
    );
});
