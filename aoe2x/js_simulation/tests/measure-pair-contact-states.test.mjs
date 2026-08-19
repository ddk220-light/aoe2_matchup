import assert from "node:assert/strict";
import test from "node:test";

import {
  PHASE2_ARCHIVE,
  normalizeTapeFrames,
  renderPairContactMarkdown,
  validateAnalysisSource,
} from "../tools/measure_pair_contact_states.mjs";

test("pair contact reports require the authorized Phase 2 archive hash", () => {
  assert.throws(() => validateAnalysisSource({
    name: "wrong.zip",
    zip_sha256: "00",
  }), /authorized Phase 2 archive/);
  assert.throws(() => validateAnalysisSource({
    name: PHASE2_ARCHIVE.name,
    zip_sha256: "00",
  }), /authorized Phase 2 archive/);
  assert.doesNotThrow(() => validateAnalysisSource({
    name: PHASE2_ARCHIVE.name,
    zip_sha256: PHASE2_ARCHIVE.zipSha256,
  }));
});

test("tape normalization derives sampled movement and preserves decoded combat state", () => {
  const mechanicsByMaster = new Map([[10, {
    collision_size_tiles: { x: 0.2, y: 0.25 },
    min_collision_size_multiplier: 0.5,
  }]]);
  const rawFrames = [
    { timeMs: 0, units: [{ id: 1, owner: 2, master: 10, x: 1, y: 2, hp: 20 }] },
    { timeMs: 100, units: [{
      id: 1, owner: 2, master: 10, x: 1.1, y: 2, hp: 20,
      action_state: 7, target_id: 2,
    }] },
    { timeMs: 200, units: [{
      id: 1, owner: 2, master: 10, x: 1.1, y: 2, hp: 20,
      action_state: 6, target_id: 2,
    }] },
  ];

  const normalized = normalizeTapeFrames(rawFrames, mechanicsByMaster, { cadenceMs: 100 });

  assert.equal(normalized[0].units[0].moving, false);
  assert.equal(normalized[1].units[0].moving, true);
  assert.equal(normalized[1].units[0].attacking, true);
  assert.equal(normalized[1].units[0].attackTargetId, 2);
  assert.equal(normalized[1].units[0].radius, 0.25);
  assert.equal(normalized[1].units[0].minCollisionMultiplier, 0.5);
  assert.equal(normalized[2].units[0].moving, false);
});

test("markdown exposes relationship, motion, attack, intent, phase, depth, and graph metrics", () => {
  const populationKey = "enemies|both-moving|one-attacking|direct-target|persisting";
  const metrics = {
    pairFrames: 10,
    overlapPairs: 2,
    overlapPairShare: 0.2,
    p05Depth: 0.02,
    medianDepth: 0.05,
    p95Depth: 0.09,
    contactWindowMs: { median: 300 },
    maximumLocalDegree: 2,
    maximumComponentSize: 3,
    maximumTriangles: 1,
    maximumFourCliques: 0,
  };
  const markdown = renderPairContactMarkdown({
    source: {
      name: PHASE2_ARCHIVE.name,
      zipSha256: PHASE2_ARCHIVE.zipSha256,
    },
    sampling: { cadenceMs: 100, samples: 1, seed: 7 },
    rows: [{
      id: "row",
      matchup: "Left vs Right",
      tape: { runs: [{ label: "tape-1", metrics: {
        populations: { [populationKey]: metrics },
        relationships: {},
      } }] },
      simulation: { runs: [] },
    }],
  });

  assert.match(markdown, /both-moving/);
  assert.match(markdown, /one-attacking/);
  assert.match(markdown, /direct-target/);
  assert.match(markdown, /persisting/);
  assert.match(markdown, /p05 depth/i);
  assert.match(markdown, /local degree/i);
  assert.match(markdown, /triangle/i);
});
