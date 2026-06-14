// Game constants used by the engine. Provenance for every value:
//   [dat] known game-data constant; [cap] measured from a gRPC capture
//   (game build 178524); [cal] calibrated so the verifier matches the capture.
export const TICK = 1 / 20;            // [engine] 20 Hz sim tick (game clock rate)
export const VILL_SPEED = 0.8;         // [dat] tiles/s        [cap] confirms 0.8
export const SCOUT_SPEED = 1.2;        // [dat] Scout Cavalry  [cap] median 1.20 t/s
export const GATHER_RATE = 0.39;       // [dat] wood/s         [cap] measured 0.391
export const FORAGE_RATE = 0.31;       // [dat] food/s from forage bushes
export const HERD_GATHER_RATE = 0.33;  // [dat] food/s eating a slain SHEEP/goose [cap]
export const HUNT_GATHER_RATE = 0.41;  // [dat] food/s eating a slain DEER/BOAR (hunt rate > shepherd)
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

// Huntable deer (wild food). A deer is NOT herded/converted — it panic-RUNS
// directly away from the nearest mobile threat (scout/villager) in short
// dashes, rests between them, and when left alone AMBLES back to its spawn.
// All [cap] from the deer capture (master 1796): flee runs measured at 1.40
// t/s (cos +1.0 away), return-walk at a steady 0.74 t/s (n=50). Pushed ~20
// tiles from spawn => NOT leashed. Killed in place (ordered villagers, or a
// garrisoned TC) then gathered as a carcass like a slain herdable.
export const DEER_FOOD = 140;          // [cap] food pool per deer (pool 140.0)
export const FLEE_SPEED = 1.40;        // [cap] run-from-threat speed (dash p90 1.41)
export const DEER_WALK = 0.74;         // [cap] amble / return-to-spawn speed (n=50 med 0.74)
export const FLEE_TRIGGER = 3.0;       // [cap] flees when a non-hunting unit closes within this
// A deer does NOT bolt the instant a unit is in range — it waits ~REACT_DELAY,
// THEN runs away from the threat's position at that moment. That delay is what
// lets the scout get to the deer's far side, so the deer flees AWAY from the
// scout = toward the TC. Without it the deer scatters off the first approach.
// Open-loop replay can't reproduce the player's closed-loop scout micro, and
// fleeing directly away from the scout's POSITION is chaotically unstable (a
// 1-tile offset flips the push direction so the deer scatters off-line). So the
// flee direction is "away from the scout" PLUS a pull toward the herd
// destination (the TC the scout is driving it to). When the scout is on the
// anti-TC side both agree → a clean push toward the TC; when it's briefly on the
// TC side they cancel → the deer HOLDS instead of being shoved back to spawn.
export const HERD_PULL = 3.0;          // [cal] weight of toward-TC pull vs away-from-scout
export const RETURN_CLEAR = 4.0;       // [cap] threat must be beyond this before walking home
export const HOME_EPS = 0.8;           // [cap] stop returning within this of spawn
export const DEER_HP = 40;             // deer HP (hunted in place; HP combat detail = boar phase)
export const TC_FIRE_KILL = 1.5;       // [cal] garrisoned-TC ordered onto a deer -> dead in ~this
export const TC_RANGE = 8.0;           // [dat] TC arrow range

// Boar = a huntable that does NOT flee; it AGGROS whoever attacks it, chases,
// and fights back. Real HP combat (the deer/boar combat layer). All [cap] from
// the boar capture (master 48): HP 75, food 340. Boar1 is baited to the TC and
// killed by garrison arrows; boar2 kills a villager (the first unit death) then
// is swarm-killed after Loom.
export const BOAR_HP = 75;             // [cap] Wild Boar HP (seed)
export const BOAR_FOOD = 340;          // [cap] food pool per boar (pool 340.0)
export const BOAR_ATTACK = 8.75;       // [cap] dmg/hit on a villager (25hp dies in 3 hits)
export const BOAR_ATTACK_INT = 2.0;    // [cap] boar hit interval (deaths ~2s apart)
export const BOAR_SPEED = 0.95;        // [cap] chase speed (~0.94 t/s measured)
export const VILLAGER_HP = 25;         // [dat] villager HP    [cap] confirmed 25
export const LOOM_HP = 15;             // [cap] Loom (+15 HP -> 40) [tech 22]
export const VILLAGER_ATTACK = 3;      // [dat] villager melee vs boar
export const VIL_ATTACK_INT = 2.0;     // [cap] villager hit interval
export const MELEE_RANGE = 1.0;        // melee reach (attacker stands within this)
export const PROVOKE_RANGE = 7.0;      // [cal] a boar aggros an attacker once within this
export const ARROW_DMG = 5;            // [cap] dmg per TC arrow (boar drops in 5s)
export const TC_RELOAD = 2.0;          // [cap] seconds between TC arrow volleys
export const TC_BASE_ARROWS = 0;       // arrows the TC fires un-garrisoned (+1 per garrisoned)
export const LOOM_TECH = 22;           // [dat] Loom technology id
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
