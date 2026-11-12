// Load and verify a pinned matchup engine (aoe2x/matchups/engines/<id>/).
//
// Start-up checks follow loadManifest()/verifyManifest() of the 2026 runners
// (RB:aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs):
// every runtime file's SHA-256, the Node version, and that no AOE2X_EXP_*
// variable differs from the allowed experiment environment. The Node check is
// a recorded, config-controlled setting instead of the 2026 hard refusal:
//   exact    - only ENGINE.json node.pinned may run;
//   verified - pinned, or a version listed in node.verified (replay evidence
//              recorded in ENGINE.json); anything else is refused;
//   warn     - any version runs; an unverified one is reported as a warning.
import { createHash } from 'node:crypto';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const MATCHUPS_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const NODE_POLICIES = ['exact', 'verified', 'warn'];
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function engineDirectory(engineId) {
  return resolve(MATCHUPS_DIR, 'engines', engineId);
}

export function checkNodeVersion(engine, policy = 'verified', version = process.version) {
  if (!NODE_POLICIES.includes(policy)) throw new Error(`unknown node version policy ${policy}`);
  const pinned = engine.node.pinned;
  const verified = (engine.node.verified ?? []).map(v => v.version);
  const status = version === pinned ? 'pinned' : verified.includes(version) ? 'verified' : 'unverified';
  const record = { version, pinned, policy, status };
  if (policy === 'exact' && status !== 'pinned')
    throw new Error(`Node ${version} refused: engine pins ${pinned} (policy exact)`);
  if (policy === 'verified' && status === 'unverified')
    throw new Error(`Node ${version} refused: not ${pinned} and no recorded replay evidence (policy verified)`);
  if (status === 'unverified') record.warning = `Node ${version} has no recorded replay evidence for this engine`;
  return record;
}

export function checkEnvironment(allowed = {}, env = process.env) {
  const actual = Object.fromEntries(Object.entries(env).filter(([k]) => k.startsWith('AOE2X_EXP_')).sort());
  const want = Object.fromEntries(Object.entries(allowed).sort());
  if (JSON.stringify(actual) !== JSON.stringify(want))
    throw new Error(`experiment environment ${JSON.stringify(actual)} differs from allowed ${JSON.stringify(want)}`);
  return actual;
}

export function loadEngine(directory, { nodePolicy = 'verified', environment = {} } = {}) {
  const manifestPath = resolve(directory, 'ENGINE.json');
  if (!existsSync(manifestPath)) throw new Error(`missing ${manifestPath}`);
  const engine = JSON.parse(readFileSync(manifestPath, 'utf8'));
  if (engine.schema !== 'aoe2-matchup-engine/v1') throw new Error(`unknown engine schema ${engine.schema}`);
  const bad = [];
  for (const file of engine.files) {
    const path = resolve(directory, file.path);
    if (!existsSync(path)) { bad.push(`missing ${file.path}`); continue; }
    if (sha256(readFileSync(path)) !== file.sha256) bad.push(`changed ${file.path}`);
  }
  if (bad.length) throw new Error(`engine ${engine.engineId} failed verification: ${bad.join(', ')}`);
  const node = checkNodeVersion(engine, nodePolicy);
  checkEnvironment(environment);
  return {
    engine, node, runtimeRoot: directory,
    workerData: { runtimeRoot: directory, entry: engine.entry, hooks: engine.hooks },
  };
}
