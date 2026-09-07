import assert from "node:assert/strict";
import test from "node:test";

import { createKiteState, DEFAULT_KITE_PROFILE } from "../src/combat/ai-orders.js";

test("kite state preserves only the supported cohort-motion policy", () => {
  const enabled = createKiteState(2, {
    beatTicks: 240,
    firstBeatTick: 240,
    moveOffsetTicks: [40, 120, 200],
    topupOffsetTicks: [],
    preMoveTicks: [80, 160],
    cohortMotion: "contact_heading",
  });
  const unsupported = createKiteState(2, {
    beatTicks: 240,
    firstBeatTick: 240,
    moveOffsetTicks: [40, 120, 200],
    topupOffsetTicks: [],
    preMoveTicks: [80, 160],
    cohortMotion: "teleport",
  });
  const defaulted = createKiteState(2);

  assert.equal(enabled.profile.cohortMotion, "contact_heading");
  assert.equal(unsupported.profile.cohortMotion, undefined);
  assert.equal(defaulted.profile, DEFAULT_KITE_PROFILE);
  assert.equal(defaulted.profile.cohortMotion, undefined);
});
