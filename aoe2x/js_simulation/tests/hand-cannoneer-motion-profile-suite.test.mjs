import assert from "node:assert/strict";
import test from "node:test";

import {
  evaluateFiveSampleGate,
  physicsCandidate,
} from "../tools/run_hand_cannoneer_motion_profile_suite.mjs";


function row(matchup, baselineBandError, candidateBandError, overrides = {}) {
  return {
    matchup,
    baseline: { bandError: baselineBandError },
    candidate: {
      bandError: candidateBandError,
      unresolvedRuns: 0,
      wrongStableWinner: false,
      ...overrides,
    },
  };
}


const PASSING_ROWS = Object.freeze([
  row("HC vs A", 20, 10),
  row("HC vs B", 5, 4),
]);


test("five-sample gate expands only a fully passing candidate", () => {
  const gate = evaluateFiveSampleGate(PASSING_ROWS, true);

  assert.equal(gate.expandVolatile, true);
  assert.equal(gate.baselineBandError, 25);
  assert.equal(gate.candidateBandError, 14);
  assert.equal(gate.improvement, 11);
  assert.deepEqual(gate.stableWinnerFailures, []);
  assert.deepEqual(gate.goodRowRegressions, []);
  assert.equal(gate.unresolvedRuns, 0);
});


test("five-sample gate rejects each acceptance failure", () => {
  assert.equal(evaluateFiveSampleGate(PASSING_ROWS, false).expandVolatile, false);
  assert.equal(evaluateFiveSampleGate([
    row("timeout", 20, 10, { unresolvedRuns: 1 }),
  ], true).expandVolatile, false);
  assert.equal(evaluateFiveSampleGate([
    row("wrong winner", 20, 10, { wrongStableWinner: true }),
  ], true).expandVolatile, false);
  assert.equal(evaluateFiveSampleGate([
    row("good-row regression", 5, 16),
    row("offsetting gain", 30, 1),
  ], true).expandVolatile, false);
  assert.equal(evaluateFiveSampleGate([
    row("aggregate regression", 20, 21),
  ], true).expandVolatile, false);
});


test("five-sample gate lists candidate rows more than 25 points out of band", () => {
  const gate = evaluateFiveSampleGate([
    row("inside", 30, 25),
    row("outside", 30, 25.001),
  ], true);

  assert.deepEqual(gate.over25, [{ matchup: "outside", delta: 25.001 }]);
});


test("physics candidates are fixed concepts rather than free outcome parameters", () => {
  assert.deepEqual(physicsCandidate("measured_spacing"), {
    name: "measured_spacing",
    label: "HC-only formation spacing 0.35 tiles",
    experiment: { formationSpacingTiles: 0.35 },
  });
  assert.deepEqual(physicsCandidate("translated_offsets"), {
    name: "translated_offsets",
    label: "HC-only rigid translation of existing formation offsets",
    experiment: { formationMotion: "translated_offsets" },
  });
  assert.deepEqual(physicsCandidate("opening_volley"), {
    name: "opening_volley",
    label: "HC-only opening attack on the first 0.667-second order clock",
    experiment: { firstBeatTick: 40 },
  });
  assert.deepEqual(physicsCandidate("translated_opening"), {
    name: "translated_opening",
    label: "HC-only rigid formation translation plus measured opening volley",
    experiment: { formationMotion: "translated_offsets", firstBeatTick: 40 },
  });
  assert.deepEqual(physicsCandidate("immediate_opening"), {
    name: "immediate_opening",
    label: "HC-only opening attack active from the first simulation tick",
    experiment: { firstBeatTick: 1 },
  });
  assert.deepEqual(physicsCandidate("translated_immediate"), {
    name: "translated_immediate",
    label: "HC-only rigid formation translation plus immediate opening attack",
    experiment: { formationMotion: "translated_offsets", firstBeatTick: 1 },
  });
  assert.deepEqual(physicsCandidate("closing_opening"), {
    name: "closing_opening",
    label: "HC-only immediate opening order that closes to firing range",
    experiment: { firstBeatTick: 1, openingVolley: "close_to_fire" },
  });
  assert.deepEqual(physicsCandidate("translated_closing"), {
    name: "translated_closing",
    label: "HC-only rigid formation translation plus closing opening volley",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      openingVolley: "close_to_fire",
    },
  });
  assert.deepEqual(physicsCandidate("persistent_volleys"), {
    name: "persistent_volleys",
    label: "HC-only immediate opening plus close-to-fire pursuit on every volley",
    experiment: { firstBeatTick: 1, volleyPursuit: "close_to_fire" },
  });
  assert.deepEqual(physicsCandidate("translated_persistent"), {
    name: "translated_persistent",
    label: "HC-only rigid translation plus persistent close-to-fire volleys",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
    },
  });
  assert.deepEqual(physicsCandidate("translated_persistent_escape"), {
    name: "translated_persistent_escape",
    label: "HC-only translated persistent volleys with contact escape steering",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      kitedEscape: true,
    },
  });
  assert.deepEqual(physicsCandidate("translated_persistent_capture"), {
    name: "translated_persistent_capture",
    label: "HC-only translated persistent volleys with contact target capture",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      chaseCapture: true,
    },
  });
  assert.deepEqual(physicsCandidate("translated_persistent_half_wave"), {
    name: "translated_persistent_half_wave",
    label: "HC-only translated persistent volleys with measured half-roster melee wave",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      meleeWave: "half_roster",
    },
  });
  assert.deepEqual(physicsCandidate("translated_persistent_locations"), {
    name: "translated_persistent_locations",
    label: "HC-only translated persistent volleys with tape-location melee approach",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      meleeWave: "location_approach",
    },
  });
  assert.deepEqual(physicsCandidate("translated_persistent_measured_phase"), {
    name: "translated_persistent_measured_phase",
    label: "HC-only translated persistent volleys on the measured 0.2/1.33-second phase",
    experiment: {
      formationMotion: "translated_offsets",
      firstBeatTick: 12,
      moveOffsetTicks: [68, 148, 228],
      volleyPursuit: "close_to_fire",
    },
  });
  assert.throws(() => physicsCandidate("spacing_0.36"), /unknown HC physics candidate/);
});
