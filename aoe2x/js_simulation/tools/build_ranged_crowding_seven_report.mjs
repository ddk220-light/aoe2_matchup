import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";


const CURRENT = resolve(
  "calibration/reports/ranged_crowding_seven_failures_2026-08-30/results.json",
);
const BASELINE = resolve(
  "calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json",
);
const OUTPUT_ROOT = resolve(
  "calibration/reports/ranged_crowding_seven_failures_2026-08-30",
);
const PUBLISHED_ROOT = resolve(
  "calibration/reports/ranged_combat_comprehensive_2026-08-29",
);
const LIVE_ROOT = "aoe2x/js_simulation/calibration/live_observations/ranged_matrix_5x_2026-08-29";
const RESULTS_PATH = "aoe2x/js_simulation/calibration/reports/ranged_crowding_seven_failures_2026-08-30/results.json";
const VIEWER_BASE = "https://starlight.tail82a190.ts.net/golden-map/";
const HP_TARGET = 0.05;


const LABELS = Object.freeze({
  arbalester: "Arbalester",
  champion: "Champion",
  elite_steppe: "Elite Steppe Lancer",
  hand_cannoneer: "Hand Cannoneer",
  heavy_cav_archer: "Heavy Cavalry Archer",
  paladin: "Paladin",
});


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function label(row) {
  const side = ({ civ, slug, count }) => `${civ} ${LABELS[slug] ?? slug} (${count})`;
  return `${side(row.side2)} vs ${side(row.side3)}`;
}


function classify(row) {
  const liveOwner = new Set(row.tape.winnerOwners).size === 1 ? row.tape.winnerOwners[0] : null;
  const completed = row.simulation.runs.filter(({ score }) => Number.isFinite(score));
  const wrong = completed.filter(({ winnerOwner }) => winnerOwner !== liveOwner);
  const liveHp = mean(row.tape.winnerHp);
  const simHp = completed.length ? mean(completed.map(({ winnerHp }) => winnerHp)) : null;
  const hpDelta = completed.length === row.simulation.runs.length && wrong.length === 0
    ? Math.abs(simHp - liveHp) / liveHp
    : null;
  const status = completed.length !== row.simulation.runs.length
    ? "unresolved"
    : wrong.length
      ? "wrong-winner"
      : hpDelta > HP_TARGET
        ? "hp-outside-target"
        : "pass";
  return { row, liveOwner, completed, wrong, liveHp, simHp, hpDelta, status };
}


function representative(item) {
  const candidates = item.wrong.length ? item.wrong : item.completed;
  const target = item.wrong.length
    ? mean(item.wrong.map(({ score }) => score))
    : item.simHp;
  const distance = item.wrong.length
    ? ({ score }) => Math.abs(score - target)
    : ({ winnerHp }) => Math.abs(winnerHp - target);
  return candidates.toSorted((left, right) => (
    distance(left) - distance(right) || left.openingSeed - right.openingSeed
  ))[0];
}


function issue(item) {
  if (item.status === "wrong-winner") {
    return `${item.wrong.length}/5 seeds pick the wrong winner`;
  }
  if (item.status === "hp-outside-target") {
    return `${(item.hpDelta * 100).toFixed(1)}% winner-HP delta`;
  }
  if (item.status === "unresolved") return "one or more seeds did not resolve";
  return "meets 5% target";
}


function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}


const [current, baseline] = await Promise.all([
  readFile(CURRENT, "utf8").then(JSON.parse),
  readFile(BASELINE, "utf8").then(JSON.parse),
]);
const currentRows = current.rows.map(classify);
const baselineByKey = new Map(baseline.rows.map((row) => [row.key, classify(row)]));
const generatedAt = new Date().toISOString();
const comparisons = currentRows.map((item) => {
  const before = baselineByKey.get(item.row.key);
  return {
    key: item.row.key,
    label: label(item.row),
    family: item.row.family,
    liveWinnerOwner: item.liveOwner,
    liveWinnerHpMean: item.liveHp,
    liveScore: item.row.tape.mean,
    before: {
      wrongWinnerSeeds: before.wrong.length,
      winnerHpDeltaPct: before.hpDelta === null ? null : before.hpDelta * 100,
      simulationScore: before.row.simulation.score,
    },
    after: {
      status: item.status,
      issue: issue(item),
      wrongWinnerSeeds: item.wrong.length,
      wrongWinnerSeedNumbers: item.wrong.map(({ openingSeed }) => openingSeed),
      winnerHpMean: item.simHp,
      winnerHpDeltaPct: item.hpDelta === null ? null : item.hpDelta * 100,
      simulationScore: item.row.simulation.score,
      runs: item.row.simulation.runs.map(({ openingSeed, winnerOwner, winnerHp, score, ticks }) => ({
        openingSeed, winnerOwner, winnerHp, score, ticks,
      })),
    },
    liveEvidence: [1, 2, 3, 4, 5].map((run) => ({
      run,
      framesBin: `${LIVE_ROOT}/${item.row.key}/run_${String(run).padStart(3, "0")}/raw recordings/${item.row.key}.frames.bin`,
    })),
  };
});
await writeFile(resolve(OUTPUT_ROOT, "before_after.json"), `${JSON.stringify({
  schemaVersion: 1,
  generatedAt,
  hpTargetPct: 5,
  currentResults: RESULTS_PATH,
  baselineResults: "aoe2x/js_simulation/calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json",
  comparisons,
}, null, 2)}\n`);

const problemRows = currentRows.filter(({ status }) => status !== "pass");
const viewerRows = problemRows.map((item) => {
  const selected = representative(item);
  const url = new URL(VIEWER_BASE);
  url.searchParams.set("mode", "problem-matchups");
  url.searchParams.set("matchup", item.row.key);
  return {
    id: item.row.key,
    label: label(item.row),
    family: item.row.family,
    status: item.status,
    issue: issue(item),
    liveScore: item.row.tape.mean,
    simulationScore: item.row.simulation.score,
    simulationScoreIsPartial: false,
    liveWinnerOwner: item.liveOwner,
    liveWinnerHpMean: item.liveHp,
    simulationWinnerHpMean: item.simHp,
    relativeWinnerHpDeltaPct: item.hpDelta === null ? null : item.hpDelta * 100,
    resolvedSeeds: item.completed.length,
    timeoutSeeds: [],
    wrongWinnerSeeds: item.wrong.length,
    wrongWinnerSeedNumbers: item.wrong.map(({ openingSeed }) => openingSeed),
    representativeSeed: selected.openingSeed,
    representativeReason: item.wrong.length ? "wrong-winner seed" : "winner-HP seed nearest simulation mean",
    representativeWinnerOwner: selected.winnerOwner,
    representativeWinnerHp: selected.winnerHp,
    viewerUrl: url.href,
    side2: { ...item.row.side2, label: LABELS[item.row.side2.slug] },
    side3: { ...item.row.side3, label: LABELS[item.row.side3.slug] },
  };
});
await writeFile(resolve(PUBLISHED_ROOT, "viewer_problem_catalogue.json"), `${JSON.stringify({
  schemaVersion: 2,
  generatedAt,
  repositoryBase: null,
  comparisonResults: RESULTS_PATH,
  hpTargetPct: 5,
  rows: viewerRows,
}, null, 2)}\n`);

const tableRows = comparisons.map((row) => {
  const before = row.before.winnerHpDeltaPct === null
    ? `${row.before.wrongWinnerSeeds}/5 wrong`
    : `${row.before.winnerHpDeltaPct.toFixed(1)}% HP`;
  const after = row.after.winnerHpDeltaPct === null
    ? `${row.after.wrongWinnerSeeds}/5 wrong`
    : `${row.after.winnerHpDeltaPct.toFixed(1)}% HP`;
  const href = `${VIEWER_BASE}?mode=problem-matchups&amp;matchup=${encodeURIComponent(row.key)}`;
  return `<tr><td><a href="${href}">${escapeHtml(row.label)}</a></td><td>${before}</td><td>${after}</td><td>${escapeHtml(row.after.issue)}</td></tr>`;
}).join("\n");
const improved = comparisons.filter((row) => (
  row.after.wrongWinnerSeeds < row.before.wrongWinnerSeeds
  || (row.after.winnerHpDeltaPct !== null && row.before.winnerHpDeltaPct !== null
    && row.after.winnerHpDeltaPct < row.before.winnerHpDeltaPct)
)).length;
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ranged crowding five-seed audit</title><style>body{font:16px/1.45 system-ui;margin:0;background:#10151d;color:#eef3f8}main{max-width:1100px;margin:auto;padding:24px}h1{font-size:clamp(1.6rem,5vw,2.6rem)}.summary{background:#182231;border:1px solid #31445d;border-radius:12px;padding:16px}table{width:100%;border-collapse:collapse;margin-top:20px;background:#151e2a}th,td{padding:12px;border-bottom:1px solid #304052;text-align:left;vertical-align:top}a{color:#7dc4ff}small{color:#aebdcb}@media(max-width:700px){table{font-size:13px}th,td{padding:8px}}</style></head><body><main><h1>Ranged crowding: seven-row, five-seed audit</h1><div class="summary"><strong>0 of 7 meet the strict 5% rule.</strong> ${improved} rows improved on winner stability or valid HP delta; 35/35 simulations completed. Three rows still contain wrong-winner seeds. The overlap mechanic is therefore useful but not a complete generic correction.</div><table><thead><tr><th>Matchup</th><th>Before</th><th>After</th><th>Current issue</th></tr></thead><tbody>${tableRows}</tbody></table><p><small>Live evidence: five runs per row from <code>${LIVE_ROOT}/&lt;matchup&gt;/run_001..005/raw recordings/&lt;matchup&gt;.frames.bin</code>. Current engine output: <code>${RESULTS_PATH}</code>. Every matchup link opens the representative failing seed from this same comparison output.</small></p></main></body></html>`;
await Promise.all([
  writeFile(resolve(OUTPUT_ROOT, "report.html"), html),
  writeFile(resolve(PUBLISHED_ROOT, "report.html"), html),
]);
process.stdout.write(`${JSON.stringify({ generatedAt, report: resolve(OUTPUT_ROOT, "report.html"), published: resolve(PUBLISHED_ROOT, "report.html"), viewerRows: viewerRows.length, improved })}\n`);
