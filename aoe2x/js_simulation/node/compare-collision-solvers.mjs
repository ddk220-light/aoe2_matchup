// Differential checks against a specified frozen collision module, with seeded
// synthetic geometry plus the repository's authored movement regression cases.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { resolveMovementProposals as candidate } from '../src/combat/collision.js';
import { createPairInteractionSnapshot } from '../src/combat/pair-interactions.js';

const [baselinePath, outputPath] = process.argv.slice(2);
const { resolveMovementProposals: baseline } = await import(pathToFileURL(resolve(baselinePath)).href);
let seed = 0xb71027;
const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 2 ** 32; };
const mechanics = JSON.parse(readFileSync(new URL('../fixtures/unit_stats/champion_chinese_imperial.json', import.meta.url)));
let matches = 0, valid = 0, rejected = 0;
const run = (solver, units, proposals, map, interactions) => {
  const diagnostics = [], recovery = { active: false };
  try {
    return { result: solver(units, proposals, map, { pairInteractions: interactions,
      collisionRecoveryState: recovery, onCollisionDiagnostics: value => diagnostics.push(value) }), diagnostics, recovery };
  } catch (error) { return { error: { name: error.name, message: error.message }, diagnostics, recovery }; }
};
for (let index = 0; index < 1200; index++) {
  const radius = [.2, .4, .6][index % 3], spacing = radius * 2 + .005;
  const n = 2 + Math.floor(random() * 15);
  const units = Array.from({ length: n }, (_, i) => ({ referenceId: i + 1, owner: i % 2 + 2,
    x: 5 + (i % 4) * spacing, y: 5 + Math.floor(i / 4) * spacing, alive: true,
    mechanics: { ...mechanics, collision_size_tiles: { ...mechanics.collision_size_tiles, x: radius, y: radius } },
  }));
  const map = { width: 20, height: 20, obstacles: [
    { x: 4.5 - radius, y: 5, radius: .5 },
    { x: 8 + radius * 3, y: 5 + spacing, radius: .5 },
    ...Array.from({ length: 24 }, (_, i) => ({ x: (i % 6) * 3 + 1, y: i < 12 ? 1 : 19, radius: .4 })),
  ] };
  const scale = index % 7 === 0 ? 6 : index % 5 === 0 ? .00000000001 : .08;
  const proposals = units.map(unit => ({ referenceId: unit.referenceId,
    dx: (random() - .5) * scale, dy: (random() - .5) * scale }));
  const reservations = new Map();
  if (index % 4 === 0) {
    units[0].owner = units[1].owner;
    units[1].x = units[0].x + radius;
    reservations.set('1:2', { leftId: 1, rightId: 2, kind: 'allied-transit', collisionExtent: radius,
      pathObstructs: false, attackSurfaceExtent: radius * 2, mayDeepen: false,
      initiatorId: 1, targetId: null, acquiredTick: 0 });
  }
  const interactions = createPairInteractionSnapshot({ contactReservations: reservations });
  const expected = run(baseline, units, proposals, map, interactions);
  const actual = run(candidate, units, proposals, map, interactions);
  assert.deepEqual(actual, expected, `collision case ${index}`);
  matches++; if (actual.error) rejected++; else valid++;
}
const report = { exact: true, cases: matches, valid, rejected,
  candidateSha256: createHash('sha256').update(readFileSync(new URL('../src/combat/collision.js', import.meta.url))).digest('hex'),
  baselineSha256: createHash('sha256').update(readFileSync(baselinePath)).digest('hex') };
if (outputPath) writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
