// Game constants used by the engine. Provenance for every value:
//   [dat] known game-data constant; [cap] measured from the 4_lumber gRPC
//   capture (lab/captures/4_lumber.frames.bin, game build 178524);
//   [cal] calibrated so the verifier matches the capture within tolerance.
export const TICK = 1 / 20;            // [engine] 20 Hz sim tick (game clock rate)
export const VILL_SPEED = 0.8;         // [dat] tiles/s        [cap] confirms 0.8
export const GATHER_RATE = 0.39;       // [dat] wood/s         [cap] measured 0.391
export const CARRY_CAP = 10;           // [dat]                [cap] confirms 10.0
export const TRAIN_TIME_VILLAGER = 25; // [dat]                [cap] 10.27 -> 35.26
export const TREE_WOOD = 100;          // [dat]                [cap] confirms 100.0
export const TREE_HP = 20;             // [dat]                [cap] confirms 20.0
export const FELL_DPS = 5.8;           // [cal] solo fell ~3.45 s (felled_t 12.2)
export const SETTLE_TIME = 0.7;        // [cap] arrive->first-wood-tick lag
export const GATHER_REACH = 0.9;       // [cap] stand distance from tree center
export const TC_SIZE = 4;              // [dat] 4x4 tile footprint
export const DEPOSIT_REACH = 0.3;      // [cap] deposit points sit 0-0.6 off edge
