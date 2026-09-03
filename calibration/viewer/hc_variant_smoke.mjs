// Headless integration smoke for the viewer's isolated engine arms.
import { createReadStream, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const FIXTURES = path.join(ROOT, "calibration", "fixtures");
const ENGINE_REL = path.join("apps", "website", "static", "js", "engine");
const LOCKED_ARCHIVE = "aoe2_golden_STANDARD_UNITS_FINAL.zip";
const LOCKED_SHA256 = "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9";
const LOCKED_RECORDINGS = 339;
const TOP_GAP_MATCHUPS = [
  "hand_cannoneer__vs__heavy_scorpion",
  "hand_cannoneer__vs__elite_steppe",
  "hand_cannoneer__vs__paladin",
];

const VARIANTS = {
  base: {
    engine: path.join(ROOT, ENGINE_REL),
    flags: {}, arena: "tapebox",
  },
  recovery: {
    engine: path.join(ROOT, ".worktrees", "hc-h1-posthit", ENGINE_REL),
    flags: { c3: ["postSwingRecovery"] }, arena: "tapebox",
  },
  h1: {
    engine: path.join(ROOT, ".worktrees", "hc-h1-posthit", ENGINE_REL),
    flags: { c3: ["postSwingRecovery", "postSwingPlant", "postSwingCollisionAnchor"] },
    arena: "tapebox",
  },
  h2: {
    engine: path.join(ROOT, ".worktrees", "hc-h2-viewer", ENGINE_REL),
    flags: { c3: ["postSwingRecovery"], h2: ["laneAwareRangedHandoff"] },
    arena: "tapebox",
  },
  h3: {
    engine: path.join(ROOT, ".worktrees", "hc-h3-obstacle", ENGINE_REL),
    flags: { c3: ["postSwingRecovery"] }, arena: "tapebox-obstacle",
  },
  h1_h3: {
    engine: path.join(ROOT, ".worktrees", "hc-h3-obstacle", ENGINE_REL),
    flags: {
      c3: ["postSwingRecovery", "postSwingPlant", "postSwingCollisionAnchor"],
    },
    arena: "tapebox-obstacle",
  },
};

async function smokePhysicsRenderer() {
  // The browser server mounts this module beside variant-specific engine files.
  // Rewrite those two browser-relative imports to file URLs for this Node smoke.
  const sourcePath = path.join(HERE, "physics_renderer.js");
  const constantsUrl = pathToFileURL(path.join(ROOT, "apps", "website", "static", "js", "engine", "constants.js")).href;
  const simRendererSource = readFileSync(
    path.join(ROOT, "apps", "website", "static", "js", "sim_renderer.js"),
    "utf8",
  ).replace('"./engine/constants.js"', JSON.stringify(constantsUrl));
  const simRendererUrl = `data:text/javascript;base64,${Buffer.from(simRendererSource).toString("base64")}`;
  const source = readFileSync(sourcePath, "utf8")
    .replace('"./sim_renderer.js"', JSON.stringify(simRendererUrl))
    .replace('"./engine/constants.js"', JSON.stringify(constantsUrl));
  globalThis.window = globalThis.window || { devicePixelRatio: 1 };
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  const { PhysicsSimRenderer } = await import(moduleUrl);
  const context = new Proxy({}, {
    get(target, property) {
      if (!(property in target)) target[property] = () => {};
      return target[property];
    },
    set(target, property, value) {
      target[property] = value;
      return true;
    },
  });
  const canvas = {
    width: 900,
    height: 600,
    getContext: () => context,
    getBoundingClientRect: () => ({ width: 900, height: 600 }),
  };
  const renderer = new PhysicsSimRenderer(canvas);
  if (!renderer || renderer.ctx !== context) throw new Error("PhysicsSimRenderer construction failed");
}

const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));
async function sha256File(file) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};
const mode = (values) => {
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0][0];
};

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function tapeOutcome(truth, dicts) {
  const winner = Object.values(truth.sides).find((side) => Number(side.hp_remaining) > 0);
  if (!winner) return { winner: "draw", hp: 0 };
  const dict = dicts[`${winner.civ}|${winner.slug}`];
  return {
    winner: winner.slug,
    hp: 100 * Number(winner.hp_remaining) / (Number(dict.hp) * Number(winner.start_count)),
  };
}

function signedOutcome(outcome, focalSlug) {
  if (outcome.winner === "draw" || outcome.winner === "mutual" || outcome.winner === "cap") return 0;
  return outcome.winner === focalSlug ? outcome.hp : -outcome.hp;
}

function representativeFight(matchup, manifest, dicts) {
  const candidates = manifest.filter((fight) => fight.matchup === matchup).map((fight) => {
    const truth = readJson(path.join(FIXTURES, "truth", `${fight.tag}.json`));
    return { fight, tape: tapeOutcome(truth, dicts) };
  });
  const winner = mode(candidates.map((item) => item.tape.winner));
  const winnerRuns = candidates.filter((item) => item.tape.winner === winner);
  const hp = median(winnerRuns.map((item) => item.tape.hp));
  return winnerRuns.sort((a, b) =>
    Math.abs(a.tape.hp - hp) - Math.abs(b.tape.hp - hp) || a.fight.tag.localeCompare(b.fight.tag)
  )[0].fight;
}

function configure(constants, flags) {
  if (flags.c3) constants.setC3(Object.fromEntries(flags.c3.map((name) => [name, true])));
  if (flags.h2) constants.setH2(Object.fromEntries(flags.h2.map((name) => [name, true])));
}

function buildSimulation(createSimulation, TapeBoxWithObstruction, fight, dicts, spawns, seed, arena, cutFraction) {
  const teams = [fight.side1, fight.side2].map((side, index) => ({
    combatDict: dicts[`${side.civ}|${side.slug}`],
    slug: side.slug,
    civ: side.civ,
    count: side.count,
    positions: spawns[fight.tag][String(side.owner)],
  }));
  const arenaSpec = arena === "tapebox-obstacle" && Number.isFinite(cutFraction)
    ? new TapeBoxWithObstruction({ pursuitCutFieldFraction: cutFraction })
    : arena;
  return createSimulation({ teams, seed, arena: arenaSpec });
}

function finish(sim) {
  const maxTicks = 600 * 60;
  let ticks = 0;
  const orbit = {
    1: { radius_sum: 0, samples: 0 },
    2: { radius_sum: 0, samples: 0 },
  };
  while (sim.winner === null && ticks < maxTicks) {
    sim.step(1 / 60);
    ticks++;
    const obstruction = sim.arena?.obstruction;
    if (obstruction && ticks % 6 === 0) {
      for (const [teamId, team] of [[1, sim.team1], [2, sim.team2]]) {
        for (const unit of team) {
          if (unit.state === "dead") continue;
          const radius = Math.hypot(unit.x - obstruction.x, unit.y - obstruction.y) / 30;
          if (radius <= 6) {
            orbit[teamId].radius_sum += radius;
            orbit[teamId].samples++;
          }
        }
      }
    }
  }
  const orbitRadiusTiles = Object.fromEntries(Object.entries(orbit).map(([teamId, value]) => [
    teamId,
    value.samples ? value.radius_sum / value.samples : null,
  ]));
  if (sim.winner !== 1 && sim.winner !== 2) {
    return { winner: sim.winner === 0 ? "mutual" : "cap", hp_pct: 0, duration_s: sim.battleTime, combat_stats: sim.combatStats, orbit_radius_tiles: orbitRadiusTiles };
  }
  const team = sim.winner === 1 ? sim.team1 : sim.team2;
  const hp = team.filter((unit) => unit.state !== "dead").reduce((sum, unit) => sum + unit.currentHp, 0);
  const maxHp = team.reduce((sum, unit) => sum + unit.maxHp, 0);
  return {
    winner: sim.winner === 1 ? sim.team1[0].slug : sim.team2[0].slug,
    hp_pct: maxHp ? 100 * hp / maxHp : 0,
    duration_s: sim.battleTime,
    combat_stats: sim.combatStats,
    orbit_radius_tiles: orbitRadiusTiles,
  };
}

const variantId = arg("--variant", "base");
const seeds = Math.max(1, Number.parseInt(arg("--seeds", "1"), 10) || 1);
const scope = arg("--scope", "top-gaps");
const matchupFilter = arg("--matchup", "");
const diagnostics = arg("--diagnostics", "false") === "true";
const cutFractionArg = Number.parseFloat(arg("--cut-fraction", ""));
const cutFraction = Number.isFinite(cutFractionArg) ? cutFractionArg : null;
if (!(variantId in VARIANTS)) throw new Error(`Unknown variant ${variantId}`);
if (scope === "hc-melee" && seeds !== 5) {
  throw new Error("the hc-melee acceptance gate requires exactly 5 seeds");
}
await smokePhysicsRenderer();
const variant = VARIANTS[variantId];
const engineUrl = pathToFileURL(path.join(variant.engine, "index.js")).href;
const constantsUrl = pathToFileURL(path.join(variant.engine, "constants.js")).href;
const [{ createSimulation, TapeBoxWithObstruction }, constants] = await Promise.all([import(engineUrl), import(constantsUrl)]);
configure(constants, variant.flags);

const source = readJson(path.join(ROOT, "calibration", "source", "source_of_truth.json"));
if (source.archive !== LOCKED_ARCHIVE) throw new Error(`Unexpected tape archive ${source.archive}`);
const archiveSha256 = await sha256File(path.join(ROOT, "calibration", "source", LOCKED_ARCHIVE));
if (String(source.sha256).toUpperCase() !== archiveSha256) {
  throw new Error(`Archive SHA-256 metadata mismatch: ${source.sha256} != ${archiveSha256}`);
}
if (archiveSha256 !== LOCKED_SHA256) throw new Error(`Not the locked FINAL archive: ${archiveSha256}`);
const manifest = readJson(path.join(FIXTURES, "manifest.json")).fights;
if (manifest.length !== LOCKED_RECORDINGS || Number(source.recordings) !== LOCKED_RECORDINGS) {
  throw new Error(`Locked FINAL source must contain ${LOCKED_RECORDINGS} recordings`);
}
if (manifest.some((fight) =>
  fight.source_archive !== LOCKED_ARCHIVE ||
  String(fight.zip_sha256).toUpperCase() !== archiveSha256)) {
  throw new Error("Fixture manifest contains a non-FINAL tape source");
}
const dicts = readJson(path.join(FIXTURES, "combat_dicts.json"));
const spawns = readJson(path.join(FIXTURES, "spawns.json"));
const fightSets = readJson(path.join(FIXTURES, "fight_sets.json"));
const melee = new Set(fightSets.melee);
let matchups = scope === "hc-melee"
  ? [...new Set(manifest
    .filter((fight) => {
      const slugs = [fight.side1.slug, fight.side2.slug];
      return slugs.includes("hand_cannoneer") && slugs.some((slug) => melee.has(slug));
    })
    .map((fight) => fight.matchup))].sort()
  : TOP_GAP_MATCHUPS;
if (matchupFilter) matchups = matchups.filter((matchup) => matchup === matchupFilter);
if (scope === "hc-melee" && !matchupFilter) {
  const opponents = [...new Set(manifest
    .filter((fight) => matchups.includes(fight.matchup))
    .flatMap((fight) => [fight.side1.slug, fight.side2.slug])
    .filter((slug) => slug !== "hand_cannoneer"))].sort();
  const expected = [...fightSets.melee].sort();
  if (JSON.stringify(opponents) !== JSON.stringify(expected)) {
    throw new Error(`HC-melee gate families differ from fight_sets.json: ${opponents.join(",")}`);
  }
}
const results = [];
for (const matchup of matchups) {
  const matchupFights = manifest.filter((candidate) => candidate.matchup === matchup);
  const fights = scope === "hc-melee"
    ? matchupFights
    : [representativeFight(matchup, manifest, dicts)];
  const tapeRuns = matchupFights
    .map((candidate) => tapeOutcome(readJson(path.join(FIXTURES, "truth", `${candidate.tag}.json`)), dicts));
  const tapeSignedHp = median(tapeRuns.map((outcome) => signedOutcome(outcome, "hand_cannoneer")));
  const runs = [];
  for (const fight of fights) {
    for (let seed = 1; seed <= seeds; seed++) {
      runs.push(finish(buildSimulation(
        createSimulation,
        TapeBoxWithObstruction,
        fight,
        dicts,
        spawns,
        seed,
        variant.arena,
        cutFraction,
      )));
    }
  }
  const simSignedHp = median(runs.map((run) =>
    run.winner === "hand_cannoneer" ? run.hp_pct : -run.hp_pct));
  const modalWinner = simSignedHp >= 0
    ? "hand_cannoneer"
    : fights[0].side1.slug === "hand_cannoneer"
      ? fights[0].side2.slug
      : fights[0].side1.slug;
  const result = {
    matchup,
    representative_tag: scope === "hc-melee" ? `all:${fights.length}` : fights[0].tag,
    winner: modalWinner,
    winner_hp_pct: Math.abs(simSignedHp),
    tape_signed_hp_pct: tapeSignedHp,
    sim_signed_hp_pct: simSignedHp,
    signed_hp_gap: Math.abs(simSignedHp - tapeSignedHp),
    winner_correct: Math.sign(simSignedHp) === Math.sign(tapeSignedHp),
    within_25pct: Math.abs(simSignedHp - tapeSignedHp) <= 25,
    duration_s: median(runs.map((run) => run.duration_s)),
    recordings: fights.length,
    runs: runs.length,
  };
  if (diagnostics) result.run_outcomes = runs;
  results.push(result);
}

const gatePassed = scope === "hc-melee"
  ? results.length === 7 && results.every((row) => row.winner_correct && row.within_25pct)
  : null;
process.stdout.write(JSON.stringify({
  variant: variantId,
  seeds,
  scope,
  source_sha256: archiveSha256,
  gate_passed: gatePassed,
  results,
}));
if (scope === "hc-melee" && !gatePassed) process.exitCode = 1;
