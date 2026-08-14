import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRangedVsMeleeAnalysis,
  renderRangedVsMeleeCsv,
} from "../tools/run_ranged_vs_melee_suite.mjs";


const report = {
  schemaVersion: 1,
  lane: "tape_conditioned_canonical_start",
  source: { zip_sha256: "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D" },
  config: { samples: 5, volatileSamples: 100, seed: 20260411, maxTicks: 9000 },
  schedule: { stableRows: 1, volatileRows: 1, totalRuns: 105 },
  summary: { unresolvedRuns: 2 },
  rows: [
    {
      id: "5-10_vs_359-21",
      matchup: "Hand Cannoneer vs Halberdier",
      category: "kite",
      side2: { count: 10, master: 5, owner: 2, unit: "Hand Cannoneer" },
      side3: { count: 21, master: 359, owner: 3, unit: "Halberdier" },
      tape: { mean: -76.5, min: -76.5, max: -76.5, volatile: false, side3WinRate: 0 },
      comparison: {
        mean: -51,
        min: -60,
        max: -40,
        bandError: 25.5,
        tapeBandCoverage: 0,
        wrongStableWinner: false,
        side3WinRate: 0,
        side3WinRateError: 0,
        unresolvedRuns: 0,
        simulationRuns: 5,
      },
      samples: [],
    },
    {
      id: "474-5_vs_567-10",
      matchup: "Heavy Cavalry Archer vs Champion",
      category: "kite",
      side2: { count: 5, master: 474, owner: 2, unit: "Heavy Cavalry Archer" },
      side3: { count: 10, master: 567, owner: 3, unit: "Champion" },
      tape: { mean: 5, min: -10, max: 20, volatile: true, side3WinRate: 0.6 },
      comparison: {
        mean: -10,
        min: -25,
        max: 5,
        bandError: 0,
        tapeBandCoverage: 0.4,
        wrongStableWinner: false,
        side3WinRate: 0.3,
        side3WinRateError: 0.3,
        unresolvedRuns: 2,
        simulationRuns: 100,
      },
      samples: [],
    },
  ],
};


test("ranged-versus-melee analysis exposes auditable deltas and failures", () => {
  const analysis = buildRangedVsMeleeAnalysis(report);

  assert.equal(analysis.summary.rowCount, 2);
  assert.equal(analysis.summary.totalRuns, 105);
  assert.equal(analysis.summary.rowsOver25PointDelta, 1);
  assert.equal(analysis.summary.rowsInsideTapeBand, 1);
  assert.equal(analysis.summary.unresolvedRuns, 2);
  assert.equal(analysis.rows[0].signedMeanDelta, 25.5);
  assert.equal(analysis.rows[0].absoluteMeanDelta, 25.5);
  assert.equal(analysis.rows[0].winnerAgreement, "match");
  assert.equal(analysis.rows[1].winnerAgreement, "volatile");
  assert.equal(analysis.rows[1].failure, "2 unresolved runs");
});


test("ranged-versus-melee CSV records exact tape ratios and comparison fields", () => {
  const csv = renderRangedVsMeleeCsv(buildRangedVsMeleeAnalysis(report));

  assert.match(csv, /^id,matchup,ranged_unit,ranged_count,melee_unit,melee_count,/);
  assert.match(csv, /5-10_vs_359-21,Hand Cannoneer vs Halberdier,Hand Cannoneer,10,Halberdier,21,/);
  assert.match(csv, /25\.5,25\.5,25\.5,0,match,5,0,$/m);
});
