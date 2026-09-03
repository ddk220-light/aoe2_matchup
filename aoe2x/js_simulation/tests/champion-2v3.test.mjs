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


test("Champion 2v3 changes pursuit only after next-tick dead-target invalidation", () => {
  const result = runChampionRatio("2v3");
  const deathsByTarget = new Map(
    result.events
      .filter(({ type }) => type === "death")
      .map((event) => [event.targetId, event]),
  );
  let liveTargetChangeCount = 0;

  for (let tick = 1; tick < result.snapshots.length; tick += 1) {
    const previous = result.snapshots[tick - 1];
    const current = result.snapshots[tick];
    const previousById = new Map(previous.units.map((unit) => [unit.referenceId, unit]));
    const currentById = new Map(current.units.map((unit) => [unit.referenceId, unit]));

    for (const unit of current.units) {
      const before = previousById.get(unit.referenceId);
      if (before.pursuitTargetId === unit.pursuitTargetId) continue;

      const matchingEvents = current.events.filter(({ actorId }) => actorId === unit.referenceId);
      if (before.pursuitTargetId === null) {
        assert.deepEqual(
          matchingEvents
            .filter(({ type }) => type === "pursuit-acquired")
            .map(({ targetId }) => targetId),
          [unit.pursuitTargetId],
        );
      } else if (!unit.alive) {
        assert.ok(current.events.some(({ type, targetId }) => (
          type === "death" && targetId === unit.referenceId
        )));
        assert.equal(unit.pursuitTargetId, null);
      } else {
        const death = deathsByTarget.get(before.pursuitTargetId);
        const invalidationIndex = current.events.findIndex((event) => (
          event.type === "pursuit-invalidated"
          && event.actorId === unit.referenceId
          && event.targetId === before.pursuitTargetId
        ));
        const acquisitionIndex = current.events.findIndex((event) => (
          event.type === "pursuit-acquired"
          && event.actorId === unit.referenceId
          && event.targetId === unit.pursuitTargetId
        ));
        assert.ok(
          death,
          `pursuit target ${before.pursuitTargetId} changed without a preceding death`,
        );
        assert.equal(current.tick, death.tick + 1);
        assert.ok(invalidationIndex >= 0, `actor ${unit.referenceId} changed without invalidation`);
        assert.ok(acquisitionIndex > invalidationIndex, "acquisition must follow invalidation");
        assert.equal(current.events[invalidationIndex].reason, "target-dead");
        liveTargetChangeCount += 1;
      }
    }

    for (const blocked of current.events.filter(({ type }) => type === "blocked")) {
      const actorBefore = previousById.get(blocked.actorId);
      const actorAfter = currentById.get(blocked.actorId);
      const targetBefore = previousById.get(actorBefore.pursuitTargetId);
      const targetAfter = currentById.get(actorBefore.pursuitTargetId);
      if (actorBefore.alive && actorAfter.alive && targetBefore?.alive && targetAfter?.alive) {
        assert.equal(
          actorAfter.pursuitTargetId,
          actorBefore.pursuitTargetId,
          `blocked actor ${blocked.actorId} released a live pursuit target`,
        );
      }
    }
  }

  assert.ok(liveTargetChangeCount > 0);
});


test("Champion 2v3 never starts or commits an attack against a dead target", () => {
  const result = runChampionRatio("2v3");
  const deathByUnit = new Map();

  for (let tick = 1; tick < result.snapshots.length; tick += 1) {
    const previous = result.snapshots[tick - 1];
    const current = result.snapshots[tick];
    const previousById = new Map(previous.units.map((unit) => [unit.referenceId, unit]));
    const currentById = new Map(current.units.map((unit) => [unit.referenceId, unit]));
    const aliveDuringCommit = new Set(
      previous.units.filter(({ alive }) => alive).map(({ referenceId }) => referenceId),
    );

    for (const event of current.events) {
      if (event.type === "attack-start" || event.type === "damage") {
        assert.ok(aliveDuringCommit.has(event.actorId), `dead actor ${event.actorId} attacked`);
        assert.ok(aliveDuringCommit.has(event.targetId), `dead target ${event.targetId} was attacked`);
      } else if (event.type === "death") {
        assert.ok(
          aliveDuringCommit.delete(event.targetId),
          `target ${event.targetId} died more than once`,
        );
        assert.equal(currentById.get(event.targetId).alive, false);
        deathByUnit.set(event.targetId, event);
      }
    }

    for (const unit of current.units) {
      if (unit.alive) continue;
      const death = deathByUnit.get(unit.referenceId);
      assert.ok(death, `dead snapshot unit ${unit.referenceId} has no death event`);
      assert.ok(death.tick <= current.tick);
      if (previousById.get(unit.referenceId).alive) {
        assert.equal(death.tick, current.tick);
      }
    }
  }
});


test("Champion 2v3 is invariant to reversing the scenario unit array", () => {
  const forward = runChampionRatio("2v3");
  const reversed = runChampionRatio("2v3", { reverseUnits: true });

  assert.equal(reversed.finalStateHash, forward.finalStateHash);
  assert.equal(reversed.eventLogHash, forward.eventLogHash);
});
