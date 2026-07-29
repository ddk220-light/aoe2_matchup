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
// state. Everything else (formulas, comments, statement order) is byte-identical
// to simulate.js, which keeps its own copy until the Task 8 cutover; change one,
// change the other until then.
//
// The class deliberately owns no canvas, no timers and no page state: `loop()`,
// `render()`, `start()`/`pause()`/`reset()` and the debug panel all stay behind
// in simulate.js / the Task 6 renderer. A host drives this with step()/runToEnd().

import { TILE_SIZE, CANVAS_WIDTH, CANVAS_HEIGHT } from "./constants.js";

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
    }

    update(dt) {
        this.battleTime += dt;
        const allUnits = [...this.team1, ...this.team2];
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
        // Run multiple passes to resolve cascading overlaps
        for (let pass = 0; pass < 3; pass++) {
            for (let i = 0; i < n; i++) {
                for (let j = i + 1; j < n; j++) {
                    const a = alive[i],
                        b = alive[j];
                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    const minDist = a.radius + b.radius + 1;
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
        for (const u of alive) {
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
