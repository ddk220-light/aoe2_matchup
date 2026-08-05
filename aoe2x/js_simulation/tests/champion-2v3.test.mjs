import assert from "node:assert/strict";
import test from "node:test";

import { runChampionRatio } from "./support/champion-ratio.mjs";


test("Champion 2v3 matches the exact repeated tape outcome", () => {
  const result = runChampionRatio("2v3");

  assert.equal(result.winnerOwner, 3);
  assert.equal(result.winnerHp, 126);
  assert.equal(result.livingUnits.length, 2);
  assert.equal(result.damageEvents.length, 16);
});


test("Champion 2v3 retargets only after next-tick dead-target invalidation", () => {
  const result = runChampionRatio("2v3");
  const currentTargetByActor = new Map();
  const deathsByTarget = new Map();
  const invalidationsByActorAndTarget = new Map();
  let reacquisitionCount = 0;

  for (const event of result.events) {
    if (event.type === "death") {
      deathsByTarget.set(event.targetId, event);
      continue;
    }
    if (event.type === "target-invalidated") {
      const death = deathsByTarget.get(event.targetId);
      assert.ok(death, `target ${event.targetId} was invalidated before its death`);
      assert.equal(event.reason, "target-dead");
      assert.equal(event.tick, death.tick + 1);
      invalidationsByActorAndTarget.set(`${event.actorId}:${event.targetId}`, event);
      continue;
    }
    if (event.type !== "target-acquired") continue;

    const oldTargetId = currentTargetByActor.get(event.actorId);
    if (oldTargetId !== undefined) {
      const death = deathsByTarget.get(oldTargetId);
      const invalidation = invalidationsByActorAndTarget.get(
        `${event.actorId}:${oldTargetId}`,
      );
      assert.ok(death, `actor ${event.actorId} changed from a live target`);
      assert.ok(invalidation, `actor ${event.actorId} changed target without invalidation`);
      assert.equal(invalidation.tick, death.tick + 1);
      assert.equal(event.tick, invalidation.tick);
      reacquisitionCount += 1;
    }
    currentTargetByActor.set(event.actorId, event.targetId);
  }

  assert.ok(reacquisitionCount > 0);
});


test("Champion 2v3 never starts or commits an attack against a dead target", () => {
  const result = runChampionRatio("2v3");
  const alive = new Set(result.snapshots[0].units.map(({ referenceId }) => referenceId));

  for (const event of result.events) {
    if (event.type === "attack-start" || event.type === "damage") {
      assert.ok(alive.has(event.actorId), `dead actor ${event.actorId} attacked`);
      assert.ok(alive.has(event.targetId), `dead target ${event.targetId} was attacked`);
    } else if (event.type === "death") {
      assert.ok(alive.delete(event.targetId), `target ${event.targetId} died more than once`);
    }
  }
});


test("Champion 2v3 is invariant to reversing the scenario unit array", () => {
  const forward = runChampionRatio("2v3");
  const reversed = runChampionRatio("2v3", { reverseUnits: true });

  assert.equal(reversed.finalStateHash, forward.finalStateHash);
  assert.equal(reversed.eventLogHash, forward.eventLogHash);
});
