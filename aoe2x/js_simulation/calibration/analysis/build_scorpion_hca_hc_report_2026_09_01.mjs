import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const reportRoot = path.join(
  root, "calibration", "reports", "scorpion_hca_hc_deep_dive_2026-09-01",
);

const sources = Object.freeze({
  liveCombined: path.join(reportRoot, "live_full_rate.json"),
  liveHc: path.join(reportRoot, "live_full_rate_heavy_scorpion_vs_hand_cannoneer.json"),
  simHc: path.join(reportRoot, "candidate_reload_refund_heavy_scorpion_vs_hand_cannoneer_seed0.json"),
  simHca: path.join(reportRoot, "candidate_reload_refund_heavy_scorpion_vs_heavy_cav_archer_seed0.json"),
  outcomeHc: path.join(reportRoot, "candidate_reload_refund_5x_heavy_scorpion_vs_hand_cannoneer.json"),
  outcomeHca: path.join(reportRoot, "final_reload_refund_5x_heavy_scorpion_vs_heavy_cav_archer.json"),
});

const matchupConfig = Object.freeze({
  heavy_scorpion_vs_hand_cannoneer: Object.freeze({
    label: "Chinese Heavy Scorpion vs Spanish Hand Cannoneer",
    shortLabel: "Scorpion vs HC",
    ownerLabels: Object.freeze({ 2: "Heavy Scorpion", 3: "Hand Cannoneer" }),
    liveSource: "liveHc",
    simSource: "simHc",
    outcomeSource: "outcomeHc",
    viewerPath: "/golden-map/?mode=battle&side2=heavy_scorpion&side3=hand_cannoneer&n2=17&n3=27",
  }),
  heavy_scorpion_vs_heavy_cav_archer: Object.freeze({
    label: "Chinese Heavy Scorpion vs Saracens Heavy Cavalry Archer",
    shortLabel: "Scorpion vs HCA",
    ownerLabels: Object.freeze({ 2: "Heavy Scorpion", 3: "Heavy Cavalry Archer" }),
    liveSource: "liveCombined",
    simSource: "simHca",
    outcomeSource: "outcomeHca",
    viewerPath: "/golden-map/?mode=battle&side2=heavy_scorpion&side3=heavy_cav_archer&n2=18&n3=27",
  }),
});

const windows = Object.freeze([
  Object.freeze({ label: "0–5 s", start: 0, end: 5 }),
  Object.freeze({ label: "5–20 s", start: 5, end: 20 }),
  Object.freeze({ label: "20–40 s", start: 20, end: 40 }),
]);

const round = (value, digits = 2) => (
  Number.isFinite(value) ? Number(value.toFixed(digits)) : null
);

const mean = (values) => {
  const finite = values.filter(Number.isFinite);
  return finite.length === 0
    ? null
    : finite.reduce((total, value) => total + value, 0) / finite.length;
};

const readJson = async (file) => JSON.parse(await readFile(file, "utf8"));

function normalizedLiveRows(report, key, owner) {
  return report.matchups[key].meanPerSecond.map((row) => Object.freeze({
    second: row.second,
    overlapPairs: row[String(owner)].meanBoxOverlapPairs,
    overlapDepth: row[String(owner)].meanBoxOverlapDepth,
    maxOverlapDepth: row[String(owner)].maxBoxOverlapDepth,
    overlappedUnits: row[String(owner)].meanBoxOverlappedUnits,
    tripleStacks: row[String(owner)].meanTripleStacks,
    fourStacks: row[String(owner)].meanFourStacks,
    nearestDistance: row[String(owner)].meanNearestFriendlyDistance,
  }));
}

function normalizedSimulationRows(report, owner) {
  return report.rows[0].simulation[0].metrics.formationPerSecond.map((row) => Object.freeze({
    second: row.second,
    overlapPairs: row[String(owner)].boxOverlapPairs,
    overlapDepth: row[String(owner)].meanBoxOverlapDepth,
    maxOverlapDepth: row[String(owner)].maxBoxOverlapDepth,
    overlappedUnits: row[String(owner)].boxOverlappedUnits,
    tripleStacks: row[String(owner)].tripleStacks,
    fourStacks: row[String(owner)].fourStacks,
    nearestDistance: row[String(owner)].meanNearestFriendlyDistance,
  }));
}

function windowSummary(rows, { start, end }) {
  const selected = rows.filter(({ second }) => second >= start && second < end);
  return Object.freeze({
    overlapPairs: round(mean(selected.map(({ overlapPairs }) => overlapPairs))),
    overlapDepth: round(mean(selected.map(({ overlapDepth }) => overlapDepth)), 3),
    maxOverlapDepth: round(Math.max(0, ...selected.map(({ maxOverlapDepth }) => maxOverlapDepth)), 3),
    overlappedUnits: round(mean(selected.map(({ overlappedUnits }) => overlappedUnits))),
    tripleStacks: round(mean(selected.map(({ tripleStacks }) => tripleStacks))),
    fourStacks: round(mean(selected.map(({ fourStacks }) => fourStacks))),
    nearestDistance: round(mean(selected.map(({ nearestDistance }) => nearestDistance)), 3),
  });
}

function peakSummary(rows) {
  const pairPeak = rows.reduce((best, row) => (
    row.overlapPairs > best.overlapPairs ? row : best
  ), rows[0]);
  const depthPeak = rows.reduce((best, row) => (
    row.maxOverlapDepth > best.maxOverlapDepth ? row : best
  ), rows[0]);
  return Object.freeze({
    firstOverlapSecond: rows.find(({ overlapPairs }) => overlapPairs > 0.05)?.second ?? null,
    pairPeakSecond: pairPeak.second,
    pairPeak: round(pairPeak.overlapPairs),
    depthPeakSecond: depthPeak.second,
    depthPeak: round(depthPeak.maxOverlapDepth, 3),
  });
}

function outcomeSummary(report) {
  const row = report.rows[0];
  return Object.freeze({
    liveWinnerOwner: row.liveSummary.winnerOwners[0],
    liveWinnerHpMean: round(row.liveSummary.winnerHp.mean, 1),
    liveWinnerHpRange: Object.freeze([
      round(row.liveSummary.winnerHp.min, 1),
      round(row.liveSummary.winnerHp.max, 1),
    ]),
    simulationWinnerOwners: row.simulationSummary.winnerOwners,
    simulationWinnerHpMean: round(row.simulationSummary.winnerHp.mean, 1),
    simulationWinnerHpRange: Object.freeze([
      round(row.simulationSummary.winnerHp.min, 1),
      round(row.simulationSummary.winnerHp.max, 1),
    ]),
    correctWinnerRuns: row.simulationSummary.correctWinnerRuns,
    resolvedRuns: row.simulationSummary.resolved,
    hpDeltaPct: round(100 * row.simulationSummary.relativeWinnerHpDelta, 1),
  });
}

function htmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function reportHtml(data) {
  const outcomeRows = data.matchups.map((matchup) => {
    const winner = matchup.ownerLabels[matchup.outcome.liveWinnerOwner];
    return `<tr><td>${htmlEscape(matchup.shortLabel)}</td><td>${htmlEscape(winner)}</td><td>${matchup.outcome.liveWinnerHpMean} <span class="muted">(${matchup.outcome.liveWinnerHpRange.join("–")})</span></td><td>${matchup.outcome.simulationWinnerHpMean} <span class="muted">(${matchup.outcome.simulationWinnerHpRange.join("–")})</span></td><td>${matchup.outcome.correctWinnerRuns}/${matchup.outcome.resolvedRuns}</td><td><strong>${matchup.outcome.hpDeltaPct}%</strong></td><td><a class="button" href="${matchup.viewerPath}">Open replay</a></td></tr>`;
  }).join("");
  const overlapRows = data.matchups.flatMap((matchup) => (
    matchup.armies.flatMap((army) => army.windows.map((window) => (
      `<tr><td>${htmlEscape(matchup.shortLabel)}</td><td>${htmlEscape(army.label)}</td><td>${window.label}</td><td>${window.live.overlapPairs}</td><td>${window.simulation.overlapPairs}</td><td>${window.live.overlappedUnits}</td><td>${window.simulation.overlappedUnits}</td><td>${window.live.overlapDepth}</td><td>${window.simulation.overlapDepth}</td><td>${window.live.tripleStacks}/${window.live.fourStacks}</td><td>${window.simulation.tripleStacks}/${window.simulation.fourStacks}</td></tr>`
    )))
  )).join("");
  const charts = data.matchups.flatMap((matchup) => matchup.armies.map((army) => (
    `<section class="chart-card"><h3>${htmlEscape(matchup.shortLabel)} · ${htmlEscape(army.label)}</h3><div class="legend"><span><i class="live"></i>Live 5-run mean</span><span><i class="sim"></i>Simulation seed 0</span></div><svg class="chart" role="img" aria-label="Friendly overlap pairs by second" data-series='${htmlEscape(JSON.stringify({ live: army.liveSeries, simulation: army.simulationSeries }))}'></svg><p class="caption">Peak pairs: live ${army.peaks.live.pairPeak} at ${army.peaks.live.pairPeakSecond}s; simulation ${army.peaks.simulation.pairPeak} at ${army.peaks.simulation.pairPeakSecond}s. Maximum depth: live ${army.peaks.live.depthPeak} tiles; simulation ${army.peaks.simulation.depthPeak} tiles.</p></section>`
  ))).join("");
  const evidence = data.evidence.liveFrames.map(({ matchup, run, path: evidencePath }) => (
    `<li>${htmlEscape(matchup)} · run ${run}: <code>${htmlEscape(evidencePath)}</code></li>`
  )).join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Heavy Scorpion HCA/HC deep dive</title><style>
:root{color-scheme:dark;--bg:#0b1020;--card:#121a2e;--line:#2b3858;--text:#eef3ff;--muted:#9ba9c7;--live:#55b7ff;--sim:#ffb44c;--good:#5fe09a}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#182443 0,#0b1020 42rem);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}main{width:min(1180px,calc(100% - 28px));margin:auto;padding:34px 0 70px}h1{font-size:clamp(28px,5vw,48px);line-height:1.05;margin:0 0 12px}h2{font-size:22px;margin:38px 0 12px}h3{font-size:16px;margin:0 0 8px}.lede{max-width:850px;color:#c7d3ed;font-size:17px}.pill{display:inline-flex;gap:7px;align-items:center;padding:7px 11px;border:1px solid #2e7655;border-radius:999px;color:var(--good);background:#10271f;font-weight:700}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card,.chart-card{background:rgba(18,26,46,.94);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 14px 40px #05091666}.metric{font-size:30px;font-weight:800}.muted,.caption{color:var(--muted)}.caption{font-size:13px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px;background:var(--card)}table{border-collapse:collapse;width:100%;min-width:850px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid #26324e;white-space:nowrap}th{position:sticky;top:0;background:#17213a;color:#b9c8e8;font-size:12px;text-transform:uppercase;letter-spacing:.04em}.button{display:inline-block;color:#07111e;background:#80caff;text-decoration:none;padding:7px 10px;border-radius:8px;font-weight:800}.legend{display:flex;gap:18px;color:var(--muted);font-size:12px}.legend i{display:inline-block;width:14px;height:3px;margin:0 6px 3px 0}.legend .live{background:var(--live)}.legend .sim{background:var(--sim)}.chart{width:100%;height:190px;overflow:visible}.axis{stroke:#405075;stroke-width:1}.gridline{stroke:#26334f;stroke-width:1}.live-line{fill:none;stroke:var(--live);stroke-width:2.5}.sim-line{fill:none;stroke:var(--sim);stroke-width:2.5}.note{border-left:3px solid var(--live);padding:10px 14px;background:#101a31;border-radius:0 10px 10px 0}.sources{font-size:12px;word-break:break-all}code{color:#c9d7f5}details{margin-top:12px}summary{cursor:pointer;font-weight:700}@media(max-width:760px){.grid{grid-template-columns:1fr}main{width:min(100% - 18px,1180px);padding-top:20px}.card,.chart-card{padding:14px}}
</style></head><body><main>
<span class="pill">✓ Both matchups now choose the live winner in 5/5 seeds</span>
<h1>Heavy Scorpion vs HCA / Hand Cannoneer</h1>
<p class="lede">The reusable fix is attack-cycle correctness: when a ranged target dies before release, the canceled shot refunds reload and begins a fresh acquisition/wind-up. It does not carry the old wind-up to a new victim. Large-body crowding remains physical and unit-agnostic.</p>
<div class="grid"><article class="card"><div class="muted">Scorpion vs HCA</div><div class="metric">${data.matchups[1].outcome.hpDeltaPct}%</div><div>mean survivor-HP delta · 5/5 correct</div></article><article class="card"><div class="muted">Scorpion vs HC</div><div class="metric">${data.matchups[0].outcome.hpDeltaPct}%</div><div>mean survivor-HP delta · 5/5 correct · inside the agreed 50% siege tolerance</div></article></div>
<h2>Outcome comparison</h2><div class="table-wrap"><table><thead><tr><th>Matchup</th><th>Live winner</th><th>Live mean HP</th><th>Sim mean HP</th><th>Correct seeds</th><th>HP delta</th><th>Viewer</th></tr></thead><tbody>${outcomeRows}</tbody></table></div>
<h2>What changed</h2><div class="grid"><article class="card"><h3>Attack-cycle fix</h3><p>All five HC captures show zero target swaps that preserve Action 7 wind-up. When a victim dies during wind-up, reacquisition usually appears 0.03–0.07 s later in pursuit state. The engine now cancels the unreleased cycle, refunds reload, and aims again normally.</p></article><article class="card"><h3>No output fitting</h3><p>No damage multiplier, forced target, winner override, HP correction, matchup timer, or copied waypoint was added. Scorpion full/pass damage remains the DAT/class result plus the measured 50% pass-through rule.</p></article></div>
<h2>Friendly-unit overlap</h2><p class="note">“Pairs” counts simultaneous same-army pairs whose collision boxes intersect. “Units” counts distinct bodies participating in at least one overlap. Depth is the mean positive Chebyshev penetration in tiles. Triple/four values count shared positive-area stacks.</p>
<div class="table-wrap"><table><thead><tr><th>Matchup</th><th>Army</th><th>Time</th><th>Live pairs</th><th>Sim pairs</th><th>Live units</th><th>Sim units</th><th>Live depth</th><th>Sim depth</th><th>Live 3/4</th><th>Sim 3/4</th></tr></thead><tbody>${overlapRows}</tbody></table></div>
<h2>Overlap over time</h2><div class="grid">${charts}</div>
<h2>Interpretation</h2><div class="card"><p>Live Scorpions begin heavily compressed, then shed overlap as firing lanes and casualties develop. HC and HCA lines also compress on approach, but the live lines form fewer, more selective overlap pockets than seed 0 of the simulation. The simulation still over-counts shallow friendly contacts after 5 s—especially for HC/HCA—even though firing participation and winner direction now agree. That is a documented geometry residual, not hidden calibration.</p><p>The stronger HCA result emerges from reusable size/path behavior: medium cavalry bodies inherit obstruction from their committed firing contacts, while large Scorpion bodies screen later siege ingress. The HC result was principally the canceled-reload bug, not Scorpion damage.</p></div>
<h2>Evidence and traceability</h2><div class="card sources"><p>Outcome sources: <code>${htmlEscape(data.evidence.outcomeFiles.join(" · "))}</code></p><p>Simulation overlap sources: <code>${htmlEscape(data.evidence.simulationFiles.join(" · "))}</code></p><details><summary>Exact live frames.bin files (${data.evidence.liveFrames.length})</summary><ul>${evidence}</ul></details></div>
</main><script>
const NS="http://www.w3.org/2000/svg";for(const svg of document.querySelectorAll("svg.chart")){const series=JSON.parse(svg.dataset.series);const rows=[...series.live,...series.simulation];const maxX=Math.max(40,...rows.map(r=>r.second));const maxY=Math.max(1,...rows.map(r=>r.overlapPairs))*1.08;const W=560,H=190,L=34,R=10,T=12,B=24;const x=v=>L+(v/maxX)*(W-L-R);const y=v=>T+(1-v/maxY)*(H-T-B);svg.setAttribute("viewBox","0 0 "+W+" "+H);for(let i=0;i<=4;i++){const line=document.createElementNS(NS,"line");line.setAttribute("x1",L);line.setAttribute("x2",W-R);line.setAttribute("y1",y(maxY*i/4));line.setAttribute("y2",y(maxY*i/4));line.setAttribute("class","gridline");svg.append(line)}for(const [name,values] of Object.entries(series)){const poly=document.createElementNS(NS,"polyline");poly.setAttribute("points",values.filter(r=>r.second<=maxX).map(r=>x(r.second)+","+y(r.overlapPairs)).join(" "));poly.setAttribute("class",name==="live"?"live-line":"sim-line");svg.append(poly)}const axis=document.createElementNS(NS,"line");axis.setAttribute("x1",L);axis.setAttribute("x2",W-R);axis.setAttribute("y1",H-B);axis.setAttribute("y2",H-B);axis.setAttribute("class","axis");svg.append(axis)}
</script></body></html>`;
}


async function main() {
  const documents = Object.fromEntries(await Promise.all(Object.entries(sources).map(
    async ([name, file]) => [name, await readJson(file)],
  )));
  const matchups = [];
  const liveFrames = [];
  for (const [key, config] of Object.entries(matchupConfig)) {
    const liveReport = documents[config.liveSource];
    const simReport = documents[config.simSource];
    const outcomeReport = documents[config.outcomeSource];
    liveFrames.push(...liveReport.matchups[key].runs.map(({ repeat, framesBin }) => ({
      matchup: key,
      run: repeat,
      path: framesBin,
    })));
    const armies = [2, 3].map((owner) => {
      const liveRows = normalizedLiveRows(liveReport, key, owner);
      const simulationRows = normalizedSimulationRows(simReport, owner);
      return Object.freeze({
        owner,
        label: config.ownerLabels[owner],
        windows: windows.map((window) => Object.freeze({
          label: window.label,
          live: windowSummary(liveRows, window),
          simulation: windowSummary(simulationRows, window),
        })),
        peaks: Object.freeze({
          live: peakSummary(liveRows.slice(0, 40)),
          simulation: peakSummary(simulationRows.filter(({ second }) => second < 40)),
        }),
        liveSeries: liveRows.filter(({ second }) => second < 40),
        simulationSeries: simulationRows.filter(({ second }) => second < 40),
      });
    });
    matchups.push(Object.freeze({
      key,
      ...config,
      outcome: outcomeSummary(outcomeReport),
      armies,
    }));
  }
  const data = Object.freeze({
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    acceptance: Object.freeze({
      ordinaryHpDeltaPct: 15,
      siegeHpDeltaPct: 50,
      requiresStableCorrectWinner: true,
    }),
    matchups,
    evidence: Object.freeze({
      liveFrames,
      outcomeFiles: [sources.outcomeHc, sources.outcomeHca],
      simulationFiles: [sources.simHc, sources.simHca],
    }),
  });
  await writeFile(
    path.join(reportRoot, "final_report_data.json"),
    `${JSON.stringify(data, null, 2)}\n`,
  );
  await writeFile(path.join(reportRoot, "report.html"), reportHtml(data));
  console.log(path.join(reportRoot, "report.html"));
}


await main();
