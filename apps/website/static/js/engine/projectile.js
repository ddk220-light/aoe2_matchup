// Role: engine — projectile flight (logic only; rendering stays in simulate.js).
//
// classifyProjectile + the Projectile constructor/update are copied verbatim out
// of simulate.js (lines 561-580 and 582-631); the only edits are the `import`
// line below and the `export` keywords. The render methods (_renderBall, render)
// deliberately stay behind in simulate.js and move to the renderer in Task 6.

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
        this.prevX = startX;
        this.prevY = startY;
        // Constant flight heading (straight line start->target), used to orient
        // the arrow so it always points the way it's travelling.
        this.angle = Math.atan2(targetY - startY, targetX - startX);
    }

    update(dt) {
        if (this.done) return;
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
}
