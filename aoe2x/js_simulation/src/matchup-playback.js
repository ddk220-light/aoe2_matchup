// Playback for an asymmetric matchup (two different units on the two sides).
//
// Deliberately separate from champion-comparison.js: that path is locked to the
// champion-vs-champion archive by SHA and to the five mirror ratios, and those
// locks are worth keeping. This one carries its own provenance and reuses the
// same engine, so the two never share a validation surface.
import { readFile } from "node:fs/promises";

import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { hashCanonicalJson } from "./canonical-json.js";


const MATCHUPS = Object.freeze({
  champion_vs_paladin: Object.freeze({
    truth: "calibration/fixtures/champion_vs_paladin_basics.json",
    mechanics: Object.freeze({
      567: "fixtures/unit_stats/champion_chinese_imperial.json",
      569: "fixtures/unit_stats/paladin_spanish_imperial.json",
    }),
  }),
});


export function matchupNames() {
  return Object.keys(MATCHUPS);
}


const cache = new Map();


async function loadMatchup(root, name) {
  const spec = MATCHUPS[name];
  if (!spec) throw new RangeError(`unknown matchup ${name}`);
  if (cache.has(name)) return cache.get(name);
  const truth = JSON.parse(await readFile(new URL(spec.truth, root), "utf8"));
  const mechanics = new Map();
  for (const [master, path] of Object.entries(spec.mechanics)) {
    mechanics.set(Number(master), JSON.parse(await readFile(new URL(path, root), "utf8")));
  }
  const loaded = { truth, mechanics };
  cache.set(name, loaded);
  return loaded;
}


export async function matchupRatios(root, name) {
  const { truth } = await loadMatchup(root, name);
  return Object.keys(truth.ratios);
}


export async function matchupTruth(root, name) {
  const { truth } = await loadMatchup(root, name);
  return truth;
}


const playbackCache = new Map();


export async function matchupPlayback(root, name, ratio) {
  const key = `${name}:${ratio}`;
  if (playbackCache.has(key)) return playbackCache.get(key);
  const { truth, mechanics } = await loadMatchup(root, name);
  const ratioTruth = truth.ratios?.[ratio];
  if (!ratioTruth) throw new RangeError(`unknown ratio ${ratio} for ${name}`);

  const roster = ratioTruth.canonicalStartUnits;
  const units = roster.map(([referenceId, owner, master, x, y], index) => {
    const unitMechanics = mechanics.get(master);
    if (!unitMechanics) throw new RangeError(`no mechanics fixture for master ${master}`);
    return createUnitState({
      referenceId,
      owner,
      x,
      y,
      facing: 0,
      mechanics: unitMechanics,
      // Engine reaction lag is staggered across the roster; see
      // acquisitionDelaySeconds in combat/targeting.js.
      acquisitionRank: index,
      acquisitionCount: roster.length,
    });
  });

  const result = runWorld(createWorld({ ratio, units }));
  const live = result.world.units.filter(({ alive }) => alive);
  const playback = Object.freeze({
    schemaVersion: 1,
    matchup: name,
    ratio,
    ticks: result.ticks,
    winnerOwner: live.length ? live[0].owner : null,
    winnerHp: live.reduce((total, unit) => total + unit.hp, 0),
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio,
      units: result.world.units,
    }),
    eventLogHash: hashCanonicalJson(result.events),
    source: Object.freeze({
      matchup: name,
      archive: truth.archive,
      sides: truth.sides,
    }),
    snapshots: result.snapshots,
    events: result.events,
  });
  playbackCache.set(key, playback);
  return playback;
}
