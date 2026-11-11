// Role: engine — projectile flight (logic only; rendering lives in the renderer).
//
// classifyProjectile + the Projectile constructor/update are copied verbatim out
// of simulate.js (lines 561-580 and 582-631); the only edits are the `import`
// line below and the `export` keywords. The render methods (_renderBall, render)
// did not come along — they are `static/js/sim_renderer.js` drawProjectileBall /
// drawProjectile.

import { TILE_SIZE } from "./constants.js";

// Classify a firing unit (by slug) into a projectile KIND, so each unit line
// gets a realistic, recognisable projectile (NOT team-tinted — projectiles are
// coloured by what they are). Order matters: bombard before gunpowder.
// unitName disambiguates civ variants that share a slug: the Rocket Cart line
// (Chinese/Koreans/Jurchens/Khitans) rides the siege_onager slug but fires
// rockets, not boulders.
export function classifyProjectile(slug, unitName) {
    const s = slug || "";
    if ((unitName || "").indexOf("Rocket") !== -1) return "rocket"; // fiery rocket
    if (s.indexOf("bombard_cannon") !== -1) return "cannonball"; // big black ball
    if (s.indexOf("siege_onager") !== -1) return "stone";        // onager boulder
    if (s.indexOf("hand_cannoneer") !== -1 || s.indexOf("janissary") !== -1
        || s.indexOf("conquistador") !== -1 || s.indexOf("organ_gun") !== -1)
        return "bullet";                                          // gunpowder shot
    if (s.indexOf("scorpion") !== -1 || s.indexOf("ballista_elephant") !== -1)
        return "bolt";                                            // heavy ballista bolt
    if (s.indexOf("skirm") !== -1 || s.indexOf("genitour") !== -1)
        return "javelin";                                         // thrown javelin
    return "arrow";                                               // archers / default
}

export class Projectile {
    constructor(
        startX,
        startY,
        targetX,
        targetY,
        speed,
        team,
        kind,
        onHit,
    ) {
        this.x = startX;
        this.y = startY;
        this.targetX = targetX;
        this.targetY = targetY;
        this.speed = speed || 7 * TILE_SIZE; // default fallback
        this.team = team;
        // Projectile kind drives the shape/colour: arrow | javelin | bolt |
        // bullet | cannonball | stone. (Back-compat: a truthy non-string — the
        // old is_siege_projectile flag — maps to a generic siege "stone".)
        this.kind = typeof kind === "string" ? kind : (kind ? "stone" : "arrow");
        this.onHit = onHit; // callback when projectile arrives
        this.done = false;
        // D3 in-flight damage accounting (Round 5b). Labels set by the firing
        // unit right after construction: who this shot is for, and the damage
        // it will apply if it lands. Default to "counts for nothing" so any
        // projectile path that does not set them (charge volleys) can never
        // contribute phantom damage to another shooter's overkill check.
        this.targetUnit = null;
        this.plannedDamage = 0;
        this.prevX = startX;
        this.prevY = startY;
        // Constant flight heading (straight line start->target), used to orient
        // the arrow so it always points the way it's travelling.
        this.angle = Math.atan2(targetY - startY, targetX - startX);
        // ===== D2-S1: OPTIONAL PASS-THROUGH SWEEP =====
        // Null on every projectile the engine has ever fired, and left null
        // unless D2.boltCorridor attaches one -- which is what makes the D2
        // off-switch bit-identical STRUCTURALLY rather than by test: with no
        // descriptor the branch in update() is unreachable and the flight below
        // is the original code, statement for statement.
        //
        // Shape (see BattleUnit.fireProjectile):
        //   { totalDist, hitAtDist, halfWidthPx, foes(), onPass(unit), skip }
        // `totalDist` is how far the bolt flies from the muzzle -- PAST the aim
        // point, which is the whole point -- `hitAtDist` is where the aim point
        // sits along that line (the normal arrival callback fires there and
        // resolves the primary exactly as it always has), and `onPass` is
        // invoked once per body the corridor sweeps.
        this.sweep = null;
    }

    update(dt) {
        if (this.done) return;
        if (this.sweep) return this.updateSweeping(dt);
        this.prevX = this.x;
        this.prevY = this.y;

        const dx = this.targetX - this.x;
        const dy = this.targetY - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const moveAmt = this.speed * dt;

        if (dist <= moveAmt) {
            this.x = this.targetX;
            this.y = this.targetY;
            this.done = true;
            if (this.onHit) this.onHit();
        } else {
            this.x += (dx / dist) * moveAmt;
            this.y += (dy / dist) * moveAmt;
        }
    }

    // ===== D2-S1: THE BOLT THAT DOES NOT STOP =====
    // A pass-through bolt flies a FIXED distance along its launch heading and
    // damages every body it threads on the way, rather than terminating on its
    // aim point. Three facts from docs/calibration/d1_siege_forensics.md §2.3
    // drive the shape of this method:
    //
    //   * the flight length is near-constant (median 10.56 tiles, 271/647 in one
    //     bin) and independent of how far the target was, so `totalDist` is a
    //     property of the BOLT and not of the shot;
    //   * damage events on one tape bolt fire at DIFFERENT TIMES along the path
    //     (missile -2 of heavy_scorpion__vs__hussar damaged three units at
    //     t=1.488, 1.902 and 2.016), so the corridor is swept tick by tick
    //     against where bodies actually are when the bolt reaches them -- not
    //     resolved in one go at launch or at arrival;
    //   * the aim target is paid at the aim point by the ordinary arrival
    //     callback, so `onHit` still fires exactly where and when it used to.
    //
    // Draws no randomness. Ordering inside a tick is fixed by the team array,
    // and a body is paid at most once per bolt (`hit`), so the whole method is
    // deterministic.
    updateSweeping(dt) {
        const s = this.sweep;
        const step = this.speed * dt;
        const fromX = this.x;
        const fromY = this.y;
        const nextDist = s.traveled + step;
        const ux = Math.cos(this.angle);
        const uy = Math.sin(this.angle);

        // The aim point is crossed mid-tick: resolve the primary there, at the
        // aim point, before the bolt travels on. This is the unmodified arrival
        // path -- same callback, same impact coordinates.
        if (!s.hitFired && nextDist >= s.hitAtDist) {
            s.hitFired = true;
            this.x = this.targetX;
            this.y = this.targetY;
            if (this.onHit) this.onHit();
        }

        const capped = Math.min(nextDist, s.totalDist);
        this.prevX = fromX;
        this.prevY = fromY;
        this.x = s.originX + ux * capped;
        this.y = s.originY + uy * capped;
        s.traveled = capped;

        // Sweep the segment just flown. `sweptDistanceSq` is a point-to-SEGMENT
        // test, which is what makes this a corridor rather than a ring of
        // per-tick discs: at 6 tiles/s and 1/60 s the bolt covers 3 px a tick,
        // well under a body, but the segment form means the result cannot depend
        // on the tick rate.
        for (const foe of s.foes()) {
            if (foe.state === "dead") continue;
            if (foe === s.skip) continue;
            if (s.hit.has(foe)) continue;
            const reach = foe.radius + s.halfWidthPx;
            if (
                sweptDistanceSq(foe.x, foe.y, fromX, fromY, this.x, this.y) <=
                reach * reach
            ) {
                s.hit.add(foe);
                s.onPass(foe);
            }
        }

        if (capped >= s.totalDist) this.done = true;
    }
}

/** Squared distance from (px,py) to the segment (ax,ay)-(bx,by). */
export function sweptDistanceSq(px, py, ax, ay, bx, by) {
    const vx = bx - ax;
    const vy = by - ay;
    const len2 = vx * vx + vy * vy;
    let t = 0;
    if (len2 > 0) {
        t = ((px - ax) * vx + (py - ay) * vy) / len2;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
    }
    const dx = px - (ax + t * vx);
    const dy = py - (ay + t * vy);
    return dx * dx + dy * dy;
}
