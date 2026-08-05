import assert from "node:assert/strict";
import test from "node:test";

import { surfaceGap } from "../src/combat/targeting.js";
import { runChampionRatio } from "./support/champion-ratio.mjs";


const EPSILON = 1e-12;


test("Champion 6v3 matches the authorized median outcome", () => {
  const result = runChampionRatio("6v3");

  assert.equal(result.winnerOwner, 2);
  assert.equal(result.winnerHp, 336);
  assert.ok(new Set([5, 6]).has(result.livingUnits.length));
  assert.ok(result.damageEvents.length >= 21 && result.damageEvents.length <= 23);
});


test("Champion 6v3 overflow attackers make explained progress without overlap", () => {
  const result = runChampionRatio("6v3");

  for (const snapshot of result.snapshots) {
    const living = snapshot.units.filter(({ alive }) => alive);
    const byReference = new Map(living.map((unit) => [unit.referenceId, unit]));
    for (let leftIndex = 0; leftIndex < living.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < living.length; rightIndex += 1) {
        assert.ok(
          surfaceGap(living[leftIndex], living[rightIndex]) >= -EPSILON,
          `tick ${snapshot.tick}: ${living[leftIndex].referenceId} overlaps ${living[rightIndex].referenceId}`,
        );
      }
    }

    if (snapshot.tick === 0) continue;
    for (const unit of living) {
      const visibleEnemy = living.some((candidate) => (
        candidate.owner !== unit.owner
        && Math.hypot(candidate.x - unit.x, candidate.y - unit.y)
          <= unit.mechanics.line_of_sight_tiles + EPSILON
      ));
      if (!visibleEnemy) continue;

      const pursuit = byReference.get(unit.pursuitTargetId);
      const engagement = byReference.get(unit.engagedTargetId);
      const blocker = byReference.get(unit.avoidance?.blockerReferenceId);
      const moved = snapshot.events.some(({ type, actorId }) => (
        type === "move" && actorId === unit.referenceId
      ));
      const blockedByNamedBody = Boolean(blocker) && snapshot.events.some(({ type, actorId }) => (
        type === "blocked" && actorId === unit.referenceId
      )) && blocker.referenceId !== unit.referenceId;
      const pursuing = pursuit?.alive && pursuit.owner !== unit.owner;
      const engaged = engagement?.alive && engagement.owner !== unit.owner;
      const winding = (
        unit.action === "attacking"
        && Number.isSafeInteger(unit.actionTimers.windup)
        && unit.actionTimers.windup > 0
      );
      const reloading = unit.action === "reload" || unit.actionTimers.reload > 0;

      assert.ok(
        pursuing || moved || blockedByNamedBody || engaged || winding || reloading,
        `tick ${snapshot.tick}: visible attacker ${unit.referenceId} is unexplained idle`,
      );
      if (unit.avoidance !== null) {
        assert.ok(
          blocker?.alive && blocker.owner === unit.owner,
          `tick ${snapshot.tick}: ${unit.referenceId} avoidance lacks a named live allied blocker`,
        );
      }
    }
  }
});


test("Champion 6v3 converges and is invariant to reversing the scenario unit array", () => {
  const forward = runChampionRatio("6v3");
  const reversed = runChampionRatio("6v3", { reverseUnits: true });

  assert.equal(reversed.finalStateHash, forward.finalStateHash);
  assert.equal(reversed.eventLogHash, forward.eventLogHash);
});
