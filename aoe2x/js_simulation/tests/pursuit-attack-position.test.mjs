import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { createWorld, stepWorld } from '../src/combat/world.js';
import { isWithinReach } from '../src/combat/targeting.js';
import { isWithinStopRange } from '../src/combat/attacks.js';

const load = async name => JSON.parse(await readFile(new URL(
  `../fixtures/unit_stats/${name}`, import.meta.url), 'utf8'));
const cavalry = await load('paladin_spanish_imperial.json');
const infantry = await load('champion_chinese_imperial.json');
const unit = (referenceId, owner, x, mechanics, pursuitTargetId) => ({
  referenceId, owner, x, y: 5, facing: 0, mechanics,
  unitMaster: mechanics.unit_master, hp: mechanics.hit_points, alive: true,
  pursuitTargetId, engagedTargetId: null, attackTargetId: null,
  avoidance: null, action: 'idle',
  actionTimers: { windup: 0, reload: 0, acquire: 0, swing: 0 },
});

test('a blocked range-zero attacker requests recovery outside its swing-start envelope', () => {
  let world = createWorld({ ratio: 'attack-position-recovery',
    map: { width: 12, height: 12,
      obstacles: Array.from({ length: 8 }, (_, index) => ({ referenceId: 900 + index,
        x: 5 + 0.35 * Math.cos(index * Math.PI / 4),
        y: 5 + 0.35 * Math.sin(index * Math.PI / 4), radius: 0.1 })) },
    units: [unit(1, 2, 5, cavalry, 2),
      unit(2, 3, 5.68, { ...infantry, speed_tiles_per_second: 0 }, 1)] });
  assert.equal(isWithinReach(world.units[0], world.units[1]), true);
  assert.equal(isWithinStopRange(world.units[0], world.units[1]), false);
  let recovery = false, attacked = false;
  for (let tick = 0; tick < 180; tick++) {
    world = stepWorld(world);
    recovery ||= world.events.some(event => event.actorId === 1
      && ['pursuit-route-planned', 'pursuit-retarget-requested'].includes(event.type));
    attacked ||= world.events.some(event => event.actorId === 1
      && event.type === 'attack-start');
    if (recovery) break;
  }
  assert.equal(recovery, true, `outline reach must not suppress blocked-step recovery (attacked=${attacked}, x=${world.units[0].x}, y=${world.units[0].y})`);
  assert.equal(attacked, false, 'recovery must not grant a longer attack range');
});
