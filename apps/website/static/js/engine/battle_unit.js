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
        // Scale radius based on unit outline_size
        // infantry(0.2)->14, cavalry(0.4)->18, paladin(0.5)->20, mangonel(0.5)->20, ram(0.8)->26, treb(1.0)->30
        const outlineSize = stats.outline_size || 0.2;
        this.radius = Math.round(
            10 + Math.min(outlineSize, 1.0) * 20,
        );
        this.target = null;
        this.state = "idle";
        this.attackCooldown = 0;
        this.wasMoving = true;
        this.committedAttack = null;
        this.attackAnimTimer = 0;
        // Seconds the attack sprite-sheet keeps playing after a swing/shot fires,
        // independent of state — so the animation completes even once the unit
        // starts moving/kiting away (set to one full sheet cycle on each attack).
        this.animHold = 0;
        this.damageNumbers = [];

        // Movement smoothing -- prevents vibration
        this.vx = 0;
        this.vy = 0;
        // Horizontal facing: sprites are authored facing LEFT, so faceRight=true
        // means mirror. At spawn, team 1 (left) faces its enemies on the right and
        // team 2 (right) faces left; during battle it tracks the target/movement
        // direction (see render) so a unit always faces what it's attacking.
        this.faceRight = this.team === 1;
        // Stuck detection -- switch targets when blocked
        this.stuckTimer = 0;
        this.lastDistToTarget = Infinity;
        this.blockedTargets = new Set();

        // Attack sprite-sheet ref, stamped by the page/harness for animation timing
        // only (triggerAttackAnim). The renderer owns all other draw assets.
        this.attackSheet = null;
    }

    isRanged() {
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
        // Use unblocked target if available, else fall back to closest
        this.target = closest || fallback;
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

    update(dt, allUnits, enemies) {
        if (this.state === "dead") return;

        this.attackCooldown = Math.max(0, this.attackCooldown - dt);
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

        if (this.isRanged()) {
            const shouldKite = !this.target.isRanged();
            if (this.tooClose()) {
                this.state = "kiting";
                this.moveAwayFromTarget(dt, allUnits);
                this.wasMoving = true;
            } else if (
                !this.wasMoving &&
                this.attackCooldown <= 0
            ) {
                this.state = "attacking";
                this.performAttack();
                this.wasMoving = true;
            } else if (!this.wasMoving) {
                this.state = "attacking";
            } else if (this.attackCooldown > 0 && shouldKite) {
                this.state = "kiting";
                this.moveAwayFromTarget(dt, allUnits);
            } else if (this.attackCooldown > 0) {
                this.state = "attacking";
            } else if (this.inRange()) {
                this.attackCooldown = this.attackDelay;
                this.wasMoving = false;
                this.state = "attacking";
            } else {
                this.state = "moving";
                this.moveTowardTarget(dt, allUnits);
            }
        } else {
            // Charge projectile attack (Fire Lancer): fire at range before melee
            if (
                this.chargeProjectileCount > 0 &&
                !this.hasUsedCharge &&
                this.target
            ) {
                const distToTarget = this.distanceTo(this.target);
                const chargeRange =
                    this.chargeAttackRange +
                    this.radius +
                    this.target.radius;
                if (distToTarget <= chargeRange) {
                    // In charge range -- fire charge projectiles
                    this.hasUsedCharge = true;
                    this.state = "attacking";
                    this.attackAnimTimer = 0.3;
                    this.triggerAttackAnim();
                    for (
                        let cp = 0;
                        cp < this.chargeProjectileCount;
                        cp++
                    ) {
                        this.fireChargeProjectile(this.target);
                    }
                    this.attackCooldown = this.reloadTime;
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
                    this.attackCooldown = this.reloadTime;
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
        let scatI = 0;
        for (let p = 0; p < numProjectiles; p++) {
            if (this.target && this.target.state !== "dead") {
                if (this.isRanged()) {
                    let tgt = this.target;
                    if (p > 0 && scatter && scatter.length > 0) {
                        tgt = scatter[scatI % scatter.length];
                        scatI++;
                    }
                    this.fireProjectile(tgt, p > 0);
                } else {
                    this.performAttackOn(this.target);
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
        // Siege splash: scale up radius so mangonel/onager can hit clusters.
        // Volley units (Rocket Cart: every projectile blasts) keep their true
        // per-projectile radius — the upscale only compensates single stones.
        const splashR =
            attacker.splashRadius > 0
                ? attacker.extraProjectiles > 0
                    ? attacker.splashRadius
                    : Math.max(attacker.splashRadius, 2.5 * TILE_SIZE)
                : 0;
        const impactX = target.x;
        const impactY = target.y;
        const proj = new Projectile(
            this.x,
            this.y,
            target.x,
            target.y,
            speed,
            this.team,
            this.projectileKind,
            () => {
                const targetWasAlive = target.state !== "dead";
                if (target.state !== "dead" && willHit) {
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

                // Siege area splash damage with distance falloff
                if (splashR > 0 && willHit) {
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
                            // Damage falls off linearly from 100% at center to 25% at edge
                            const distRatio = Math.min(
                                1,
                                dist / splashR,
                            );
                            const falloff = 1.0 - 0.75 * distRatio;
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
                    willHit
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
                if (attacker.passThroughPercent > 0 && willHit) {
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
                if (attacker.bleedDps > 0 && targetWasAlive && willHit) {
                    target.bleedEffect = {
                        dps: attacker.bleedDps,
                        timeRemaining: attacker.bleedDuration,
                    };
                }
            },
        );
        this.recordMissile();
        this.sim.projectiles.push(proj);
        this.attackAnimTimer = 0.15;
        this.triggerAttackAnim();
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
                            if (
                                dist <=
                                trampleInfo.radius + enemy.radius
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
                y: this.y - this.radius - 5,
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
                y: this.y - this.radius - 5,
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
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
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
        this.x = Math.max(
            this.radius,
            Math.min(CANVAS_WIDTH - this.radius, this.x),
        );
        this.y = Math.max(
            this.radius,
            Math.min(CANVAS_HEIGHT - this.radius, this.y),
        );

        // Stuck detection: if not making progress, mark target as blocked
        const newDist = this.distanceTo(this.target);
        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }
        this.lastDistToTarget = newDist;
        if (this.stuckTimer > 0.8) {
            this.blockedTargets.add(this.target);
            this.target = null; // force re-target next frame
            this.stuckTimer = 0;
        }
    }

    moveAwayFromTarget(dt, allUnits) {
        if (!this.target) return;
        let dx = this.x - this.target.x;
        let dy = this.y - this.target.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) {
            dx = this.team === 1 ? -1 : 1;
            dy = 0;
        } else {
            dx /= dist;
            dy /= dist;
        }
        const avoidance = this.calculateAvoidance(allUnits);
        dx += avoidance.x;
        dy += avoidance.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
            dx /= len;
            dy /= len;
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
        this.x = Math.max(
            this.radius,
            Math.min(CANVAS_WIDTH - this.radius, this.x),
        );
        this.y = Math.max(
            this.radius,
            Math.min(CANVAS_HEIGHT - this.radius, this.y),
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
            const minDist = this.radius + other.radius + 2;
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
