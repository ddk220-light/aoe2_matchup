// Seeded PRNG (mulberry32). EXACT algorithm and seeding semantics of the vm
// harness that captured tools/simjs/golden/panel.json (state = (seed>>>0)||1)
// — do not alter: bit-for-bit parity with the golden depends on it.
export function makeRng(seed) {
    let state = (seed >>> 0) || 1;
    return {
        next() {
            state |= 0;
            state = (state + 0x6d2b79f5) | 0;
            let t = Math.imul(state ^ (state >>> 15), 1 | state);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        },
        getState() {
            return state >>> 0;
        },
    };
}
