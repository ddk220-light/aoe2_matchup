// Role: engine — the BattleUnit combat/movement logic (rendering stays behind).
//
// Copied verbatim out of simulate.js (lines 834-2173 plus the class-closing brace
// at 2314). Exactly five mechanical edits were applied:
//   1. the render(ctx) method (simulate.js:2175-2313) did NOT move -- it belongs to
//      the renderer (`static/js/sim_renderer.js` drawUnit);
//   2. the imports below + the `export` keywords;
//   3. the constructor takes a `sim` back-reference and stores it as its first act;
//   4. every page-global `simulation` singleton reference became `this.sim` (or
//      `attacker.sim` inside the fireProjectile onHit closure, whose alias for the
//      firing unit is `attacker`);
//   5. the three unseeded random draws became `sim.rng.next()` -- seeded, replayable.
// The page-global `armorClassNames` lookup is now a module-level map fed by
// setArmorClassNames(). Everything else -- every formula, constant, comment and
// statement order -- carried over byte-identical. This module is the single
// source: simulate.js is only the page shell and keeps no copy. Any edit here
// changes sim behavior -- re-run `node tools/simjs/parity_check.mjs`.

import {
    TILE_SIZE,
    MELEE_RANGE_BUFFER,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    STUCK_PROGRESS_RATE,
    PURSUIT_BAR_FRACTION,
    PURSUIT_MIN_ADVANTAGE,
    KITE_TANGENTIAL_WEIGHT,
    KITE_COHESION_WEIGHT,
    KITE_COHESION_RAMP_TILES,
    COMBAT_PACK_FACTOR,
    COMBAT_PACK_SLACK_TILES,
    COMBAT_PACK_RANGED,
    FIRE_CYCLE_QUANTUM,
    RANGED_STOP_OVERHEAD,
    RANGED_POST_FIRE_RECOVERY,
    RANGED_POST_FIRE_RECOVERY_BY_SLUG,
    MELEE_TARGET_LOCK,
    MELEE_CONTACT_SLOTS,
    MELEE_BUMP_RETARGET,
    MELEE_SWING_RECOVERY_S,
    MELEE_LANE_REACQUIRE,
    MELEE_LANE_CANDIDATE_CAP,
    R5B,
    R5D1,
    R5D,
    B2,
    PROJECTILE_RADIUS_TILES,
    ACCURACY_DISPERSION_BY_SLUG,
    LEAD_WINDOW_SECONDS,
} from "./constants.js";
import { Projectile, classifyProjectile } from "./projectile.js";
import { MeleeEffect } from "./melee_effect.js";

// Armor-class display names (id -> label), used only for the damage-breakdown
// labels in getDamageAgainst(detailed). The page loads them from the API and
// injects them here; headless callers can leave it empty (labels fall back to
// `Class <id>`).
let armorClassNames = {};

export function setArmorClassNames(map) {
    armorClassNames = map || {};
}

// ===== UNIT RADII (E11) =====
// Two different radii, deliberately. They used to be one number and that was
// the bug:
//
//   PHYSICS radius (`unit.radius`) -- the .dat's `collision_size_x`, in tiles.
//     Decides packing, contact distance and melee reach. Nearly uniform across
//     the roster: 0.20 tiles on foot, 0.25 tiles for ANYTHING mounted (paladin,
//     hussar, camel, steppe lancer, cavalry archer AND the battle elephant),
//     0.50 for the mangonel/scorpion lines.
//   DRAW radius (`unit.drawRadius`) -- the .dat's `outline_size_x`, i.e. the
//     selection circle. Only the renderer reads it, so an elephant still LOOKS
//     like an elephant.
//
// The old formula, `Math.round(10 + min(outline, 1) * 20)`, was neither: a
// 10 px pedestal on top of a 20 px/tile scale gave infantry 14 px (2.3x their
// true 6 px), cavalry 18 px (1.5x their true 7.5 px) and elephants 20 px
// (2.7x) -- inflating everyone AND flattening the class differences into
// 14:18:20 where the truth is 6:7.5:7.5. The tapes' own p10 same-owner
// nearest-neighbour distance (all 155 recordings) is 0.394-0.400 tiles for
// foot units, 0.43-0.50 for every mounted unit including the elephant, and
// exactly 1.000 for scorpions/onagers -- 2 x collision_size, in every class.
//
// `collision_size` arrives on the combat dict from
// aoe2x/sim/combat_unit_loader.py (which owns the .dat readout and the
// class-based derivation), so every real unit -- API, lab harness, headless,
// calibration -- has it. The fallback is only reachable for hand-built test
// fixtures, and it is deliberately the IDENTITY on outline rather than a
// clamp: identity is right for everything on foot and for the whole
// mangonel/scorpion line, and merely too generous for mounted units, whereas
// clamping at 0.25 would halve a scorpion.
const MIN_PHYSICS_RADIUS_PX = 5;

export function physicsRadiusPx(stats) {
    const tiles = stats.collision_size != null
        ? stats.collision_size
        : (stats.outline_size || 0.2);
    return Math.max(MIN_PHYSICS_RADIUS_PX, tiles * TILE_SIZE);
}

export function drawRadiusPx(stats) {
    // Unchanged from the pre-E11 formula on purpose: this is what the canvas
    // has always drawn, and shrinking the sprites was never the point.
    return Math.round(10 + Math.min(stats.outline_size || 0.2, 1.0) * 20);
}

// Median of `pick(unit)` over the LIVING units of `units`, optionally restricted
// to one team. Returns null when nobody is left. Median, not max, on purpose: it
// is the statistic ddkSquareV25's own `gKiteOK` uses ("our range out-ranges the
// enemy median" -- docs/simulation-engine-migration.md §5.2), it is robust to a
// single odd unit, and it is deterministic (a plain numeric sort over a
// fixed-order array).
export function medianLiving(units, team, pick) {
    const vals = [];
    for (const u of units) {
        if (u.state === "dead") continue;
        if (team !== null && u.team !== team) continue;
        vals.push(pick(u));
    }
    if (vals.length === 0) return null;
    vals.sort((a, b) => a - b);
    const mid = vals.length >> 1;
    return vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
}

const pickRange = (u) => u.rawAttackRange;
const pickSpeed = (u) => u.moveSpeed;

// ===== BATTLE UNIT CLASS =====
export class BattleUnit {
    constructor(id, team, stats, slug = "", civName = "", sim = null) {
        this.sim = sim;
        this.id = id;
        this.team = team;
        this.stats = stats;
        this.slug = slug;
        // Realistic per-line projectile shape (arrow/javelin/bolt/bullet/cannonball/stone/rocket).
        this.projectileKind = classifyProjectile(slug, stats.unit_name);
        this.civName = civName;

        this.maxHp = stats.hp;
        this.currentHp = stats.hp;
        this.attack = stats.attack;
        this.rawAttackRange = stats.attack_range || 0;
        this.isRangedFlag =
            stats.is_ranged === undefined || stats.is_ranged === null
                ? null
                : Boolean(stats.is_ranged);
        this.attackRange =
            this.rawAttackRange * TILE_SIZE + MELEE_RANGE_BUFFER;
        this.attackSpeed = stats.attack_speed || 0.5;
        this.reloadTime = 1.0 / this.attackSpeed;
        this.attackDelay = stats.attack_delay || 0;
        this.moveSpeed = (stats.movement_speed || 1) * TILE_SIZE;
        this.meleeArmor = stats.melee_armor || 0;
        this.pierceArmor = stats.pierce_armor || 0;
        this.attacks = stats.attacks_json
            ? JSON.parse(stats.attacks_json)
            : {};
        this.armors = stats.armors_json
            ? JSON.parse(stats.armors_json)
            : {};

        // Combat properties
        this.minAttackRange =
            (stats.min_attack_range || 0) * TILE_SIZE;
        this.isSiegeProjectile = stats.is_siege_projectile || 0;
        this.splashRadius = (stats.splash_radius || 0) * TILE_SIZE;
        this.projectileSpeed =
            (stats.projectile_speed || 0) * TILE_SIZE;
        this.ignoresPierceArmor = stats.ignores_pierce_armor || 0;
        this.ignoresMeleeArmor = stats.ignores_melee_armor || 0;
        this.tramplePercent = stats.trample_percent || 0;
        this.trampleRadius =
            (stats.trample_radius || 0) * TILE_SIZE;
        this.trampleFlatDamage = stats.trample_flat_damage || 0;
        this.bonusDamageReduction =
            stats.bonus_damage_reduction || 0;
        // Projectile accuracy (0-1 fraction). A missed shot still flies but
        // deals no direct damage; it may graze a different nearby unit (default
        // 0.5x, Arambai missDamagePercent=1.0 -> full). Mirrors simulation_real.py.
        // Primary arrow uses `accuracy`; extra/secondary arrows use baseAccuracy
        // (Thumb Ring only boosts the primary), matching the backend.
        this.accuracy = (stats.accuracy || 100) / 100;
        this.baseAccuracy = (stats.base_accuracy || 100) / 100;
        // D2: the dat's Type50.accuracy_dispersion, in TILES -- the radius an
        // accuracy-roll failure throws the aim point by. Not yet carried by
        // the extraction pipeline, so this is normally 0 here and the per-slug
        // dat table in constants.js supplies it; see accuracyDispersionPx().
        this.accuracyDispersion = stats.accuracy_dispersion || 0;

        // Unique mechanics
        this.extraProjectiles = stats.extra_projectiles || 0;
        this.splashOnHitRadius =
            (stats.splash_on_hit_radius || 0) * TILE_SIZE;
        this.dodgeShieldMax = stats.dodge_shield_max || 0;
        this.dodgeShieldRecharge = stats.dodge_shield_recharge || 0;
        this.bleedDps = stats.bleed_dps || 0;
        this.bleedDuration = stats.bleed_duration || 0;
        this.blockFirstMelee = stats.block_first_melee || 0;
        this.attackBonusPerKill = stats.attack_bonus_per_kill || 0;
        this.firstAttackExtraProjectiles =
            stats.first_attack_extra_projectiles || 0;
        this.hpTransformThreshold =
            stats.hp_transform_threshold || 0;
        this.hpRegen = stats.hp_regen || 0;
        this.passThroughPercent = stats.pass_through_percent || 0;

        // Charge projectiles (Fire Lancer)
        this.chargeProjectileCount =
            stats.charge_projectile_count || 0;
        this.chargeProjectileSpeed =
            (stats.charge_projectile_speed || 0) * TILE_SIZE;
        this.chargeAttackRange =
            (stats.charge_attack_range || 0) * TILE_SIZE;
        this.chargeIgnoresArmor = stats.charge_ignores_armor || 0;
        this.chargeProjectileAttacks =
            stats.charge_projectile_attacks_json
                ? JSON.parse(stats.charge_projectile_attacks_json)
                : null;

        // State
        this.shieldCharges = this.dodgeShieldMax;
        this.shieldRechargeTimer = 0;
        this.hasBlockedFirstMelee = false;
        this.killBonusAttack = 0;
        this.hasUsedFirstAttack = false;
        this.isTransformed = false;
        this.bleedEffect = null;
        this.hasUsedCharge = false;

        // --- ported abilities (parity with simulation_real.py) ---
        this.chargeAttackMelee = stats.charge_attack_melee || 0;
        this.chargeRechargeTime = stats.charge_recharge_time || 0;
        this.chargeTimer = 0;
        this.chargeSlowPercent = stats.charge_slow_percent || 0;
        this.chargeSlowDuration = stats.charge_slow_duration || 0;
        this.executeDamagePerStep = stats.execute_damage_per_step || 0;
        this.executeHpStep = stats.execute_hp_step || 0;
        this.attackSpeedRamp = stats.attack_speed_ramp || 0;
        this.attackSpeedMin = stats.attack_speed_min || 0;
        this.rampReduction = 0;
        this.hpPerKill = stats.hp_per_kill || 0;
        this.hpPerKillMax = stats.hp_per_kill_max || 0;
        this.hpGainedFromKills = 0;
        this.missDamagePercent = stats.miss_damage_percent || 0;
        this.armorStripPerHit = stats.armor_strip_per_hit || 0;
        this.attackBonusNearby = stats.attack_bonus_nearby || 0;
        this.nearbyBonusCount = stats.nearby_bonus_count || 0;
        this.auraAttackBonus = 0;
        this.hpNearbyPercentPerUnit = stats.hp_nearby_percent_per_unit || 0;
        this.hpNearbyMaxUnits = stats.hp_nearby_max_units || 0;
        this.auraHpBonus = 0;
        this.damageReflectPercent = stats.damage_reflect_percent || 0;
        this.allyDeathHeal = stats.ally_death_heal || 0;
        this.allyDeathHealDuration = stats.ally_death_heal_duration || 0;
        this.allyHealRemaining = 0;
        this.allyHealRate = 0;
        this.extraProjScatter = stats.extra_proj_scatter || 0;
        this.slowTimer = 0;
        this.baseMoveSpeed = this.moveSpeed;
        // Transform target stats (Jian Swordsman)
        this.transformMaxHp = stats.transform_hp || 0;
        this.transformAttack = stats.transform_attack || 0;
        this.transformMeleeArmor = stats.transform_melee_armor || 0;
        this.transformPierceArmor = stats.transform_pierce_armor || 0;
        this.transformAttackSpeed = stats.transform_attack_speed || 0;
        this.transformMoveSpeed = stats.transform_movement_speed || 0;
        this.transformAttacks = stats.transform_attacks_json
            ? JSON.parse(stats.transform_attacks_json)
            : null;
        this.transformArmors = stats.transform_armors_json
            ? JSON.parse(stats.transform_armors_json)
            : null;
        // Dismount-on-death stat block (Konnik); inert unless dismountHp > 0.
        // Mirrors the simulation_real.py port (2026-06-10).
        this.dismountHp = stats.dismount_hp || 0;
        this.dismountAttack = stats.dismount_attack || 0;
        this.dismountMeleeArmor = stats.dismount_melee_armor || 0;
        this.dismountPierceArmor = stats.dismount_pierce_armor || 0;
        this.dismountAttackSpeed = stats.dismount_attack_speed || 0;
        this.dismountAttackDelay = stats.dismount_attack_delay || 0;
        this.dismountMovementSpeed = stats.dismount_movement_speed || 0;
        this.dismountAttacks = stats.dismount_attacks_json
            ? JSON.parse(stats.dismount_attacks_json)
            : null;
        this.dismountArmors = stats.dismount_armors_json
            ? JSON.parse(stats.dismount_armors_json)
            : null;
        this.isDismounted = false;

        this.x = 0;
        this.y = 0;
        // Physics radius = the .dat's true collision_size; draw radius = the
        // selection circle. See the physicsRadiusPx/drawRadiusPx block above.
        // infantry 6 px, anything mounted 7.5 px, mangonel/scorpion line 15 px.
        this.radius = physicsRadiusPx(stats);
        this.drawRadius = drawRadiusPx(stats);
        this.target = null;
        this.state = "idle";
        // Combat-pack flag (E8) -- refreshed once per tick by
        // Simulation.update() before any unit moves, so both members of a pair
        // read the SAME tick's value in calculateAvoidance and again in
        // resolveCollisions. Never true before the first update().
        this.inCombatPack = false;
        // B2: the CROSS-TEAM bodies Simulation.resolveCollisions found this
        // unit in contact with on the most recent tick -- written by that pass,
        // read by meleeBumpRetarget on the next one, cleared by that pass at
        // the start of every tick. A Set so three resolver passes over the same
        // pair record it once and the consumer's answer cannot depend on how
        // many passes touched it. Empty until the first resolveCollisions has
        // run, which is correct: nothing has bumped anything yet.
        this.bumpContacts = new Set();
        this.attackCooldown = 0;
        this.wasMoving = true;
        this.committedAttack = null;
        this.attackAnimTimer = 0;

        // --- ranged stand-and-shoot cost (E9; see constants.js for the tapes) ---
        // Seconds of post-fire recovery still owed: while > 0 the unit is frozen
        // and may not kite, chase or back out of its min-range dead zone.
        this.fireRecovery = 0;
        // Per-slug recovery, defaulting to the shared constant.
        this.postFireRecovery =
            RANGED_POST_FIRE_RECOVERY_BY_SLUG.get(slug) ??
            RANGED_POST_FIRE_RECOVERY;
        // Did this unit move at any point since its last shot? Decides whether
        // the current cycle is a bare reload (stood still) or a quantised
        // stand-and-shoot cycle. Starts true: a unit walks into range before its
        // opening shot, which is exactly the "had to stop" case.
        this.movedSinceShot = true;
        // Seconds the attack sprite-sheet keeps playing after a swing/shot fires,
        // independent of state — so the animation completes even once the unit
        // starts moving/kiting away (set to one full sheet cycle on each attack).
        this.animHold = 0;
        this.damageNumbers = [];

        // Movement smoothing -- prevents vibration. NOTE: vx/vy is a normalised
        // HEADING, not a velocity (it is multiplied by moveAmount at the point
        // of use, and is never reset when the unit stops). D2's lead needs a
        // real velocity, which is velX/velY below.
        this.vx = 0;
        this.vy = 0;

        // --- true per-tick velocity, px/s (D2 ballistic lead) ---
        // Derived from the distance actually covered over the previous tick,
        // so it includes collision shoves and is exactly zero for a unit that
        // stood still. Refreshed once per tick by Simulation.update().
        this.velX = 0;
        this.velY = 0;
        this.prevTickX = 0;
        this.prevTickY = 0;
        // x/y are assigned by the scenario AFTER construction, so the first
        // refresh only seeds the baseline and reports zero velocity.
        this.velSeeded = false;

        // --- trailing position history, for the P2 lead window ---
        // A fixed-capacity ring buffer of this unit's position at the START of
        // each of the last LEAD_WINDOW_SECONDS worth of ticks, written once per
        // tick by refreshVelocity() alongside velX/velY. AIM infrastructure: it
        // exists so a SHOOTER can measure how this unit has actually been
        // moving, and nothing else in the engine reads it.
        //
        // Capacity is sized from the real dt on the first refresh rather than
        // hardcoded to 18 (= 0.3 s at 60 Hz), so the window stays 0.3 s of
        // WALL CLOCK if the tick rate ever changes -- the same lesson as the
        // stuck bar's px/s rate in constants.js. Allocated lazily: a unit that
        // is never ticked (most unit tests) never pays for it.
        this.histX = null;
        this.histY = null;
        this.histT = null;
        this.histHead = 0;    // index the NEXT sample is written to
        this.histCount = 0;   // samples written, capped at capacity
        this.histClock = 0;   // this unit's own accumulated tick time, seconds

        // D4 approach hysteresis: true once this unit has closed to within a
        // body diameter inside reach, false again the moment its target
        // leaves reach. Starts false -- everything opens the fight by
        // approaching.
        this.rangedClosed = false;
        // Horizontal facing: sprites are authored facing LEFT, so faceRight=true
        // means mirror. At spawn, team 1 (left) faces its enemies on the right and
        // team 2 (right) faces left; during battle it tracks the target/movement
        // direction (see render) so a unit always faces what it's attacking.
        this.faceRight = this.team === 1;
        // Stuck detection -- switch targets when blocked
        this.stuckTimer = 0;
        this.lastDistToTarget = Infinity;
        this.blockedTargets = new Set();

        // --- E15b rule 1: swing-recovery plant (see constants.js) ---
        // Sim clock instant before which this unit may not WALK, because its
        // own attack animation has not finished. Stamped in performAttackOn
        // (i.e. when a melee swing LANDS, killing blows included) and read only
        // by the melee locomotion branches of update(). -Infinity, not 0, so a
        // unit that has never swung is unlocked at battleTime 0 too.
        this.moveLockUntil = -Infinity;
        // --- E15b rule 2: lane-gated re-acquisition (see constants.js) ---
        // Has this unit ever picked a target? The lane rule is scoped to
        // RE-acquisition, so the opening pick has to be distinguishable from
        // every later one. Set by findTarget, never cleared.
        this.hasAcquiredTarget = false;

        // Attack sprite-sheet ref, stamped by the page/harness for animation timing
        // only (triggerAttackAnim). The renderer owns all other draw assets.
        this.attackSheet = null;
    }

    isRanged() {
        // Explicit flag from the combat dict wins: a Steppe Lancer/Kamayuk has
        // 1.0 tile of MELEE reach, which defeats the old >= 1.0 inference.
        if (this.isRangedFlag !== null) return this.isRangedFlag;
        return this.rawAttackRange >= 1.0;
    }

    // Latch the attack sprite-sheet to keep playing for one full cycle from now,
    // so a swing/shot finishes on-screen even if the unit immediately moves or
    // kites away. Frames are sampled off the global clock, so this just extends
    // how long playback stays on past the brief "attacking" state.
    triggerAttackAnim() {
        const sh = this.attackSheet;
        this.animHold =
            sh && sh.meta ? (sh.meta.frames * sh.meta.dur) / 1000 : 0.4;
    }

    getDamageAgainst(target, detailed = false) {
        const isRanged = this.isRanged();
        const baseAttackClass = isRanged ? "3" : "4";
        const baseAttack =
            (this.attacks[baseAttackClass] ||
                this.attacks["4"] ||
                this.attack) + this.auraAttackBonus;
        let targetBaseArmor;
        if (isRanged && this.ignoresPierceArmor) {
            targetBaseArmor = 0;
        } else if (!isRanged && this.ignoresMeleeArmor) {
            targetBaseArmor = 0;
        } else {
            targetBaseArmor = isRanged
                ? target.armors["3"] || target.pierceArmor || 0
                : target.armors["4"] || target.meleeArmor || 0;
        }

        let bonusDamage = 0;
        const breakdown = [];

        const baseDmg = Math.max(0, baseAttack - targetBaseArmor);
        breakdown.push({
            classId: baseAttackClass,
            className: isRanged ? "Base Pierce" : "Base Melee",
            attack: baseAttack,
            armor: targetBaseArmor,
            damage: baseDmg,
            applies: true,
        });

        for (const [armorClass, attackValue] of Object.entries(
            this.attacks,
        )) {
            if (armorClass === "3" || armorClass === "4") continue;
            if (attackValue <= 0) continue;
            const targetHasClass =
                target.armors.hasOwnProperty(armorClass);
            const targetArmor = targetHasClass
                ? target.armors[armorClass]
                : 0;

            if (targetHasClass) {
                const effectiveBonus = Math.max(
                    0,
                    attackValue - targetArmor,
                );
                bonusDamage += effectiveBonus;
                breakdown.push({
                    classId: armorClass,
                    className:
                        armorClassNames[armorClass] ||
                        `Class ${armorClass}`,
                    attack: attackValue,
                    armor: targetArmor,
                    damage: effectiveBonus,
                    applies: true,
                });
            } else if (detailed) {
                breakdown.push({
                    classId: armorClass,
                    className:
                        armorClassNames[armorClass] ||
                        `Class ${armorClass}`,
                    attack: attackValue,
                    armor: "-",
                    damage: 0,
                    applies: false,
                });
            }
        }

        if (target.bonusDamageReduction > 0) {
            bonusDamage = Math.floor(
                bonusDamage * (1 - target.bonusDamageReduction),
            );
        }

        // Execute scaling (Kona): +N damage per missing-HP step on the target.
        let executeBonus = 0;
        if (
            this.executeDamagePerStep > 0 &&
            this.executeHpStep > 0 &&
            target.maxHp > 0
        ) {
            const missing = 1 - target.currentHp / target.maxHp;
            executeBonus =
                this.executeDamagePerStep *
                Math.floor(missing / this.executeHpStep);
        }
        const totalDamage = Math.max(
            1,
            baseDmg + bonusDamage + executeBonus,
        );
        if (detailed) return { total: totalDamage, breakdown };
        return totalDamage;
    }

    // Nearest living enemy, minus anything the stuck bar has blacklisted. This
    // is the game's own acquisition rule and E14 deliberately left it alone: a
    // fitted "prefer the foe my allies are already on" discount was built,
    // swept and measured monotonically HARMFUL (melee-62 within-10 50 -> 48 ->
    // 45 -> 42 -> 41 at a 0 / 0.25 / 0.5 / 1.0 / 2.0-tile bonus), and removed.
    // Which fight a freed unit joins is decided by where its body can get to,
    // not by a preference weight.
    findTarget(enemies) {
        let closest = null;
        let closestDist = Infinity;
        let fallback = null;
        let fallbackDist = Infinity;
        for (const enemy of enemies) {
            if (enemy.state === "dead") continue;
            const dist = this.distanceTo(enemy);
            // Prefer targets not in blockedTargets
            if (!this.blockedTargets.has(enemy)) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }
            // Track overall closest as fallback
            if (dist < fallbackDist) {
                fallbackDist = dist;
                fallback = enemy;
            }
        }
        // E15b rule 2 (LANE-GATED RE-ACQUISITION). Only ever narrows the choice
        // among the SAME unblocked candidates the loop above ranked, and only on
        // a RE-acquisition: `hasAcquiredTarget` is still false on the opening
        // pick, which is why the fight's first targets keep the plain
        // nearest-enemy rule. `closest` is the pre-E15b answer and is also the
        // fallback when every candidate in the cap is walled in, so the rule can
        // only move the pick to a REACHABLE enemy, never to no enemy at all.
        let chosen = closest;
        if (
            closest &&
            MELEE_LANE_REACQUIRE &&
            this.hasAcquiredTarget &&
            !this.isRanged()
        ) {
            chosen = this.laneAcquire(enemies) || closest;
        }
        // Use unblocked target if available, else fall back to closest
        this.target = chosen || fallback;
        // Only a pick that actually produced a foe counts as "this unit has
        // opened its fight" -- a findTarget that found nothing alive leaves the
        // opening exemption intact.
        if (this.target) this.hasAcquiredTarget = true;
        // Reset stuck tracking for new target
        this.stuckTimer = 0;
        this.lastDistToTarget = this.target
            ? this.distanceTo(this.target)
            : Infinity;
        return this.target;
    }

    distanceTo(other) {
        const dx = other.x - this.x;
        const dy = other.y - this.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    inRange() {
        if (!this.target) return false;
        const dist = this.distanceTo(this.target);
        const effectiveRange =
            this.attackRange + this.radius + this.target.radius;
        if (dist > effectiveRange) return false;
        if (this.minAttackRange > 0 && dist < this.minAttackRange)
            return false;
        return true;
    }

    tooClose() {
        if (!this.target || this.minAttackRange <= 0) return false;
        return this.distanceTo(this.target) < this.minAttackRange;
    }

    // ===== MELEE TARGET LOCK + BUMP RETARGET (E14) =====
    // What replaced E13's stochastic churn. E13 injected two probabilities
    // (break-off-per-swing, fumble-after-kill) and a fixed 5.8 s gap, fitted to
    // the corpus's own unit types and army sizes. Those numbers cannot
    // generalise -- a different unit at a different count would need a
    // different number, which is the definition of a curve fit rather than a
    // mechanism. They are gone. What is here instead is the behaviour the GAME
    // documents, and the contact loss E13 injected now has to EMERGE from
    // geometry.
    //
    // Two rules, both physical, neither carrying a fitted rate:
    //
    // 1. TARGET LOCK. A melee unit does not voluntarily leave a living melee
    //    foe. It presses, it waits, it gets shoved -- it does not re-pick on a
    //    timer. Concretely the stuck bar (moveTowardTarget) may no longer
    //    blacklist a melee target for a melee unit. Measured cause: the bar was
    //    responsible for 39.5% of all melee re-acquisitions -- MORE than the
    //    31.1% caused by the target dying -- firing at a median 0.61 tiles past
    //    the unit's own reach, i.e. on second-rank units that were queueing
    //    rather than stuck (tools/simjs/melee_select_probe.mjs).
    //
    // 2. BUMP RETARGET. The release valve is the one the game actually ships.
    //    AoE2:DE update 81058 (12 Apr 2023): "Units will now retarget to a unit
    //    of the same type if they bump into them and cannot reach the current
    //    target." The same behaviour is described by players from earlier DE
    //    builds in a broader form -- a melee unit that bumps an enemy other
    //    than its target switches to the one it bumped. Both readings agree on
    //    every fight in this corpus (single-unit-type armies), so the corpus
    //    cannot distinguish them; the broader one is implemented because it is
    //    the one described as the in-game feel, and the narrow one is a subset.
    //
    // The trigger is a body contact, not a probability: the test below reuses
    // resolveCollisions' own floor (radius + radius + 1 px), so "bumped" here
    // and "pushed apart" there are the same event by construction. Nothing in
    // either rule reads the rng, scales with army size, or names a unit.

    // Same-team units currently swinging at the same victim. Kept from E13 --
    // no longer used by any shipped mechanism, but it is the cheapest honest
    // way for a probe or a test to ask "how crowded is this victim".
    contestingAllies(victim) {
        const allies = this.team === 1 ? this.sim.team1 : this.sim.team2;
        let n = 0;
        for (const a of allies) {
            if (a.state === "dead") continue;
            if (a.target === victim) n++;
        }
        return n;
    }

    // Rule 1's predicate: is this a melee unit holding a living melee foe? Used
    // only by the stuck bar, to decide whether it may blacklist. A RANGED unit,
    // or a melee unit chasing a RANGED one, is unchanged -- that is a pursuit,
    // which is what the stuck bar was built for and still does.
    meleeTargetLock() {
        if (!MELEE_TARGET_LOCK) return false;
        if (this.isRanged()) return false;
        const t = this.target;
        if (!t || t.state === "dead" || t.isRanged()) return false;
        // ...unless the victim's contact slots are already full. A body can
        // only be surrounded by so many attackers, and the tape says how many:
        // attackers-per-victim runs median 2 / p90 3 / max 4 over all 31
        // pure-melee recordings, and the engine reproduces 2/3/4 exactly. A
        // unit locked on a foe that already has MELEE_CONTACT_SLOTS attackers
        // IN REACH of it is not queueing for a slot that will open, it is
        // standing behind a full ring -- so the stuck bar keeps its old job and
        // sends it somewhere it can actually fight.
        //
        // "In reach" is each ally's own reach test, not a tuned radius: the
        // count is exactly the number of allies that could swing at this victim
        // right now. There is no distance constant anywhere in this rule.
        let n = 0;
        const allies = this.team === 1 ? this.sim.team1 : this.sim.team2;
        for (const a of allies) {
            if (a === this || a.state === "dead" || a.target !== t) continue;
            if (a.distanceTo(t) <= a.attackRange + a.radius + t.radius) {
                n++;
                if (n >= MELEE_CONTACT_SLOTS) return false;
            }
        }
        return true;
    }

    // Rule 2. Called once per tick from update(), before the target is used.
    // Fires only when BOTH halves of the documented condition hold: the unit
    // cannot reach its current target, and its body is touching a different
    // living enemy. The nearest such enemy wins, so the outcome cannot depend
    // on array order.
    meleeBumpRetarget(enemies) {
        if (!MELEE_BUMP_RETARGET) return;
        if (this.isRanged()) return;
        const t = this.target;
        if (!t || t.state === "dead") return;
        // MELEE-VS-MELEE ONLY, on both ends -- the same scope as rule 1, and
        // for a measured reason. Left unscoped, this rule fires on every melee
        // unit CHASING archers (it bumps them constantly and re-picks the
        // nearest), which is a pursuit and not a brawl: it took the
        // champion__vs__arbalester canary from 6/6 to 0/6 and the corpus from
        // 126 to 114. Pursuit belongs to the ranged round.
        if (t.isRanged()) return;
        if (this.inRange()) return;
        const useEvent = B2.resolverContactBump;
        let best = null;
        let bestDist = Infinity;
        for (const enemy of enemies) {
            if (enemy === t || enemy.state === "dead" || enemy.isRanged())
                continue;
            const dist = this.distanceTo(enemy);
            // "In contact" asks the engine's OWN body physics, and the engine
            // separates bodies in two places. Both are asked, because B2
            // measured that only the second one is ever reachable:
            //
            //  * the HARD pass (Simulation.resolveCollisions, floor
            //    `radius + radius + 1`) -- consulted as its own recorded
            //    contact EVENT rather than re-derived from a distance a tick
            //    later, since by the time this runs the pair has already been
            //    pushed to the floor and cascading pushes carry it past.
            //  * the SOFT pass (calculateAvoidance, floor
            //    `radius + radius + 2`) -- the steering repulsion every unit
            //    applies to every body within one more pixel than the hard
            //    floor.
            //
            // THE SOFT FLOOR IS THE ONE THAT HOLDS A CROSS-TEAM PAIR, and that
            // is why E14's trigger could not fire. The soft floor is 1 px
            // WIDER than the hard one, so two enemies pressed together settle
            // at the soft floor and the hard pass never sees them: measured
            // over the three collapse/near-collapse fights x 2 seeds, on a
            // frozen tick with a hittable non-target foe present, the hard
            // floor is satisfied on 0.001 of ticks and its contact event on
            // 0.002 -- against 0.321 for the soft floor. B1 named the hard
            // floor as the culprit (forensics §2b); the arithmetic is one
            // pixel off, and the one pixel is the whole rule.
            //
            // Neither term is a new number: both floors already existed, for
            // this exact purpose, and `radius + radius + 2` is quoted from
            // calculateAvoidance rather than chosen. `<= hard` implies
            // `< soft`, so the soft term SUBSUMES the pre-B2 trigger and the
            // B2 rule is a strict superset: nothing that used to bump stops.
            const contact = useEvent
                ? (dist < this.radius + enemy.radius + 2 ||
                    this.bumpContacts.has(enemy))
                : dist <= this.radius + enemy.radius + 1;
            if (contact && dist < bestDist) {
                bestDist = dist;
                best = enemy;
            }
        }
        if (!best) return;
        this.target = best;
        // A bump is a fresh engagement: re-arm the stuck bar against the new
        // foe rather than carrying the old chase's progress history over.
        this.stuckTimer = 0;
        this.lastDistToTarget = bestDist;
    }

    // ===== E15b RULE 2: LANE-GATED RE-ACQUISITION =====
    // Full derivation, the 2062-lock-birth measurement and the mandatory
    // fight-opening exemption are in constants.js next to MELEE_LANE_REACQUIRE.
    // In one line: a freed melee unit takes the nearest enemy it can actually
    // WALK to, not the nearest body, because inside a scrum the nearest body is
    // whichever one the collision floor happened to park against it.

    // Is the straight approach from this unit's centre to `candidate`'s centre
    // wide enough for this unit's body to pass? The corridor is the segment
    // swept by a disc of the ATTACKER'S OWN RADIUS -- no tolerance constant
    // exists here -- so another body blocks it exactly when its centre lies
    // within `other.radius + this.radius` of the segment. Distance is measured
    // to the SEGMENT (the projection is clamped to [0,1]), so a body standing
    // behind the attacker or beyond the candidate does not block: it is not on
    // the way.
    laneClear(candidate) {
        const dx = candidate.x - this.x;
        const dy = candidate.y - this.y;
        const segLen2 = dx * dx + dy * dy;
        // Degenerate lane (bodies coincident): nothing can be "in between".
        if (segLen2 <= 0) return true;
        if (this._laneBlockedBy(this.sim.team1, candidate, dx, dy, segLen2))
            return false;
        if (this._laneBlockedBy(this.sim.team2, candidate, dx, dy, segLen2))
            return false;
        return true;
    }

    // Both teams are scanned -- an enemy body in the way is exactly as solid as
    // an allied one, and the collision pass treats them identically.
    _laneBlockedBy(units, candidate, dx, dy, segLen2) {
        for (const o of units) {
            if (o === this || o === candidate || o.state === "dead") continue;
            const px = o.x - this.x;
            const py = o.y - this.y;
            let t = (px * dx + py * dy) / segLen2;
            if (t < 0) t = 0;
            else if (t > 1) t = 1;
            const cx = px - t * dx;
            const cy = py - t * dy;
            const clear = o.radius + this.radius;
            if (cx * cx + cy * cy < clear * clear) return true;
        }
        return false;
    }

    // The nearest living, non-blacklisted enemy whose lane is clear, or null if
    // every candidate inside the cost cap is walled in (the caller then keeps
    // the plain nearest, i.e. the pre-E15b answer). Candidates are ranked by the
    // same distance the caller used and the sort is stable, so equal distances
    // keep enemy-array order exactly as the nearest-only loop did.
    laneAcquire(enemies) {
        const pool = [];
        for (const enemy of enemies) {
            if (enemy.state === "dead") continue;
            if (this.blockedTargets.has(enemy)) continue;
            pool.push({ e: enemy, d: this.distanceTo(enemy) });
        }
        pool.sort((a, b) => a.d - b.d);
        const cap = Math.min(pool.length, MELEE_LANE_CANDIDATE_CAP);
        for (let i = 0; i < cap; i++) {
            const e = pool[i].e;
            // MELEE-VS-MELEE ONLY, exactly as E14's bump retarget is scoped,
            // and for the same measured reason. The 2062 lock births this rule
            // is derived from are all from PURE-MELEE recordings: chasing
            // archers is a pursuit, not a brawl, and there is no tape evidence
            // that a chaser threads the scrum to pick a further archer. Left
            // unscoped it fires on every champion re-picking among a kiting
            // ball and took the champion__vs__arbalester canary from 6/6 to
            // 0/6 (measured, this experiment) -- the identical failure E14
            // recorded for the same over-application. A ranged candidate is
            // therefore taken as-is, which for a single-unit-type army means
            // the whole rule reduces to the pre-E15b nearest.
            if (e.isRanged()) return e;
            if (this.laneClear(e)) return e;
        }
        return null;
    }

    // ===== E15b RULE 1: SWING-RECOVERY PLANT =====
    // Derivation (the tape's swing-phase ramp) is in constants.js next to
    // MELEE_SWING_RECOVERY_S. This predicate is read ONLY by the melee
    // locomotion branches of update(): a unit inside its recovery window still
    // turns, still re-targets, still bump-retargets, still reloads, still gets
    // shoved by resolveCollisions -- it just may not walk.
    meleeMoveLocked() {
        if (MELEE_SWING_RECOVERY_S <= 0) return false;
        if (this.isRanged()) return false;
        return this.sim.battleTime < this.moveLockUntil;
    }

    // ===== RANGED STAND-AND-SHOOT COST (E9) =====
    // Tape derivation, per-unit numbers and the rejected additive model all live
    // in constants.js next to FIRE_CYCLE_QUANTUM. In one line: a ranged unit that
    // stood still all cycle re-fires at a bare reloadTime; one that moved has to
    // stop, aim and recover, and its shot lands on the next quantum boundary.

    // Launch-to-launch cycle for a shot the unit had to STOP to take. Derived
    // live rather than cached at construction because reloadTime is mutable at
    // runtime (Temple Guard attack-speed ramp, transform, dismount).
    fireCycleLength() {
        // The -1e-9 keeps a reload that already sits exactly on the grid
        // (siege_onager: 6.0 === 9 * 2/3) from being bumped a whole extra slot
        // by float residue in the division.
        return (
            Math.ceil(this.reloadTime / FIRE_CYCLE_QUANTUM - 1e-9) *
            FIRE_CYCLE_QUANTUM
        );
    }

    // Windup for the shot being started now: attack_delay, plus the stop/turn
    // overhead when this unit had to halt for it.
    //
    // D1 changes only WHICH movement fact is asked. E9 asked the latched
    // "did this unit move at any point since its last shot" (movedSinceShot);
    // R5b asks the instantaneous "was it moving on the tick the cooldown came
    // up" (wasMoving), because that is the thing the pre-shot delay physically
    // pays for -- coming to a halt. A unit that repositioned early and then
    // stood waiting out the rest of its reload is already stopped when the
    // cooldown expires and owes nothing, which is §1b's measurement.
    rangedWindup() {
        const hadToStop = R5B.stopToFire
            ? this.wasMoving
            : this.movedSinceShot;
        return this.attackDelay + (hadToStop ? RANGED_STOP_OVERHEAD : 0);
    }

    // ===== D2 BALLISTIC LEAD + ARRIVAL RESOLUTION =====

    // Per-tick velocity in px/s, from the ground actually covered last tick.
    // Called once per unit per tick by Simulation.update(), before anyone
    // moves. The first call only seeds the baseline (the scenario assigns x/y
    // after construction), so nothing is ever launched at a phantom velocity.
    refreshVelocity(dt) {
        if (this.velSeeded && dt > 0) {
            this.velX = (this.x - this.prevTickX) / dt;
            this.velY = (this.y - this.prevTickY) / dt;
        } else {
            this.velX = 0;
            this.velY = 0;
        }
        this.prevTickX = this.x;
        this.prevTickY = this.y;
        this.velSeeded = true;
        this.recordPositionSample(dt);
    }

    // Push this tick's pre-move position into the trailing history ring (P2).
    // Costs one write and no allocation after the first tick; the buffer is
    // pure measurement -- it feeds windowVelocity() and nothing else, takes no
    // rng draw, and is deliberately absent from Simulation.stateHash() for the
    // same reason the event log is: it cannot influence a battle except
    // through the aim point, which is hashed via the positions it produces.
    recordPositionSample(dt) {
        if (!(dt > 0)) return;
        if (this.histX === null) {
            // +1 because the window is measured BETWEEN the oldest and the
            // newest sample: N intervals of dt need N+1 samples.
            const cap = Math.max(2, Math.round(LEAD_WINDOW_SECONDS / dt) + 1);
            this.histX = new Float64Array(cap);
            this.histY = new Float64Array(cap);
            this.histT = new Float64Array(cap);
        }
        this.histClock += dt;
        const cap = this.histX.length;
        this.histX[this.histHead] = this.x;
        this.histY[this.histHead] = this.y;
        this.histT[this.histHead] = this.histClock;
        this.histHead = (this.histHead + 1) % cap;
        if (this.histCount < cap) this.histCount++;
    }

    // The velocity a shooter should lead this unit by: its displacement over
    // the trailing window, divided by that window's own length. A MEASUREMENT of recent
    // motion, not a behaviour constant -- see LEAD_WINDOW_SECONDS.
    //
    // Read entirely out of the ring buffer (oldest sample -> newest sample),
    // never off the live x/y, so every shooter on a tick measures every target
    // off the same snapshot whatever order the teams update in. That is the
    // same invariant Simulation.update() preserves by refreshing all
    // velocities before anyone moves.
    //
    // Warm-up (fewer samples than the window) uses whatever span exists, which
    // is honest: it is still "displacement over the interval it was measured
    // over". With one sample or a zero span there is nothing to measure and it
    // reports zero.
    windowVelocity() {
        const n = this.histCount;
        if (n < 2) return { vx: 0, vy: 0 };
        const cap = this.histX.length;
        const newest = (this.histHead - 1 + cap) % cap;
        const oldest = (this.histHead - n + cap) % cap;
        const span = this.histT[newest] - this.histT[oldest];
        if (!(span > 0)) return { vx: 0, vy: 0 };
        return {
            vx: (this.histX[newest] - this.histX[oldest]) / span,
            vy: (this.histY[newest] - this.histY[oldest]) / span,
        };
    }

    // Accuracy dispersion in PIXELS: the radius an accuracy-roll failure may
    // throw the aim point by. Prefers a dict field (so the day extraction
    // starts carrying accuracy_dispersion this lookup silently becomes dead
    // code), then the dat-read per-slug table, and returns 0 for a unit we
    // have no dat value for -- which fireProjectile reads as "use the legacy
    // MISS_SPREAD scatter". See constants.js for the values and the reasoning.
    accuracyDispersionPx() {
        const fromDict = this.accuracyDispersion;
        if (fromDict > 0) return fromDict * TILE_SIZE;
        const bySlug = ACCURACY_DISPERSION_BY_SLUG.get(this.slug);
        return bySlug > 0 ? bySlug * TILE_SIZE : 0;
    }

    // Where to throw the shot so it meets a moving target: the intercept of
    // the target's current velocity with the projectile's flight time.
    //
    // The tape says this is what the game does. Over 1,501 reconstructed tape
    // flights the largest perpendicular deviation from a track's own
    // launch->impact chord is 0.00122 tiles -- the arrow does NOT home -- yet
    // for victims that moved, the landing point sits 0.50-0.88 tiles from
    // where the victim was at LAUNCH and only 0.22-0.38 tiles from where it
    // was at IMPACT. It is aimed at where the target will be. (The dat agrees
    // that nothing homes: smart_mode = 0 on all four of these projectiles.)
    //
    // Solved by two fixed-point iterations rather than the quadratic: the
    // flight time depends on the distance to the aim point, which depends on
    // the flight time. Two passes converge to well under a pixel at these
    // speeds and, unlike the closed form, cannot produce a complex root when
    // the target outruns the projectile.
    // P2 (Round 5d-1) changes WHICH velocity goes into the intercept and how
    // hard it is solved. R5b used `target.velX/velY` -- the ground covered in
    // the ONE previous tick -- and R5c Q2d measured the consequence: on the
    // nine accuracy-100 sides the engine applied any lead at all on 0.0-9.0%
    // of shots, median 0.000 tiles, because D1 stops units to fire and D4
    // parks them at the approach margin, so a target that has been walking for
    // a second is standing still on the launch tick. The tape, meanwhile, aims
    // a FULL intercept of the target's real motion (lead ratio ~0.9-1.2 on
    // displaced targets) and lands 0.118-0.226 tiles from where the victim
    // actually is at impact -- the position-noise floor.
    //
    // The fix is to measure the target's motion over a trailing 0.3 s window
    // instead of one tick (windowVelocity), and to iterate the fixed point to
    // convergence rather than stopping at two passes. Both are gated on
    // R5D1.trailingWindowLead; with it off this is R5b's function verbatim.
    aimPointFor(target) {
        if (!R5B.ballisticLead) return { x: target.x, y: target.y };
        const speed =
            this.projectileSpeed > 0 ? this.projectileSpeed : 7 * TILE_SIZE;
        let vx = target.velX;
        let vy = target.velY;
        let passes = 2;
        if (R5D1.trailingWindowLead) {
            const wv = target.windowVelocity();
            vx = wv.vx;
            vy = wv.vy;
            // Iterate to convergence instead of two fixed passes. The map is a
            // contraction whenever the target is slower than the projectile
            // (every case in this corpus), so this settles in 3-6 passes; the
            // cap is what keeps a hypothetical faster-than-the-arrow target
            // from spinning, and degrades to "the best aim point we had",
            // exactly as the two-pass version already did.
            passes = 24;
        }
        let ax = target.x;
        let ay = target.y;
        for (let i = 0; i < passes; i++) {
            const dx = ax - this.x;
            const dy = ay - this.y;
            const flight = Math.sqrt(dx * dx + dy * dy) / speed;
            const nx = target.x + vx * flight;
            const ny = target.y + vy * flight;
            const moved = Math.abs(nx - ax) + Math.abs(ny - ay);
            ax = nx;
            ay = ny;
            // Converged well inside a pixel -- four orders of magnitude below
            // the ~9-10 px overlap radius that decides a hit.
            if (R5D1.trailingWindowLead && moved < 1e-9) break;
        }
        return { x: ax, y: ay };
    }

    // ===== D4 APPROACH MARGIN + HYSTERESIS =====
    // Pre-R5b a ranged unit approached until inRange() flipped and then
    // stopped dead on the reach lip: the forensics measured its launch-range
    // distribution DEGENERATE at its own reach (median == reach to two
    // digits, p90 == median) against a tape median 0.9-1.4 tiles closer with
    // a broad spread. Stopping on the lip is also unstable -- a hair of
    // target movement puts the target back out of reach -- which is how
    // heavy_cav_archer__vs__hand_cannoneer ends up HOLDING at 8.06 tiles
    // against a 7.62 reach while the tape's two armies close to 4.84 and sit
    // at ~6.4 with 96-100% of both sides in reach.
    //
    // The margin is physical, not fitted: a unit closes until its target is
    // one of its OWN BODY DIAMETERS inside reach, and only re-approaches once
    // the target has actually left reach. The band between those two
    // distances is the hysteresis, and it is the same quantity -- there is no
    // second number to choose. Clamped so it can never walk a unit into its
    // own minimum-range dead zone.
    //
    // Approach/hold only. Kiting and retreat (E10a) are untouched.
    // ===== R5d-T3: THE LATCH IS GONE =====
    // The hysteresis above was measured, and what it actually produces is a
    // one-shot approach. `rangedClosed` is set the first time a unit reaches
    // `reach - 2r` and is cleared ONLY when the target leaves reach entirely,
    // so a unit that has once closed never approaches again while its target
    // survives anywhere inside reach -- including at the lip, 2r further out
    // than the margin it is supposed to hold. The consequence is measured in
    // r5c_depth_forensics.md §6a: in heavy_cav_archer__vs__hand_cannoneer the
    // tape's archers close continuously for the whole 41 s (radial speed
    // positive in 20 of 30 buckets, +3.06 tiles cumulative, separation
    // 9.03 -> 4.84) while the engine's close for 5 s and then stop dead
    // (radial +-0.00 in eight post-t=5 buckets, nearest-enemy distance pinned
    // at 6.55 for 14 s and then RECEDING to 7.21). That fight's HP error is
    // 18.7 points and its army is a 1.62-tile-deep line against the tape's
    // 6.25-tile column.
    //
    // T3 replaces the latch with the same margin as a CONTINUOUS condition:
    // approach whenever the target is outside `reach - 2r`, hold inside it, no
    // memory. It introduces no constant -- it deletes state. The band between
    // `inner` and `reach` is no longer a hold zone that a unit can be trapped
    // in; it is simply outside the margin, so the unit keeps walking. Army
    // elongation is NOT modelled here and no formation logic is added: if it
    // appears it has to emerge from units re-approaching different targets.
    rangedShouldApproach() {
        if (!R5B.approachMargin) return !this.inRange();
        const dist = this.distanceTo(this.target);
        const reach =
            this.attackRange + this.radius + this.target.radius;
        const inner = Math.max(this.minAttackRange, reach - 2 * this.radius);
        if (R5D.reapproach) return dist > inner;
        if (dist > reach) {
            this.rangedClosed = false;      // target has left reach entirely
        } else if (dist <= inner) {
            this.rangedClosed = true;       // settled inside the margin
        }
        return !this.rangedClosed;
    }

    // ===== D3 IN-FLIGHT DAMAGE ACCOUNTING =====
    // The engine's single largest shot-outcome error was overkill in the air:
    // it wasted 13.6-37.7% of its shots on units that died before the arrow
    // landed, where the tape's hand cannoneer -- in all three of its
    // recordings -- wastes exactly 0.0%. Tape HCs also spread over 3.0-5.0
    // distinct victims per reload window against the engine's 1.98-3.95: the
    // same fact seen from the other side. They are not all shooting the same
    // dying unit.
    //
    // The rule carries no constant and no randomness: a shooter counts the
    // damage already on its way to a candidate, and if that is enough to kill
    // it, shoots something else instead.

    // Damage of this team's projectiles already in flight toward `unit` that
    // will LAND BEFORE a shot fired now would.
    //
    // The arrival-order qualifier is not a softening knob, it is what makes
    // the test mean what it says. "The target is already dead" is only true
    // from this shot's point of view if that damage gets there first; a
    // projectile that lands after mine does not make mine wasted, because
    // mine lands while the target is still alive and contributes to killing
    // it. Counting every projectile regardless of arrival time made a nearby
    // shooter defer to a distant one whose arrow was still seconds away,
    // which drove in-flight waste to ~0 on sides where the tape measures
    // 13-33% (imp_elite_skirm) and 8-21% (heavy_cav_archer).
    inboundDamageOn(unit, myFlightTime = Infinity) {
        // R5d-T2: shots committed earlier in THIS tick are accounted by the
        // claim ledger instead (coveredDamageOn), unconditionally rather than
        // by arrival order. Skipping them here is what stops the same arrow
        // being counted twice when it happens to also pass the eta test.
        const claimed = R5D.sameTickClaims && this.sim && this.sim.tickClaimShots
            ? this.sim.tickClaimShots
            : null;
        let total = 0;
        for (const p of this.sim.projectiles) {
            if (p.done) continue;
            if (p.team !== this.team) continue;
            if (p.targetUnit !== unit) continue;
            if (claimed && claimed.has(p)) continue;
            if (p.speed > 0) {
                const rx = p.targetX - p.x;
                const ry = p.targetY - p.y;
                const eta = Math.sqrt(rx * rx + ry * ry) / p.speed;
                if (eta >= myFlightTime) continue;
            }
            total += p.plannedDamage;
        }
        return total;
    }

    // All friendly damage already COMMITTED to `unit` that a shot fired at it
    // right now would duplicate: the in-flight damage that arrives first (R5b
    // D3, above) plus this tick's claims (R5d T2). One function so every
    // coverage question in the engine -- the legacy D3 redirect and T1's
    // per-shot selection alike -- asks it the same way.
    coveredDamageOn(unit) {
        let total = this.inboundDamageOn(unit, this.flightTimeTo(unit));
        if (R5D.sameTickClaims && this.sim && this.sim.tickClaims) {
            total += this.sim.tickClaims.get(unit) || 0;
        }
        return total;
    }

    // R5d-T2 write side: record that this shot is committed to `victim` for
    // the rest of THIS tick. Called from fireProjectile once the projectile
    // and its damage exist; the projectile itself is remembered so
    // inboundDamageOn can exclude it. Behind the flag, and tolerant of a sim
    // stub with no ledger, so nothing on the off path is touched.
    claimShot(proj, victim, damage) {
        if (!R5D.sameTickClaims) return;
        const sim = this.sim;
        if (!sim || !sim.tickClaims || !victim) return;
        sim.tickClaimShots.add(proj);
        sim.tickClaims.set(victim, (sim.tickClaims.get(victim) || 0) + damage);
    }

    /** Flight time of a shot fired at `enemy` right now, in seconds. */
    flightTimeTo(enemy) {
        const speed =
            this.projectileSpeed > 0 ? this.projectileSpeed : 7 * TILE_SIZE;
        return this.distanceTo(enemy) / speed;
    }

    /** Same reach test as inRange(), for an enemy other than this.target. */
    canReach(enemy) {
        const dist = this.distanceTo(enemy);
        if (dist > this.attackRange + this.radius + enemy.radius) return false;
        if (this.minAttackRange > 0 && dist < this.minAttackRange) return false;
        return true;
    }

    // Who this particular shot should go to. Returns `primary` unchanged
    // unless it is already dead on arrival, in which case the next reachable
    // enemy is taken in the SAME nearest-first order findTarget() acquires in
    // -- this re-picks one shot, it does not re-target the unit.
    pickShotTarget(primary) {
        if (!R5B.inflightAccounting) return primary;
        if (!primary || primary.state === "dead") return primary;
        if (R5D.perShotSelect) return this.selectShotTarget(primary);
        if (this.coveredDamageOn(primary) < primary.currentHp) {
            return primary;
        }

        const foes = this.team === 1 ? this.sim.team2 : this.sim.team1;
        let best = null;
        let bestDist = Infinity;
        for (const foe of foes) {
            if (foe === primary || foe.state === "dead") continue;
            if (!this.canReach(foe)) continue;
            if (this.coveredDamageOn(foe) >= foe.currentHp) continue;
            const d = this.distanceTo(foe);
            if (d < bestDist) {
                bestDist = d;
                best = foe;
            }
        }
        // Nothing reachable is still worth shooting: take the shot anyway,
        // rather than inventing a hold-fire behaviour the tape does not show.
        return best || primary;
    }

    // ===== R5d-T1: PER-SHOT RE-SELECTION =====
    // R5b's redirect only ran when the STANDING target was already covered;
    // otherwise the unit's acquisition target got the shot however stale that
    // pick was. That is measurably not how the tape behaves. Its ranged units
    // re-pick every shot: they fire at their nearest reachable enemy on only
    // 34-65% of launches (engine 56-83%), their chosen victim's rank in the
    // nearest-first ordering is 1.5-3.5 (engine 1.1-2.0), and they re-pick the
    // SAME victim on only 6-26% of consecutive shots (engine up to 66%).
    // r5c_targeting_forensics.md Q1a. And the tape's hand cannoneer never
    // fires at a victim whose death is already covered -- cov% 0.000 on all
    // three of its recordings, and all 23 occasions where its nearest enemy
    // was lethally covered resolved as shoot-something-else, 0 stubborn (Q1c).
    //
    // The rule, whole: at EVERY shot, take the nearest enemy in reach whose
    // remaining hp is not already covered by committed friendly damage
    // (in-flight arriving first + this tick's claims). It is not sticky -- the
    // unit's own `this.target` gets no privilege beyond being one candidate
    // among the reachable ones, and nothing is remembered between shots. If
    // every reachable enemy is covered, the nearest one is shot anyway: no
    // hold-fire, which the tape does not show either. No constant, no rng;
    // ties break on team-array order exactly as findTarget's do.
    selectShotTarget(primary) {
        const foes = this.team === 1 ? this.sim.team2 : this.sim.team1;
        let best = null;
        let bestDist = Infinity;
        let nearest = null;
        let nearestDist = Infinity;
        for (const foe of foes) {
            if (foe.state === "dead") continue;
            if (!this.canReach(foe)) continue;
            const d = this.distanceTo(foe);
            if (d < nearestDist) {
                nearestDist = d;
                nearest = foe;
            }
            if (this.coveredDamageOn(foe) >= foe.currentHp) continue;
            if (d < bestDist) {
                bestDist = d;
                best = foe;
            }
        }
        const stats = this.sim && this.sim.combatStats
            ? this.sim.combatStats[this.team]
            : null;
        if (stats) stats.shotPicks++;
        if (best) return best;
        // Every reachable enemy is already dead on arrival. Diagnostic only --
        // the forensics predict this becomes rare once the choice set widens.
        if (stats) stats.allCovered++;
        return nearest || primary;
    }

    // The launch itself, factored out of update()'s ranged branch so the
    // D1 fast path and the legacy path cannot drift. Starts the windup when
    // there is one, otherwise fires on the spot.
    startRangedShot() {
        const windup = this.rangedWindup();
        if (windup > 0) {
            this.committedAttack = { target: this.target, timeLeft: windup };
            this.state = "attacking";
            this.wasMoving = false;
        } else {
            this.state = "attacking";
            this.performAttack();
            this.fireRecovery = this.postFireRecovery;
            this.movedSinceShot = false;
            this.wasMoving = false;
        }
    }

    // Called the first time a ranged unit moves after firing. The cooldown set
    // at launch carries the STOOD budget (reloadTime - attackDelay); moving
    // converts this cycle to the quantised one, which costs the difference
    // between the two cycle lengths less the extra windup the stop now buys.
    // Net launch-to-launch: (fireCycle - windup) + windup === fireCycle.
    // Latched by movedSinceShot, so it is paid once per cycle however many
    // ticks the unit spends moving.
    markRangedMovement() {
        if (this.movedSinceShot) return;
        this.movedSinceShot = true;
        // D1 REMOVES the quantised-cycle top-up. E9 charged a unit that moved
        // at any point in a cycle the difference up to ceil(reload/Q)*Q; the
        // forensics re-tested that trigger on this corpus (§1b) and found it
        // over-charges -- on ranged-vs-ranged tape a cycle with a little
        // movement in it costs arbalester, imp_elite_skirm and hand_cannoneer
        // NOTHING. The engine was charging it twice over: the quantum, and
        // then the walk-in on top. What remains is the pre-shot delay, paid
        // only by a unit that is actually still moving when its cooldown
        // expires, so the quantum emerges for a continuous runner instead of
        // being imposed on everyone who took a step.
        //
        // movedSinceShot itself is kept: it is what the legacy (flag-off) path
        // reads, and it is still the honest record of "moved this cycle".
        if (R5B.stopToFire) return;
        this.attackCooldown = Math.max(
            0,
            this.attackCooldown +
                (this.fireCycleLength() -
                    this.reloadTime -
                    RANGED_STOP_OVERHEAD),
        );
    }

    update(dt, allUnits, enemies) {
        if (this.state === "dead") return;

        this.attackCooldown = Math.max(0, this.attackCooldown - dt);
        this.fireRecovery = Math.max(0, this.fireRecovery - dt);
        this.attackAnimTimer = Math.max(
            0,
            this.attackAnimTimer - dt,
        );
        this.animHold = Math.max(0, this.animHold - dt);

        this.damageNumbers = this.damageNumbers.filter((dn) => {
            dn.y -= 40 * dt;
            dn.alpha -= dt * 1.5;
            return dn.alpha > 0;
        });

        // HP regen
        if (
            this.hpRegen > 0 &&
            this.currentHp > 0 &&
            this.currentHp < this.maxHp
        ) {
            this.currentHp = Math.min(
                this.maxHp,
                this.currentHp + (this.hpRegen / 60) * dt,
            );
        }

        // Bleed damage tick
        if (this.bleedEffect) {
            this.currentHp -= this.bleedEffect.dps * dt;
            this.bleedEffect.timeRemaining -= dt;
            if (this.bleedEffect.timeRemaining <= 0)
                this.bleedEffect = null;
            if (this.currentHp <= 0) {
                this.currentHp = 0;
                this.state = "dead";
                this.target = null;
                return;
            }
        }

        // Shield recharge
        if (this.shieldRechargeTimer > 0) {
            this.shieldRechargeTimer -= dt;
            if (this.shieldRechargeTimer <= 0) {
                this.shieldCharges = Math.min(
                    this.shieldCharges + 1,
                    this.dodgeShieldMax,
                );
                if (this.shieldCharges < this.dodgeShieldMax) {
                    this.shieldRechargeTimer =
                        this.dodgeShieldRecharge;
                } else {
                    this.shieldRechargeTimer = 0;
                }
            }
        }

        // Charge recharge timer (melee charge + charge projectiles)
        if (this.chargeTimer > 0)
            this.chargeTimer = Math.max(0, this.chargeTimer - dt);

        // Charge-slow expiry: restore movement speed
        if (this.slowTimer > 0) {
            this.slowTimer = Math.max(0, this.slowTimer - dt);
            if (this.slowTimer <= 0) this.moveSpeed = this.baseMoveSpeed;
        }

        // Ally-death heal-over-time (Guecha Warrior)
        if (
            this.allyHealRemaining > 0 &&
            this.currentHp > 0 &&
            this.currentHp < this.maxHp
        ) {
            const heal = Math.min(
                this.allyHealRate * dt,
                this.allyHealRemaining,
            );
            this.currentHp = Math.min(this.maxHp, this.currentHp + heal);
            this.allyHealRemaining -= heal;
        }

        // Nearby-ally auras (Monaspa attack, Shu %HP)
        if (this.attackBonusNearby > 0 || this.hpNearbyPercentPerUnit > 0) {
            const auraRadius = 5 * TILE_SIZE;
            const allies =
                this.team === 1 ? this.sim.team1 : this.sim.team2;
            let n = 0;
            for (const ally of allies) {
                if (ally === this || ally.state === "dead") continue;
                if (this.distanceTo(ally) <= auraRadius) n++;
            }
            if (this.attackBonusNearby > 0) {
                const cap = this.nearbyBonusCount || n;
                this.auraAttackBonus =
                    this.attackBonusNearby * Math.min(n, cap);
            }
            if (this.hpNearbyPercentPerUnit > 0) {
                const cap = this.hpNearbyMaxUnits || n;
                const base = this.maxHp - this.auraHpBonus;
                const targetBonus =
                    base *
                    (this.hpNearbyPercentPerUnit / 100) *
                    Math.min(n, cap);
                const delta = targetBonus - this.auraHpBonus;
                this.maxHp += delta;
                if (delta > 0) this.currentHp += delta;
                else if (this.currentHp > this.maxHp)
                    this.currentHp = this.maxHp;
                this.auraHpBonus = targetBonus;
            }
        }

        // HP transform (Jian Swordsman): swap to transformed stats once
        if (this.hpTransformThreshold > 0 && !this.isTransformed) {
            if (
                this.currentHp <=
                    this.maxHp * this.hpTransformThreshold &&
                this.currentHp > 0
            ) {
                this.isTransformed = true;
                if (this.transformMaxHp > 0) {
                    this.maxHp = this.transformMaxHp;
                    if (this.currentHp > this.maxHp)
                        this.currentHp = this.maxHp;
                    if (this.transformAttack > 0)
                        this.attack = this.transformAttack;
                    this.meleeArmor = this.transformMeleeArmor;
                    this.pierceArmor = this.transformPierceArmor;
                    if (this.transformAttacks)
                        this.attacks = this.transformAttacks;
                    if (this.transformArmors)
                        this.armors = this.transformArmors;
                    if (this.transformAttackSpeed > 0) {
                        this.attackSpeed = this.transformAttackSpeed;
                        this.reloadTime = 1.0 / this.transformAttackSpeed;
                    }
                    if (this.transformMoveSpeed > 0) {
                        this.moveSpeed = this.transformMoveSpeed * TILE_SIZE;
                        this.baseMoveSpeed = this.moveSpeed;
                    }
                } else {
                    this.killBonusAttack += 3;
                }
            }
        }

        // Clean up blockedTargets: remove dead enemies
        for (const bt of this.blockedTargets) {
            if (bt.state === "dead") this.blockedTargets.delete(bt);
        }
        // If all alive enemies are blocked, clear and retry
        if (
            this.blockedTargets.size > 0 &&
            this.blockedTargets.size >=
                enemies.filter((e) => e.state !== "dead").length
        ) {
            this.blockedTargets.clear();
        }

        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }
        if (!this.target) {
            this.state = "idle";
            return;
        }

        // E14 rule 2 (BUMP RETARGET). Checked here, after the target is known
        // to be alive and BEFORE anything acts on it, so a unit that spent the
        // tick shoulder to shoulder with the wrong enemy swings at the one it
        // is actually touching. Costs nothing for a unit that can reach its own
        // target (the inRange() early-out) or for any ranged unit.
        this.meleeBumpRetarget(enemies);

        if (this.isRanged()) {
            const shouldKite = !this.target.isRanged();

            // Committed shot: locked in the windup animation, can't move.
            // Mirrors the melee branch's committedAttack pattern and
            // simulation_real.py:938-956. The windup is paid INSIDE the reload
            // period, not on top of it: when it elapses the projectile flies
            // and only the REMAINDER of the reload becomes the post-fire
            // cooldown, so hit-to-hit stays == reloadTime.
            //
            // Checked BEFORE tooClose() on purpose (python does the same): a
            // shot already committed still completes even if the target slips
            // into the min-range dead zone mid-windup.
            if (this.committedAttack) {
                this.committedAttack.timeLeft -= dt;
                // "attacking" (not "committed") keeps the draw-the-bow
                // animation the renderer keys off state — the same thing the
                // pre-fix code displayed while winding up.
                this.state = "attacking";
                if (this.committedAttack.timeLeft <= 0) {
                    const target = this.committedAttack.target;
                    if (target && target.state !== "dead") {
                        // performAttack reads this.target; restore it in case
                        // the primary target changed during the windup.
                        const prevTarget = this.target;
                        this.target = target;
                        this.performAttack();
                        this.target =
                            prevTarget && prevTarget.state !== "dead"
                                ? prevTarget
                                : target;
                    }
                    this.committedAttack = null;
                    // performAttack (every path, charge volley included) leaves
                    // cooldown = reloadTime; subtract the windup already spent.
                    // This is the STOOD-STILL budget (cycle == reloadTime); if
                    // the unit moves before its next shot markRangedMovement()
                    // tops it up to the quantised stand-and-shoot cycle.
                    this.attackCooldown = Math.max(
                        0,
                        this.reloadTime - this.attackDelay,
                    );
                    // Frozen while the shot recovers (E9). Runs CONCURRENTLY
                    // with the cooldown above -- it blocks movement, not
                    // reloading -- which is why the tape's cadence is the
                    // quantum alone and not reload + recovery.
                    this.fireRecovery = this.postFireRecovery;
                    this.movedSinceShot = false;
                    this.wasMoving = false;
                }
                return;
            }

            // Post-fire recovery: immobilised, and deliberately checked before
            // tooClose() so the unit cannot even back out of its min-range dead
            // zone until the shot has recovered.
            if (this.fireRecovery > 0) {
                this.state = "attacking";
                this.wasMoving = false;
                return;
            }

            // ===== D1 STOP-TO-FIRE (R5B) =====
            // The launch test is now the FIRST thing the ranged branch asks,
            // every tick: "cooldown expired and something in reach?" Before
            // R5b it was the fourth branch of an if/else chain whose third arm
            // was `attackCooldown > 0 -> stand`, so a reloading ranged unit
            // parked itself wherever it happened to be -- including well
            // outside its own reach -- and only began to approach once the
            // reload had already elapsed. That single ordering is what the
            // forensics measured as "the engine is idle even when it has a
            // target" (engine in-reach 73.8% vs the tape's 91.6%), as the
            // moving-cadence overshoot (launch-to-launch = reload + the whole
            // walk-in, e.g. heavy_cav_archer 3.90 s against a 2.00 s quantum),
            // and as heavy_cav_archer__vs__hand_cannoneer's refusal to close
            // (held at 8.06 tiles, ABOVE the 7.62 reach).
            //
            // The rule, in one line: a ranged unit fires the instant its
            // cooldown expires if a target is in reach, and it approaches
            // whenever the target is not -- reloading or not. Whether it had
            // to STOP for the shot is now an instantaneous fact (was it moving
            // on the tick the cooldown came up?), not the latched
            // "moved at any point this cycle" of E9's trigger.
            //
            // The quantised cycle is no longer imposed; it EMERGES. A unit
            // that is genuinely running at every expiry pays the measured
            // pre-shot delay on every cycle (reload + 0.15), while one that
            // finished repositioning before the cooldown came up pays nothing
            // and re-fires at a bare reload -- which is exactly what §1b of
            // the forensics measures on ranged-vs-ranged tape (arbalester,
            // imp_elite_skirm and hand_cannoneer all sit at bare reload
            // through the mv<60% buckets; only heavy_cav_archer is graded).
            const canFireNow =
                R5B.stopToFire && this.attackCooldown <= 0 && this.inRange();
            if (canFireNow) {
                this.startRangedShot();
            } else if (this.tooClose()) {
                this.state = "kiting";
                this.markRangedMovement();
                this.moveAwayFromTarget(
                    dt,
                    allUnits,
                    this.kiteSteering(allUnits, enemies),
                );
                this.wasMoving = true;
            } else if (this.attackCooldown > 0 && shouldKite) {
                // Kiting a MELEE foe is E10a's business and is untouched here.
                this.state = "kiting";
                this.markRangedMovement();
                this.moveAwayFromTarget(
                    dt,
                    allUnits,
                    this.kiteSteering(allUnits, enemies),
                );
            } else if (R5B.stopToFire) {
                if (this.rangedShouldApproach()) {
                    // Not closed yet -- CLOSE, whether or not the reload is
                    // done. With D4 this keeps going past the reach lip until
                    // the target is a body diameter inside it.
                    this.state = "moving";
                    this.markRangedMovement();
                    this.moveTowardTarget(dt, allUnits);
                    this.wasMoving = true;
                } else {
                    // Settled: hold position and keep the target.
                    this.state = "attacking";
                    this.wasMoving = false;
                }
            } else if (this.attackCooldown > 0) {
                this.state = "attacking";
            } else if (this.inRange()) {
                // Cooldown done, in range — start the windup for the next shot.
                // The windup carries the stop/turn overhead when this unit had
                // to halt to take the shot, so a delay-0 shooter that was
                // moving (siege_onager) still pays one.
                const windup = this.rangedWindup();
                if (windup > 0) {
                    this.committedAttack = {
                        target: this.target,
                        timeLeft: windup,
                    };
                    this.state = "attacking";
                    this.wasMoving = false;
                } else {
                    this.state = "attacking";
                    this.performAttack();
                    this.fireRecovery = this.postFireRecovery;
                    this.movedSinceShot = false;
                    this.wasMoving = false;
                }
            } else {
                this.state = "moving";
                this.markRangedMovement();
                this.moveTowardTarget(dt, allUnits);
            }
        } else {
            // Charge projectile attack (Fire Lancer): fire at range before melee.
            // Recharges if the unit has a charge_recharge_time; otherwise it is
            // a one-shot (legacy fallback for units whose recharge data isn't
            // populated). Mirrors simulation_real.py's charge_ready gate.
            const chargeReady =
                this.chargeRechargeTime > 0
                    ? this.chargeTimer <= 0
                    : !this.hasUsedCharge;
            if (
                this.chargeProjectileCount > 0 &&
                chargeReady &&
                this.attackCooldown <= 0 &&
                this.target
            ) {
                const distToTarget = this.distanceTo(this.target);
                const chargeRange =
                    this.chargeAttackRange +
                    this.radius +
                    this.target.radius;
                if (distToTarget <= chargeRange) {
                    // In charge range -- fire charge projectiles
                    if (this.chargeRechargeTime > 0) {
                        this.chargeTimer = this.chargeRechargeTime;
                    } else {
                        this.hasUsedCharge = true;
                    }
                    this.state = "attacking";
                    this.attackAnimTimer = 0.3;
                    this.triggerAttackAnim();
                    // The volley is a spray, not a focused burst: the tapes cap
                    // a single volley's same-instant victim count at exactly
                    // chargeProjectileCount with a mean near 2, i.e. the three
                    // projectiles land on up to three DIFFERENT enemies. Spread
                    // them over the nearest distinct living foes inside charge
                    // range; if fewer exist, the surplus re-hits the ones we
                    // picked (a lone target still eats the whole volley).
                    const volleyTargets = this.pickChargeVolleyTargets();
                    for (
                        let cp = 0;
                        cp < this.chargeProjectileCount;
                        cp++
                    ) {
                        this.fireChargeProjectile(
                            volleyTargets[cp % volleyTargets.length],
                        );
                    }
                    this.attackCooldown = this.reloadTime;
                } else if (this.meleeMoveLocked()) {
                    // E15b rule 1: still finishing a melee swing animation, so
                    // it cannot close on its charge target either. Same plant
                    // the main melee branch below uses.
                    this.state = "attacking";
                    this.wasMoving = false;
                } else {
                    // Move toward target to get in charge range
                    this.state = "moving";
                    this.moveTowardTarget(dt, allUnits);
                    this.wasMoving = true;
                }
            } else if (this.committedAttack) {
                this.committedAttack.timeLeft -= dt;
                this.state = "committed";
                if (this.committedAttack.timeLeft <= 0) {
                    const target = this.committedAttack.target;
                    if (target.state !== "dead") {
                        this.performAttackOn(target);
                    }
                    this.committedAttack = null;
                    // The windup is spent INSIDE the reload period, not added
                    // to it: only the remainder becomes the post-swing
                    // cooldown, so hit-to-hit stays == reloadTime. (Delay-0
                    // melee never reaches here — it fires via performAttack.)
                    this.attackCooldown = Math.max(
                        0,
                        this.reloadTime - this.attackDelay,
                    );
                    this.wasMoving = false;
                }
            } else if (this.inRange()) {
                if (this.attackCooldown <= 0) {
                    if (this.attackDelay > 0) {
                        this.committedAttack = {
                            target: this.target,
                            timeLeft: this.attackDelay,
                        };
                        this.state = "committed";
                        this.wasMoving = false;
                    } else {
                        this.state = "attacking";
                        this.performAttack();
                    }
                } else {
                    this.state = "attacking";
                }
            } else if (this.meleeMoveLocked()) {
                // E15b rule 1 (SWING RECOVERY PLANT). This is the branch the
                // tape's swing-phase ramp indicts. Pre-E15b the ONLY thing that
                // planted a melee unit was `inRange()` being true, so the moment
                // its victim died or stepped out of reach it walked on the very
                // next tick -- phase 0.0-0.1 of the reload cycle, where the tape
                // says it is moving 0.90% of the time. Now it stands and
                // finishes the swing first.
                //
                // NOT double-counting the in-range plant above: that one is
                // gated on distance and has no duration, this one is gated on
                // time-since-landing and has no distance. A unit still in reach
                // of a living foe never reaches here at all.
                this.state = "attacking";
                this.wasMoving = false;
            } else {
                this.state = "moving";
                this.moveTowardTarget(dt, allUnits);
                this.wasMoving = true;
            }
        }
    }

    performAttack() {
        if (!this.target || this.target.state === "dead") return;
        // Ranged charge volley (Fire Archer/Xianbei/Bolas). recharge<=0 fires
        // every attack and replaces the normal shot; recharge>0 adds then recharges.
        if (
            this.isRanged() &&
            this.chargeProjectileCount > 0 &&
            this.chargeTimer <= 0
        ) {
            for (let c = 0; c < this.chargeProjectileCount; c++)
                this.fireChargeProjectile(this.target);
            if (this.chargeRechargeTime > 0) {
                this.chargeTimer = this.chargeRechargeTime;
            } else {
                this.attackCooldown = this.reloadTime;
                return;
            }
        }
        let numProjectiles = 1 + this.extraProjectiles;
        if (
            this.firstAttackExtraProjectiles > 0 &&
            !this.hasUsedFirstAttack
        ) {
            numProjectiles += this.firstAttackExtraProjectiles;
            this.hasUsedFirstAttack = true;
        }
        // Organ Gun: extra projectiles scatter to different enemies.
        let scatter = null;
        if (this.extraProjScatter && this.isRanged()) {
            const foes =
                this.team === 1 ? this.sim.team2 : this.sim.team1;
            scatter = foes.filter(
                (e) => e.state !== "dead" && e !== this.target,
            );
        }
        // D3: pick this SHOT's victim. Unchanged from this.target unless the
        // primary is already covered by friendly damage in the air, in which
        // case the shot goes to the next reachable enemy instead of being
        // spent on a corpse-to-be. Does not re-target the unit itself.
        const primary = this.isRanged()
            ? this.pickShotTarget(this.target)
            : this.target;
        let scatI = 0;
        for (let p = 0; p < numProjectiles; p++) {
            if (primary && primary.state !== "dead") {
                if (this.isRanged()) {
                    let tgt = primary;
                    if (p > 0 && scatter && scatter.length > 0) {
                        tgt = scatter[scatI % scatter.length];
                        scatI++;
                    }
                    this.fireProjectile(tgt, p > 0);
                } else {
                    this.performAttackOn(primary);
                }
            }
        }
        this.attackCooldown = this.reloadTime;
    }

    // Event recorder for cross-engine calibration (see Simulation.eventLog in
    // sim.js): called once per projectile actually created, from both
    // fireProjectile and fireChargeProjectile, so every arrow/bolt/charge
    // volley gets exactly one missile record with a distinct id. The id
    // counter lives ONLY on the log object -- never on `sim` -- so it cannot
    // exist (and cannot affect determinism) while recording is off. Read-only
    // otherwise: no rng draw, no ordering change, not in stateHash().
    recordMissile() {
        const log = this.sim && this.sim.eventLog;
        if (!log) return;
        log._nextMissileId = (log._nextMissileId || 0) + 1;
        log.missiles.push({
            t: this.sim.battleTime,
            id: log._nextMissileId,
            fired_from: this.id,
            owner: this.team,
        });
    }

    fireProjectile(target, isExtra = false) {
        // Diagnostic counter (see Simulation.combatStats): one swing per
        // projectile launched, so a multi-arrow volley (Chu Ko Nu, Organ Gun)
        // counts once per arrow — that is what makes hitsLanded/swings read as
        // a per-projectile accuracy rate. Nothing here is read back by the
        // engine and no rng is drawn, so behaviour is untouched.
        if (this.sim && this.sim.combatStats)
            this.sim.combatStats[this.team].swings++;
        const damage =
            this.getDamageAgainst(target) +
            Math.floor(this.killBonusAttack);
        // Accuracy roll (mirrors simulation_real.py fire_projectile). A miss
        // still spawns a projectile but applies 0 direct damage; on impact it
        // grazes a random nearby unit instead. Primary arrow uses unit accuracy;
        // extra arrows use baseAccuracy.
        const accuracy = isExtra ? this.baseAccuracy : this.accuracy;
        const willHit = accuracy >= 1.0 ? true : this.sim.rng.next() < accuracy;
        const MISS_SPREAD = 2.0 * TILE_SIZE; // tiles, matches MISS_SPREAD_RADIUS
        const speed =
            this.projectileSpeed > 0
                ? this.projectileSpeed
                : 7 * TILE_SIZE;
        const attacker = this;

        // ===== D2: WHERE THE SHOT IS THROWN =====
        // Pre-R5b the aim point was `target.x, target.y` at LAUNCH and the hit
        // was decided by the accuracy roll alone -- the projectile's flight was
        // decorative, so a shot could not miss a target that walked away, and a
        // dat-100%-accuracy unit could not miss at all. The tape says both are
        // wrong: 100%-accuracy units miss 6-27% of their shots against movers
        // (and ~0% against stationary targets), and the hand cannoneer's
        // on-target failure is 4-12%, not the flat 25% its dat accuracy implies.
        //
        // The replacement has three parts and no new constant:
        //   1. aim at the INTERCEPT (aimPointFor), so a mover is led;
        //   2. an accuracy-roll failure DISPLACES that aim point by up to the
        //      dat's accuracy_dispersion instead of teleporting the shot 2
        //      tiles away -- so a near miss can still connect;
        //   3. the hit is resolved ON ARRIVAL against where the target actually
        //      is by then (see the onHit closure), not predetermined here.
        const aim = this.aimPointFor(target);
        let impactX = aim.x;
        let impactY = aim.y;
        const dispersionPx = this.accuracyDispersionPx();
        // Legacy scatter is kept for any unit whose dat dispersion we have not
        // read (dispersionPx === 0): those keep the flat 2-tile miss throw, so
        // D2 cannot silently invent accuracy for the rest of the roster.
        const scatterPx = dispersionPx > 0 ? dispersionPx : MISS_SPREAD;
        if (R5B.ballisticLead && !willHit) {
            // Same two rng draws, in the same order and from the same stream,
            // as the legacy miss throw -- this is the EXISTING accuracy roll's
            // consequence relocated from impact time to launch time, not a new
            // random source. It MUST stay behind the flag: the legacy path
            // still draws these two at arrival, and drawing them twice would
            // desync the rng and break the off-switch's bit-identity.
            const missAngle = this.sim.rng.next() * 2 * Math.PI;
            const missDist = this.sim.rng.next() * scatterPx;
            impactX += missDist * Math.cos(missAngle);
            impactY += missDist * Math.sin(missAngle);
        }
        // A shot connects when it arrives within the target's body plus the
        // projectile's own body (both dat collision radii).
        const projRadiusPx = PROJECTILE_RADIUS_TILES * TILE_SIZE;
        // Siege splash: every unit blasts at its TRUE splash_radius. This used
        // to inflate single stones to a 2.5-tile minimum "so mangonel/onager
        // can hit clusters"; the tapes say otherwise (see the blast-falloff
        // commit and tests/js/engine/blast_falloff.test.mjs).
        const splashR =
            attacker.splashRadius > 0 ? attacker.splashRadius : 0;
        if (!R5B.ballisticLead) {
            // Legacy aim: freeze the impact at the target's launch position.
            impactX = target.x;
            impactY = target.y;
        }
        // `didHit` is filled in by the closure below and read afterwards by the
        // splash / pass-through / kill-bonus blocks, all of which used to key
        // off the launch-time `willHit`.
        let didHit = false;
        const proj = new Projectile(
            this.x,
            this.y,
            impactX,
            impactY,
            speed,
            this.team,
            this.projectileKind,
            () => {
                const targetWasAlive = target.state !== "dead";
                if (R5B.ballisticLead) {
                    // ===== D2: ARRIVAL RESOLUTION =====
                    // The shot has landed at (impactX, impactY). Whether it
                    // connects is decided HERE, against where the target
                    // actually is now -- not by a flag set when it was fired.
                    // A target that stepped off the aim point is missed, which
                    // is the mechanism behind the tape's dodge rate and behind
                    // hand cannoneer flights that reach 9.3 tiles on a 7-tile
                    // unit (the aim was thrown ahead of a runner).
                    // Under P1 a failed roll can never be a FULL hit, however
                    // close its displaced landing point came down to the
                    // primary -- that case is the measured half hit, handled
                    // below. `didHit` therefore stays false for it, and with
                    // it every downstream consequence of a clean hit (splash,
                    // pass-through, bleed, kill bonus).
                    const rollFailedUnderP1 =
                        R5D1.reducedDamageHits && !willHit;
                    if (targetWasAlive && !rollFailedUnderP1) {
                        const dx = target.x - impactX;
                        const dy = target.y - impactY;
                        const reach = target.radius + projRadiusPx;
                        didHit = dx * dx + dy * dy <= reach * reach;
                    }
                    if (rollFailedUnderP1) {
                        // ===== P1: REDUCED-DAMAGE DISPLACED HIT =====
                        // The accuracy roll failed, so this shot was thrown off
                        // its aim point by the dat dispersion at launch. What
                        // it does now is decided ENTIRELY at its landing point:
                        // whoever's body that point is inside takes exactly
                        // HALF the final post-armor damage, unrounded, and if
                        // it is inside nobody's the shot grounds. It does NOT
                        // matter whose bodies the flight crossed on the way --
                        // there is no swept collision here and the tape agrees
                        // there should not be: one confirmed stray in the whole
                        // corpus, over flights that cross whole formations.
                        //
                        // R5c Q0 measured all three parts:
                        //  * the value is half of the FINAL damage, not half
                        //    the raw attack then armor (6.5 / 4.5 / 5.5 against
                        //    fulls of 13 / 9 / 11, with the .5 recorded), and
                        //    is NOT floored;
                        //  * the intended target is the usual victim, not an
                        //    excluded one -- 26 of 27 reduced hits landed on
                        //    the unit the shot was aimed at, because a 0.25-
                        //    0.30 tile median displacement rarely clears a
                        //    0.2 + 0.1 tile body;
                        //  * the window is the landing point against body plus
                        //    projectile radius, the same overlap test a
                        //    successful shot uses -- not the enemy's centre
                        //    inside its own radius.
                        // R5b's branch got all three wrong at once (excluded
                        // the target, centre-only window, floored) and fired
                        // ZERO times in 120 seed-runs; the same failed roll
                        // that still landed on the primary was paid as a FULL
                        // hit, which is the other half of the correction.
                        let victim = null;
                        let bestD2 = Infinity;
                        const foes =
                            attacker.team === 1
                                ? attacker.sim.team2
                                : attacker.sim.team1;
                        for (const enemy of foes) {
                            if (enemy.state === "dead") continue;
                            const ex = enemy.x - impactX;
                            const ey = enemy.y - impactY;
                            const d2 = ex * ex + ey * ey;
                            const reach = enemy.radius + projRadiusPx;
                            if (d2 > reach * reach) continue;
                            // The body the shot came down ON is the nearest
                            // overlapping one. Deterministic and independent of
                            // team-array order, which the old first-match loop
                            // was not.
                            if (d2 < bestD2) {
                                bestD2 = d2;
                                victim = enemy;
                            }
                        }
                        if (victim) {
                            // `damage` is already the final post-armor value
                            // for `target`; a displaced hit on somebody else
                            // has to be re-costed against THAT body's armor,
                            // which is what "final post-armor damage" means.
                            // Identical to `damage` in the 26/27 case.
                            const full =
                                victim === target
                                    ? damage
                                    : attacker.getDamageAgainst(victim) +
                                      Math.floor(attacker.killBonusAttack);
                            // Arambai (missDamagePercent = 1.0) is the one unit
                            // the config says pays FULL on a displaced hit; the
                            // measured rule for everyone else is exactly half,
                            // unrounded.
                            const frac =
                                attacker.missDamagePercent > 0
                                    ? attacker.missDamagePercent
                                    : 0.5;
                            victim.takeDamage(full * frac, attacker);
                        }
                        // Otherwise: it hit the ground.
                        //
                        // A reduced hit deliberately does NOT set `didHit`, so
                        // it triggers no splash, pass-through or bleed. Those
                        // are the consequences of a shot landing where it was
                        // aimed; nothing in this corpus measures what a
                        // displaced siege shell does, and inventing it here
                        // would change siege behaviour on a guess.
                    } else if (didHit) {
                        target.takeDamage(damage, attacker);
                    } else if (targetWasAlive && !willHit) {
                        // The shot went wide AND the accuracy roll had failed:
                        // it may still graze whoever's body it came down on.
                        // Unchanged in kind from the legacy graze -- only the
                        // landing point is now the real one, so no extra rng is
                        // drawn here (the scatter was rolled at launch).
                        const foes =
                            attacker.team === 1
                                ? attacker.sim.team2
                                : attacker.sim.team1;
                        for (const enemy of foes) {
                            if (enemy === target || enemy.state === "dead")
                                continue;
                            const ex = enemy.x - impactX;
                            const ey = enemy.y - impactY;
                            if (
                                ex * ex + ey * ey <=
                                enemy.radius * enemy.radius
                            ) {
                                const frac =
                                    attacker.missDamagePercent > 0
                                        ? attacker.missDamagePercent
                                        : 0.5;
                                enemy.takeDamage(
                                    Math.max(1, Math.floor(damage * frac)),
                                    attacker,
                                );
                                break;
                            }
                        }
                    }
                    // Otherwise: it hit the ground. No pass-through, no graze.
                } else if (target.state !== "dead" && willHit) {
                    didHit = true;
                    target.takeDamage(damage, attacker);
                } else if (target.state !== "dead" && !willHit) {
                    // Missed: the arrow lands at a random point within
                    // MISS_SPREAD of the intended impact. If a (different) unit
                    // happens to occupy that spot it is grazed; otherwise the
                    // shot is wasted. Graze is 0.5x by default; Arambai
                    // (missDamagePercent=1.0) deals full damage on a graze.
                    const missAngle = attacker.sim.rng.next() * 2 * Math.PI;
                    const missDist = attacker.sim.rng.next() * MISS_SPREAD;
                    const landX = impactX + missDist * Math.cos(missAngle);
                    const landY = impactY + missDist * Math.sin(missAngle);
                    const foes =
                        attacker.team === 1
                            ? attacker.sim.team2
                            : attacker.sim.team1;
                    for (const enemy of foes) {
                        if (enemy === target || enemy.state === "dead")
                            continue;
                        const ex = enemy.x - landX;
                        const ey = enemy.y - landY;
                        if (
                            ex * ex + ey * ey <=
                            enemy.radius * enemy.radius
                        ) {
                            const frac =
                                attacker.missDamagePercent > 0
                                    ? attacker.missDamagePercent
                                    : 0.5;
                            enemy.takeDamage(
                                Math.max(1, Math.floor(damage * frac)),
                                attacker,
                            );
                            break;
                        }
                    }
                }

                if (
                    attacker.attackBonusPerKill > 0 &&
                    targetWasAlive &&
                    target.state === "dead"
                ) {
                    // attackBonusPerKill is the MAX CAP: +1 per kill up to it
                    // (Tiger Cav/Jaguar: +1/kill, max +4), not +cap/kill.
                    attacker.killBonusAttack = Math.min(
                        attacker.attackBonusPerKill,
                        attacker.killBonusAttack + 1,
                    );
                }

                // Did the shot actually connect? Under D2 that is the arrival
                // test; on the legacy path it is the launch-time roll, kept
                // verbatim (including its quirk that a shot at a target which
                // died mid-flight still splashes).
                const landed = R5B.ballisticLead ? didHit : willHit;

                // Siege area splash damage with distance falloff
                if (splashR > 0 && landed) {
                    const enemies =
                        attacker.team === 1
                            ? attacker.sim.team2
                            : attacker.sim.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy === target ||
                            enemy.state === "dead"
                        )
                            continue;
                        const dx = enemy.x - impactX;
                        const dy = enemy.y - impactY;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist <= splashR + enemy.radius) {
                            // Damage falls off linearly from 100% (the unit's
                            // body overlaps the impact point) to 0% one full
                            // blast radius beyond the unit's edge.
                            const edgeDist = Math.max(
                                0,
                                dist - enemy.radius,
                            );
                            const distRatio = Math.min(
                                1,
                                edgeDist / splashR,
                            );
                            const falloff = 1.0 - distRatio;
                            const splashDmg = Math.max(
                                1,
                                Math.round(damage * falloff),
                            );
                            enemy.takeDamage(splashDmg, attacker);
                        }
                    }
                    // Visual: add a splash effect
                    attacker.sim.effects.push(
                        new MeleeEffect(
                            impactX,
                            impactY,
                            attacker.team,
                            splashR,
                        ),
                    );
                }

                // Splash on hit (non-siege, e.g. scorpion pass-through)
                if (
                    attacker.splashOnHitRadius > 0 &&
                    splashR === 0 &&
                    landed
                ) {
                    const enemies =
                        attacker.team === 1
                            ? attacker.sim.team2
                            : attacker.sim.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dx = enemy.x - impactX;
                            const dy = enemy.y - impactY;
                            const dist = Math.sqrt(
                                dx * dx + dy * dy,
                            );
                            if (
                                dist <=
                                attacker.splashOnHitRadius +
                                    enemy.radius
                            ) {
                                enemy.takeDamage(damage, attacker);
                            }
                        }
                    }
                }

                // Pass-through: 1 unit behind target takes fraction of damage
                if (attacker.passThroughPercent > 0 && landed) {
                    const ptDmg = Math.max(
                        1,
                        Math.floor(
                            damage * attacker.passThroughPercent,
                        ),
                    );
                    const enemies =
                        attacker.team === 1
                            ? attacker.sim.team2
                            : attacker.sim.team1;
                    // Find closest alive enemy behind target (not the target itself)
                    let best = null;
                    let bestDist = Infinity;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dx = enemy.x - target.x;
                            const dy = enemy.y - target.y;
                            const d = Math.sqrt(dx * dx + dy * dy);
                            if (d < bestDist) {
                                bestDist = d;
                                best = enemy;
                            }
                        }
                    }
                    if (best) {
                        best.takeDamage(ptDmg, attacker);
                    }
                }

                // Bleed
                if (attacker.bleedDps > 0 && targetWasAlive && landed) {
                    target.bleedEffect = {
                        dps: attacker.bleedDps,
                        timeRemaining: attacker.bleedDuration,
                    };
                }
            },
        );
        // D3 bookkeeping: who this shot is for and how much it will do if it
        // lands, so the next shooter can see the damage already in the air.
        // Read-only labels -- the projectile's own flight ignores them, and
        // they are set on every path so the legacy engine carries them too
        // (inert there, because nothing reads them with the flag off).
        proj.targetUnit = target;
        proj.plannedDamage = damage;
        // R5d-T2: and register the same fact in this tick's claim ledger, so a
        // shooter that has not updated yet this tick sees the commitment even
        // though the arrival-order test would discard the arrow.
        this.claimShot(proj, target, damage);
        this.recordMissile();
        this.sim.projectiles.push(proj);
        this.attackAnimTimer = 0.15;
        this.triggerAttackAnim();
    }

    // Pick the distinct enemies a single charge volley sprays over. The primary
    // target leads (it is the one the caller already range-checked), then the
    // remaining living foes whose edge-to-edge distance is inside charge range,
    // nearest first. Ties break on the enemy's position in its team array, so
    // the choice is fully deterministic -- no RNG draw is taken here, which
    // keeps every other consumer of sim.rng bit-identical.
    pickChargeVolleyTargets() {
        const picked = [this.target];
        if (this.chargeProjectileCount <= 1) return picked;
        const foes = this.team === 1 ? this.sim.team2 : this.sim.team1;
        const candidates = [];
        for (let i = 0; i < foes.length; i++) {
            const foe = foes[i];
            if (foe === this.target || foe.state === "dead") continue;
            const dist = this.distanceTo(foe);
            if (dist <= this.chargeAttackRange + this.radius + foe.radius) {
                candidates.push({ foe, dist, i });
            }
        }
        candidates.sort((a, b) => a.dist - b.dist || a.i - b.i);
        for (const c of candidates) {
            if (picked.length >= this.chargeProjectileCount) break;
            picked.push(c.foe);
        }
        return picked;
    }

    fireChargeProjectile(target) {
        if (!target || target.state === "dead") return;
        // Calculate charge projectile damage using charge attacks
        let chargeDmg = 0;
        if (this.chargeProjectileAttacks) {
            for (const [cls, atkVal] of Object.entries(
                this.chargeProjectileAttacks,
            )) {
                if (atkVal <= 0) continue;
                if (this.chargeIgnoresArmor) {
                    chargeDmg += atkVal;
                } else {
                    const armor = target.armors[cls] || 0;
                    chargeDmg += Math.max(0, atkVal - armor);
                }
            }
        }
        chargeDmg = Math.max(1, chargeDmg);
        const speed =
            this.chargeProjectileSpeed > 0
                ? this.chargeProjectileSpeed
                : 7 * TILE_SIZE;
        const proj = new Projectile(
            this.x,
            this.y,
            target.x,
            target.y,
            speed,
            this.team,
            this.projectileKind,
            () => {
                if (target.state === "dead") return;
                target.takeDamage(chargeDmg, this);
                // Charge slow (Bolas Rider): slow the struck target.
                if (this.chargeSlowPercent > 0 && target.slowTimer <= 0) {
                    target.moveSpeed =
                        target.baseMoveSpeed * (1 - this.chargeSlowPercent);
                    target.slowTimer = this.chargeSlowDuration;
                }
            },
        );
        this.recordMissile();
        this.sim.projectiles.push(proj);
        this.attackAnimTimer = 0.3;
        this.triggerAttackAnim();
    }

    performAttackOn(target) {
        if (!target || target.state === "dead") return;
        // Diagnostic counter (see Simulation.combatStats): one swing per melee
        // strike that actually happens. Placed AFTER the dead-target guard so a
        // no-op call is not counted as a swing (in practice both call sites
        // already check, so this guard rarely fires). Charge projectiles
        // (fireChargeProjectile) are NOT counted as swings — they are a bonus
        // volley on top of the normal attack; their damage still lands in
        // hitsLanded/damageDealt via takeDamage.
        if (this.sim && this.sim.combatStats)
            this.sim.combatStats[this.team].swings++;
        // E15b rule 1 (SWING RECOVERY PLANT). The swing has LANDED, so the
        // attack animation is now running and this unit may not walk until it
        // finishes. Stamped here rather than at the call sites so every melee
        // landing path -- delay-0 performAttack, the committedAttack windup's
        // completion, and a killing blow -- pays it identically; the victim's
        // survival is deliberately not consulted, because the animation does not
        // abort when the target dies. See meleeMoveLocked() for what it gates
        // (locomotion, nothing else) and constants.js for the tape ramp it is
        // read off. Ranged units never reach this method (they fire projectiles)
        // and meleeMoveLocked() excludes them anyway.
        if (MELEE_SWING_RECOVERY_S > 0 && !this.isRanged()) {
            this.moveLockUntil =
                this.sim.battleTime + MELEE_SWING_RECOVERY_S;
        }
        let damage =
            this.getDamageAgainst(target) +
            Math.floor(this.killBonusAttack);

        // Melee charge bonus (Coustillier/Centurion/Urumi): extra damage on the
        // charged strike (reduced by target melee armor), then it recharges.
        let charged = false;
        if (this.chargeAttackMelee > 0 && this.chargeTimer <= 0) {
            damage += Math.max(0, this.chargeAttackMelee - target.meleeArmor);
            this.chargeTimer = this.chargeRechargeTime;
            charged = true;
        }

        const targetWasAlive = target.state !== "dead";
        target.takeDamage(damage, this);

        // Armor strip (Obuch): permanently lower the target's armor each hit.
        if (this.armorStripPerHit > 0 && target.state !== "dead") {
            target.meleeArmor = Math.max(
                0,
                target.meleeArmor - this.armorStripPerHit,
            );
            target.pierceArmor = Math.max(
                0,
                target.pierceArmor - this.armorStripPerHit,
            );
            if ("4" in target.armors)
                target.armors["4"] = Math.max(
                    0,
                    target.armors["4"] - this.armorStripPerHit,
                );
            if ("3" in target.armors)
                target.armors["3"] = Math.max(
                    0,
                    target.armors["3"] - this.armorStripPerHit,
                );
        }

        if (
            this.attackBonusPerKill > 0 &&
            targetWasAlive &&
            target.state === "dead"
        ) {
            // attackBonusPerKill is the MAX CAP: +1 per kill, up to it.
            this.killBonusAttack = Math.min(
                this.attackBonusPerKill,
                this.killBonusAttack + 1,
            );
        }

        // HP per kill (Tiger Cavalry): heal on kill, up to the cap.
        if (
            this.hpPerKill > 0 &&
            targetWasAlive &&
            target.state === "dead" &&
            this.hpGainedFromKills < this.hpPerKillMax
        ) {
            const heal = Math.min(
                this.hpPerKill,
                this.hpPerKillMax - this.hpGainedFromKills,
            );
            this.currentHp = Math.min(this.maxHp, this.currentHp + heal);
            this.hpGainedFromKills += heal;
        }

        // Attack-speed ramp (Temple Guard): shorten reload toward the floor.
        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            this.rampReduction = Math.min(
                this.rampReduction + this.attackSpeedRamp,
                Math.max(0, baseReload - this.attackSpeedMin),
            );
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.rampReduction,
            );
        }

        // Trample (melee). Charge-melee units (Urumi) splash only on the charged
        // strike; always-on tramplers (Cataphract/elephants) every hit.
        if (!this.isRanged() && (this.chargeAttackMelee <= 0 || charged)) {
            const trampleInfo = this.getTrampleInfo();
            if (trampleInfo) {
                const trampleDmg =
                    Math.floor(damage * trampleInfo.percent) +
                    trampleInfo.flat;
                if (trampleDmg > 0) {
                    const enemies =
                        this.team === 1
                            ? this.sim.team2
                            : this.sim.team1;
                    for (const enemy of enemies) {
                        if (
                            enemy !== target &&
                            enemy.state !== "dead"
                        ) {
                            const dist = this.distanceTo(enemy);
                            // Blast emanates from the trampler's BODY, not a
                            // point: reach is edge-to-edge, so the attacker's
                            // own radius counts (parity with
                            // simulation_real.py's identical reach formula).
                            // Omitting it leaves a packed ring around a
                            // big-footprint unit (elephant, r~0.6 tile) just
                            // out of reach -- ~0 units trampled per swing
                            // where the tape shows the elephant landing
                            // splash hits on 3+ victims routinely.
                            if (
                                dist <=
                                this.radius +
                                    trampleInfo.radius +
                                    enemy.radius
                            ) {
                                enemy.takeDamage(trampleDmg, this);
                            }
                        }
                    }
                }
            }
        }

        // Splash on hit (melee)
        if (this.splashOnHitRadius > 0) {
            const enemies =
                this.team === 1
                    ? this.sim.team2
                    : this.sim.team1;
            for (const enemy of enemies) {
                if (enemy !== target && enemy.state !== "dead") {
                    const dx = enemy.x - target.x;
                    const dy = enemy.y - target.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (
                        dist <=
                        this.splashOnHitRadius + enemy.radius
                    ) {
                        enemy.takeDamage(damage, this);
                    }
                }
            }
        }

        // Pass-through (melee path, if applicable)
        if (this.passThroughPercent > 0) {
            const ptDmg = Math.max(
                1,
                Math.floor(damage * this.passThroughPercent),
            );
            const enemies =
                this.team === 1
                    ? this.sim.team2
                    : this.sim.team1;
            let best = null;
            let bestDist = Infinity;
            for (const enemy of enemies) {
                if (enemy !== target && enemy.state !== "dead") {
                    const dx = enemy.x - target.x;
                    const dy = enemy.y - target.y;
                    const d = Math.sqrt(dx * dx + dy * dy);
                    if (d < bestDist) {
                        bestDist = d;
                        best = enemy;
                    }
                }
            }
            if (best) {
                best.takeDamage(ptDmg, this);
            }
        }

        // Bleed
        if (this.bleedDps > 0 && targetWasAlive) {
            target.bleedEffect = {
                dps: this.bleedDps,
                timeRemaining: this.bleedDuration,
            };
        }

        this.attackAnimTimer = 0.15;
        this.triggerAttackAnim();

        // Spawn melee visual effect
        this.sim.effects.push(
            new MeleeEffect(target.x, target.y, this.team),
        );
    }

    getTrampleInfo() {
        if (this.tramplePercent > 0 || this.trampleFlatDamage > 0) {
            return {
                percent: this.tramplePercent,
                radius: this.trampleRadius,
                flat: this.trampleFlatDamage,
            };
        }
        return null;
    }

    // Event recorder for cross-engine calibration (see Simulation.eventLog in
    // sim.js): appends one damage record, shared by every site in takeDamage
    // that applies real HP loss (the main hit below AND the damage-reflect
    // bounce), so the record shape cannot drift between the two. `srcUnit` is
    // the damage's source, `dstUnit` is whoever lost the HP -- for the reflect
    // bounce these are reversed relative to the call's own `this`/`attacker`,
    // since the original victim becomes the source and the original attacker
    // becomes the one taking damage. Read-only: no rng draw, no ordering
    // change, not in stateHash().
    recordDamageEvent(srcUnit, dstUnit, damage, hpAfter, kill) {
        if (!(this.sim && this.sim.eventLog)) return;
        this.sim.eventLog.damage.push({
            t: this.sim.battleTime,
            attacker: srcUnit.id,
            victim: dstUnit.id,
            damage,
            victim_hp_after: hpAfter,
            kill,
            attacker_owner: srcUnit.team,
            victim_owner: dstUnit.team,
        });
    }

    takeDamage(amount, attacker) {
        if (
            this.dodgeShieldMax > 0 &&
            attacker &&
            attacker.isRanged() &&
            this.shieldCharges > 0
        ) {
            this.shieldCharges--;
            this.shieldRechargeTimer = this.dodgeShieldRecharge;
            this.damageNumbers.push({
                value: "DODGE",
                x: this.x,
                y: this.y - this.drawRadius - 5,
                alpha: 1.0,
            });
            return;
        }
        if (
            this.blockFirstMelee &&
            attacker &&
            !attacker.isRanged() &&
            !this.hasBlockedFirstMelee
        ) {
            this.hasBlockedFirstMelee = true;
            this.damageNumbers.push({
                value: "BLOCK",
                x: this.x,
                y: this.y - this.drawRadius - 5,
                alpha: 1.0,
            });
            return;
        }
        // Damage reflect (Khitan Lamellar Armor): bounce a % of melee damage back.
        if (
            this.damageReflectPercent > 0 &&
            amount > 0 &&
            attacker &&
            !attacker.isRanged() &&
            attacker.state !== "dead"
        ) {
            const reflectHpBefore = attacker.currentHp;
            attacker.currentHp -= amount * this.damageReflectPercent;
            let reflectKilled = false;
            if (attacker.currentHp <= 0) {
                attacker.currentHp = 0;
                attacker.state = "dead";
                attacker.target = null;
                reflectKilled = true;
            }
            // This bounce is itself a real HP loss with no separate call into
            // attacker.takeDamage (deliberately -- a second reflect off the
            // reflect would be wrong), so it needs its own event: roles
            // reversed from the main hit below, since `this` (the unit that
            // was hit) is the source of the bounce and `attacker` is who takes
            // it.
            this.recordDamageEvent(
                this,
                attacker,
                reflectHpBefore - attacker.currentHp,
                attacker.currentHp,
                reflectKilled,
            );
        }
        const hpBeforeHit = this.currentHp;
        this.currentHp -= amount;
        // Floating per-hit damage numbers were removed — at 30v30 they spawn
        // dozens/sec and just clutter the field; live damage is read from the
        // team side panels (HP + Res Lost) instead. DODGE/BLOCK event labels
        // (rare, word-based) still use damageNumbers above.
        if (this.currentHp <= 0) {
            this.currentHp = 0;
            this.state = "dead";
            this.target = null;
        }
        // Diagnostic counters (see Simulation.combatStats). Recorded here, past
        // the DODGE/BLOCK early-returns, so a hit only counts once it actually
        // reached HP; `damageDealt` is the HP the victim REALLY lost (the clamp
        // at 0 above means overkill is not credited). `attacker` is absent on
        // some paths (bleed ticks, execute damage) and BattleUnit may be built
        // without a sim in tests, hence the guards. Read-only for the engine —
        // no rng, no ordering change, not in stateHash().
        if (attacker && attacker.sim && attacker.sim.combatStats) {
            const cs = attacker.sim.combatStats[attacker.team];
            if (cs) {
                cs.hitsLanded++;
                cs.damageDealt += hpBeforeHit - this.currentHp;
            }
        }
        // Event recorder for cross-engine calibration (see Simulation.eventLog
        // in sim.js): one damage record per application, covering direct hits,
        // splash, trample, pass-through and charge damage -- everything that
        // flows through this single funnel, PLUS the damage-reflect bounce
        // recorded separately above.
        //
        // Known remaining bypass, NOT recorded anywhere: the continuous
        // per-tick bleed drain applied directly to currentHp in update()
        // (~line 425) never calls takeDamage, so it emits no damage event at
        // all. As of this writing the only units with bleed_dps > 0 are
        // Khitans' Liao Dao / Elite Liao Dao (config_combat.py's base
        // COMBAT_PROPERTIES) and Tupi's arbalester / elite blackwood archer
        // (Tupi Curare, civ-specific) -- none of which are in today's
        // standard-unit recording corpus, so this is out of scope for now but
        // MUST be revisited before any bleed-capable unique unit is recorded.
        if (attacker) {
            this.recordDamageEvent(
                attacker,
                this,
                hpBeforeHit - this.currentHp,
                this.currentHp,
                hpBeforeHit > 0 && this.currentHp === 0,
            );
        }
    }

    applyDismount() {
        // Replace this dead mounted unit in place with its dismounted form
        // (Konnik). Called by BattleSimulation.update() at END of tick,
        // mirroring simulation_real.py / simulation.py: the horse's death
        // still credits on-kill effects, same-tick overkill is forgiven,
        // any committed strike is cancelled and a killing-blow bleed dies
        // with the old body. The foot soldier spawns at FULL dismount HP
        // with its cooldown starting at one full dismount reload, and is
        // always melee (the dismount block carries no range).
        this.isDismounted = true;
        this.maxHp = this.dismountHp;
        this.currentHp = this.dismountHp;
        if (this.dismountAttack > 0) this.attack = this.dismountAttack;
        this.meleeArmor = this.dismountMeleeArmor;
        this.pierceArmor = this.dismountPierceArmor;
        if (this.dismountAttacks) this.attacks = this.dismountAttacks;
        if (this.dismountArmors) this.armors = this.dismountArmors;
        if (this.dismountAttackSpeed > 0) {
            this.attackSpeed = this.dismountAttackSpeed;
            this.reloadTime = 1.0 / this.dismountAttackSpeed;
        }
        this.attackDelay = this.dismountAttackDelay;
        if (this.dismountMovementSpeed > 0) {
            this.moveSpeed = this.dismountMovementSpeed * TILE_SIZE;
            this.baseMoveSpeed = this.moveSpeed;
        }
        this.rawAttackRange = 0;
        this.attackRange = MELEE_RANGE_BUFFER; // dismounted is always melee
        this.state = "idle";
        this.target = null;
        this.attackCooldown = this.reloadTime;
        this.committedAttack = null;
        this.bleedEffect = null;
        // The second, final death may trigger ally-death heals again.
        this.deathHealTriggered = false;
    }

    moveTowardTarget(dt, allUnits) {
        if (!this.target) return;
        let dx = this.target.x - this.x;
        let dy = this.target.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) return;
        dx /= dist;
        dy /= dist;
        const avoidance = this.calculateAvoidance(allUnits);
        const avoidMag = Math.sqrt(
            avoidance.x * avoidance.x + avoidance.y * avoidance.y,
        );
        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }
        let len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
        }
        // Golden arena only (this.sim.arena is null on every other path, so it
        // costs one null test on the plain rectangle): push out of the central
        // tree cluster and slide around it, so a chaser rounds the trees instead
        // of grinding into them. Applied to the ALREADY-NORMALISED heading, so
        // the slide term's "how hard is this unit driving into the trees" dot
        // product means the same thing however crowded the unit is.
        // See engine/arena.js.
        if (this.sim.arena) {
            const o = this.sim.arena.obstacleSteer(
                this.x,
                this.y,
                this.radius,
                dx,
                dy,
            );
            if (o) {
                dx += o.x;
                dy += o.y;
                len = Math.sqrt(dx * dx + dy * dy);
                if (len > 0) {
                    dx /= len;
                    dy /= len;
                }
            }
        }

        // Smooth velocity -- blend desired direction with previous velocity
        const smoothing = 0.3; // 0=instant snap, 1=no change
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }

        const moveAmount = this.moveSpeed * dt;
        this.x += this.vx * moveAmount;
        this.y += this.vy * moveAmount;
        // The golden arena's diamond + tree cluster REPLACE the rectangle clamp
        // (see engine/arena.js); with no arena this is the historical clamp,
        // unchanged. Note this runs BEFORE the stuck check below on purpose:
        // a unit walking into the trees really has made no progress, and should
        // be allowed to blacklist an unreachable target exactly as it would
        // behind a wall of allies.
        if (this.sim.arena) {
            this.sim.arena.constrain(this);
        } else {
            this.x = Math.max(
                this.radius,
                Math.min(CANVAS_WIDTH - this.radius, this.x),
            );
            this.y = Math.max(
                this.radius,
                Math.min(CANVAS_HEIGHT - this.radius, this.y),
            );
        }

        // Stuck detection: if not making progress, mark target as blocked.
        // The bar is a RATE (px/s), not a bare per-substep constant -- see
        // STUCK_PROGRESS_RATE's own comment in constants.js. At dt = 1/60
        // this is exactly the historical `- 0.5` literal, pinned by
        // tests/js/engine/pursuit.test.mjs.
        const newDist = this.distanceTo(this.target);
        // The bar can never exceed what this unit could PHYSICALLY close.
        // Chasing a target that is itself running away closes the gap at the
        // SPEED DIFFERENCE, so the flat bar brands honest, physically-maximal
        // pursuit as "stuck": a Champion (1.06 t/s) chasing a Siege Onager
        // (0.6 t/s) closes at 0.46 t/s, never clears 1.0 t/s, and blacklists
        // every onager every 0.8 s -- melee literally cannot engage siege.
        // Only an actively KITING target relaxes the bar, and only to
        // PURSUIT_BAR_FRACTION of the achievable rate. A chaser slower than
        // its fleeing target yields max(0, ...) === 0 and still blacklists,
        // preserving re-targeting off uncatchable kiters.
        let progressBar = STUCK_PROGRESS_RATE;
        if (this.target.state === "kiting") {
            const advantage = this.moveSpeed - this.target.moveSpeed;
            if (advantage >= PURSUIT_MIN_ADVANTAGE) {
                progressBar = Math.min(
                    progressBar,
                    advantage * PURSUIT_BAR_FRACTION,
                );
            }
        }
        if (newDist >= this.lastDistToTarget - progressBar * dt) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }
        this.lastDistToTarget = newDist;
        if (this.stuckTimer > 0.8) {
            // E14 rule 1 (TARGET LOCK): a melee unit does not abandon a living
            // melee foe because it failed to make forward progress -- in a
            // scrum "no progress" means the front rank has the contact slot,
            // not that the foe is unreachable. It re-arms the bar and keeps
            // pressing; the only thing that moves it off is the foe dying or
            // rule 2's bump. A pursuit (ranged unit, or a RANGED target) is
            // untouched: that is what the bar was built for.
            if (this.meleeTargetLock()) {
                this.stuckTimer = 0;
            } else {
                this.blockedTargets.add(this.target);
                this.target = null; // force re-target next frame
                this.stuckTimer = 0;
            }
        }
    }

    // ---- group-kite steering (E5a) -------------------------------------------
    // Returns null when this unit is NOT in group-kite mode -- and null means
    // "change nothing", so every gated-out fight stays bit-identical to the
    // pre-E5a engine (the caller skips the vector add entirely rather than
    // adding a zero). Otherwise returns the extra steering vector to blend into
    // the radial flee: a tangential (orbit) term plus a cohesion term.
    //
    // GATE -- all five must hold:
    //   1. the unit is ranged (melee never reaches moveAwayFromTarget anyway);
    //   2. it has NO minimum-range dead zone. minAttackRange > 0 is exactly the
    //      siege weapons (Siege Onager 3.0, Heavy Scorpion 2.0) and nothing
    //      else in the corpus. Siege does not run a kite circuit -- it is far
    //      too slow to -- and it already owns a competing repositioning path
    //      (tooClose()), so an orbit term there would fight it. This clause is
    //      what keeps every siege-attacker fight byte-identical to baseline;
    //   3. both sides still have living units;
    //   4. this side's MEDIAN attack range strictly out-ranges the enemy's --
    //      the same predicate as the recording AI's `gKiteOK`. Melee-vs-melee
    //      is 0 > 0 = false, so those fights are untouched too;
    //   5. (E10: NO LONGER A GATE -- see below.) The median speed margin now
    //      scales the ORBIT TERM ONLY, ramping it to zero for a side with no
    //      speed to spare. Cohesion and the shared retreat basis apply to every
    //      group-kiting side regardless of speed.
    //
    //      HONESTY NOTE: clause 5 is NOT a model of ddkSquareV25 -- that script
    //      kites on a RANGE test alone and never checks speed. It compensates
    //      for an arena mismatch this engine has no other answer to: the tapes
    //      are a 16x16 map that is 39% solid trees (a donut), so the AI's
    //      clockwise circuit repeatedly drives its own ball into the central
    //      cluster and the chasers catch it. This engine's arena is an EMPTY
    //      30x20 rectangle, where an unconditional orbit lets any kiter circle
    //      out of reach forever. Measured on the tuning subset: an ungated
    //      orbit fixes the cav-archer fights and simultaneously breaks the
    //      arbalester/hand-cannoneer fights the engine already got right, at
    //      every weight tried (0.5/1.0/1.5/2.0). The speed margin is the
    //      property that separates the two families -- Heavy Cav Archer at
    //      46.2 px/s outruns every melee chaser in the corpus, while every foot
    //      archer sits at 28.8 px/s and outruns none of them.
    //
    // E10 -- SHARED RETREAT BASIS, and why clause 5 stopped being a hard gate.
    // Forensics on the two broken families (champion__vs__heavy_cav_archer
    // seed 1, hand_cannoneer__vs__heavy_camel seed 1; 5 s bins, mid-fight):
    //
    //   heading coherence of the kiting ball   0.28-0.69   (1.0 = one direction)
    //   angle between "flee from MY target"
    //     and "flee from the enemy CENTROID"   mean 44-74 deg, max 98-179 deg
    //
    // The ball was never DISPERSING -- E8's packing already holds its
    // nearest-neighbour spacing at the tape's 0.6-0.9 tiles. It was MILLING:
    // twelve Heavy Cav Archers each fleeing their OWN target ran twelve
    // different ways, the group's centroid stopped receding (radius of gyration
    // collapsed to 0.8 tiles while 4-8 champions stayed in contact from t=15 s
    // to the end), and the melee side simply enveloped a stationary blob.
    //
    // So a group-kiting unit now backs away from the ENEMY CENTROID, not from
    // its own target. One shared threat direction per side per tick turns
    // twelve individual flights into one translating ball -- which is what the
    // tape's ddkSquareV25 patrol produces for free, because it steers the whole
    // army with one order. Costs nothing and needs no constant: it is a change
    // of BASIS, not an added force. `moveAwayFromTarget` falls back to the
    // per-target radial whenever this returns null, so every gated-out fight
    // (siege, melee, non-out-ranging sides) is untouched.
    //
    // Clause 5 stopped being a hard gate for the same reason: it was returning
    // null for exactly the sides that need cohesion most -- every FOOT archer,
    // which by construction never out-runs its chaser (hand_cannoneer 28.8 px/s
    // vs heavy_camel 48.0). Those sides got no cohesion and no shared retreat at
    // all. The orbit term still ramps to zero for them, so the arena-mismatch
    // argument above is preserved exactly; only the two group-forming terms
    // (which cannot manufacture distance, and so cannot let a kiter circle out
    // of reach forever) now apply.
    //
    // The ramp scale is PURSUIT_MIN_ADVANTAGE, reused rather than duplicated:
    // it is already defined as the speed margin below which a pursuit is a
    // stalemate not worth committing to, which is exactly the threshold that
    // decides whether a kiter can afford to trade speed for angle.
    //
    // Everything below is a deterministic function of the current tick's
    // positions: fixed-order sums, a numeric sort, no RNG, no wall clock.
    kiteSteering(allUnits, enemies) {
        if (!this.isRanged() || this.minAttackRange > 0) return null;
        const mine = medianLiving(allUnits, this.team, pickRange);
        const theirs = medianLiving(enemies, null, pickRange);
        if (mine === null || theirs === null || mine <= theirs) return null;

        const ourSpeed = medianLiving(allUnits, this.team, pickSpeed);
        const theirSpeed = medianLiving(enemies, null, pickSpeed);
        // Clamped at 0 rather than returning null (E10): a side with no speed
        // margin gets no orbit, but still gets cohesion and the shared retreat
        // basis below.
        const margin = Math.max(0, ourSpeed - theirSpeed);
        const orbit =
            KITE_TANGENTIAL_WEIGHT *
            Math.min(1, margin / PURSUIT_MIN_ADVANTAGE);

        // Enemy centroid -- the point the whole side orbits.
        let ex = 0,
            ey = 0,
            en = 0;
        for (const e of enemies) {
            if (e.state === "dead") continue;
            ex += e.x;
            ey += e.y;
            en++;
        }
        if (en === 0) return null;
        ex /= en;
        ey /= en;

        // Own living centroid -- the point cohesion pulls toward. `this` is
        // alive and present in allUnits, so an >= 1.
        let ax = 0,
            ay = 0,
            an = 0;
        for (const u of allUnits) {
            if (u.state === "dead" || u.team !== this.team) continue;
            ax += u.x;
            ay += u.y;
            an++;
        }
        ax /= an;
        ay /= an;

        // Tangential: rotate the enemy-centroid-to-self radial by +90 deg. In
        // screen coordinates (y down) that is (x, y) -> (-y, x), i.e. a
        // CLOCKWISE circuit -- the same sense for every unit on the side and
        // for every seed, which is what turns individual flight into one
        // rotating ball. Sign matches the tape script's clockwise patrol; the
        // orbit's rotation rate/period is emergent, never fitted.
        let rx = this.x - ex,
            ry = this.y - ey;
        const rlen = Math.sqrt(rx * rx + ry * ry);
        let tx = 0,
            ty = 0;
        if (rlen > 0) {
            tx = -ry / rlen;
            ty = rx / rlen;
        }

        // Cohesion: toward own centroid, ramping linearly from 0 at the
        // centroid to full strength at KITE_COHESION_RAMP_TILES.
        let cx = ax - this.x,
            cy = ay - this.y;
        const clen = Math.sqrt(cx * cx + cy * cy);
        const ramp = KITE_COHESION_RAMP_TILES * TILE_SIZE;
        if (clen > 0 && ramp > 0) {
            const scale = Math.min(1, clen / ramp) / clen;
            cx *= scale;
            cy *= scale;
        } else {
            cx = 0;
            cy = 0;
        }

        return {
            x: orbit * tx + KITE_COHESION_WEIGHT * cx,
            y: orbit * ty + KITE_COHESION_WEIGHT * cy,
            // Shared retreat basis (E10): the unit vector from the enemy
            // centroid to this unit -- identical in SOURCE for every unit on the
            // side, so the whole ball backs away along one bearing instead of
            // twelve. `rlen === 0` (this unit sits exactly on the enemy
            // centroid) leaves it zero and moveAwayFromTarget falls back to the
            // per-target radial.
            rx: rlen > 0 ? rx / rlen : 0,
            ry: rlen > 0 ? ry / rlen : 0,
        };
    }

    moveAwayFromTarget(dt, allUnits, steering = null) {
        if (!this.target) return;
        let dx, dy;
        // Group kiters back away from the SHARED threat direction (the enemy
        // centroid) rather than from their own target -- see kiteSteering's
        // E10 note. Everyone else keeps the per-target radial exactly.
        if (steering && (steering.rx !== 0 || steering.ry !== 0)) {
            dx = steering.rx;
            dy = steering.ry;
        } else {
            dx = this.x - this.target.x;
            dy = this.y - this.target.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 1) {
                dx = this.team === 1 ? -1 : 1;
                dy = 0;
            } else {
                dx /= dist;
                dy /= dist;
            }
        }
        // Group-kite steering (null => untouched pre-E5a behaviour).
        if (steering) {
            dx += steering.x;
            dy += steering.y;
        }
        const avoidance = this.calculateAvoidance(allUnits);
        dx += avoidance.x;
        dy += avoidance.y;
        let len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
        }
        // Golden arena only — same treatment as moveTowardTarget's, so a kiting
        // ball orbits the tree cluster rather than backing into it. Combined
        // with the clockwise tangential term above, that is what makes the lap
        // around the cluster the natural retreat path. See engine/arena.js.
        if (this.sim.arena) {
            const o = this.sim.arena.obstacleSteer(
                this.x,
                this.y,
                this.radius,
                dx,
                dy,
            );
            if (o) {
                dx += o.x;
                dy += o.y;
                len = Math.sqrt(dx * dx + dy * dy);
                if (len > 0) {
                    dx /= len;
                    dy /= len;
                }
            }
        }
        // Smooth velocity for kiting too
        const smoothing = 0.3;
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }
        const moveAmount = this.moveSpeed * dt;
        this.x += this.vx * moveAmount;
        this.y += this.vy * moveAmount;
        if (this.sim.arena) {
            this.sim.arena.constrain(this);
        } else {
            this.x = Math.max(
                this.radius,
                Math.min(CANVAS_WIDTH - this.radius, this.x),
            );
            this.y = Math.max(
                this.radius,
                Math.min(CANVAS_HEIGHT - this.radius, this.y),
            );
        }
    }

    // ---- combat-pack predicate (E8) ------------------------------------------
    // True when this unit is committed to a fight at contact range: alive, with
    // a living target no further than its own effective reach plus
    // COMBAT_PACK_SLACK_TILES. The slack is what admits the rank BEHIND the
    // contact line, which by definition has nothing in reach yet -- see the
    // reach arithmetic in constants.js. Recomputed once per tick by
    // Simulation.update() and cached as `this.inCombatPack`; nothing here draws
    // randomness and nothing here mutates the unit.
    computeCombatPack() {
        if (this.state === "dead") return false;
        if (!COMBAT_PACK_RANGED && this.isRanged()) return false;
        const t = this.target;
        if (!t || t.state === "dead") return false;
        const reach = this.attackRange + this.radius + t.radius;
        return (
            this.distanceTo(t) <=
            reach + COMBAT_PACK_SLACK_TILES * TILE_SIZE
        );
    }

    calculateAvoidance(allUnits) {
        let avoidX = 0,
            avoidY = 0;
        for (const other of allUnits) {
            if (other === this || other.state === "dead") continue;
            const dx = this.x - other.x;
            const dy = this.y - other.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            // Same-team pairs that are BOTH engaged compress (E8): the soft
            // floor shrinks by the same factor as the hard one in
            // resolveCollisions, otherwise this separation force would just
            // push the pair straight back out of the compressed band. Cross-
            // team pairs and any pair with an unengaged member are untouched.
            let minDist = this.radius + other.radius + 2;
            if (
                this.team === other.team &&
                this.inCombatPack &&
                other.inCombatPack
            ) {
                minDist *= COMBAT_PACK_FACTOR;
            }
            if (dist < minDist * 1.5 && dist > 0) {
                const overlap =
                    Math.max(0, minDist - dist) / minDist;
                // Strong force when overlapping, moderate when close
                const force = overlap > 0 ? 3 + overlap * 5 : 0.5;
                avoidX += (dx / dist) * force;
                avoidY += (dy / dist) * force;
            }
        }
        return { x: avoidX, y: avoidY };
    }
}
