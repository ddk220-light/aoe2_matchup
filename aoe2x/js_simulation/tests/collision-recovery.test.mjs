import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { resolveMovementProposals } from "../src/combat/collision.js";
import {
  loadDedicatedComparisonContext,
  runDedicatedTapeRepeat,
} from "../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../src/dedicated-golden-corpus.js";


const ROOT = new URL("../", import.meta.url);
const championMechanics = JSON.parse(await readFile(
  new URL("fixtures/unit_stats/champion_chinese_imperial.json", ROOT),
  "utf8",
));


function capturedChampion(referenceId, x, y) {
  return Object.freeze({
    referenceId,
    owner: 3,
    x,
    y,
    alive: true,
    mechanics: championMechanics,
  });
}


function capturedRanged(referenceId, x, y) {
  return Object.freeze({
    referenceId,
    owner: 2,
    x,
    y,
    alive: true,
    moveOrder: Object.freeze({ kind: "move" }),
    mechanics: championMechanics,
  });
}


test("a sub-tile obstacle residual preserves the safe portion of crowd movement", () => {
  const captured = [
    [1605, 5.664279002262242, 5.972414173574474, 0.014498347492853206, -0.00997787218820785],
    [1606, 6.438178368566149, 6.3012709574397805, 0.015274372273957625, -0.008743772930736998],
    [1607, 6.9103077897787974, 5.621270950287223, 0, 0],
    [1608, 4.148326197615705, 6.121275070159191, 0.007227486833596469, -0.016047537116265668],
    [1609, 4.603291668657258, 6.0851525373090265, 0.009112320682852275, -0.01505741097269372],
    [1610, 6.480149896009585, 6.636469230889832, 0.00019266610376060688, -0.017598945797978816],
    [1611, 6.602203134252346, 5.981270952671409, -0.007420145130270318, -0.015959369024916372],
    [1612, 5.250923294666577, 5.787571329016924, 0.01387641226411607, -0.010826134864485276],
    [1613, 5.929088442112617, 5.431150963709605, 0.007459344104143175, -0.015941085250500326],
    [1614, 5.423481092707521, 6.850377407014211, 0.005978164977949852, -0.016553596495147163],
    [1615, 6.484177703643399, 7.234129249166916, 0.0020976431445263828, -0.017474550256471728],
    [1616, 6.8001499007779564, 6.51448643091714, 0.006728294382869332, -0.016263150621118393],
    [1618, 6.118178363797777, 6.056650557756287, -0.004809163168800951, -0.016930208594213573],
    [1619, 7.0299785372383745, 5.98127095267045, 0.010043394070499428, -0.014453035977689654],
    [1621, 6.332942039120035, 5.51187327998363, 0.011965248855878047, -0.012907084614452781],
    [1622, 5.892388115393565, 6.729588252254998, 0.006212167552925807, -0.01646720946979513],
    [1623, 6.924133771445857, 6.925194783093973, 0.006201426938428149, -0.01647125730947921],
  ];
  const capturedRangedCrowd = [
    [1263, 10.168570596967044, 5.059019437549293, 0.013958542986035835, 0.007820426951707293],
    [1264, 12.49, 5.334101738604459, 0, 0],
    [1265, 11.080108145171153, 4.700417289479046, 0.015169949767673808, 0.005086513938470373],
    [1266, 12.01, 6.294101738604459, 0, 0],
    [1267, 12.49, 6.294101738604459, 0, 0],
    [1268, 11.257693006041645, 5.079400179194696, 0.011685139856107973, 0.01092966177624893],
    [1269, 7.934109805305673, 4.976220569273163, 0.01566562301392629, -0.0032539599852399697],
    [1270, 11.126057489889629, 5.340970415879427, 0.01549796333815639, 0.003976572942768736],
    [1271, 8.760907150477669, 4.765256357007047, 0.01593993422097613, -0.001385098202639143],
    [1272, 9.17346942397661, 4.752005978988772, 0.015242173806373379, 0.004865813154684974],
    [1273, 10.051507482007183, 5.002488288721725, 0.012057520268185292, 0.010517423875754982],
    [1549, 11.499725002517263, 5.7902790169464895, 0.01257398320093273, 0.009894187508970182],
    [1550, 11.53, 6.294101738604459, 0, 0],
    [1551, 12.003506839611262, 5.326770154083838, 0.0064931603887377065, 0.007331584520620993],
    [1552, 12.01, 5.8141017386044584, 0, 0],
  ];
  const snapshot = [
    ...capturedRangedCrowd.map(([referenceId, x, y]) => (
      capturedRanged(referenceId, x, y)
    )),
    ...captured.map(([referenceId, x, y]) => capturedChampion(referenceId, x, y)),
  ];
  const proposals = [...capturedRangedCrowd, ...captured].map(([
    referenceId, , , dx, dy,
  ]) => ({
    referenceId, dx, dy,
  }));
  const map = {
    width: 16,
    height: 16,
    obstacles: [
      { referenceId: 1577, x: 7.5, y: 6.5, radius: 0.5 },
      { referenceId: 1578, x: 7.5, y: 7.5, radius: 0.5 },
      { referenceId: 1579, x: 10.5, y: 6.5, radius: 0.5 },
      { referenceId: 1580, x: 10.5, y: 7.5, radius: 0.5 },
      { referenceId: 1581, x: 8.5, y: 5.5, radius: 0.5 },
      { referenceId: 1582, x: 9.5, y: 5.5, radius: 0.5 },
    ],
  };

  const diagnostics = [];
  const moved = resolveMovementProposals(snapshot, proposals, map, {
    onCollisionDiagnostics: (diagnostic) => diagnostics.push(diagnostic),
  });
  const recovered = moved.find(({ referenceId }) => referenceId === 1616);

  assert.equal(diagnostics.length, 1);
  assert.equal(diagnostics[0].mode, "slop");
  assert.equal(diagnostics[0].sweeps, 4096);
  assert.ok(
    recovered.y < snapshot.find(({ referenceId }) => referenceId === 1616).y - 0.001,
    `expected preserved movement, got ${
      snapshot.find(({ referenceId }) => referenceId === 1616).y - recovered.y
    }`,
  );

  const followupDiagnostics = [];
  const toleratedStart = moved.map((unit) => (unit.referenceId === 1616
    ? Object.freeze({
      ...unit,
      x: 6.8001499007779564,
      y: 6.511696881805894,
    })
    : unit));
  const collisionRecoveryState = { active: true };
  resolveMovementProposals(toleratedStart, proposals, map, {
    collisionRecoveryState,
    onCollisionDiagnostics: (diagnostic) => followupDiagnostics.push(diagnostic),
  });
  assert.equal(followupDiagnostics.length, 1);
  assert.ok(followupDiagnostics[0].sweeps < 4096);
});


test("a formerly non-convergent dense obstacle fight completes", async () => {
  const [corpus, context] = await Promise.all([
    loadDedicatedGoldenCorpus(ROOT),
    loadDedicatedComparisonContext(ROOT),
  ]);
  const row = corpus.rows.find(({ id }) => id === "arbalester_vs_champion_15v20");
  assert.ok(row, "expected the authorized Arbalester 15v20 golden row");

  const result = runDedicatedTapeRepeat({ row, run: row.runs[0], context });

  assert.equal(result.outcome, "win");
  assert.ok(Number.isFinite(result.score));
  assert.ok(result.ticks > 0);
});


test("collision recovery preserves a previously working HCA Steppe result", async () => {
  const [corpus, context] = await Promise.all([
    loadDedicatedGoldenCorpus(ROOT),
    loadDedicatedComparisonContext(ROOT),
  ]);
  const row = corpus.rows.find(({ id }) => (
    id === "heavy_cav_archer_vs_elite_steppe_20v20"
  ));
  assert.ok(row, "expected the authorized HCA Steppe 20v20 golden row");

  const result = runDedicatedTapeRepeat({ row, run: row.runs[0], context });

  assert.equal(result.score, -41.875);
  assert.equal(result.winnerOwner, 2);
  assert.equal(result.ticks, 4072);
});
