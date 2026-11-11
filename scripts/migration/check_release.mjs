import {readFileSync, readdirSync, statSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve, relative} from 'node:path';
const root = fileURLToPath(new URL('../../', import.meta.url));
const service = process.argv[2];
if (!['frontend', 'backend'].includes(service)) throw new Error('Choose frontend or backend');
const generated = resolve(root, 'apps/web/src/generated');
const runtime = resolve(root, 'apps/backend/runtime');
const manifest = JSON.parse(readFileSync(resolve(service === 'frontend' ? generated : runtime, 'release.json')));
const base = service === 'frontend' ? resolve(root, 'apps/web/public') : runtime;
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
for (const [path, expected] of Object.entries(manifest[service])) {
  if (hash(resolve(base, path)) !== expected) throw new Error(`Unsealed artifact: ${path}`);
}
for (const [path, expected] of Object.entries(manifest.source_sha256)) {
  const owned = service === 'frontend'
    ? path.startsWith('apps/web/') || path === 'scripts/migration/check_release.mjs'
    : path.startsWith('apps/backend/');
  if (owned && hash(resolve(root, path)) !== expected) throw new Error(`Source changed after sealing: ${path}`);
}
function files(dir) {
  return readdirSync(dir).flatMap(name => {
    const path = resolve(dir, name);
    if (name === '__pycache__') return [];
    return statSync(path).isDirectory() ? files(path) : [relative(base, path)];
  });
}
for (const path of files(base)) {
  if (service === 'backend' && path === 'release.json') continue;
  if (!(path in manifest[service])) throw new Error(`Unexpected artifact: ${path}`);
}
if (service === 'frontend' && hash(resolve(generated, 'about.json')) !== manifest.about_sha256) {
  throw new Error('Unsealed about page');
}
if (service === 'frontend') {
  for (const [name,expected] of Object.entries(manifest.generated)) {
    if (hash(resolve(generated,name)) !== expected) throw new Error(`Unsealed generated data: ${name}`);
  }
}
console.log(`Verified ${service} release ${manifest.release_id}`);
