// Role: engine — shared numeric/lookup constants for the battle sim.
//
// This module is the single source of these values: simulate.js (the page shell)
// and the lab harness import them from here — no duplicate copies exist.
// Any edit here changes sim behavior: re-run `node tools/simjs/parity_check.mjs`.

// ===== CONSTANTS =====
export const CANVAS_WIDTH = 900;
export const CANVAS_HEIGHT = 600;
export const TILE_SIZE = 30;

export const MELEE_RANGE_BUFFER = 5;

// ===== CROWD CHURN =====
// In a packed scrum, units shove, turn, and lose the target they were
// winding up on, so the OBSERVED swing/shot interval runs longer than the
// unit's nominal reload -- the denser the local crowd, the bigger the delay.
// See BattleUnit.churnCooldown() (battle_unit.js) for the neighbour-count
// formula: crowding = min(1, neighbours-within-CHURN_RADIUS / CHURN_SATURATION),
// added delay = rng.next() * CHURN_MAX * crowding.
//
// Shape borrowed from aoe2x/sim/simulation_real.py's CHURN_MAX/_RADIUS/
// _SATURATION (that file's reference implementation restricts churn to
// MELEE units only -- "ranged units ... are not shoving anyone"). This
// engine's fit against the 84-fight recorded-tape corpus
// (docs/architecture/calibration-rig.md, Task 6) found real churn on a
// RANGED unit too (Japanese Hand Cannoneer, +0.494s), so here churn applies
// to both melee and ranged attacks -- a deliberate shape difference from
// simulation_real.py, not an oversight.
//
// CHURN_MAX was fit fresh against THIS engine's own 30x20 open-box geometry
// and the tape corpus -- do NOT copy simulation_real.py's 1.25, which was
// fit against a different arena (block spawns, no collision walls) and a
// different (38-row) corpus.
//
// FINDING (see task-6-report.md for the full sweep table): a single global
// constant cannot reproduce the tape's actual spread -- the Elite Battle
// Elephant's real churn (+4.23s on this fight) is ~9-15x the Elite Steppe
// Lancer's (+0.28s) and Hand Cannoneer's (+0.49s), but this engine's own
// neighbour-count crowding is roughly the SAME order of magnitude for all
// three (measured mean crowding fraction 0.14/0.14/0.38 respectively) --
// there is no value where all three individually match without also
// swamping ordinary infantry/cavalry fights (champion/halberdier/arbalester)
// whose tape swing intervals sit almost exactly on their nominal reload.
// 0.5 is the corpus-optimal compromise found by sweeping 0.0-8.0: it is the
// only positive value where all three target units simultaneously score
// MATCH (elephant only via its own wide seed-to-seed spread, itself a
// symptom worth a follow-up), while leaving the corpus-wide `churn`
// mismatch count effectively flat (59->60 of 84) and `swing_interval_median`
// the least-regressed of any tested nonzero value (67->85, vs +79 at 8.0).
// A real fix likely needs churn scaled by the ACTING unit's own body/
// collision radius (matching collision_radius()'s role in
// simulation_real.py), not a uniform constant across every unit class --
// flagged for a later task, not attempted here.
export const CHURN_MAX = 0.5;           // seconds, uniform [0, CHURN_MAX)
export const CHURN_RADIUS = 2.0 * TILE_SIZE; // px: neighbours this close count as crowding
export const CHURN_SATURATION = 6.0;    // neighbour count at which crowding maxes out

// ===== ADJUSTABLE PRE-BATTLE CONDITIONS =====
// Lithuanian relic bonus: the reference DB bakes in all 4 relics (+1 base
// melee attack each) for these units. The rail picker lets the user dial
// 0-4; setupTeam applies the delta vs the baked-in 4 client-side.
export const RELIC_MAX = 4;
export const RELIC_BONUS_UNITS = new Set(["paladin", "elite_leitis_lithuanians"]);
// Units that snowball +1 attack per kill up to attack_bonus_per_kill (cap 4):
// Jaguar Warrior (Aztecs), Tiger Cavalry (Wei). "Starting kills" pre-loads
// that counter so the battle can start mid-rampage.
export const KILL_BONUS_MAX = 4;
export const KILL_BONUS_UNITS = new Set([
    "elite_jaguar_warrior_aztecs",
    "elite_tiger_cavalry_wei",
]);
