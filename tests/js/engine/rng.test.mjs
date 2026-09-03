import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

test("same seed produces the identical sequence", () => {
    const a = makeRng(42), b = makeRng(42);
    for (let i = 0; i < 1000; i++) assert.equal(a.next(), b.next());
});

test("different seeds diverge", () => {
    const a = makeRng(1), b = makeRng(2);
    const same = Array.from({ length: 100 }, () => a.next() === b.next());
    assert.ok(same.includes(false));
});

test("values lie in [0, 1)", () => {
    const r = makeRng(7);
    for (let i = 0; i < 10000; i++) {
        const v = r.next();
        assert.ok(v >= 0 && v < 1);
    }
});

test("seed 0 is coerced to 1 (vm-harness semantics)", () => {
    const z = makeRng(0), one = makeRng(1);
    assert.equal(z.next(), one.next());
});

test("getState changes with each draw and is a uint32", () => {
    const r = makeRng(5);
    const s0 = r.getState();
    r.next();
    const s1 = r.getState();
    assert.notEqual(s0, s1);
    assert.equal(s1, s1 >>> 0);
});
