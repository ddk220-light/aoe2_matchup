import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


const REFERENCE_DB_SHA256 = "51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087";
const DAT_SHA256 = "CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF";

const BATCH_1 = Object.freeze([
  ["elite_longbowman_britons", "Britons", 530],
  ["elite_throwing_axeman_franks", "Franks", 531],
  ["elite_woad_raider_celts", "Celts", 534],
  ["elite_shotel_warrior_ethiopians", "Ethiopians", 1018],
  ["elite_gbeto_malians", "Malians", 1015],
  ["elite_huskarl_goths", "Goths", 555],
  ["elite_teutonic_knight_teutons", "Teutons", 554],
  ["elite_boyar_slavs", "Slavs", 878],
  ["elite_tarkan_huns", "Huns", 757],
  ["elite_genoese_crossbowman_italians", "Italians", 868],
  ["elite_plumed_archer_mayans", "Mayans", 765],
  ["elite_mangudai_mongols", "Mongols", 561],
  ["elite_rattan_archer_vietnamese", "Vietnamese", 1131],
  ["elite_janissary_turks", "Turks", 557],
  ["elite_conquistador_spanish", "Spanish", 773],
  ["elite_war_wagon_koreans", "Koreans", 829],
  ["elite_magyar_huszar_magyars", "Magyars", 871],
  ["elite_keshik_tatars", "Tatars", 1230],
  ["elite_karambit_warrior_malay", "Malay", 1125],
  ["warrior_priest_armenians", "Armenians", 1811],
]);

async function fixture(slug) {
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${slug}_imperial.json`, import.meta.url),
    "utf8",
  ));
}

test("Batch 1 has twenty source-backed Imperial mechanics fixtures", async () => {
  assert.equal(BATCH_1.length, 20);
  for (const [slug, civilization, master] of BATCH_1) {
    const mechanics = await fixture(slug);
    assert.equal(mechanics.unit_master, master, `${slug} master`);
    assert.equal(mechanics.civilization, civilization, `${slug} civilization`);
    assert.equal(mechanics.age, "Imperial", `${slug} age`);
    assert.equal(
      mechanics.provenance.reference_db_sha256,
      REFERENCE_DB_SHA256,
      `${slug} reference DB`,
    );
    assert.equal(mechanics.provenance.dat_sha256, DAT_SHA256, `${slug} Genie dat`);
  }
});

test("ranged infantry keeps mobile projectile mechanics and melee damage classes", async () => {
  for (const slug of ["elite_throwing_axeman_franks", "elite_gbeto_malians"]) {
    const mechanics = await fixture(slug);
    assert.ok(mechanics.ranged, `${slug} projectile block`);
    assert.ok(mechanics.attack_classes["4"] > 0, `${slug} melee-class attack`);
    assert.equal(mechanics.attack_classes["3"], undefined, `${slug} no pierce base attack`);
  }
});

test("Batch 1 records sourced accuracy, population, and Royal Heirs semantics", async () => {
  const longbow = await fixture("elite_longbowman_britons");
  const janissary = await fixture("elite_janissary_turks");
  const conquistador = await fixture("elite_conquistador_spanish");
  const karambit = await fixture("elite_karambit_warrior_malay");
  const shotel = await fixture("elite_shotel_warrior_ethiopians");

  assert.equal(longbow.ranged.accuracy_percent, 80);
  assert.equal(janissary.ranged.accuracy_percent, 65);
  assert.equal(conquistador.ranged.accuracy_percent, 70);
  assert.equal(karambit.population_space, 0.5);
  assert.deepEqual(shotel.damage_reduction_by_attacker_category, { mounted: 3 });
});

test("Warrior Priest fixture is combat-only", async () => {
  const priest = await fixture("warrior_priest_armenians");
  assert.equal(priest.attack_range_tiles, 0);
  assert.equal(priest.healing, undefined);
  assert.equal(priest.heal_rate, undefined);
  assert.equal(priest.heal_range, undefined);
});
