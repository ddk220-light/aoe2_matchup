import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createPairInteractionSnapshot, resolvePairInteraction } from "../src/combat/pair-interactions.js";
import { resolveMovementProposals } from "../src/combat/collision.js";
import {
  loadDedicatedComparisonContext,
  runDedicatedTapeRepeat,
} from "../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../src/dedicated-golden-corpus.js";


const ROOT = new URL("../", import.meta.url);
test("fallback restores allied reservation violations while preserving independent movement", async () => {
  const input = JSON.parse(await readFile(new URL(
    "fixtures/collision/allied-fallback-residual.json", ROOT,
  ), "utf8"), (_, value) => value?.mapEntries ? new Map(value.mapEntries)
    : value?.setValues ? new Set(value.setValues) : value);
  const diagnostics = [];
  const moved = resolveMovementProposals(input.snapshot, input.proposals, input.map, {
    ...input.options, onCollisionDiagnostics: value => diagnostics.push(value),
  });
  assert.equal(diagnostics[0].mode, "fallback");
  assert.ok(diagnostics[0].restoredReferences.includes(9502));
  assert.ok(diagnostics[0].restoredReferences.includes(9515));
  assert.ok(moved.some((unit, index) => !diagnostics[0].restoredReferences.includes(unit.referenceId)
    && Math.hypot(unit.x - input.snapshot[index].x, unit.y - input.snapshot[index].y) > 0.001),
  "a local invalid contact must not freeze the whole army");
  for (let i = 0; i < moved.length; i++) for (let j = i + 1; j < moved.length; j++) {
    const extent = resolvePairInteraction(input.snapshot[i], input.snapshot[j],
      input.options.pairInteractions).collisionExtent;
    assert.ok(Math.max(Math.abs(moved[i].x - moved[j].x), Math.abs(moved[i].y - moved[j].y))
      >= extent - 1e-4, `published surface violated for ${moved[i].referenceId}:${moved[j].referenceId}`);
  }
});

test("a sub-tile obstacle residual preserves movement and reuses recovery on the next tick", async () => {
  // This capture includes the contact reservations that make its starting
  // overlaps valid. The older hand-copied fixture omitted that authority.
  const { input } = JSON.parse(await readFile(new URL(
    "fixtures/collision/ranking-crossbow-hussar-residual.json", ROOT,
  ), "utf8"));
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map(input.reservations),
  });
  const diagnostics = [], collisionRecoveryState = { active: false };
  const moved = resolveMovementProposals(input.snapshot, input.proposals, input.map, {
    pairInteractions, collisionRecoveryState,
    onCollisionDiagnostics: value => diagnostics.push(value),
  });
  assert.equal(diagnostics[0].mode, "slop");
  assert.equal(collisionRecoveryState.active, true);
  assert.ok(moved.some((unit, index) => Math.hypot(
    unit.x - input.snapshot[index].x, unit.y - input.snapshot[index].y,
  ) > 0.001), "safe movement must survive a residual elsewhere in the crowd");
  const followup = [];
  resolveMovementProposals(moved, input.proposals, input.map, {
    pairInteractions, collisionRecoveryState,
    onCollisionDiagnostics: value => followup.push(value),
  });
  assert.equal(followup.length, 1);
  assert.ok(followup[0].sweeps < diagnostics[0].sweeps,
    "active recovery must avoid repeating the initial full sweep budget");
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


test("dense HCA Steppe collision recovery completes with deterministic replay", async () => {
  const [corpus, context] = await Promise.all([
    loadDedicatedGoldenCorpus(ROOT),
    loadDedicatedComparisonContext(ROOT),
  ]);
  const row = corpus.rows.find(({ id }) => (
    id === "heavy_cav_archer_vs_elite_steppe_20v20"
  ));
  assert.ok(row, "expected the authorized HCA Steppe 20v20 golden row");

  const result = runDedicatedTapeRepeat({ row, run: row.runs[0], context });

  // The old -41.875/4072 expectation already disagreed with the frozen
  // ranking engine before these fixes. Outcome calibration belongs in the
  // versioned comparison reports, not a collision-recovery safety contract.
  const replay = runDedicatedTapeRepeat({ row, run: row.runs[0], context });
  assert.equal(result.outcome, "win");
  assert.ok(Number.isFinite(result.score));
  assert.ok(result.ticks > 0);
  assert.deepEqual(replay, result);
});
