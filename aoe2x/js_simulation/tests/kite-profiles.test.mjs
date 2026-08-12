import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { DEFAULT_KITE_PROFILE } from "../src/combat/ai-orders.js";
import { runFight } from "../src/fight.js";
import { KITE_PROFILES, KITE_PROFILE_PROVENANCE } from "../src/kite-profiles.js";
import { UNIT_REGISTRY } from "../src/unit-registry.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");
const fixtureDir = path.resolve(here, "..", "calibration", "fixtures");

// The truth fixtures themselves, read here and NOWHERE on the request path --
// the generated table is what /api/fight consults. This is the check that the
// generated table still says what the tapes say.
const truths = [];
for (const name of (await readdir(fixtureDir)).filter((n) => n.endsWith(".json"))) {
  const value = JSON.parse(await readFile(path.join(fixtureDir, name), "utf8"));
  if (value && typeof value === "object" && Number.isInteger(value.kiteOwner)) {
    truths.push({ name, truth: value });
  }
}

const slugByFixtureStem = new Map(
  UNIT_REGISTRY.map(({ slug, fixture }) => [fixture.replace(/\.json$/, ""), slug]));


test("the archive still has kiting fixtures to check against", () => {
  assert.ok(truths.length >= 12, `only ${truths.length} kiting fixtures found`);
  assert.equal(truths.length, KITE_PROFILE_PROVENANCE.kitingFixtures);
});


test("the generated table reproduces the measured profile of every kiter "
  + "that has a tape column", () => {
  let checked = 0;
  for (const { name, truth } of truths) {
    if (!truth.kiteProfile) continue;
    const slug = slugByFixtureStem.get(truth.sides[String(truth.kiteOwner)]);
    assert.ok(slug, `${name}: no registry row for ${truth.sides[String(truth.kiteOwner)]}`);
    const generated = KITE_PROFILES[slug];
    assert.ok(generated, `${name}: no generated profile for ${slug}`);
    assert.equal(generated.beatTicks, truth.kiteProfile.beatTicks, `${name} beatTicks`);
    assert.equal(generated.firstBeatTick, truth.kiteProfile.firstBeatTick, `${name} firstBeatTick`);
    assert.deepEqual([...generated.moveOffsetTicks],
      [...truth.kiteProfile.moveOffsetTicks], `${name} moveOffsetTicks`);
    assert.deepEqual([...generated.topupOffsetTicks],
      [...(truth.kiteProfile.topupOffsetTicks ?? [])], `${name} topupOffsetTicks`);
    assert.deepEqual([...generated.preMoveTicks],
      [...(truth.kiteProfile.preMoveTicks ?? [])], `${name} preMoveTicks`);
    checked += 1;
  }
  assert.equal(checked, 12, "every kiting fixture with a recorded profile must be checked");
  // Three distinct kiters carry a tape column; a fourth (hand_cannoneer) does
  // not, and is flagged constructed below.
  const measured = Object.entries(KITE_PROFILE_PROVENANCE.profiles)
    .filter(([, row]) => row.source === "tape").map(([slug]) => slug);
  assert.deepEqual(measured.sort(), ["arbalester", "heavy_cav_archer", "imp_elite_skirm"]);
});


test("the engine default IS the arbalester's cadence, which is why the other "
  + "three kiters were running on the wrong one", () => {
  // Finding 1 in one assertion. The fixtures that omit kiteProfile ran on
  // DEFAULT_KITE_PROFILE; the generated arbalester row has to equal it or
  // "those fixtures are arbalester fights on the default" is not true.
  assert.deepEqual({
    beatTicks: KITE_PROFILES.arbalester.beatTicks,
    firstBeatTick: KITE_PROFILES.arbalester.firstBeatTick,
    moveOffsetTicks: [...KITE_PROFILES.arbalester.moveOffsetTicks],
    topupOffsetTicks: [...KITE_PROFILES.arbalester.topupOffsetTicks],
    preMoveTicks: [...KITE_PROFILES.arbalester.preMoveTicks],
  }, {
    beatTicks: DEFAULT_KITE_PROFILE.beatTicks,
    firstBeatTick: DEFAULT_KITE_PROFILE.firstBeatTick,
    moveOffsetTicks: [...DEFAULT_KITE_PROFILE.moveOffsetTicks],
    topupOffsetTicks: [...DEFAULT_KITE_PROFILE.topupOffsetTicks],
    preMoveTicks: [...DEFAULT_KITE_PROFILE.preMoveTicks],
  });
  for (const slug of ["imp_elite_skirm", "heavy_cav_archer", "hand_cannoneer"]) {
    assert.notDeepEqual(
      [KITE_PROFILES[slug].beatTicks, KITE_PROFILES[slug].firstBeatTick,
        [...KITE_PROFILES[slug].moveOffsetTicks]],
      [DEFAULT_KITE_PROFILE.beatTicks, DEFAULT_KITE_PROFILE.firstBeatTick,
        [...DEFAULT_KITE_PROFILE.moveOffsetTicks]],
      `${slug} is indistinguishable from the default; the fix would be a no-op for it`);
  }
});


test("the three measured profiles are genuinely different from each other", () => {
  // The bug this table exists to fix was every kiter silently running the
  // arbalester's cadence, so "they all agree" would be a false pass.
  const shapes = new Set(["arbalester", "heavy_cav_archer", "imp_elite_skirm"]
    .map((slug) => JSON.stringify(KITE_PROFILES[slug])));
  assert.equal(shapes.size, 3);
});


test("every mobile-ranged unit in the registry has a profile", () => {
  for (const { slug, class: unitClass } of UNIT_REGISTRY) {
    if (unitClass !== "mobile_ranged") continue;
    assert.ok(KITE_PROFILES[slug], `${slug} kites but has no generated profile`);
    assert.ok(KITE_PROFILE_PROVENANCE.profiles[slug], `${slug} has no provenance row`);
  }
  // Nothing that cannot kite should have one.
  const kiters = new Set(UNIT_REGISTRY
    .filter(({ class: unitClass }) => unitClass === "mobile_ranged").map(({ slug }) => slug));
  for (const slug of Object.keys(KITE_PROFILES)) {
    assert.ok(kiters.has(slug), `${slug} has a kite profile but is not mobile_ranged`);
  }
});


test("hand_cannoneer is sourced from the authorized standard-unit streams", () => {
  const row = KITE_PROFILE_PROVENANCE.profiles.hand_cannoneer;
  assert.equal(row.source, "standard-units-tape");
  assert.equal(row.zipSha256,
    "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D");
  assert.equal(row.streamsMeasured, 34);
  assert.equal(row.acceptanceReport,
    "calibration/reports/hand_cannoneer_translated_persistent_measured_phase_results_2026-08-09.json");
  assert.equal(KITE_PROFILES.hand_cannoneer.beatTicks, 240);
  assert.equal(KITE_PROFILES.hand_cannoneer.firstBeatTick, 12);
  assert.deepEqual([...KITE_PROFILES.hand_cannoneer.moveOffsetTicks], [68, 148, 228]);
  assert.deepEqual([...KITE_PROFILES.hand_cannoneer.preMoveTicks], []);
  assert.equal(KITE_PROFILES.hand_cannoneer.formationMotion, "translated_offsets");
  assert.equal(KITE_PROFILES.hand_cannoneer.volleyPursuit, "close_to_fire");
  assert.equal(KITE_PROFILES.hand_cannoneer.kitedEscape, undefined,
    "the measured HCA-style control failed its acceptance gate and must stay disabled");
  assert.equal(KITE_PROFILES.hand_cannoneer.kitedPath, undefined);
  assert.equal(KITE_PROFILES.hand_cannoneer.cohortMotion, undefined,
    "the cohort-motion screen failed and must stay off the product profile");
  for (const [slug, profile] of Object.entries(KITE_PROFILES)) {
    if (slug === "hand_cannoneer") continue;
    assert.equal(profile.kitedEscape, undefined,
      `${slug} must retain its existing profile-selected escape behavior`);
    assert.equal(profile.kitedPath, undefined,
      `${slug} must retain its existing movement path`);
    assert.equal(profile.cohortMotion, undefined,
      `${slug} must retain its existing cohort movement behavior`);
  }
  assert.ok(!truths.some(({ truth }) => (
    slugByFixtureStem.get(truth.sides[String(truth.kiteOwner)]) === "hand_cannoneer")),
  "the legacy fixture directory unexpectedly gained a duplicate HC tape column");
});


test("the constructed beat rule still reproduces every measured beat", () => {
  // If it stops holding, the constructed row rests on a rule the tapes
  // contradict; the generator refuses to emit in that case and so does this.
  assert.equal(KITE_PROFILE_PROVENANCE.beatRuleChecks.length, 3);
  for (const check of KITE_PROFILE_PROVENANCE.beatRuleChecks) {
    assert.equal(check.agrees, true,
      `${check.slug}: reload ${check.reloadSeconds}s predicts ${check.predictedBeatTicks} `
      + `but the tape measured ${check.measuredBeatTicks}`);
    assert.equal(check.predictedBeatTicks, KITE_PROFILES[check.slug].beatTicks);
  }
});


// The whole point of Finding 1: a fight must run on the KITER's cadence. The
// kite-move order ticks are the cadence made observable -- pre-fight moves,
// then one set of moves per beat at the profile's offsets.
function kiteMoveTicks(fight) {
  const ticks = new Set();
  for (const snapshot of fight.snapshots) {
    for (const entry of snapshot.events) {
      if (entry.type === "kite-move") ticks.add(entry.tick);
    }
  }
  return [...ticks].sort((a, b) => a - b);
}


for (const slug of ["arbalester", "imp_elite_skirm", "heavy_cav_archer", "hand_cannoneer"]) {
  test(`a ${slug} fight runs on the ${slug} cadence, not the default`, async () => {
    const fight = await runFight(root, {
      side2Slug: slug, n2: 15, side3Slug: "champion", n3: 21,
    });
    assert.equal(fight.family, "kite");
    assert.equal(fight.kiteOwner, 2);
    const profile = KITE_PROFILES[slug];
    const expected = [...profile.preMoveTicks];
    for (let beat = 0; beat < 3; beat += 1) {
      for (const offset of profile.moveOffsetTicks) {
        expected.push(profile.firstBeatTick + beat * profile.beatTicks + offset);
      }
    }
    expected.sort((a, b) => a - b);
    assert.deepEqual(kiteMoveTicks(fight).slice(0, expected.length), expected);
  });
}
