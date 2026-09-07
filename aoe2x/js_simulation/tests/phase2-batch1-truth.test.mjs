import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


const truth = JSON.parse(await readFile(
  new URL("../calibration/fixtures/phase2/batch1_truth.json", import.meta.url),
  "utf8",
));

const EXPECTED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const BATCH1_SLUGS = Object.freeze([
  "elite_longbowman",
  "elite_throwing_axeman",
  "elite_woad_raider",
  "elite_shotel_warrior",
  "elite_gbeto",
  "elite_huskarl",
  "elite_teutonic_knight",
  "elite_boyar",
  "elite_tarkan",
  "elite_genoese_crossbowman",
  "elite_plumed_archer",
  "elite_mangudai",
  "elite_rattan_archer",
  "elite_janissary",
  "elite_conquistador",
  "elite_war_wagon",
  "elite_magyar_huszar",
  "elite_keshik",
  "elite_karambit_warrior",
  "warrior_priest",
]);
const OPPONENT_SLUGS = Object.freeze([
  "arbalester",
  "champion",
  "elite_elephant",
  "heavy_cav_archer",
  "heavy_scorpion",
  "paladin",
]);


test("Phase 2 Batch 1 truth is locked to the authorized golden archive", () => {
  assert.equal(truth.schema_version, 1);
  assert.deepEqual(truth.archive, {
    name: "aoe2_golden_phase2_WITH_TAPES.zip",
    path: "aoe2x/js_simulation/calibration/source/aoe2_golden_phase2_WITH_TAPES.zip",
    zip_sha256: EXPECTED_SHA256,
  });
  assert.equal(truth.batch, 1);
  assert.equal(truth.rows.length, 120);
  assert.equal(truth.rows.reduce((total, row) => total + row.runs.length, 0), 288);
});


test("every Batch 1 unit has exactly the six recorded standard opponents", () => {
  assert.deepEqual(truth.unit_slugs, BATCH1_SLUGS);
  for (const slug of BATCH1_SLUGS) {
    const rows = truth.rows.filter(({ subject_slug: subjectSlug }) => subjectSlug === slug);
    assert.equal(rows.length, 6, slug);
    assert.deepEqual(rows.map(({ opponent_slug: opponentSlug }) => opponentSlug).sort(), [...OPPONENT_SLUGS].sort(), slug);
    for (const row of rows) {
      assert.deepEqual(
        new Set([row.side2.slug, row.side3.slug]),
        new Set([row.subject_slug, row.opponent_slug]),
        row.id,
      );
    }
  }
});


test("each tape run preserves raw provenance, exact starts, and a scored outcome", () => {
  for (const row of truth.rows) {
    assert.equal(row.side2.owner, 2, row.id);
    assert.equal(row.side3.owner, 3, row.id);
    for (const run of row.runs) {
      assert.match(run.source_members.frames, /^phase2\/raw recordings\/.+\.frames\.bin$/);
      assert.match(run.source_members.summary, /^phase2\/decoded\/.+\.summary\.json$/);
      assert.match(run.source_members.units, /^phase2\/decoded\/.+\.units\.jsonl\.gz$/);
      assert.equal(run.status, "scored", run.tag);
      assert.ok(run.winner_owner === 2 || run.winner_owner === 3, run.tag);
      assert.ok(Number.isFinite(run.signed_score) && run.signed_score !== 0, run.tag);
      assert.equal(
        run.starting_units.filter(({ owner }) => owner === 2).length,
        row.side2.count,
        run.tag,
      );
      assert.equal(
        run.starting_units.filter(({ owner }) => owner === 3).length,
        row.side3.count,
        run.tag,
      );
    }
  }
});
