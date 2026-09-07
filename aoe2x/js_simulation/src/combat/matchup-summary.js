import {
  calculateDamage,
  chargeProjectileDamage,
  chargeSpec,
  meleeChargeSpec,
  rangedSpec,
  trampleSpec,
} from "./attacks.js";


const TICKS_PER_SECOND = 60;
const MAX_TTK_TICKS = 10 * 60 * TICKS_PER_SECOND;

const ARMOR_CLASS_NAMES = Object.freeze({
  1: "infantry",
  3: "pierce",
  4: "melee",
  5: "war elephants",
  8: "cavalry",
  11: "buildings",
  15: "archers",
  17: "rams",
  19: "unique units",
  20: "siege",
  21: "buildings",
  23: "gunpowder units",
  25: "monks",
  27: "spearmen",
  28: "cavalry archers",
  29: "eagle warriors",
  30: "camels",
  32: "condottieri",
  34: "mamelukes",
  36: "Hussite Wagons",
  38: "skirmishers",
  39: "mounted archers",
});


function finite(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}


function percent(value) {
  return `${Math.round(finite(value) * 100)}%`;
}


function seconds(value) {
  const rounded = Math.round(finite(value) * 10) / 10;
  return `${rounded.toFixed(Number.isInteger(rounded) ? 0 : 1)}s`;
}


function syntheticUnit(mechanics, hp = mechanics.hp) {
  return {
    mechanics,
    hp,
    maxHp: mechanics.hp,
    specialState: {
      baseMaxHp: mechanics.hp,
      transformed: false,
      armorStripped: 0,
      killAttackBonus: 0,
      nearbyAttackBonus: 0,
    },
  };
}


function attackCategory(mechanics) {
  const declared = mechanics?.combat_categories;
  if (Array.isArray(declared) && declared.includes("mounted")) return "mounted";
  return finite(mechanics?.attack_classes?.["39"]) < 0 ? "mounted" : null;
}


function matchingBonusDamage(attacker, target) {
  const rows = [];
  for (const [classId, rawAttack] of Object.entries(attacker.attack_classes ?? {})) {
    if (classId === "3" || classId === "4" || rawAttack <= 0) continue;
    const rawArmor = target.armor_classes?.[classId];
    if (!Number.isFinite(rawArmor)) continue;
    const damage = Math.max(0, rawAttack - rawArmor);
    if (damage <= 0) continue;
    rows.push({
      classId,
      label: ARMOR_CLASS_NAMES[classId] ?? `class ${classId}`,
      attack: rawAttack,
      armor: rawArmor,
      damage,
    });
  }
  return rows;
}


function recurringProjectilePackets(attacker, target) {
  const actor = syntheticUnit(attacker);
  const victim = syntheticUnit(target);
  const ranged = rangedSpec(attacker);
  // DAT accuracy 0 is used by ground/scatter weapons (Organ Gun, Grenadier,
  // War Chariot barrage), not as a literal “can never deal damage” chance.
  // Their physical projectile spread is an army-geometry concern; the card's
  // one-target clock treats a projectile that connects as a hit.
  const accuracy = ranged && ranged.accuracyPercent > 0
    ? ranged.accuracyPercent / 100
    : 1;
  const packets = [{
    amount: calculateDamage(actor, victim) * accuracy,
    hitWeight: accuracy,
  }];
  if (ranged?.extraProjectileCount > 0) {
    for (let index = 0; index < ranged.extraProjectileCount; index += 1) {
      packets.push({
        amount: calculateDamage(actor, victim, {
          attackClasses: ranged.extraProjectileAttacks ?? undefined,
        }) * accuracy,
        hitWeight: accuracy,
      });
    }
  }
  return packets;
}


function recurringCycleSeconds(mechanics) {
  const ranged = rangedSpec(mechanics);
  const extras = ranged?.extraProjectileCount ?? 0;
  const burstTail = ranged?.reloadAfterFinalProjectile
    ? extras * ranged.volleyIntervalTicks / TICKS_PER_SECOND
    : 0;
  return Math.max(1 / TICKS_PER_SECOND, mechanics.reload_seconds + burstTail);
}


function recurringDamagePerSecond(attacker, target) {
  const damage = recurringProjectilePackets(attacker, target)
    .reduce((sum, packet) => sum + packet.amount, 0);
  return damage / recurringCycleSeconds(attacker);
}


function transformTargetIfNeeded(target) {
  const effects = target.mechanics.effects ?? {};
  const threshold = finite(effects.hp_transform_threshold);
  if (target.specialState.transformed || threshold <= 0) return;
  if (target.hp >= target.specialState.baseMaxHp * threshold - 1e-12) return;
  target.specialState.transformed = true;
  if (finite(effects.transform_hp) > 0) {
    target.maxHp = effects.transform_hp;
    target.hp = Math.min(target.hp, target.maxHp);
  }
}


function shieldChargesFor(target, attacker) {
  const effects = target.effects ?? {};
  const ranged = attacker.ranged !== null && attacker.ranged !== undefined;
  const universal = finite(
    effects.dodge_shield_max
      ?? effects.block_first_attacks
      ?? effects.ignore_first_attacks,
  );
  if (universal > 0) return Math.floor(universal);
  if (!ranged && effects.block_first_melee) return 1;
  if (ranged && effects.block_first_ranged) return 1;
  return 0;
}


function attackReloadTicks(attacker, hitTicks, transformed = false) {
  const effects = attacker.effects ?? {};
  let reload = transformed && finite(effects.transform_attack_speed) > 0
    ? 1 / effects.transform_attack_speed
    : attacker.reload_seconds;
  const ramp = finite(effects.attack_speed_ramp);
  if (ramp > 0) {
    const cutoff = (hitTicks.at(-1) ?? 0) - 5 * TICKS_PER_SECOND;
    const recent = hitTicks.filter((tick) => tick > cutoff).length;
    reload = Math.max(finite(effects.attack_speed_min, 1), reload - ramp * recent);
  }
  const ranged = rangedSpec(attacker);
  const burstTail = ranged?.reloadAfterFinalProjectile
    ? (ranged.extraProjectileCount ?? 0) * ranged.volleyIntervalTicks
    : 0;
  return Math.max(1, Math.ceil(reload * TICKS_PER_SECOND) + burstTail);
}


function packetDamage(attacker, target, attackClasses = undefined) {
  return calculateDamage(syntheticUnit(attacker), target, { attackClasses });
}


// A compact one-on-one combat clock. It intentionally excludes walking,
// projectile travel and retaliation: the card answers “once this unit can
// attack, how long does it take to defeat one of that unit?” The damage path
// is shared with the V3 engine, while the small timeline below accounts for
// charge recharge, burst cadence, armor stripping, bleed, regeneration,
// transformations, dismounts and any first-hit shield exported by the profile.
export function estimateTimeToKill(attackerMechanics, targetMechanics) {
  const attacker = attackerMechanics;
  let target = syntheticUnit(targetMechanics);
  let shieldCharges = shieldChargesFor(targetMechanics, attackerMechanics);
  const openingProjectileCharge = chargeSpec(attacker);
  const openingMeleeCharge = meleeChargeSpec(attacker);
  const openingDelaySeconds = openingProjectileCharge
    ? openingProjectileCharge.windupTicks / TICKS_PER_SECOND
    : openingMeleeCharge
      ? openingMeleeCharge.windupTicks / TICKS_PER_SECOND
      : attacker.attack_delay_seconds;
  let nextAttackTick = Math.max(0, Math.round(
    openingDelaySeconds * TICKS_PER_SECOND,
  ));
  let nextChargeTick = 0;
  let bleedStacks = [];
  let delayedDamage = [];
  let activeHazards = [];
  const hitTicks = [];
  let dismounted = false;

  const damageTarget = (amount, hitWeight = 1) => {
    if (amount <= 0) return;
    if (shieldCharges > 0) {
      shieldCharges -= 1;
      return;
    }
    target.hp = Math.max(0, target.hp - amount);
    const effects = attacker.effects ?? {};
    if (target.hp > 0 && finite(effects.armor_strip_per_hit) > 0) {
      target.specialState.armorStripped += effects.armor_strip_per_hit * hitWeight;
    }
    if (target.hp > 0 && finite(effects.bleed_dps) > 0
        && finite(effects.bleed_duration) > 0) {
      bleedStacks.push({
        dps: effects.bleed_dps * hitWeight,
        until: currentTick + Math.ceil(effects.bleed_duration * TICKS_PER_SECOND),
      });
    }
    transformTargetIfNeeded(target);
  };

  let currentTick = 0;
  while (currentTick <= MAX_TTK_TICKS) {
    if (target.hp <= 1e-9) {
      if (!dismounted && target.mechanics.dismount_form) {
        target = syntheticUnit(target.mechanics.dismount_form);
        shieldCharges = shieldChargesFor(target.mechanics, attacker);
        bleedStacks = [];
        activeHazards = [];
        dismounted = true;
      } else {
        return currentTick / TICKS_PER_SECOND;
      }
    }
    const targetEffects = target.mechanics.effects ?? {};
    const regenPerMinute = finite(targetEffects.hp_regen);
    if (regenPerMinute > 0 && target.hp < target.maxHp) {
      target.hp = Math.min(target.maxHp,
        target.hp + regenPerMinute / 60 / TICKS_PER_SECOND);
    }
    bleedStacks = bleedStacks.filter(({ until }) => until > currentTick);
    const bleedDamage = bleedStacks.reduce((sum, stack) => sum + stack.dps, 0)
      / TICKS_PER_SECOND;
    if (bleedDamage > 0) damageTarget(bleedDamage, 0);

    for (const pending of delayedDamage.filter(({ tick }) => tick === currentTick)) {
      damageTarget(pending.amount, 0);
    }
    delayedDamage = delayedDamage.filter(({ tick }) => tick > currentTick);
    activeHazards = activeHazards.filter(({ until }) => until > currentTick);
    if (activeHazards.length > 0) {
      const stacks = (attacker.effects ?? {}).impact_hazard_stacks === true;
      const dps = stacks
        ? activeHazards.reduce((sum, hazard) => sum + hazard.dps, 0)
        : Math.max(...activeHazards.map(({ dps: value }) => value));
      damageTarget(dps / TICKS_PER_SECOND, 0);
    }

    if (currentTick === nextAttackTick) {
      const ranged = rangedSpec(attacker);
      const projectileCharge = chargeSpec(attacker);
      const meleeCharge = meleeChargeSpec(attacker);
      const legacyCharge = finite(attacker.effects?.charge_attack_melee);
      const chargeReady = currentTick >= nextChargeTick;
      let releasedRegularAttack = true;

      if (projectileCharge && chargeReady) {
        const hitWeight = (ranged?.baseAccuracyPercent ?? 100) / 100;
        for (let index = 0; index < projectileCharge.projectileCount; index += 1) {
          damageTarget(chargeProjectileDamage(projectileCharge, target) * hitWeight,
            hitWeight);
        }
        releasedRegularAttack = projectileCharge.addsToNormalAttack;
        const rechargeSeconds = finite(attacker.charge?.recharge_seconds)
          || projectileCharge.maxCharge / projectileCharge.rechargeRate;
        nextChargeTick = currentTick + Math.ceil(rechargeSeconds * TICKS_PER_SECOND);
      }

      if (!projectileCharge && chargeReady && (meleeCharge || legacyCharge > 0)) {
        const base = packetDamage(attacker, target);
        damageTarget(base + (meleeCharge?.attackBonus ?? legacyCharge));
        releasedRegularAttack = false;
        const recharge = meleeCharge?.rechargeSeconds
          ?? finite(attacker.effects?.charge_recharge_time);
        nextChargeTick = currentTick + Math.ceil(recharge * TICKS_PER_SECOND);
      }

      if (releasedRegularAttack) {
        const accuracy = ranged && ranged.accuracyPercent > 0
          ? ranged.accuracyPercent / 100
          : 1;
        damageTarget(packetDamage(attacker, target) * accuracy, accuracy);
        for (let index = 0; index < (ranged?.extraProjectileCount ?? 0); index += 1) {
          damageTarget(packetDamage(
            attacker,
            target,
            ranged.extraProjectileAttacks ?? undefined,
          ) * accuracy, accuracy);
        }
        const effects = attacker.effects ?? {};
        const delayedAttack = finite(effects.delayed_impact_melee_attack);
        const repeats = Math.max(0, Math.floor(finite(effects.delayed_impact_repeat_count)));
        const delaySeconds = finite(effects.delayed_impact_delay_seconds);
        const intervalSeconds = finite(
          effects.delayed_impact_repeat_interval_seconds,
          delaySeconds,
        );
        if (delayedAttack > 0 && repeats > 0 && delaySeconds > 0) {
          const amount = packetDamage(attacker, target, { 4: delayedAttack });
          for (let repeat = 0; repeat < repeats; repeat += 1) {
            delayedDamage.push({
              tick: currentTick + Math.ceil(
                (delaySeconds + repeat * intervalSeconds) * TICKS_PER_SECOND,
              ),
              amount,
            });
          }
        }
        const hazardDps = finite(effects.impact_hazard_damage_per_second);
        const hazardDuration = finite(effects.impact_hazard_duration_seconds);
        if (hazardDps > 0 && hazardDuration > 0) {
          activeHazards.push({
            dps: hazardDps,
            until: currentTick + Math.ceil(hazardDuration * TICKS_PER_SECOND),
          });
        }
      }

      hitTicks.push(currentTick);
      nextAttackTick = currentTick + attackReloadTicks(
        attacker,
        hitTicks,
        false,
      );
    }
    currentTick += 1;
  }
  return null;
}


function mechanicCallouts(attacker, target, bonusRows) {
  const effects = attacker.effects ?? {};
  const targetEffects = target.effects ?? {};
  const ranged = rangedSpec(attacker);
  const callouts = [];
  const add = (text) => {
    if (text && !callouts.includes(text)) callouts.push(text);
  };

  for (const bonus of bonusRows) {
    add(`+${bonus.damage} bonus damage vs ${bonus.label}`);
  }
  const areaCharge = meleeChargeSpec(attacker);
  const projectileCharge = chargeSpec(attacker);
  const legacyCharge = finite(effects.charge_attack_melee);
  if (areaCharge || legacyCharge > 0) {
    const amount = areaCharge?.attackBonus ?? legacyCharge;
    const recharge = areaCharge?.rechargeSeconds ?? effects.charge_recharge_time;
    add(`Charge: +${amount} damage${recharge ? ` every ${seconds(recharge)}` : ""}`);
  }
  if (projectileCharge) {
    add(`Charge volley: ${projectileCharge.projectileCount} projectile${projectileCharge.projectileCount === 1 ? "" : "s"}`);
  }
  if (effects.ignores_melee_armor) add("Ignores melee armor");
  if (effects.ignores_pierce_armor) add("Ignores pierce armor");
  if (ranged && ranged.accuracyPercent === 0) {
    add("Projectiles use physical spread");
  } else if (ranged && ranged.accuracyPercent < 100) {
    add(`${Math.round(ranged.accuracyPercent)}% accuracy; missed shots can strike other units`);
  }
  if ((ranged?.extraProjectileCount ?? 0) > 0) {
    add(`${ranged.extraProjectileCount + 1}-projectile attack`);
  }
  if (ranged?.reloadAfterFinalProjectile && ranged.volleyIntervalTicks > 0) {
    add(`Burst fire: ${seconds(ranged.volleyIntervalTicks / TICKS_PER_SECOND)} between arrows`);
  }
  if (ranged?.minRangeTiles > 0) add(`${ranged.minRangeTiles}-tile minimum range`);
  if (ranged?.passThrough) {
    add(`Pass-through: ${percent(ranged.passThroughDamageFraction)} damage to units behind`);
  }
  const trample = trampleSpec(attacker);
  if (trample) {
    const shape = trample.shape === "forward-cone" ? "Forward splash" : "Area damage";
    add(`${shape}: ${percent(trample.damageFraction)} within ${trample.widthTiles.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")} tiles`);
  }
  if (finite(effects.armor_strip_per_hit) > 0) {
    add(`Strips ${effects.armor_strip_per_hit} armor per hit`);
  }
  if (finite(effects.bleed_dps) > 0) {
    add(`Bleed: ${effects.bleed_dps} DPS for ${seconds(effects.bleed_duration)}`);
  }
  if (finite(effects.execute_damage_per_step) > 0) {
    const step = effects.execute_hp_step > 1
      ? effects.execute_hp_step / 100
      : effects.execute_hp_step;
    add(`Deals +${effects.execute_damage_per_step} damage per ${percent(step)} target HP lost`);
  }
  if (finite(effects.on_hit_slow_percent) > 0) {
    add(`Slows movement ${percent(effects.on_hit_slow_percent)} for ${seconds(effects.on_hit_slow_duration_seconds)}`);
  }
  if (finite(effects.delayed_impact_repeat_count) > 0) {
    add(`${effects.delayed_impact_repeat_count} delayed impact explosions`);
  }
  if (finite(effects.impact_hazard_damage_per_second) > 0) {
    add(`Burning ground: ${effects.impact_hazard_damage_per_second} DPS for ${seconds(effects.impact_hazard_duration_seconds)}`);
  }
  if (finite(effects.attack_speed_ramp) > 0) add("Attacks faster with consecutive hits");
  if (finite(effects.attack_bonus_per_kill) > 0) {
    add(`Gains up to +${effects.attack_bonus_per_kill} attack from kills`);
  }
  if (finite(effects.hp_per_kill) > 0) add(`Heals ${effects.hp_per_kill} HP per kill`);
  if (finite(effects.hp_regen) > 0) add(`Regenerates ${effects.hp_regen} HP per minute`);
  if (finite(effects.hp_nearby_percent_per_unit) > 0) add("Gains HP near allied units");
  if (finite(effects.hp_transform_threshold) > 0) {
    add(`Changes form below ${percent(effects.hp_transform_threshold)} HP`);
  }
  if (attacker.dismount_form) add("Continues fighting dismounted after defeat");
  if (finite(effects.death_explosion_melee_attack) > 0) add("Explodes on death");
  if (finite(effects.damage_reflect_percent) > 0) {
    add(`Reflects ${percent(effects.damage_reflect_percent)} melee damage`);
  }

  const reduction = finite(
    target.damage_reduction_by_attacker_category?.[attackCategory(attacker)],
  );
  if (reduction > 0) add(`Target reduces each hit by ${reduction}`);
  const shield = shieldChargesFor(target, attacker);
  if (shield > 0) add(`Target blocks the first ${shield} hit${shield === 1 ? "" : "s"}`);
  if (finite(targetEffects.hp_regen) > 0) {
    add(`Target regenerates ${targetEffects.hp_regen} HP per minute`);
  }
  if (target.dismount_form) add("Time to kill includes the target's dismounted form");
  return callouts;
}


export function summarizeMatchup(attackerMechanics, targetMechanics) {
  const attacker = syntheticUnit(attackerMechanics);
  const target = syntheticUnit(targetMechanics);
  const damagePerHit = calculateDamage(attacker, target);
  const bonusDamage = matchingBonusDamage(attackerMechanics, targetMechanics);
  const timeToKillSeconds = estimateTimeToKill(attackerMechanics, targetMechanics);
  return Object.freeze({
    damagePerHit,
    damagePerSecond: recurringDamagePerSecond(attackerMechanics, targetMechanics),
    timeToKillSeconds,
    bonusDamage: Object.freeze(bonusDamage),
    callouts: Object.freeze(mechanicCallouts(
      attackerMechanics,
      targetMechanics,
      bonusDamage,
    )),
    timeToKillHelp: "One unit defeating one opposing unit from attack-ready range. Includes reload, accuracy, bursts, charge, armor changes, regeneration, damage-over-time and dismounting; excludes walking, projectile travel and retaliation.",
  });
}
