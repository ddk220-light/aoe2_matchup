import { test } from "node:test";
import assert from "node:assert/strict";
import { Projectile, classifyProjectile } from "../../../apps/website/static/js/engine/projectile.js";
import { MeleeEffect } from "../../../apps/website/static/js/engine/melee_effect.js";
import { TILE_SIZE } from "../../../apps/website/static/js/engine/constants.js";

test("projectile flies toward target and fires onHit exactly once on arrival", () => {
    let hits = 0;
    const p = new Projectile(0, 0, 300, 0, 7 * TILE_SIZE, 1, "arrow", () => hits++);
    let ticks = 0;
    while (!p.done && ticks++ < 600) p.update(1 / 60);
    assert.equal(p.done, true);
    assert.equal(p.x, 300);
    assert.equal(hits, 1);
    p.update(1 / 60); // done projectiles are inert
    assert.equal(hits, 1);
});

test("non-string truthy kind maps to legacy siege stone", () => {
    const p = new Projectile(0, 0, 1, 1, 100, 1, 1, null);
    assert.equal(p.kind, "stone");
});

test("melee effect expires after its lifetime", () => {
    const e = new MeleeEffect(10, 10, 1, 0);
    for (let i = 0; i < 13; i++) e.update(1 / 60); // 0.216s > 0.2s lifetime
    assert.equal(e.done, true);
});

test("classifyProjectile is a pure string mapping", () => {
    assert.equal(typeof classifyProjectile("arbalester", "Arbalester"), "string");
});
