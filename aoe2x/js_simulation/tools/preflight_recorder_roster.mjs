// Validate the entire approved roster before starting a comparison campaign.
import { readFile, writeFile } from 'node:fs/promises';
import { unitBySlug } from '../src/unit-registry.js';
import { loadLabScenario } from '../src/lab-scenario.js';
const root = new URL('../', import.meta.url);
const roster = JSON.parse(await readFile(new URL('../../../data/unique-unit-roster.json', import.meta.url)));
const rows = [];
for (const unit of roster.units) {
  try {
    const entry = unitBySlug(unit.slug);
    if (!entry) throw Error('Missing registry entry');
    const profile = JSON.parse(await readFile(new URL(`fixtures/unit_stats/${entry.fixture}`, root)));
    if (profile.unit_master !== unit.master || profile.civilization !== unit.civ) throw Error('Wrong unit/civilization');
    if (!(profile.hp > 0) || !Number.isFinite(profile.speed_tiles_per_second)) throw Error('Invalid HP or speed');
    if (!/^[a-f0-9]{64}$/i.test(profile.provenance?.dat_sha256 ?? '')) throw Error('Missing DAT provenance');
    if (!Object.keys(profile.attack_classes).length && !profile.effects?.non_attacking) throw Error('Unspecified attack behavior');
    const scenario = await loadLabScenario(root, 'elite_tiger_cavalry_wei', unit.slug);
    rows.push({slug:unit.slug, status:'ready', fixture:entry.fixture, family:scenario.family,
      datSha256:profile.provenance.dat_sha256});
  } catch (error) { rows.push({slug:unit.slug,status:'failed',error:error.message}); }
}
const result = {generatedAt:new Date().toISOString(), ready:rows.filter(r=>r.status==='ready').length,
  total:rows.length, scope:'Source profiles and Golden scenario inputs; empirical accuracy is evaluated separately', rows};
const output = process.argv[2];
if (output) await writeFile(output, JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({ready:result.ready,total:result.total,failures:rows.filter(r=>r.status==='failed')}));
if (result.ready !== result.total) process.exitCode=1;
