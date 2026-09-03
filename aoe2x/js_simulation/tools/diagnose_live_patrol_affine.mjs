import { readFile } from "node:fs/promises";


const ROOT = new URL("../", import.meta.url);
const analysis = JSON.parse(await readFile(new URL(
  "calibration/live_observations/ranged_matrix_5x_2026-08-29/grpc_matrix_analysis.json",
  ROOT,
), "utf8"));
const formations = JSON.parse(await readFile(new URL(
  "fixtures/current_ranged_golden_formations.json",
  ROOT,
), "utf8"));


function solve3(matrix, values) {
  const rows = matrix.map((row, index) => [...row, values[index]]);
  for (let column = 0; column < 3; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < 3; row += 1) {
      if (Math.abs(rows[row][column]) > Math.abs(rows[pivot][column])) pivot = row;
    }
    [rows[column], rows[pivot]] = [rows[pivot], rows[column]];
    const divisor = rows[column][column];
    for (let index = column; index < 4; index += 1) rows[column][index] /= divisor;
    for (let row = 0; row < 3; row += 1) {
      if (row === column) continue;
      const factor = rows[row][column];
      for (let index = column; index < 4; index += 1) {
        rows[row][index] -= factor * rows[column][index];
      }
    }
  }
  return rows.map((row) => row[3]);
}


function affine(rows, outputName) {
  const normal = Array.from({ length: 3 }, () => Array(3).fill(0));
  const rhs = Array(3).fill(0);
  for (const row of rows) {
    const vector = [1, row.initial.x, row.initial.y];
    for (let left = 0; left < 3; left += 1) {
      rhs[left] += vector[left] * row[outputName];
      for (let right = 0; right < 3; right += 1) {
        normal[left][right] += vector[left] * vector[right];
      }
    }
  }
  return solve3(normal, rhs);
}


function summarize(matchupKey, owner, waypointName) {
  const matchup = analysis.matchups[matchupKey];
  const family = formations.families[matchup.family];
  const rows = matchup.runs.flatMap((run) => run.units
    .filter((unit) => unit.owner === owner && unit[waypointName])
    .map((unit) => ({
      initial: family.sides[String(owner)][unit.slot - 1].position,
      x: unit[waypointName].x,
      y: unit[waypointName].y,
    })));
  const x = affine(rows, "x");
  const y = affine(rows, "y");
  const determinant = x[1] * y[2] - x[2] * y[1];
  const columnScaleX = Math.hypot(x[1], y[1]);
  const columnScaleY = Math.hypot(x[2], y[2]);
  return {
    samples: rows.length,
    translation: { x: x[0], y: y[0] },
    linear: [[x[1], x[2]], [y[1], y[2]]],
    determinant,
    columnScale: { x: columnScaleX, y: columnScaleY },
    rotationDegrees: Math.atan2(y[1], x[1]) * 180 / Math.PI,
  };
}


const keys = process.argv.slice(2);
for (const matchupKey of keys.length ? keys : [
  "arbalester_vs_hand_cannoneer",
  "arbalester_vs_heavy_cav_archer",
]) {
  const result = {};
  for (const owner of [2, 3]) {
    result[owner] = {
      at3s: summarize(matchupKey, owner, "waypoint_3s"),
      at4_5s: summarize(matchupKey, owner, "waypoint_4_5s"),
    };
  }
  process.stdout.write(`${matchupKey}\n${JSON.stringify(result, null, 2)}\n`);
}
