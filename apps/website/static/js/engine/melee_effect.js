// Role: engine — melee/splash hit effect timing (logic only; render elsewhere).
//
// The MeleeEffect constructor/update are copied verbatim out of simulate.js
// (lines 778-792); the only edit is the `export` keyword. The render method did
// not come along — it is `static/js/sim_renderer.js` drawEffect.

export class MeleeEffect {
    constructor(x, y, team, splashRadius) {
        this.x = x;
        this.y = y;
        this.team = team;
        this.splashRadius = splashRadius || 0;
        this.lifetime = this.splashRadius > 0 ? 0.4 : 0.2;
        this.age = 0;
        this.done = false;
    }

    update(dt) {
        this.age += dt;
        if (this.age >= this.lifetime) this.done = true;
    }
}
