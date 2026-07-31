// C4 -- FLEE DURING RELOAD (docs/calibration/c1_chaser_cadence.md M2 Table 2b,
// docs/calibration/c4_flee_during_reload.md).
//
// THE MEASUREMENT. The tape cycle for a ranged kiter hunted by melee is
// FIRE -> RUN THE WHOLE RELOAD WINDOW -> HALT (stop-to-fire) -> FIRE. C1
// Table 2b: the tape's hunted foot shooters move in 2.7-3.4 s CONTINUOUS
// stretches with ONE ~0.62 s stop per cycle -- the pre-shot windup alone --
// while the engine's same units stand ~2x the tape's duty cycle. The
// standing that is a DECISION (not body physics) is E9's post-fire recovery
// freeze and the R5B reloading park; E9's recovery was measured on UN-HUNTED
// (ranged-vs-ranged) cycles and still binds there.
//
// THE RULE. With C4.fleeDuringReload on, a RANGED non-siege unit that is
// (a) mid-reload (attackCooldown > 0) and (b) currently the TARGET of at
// least one living MELEE enemy (engine target bookkeeping -- no distance, no
// timer) keeps moving through the reload window via the EXISTING kite arm
// (same moveAwayFromTarget + kiteSteering call; E1 orbit basis when on,
// radial otherwise):
//   * firing is never delayed -- the predicate requires attackCooldown > 0,
//     so at reload expiry the stop-to-fire law, windup and halt cost run
//     exactly as today;
//   * the committed-shot windup still freezes (animation in flight);
//   * un-hunted units, ranged-vs-ranged fights (no melee hunter exists),
//     siege (minAttackRange > 0, the C1 corpus's own exclusion) and melee
//     units are all bit-identical.
//
// OFF-SWITCH. c4FleeDuringReload() returns false before reading anything
// with the flag off, so every caller composes its pre-C4 expression -- off
// is a no-op by construction, pinned by the defaults test below.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    C4,
    setC4,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Same arrow-wrap pattern as the other flag tests (c3/e1 etc.):
// override, run, ALWAYS restore.
function withC4(cfg, fn) {
    const saved = { ...C4 };
    setC4(cfg);
    try {
        return fn();
    } finally {
        setC4(saved);
    }
}

const C4_ON = { fleeDuringReload: true };

function simStub(rng) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: rng || makeRng(1),
    };
}

function stats({
    range = 0, isRanged = false, hp = 100, attack = 10, minRange = 0,
    armors = null,
} = {}) {
    return {
        hp, attack, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.4, collision_size: 0.25, accuracy: 100,
        unit_name: "U", is_ranged: isRanged, min_attack_range: minRange,
        armors_json: armors ? JSON.stringify(armors) : null,
    };
}

let nextId = 0;
function mk(sim, team, opts = {}) {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, stats(opts), opts.slug || "u",
        "Chinese", sim,
    );
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

// One hunted-kiter fixture: team-1 archer mid-reload, in post-fire recovery,
// with a living team-2 melee unit whose target IS the archer. Distances are
// generous so nothing fires or collides during the window under test.
function huntedFixture(sim, { hunterTargetsArcher = true, minRange = 0 } = {}) {
    const archer = mk(sim, 1, { range: 4, isRanged: true, minRange });
    const brute = mk(sim, 2, { hp: 1e6 }); // melee
    // Mid-canvas so the boundary clamp never eats the retreat step.
    archer.x = 10 * TILE_SIZE; archer.y = 10 * TILE_SIZE;
    brute.x = 13 * TILE_SIZE; brute.y = 10 * TILE_SIZE;
    archer.target = brute;
    archer.hasAcquiredTarget = true;
    if (hunterTargetsArcher) {
        brute.target = archer;
        brute.hasAcquiredTarget = true;
    }
    archer.attackCooldown = archer.reloadTime; // mid-reload
    archer.fireRecovery = 0.3;                 // E9 freeze just stamped
    return { archer, brute };
}

// ---- shipped configuration ---------------------------------------------------

test("[C4] ships OFF", () => {
    // OFF until the C4 iteration boards land -- same A/B gate discipline as
    // E1.orbitKite / C3.postSwingPlant, whose composed cycle this is the
    // third leg of.
    assert.equal(C4.fleeDuringReload, false);
});

test("[C4] setC4 rejects unknown flags", () => {
    assert.throws(() => setC4({ nope: true }), /unknown flag/);
});

// ---- OFF is a no-op ------------------------------------------------------------

test("[C4 off] a hunted reloading unit stays frozen through the recovery", () => {
    const sim = simStub();
    const { archer } = huntedFixture(sim);
    const x0 = archer.x, y0 = archer.y;
    const dt = 1 / 60;
    sim.battleTime += dt;
    archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
    assert.equal(archer.x, x0);
    assert.equal(archer.y, y0);
    assert.equal(archer.state, "attacking", "the E9 freeze holds");
});

test("[C4 off] the predicate is inert even when every gate would pass", () => {
    const sim = simStub();
    const { archer } = huntedFixture(sim);
    assert.equal(archer.c4FleeDuringReload(sim.team2), false);
});

// ---- the mechanism -------------------------------------------------------------

test("[C4] a hunted reloading unit MOVES during the post-fire recovery", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        const { archer, brute } = huntedFixture(sim);
        assert.equal(archer.c4FleeDuringReload(sim.team2), true);
        const d0 = Math.hypot(archer.x - brute.x, archer.y - brute.y);
        const dt = 1 / 60;
        for (let i = 0; i < 12; i++) { // 0.2 s, inside both windows
            sim.battleTime += dt;
            archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
        }
        const d1 = Math.hypot(archer.x - brute.x, archer.y - brute.y);
        assert.ok(d1 > d0 + 1,
            `runs the reload window, away from the hunter (${d0} -> ${d1})`);
        assert.equal(archer.state, "kiting", "the existing kite arm, not a new mode");
    });
});

test("[C4] a hunted unit keeps kiting through the WHOLE reload window", () => {
    // Not just the recovery span: every mid-reload tick is spent in the kite
    // arm (state 'kiting', position advancing) until the cooldown expires.
    withC4(C4_ON, () => {
        const sim = simStub();
        const { archer } = huntedFixture(sim);
        const dt = 1 / 60;
        let lastX = archer.x;
        while (archer.attackCooldown > dt / 2) {
            sim.battleTime += dt;
            archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
            assert.equal(archer.state, "kiting");
            assert.notEqual(archer.x, lastX, "displaced every mid-reload tick");
            lastX = archer.x;
        }
    });
});

test("[C4] an UN-hunted reloading unit behaves exactly as today", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        // The melee enemy exists but is hunting someone else.
        const { archer, brute } = huntedFixture(sim, { hunterTargetsArcher: false });
        const decoy = mk(sim, 1, { range: 4, isRanged: true });
        decoy.x = 5 * TILE_SIZE; decoy.y = 5 * TILE_SIZE;
        brute.target = decoy;
        brute.hasAcquiredTarget = true;
        assert.equal(archer.c4FleeDuringReload(sim.team2), false);
        const x0 = archer.x, y0 = archer.y;
        const dt = 1 / 60;
        sim.battleTime += dt;
        archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
        assert.equal(archer.x, x0, "the E9 freeze still binds the un-hunted");
        assert.equal(archer.y, y0);
        assert.equal(archer.state, "attacking");
    });
});

test("[C4] a RANGED hunter never arms the rule (ranged-vs-ranged unreachable)", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        const archer = mk(sim, 1, { range: 4, isRanged: true });
        const foe = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        archer.x = 0; archer.y = 0;
        foe.x = 3 * TILE_SIZE; foe.y = 0;
        archer.target = foe;
        foe.target = archer; // "hunted", but by a RANGED unit
        archer.attackCooldown = archer.reloadTime;
        archer.fireRecovery = 0.3;
        assert.equal(archer.c4FleeDuringReload(sim.team2), false);
        const x0 = archer.x;
        const dt = 1 / 60;
        sim.battleTime += dt;
        archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
        assert.equal(archer.x, x0, "reloading park unchanged without a melee hunter");
    });
});

test("[C4] a DEAD melee hunter does not arm the rule", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        const { archer, brute } = huntedFixture(sim);
        brute.state = "dead";
        assert.equal(archer.c4FleeDuringReload(sim.team2), false);
    });
});

test("[C4] a MOUNTED ranged unit hunted mid-reload behaves as today (foot only)", () => {
    // C1 M2's class split: the tape's mounted archer pays its post-fire
    // recovery even while hunted (stopMed 1.26 s = windup + recovery; duty
    // cycle already engine-correct). A hunted unit carrying the dat's
    // Cavalry (8) or Cavalry Archer (28) armor class is never armed.
    withC4(C4_ON, () => {
        for (const armors of [{ 8: 0 }, { 28: 0 }, { 3: 0, 4: 0, 8: 0, 15: 0, 28: 0, 31: 0 }]) {
            const sim = simStub();
            const hca = mk(sim, 1, { range: 4, isRanged: true, armors });
            const brute = mk(sim, 2, { hp: 1e6 });
            hca.x = 10 * TILE_SIZE; hca.y = 10 * TILE_SIZE;
            brute.x = 13 * TILE_SIZE; brute.y = 10 * TILE_SIZE;
            hca.target = brute; hca.hasAcquiredTarget = true;
            brute.target = hca; brute.hasAcquiredTarget = true;
            hca.attackCooldown = hca.reloadTime;
            hca.fireRecovery = 0.3;
            assert.equal(hca.c4FleeDuringReload(sim.team2), false,
                `mounted classes ${JSON.stringify(armors)} never arm`);
            const x0 = hca.x;
            const dt = 1 / 60;
            sim.battleTime += dt;
            hca.update(dt, [...sim.team1, ...sim.team2], sim.team2);
            assert.equal(hca.x, x0, "the E9 freeze still binds the mounted archer");
            assert.equal(hca.state, "attacking");
        }
    });
});

test("[C4] siege is excluded by the C1 corpus's own clause (minAttackRange > 0)", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        const { archer } = huntedFixture(sim, { minRange: 2 });
        assert.equal(archer.minAttackRange > 0, true, "fixture really is siege-like");
        assert.equal(archer.c4FleeDuringReload(sim.team2), false);
    });
});

test("[C4] a MELEE unit is never armed and never changed", () => {
    withC4(C4_ON, () => {
        const sim = simStub();
        const brawlerA = mk(sim, 1, { hp: 1e6 });
        const brawlerB = mk(sim, 2, { hp: 1e6 });
        brawlerA.x = 0; brawlerA.y = 0;
        brawlerB.x = 5 * TILE_SIZE; brawlerB.y = 0;
        brawlerA.target = brawlerB;
        brawlerB.target = brawlerA;
        brawlerA.attackCooldown = brawlerA.reloadTime;
        assert.equal(brawlerA.c4FleeDuringReload(sim.team2), false,
            "isRanged gate: melee never arms");
    });
    // Behavioural twin: a short melee chase is IDENTICAL with the flag on.
    const run = () => {
        const sim = simStub(makeRng(7));
        const a = mk(sim, 1, { hp: 1e6 });
        const v = mk(sim, 2, { hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = 6 * TILE_SIZE; v.y = 0;
        a.target = v; a.hasAcquiredTarget = true;
        const dt = 1 / 60;
        for (let i = 0; i < 120; i++) {
            sim.battleTime += dt;
            a.update(dt, [a, v], [v]);
        }
        return [a.x, a.y, a.state];
    };
    const off = run();
    const on = withC4(C4_ON, run);
    assert.deepEqual(on, off, "melee locomotion bit-identical under the flag");
});

test("[C4] firing is not delayed beyond the stop-to-fire law", () => {
    // The hunted unit kites its whole reload; at cooldown expiry it must
    // start its shot on EXACTLY the tick it would have anyway (the predicate
    // requires attackCooldown > 0, so the fire tick is never re-routed).
    const fireTick = (c4on) => {
        const run = () => {
            const sim = simStub(makeRng(3));
            const archer = mk(sim, 1, { range: 40, isRanged: true });
            const brute = mk(sim, 2, { hp: 1e6 });
            archer.x = 0; archer.y = 0;
            brute.x = 3 * TILE_SIZE; brute.y = 0;
            archer.target = brute; archer.hasAcquiredTarget = true;
            brute.target = archer; brute.hasAcquiredTarget = true;
            archer.attackCooldown = archer.reloadTime;
            archer.fireRecovery = 0.3;
            const dt = 1 / 60;
            for (let i = 1; i <= 600; i++) {
                sim.battleTime += dt;
                archer.update(dt, [archer, brute], sim.team2);
                // The shot's start is either the committed windup or (with a
                // zero windup) the launch itself resetting the cooldown.
                if (archer.committedAttack ||
                    archer.attackCooldown > archer.reloadTime - 2 * dt) {
                    return i;
                }
            }
            return -1;
        };
        return c4on ? withC4(C4_ON, run) : run();
    };
    const off = fireTick(false);
    const on = fireTick(true);
    assert.notEqual(off, -1, "fixture fires at all");
    assert.equal(on, off,
        `shot starts on the same tick with C4 on (${on}) as off (${off})`);
});

test("[C4] the freeze still rules a tick on which the unit could otherwise fire", () => {
    // Degenerate guard: recovery outlasting the reload (not true of any real
    // unit in the corpus, but the law must hold anyway) -- with the cooldown
    // expired the predicate disarms and the E9 freeze is back in charge, so
    // C4 can never manufacture a moving launch.
    withC4(C4_ON, () => {
        const sim = simStub();
        const { archer } = huntedFixture(sim);
        archer.attackCooldown = 0;
        archer.fireRecovery = 0.5;
        assert.equal(archer.c4FleeDuringReload(sim.team2), false);
        const x0 = archer.x;
        const dt = 1 / 60;
        sim.battleTime += dt;
        archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
        assert.equal(archer.x, x0, "frozen: no moving launch is possible");
        assert.equal(archer.state, "attacking");
    });
});

test("[C4] a hunted unit whose OWN target is ranged still runs (settle park outranked)", () => {
    // The marginal reach of the kite-arm join: in a mixed fight the unit's
    // standing target can be a ranged enemy while a melee hunter bears down.
    // Mid-reload it must run the kite arm, not park on the R5B margin.
    withC4(C4_ON, () => {
        const sim = simStub();
        const archer = mk(sim, 1, { range: 4, isRanged: true });
        const enemyArcher = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        const brute = mk(sim, 2, { hp: 1e6 });
        archer.x = 0; archer.y = 0;
        enemyArcher.x = 3 * TILE_SIZE; enemyArcher.y = 0;
        brute.x = -2 * TILE_SIZE; brute.y = 0;
        archer.target = enemyArcher;   // own target: RANGED
        archer.hasAcquiredTarget = true;
        brute.target = archer;         // hunted by MELEE
        brute.hasAcquiredTarget = true;
        archer.attackCooldown = archer.reloadTime;
        archer.fireRecovery = 0;       // recovery over; would settle today
        assert.equal(archer.c4FleeDuringReload(sim.team2), true);
        const x0 = archer.x;
        const dt = 1 / 60;
        sim.battleTime += dt;
        archer.update(dt, [...sim.team1, ...sim.team2], sim.team2);
        assert.equal(archer.state, "kiting");
        assert.notEqual(archer.x, x0, "moved instead of parking mid-reload");
    });
});

test("[C4] the predicate never touches the rng", () => {
    const draws = [];
    const inner = makeRng(1);
    const rng = {
        next() { draws.push(1); return inner.next(); },
        getState() { return inner.getState(); },
    };
    withC4(C4_ON, () => {
        const sim = simStub(rng);
        const { archer } = huntedFixture(sim);
        const before = draws.length;
        archer.c4FleeDuringReload(sim.team2);
        assert.equal(draws.length, before, "predicate draws nothing");
    });
});
