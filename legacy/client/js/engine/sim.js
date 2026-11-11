// Role: engine — the simulation core: tick loop, collision resolution, winner
// detection, and a deterministic state hash for parity/divergence testing.
//
// `update(dt)` is copied out of simulate.js (lines 2535-2612) and
// `resolveCollisions(allUnits)` out of simulate.js (lines 2614-2654). Exactly
// three statements were deleted from update(), all of them page-UI calls that
// belong to the renderer, never to the engine:
//   * `this.updateStats();`      (the live stat readout)
//   * `updateBattleWinner(1|2|0)` x3 (the page-global banner)
// The winner assignment and `this.running = false` STAY — those are engine
// state. Everything else (formulas, comments, statement order) carried over
// byte-identical. This module is the single source: simulate.js is only the page
// shell and keeps no copy. Any edit here changes sim behavior — re-run
// `node tools/simjs/parity_check.mjs`.
//
// The class deliberately owns no canvas, no timers and no page state: `loop()`,
// `render()`, `start()`/`pause()`/`reset()` and the debug panel all stay behind
// in simulate.js / `static/js/sim_renderer.js`. A host drives this with
// step()/runToEnd().

import {
    TILE_SIZE,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    COMBAT_PACK_FACTOR,
    B2,
} from "./constants.js";

// ---- deterministic state hash ------------------------------------------------
// FNV-1a (32-bit) over the full mutable sim state, in a fixed order. Used by the
// tests (same seed => same hash stream) and by the parity runner to pinpoint the
// exact tick at which two engines diverge.
const STATE_IDS = {
    idle: 0,
    moving: 1,
    attacking: 2,
    kiting: 3,
    committed: 4,
    dead: 5,
};
const _hbuf = new DataView(new ArrayBuffer(8));
function fnv(h, u32) {
    h ^= u32 & 0xff;
    h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 8) & 0xff;
    h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 16) & 0xff;
    h = Math.imul(h, 0x01000193);
    h ^= (u32 >>> 24) & 0xff;
    h = Math.imul(h, 0x01000193);
    return h >>> 0;
}
function fnvF64(h, v) {
    _hbuf.setFloat64(0, v);
    return fnv(fnv(h, _hbuf.getUint32(0)), _hbuf.getUint32(4));
}

// ===== BATTLE SIMULATION (engine core) =====
export class Simulation {
    constructor(mapW = CANVAS_WIDTH, mapH = CANVAS_HEIGHT, rng = null) {
        if (!rng || typeof rng.next !== "function") {
            // Fail loudly rather than quietly picking a seed: every draw in the
            // engine goes through sim.rng, so a missing one would either crash
            // deep inside a unit's accuracy roll or (worse) silently replay the
            // wrong stream.
            throw new Error("Simulation requires an rng — see makeRng(seed)");
        }
        // Logical coordinate space the whole sim works in (the page's canvas
        // backing store is a rendering concern and lives in the renderer).
        this.W = mapW;
        this.H = mapH;
        this.rng = rng;
        this.team1 = [];
        this.team2 = [];
        this.team1Stats = null;
        this.team2Stats = null;
        this.running = true;
        this.battleTime = 0;
        this.winner = null;
        this.projectiles = [];
        this.effects = [];
        // Diagnostic bookkeeping, per team. Pure counters: nothing in the engine
        // ever READS them, they draw no randomness and they are deliberately
        // absent from stateHash() — so they cannot influence a battle and the
        // parity gate stays bit-exact. The lab harness
        // (static/lab/sim_harness.js) reads them for its live DPS / hit-rate
        // readout. Written in BattleUnit.performAttackOn / fireProjectile
        // (swings) and BattleUnit.takeDamage (hitsLanded + damageDealt).
        // `shotPicks` / `allCovered` are R5d-T1's own diagnostics: how many
        // ranged shots went through the per-shot selection, and how many of
        // those found EVERY reachable enemy already covered and fell back to
        // the nearest. Same contract as the three counters above -- never read
        // by the engine, no rng, absent from stateHash().
        this.combatStats = {
            1: { swings: 0, hitsLanded: 0, damageDealt: 0, shotPicks: 0, allCovered: 0 },
            2: { swings: 0, hitsLanded: 0, damageDealt: 0, shotPicks: 0, allCovered: 0 },
        };
        // ===== R5d-T2: SAME-TICK CLAIM LEDGER =====
        // Two shooters that launch in the same 1/60 s tick are invisible to
        // each other's in-flight accounting: the second one's arrival-order
        // test (inboundDamageOn) discards the first one's projectile whenever
        // it will land later, even though both were fired from the same frozen
        // positions and neither could have reacted to the other. The forensics
        // attribute 27-43% of the engine hand cannoneer's residual in-flight
        // waste to exactly that pair (r5c_targeting_forensics.md Q1d).
        //
        // The ledger is the missing "I have already committed a shot to this
        // unit this tick" fact, and nothing more: `tickClaims` totals the
        // planned post-armor damage per victim, and `tickClaimShots` names the
        // projectiles it came from so inboundDamageOn can drop them and avoid
        // double-counting the same arrow twice. Both are cleared at the top of
        // every update(), so no state survives a tick and unit update order --
        // which is fixed -- is the only thing that decides who sees whom.
        //
        // Written by BattleUnit.fireProjectile (behind R5D.sameTickClaims),
        // read by BattleUnit.coveredDamageOn. Absent from stateHash() because
        // it is derived, per-tick, and empty at every tick boundary.
        this.tickClaims = new Map();
        this.tickClaimShots = new Set();
        // Event recorder for cross-engine calibration (Task 3 of the combat-
        // calibration project): null by default, exactly like combatStats above
        // it — nothing in the engine ever reads this back, it draws no
        // randomness, and it is deliberately absent from stateHash(), so it
        // cannot influence a battle and the parity gate stays bit-exact. A
        // caller opts in by setting `sim.eventLog = { damage: [], missiles: [] }`
        // before stepping; BattleUnit.takeDamage / fireProjectile / the charge
        // projectile paths append tape-shaped records when it is non-null. The
        // projectile-id counter lives ONLY on the log object (see the missile
        // hooks in battle_unit.js) so it cannot exist -- and cannot affect
        // determinism -- while recording is off.
        this.eventLog = null;
        // Golden-arena overlay (engine/arena.js), or null for the plain
        // rectangle this engine has always fought on. Set by createSimulation
        // when a caller passes `arena: "golden"`; NEVER set by default. Every
        // arena hook in this file and in battle_unit.js is guarded on this
        // being null, so the no-arena path is bit-identical to the pre-arena
        // engine -- which is what keeps the 155-fight calibration corpus and
        // tools/simjs/parity_check.mjs valid. Deliberately absent from
        // stateHash(): it is fixed geometry, not mutable state.
        this.arena = null;
        // E1 fight centre: midpoint of the two sides' unit centroids at spawn,
        // set once by createSimulation after both teams are placed (scenario.js)
        // and never updated — the tape boards' own fixed reference point C.
        // Read ONLY behind E1.orbitKite in BattleUnit.moveAwayFromTarget; null
        // (hand-built sims that never call createSimulation) falls back to the
        // radial retreat there. Like `arena` it is fixed geometry, deliberately
        // absent from stateHash().
        this.fightCenter = null;
    }

    update(dt) {
        this.battleTime += dt;
        // R5d-T2: the claim ledger is per-TICK by definition. Cleared here,
        // before anything can read or write it, so a claim can never leak from
        // one tick into the next (that is what the projectile list is for).
        this.tickClaims.clear();
        this.tickClaimShots.clear();
        const allUnits = [...this.team1, ...this.team2];
        // Combat-pack flags (E8), refreshed ONCE per tick off the positions
        // every unit can still see -- before anybody moves. Computing it here
        // rather than inside the O(3n^2) collision passes is both cheaper and
        // the only way both members of a pair agree: a flag recomputed mid-pass
        // would depend on the pair iteration order. See constants.js.
        for (const unit of allUnits) {
            unit.inCombatPack = unit.computeCombatPack();
            // D2 ballistic lead needs each unit's ACTUAL velocity (the engine's
            // vx/vy is a normalised heading, not a speed, and never returns to
            // zero when a unit stops). Refreshed here for the same reason the
            // combat-pack flag is: once per tick, off the positions everybody
            // can still see, before anyone has moved -- so two units that fire
            // at each other on the same tick lead each other off the same
            // snapshot, whatever order the teams update in.
            unit.refreshVelocity(dt);
        }
        for (const unit of this.team1)
            unit.update(dt, allUnits, this.team2);
        for (const unit of this.team2)
            unit.update(dt, allUnits, this.team1);

        // Hard collision resolution -- push overlapping units apart
        this.resolveCollisions(allUnits);

        // Update projectiles
        for (const p of this.projectiles) p.update(dt);
        this.projectiles = this.projectiles.filter((p) => !p.done);

        // Ally-death heal (Guecha Warrior): when a unit dies, nearby allies with
        // ally_death_heal gain a refreshing heal-over-time.  Each death fires once.
        for (const dead of allUnits) {
            if (dead.state !== "dead" || dead.deathHealTriggered) continue;
            dead.deathHealTriggered = true;
            const allies = dead.team === 1 ? this.team1 : this.team2;
            for (const ally of allies) {
                if (
                    ally === dead ||
                    ally.state === "dead" ||
                    ally.allyDeathHeal <= 0
                )
                    continue;
                if (dead.distanceTo(ally) <= 5 * TILE_SIZE) {
                    ally.allyHealRemaining = ally.allyDeathHeal;
                    ally.allyHealRate =
                        ally.allyDeathHealDuration > 0
                            ? ally.allyDeathHeal / ally.allyDeathHealDuration
                            : ally.allyDeathHeal;
                }
            }
        }

        // Update effects
        for (const e of this.effects) e.update(dt);
        this.effects = this.effects.filter((e) => !e.done);

        // Dismount on death (Konnik): dead mounted units respawn in place as
        // their dismounted form at END of tick — after all damage and before
        // the winner check, mirroring simulation_real.py / simulation.py.
        // The revived unit counts as alive and cannot act until next tick.
        for (const unit of allUnits) {
            if (
                unit.state === "dead" &&
                !unit.isDismounted &&
                unit.dismountHp > 0
            ) {
                unit.applyDismount();
            }
        }

        const team1Alive = this.team1.filter(
            (u) => u.state !== "dead",
        ).length;
        const team2Alive = this.team2.filter(
            (u) => u.state !== "dead",
        ).length;

        if (team1Alive === 0 && team2Alive > 0) {
            this.winner = 2;
            this.running = false;
        } else if (team2Alive === 0 && team1Alive > 0) {
            this.winner = 1;
            this.running = false;
        } else if (team1Alive === 0 && team2Alive === 0) {
            this.winner = 0;
            this.running = false;
        }
    }

    resolveCollisions(allUnits) {
        const alive = allUnits.filter((u) => u.state !== "dead");
        const n = alive.length;
        // ---- B2: the bump-contact event ------------------------------------
        // E14's bump-retarget rule needs to know "which enemies was I in body
        // contact with". This pass is the only thing in the engine that KNOWS
        // that -- it is the thing that decides it -- so it is the thing that
        // records it. B1 measured what happens when the rule re-derives the
        // answer from a distance a tick later instead: it is wrong on 99.8% of
        // the ticks it was written for, because THIS pass has already pushed
        // the pair to the floor and cascading pushes carry them 1-2 px beyond
        // it (docs/calibration/b1_engagement_forensics.md §2b).
        //
        // Recorded, consumed and cleared entirely within one tick boundary:
        // cleared here (before the passes), written by the passes below, read
        // by every unit's update() on the FOLLOWING tick -- which is the tick
        // on which those bodies were in fact touching. Deliberately absent
        // from stateHash(): it is a derived index of this pass's own work, not
        // independent state, and nothing but meleeBumpRetarget ever reads it.
        const recordBump = B2.resolverContactBump;
        if (recordBump) {
            for (const u of alive) u.bumpContacts.clear();
        }
        // Run multiple passes to resolve cascading overlaps
        for (let pass = 0; pass < 3; pass++) {
            for (let i = 0; i < n; i++) {
                for (let j = i + 1; j < n; j++) {
                    const a = alive[i],
                        b = alive[j];
                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    // E8: a SAME-TEAM pair whose members are both engaged in a
                    // fight at contact range is allowed to compress to
                    // COMBAT_PACK_FACTOR of the normal floor -- that is what
                    // lets a second rank of >= 1.0-tile-reach melee fight over
                    // the front rank, as the tapes show. Cross-team pairs keep
                    // the untouched floor, so the contact line itself does not
                    // move. The flags were computed once at the top of
                    // update(), so all three passes see the same values.
                    let minDist = a.radius + b.radius + 1;
                    if (
                        a.team === b.team &&
                        a.inCombatPack &&
                        b.inCombatPack
                    ) {
                        minDist *= COMBAT_PACK_FACTOR;
                    }
                    // B2: a CROSS-TEAM pair at or inside the floor is in body
                    // contact by this pass's own definition. `<=` rather than
                    // `<` so a pair parked exactly on the floor -- the steady
                    // state this pass drives every scrum towards -- still
                    // counts as touching; it is the same comparison the push
                    // below makes, only inclusive of its own fixed point.
                    // Set-valued, so the three passes cannot double-record and
                    // the consumer's answer cannot depend on pass count.
                    if (recordBump && a.team !== b.team && dist <= minDist) {
                        a.bumpContacts.add(b);
                        b.bumpContacts.add(a);
                    }
                    if (dist < minDist && dist > 0.01) {
                        const overlap = (minDist - dist) / 2;
                        const nx = dx / dist;
                        const ny = dy / dist;
                        a.x -= nx * overlap;
                        a.y -= ny * overlap;
                        b.x += nx * overlap;
                        b.y += ny * overlap;
                    } else if (dist <= 0.01) {
                        // Exactly on top -- nudge apart
                        a.x -= 2;
                        b.x += 2;
                    }
                }
            }
        }
        // Clamp to canvas bounds
        // TODO(accuracy): the clamp uses the CANVAS_WIDTH/CANVAS_HEIGHT constants,
        // not this.W/this.H — so a sim built on a non-900x600 map would spawn by
        // W/H but be clamped to 900x600. Legacy asymmetry, preserved deliberately:
        // "fixing" it would change unit positions and break golden parity.
        //
        // With the golden arena on, the diamond + tree cluster replace the
        // rectangle entirely: this is the LAST word on position each tick, so a
        // pair pushed apart above can never end up parked inside the trees or
        // outside the map. Hoisted out of the loop so the arena-less path below
        // is untouched.
        const arena = this.arena;
        for (const u of alive) {
            if (arena) {
                arena.constrain(u);
                continue;
            }
            u.x = Math.max(
                u.radius,
                Math.min(CANVAS_WIDTH - u.radius, u.x),
            );
            u.y = Math.max(
                u.radius,
                Math.min(CANVAS_HEIGHT - u.radius, u.y),
            );
        }
    }

    // ---- headless driving ----------------------------------------------------
    // The page's loop() converts wall-clock time into fixed 1/60 sub-steps; a
    // headless caller skips the clock and steps the same fixed timestep directly.
    step(dt = 1 / 60) {
        this.update(dt);
    }

    runToEnd(maxSeconds = 600) {
        while (this.winner === null && this.battleTime < maxSeconds - 1e-9)
            this.update(1 / 60);
        const living1 = this.team1.filter((u) => u.state !== "dead");
        const living2 = this.team2.filter((u) => u.state !== "dead");
        return {
            winner: this.winner, // 1 | 2 | 0 (mutual) | null (hit the cap)
            time: this.battleTime,
            alive1: living1.length,
            alive2: living2.length,
            hp1: living1.reduce((s, u) => s + u.currentHp, 0),
            hp2: living2.reduce((s, u) => s + u.currentHp, 0),
        };
    }

    stateHash() {
        let h = 0x811c9dc5;
        for (const u of [...this.team1, ...this.team2]) {
            h = fnvF64(h, u.x);
            h = fnvF64(h, u.y);
            h = fnvF64(h, u.currentHp);
            h = fnv(h, STATE_IDS[u.state] ?? 255);
        }
        h = fnv(h, this.projectiles.length);
        h = fnv(h, this.effects.length);
        h = fnv(h, this.rng.getState());
        return fnvF64(h, this.battleTime);
    }
}
