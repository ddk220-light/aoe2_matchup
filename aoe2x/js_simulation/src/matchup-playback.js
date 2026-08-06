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
  champion_vs_elephant: Object.freeze({
    truth: "calibration/fixtures/champion_vs_elephant_basics.json",
    mechanics: Object.freeze({
      567: "fixtures/unit_stats/champion_chinese_imperial.json",
      1134: "fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json",
    }),
  }),
  paladin_vs_elephant: Object.freeze({
    truth: "calibration/fixtures/paladin_vs_elephant_basics.json",
    mechanics: Object.freeze({
      569: "fixtures/unit_stats/paladin_spanish_imperial.json",
      1134: "fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json",
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


export const SYNTHETIC_RATIO_PATTERN = /^[1-9]\d?v[1-9]\d?$/;
const SYNTHETIC_SIDE_CAP = 40;
const SYNTHETIC_ROW_WIDTH = 8;


// Free-form NvM ratios have no tape truth; spawn a deterministic formation in
// the golden arena's own geometry: side 2 fills rows downward from y=6.5 and
// side 3 fills rows upward from y=8.5 (the recorded tapes' spawn bands), both
// left-to-right from x=1.5 at one-tile pitch.
function sideMasters(spec, truth) {
  const masterByFixture = new Map(Object.entries(spec.mechanics).map(
    ([master, path]) => [path.split("/").pop().replace(/\.json$/, ""), Number(master)],
  ));
  const masters = {};
  for (const owner of [2, 3]) {
    const master = masterByFixture.get(truth.sides?.[String(owner)]);
    if (master === undefined) {
      throw new RangeError(`no mechanics fixture for side ${owner}`);
    }
    masters[owner] = master;
  }
  return masters;
}


function syntheticRoster(spec, truth, ratio) {
  if (!SYNTHETIC_RATIO_PATTERN.test(ratio)) {
    throw new RangeError(`ratio must look like 6v3, got ${ratio}`);
  }
  const [countTwo, countThree] = ratio.split("v").map(Number);
  if (countTwo > SYNTHETIC_SIDE_CAP || countThree > SYNTHETIC_SIDE_CAP) {
    throw new RangeError(`synthetic sides are capped at ${SYNTHETIC_SIDE_CAP} units`);
  }
  const masters = sideMasters(spec, truth);
  const roster = [];
  for (let index = 0; index < countTwo; index += 1) {
    roster.push([
      9000 + index, 2, masters[2],
      1.5 + (index % SYNTHETIC_ROW_WIDTH),
      6.5 - Math.floor(index / SYNTHETIC_ROW_WIDTH),
    ]);
  }
  for (let index = 0; index < countThree; index += 1) {
    roster.push([
      9500 + index, 3, masters[3],
      1.5 + (index % SYNTHETIC_ROW_WIDTH),
      8.5 + Math.floor(index / SYNTHETIC_ROW_WIDTH),
    ]);
  }
  return roster;
}


function runRoster({ name, ratio, roster, mechanics, truth, synthetic }) {
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
  return Object.freeze({
    schemaVersion: 1,
    matchup: name,
    ratio,
    synthetic,
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
      archive: synthetic ? null : truth.archive,
      sides: truth.sides,
    }),
    snapshots: result.snapshots,
    events: result.events,
  });
}


export async function matchupPlayback(root, name, ratio) {
  const key = `${name}:${ratio}`;
  if (playbackCache.has(key)) return playbackCache.get(key);
  const { truth, mechanics } = await loadMatchup(root, name);
  const ratioTruth = truth.ratios?.[ratio];
  if (!ratioTruth) throw new RangeError(`unknown ratio ${ratio} for ${name}`);
  const playback = runRoster({
    name, ratio, roster: ratioTruth.canonicalStartUnits, mechanics, truth,
    synthetic: false,
  });
  playbackCache.set(key, playback);
  return playback;
}


// Free-form ratio with no tape run: deterministic synthesized formation, same
// engine, same playback shape, `synthetic: true` and no source archive.
export async function syntheticMatchupPlayback(root, name, ratio) {
  const key = `${name}:${ratio}:synthetic`;
  if (playbackCache.has(key)) return playbackCache.get(key);
  const spec = MATCHUPS[name];
  if (!spec) throw new RangeError(`unknown matchup ${name}`);
  const { truth, mechanics } = await loadMatchup(root, name);
  if (truth.ratios?.[ratio]) return matchupPlayback(root, name, ratio);
  const playback = runRoster({
    name, ratio, roster: syntheticRoster(spec, truth, ratio), mechanics, truth,
    synthetic: true,
  });
  playbackCache.set(key, playback);
  return playback;
}
