import { readFile } from "node:fs/promises";


const MATCHUPS = [
  ["arbalester", "champion", "arbalester_vs_champion_kiting_basics.json", "aoe2_golden_kiting_arbalestervschampion_2026-08-06.zip"],
  ["arbalester", "elite_elephant", "arbalester_vs_elephant_kiting_basics.json", "aoe2_golden_kiting_arbalestervselephant_2026-08-06.zip"],
  ["arbalester", "elite_fire_lancer", "arbalester_vs_firelancer_kiting_basics.json", "aoe2_golden_kiting_arbalestervsfirelancer_2026-08-06.zip"],
  ["arbalester", "paladin", "arbalester_vs_paladin_kiting_basics.json", "aoe2_golden_kiting_arbalestervspaladin_2026-08-06.zip"],
  ["arbalester", "elite_steppe", "arbalester_vs_steppe_kiting_basics.json", "aoe2_golden_kiting_arbalestervssteppe_2026-08-06.zip"],
  ["imp_elite_skirm", "champion", "eliteskirm_vs_champion_kiting_basics.json", "aoe2_golden_kiting_eliteskirmvschampion_2026-08-06.zip"],
  ["imp_elite_skirm", "elite_elephant", "eliteskirm_vs_elephant_kiting_basics.json", "aoe2_golden_kiting_eliteskirmvselephant_2026-08-06.zip"],
  ["imp_elite_skirm", "elite_fire_lancer", "eliteskirm_vs_firelancer_kiting_basics.json", "aoe2_golden_kiting_eliteskirmvsfirelancer_2026-08-06.zip"],
  ["imp_elite_skirm", "paladin", "eliteskirm_vs_paladin_kiting_basics.json", "aoe2_golden_kiting_eliteskirmvspaladin_2026-08-06.zip"],
  ["imp_elite_skirm", "elite_steppe", "eliteskirm_vs_steppe_kiting_basics.json", "aoe2_golden_kiting_eliteskirmvssteppe_2026-08-06.zip"],
  ["heavy_cav_archer", "champion", "hcavarcher_vs_champion_kiting_basics.json", "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip"],
  ["heavy_cav_archer", "elite_elephant", "hcavarcher_vs_elephant_kiting_basics.json", "aoe2_golden_kiting_hcavarchervselephant_2026-08-06.zip"],
  ["heavy_cav_archer", "elite_fire_lancer", "hcavarcher_vs_firelancer_kiting_basics.json", "aoe2_golden_kiting_hcavarchervsfirelancer_2026-08-06.zip"],
  ["heavy_cav_archer", "paladin", "hcavarcher_vs_paladin_kiting_basics.json", "aoe2_golden_kiting_hcavarchervspaladin_2026-08-06.zip"],
  ["heavy_cav_archer", "elite_steppe", "hcavarcher_vs_steppe_kiting_basics.json", "aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip"],
  ["heavy_scorpion", "champion", "scorpion_vs_champion_basics.json", "aoe2_golden_ranged_scorpionvschampion_2026-08-05.zip"],
  ["heavy_scorpion", "paladin", "scorpion_vs_paladin_basics.json", "aoe2_golden_ranged_scorpionvspaladin_2026-08-05.zip"],
];


export const DEDICATED_GOLDEN_MATCHUPS = Object.freeze(MATCHUPS.map(([
  rangedSlug, meleeSlug, fixture, archive,
]) => Object.freeze({
  id: `${rangedSlug}_vs_${meleeSlug}`,
  rangedSlug,
  meleeSlug,
  fixture,
  archive,
})));


export async function loadDedicatedGoldenCorpus(root) {
  const [manifest, truth] = await Promise.all([
    readFile(
      new URL("calibration/source/dedicated_ranged_melee_sources.json", root),
      "utf8",
    ).then(JSON.parse),
    readFile(
      new URL(
        "calibration/fixtures/dedicated_ranged_melee/dedicated_ranged_melee_truth.json",
        root,
      ),
      "utf8",
    ).then(JSON.parse),
  ]);
  const manifestByArchive = new Map(manifest.archives.map((entry) => [entry.archive, entry]));
  const truthById = new Map(truth.matchups.map((matchup) => [matchup.id, matchup]));
  const matchups = [];
  const rows = [];
  const runs = [];

  for (const expected of DEDICATED_GOLDEN_MATCHUPS) {
    const source = manifestByArchive.get(expected.archive);
    if (!source?.authorized) throw new RangeError(`archive is not authorized: ${expected.archive}`);
    if (!/^[A-F0-9]{64}$/.test(source.zip_sha256)) {
      throw new RangeError(`invalid manifest SHA-256: ${expected.archive}`);
    }
    const fixture = truthById.get(expected.id);
    if (!fixture || fixture.archive !== expected.archive) {
      throw new RangeError(`truth archive mismatch: ${expected.id}`);
    }
    if (fixture.zip_sha256 !== source.zip_sha256) {
      throw new RangeError(`fixture/manifest SHA-256 mismatch: ${expected.fixture}`);
    }
    const ratioRows = fixture.ratios.map((value) => Object.freeze({
      id: `${expected.id}_${value.ratio}`,
      ratio: value.ratio,
      matchupId: expected.id,
      rangedSlug: expected.rangedSlug,
      meleeSlug: expected.meleeSlug,
      archive: expected.archive,
      zipSha256: fixture.zip_sha256,
      side2: fixture.side2,
      side3: fixture.side3,
      runs: Object.freeze(value.runs.map((run) => Object.freeze({ ...run }))),
    }));
    for (const row of ratioRows) {
      if (row.runs.length !== 5) throw new RangeError(`expected five repeats: ${row.id}`);
      rows.push(row);
      runs.push(...row.runs.map((run) => Object.freeze({ ...run, rowId: row.id })));
    }
    matchups.push(Object.freeze({
      ...expected,
      zipSha256: fixture.zip_sha256,
      manifestZipSha256: source.zip_sha256,
      ratios: Object.freeze(ratioRows),
      runs: Object.freeze(ratioRows.flatMap(({ runs: ratioRuns }) => ratioRuns)),
    }));
  }

  if (
    manifestByArchive.size !== DEDICATED_GOLDEN_MATCHUPS.length
    || truthById.size !== DEDICATED_GOLDEN_MATCHUPS.length
  ) {
    throw new RangeError("dedicated manifest contains an unexpected archive set");
  }
  return Object.freeze({
    manifest: Object.freeze(manifest),
    matchups: Object.freeze(matchups),
    rows: Object.freeze(rows),
    runs: Object.freeze(runs),
  });
}
