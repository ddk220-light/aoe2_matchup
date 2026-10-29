import { hashCanonicalJson } from "../src/canonical-json.js";

// Deliberately ignore only the display civilization. Keep every other field,
// including costs, master/slug, animations, damage classes, collision, traits,
// projectiles and nested effects. Unknown future fields therefore prevent
// sharing by default. The V3 combat code never reads `civilization`.
export function combatProfileHash(mechanics) {
  return hashCanonicalJson(Object.fromEntries(Object.entries(mechanics)
    .filter(([key]) => key !== "civilization")));
}

export function equivalentMatchupHash(manifest, matchup) {
  return hashCanonicalJson({
    profiles: matchup.teamKeys.map(key => combatProfileHash(manifest.profiles[key].mechanics)),
    counts: matchup.counts,
    scenarioHash: matchup.scenarioHash,
  });
}

export function assignEquivalence(manifest, preferredIds = []) {
  const preferred = new Map(preferredIds.map((id, index) => [id, index]));
  const groups = new Map();
  for (const matchup of manifest.matchups) {
    const hash = equivalentMatchupHash(manifest, matchup);
    if (!groups.has(hash)) groups.set(hash, []);
    groups.get(hash).push(matchup);
  }
  for (const [hash, members] of groups) {
    const canonical = [...members].sort((a, b) => (preferred.get(a.id) ?? Infinity) - (preferred.get(b.id) ?? Infinity))[0];
    for (const matchup of members) {
      matchup.combatEquivalenceHash = hash;
      matchup.canonicalMatchupId = canonical.id;
    }
  }
  return { ignoredProfileFields: ["civilization"], comparison: "exact values; no rounding or approximate matching",
    distinctUnitProfiles: new Set(Object.values(manifest.profiles).map(t => combatProfileHash(t.mechanics))).size,
    unitVariants: Object.keys(manifest.profiles).length, distinctMatchups: groups.size,
    matchupRows: manifest.matchups.length, avoidedBaselineRuns: (manifest.matchups.length - groups.size) * 3,
    groups: [...groups].map(([hash, members]) => ({ hash, canonicalMatchupId: members[0].canonicalMatchupId,
      matchupIds: members.map(m => m.id) })) };
}
