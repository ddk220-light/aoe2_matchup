// Exact roster rows from the authorized standard-units truth fixture. The
// server exposes these as the kiting lab's selectable surface; tests compare
// every row back to the clean-room fixture so this copy cannot drift silently.
const ROWS = [
  ["492-18_vs_567-21", "arbalester", 18, "champion", 21, 8],
  ["492-21_vs_1134-9", "arbalester", 21, "elite_elephant", 9, 7],
  ["492-21_vs_1903-17", "arbalester", 21, "elite_fire_lancer", 17, 2],
  ["492-21_vs_1372-14", "arbalester", 21, "elite_steppe", 14, 10],
  ["492-13_vs_359-21", "arbalester", 13, "halberdier", 21, 4],
  ["492-21_vs_330-13", "arbalester", 21, "heavy_camel", 13, 2],
  ["492-18_vs_441-21", "arbalester", 18, "hussar", 21, 5],
  ["492-21_vs_569-11", "arbalester", 21, "paladin", 11, 14],
  ["5-14_vs_567-21", "hand_cannoneer", 14, "champion", 21, 4],
  ["5-21_vs_1134-12", "hand_cannoneer", 21, "elite_elephant", 12, 5],
  ["5-19_vs_1903-21", "hand_cannoneer", 19, "elite_fire_lancer", 21, 1],
  ["5-21_vs_1372-19", "hand_cannoneer", 21, "elite_steppe", 19, 1],
  ["5-10_vs_359-21", "hand_cannoneer", 10, "halberdier", 21, 1],
  ["5-21_vs_330-17", "hand_cannoneer", 21, "heavy_camel", 17, 6],
  ["5-14_vs_441-21", "hand_cannoneer", 14, "hussar", 21, 6],
  ["5-21_vs_569-14", "hand_cannoneer", 21, "paladin", 14, 10],
  ["474-12_vs_567-21", "heavy_cav_archer", 12, "champion", 21, 14],
  ["474-21_vs_1134-13", "heavy_cav_archer", 21, "elite_elephant", 13, 3],
  ["474-18_vs_1903-21", "heavy_cav_archer", 18, "elite_fire_lancer", 21, 5],
  ["474-21_vs_1372-21", "heavy_cav_archer", 21, "elite_steppe", 21, 10],
  ["474-9_vs_359-21", "heavy_cav_archer", 9, "halberdier", 21, 10],
  ["474-21_vs_330-18", "heavy_cav_archer", 21, "heavy_camel", 18, 10],
  ["474-12_vs_441-21", "heavy_cav_archer", 12, "hussar", 21, 5],
  ["474-21_vs_569-15", "heavy_cav_archer", 21, "paladin", 15, 11],
  ["542-8_vs_567-21", "heavy_scorpion", 8, "champion", 21, 3],
  ["542-16_vs_1134-14", "heavy_scorpion", 16, "elite_elephant", 14, 3],
  ["542-12_vs_1903-21", "heavy_scorpion", 12, "elite_fire_lancer", 21, 2],
  ["542-14_vs_1372-21", "heavy_scorpion", 14, "elite_steppe", 21, 2],
  ["542-6_vs_359-21", "heavy_scorpion", 6, "halberdier", 21, 2],
  ["542-15_vs_330-20", "heavy_scorpion", 15, "heavy_camel", 20, 2],
  ["542-8_vs_441-21", "heavy_scorpion", 8, "hussar", 21, 4],
  ["542-15_vs_569-17", "heavy_scorpion", 15, "paladin", 17, 5],
];


export const KITE_OBSERVATION_MATCHUPS = Object.freeze(ROWS.map(([
  id, rangedSlug, rangedCount, meleeSlug, meleeCount, tapeRunCount,
]) => Object.freeze({
  id, rangedSlug, rangedCount, meleeSlug, meleeCount, tapeRunCount,
})));


const BY_PAIR = new Map(KITE_OBSERVATION_MATCHUPS.map((row) => [
  `${row.rangedSlug}|${row.meleeSlug}`,
  row,
]));


export function kitingObservationMatchup(rangedSlug, meleeSlug) {
  return BY_PAIR.get(`${rangedSlug}|${meleeSlug}`) ?? null;
}
