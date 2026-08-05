// Sample the engine over acquisition ORDERS and report a distribution, not a
// point.
//
// Why this exists. Every repeat of a golden-basics ratio starts from
// byte-identical positions, so the spread between repeats is the GAME's own
// nondeterminism -- and it is large: 0% below six units, but 75-94% of winner
// HP at 8v4/10v5/21v10, where even the winning SIDE flips. Decoding the tapes
// shows the whole delta lives in the opening target assignment: in 8v4 the
// three repeats where two paladin pairs doubled up on one champion each are the
// three the paladins won by 19-26%, and the two repeats where they doubled up
// once are a near-tie and a champion win.
//
// Our engine ranks acquisition by reference id, which is one arbitrary draw
// from that space. Permuting the rank permutes who moves first, hence who is
// nearest when the next unit acquires, hence the opening targets. Sampling the
// permutation is therefore the honest analogue of the game's roll, and turns a
// single number into a band comparable with the tape's.
//
//   node tools/sample_acquisition_orders.mjs --ratio 8v4 --samples 200
//
// Deterministic: the permutations come from a seeded PRNG, so a given
// --seed/--samples pair always yields the same band. Sample 0 is always the
// identity order, i.e. exactly what the deterministic path produces today.
import { readFile } from "node:fs/promises";

import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, runWorld } from "../src/combat/world.js";

const ROOT = new URL("../", import.meta.url);
const TRUTH = "calibration/fixtures/champion_vs_paladin_basics.json";
const MECHANICS = {
  567: "fixtures/unit_stats/champion_chinese_imperial.json",
  569: "fixtures/unit_stats/paladin_spanish_imperial.json",
};


function parseArgs(argv) {
  const args = { ratio: null, samples: 200, seed: 20260411, json: false };
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    if (flag === "--ratio") args.ratio = argv[++i];
    else if (flag === "--samples") args.samples = Number(argv[++i]);
    else if (flag === "--seed") args.seed = Number(argv[++i]);
    else if (flag === "--json") args.json = true;
    else throw new RangeError(`unknown flag ${flag}`);
  }
  if (!args.ratio) throw new RangeError("--ratio is required");
  if (!Number.isSafeInteger(args.samples) || args.samples < 1) {
    throw new RangeError("--samples must be a positive integer");
  }
  return args;
}


// mulberry32: small, seeded, and reproducible across runs and platforms.
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}


function shuffled(count, random) {
  const order = Array.from({ length: count }, (_, i) => i);
  for (let i = count - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}


function runOnce(roster, mechanics, ratio, ranks) {
  const units = roster.map(([referenceId, owner, master, x, y], index) => (
    createUnitState({
      referenceId, owner, x, y, facing: 0,
      mechanics: mechanics.get(master),
      acquisitionRank: ranks[index],
      acquisitionCount: roster.length,
    })
  ));
  const result = runWorld(createWorld({ ratio, units }));
  const live = result.world.units.filter(({ alive }) => alive);

  // Opening target per unit = its first non-null pursuit target.
  const opening = new Map();
  for (const snapshot of result.snapshots) {
    for (const unit of snapshot.units) {
      const target = unit.pursuitTargetId;
      if (target !== null && target !== undefined && !opening.has(unit.referenceId)) {
        opening.set(unit.referenceId, target);
      }
    }
    if (opening.size === roster.length) break;
  }

  const ownerOf = new Map(roster.map(([id, owner]) => [id, owner]));
  const paladinOpenings = [...opening.entries()]
    .filter(([id]) => ownerOf.get(id) === 3).map(([, target]) => target);
  const championOpenings = [...opening.entries()]
    .filter(([id]) => ownerOf.get(id) === 2).map(([, target]) => target);

  return {
    winnerOwner: live.length ? live[0].owner : null,
    winnerHp: live.reduce((total, unit) => total + unit.hp, 0),
    survivors: live.length,
    seconds: result.ticks / 60,
    paladinDistinct: new Set(paladinOpenings).size,
    championDistinct: new Set(championOpenings).size,
    opening: Object.fromEntries([...opening.entries()].sort((a, b) => a[0] - b[0])),
  };
}


function signedMargin(nc, np, winnerOwner, winnerHp) {
  const pool = winnerOwner === 2 ? nc * 70 : np * 180;
  return (winnerHp / pool) * 100 * (winnerOwner === 2 ? 1 : -1);
}


const args = parseArgs(process.argv.slice(2));
const truth = JSON.parse(await readFile(new URL(TRUTH, ROOT), "utf8"));
const ratioTruth = truth.ratios?.[args.ratio];
if (!ratioTruth) throw new RangeError(`unknown ratio ${args.ratio}`);
const mechanics = new Map();
for (const [master, path] of Object.entries(MECHANICS)) {
  mechanics.set(Number(master), JSON.parse(await readFile(new URL(path, ROOT), "utf8")));
}

const roster = ratioTruth.canonicalStartUnits;
const [nc, np] = args.ratio.split("v").map(Number);
const random = mulberry32(args.seed);

const samples = [];
const seen = new Set();
// Some orders never resolve inside the engine's 3600-tick (60 s) guard. That is
// itself a finding -- the tape settles every 15v8 in 25.0-34.4 s -- so count
// them and report, rather than raising the cap and hiding a runaway fight.
let unresolved = 0;
for (let i = 0; i < args.samples; i += 1) {
  const ranks = i === 0
    ? Array.from({ length: roster.length }, (_, k) => k)
    : shuffled(roster.length, random);
  let run;
  try {
    run = runOnce(roster, mechanics, args.ratio, ranks);
  } catch (error) {
    if (!/exceeded \d+ ticks/.test(String(error?.message))) throw error;
    unresolved += 1;
    continue;
  }
  run.margin = signedMargin(nc, np, run.winnerOwner, run.winnerHp);
  run.openingKey = JSON.stringify(run.opening);
  samples.push(run);
  seen.add(run.openingKey);
}
if (samples.length === 0) {
  throw new Error(`every sampled order for ${args.ratio} exceeded the tick guard`);
}

const tape = ratioTruth.runs.map((run) => ({
  ...run,
  margin: signedMargin(nc, np, run.winnerOwner, run.winnerHp),
}));

if (args.json) {
  console.log(JSON.stringify({ ratio: args.ratio, samples, tape }, null, 1));
} else {
  const hp = samples.map((s) => s.winnerHp);
  const champWins = samples.filter((s) => s.winnerOwner === 2).length;
  const tapeChamp = tape.filter((r) => r.winnerOwner === 2).length;
  const pct = (n, d) => `${((n / d) * 100).toFixed(0)}%`;
  const fmt = (v) => v.map((x) => x.toFixed(1)).join(" ");

  console.log(`ratio ${args.ratio}  (${roster.length} units, ${args.samples} sampled orders, seed ${args.seed})`);
  console.log(`  distinct opening assignments : ${seen.size}`);
  if (unresolved) {
    console.log(`  orders exceeding the 60 s guard: ${unresolved}/${args.samples}`
      + `  (excluded below; the tape always resolves)`);
  }
  console.log(`  champions win                 : sim ${pct(champWins, samples.length)}`
    + `   tape ${pct(tapeChamp, tape.length)}  (${tapeChamp}/${tape.length})`);
  console.log(`  winner HP  sim  ${Math.min(...hp).toFixed(0)}-${Math.max(...hp).toFixed(0)}`
    + `   tape ${Math.min(...tape.map((r) => r.winnerHp)).toFixed(0)}`
    + `-${Math.max(...tape.map((r) => r.winnerHp)).toFixed(0)}`);
  const simMargins = samples.map((s) => s.margin).sort((a, b) => a - b);
  const tapeMargins = tape.map((r) => r.margin).sort((a, b) => a - b);
  console.log(`  signed margin (+champ/-palad)`);
  console.log(`    sim  ${simMargins[0].toFixed(1)} .. ${simMargins.at(-1).toFixed(1)}`
    + `   median ${simMargins[Math.floor(simMargins.length / 2)].toFixed(1)}`);
  console.log(`    tape ${fmt(tapeMargins)}`);
  const lo = Math.min(...tapeMargins);
  const hi = Math.max(...tapeMargins);
  const covered = simMargins.filter((m) => m >= lo && m <= hi).length;
  console.log(`  sim orders landing inside the tape margin band: `
    + `${covered}/${samples.length} (${pct(covered, samples.length)})`);
  console.log(`  identity order (today's deterministic answer): `
    + `${samples[0].margin.toFixed(1)}  ${samples[0].winnerOwner === 2 ? "champions" : "paladins"}`);
}
