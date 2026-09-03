import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";


const here = path.dirname(fileURLToPath(import.meta.url));
const simRoot = path.resolve(here, "..");
const captureRoot = path.resolve(process.argv[2]);
const waypointSeconds = Number(process.argv[3] ?? 3);
if (![3, 4.5].includes(waypointSeconds)) {
  throw new RangeError("waypoint seconds must be 3 or 4.5");
}
const waypointKey = waypointSeconds === 3 ? "waypoint_3s" : "waypoint_4_5s";


async function sha256(file) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}


function quantiles(values) {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) throw new Error("distribution has no finite values");
  const sorted = [...finite].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  return Object.freeze({
    min: Number(sorted[0].toFixed(4)),
    median: Number(median.toFixed(4)),
    mean: Number((finite.reduce((sum, value) => sum + value, 0) / finite.length).toFixed(4)),
    max: Number(sorted.at(-1).toFixed(4)),
  });
}


function bySlot(run, owner, expectedCount) {
  const rows = run.units
    .filter((unit) => unit.owner === owner)
    .sort((left, right) => left.slot - right.slot);
  if (rows.length !== expectedCount) {
    throw new Error(`run ${run.repeat} owner ${owner}: expected ${expectedCount}, got ${rows.length}`);
  }
  for (const [index, unit] of rows.entries()) {
    if (unit.slot !== index + 1 || !unit[waypointKey]
        || !Number.isFinite(unit[waypointKey].x) || !Number.isFinite(unit[waypointKey].y)
        || !Number.isSafeInteger(unit.first_target_slot)
        || !Number.isFinite(unit.first_target_t)) {
      throw new Error(`run ${run.repeat} owner ${owner} slot ${index + 1} is incomplete`);
    }
  }
  return rows;
}


if (!process.argv[2]) throw new Error("usage: node derive_live_melee_opening_profile_from_grpc.mjs <capture-root>");
const manifestFile = path.join(captureRoot, "capture_manifest.json");
const grpcReportFile = path.join(captureRoot, "grpc_opening_variance.json");
const [manifestBody, grpcBody] = await Promise.all([
  readFile(manifestFile, "utf8"),
  readFile(grpcReportFile, "utf8"),
]);
const manifest = JSON.parse(manifestBody);
const grpcReport = JSON.parse(grpcBody);
if (grpcReport.runs?.length !== 5 || manifest.runs?.length !== 5) {
  throw new Error("opening profile requires exactly five validated runs");
}
const counts = {
  2: manifest.matchup.player2.count,
  3: manifest.matchup.player3.count,
};
const runs = grpcReport.runs.map((run) => ({
  ...run,
  byOwner: { 2: bySlot(run, 2, counts[2]), 3: bySlot(run, 3, counts[3]) },
}));
const targetVectors = runs.map((run) => new Map(run.units.map((unit) => (
  [`${unit.owner}:${unit.slot}`, unit.first_target_slot]
))));
const targetMedoidIndex = targetVectors.map((vector, index) => ({
  index,
  distance: targetVectors.reduce((total, other) => total
    + [...vector].filter(([key, target]) => other.get(key) !== target).length, 0),
})).sort((left, right) => left.distance - right.distance || left.index - right.index)[0].index;

const variants = runs.map((run) => ({
  repeat: run.repeat,
  movement_start_seconds: quantiles(run.units.map((unit) => unit.movement_start_t)),
  ai_order_sweep_start_seconds: run.first_ai_order_t_game_s,
  waypoint_seconds: waypointSeconds,
  by_owner: Object.fromEntries([2, 3].map((owner) => [
    owner,
    run.byOwner[owner].map((unit) => ({
      slot: unit.slot,
      position: unit[waypointKey],
      waypoints: waypointSeconds === 4.5 ? [
        { seconds: 3, position: unit.waypoint_3s },
        { seconds: 4.5, position: unit.waypoint_4_5s },
      ] : [{ seconds: 3, position: unit.waypoint_3s }],
      first_target_slot: unit.first_target_slot,
      first_target_seconds: { mean: unit.first_target_t },
    })),
  ])),
}));

const sources = await Promise.all(runs.map(async (run) => {
  const framesFile = path.resolve(run.frames_bin);
  return {
    repeat: run.repeat,
    frames_file: path.relative(simRoot, framesFile),
    frames_sha256: await sha256(framesFile),
    first_ai_order_seconds: run.first_ai_order_t_game_s,
    waypoint_seconds: waypointSeconds,
  };
}));
const profile = {
  schema_version: 1,
  matchup: grpcReport.matchup,
  source_golden_sha256: manifest.golden.sha256,
  grpc_report_sha256: await sha256(grpcReportFile),
  derivation: `Per-slot full-rate gRPC position at the first frame at or after ${waypointSeconds} game seconds`,
  representative_target_run: targetMedoidIndex + 1,
  representative_target_rule: "Minimum total per-slot target Hamming distance to the five runs",
  variants,
  sources,
  movement_start_seconds: quantiles(runs.flatMap((run) => (
    run.units.map((unit) => unit.movement_start_t)
  ))),
  ai_order_sweep_start_seconds: quantiles(runs.map((run) => run.first_ai_order_t_game_s)),
  waypoint_seconds: waypointSeconds,
  by_owner: Object.fromEntries([2, 3].map((owner) => [
    owner,
    Array.from({ length: counts[owner] }, (_, index) => {
      const observed = runs.map((run) => run.byOwner[owner][index]);
      const targetCounts = new Map();
      for (const unit of observed) {
        targetCounts.set(unit.first_target_slot, (targetCounts.get(unit.first_target_slot) ?? 0) + 1);
      }
      return {
        slot: index + 1,
        position: {
          x: Number((observed.reduce((sum, unit) => sum + unit[waypointKey].x, 0)
            / observed.length).toFixed(4)),
          y: Number((observed.reduce((sum, unit) => sum + unit[waypointKey].y, 0)
            / observed.length).toFixed(4)),
        },
        waypoints: (waypointSeconds === 4.5 ? [
          { seconds: 3, key: "waypoint_3s" },
          { seconds: 4.5, key: "waypoint_4_5s" },
        ] : [{ seconds: 3, key: "waypoint_3s" }]).map(({ seconds, key }) => ({
          seconds,
          position: {
            x: Number((observed.reduce((sum, unit) => sum + unit[key].x, 0)
              / observed.length).toFixed(4)),
            y: Number((observed.reduce((sum, unit) => sum + unit[key].y, 0)
              / observed.length).toFixed(4)),
          },
        })),
        first_target_slot: observed[targetMedoidIndex].first_target_slot,
        first_target_slot_counts: Object.fromEntries([...targetCounts.entries()]
          .sort((left, right) => left[0] - right[0])),
        first_target_seconds: quantiles(observed.map((unit) => unit.first_target_t)),
      };
    }),
  ])),
};
const output = path.join(captureRoot, "opening_profile.json");
await writeFile(output, `${JSON.stringify(profile, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  output,
  representativeTargetRun: profile.representative_target_run,
  movementStartSeconds: profile.movement_start_seconds,
  aiOrderSweepStartSeconds: profile.ai_order_sweep_start_seconds,
}, null, 2)}\n`);
