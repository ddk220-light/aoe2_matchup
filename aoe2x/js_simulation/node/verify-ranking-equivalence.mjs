import { readFileSync, writeFileSync } from "node:fs";
import { RankingWorkerPool } from "./ranking-worker-pool.mjs";
import { combatProfileHash } from "./ranking-equivalence.mjs";
import { jobFor } from "./full-ranking-campaign.mjs";

const manifest = JSON.parse(readFileSync(process.argv[2], "utf8"));
const pairs = [
  ["Spanish", "Armenians", "halberdier", "champion"],
  ["Spanish", "Berbers", "imp_elite_skirm", "arbalester"],
  ["Spanish", "Khmer", "hussar", "arbalester"],
  ["Bengalis", "Saxons", "heavy_scorpion", "champion"],
  ["Saracens", "Khmer", "hand_cannoneer", "arbalester"],
];
const pool = new RankingWorkerPool(4), checks = [];
try {
  await Promise.all(pairs.map(async ([a, b, slug, opponent]) => {
    const matchups = [a, b].map(civ => manifest.matchups.find(m => m.civilization === civ && m.slug === slug && m.opponent === opponent));
    if (matchups.some(m => !m)) throw new Error("missing equivalence check unit");
    if (combatProfileHash(manifest.profiles[matchups[0].teamKeys[0]].mechanics)
      !== combatProfileHash(manifest.profiles[matchups[1].teamKeys[0]].mechanics)) throw new Error("check profiles are not equivalent");
    const results = await Promise.all(matchups.map(m => pool.run({ ...jobFor(manifest, m, 0), verifyFinalSnapshot: true })));
    const [x, y] = results;
    const exact = Boolean(x.result && y.result && x.finalSnapshotHash === y.finalSnapshotHash
      && x.result.eventLogHash === y.result.eventLogHash && x.result.ticks === y.result.ticks
      && JSON.stringify(x.result.remainingByOwner) === JSON.stringify(y.result.remainingByOwner)
      && x.result.winnerOwner === y.result.winnerOwner);
    checks.push({ civilizations: [a, b], slug, opponent, exact,
      finalSnapshotHashes: results.map(r => r.finalSnapshotHash ?? null),
      eventLogHashes: results.map(r => r.result?.eventLogHash ?? null) });
    console.log(JSON.stringify(checks.at(-1)));
  }));
  const report = { allExact: checks.every(c => c.exact), pairs: checks.length,
    note: "Full-state hashes contain the civilization label; compare final animation state, every combat event, HP, winner and duration instead.", checks };
  writeFileSync(process.argv[3], `${JSON.stringify(report, null, 2)}\n`);
  if (!report.allExact) throw new Error("combat equivalence validation failed");
} finally { await pool.close(); }
