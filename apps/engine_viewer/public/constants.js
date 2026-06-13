// Game constants used by the engine. Provenance for every value:
//   [dat] known game-data constant; [cap] measured from a gRPC capture
//   (game build 178524); [cal] calibrated so the verifier matches the capture.
export const TICK = 1 / 20;            // [engine] 20 Hz sim tick (game clock rate)
export const VILL_SPEED = 0.8;         // [dat] tiles/s        [cap] confirms 0.8
export const GATHER_RATE = 0.39;       // [dat] wood/s         [cap] measured 0.391
export const FORAGE_RATE = 0.31;       // [dat] food/s from forage bushes
export const HERD_GATHER_RATE = 0.33;  // [dat] food/s eating a slain herdable [cap]
export const CARRY_CAP = 10;           // [dat]                [cap] confirms 10.0
export const TRAIN_TIME_VILLAGER = 25; // [dat]  spawn #1 = queue_t + 25.0 in every capture
export const TREE_WOOD = 100;          // [dat]                [cap] confirms 100.0
export const BUSH_FOOD = 125;          // [dat] forage bush    [cap] confirms 125.0
export const HERD_FOOD = 100;          // [dat] sheep/goose    [cap] confirms 100.0

// Herdable (sheep/goose) mechanics — all [cap] from the sheep capture.
export const CONVERT_RANGE = 5.0;      // gaia herdable within this of an owned unit converts
export const HERD_SPEED = 0.95;        // herdable walk speed when herded (MOVE)
export const KILL_TIME = 0.3;          // arrive at a live herdable -> carcass (7 HP, dies fast)
export const HERD_CAP = 10;            // [cap] villagers swarm a carcass at the TC (peak 9-10)
export const HERD_AVAIL = 4.5;         // auto-hunt only herds herded within this of a dropsite
// A slain carcass DECAYS at a fixed rate independent of gatherers: measured
// 0.245 food/s across 4 carcasses (rot 13.0/10.3/7.5/2.6 over 53/42/30/12s).
// The faster villagers swarm it, the less total rot. ~10% lost here.
export const ROT_RATE = 0.245;         // [cap] food/s lost to decay while a carcass exists
export const FELL_TIME = 1.2;          // [cal] per-tree cut-down delay before wood flows
export const SETTLE_TIME = 0.7;        // [cap] arrive -> first-resource-tick lag
export const GATHER_REACH = 0.9;       // [cap] stand distance from node center
// No hard gatherer cap on trees: capacity = free orthogonal faces (4_lumber
// had 4 villagers on one lone tree; camp300's "max 3" was forest geometry).
export const DEPOSIT_REACH = 0.5;      // [cap] deposit distance from a dropsite edge
export const BUILD_REACH = 1.6;        // [cal] builder stand distance from foundation center

// Multi-builder rule (AoEZone "Mechanics of Building and Repairing"):
//   time with n builders = 3*T1/(n+2)  ==> points accrue at (n+2)/3 per sec
// n=1 -> T1; n=0 -> 1.5*T1; n→∞ -> 0 with 3*T1 villager-seconds total.
// Validated vs captures: camp300 lumber camp (staggered 3 builders) and
// millpop house (1 builder: completed = arrive + 25.0s exactly).
export const BUILD_RATE = (n) => (n + 2) / 3;  // points/sec while n>0

// Building registry: footprint size (tiles, square), single-villager build
// time T1 [dat], wood cost, population room granted ON COMPLETION, and which
// resources the building accepts as a dropsite.
export const BUILDINGS = {
  town_center: { size: 4, pop: 5, drop: ["wood", "food", "gold", "stone"] },
  lumber_camp: { size: 2, t1: 35, cost: 100, drop: ["wood"] },
  mill:        { size: 2, t1: 35, cost: 100, drop: ["food"] },
  house:       { size: 2, t1: 25, cost: 25, pop: 5 },
};
// replay BUILD action name -> engine building type
export const BUILDING_BY_NAME = {
  "Lumber Camp": "lumber_camp", "Mill": "mill", "House": "house",
  "Town Center": "town_center",
};
// Civs that don't need houses (pop cap = game max from the start).
// Proven by the captures: camp300 (Huns) trained 4 villagers straight
// through 5 pop with zero houses; millpop (Vikings) froze at 5 until the
// house finished.
export const CIV_NO_HOUSES = new Set(["Huns"]);

// resource carried per node type (herdable = a slain carcass yields food)
export const NODE_RES = { tree: "wood", bush: "food", herdable: "food" };
export const NODE_RATE = { tree: GATHER_RATE, bush: FORAGE_RATE, herdable: HERD_GATHER_RATE };

// Line of sight (tiles) — NOT in the replay; these are known AoE2:DE unit/
// building sight ranges, supplied so the viewer can recreate fog of war.
// Only the player's OWN units/buildings (+ converted herdables) reveal.
export const LOS = {
  villager: 4, scout: 6,                 // the scout is the explorer (wide LOS)
  town_center: 5, house: 4, mill: 6, lumber_camp: 6,
  herdable: 3,                            // a herded sheep reveals a little around it
};
