// Game constants used by the engine. Provenance for every value:
//   [dat] known game-data constant; [cap] measured from a gRPC capture
//   (game build 178524); [cal] calibrated so the verifier matches the capture.
export const TICK = 1 / 20;            // [engine] 20 Hz sim tick (game clock rate)
export const VILL_SPEED = 0.8;         // [dat] tiles/s        [cap] confirms 0.8
export const GATHER_RATE = 0.39;       // [dat] wood/s         [cap] measured 0.391
export const CARRY_CAP = 10;           // [dat]                [cap] confirms 10.0
export const TRAIN_TIME_VILLAGER = 25; // [dat]  camp300 spawns every ~25s
export const TREE_WOOD = 100;          // [dat]                [cap] confirms 100.0
export const FELL_TIME = 1.2;          // [cal] per-tree cut-down delay before wood flows
export const SETTLE_TIME = 0.7;        // [cap] arrive -> first-wood-tick lag
export const GATHER_REACH = 0.9;       // [cap] stand distance from tree center
export const TREE_CAP = 3;             // [cap] max simultaneous gatherers on one tree

// Town Center
export const TC_SIZE = 4;              // [dat] 4x4 tile footprint
export const DEPOSIT_REACH = 0.5;      // [cap] deposit distance from a dropsite edge

// Lumber Camp construction
export const CAMP_SIZE = 2;            // [dat] 2x2 footprint
export const CAMP_COST_WOOD = 100;     // [dat] lumber camp cost
export const BUILD_TIME_LUMBER_CAMP = 35; // [dat] single-villager build time
// Multi-builder rule (AoEZone "Mechanics of Building and Repairing"):
//   time with n builders = 3*T1/(n+2)  ==> points accrue at (n+2)/3 per sec
// n=1 -> T1; n=0 -> 1.5*T1; n→∞ -> 0 with 3*T1 villager-seconds total.
// Validated vs capture: staggered arrivals (~20.5/29/32s) integrate to
// completion ~45.5s; capture shows ~44-45s.
export const BUILD_RATE = (n) => (n + 2) / 3;  // points/sec while n>0
export const BUILD_REACH = 1.6;        // [cal] builder stand distance from camp center
