import assert from "node:assert/strict";
import test from "node:test";

import {
  analyzePairContactFrames,
  percentile,
} from "../tools/pair-contact-metrics.mjs";

const frame = (timeMs, units) => Object.freeze({
  timeMs,
  units: Object.freeze(units),
});

const unit = (id, owner, x, {
  master = owner,
  moving = false,
  attacking = false,
  targetId = null,
  minCollisionMultiplier = 1,
} = {}) => Object.freeze({
  id,
  owner,
  master,
  x,
  y: 4,
  radius: 0.25,
  hp: 100,
  moving,
  attacking,
  minCollisionMultiplier,
  pursuitTargetId: targetId,
  engagedTargetId: targetId,
  attackTargetId: attacking ? targetId : null,
});

test("pair contact metrics separate relationship, motion, attack, intent, and phase", () => {
  const report = analyzePairContactFrames([
    frame(0, [unit(1, 2, 4), unit(2, 2, 4.6), unit(3, 3, 5.2)]),
    frame(100, [
      unit(1, 2, 4.2, { moving: true, targetId: 3 }),
      unit(2, 2, 4.55, { attacking: true, targetId: 3 }),
      unit(3, 3, 4.5, { moving: true, targetId: 1 }),
    ]),
  ]);

  assert.equal(
    report.populations["same-master-allies|one-moving|one-attacking|none|entering"].overlapPairs,
    1,
  );
  assert.equal(
    report.populations["enemies|both-moving|neither-attacking|direct-target|entering"].overlapPairs,
    1,
  );
  assert.equal(
    report.populations["enemies|both-moving|neither-attacking|direct-target|entering"].medianDepth,
    0.2,
  );
});

test("contact windows and graph topology do not mistake a three-stack for pairs", () => {
  const frames = [0, 100, 200].map((timeMs) => frame(timeMs, [
    unit(1, 2, 4.00),
    unit(2, 2, 4.25),
    unit(3, 2, 4.40),
  ]));
  const report = analyzePairContactFrames(frames);
  const row = report.relationships["same-master-allies"];

  assert.equal(row.maximumLocalDegree, 2);
  assert.equal(row.maximumComponentSize, 3);
  assert.equal(row.maximumTriangles, 1);
  assert.equal(row.maximumFourCliques, 0);
  assert.equal(row.maximumDeepLocalDegree, 2);
  assert.equal(row.maximumDeepTriangles, 1);
  assert.equal(row.localNeighborCount.median, 2);
  assert.equal(row.componentSize.median, 3);
  assert.equal(row.contactWindowMs.median, 300);
});

test("sourced minimum collision multipliers distinguish shallow from deep edges", () => {
  const report = analyzePairContactFrames([frame(0, [
    unit(1, 2, 4, { minCollisionMultiplier: 0.5 }),
    unit(2, 2, 4.3, { minCollisionMultiplier: 0.5 }),
    unit(3, 2, 4.45, { minCollisionMultiplier: 0.5 }),
  ])]);
  const row = report.relationships["same-master-allies"];

  assert.equal(row.maximumLocalDegree, 2);
  assert.equal(row.maximumDeepLocalDegree, 1);
  assert.equal(row.maximumDeepTriangles, 0);
});

test("contact populations retain attacking-unit access and target-load distributions", () => {
  const report = analyzePairContactFrames([frame(0, [
    unit(1, 2, 4, { attacking: true, targetId: 3 }),
    unit(2, 2, 4.1, { attacking: true, targetId: 3 }),
    unit(3, 3, 4.25),
  ])]);
  const row = report.populations[
    "enemies|neither-moving|one-attacking|direct-target|entering"
  ];

  assert.equal(row.attackingUnitCount.median, 2);
  assert.equal(row.attackAccessRatio.median, 0.666666666667);
  assert.equal(row.targetLoad.median, 2);
});

test("percentile interpolates deterministically and handles no evidence", () => {
  assert.equal(percentile([], 0.5), null);
  assert.equal(percentile([4], 0.5), 4);
  assert.equal(percentile([0, 10], 0.25), 2.5);
  assert.throws(() => percentile([1], -0.1), /probability/);
});

test("every relationship, motion, and attack combination has a stable population key", () => {
  const relationships = [
    ["same-master-allies", unit(1, 2, 4, { master: 20 }), unit(2, 2, 4.25, { master: 20 }), "none"],
    ["mixed-master-allies", unit(1, 2, 4, { master: 20 }), unit(2, 2, 4.25, { master: 21 }), "none"],
    ["enemies", unit(1, 2, 4), unit(2, 3, 4.25), "corridor-contact"],
  ];
  const motions = [
    ["neither-moving", false, false],
    ["one-moving", true, false],
    ["both-moving", true, true],
  ];
  const attacks = [
    ["neither-attacking", false, false],
    ["one-attacking", true, false],
    ["both-attacking", true, true],
  ];

  for (const [relationship, leftBase, rightBase, intent] of relationships) {
    for (const [motion, leftMoving, rightMoving] of motions) {
      for (const [attack, leftAttacking, rightAttacking] of attacks) {
        const left = Object.freeze({ ...leftBase, moving: leftMoving, attacking: leftAttacking });
        const right = Object.freeze({ ...rightBase, moving: rightMoving, attacking: rightAttacking });
        const report = analyzePairContactFrames([frame(0, [right, left])]);
        const key = [relationship, motion, attack, intent, "entering"].join("|");
        assert.equal(report.populations[key].overlapPairs, 1, key);
      }
    }
  }
});

test("contact lifecycle counts acquisition and release without fragmenting its window", () => {
  const frames = [
    frame(0, [unit(1, 2, 4), unit(2, 2, 4.25)]),
    frame(100, [unit(2, 2, 4.3, { moving: true }), unit(1, 2, 4.1)]),
    frame(200, [unit(1, 2, 4.1), unit(2, 2, 5, { moving: true })]),
  ];
  const report = analyzePairContactFrames(frames);
  const reversed = analyzePairContactFrames(frames.map((sample) => frame(
    sample.timeMs,
    [...sample.units].reverse(),
  )));

  assert.equal(report.populations["same-master-allies|neither-moving|neither-attacking|none|entering"].pairFrames, 1);
  assert.equal(report.populations["same-master-allies|one-moving|neither-attacking|none|persisting"].pairFrames, 1);
  assert.equal(report.populations["same-master-allies|one-moving|neither-attacking|none|leaving"].frameCount, 1);
  assert.equal(report.relationships["same-master-allies"].acquisitionCount, 1);
  assert.equal(report.relationships["same-master-allies"].releaseCount, 1);
  assert.equal(report.relationships["same-master-allies"].contactWindowMs.median, 200);
  assert.deepEqual(reversed, report);
});
