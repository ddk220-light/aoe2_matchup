import assert from "node:assert/strict";
import test from "node:test";

import { runChampionRatio } from "./support/champion-ratio.mjs";


const EPSILON = 1e-12;


// Non-overlap is owner aware. Enemies hold the full box (0.20 + 0.20 = 0.40
// Chebyshev); allies may shrink to min_collision_size_multiplier against each
// other (0.16 + 0.16 = 0.32), which is what the tapes show.
function minimumSeparation(left, right) {
  const extent = (unit) => unit.mechanics.collision_size_tiles.x
    * (left.owner === right.owner ? unit.mechanics.min_collision_size_multiplier : 1);
  return extent(left) + extent(right);
}


function chebyshev(left, right) {
  return Math.max(Math.abs(right.x - left.x), Math.abs(right.y - left.y));
}


test("Champion 5v3 matches the authorized median outcome", () => {
  const result = runChampionRatio("5v3");

  assert.equal(result.winnerOwner, 2);
  // The three authorized 5v3 runs span 210-252 winner HP. The gate is that
  // band, not its median: pinning the median would be fitting the outcome, which
  // is exactly what this engine forbids.
  assert.ok(
    result.winnerHp >= 210 && result.winnerHp <= 252,
    `winner HP ${result.winnerHp} outside the authorized 5v3 band 210-252`,
  );
  assert.ok(new Set([4, 5]).has(result.livingUnits.length));
  assert.ok(result.damageEvents.length >= 22 && result.damageEvents.length <= 25);
});


test("Champion 5v3 crowding remains physical and lets every tape attacker participate", () => {
  const result = runChampionRatio("5v3");
  const expectedAttackers = new Set([1628, 1629, 1630, 1631, 1632, 1699, 1700, 1701]);
  const actualAttackers = new Set(result.damageEvents.map(({ actorId }) => actorId));
  const avoidanceSides = new Set();
  let alliedContactBlocked = false;

  for (let snapshotIndex = 0; snapshotIndex < result.snapshots.length; snapshotIndex += 1) {
    const snapshot = result.snapshots[snapshotIndex];
    for (let leftIndex = 0; leftIndex < snapshot.units.length; leftIndex += 1) {
      const left = snapshot.units[leftIndex];
      if (left.avoidance) avoidanceSides.add(left.avoidance.side);
      for (let rightIndex = leftIndex + 1; rightIndex < snapshot.units.length; rightIndex += 1) {
        const right = snapshot.units[rightIndex];
        if (!left.alive || !right.alive) continue;
        assert.ok(
          chebyshev(left, right) >= minimumSeparation(left, right) - EPSILON,
          `snapshot ${snapshot.tick} overlaps ${left.referenceId} and ${right.referenceId}`,
        );
      }
    }

    if (snapshotIndex === 0) continue;
    const previousById = new Map(
      result.snapshots[snapshotIndex - 1].units.map((unit) => [unit.referenceId, unit]),
    );
    for (const blocked of snapshot.events.filter(({ type }) => type === "blocked")) {
      const actor = previousById.get(blocked.actorId);
      const step = actor.mechanics.speed_tiles_per_second / 60;
      alliedContactBlocked ||= [...previousById.values()].some((unit) => (
        unit.alive
        && unit.referenceId !== actor.referenceId
        && unit.owner === actor.owner
        && Math.hypot(unit.x - actor.x, unit.y - actor.y)
          <= actor.mechanics.collision_size_tiles.x
            + unit.mechanics.collision_size_tiles.x
            + step
            + EPSILON
      ));
    }
  }

  assert.deepEqual([...avoidanceSides].sort(), [-1, 1]);
  assert.equal(alliedContactBlocked, true);
  assert.deepEqual([...actualAttackers].sort(), [...expectedAttackers].sort());
});


test("Champion 5v3 is invariant to reversing the scenario unit array", () => {
  const forward = runChampionRatio("5v3");
  const reversed = runChampionRatio("5v3", { reverseUnits: true });

  assert.equal(reversed.finalStateHash, forward.finalStateHash);
  assert.equal(reversed.eventLogHash, forward.eventLogHash);
});
