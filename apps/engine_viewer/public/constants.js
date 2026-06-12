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
export const TREE_CAP = 4;             // [cal] max villagers gathering one tile-tree

// Town Center
export const TC_SIZE = 4;              // [dat] 4x4 tile footprint
export const DEPOSIT_REACH = 0.5;      // [cap] deposit distance from a dropsite edge

// Lumber Camp construction
export const CAMP_SIZE = 2;            // [dat] 2x2 footprint
export const CAMP_COST_WOOD = 100;     // [dat] lumber camp cost
export const CAMP_BUILD_POINTS = 54;   // [cal] builder-seconds; camp done ~44s (1st deposit ~75s matches cap)
export const BUILD_REACH = 1.6;        // [cal] builder stand distance from camp center
