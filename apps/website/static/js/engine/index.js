// Role: engine — the public surface. Import from here, not from the individual
// modules: everything below is the supported API, everything else is internal.
//
//     import { createSimulation } from ".../engine/index.js";
//     const sim = createSimulation({ teams: [spec1, spec2], seed: 7 });
//     const result = sim.runToEnd(600);
//
// The engine is host-agnostic: no canvas, no timers, no page globals, and every
// random draw goes through the seeded `sim.rng`, so the browser page, the
// headless parity runner and the tests all replay bit-identical battles.

export { createSimulation } from "./scenario.js";
export { Simulation } from "./sim.js";
export { BattleUnit, setArmorClassNames } from "./battle_unit.js";
export { Projectile, classifyProjectile } from "./projectile.js";
export { MeleeEffect } from "./melee_effect.js";
export { makeRng } from "./rng.js";
// Opt-in battlefield geometry — pass `arena: "golden"` to createSimulation.
// Nothing here runs unless a caller asks for it; see engine/arena.js.
export { Arena, makeArena } from "./arena.js";
export * from "./constants.js";
