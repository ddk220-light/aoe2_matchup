import assert from "node:assert/strict";
import test from "node:test";

import { runChampionRatio } from "./support/champion-ratio.mjs";


test("Champion 2v1 matches the authorized median outcome", () => {
  const result = runChampionRatio("2v1");

  assert.equal(result.winnerOwner, 2);
  // The three authorized 2v1 runs span 98-112 winner HP. The gate is that
  // band, not its median: pinning the median would be fitting the outcome, which
  // is exactly what this engine forbids.
  assert.ok(
    result.winnerHp >= 98 && result.winnerHp <= 112,
    `winner HP ${result.winnerHp} outside the authorized 2v1 band 98-112`,
  );
  assert.equal(result.livingUnits.length, 2);
  assert.ok(result.damageEvents.length >= 7 && result.damageEvents.length <= 8);
});


test("Champion 2v1 preserves shared targeting, legal contact, and reversal", () => {
  const forward = runChampionRatio("2v1");
  const reversed = runChampionRatio("2v1", { reverseUnits: true });
  const acquisitions = forward.events
    .filter(({ type, actorId, targetId }) => (
      type === "pursuit-acquired" && [1628, 1629].includes(actorId) && targetId === 1699
    ))
    .map(({ actorId }) => actorId)
    .sort((left, right) => left - right);
  const rearDamage = forward.damageEvents.filter(({ actorId }) => actorId === 1629);

  assert.deepEqual(acquisitions, [1628, 1629]);
  assert.ok(forward.events.some(({ type, actorId, targetId }) => (
    type === "engagement-started" && actorId === 1629 && targetId === 1699
  )));
  assert.equal(rearDamage.length, 2);
  for (const snapshot of forward.snapshots) {
    for (let i = 0; i < snapshot.units.length; i += 1) {
      for (let j = i + 1; j < snapshot.units.length; j += 1) {
        const left = snapshot.units[i];
        const right = snapshot.units[j];
        assert.ok(
          Math.hypot(right.x - left.x, right.y - left.y)
            >= left.mechanics.collision_size_tiles.x
              + right.mechanics.collision_size_tiles.x
              - 1e-12,
        );
      }
    }
  }
  assert.equal(reversed.finalStateHash, forward.finalStateHash);
  assert.equal(reversed.eventLogHash, forward.eventLogHash);
});
