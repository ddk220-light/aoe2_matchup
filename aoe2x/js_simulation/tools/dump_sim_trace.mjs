// Dump the clean-room simulator's per-tick trace for every ratio, in the same
// shape as the tape traces decoded from frames.bin. Read-only against the repo.
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const ROOT = "D:/AI/aoe2_matchup/aoe2x/js_simulation/";
const { runChampionRatio } = await import(
  pathToFileURL(ROOT + "tests/support/champion-ratio.mjs").href
);

const TICKS = 60;
const ratios = process.argv.length > 2
  ? process.argv.slice(2)
  : ["1v1", "2v1", "2v3", "5v3", "6v3"];

for (const ratio of ratios) {
  let result;
  try {
    result = runChampionRatio(ratio);
  } catch (error) {
    console.log(JSON.stringify({ ratio, error: String(error.message ?? error) }));
    continue;
  }
  const rows = [];
  for (const snapshot of result.snapshots) {
    for (const unit of snapshot.units) {
      rows.push({
        tick: snapshot.tick,
        t_ms: Math.round((snapshot.tick / TICKS) * 1000),
        id: unit.referenceId,
        owner: unit.owner,
        x: unit.x,
        y: unit.y,
        hp: unit.hp,
        alive: unit.alive,
        action: unit.action,
        pursuit: unit.pursuitTargetId ?? null,
        engaged: unit.engagedTargetId ?? null,
        attack: unit.attackTargetId ?? null,
        windup: unit.actionTimers.windup ?? 0,
        reload: unit.actionTimers.reload ?? 0,
        recover: unit.actionTimers.recover ?? 0,
        acquire: unit.actionTimers.acquire ?? 0,
      });
    }
  }
  writeFileSync(
    `${ratio}.sim_trace.jsonl`,
    rows.map((row) => JSON.stringify(row)).join("\n") + "\n",
  );
  writeFileSync(`${ratio}.sim_events.json`, JSON.stringify(result.events));
  console.log(JSON.stringify({
    ratio,
    ticks: result.ticks,
    winnerOwner: result.winnerOwner,
    winnerHp: result.winnerHp,
    survivors: result.livingUnits.length,
    damageEvents: result.damageEvents.length,
  }));
}
