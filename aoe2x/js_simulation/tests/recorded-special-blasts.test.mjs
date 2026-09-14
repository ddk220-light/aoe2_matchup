import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {forwardLineBlastHits, suicideExplosionDamage, trampleSpec, attackDelayTicks} from '../src/combat/attacks.js';

const load = async name => JSON.parse(await readFile(new URL('../fixtures/'+name, import.meta.url)));
const tiger = await load('unit_stats/elite_tiger_cavalry_wei_imperial.json');
const ghulam = await load('unit_stats/elite_ghulam_hindustanis_imperial.json');
const camel = await load('unit_stats/flaming_camel_tatars_imperial.json');
const recorded = await load('recorded-special-blast-samples.json');

test('Ghulam geometry reproduces recorded positive and negative recipients on both temporal halves', () => {
  const counts = [0,0];
  for (const row of recorded.ghulam) {
    // Crowded events listed here have unresolved source/direction attribution;
    // preserve them in the evidence instead of assigning a fabricated label.
    if (recorded.ambiguousGhulamGameMs.includes(row.gameMs)) continue;
    const hit=forwardLineBlastHits({x:0,y:0},{x:row.fx,y:row.fy},
      {x:row.dx,y:row.dy,mechanics:tiger},trampleSpec(ghulam));
    assert.equal(hit,row.delta>0,`${row.gameMs}: ${row.actor} -> ${row.victim}`);
    counts[row.gameMs<20000 ? 0 : 1]++;
  }
  assert.ok(counts.every(n=>n>100));
});

test('Flaming Camel reproduces isolated recorded explosion HP losses, including misses and minimum damage', () => {
  assert.equal(recorded.flamingCamel.length,135);
  for (const row of recorded.flamingCamel) {
    const damage=suicideExplosionDamage({x:row.actorX,y:row.actorY,mechanics:camel},
      {x:row.victimX,y:row.victimY,mechanics:tiger});
    assert.ok(Math.abs(damage-row.damage)<.0001,`${row.gameMs}: ${damage} vs ${row.damage}`);
  }
});

test('mode 66 explosion tapers and does not reach past the radius', () => {
  const actor={x:0,y:0,mechanics:camel};
  const victim=x=>({x,y:0,mechanics:tiger});
  assert.equal(suicideExplosionDamage(actor,victim(0)),64);
  assert.equal(suicideExplosionDamage(actor,victim(1.25)),32);
  assert.equal(suicideExplosionDamage(actor,victim(2.24)),1);
  assert.equal(suicideExplosionDamage(actor,victim(2.25)),0);
});

test('the recorded Tiger, Ghulam and Shotel windups are unchanged', async () => {
  const shotel=await load('unit_stats/elite_shotel_warrior_ethiopians_imperial.json');
  assert.equal(attackDelayTicks(tiger),48);
  assert.equal(attackDelayTicks(ghulam),24);
  assert.equal(attackDelayTicks(shotel),45);
});

test('Flaming Camel self-destruct does not wait for its death-animation midpoint', () => {
  assert.equal(camel.frame_delay,0);
  assert.equal(camel.attack_animation.graphic,camel.death_animation.graphic);
  assert.equal(attackDelayTicks(camel),0);
  assert.match(camel.provenance.fields.attack_delay_seconds,/self-destruct/);
});
