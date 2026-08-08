// The units this simulator can run: one row per tape-measured mechanics
// fixture. `class` drives two things -- which side kites, and how far apart the
// two armies start (see placement.resolveFamily).
//
// baseCost is ref_units.base_cost_* from data/golden/aoe2_reference.db, the
// same database the website serves. It is deliberately the BASE column, not
// final_cost_*: the purchase rule buys at dat base prices, so a Berbers Hussar
// costs 80 here even though the civ bonus makes it 64 in game. Regenerate the
// numbers with tools/export_unit_costs.py.
const ROWS = [
  { slug: "arbalester", label: "Arbalester", civ: "Chinese", master: 492,
    fixture: "arbalester_chinese_imperial.json", class: "mobile_ranged",
    baseCost: { food: 0, wood: 25, gold: 45 } },
  { slug: "champion", label: "Champion", civ: "Chinese", master: 567,
    fixture: "champion_chinese_imperial.json", class: "melee",
    baseCost: { food: 50, wood: 0, gold: 20 } },
  { slug: "elite_elephant", label: "Elite Battle Elephant", civ: "Burmese", master: 1134,
    fixture: "elite_battle_elephant_burmese_imperial.json", class: "melee",
    baseCost: { food: 100, wood: 0, gold: 70 } },
  { slug: "elite_fire_lancer", label: "Elite Fire Lancer", civ: "Chinese", master: 1903,
    fixture: "elite_fire_lancer_chinese_imperial.json", class: "melee",
    baseCost: { food: 0, wood: 45, gold: 45 } },
  { slug: "elite_steppe", label: "Elite Steppe Lancer", civ: "Cumans", master: 1372,
    fixture: "elite_steppe_lancer_cumans_imperial.json", class: "melee",
    baseCost: { food: 70, wood: 0, gold: 40 } },
  { slug: "halberdier", label: "Halberdier", civ: "Bulgarians", master: 359,
    fixture: "halberdier_bulgarians_imperial.json", class: "melee",
    baseCost: { food: 35, wood: 25, gold: 0 } },
  { slug: "hand_cannoneer", label: "Hand Cannoneer", civ: "Bohemians", master: 5,
    fixture: "hand_cannoneer_bohemians_imperial.json", class: "mobile_ranged",
    baseCost: { food: 45, wood: 0, gold: 50 } },
  { slug: "heavy_camel", label: "Heavy Camel Rider", civ: "Berbers", master: 330,
    fixture: "heavy_camel_berbers_imperial.json", class: "melee",
    baseCost: { food: 55, wood: 0, gold: 60 } },
  { slug: "heavy_cav_archer", label: "Heavy Cav Archer", civ: "Saracens", master: 474,
    fixture: "heavy_cav_archer_saracens_imperial.json", class: "mobile_ranged",
    baseCost: { food: 0, wood: 40, gold: 60 } },
  { slug: "heavy_scorpion", label: "Heavy Scorpion", civ: "Japanese", master: 542,
    fixture: "heavy_scorpion_japanese_imperial.json", class: "siege_ranged",
    baseCost: { food: 0, wood: 75, gold: 75 } },
  { slug: "hussar", label: "Hussar", civ: "Berbers", master: 441,
    fixture: "hussar_berbers_imperial.json", class: "melee",
    baseCost: { food: 80, wood: 0, gold: 0 } },
  { slug: "imp_elite_skirm", label: "Elite Skirmisher", civ: "Chinese", master: 6,
    fixture: "elite_skirmisher_chinese_imperial.json", class: "mobile_ranged",
    baseCost: { food: 25, wood: 35, gold: 0 } },
  { slug: "paladin", label: "Paladin", civ: "Spanish", master: 569,
    fixture: "paladin_spanish_imperial.json", class: "melee",
    baseCost: { food: 60, wood: 0, gold: 75 } },
  { slug: "siege_onager", label: "Siege Onager", civ: "Slavs", master: 588,
    fixture: "siege_onager_slavs_imperial.json", class: "siege_ranged",
    baseCost: { food: 0, wood: 160, gold: 135 } },
];

export const UNIT_REGISTRY = Object.freeze(ROWS.map((row) => Object.freeze({
  ...row,
  baseCost: Object.freeze(row.baseCost),
})));

export const UNIT_SLUGS = Object.freeze(UNIT_REGISTRY.map(({ slug }) => slug));

const BY_SLUG = new Map(UNIT_REGISTRY.map((row) => [row.slug, row]));

export function unitBySlug(slug) {
  return BY_SLUG.get(slug);
}
