"""Compose the self-contained comparison dashboard (single HTML file, data inlined)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "dashboard_data.json").read_text())

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unit Matchup Comparison — V2 · DB · In-game</title>
<style>
  :root{
    --bg:#12151c; --panel:#1a1f2b; --panel2:#212736; --line:#2c3446;
    --ink:#e7eaf2; --muted:#8b94a8; --faint:#5b647a;
    --gold:#c9a54c; --accent:#7aa2ff;
    --win:#39b26a; --win-bg:#153223; --loss:#e5573f; --loss-bg:#341813; --even:#d7a63f; --even-bg:#2e2612;
    --good:#39b26a; --bad:#e5573f;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:var(--bg); color:var(--ink);
    font:14px/1.45 "Segoe UI",system-ui,-apple-system,Roboto,sans-serif;
    -webkit-font-smoothing:antialiased;}
  a{color:var(--accent)}
  .wrap{max-width:1180px; margin:0 auto; padding:22px 18px 60px}
  header.top{display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; border-bottom:1px solid var(--line); padding-bottom:14px}
  header.top h1{font-size:19px; margin:0; font-weight:640; letter-spacing:.2px}
  header.top .sub{color:var(--muted); font-size:12.5px}
  header.top .weights{margin-left:auto; color:var(--muted); font-size:12px}
  header.top .weights b{color:var(--gold); font-weight:600}

  .tabs{display:flex; gap:6px; margin:18px 0 10px; flex-wrap:wrap}
  .tab{background:var(--panel); border:1px solid var(--line); color:var(--muted);
    padding:9px 14px; border-radius:9px; cursor:pointer; font-weight:560; font-size:13px;
    display:flex; gap:9px; align-items:center; transition:.12s}
  .tab:hover{color:var(--ink); border-color:#3a4560}
  .tab.active{background:var(--panel2); color:var(--ink); border-color:var(--gold)}
  .tab .civ{color:var(--faint); font-weight:500; font-size:11.5px}
  .tab.active .civ{color:var(--gold)}

  .toolbar{display:flex; align-items:center; gap:16px; margin:6px 0 16px; flex-wrap:wrap}
  .chk{display:flex; align-items:center; gap:7px; color:var(--muted); font-size:12.5px; cursor:pointer; user-select:none}
  .chk input{accent-color:var(--gold); width:15px; height:15px}
  .legend{display:flex; gap:12px; margin-left:auto; font-size:11.5px; color:var(--muted); flex-wrap:wrap}
  .legend .pill{padding:2px 8px; border-radius:20px; font-weight:600; font-size:10.5px}

  /* summary */
  .summary{display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; margin-bottom:20px}
  .card{background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px}
  .card h3{margin:0 0 3px; font-size:11px; text-transform:uppercase; letter-spacing:.7px; color:var(--muted); font-weight:600}
  .card .big{font-size:26px; font-weight:680; font-variant-numeric:tabular-nums}
  .card .big small{font-size:14px; color:var(--muted); font-weight:500}
  .card .note{font-size:11.5px; color:var(--faint); margin-top:3px}
  .barrow{display:flex; align-items:center; gap:9px; margin-top:8px}
  .barrow .name{width:56px; font-size:11.5px; color:var(--muted)}
  .bar{flex:1; height:8px; background:var(--panel2); border-radius:6px; overflow:hidden}
  .bar > span{display:block; height:100%}
  .barrow .val{width:44px; text-align:right; font-size:11.5px; font-variant-numeric:tabular-nums; color:var(--ink)}

  /* table */
  table{width:100%; border-collapse:collapse; margin-top:4px}
  thead th{position:sticky; top:0; background:var(--bg); z-index:2; text-align:left;
    font-size:10.5px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted);
    font-weight:600; padding:9px 10px; border-bottom:1px solid var(--line)}
  thead th.src{text-align:center; width:150px}
  .catrow td{background:linear-gradient(90deg,var(--panel2),transparent);
    padding:12px 10px 6px; font-weight:660; font-size:12.5px; letter-spacing:.3px;
    border-bottom:1px solid var(--line)}
  .catrow .cnt{color:var(--faint); font-weight:500; margin-left:8px; font-size:11.5px}
  tbody tr.m{border-bottom:1px solid #232a39}
  tbody tr.m:hover{background:#171c27}
  td.opp{padding:8px 10px; vertical-align:middle}
  td.opp .nm{font-weight:580}
  td.opp .meta{color:var(--faint); font-size:11px; margin-top:1px}
  td.cell{padding:6px 8px; text-align:center; vertical-align:middle; border-left:1px solid #20273400}
  .cell.ingame{background:#161b26}
  .noval{color:var(--faint); font-size:12px}

  .chip{display:inline-block; min-width:52px; padding:3px 8px; border-radius:7px; font-weight:680;
    font-size:11px; letter-spacing:.3px}
  .chip.win{color:#8ff0b4; background:var(--win-bg); box-shadow:inset 0 0 0 1px #2a5a3e}
  .chip.loss{color:#ffb3a4; background:var(--loss-bg); box-shadow:inset 0 0 0 1px #6b2c22}
  .chip.coinflip{color:#f2d788; background:var(--even-bg); box-shadow:inset 0 0 0 1px #5c4a1e}
  .cell .cnts{font-size:11px; color:var(--muted); margin-top:3px; font-variant-numeric:tabular-nums}
  .cell .dhp{font-size:11px; font-variant-numeric:tabular-nums; margin-top:1px}
  .dhp.pos{color:#7fdca0} .dhp.neg{color:#f0a091}
  .mark{font-size:10px; font-weight:700; margin-left:5px}
  .mark.ok{color:var(--good)} .mark.no{color:var(--bad)}
  .disagree{box-shadow:inset 0 0 0 1px #6b2c22}

  .foot{margin-top:26px; color:var(--faint); font-size:11.5px; line-height:1.7}
  .foot code{background:var(--panel2); padding:1px 5px; border-radius:4px; color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Unit Matchup Comparison</h1>
    <span class="sub">V2 sim &middot; matchup&nbsp;DB &middot; in-game (showcase)</span>
    <span class="weights">weights <b>F&nbsp;__WF__ / W&nbsp;__WW__ / G&nbsp;__WG__</b> &nbsp;·&nbsp; DB scale __SCALE__ &nbsp;·&nbsp; gen __GEN__</span>
  </header>

  <div class="tabs" id="tabs"></div>
  <div class="toolbar">
    <label class="chk"><input type="checkbox" id="recorded"> Recorded matchups only (have in-game)</label>
    <label class="chk"><input type="checkbox" id="disagreeOnly"> Only where a sim disagrees with in-game</label>
    <div class="legend">
      <span class="pill chip win">WIN</span><span class="pill chip loss">LOSS</span><span class="pill chip coinflip">EVEN</span>
      <span>&nbsp;·&nbsp;✓/✗ = matches in-game direction</span>
    </div>
  </div>

  <div class="summary" id="summary"></div>
  <div id="table"></div>

  <div class="foot" id="foot"></div>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const CATLABEL = {expected_win:'Expected win', unexpected_win:'Unexpected win',
  coin_flip:'Coin flip', unexpected_loss:'Unexpected loss', expected_loss:'Expected loss'};
let active = 0;
const $ = (s,el=document)=>el.querySelector(s);

function sign(d){ return d>3?1 : d<-3?-1 : 0; }           // 3% HP margin dead-zone = even
function outClass(o){ return o==='win'?'win':o==='loss'?'loss':'coinflip'; }
function dhp(x){ const c = x>=0?'pos':'neg'; return `<div class="dhp ${c}">${x>=0?'+':''}${x.toFixed(0)}%</div>`; }

function cell(src, ig, cls){
  if(!src) return `<td class="cell ${cls}"><span class="noval">—</span></td>`;
  let mark='';
  if(ig && src!==ig){
    const ok = sign(src.delta)===sign(ig.delta);
    mark = `<span class="mark ${ok?'ok':'no'}">${ok?'✓':'✗'}</span>`;
  }
  const dis = (ig && src!==ig && sign(src.delta)!==sign(ig.delta)) ? 'disagree':'';
  return `<td class="cell ${cls}">
     <span class="chip ${outClass(src.outcome)} ${dis}">${src.outcome==='coinflip'?'EVEN':src.outcome.toUpperCase()}${mark}</span>
     <div class="cnts">${src.n_subject} v ${src.n_opp}</div>
     ${dhp(src.delta)}</td>`;
}

function renderTabs(){
  $('#tabs').innerHTML = DATA.units.map((u,i)=>
    `<div class="tab ${i===active?'active':''}" data-i="${i}">
       ${u.subject.name} <span class="civ">${u.subject.civ}</span></div>`).join('');
  $('#tabs').querySelectorAll('.tab').forEach(t=>t.onclick=()=>{active=+t.dataset.i; render();});
}

function summary(u, rows){
  const rec = u.matchups.filter(m=>m.ingame);
  function acc(srcKey){
    let dirOK=0, err=0, n=0;
    for(const m of rec){ const s=m[srcKey], ig=m.ingame; if(!s) continue;
      n++; if(sign(s.delta)===sign(ig.delta)) dirOK++; err += Math.abs(s.delta-ig.delta); }
    return {n, dir: n?Math.round(100*dirOK/n):null, mae: n?Math.round(err/n):null};
  }
  const v2=acc('v2'), db=acc('db');
  const bar=(label,a,col)=> a.n? `<div class="barrow"><span class="name">${label}</span>
      <div class="bar"><span style="width:${a.dir}%;background:${col}"></span></div>
      <span class="val">${a.dir}%</span></div>` :
      `<div class="barrow"><span class="name">${label}</span><span class="note">no in-game</span></div>`;
  const maeCard = (rec.length)? `
    <div class="card"><h3>HP-margin error vs in-game (MAE)</h3>
      <div class="big">${v2.mae??'—'}<small> V2</small> &nbsp; ${db.mae??'—'}<small> DB</small></div>
      <div class="note">avg |Δhp% − in-game Δhp%| over ${rec.length} recorded fights — lower is better</div></div>`
    : `<div class="card"><h3>In-game</h3><div class="big">0<small> recorded</small></div>
       <div class="note">Kona was flagged (escape hatch) — no showcase fights recorded</div></div>`;
  $('#summary').innerHTML = `
    <div class="card"><h3>Matchups</h3>
      <div class="big">${u.counts.total}<small> total</small></div>
      <div class="note">${u.counts.db} in DB · ${u.counts.ingame} recorded in-game</div></div>
    <div class="card"><h3>Direction match vs in-game</h3>
      ${bar('V2', v2, 'var(--good)')}
      ${bar('DB', db, 'var(--accent)')}
      <div class="note">share of recorded fights where the sim agrees on who wins</div></div>
    ${maeCard}`;
}

function render(){
  renderTabs();
  const u = DATA.units[active];
  const recOnly = $('#recorded').checked, disOnly = $('#disagreeOnly').checked;
  summary(u);
  let html = `<table><thead><tr>
      <th>Opponent</th><th class="src">V2 sim</th><th class="src">Matchup DB</th><th class="src">In-game</th>
    </tr></thead><tbody>`;
  for(const cat of DATA.cat_order){
    let ms = u.matchups.filter(m=>m.category===cat);
    if(recOnly) ms = ms.filter(m=>m.ingame);
    if(disOnly) ms = ms.filter(m=>m.ingame && (
        (m.v2 && sign(m.v2.delta)!==sign(m.ingame.delta)) ||
        (m.db && sign(m.db.delta)!==sign(m.ingame.delta))));
    if(!ms.length) continue;
    html += `<tr class="catrow"><td colspan="4">${CATLABEL[cat]||cat}
       <span class="cnt">${ms.length}</span></td></tr>`;
    for(const m of ms){
      html += `<tr class="m"><td class="opp">
          <div class="nm">${m.opp_name||m.opp_slug}</div>
          <div class="meta">${m.opp_civ} · ${m.opp_class||''}</div></td>
        ${cell(m.v2, m.ingame,'')}
        ${cell(m.db, m.ingame,'')}
        ${cell(m.ingame, null,'ingame')}</tr>`;
    }
  }
  html += `</tbody></table>`;
  $('#table').innerHTML = html;
  $('#foot').innerHTML = `
    <div><b>Reading it:</b> each cell = outcome chip + army counts (subject&nbsp;v&nbsp;opponent) + HP-margin
    (subject&nbsp;HP% − opponent&nbsp;HP% at the end). ✓/✗ on the V2 &amp; DB chips = whether that sim agrees
    with the in-game <i>direction</i>. The three sources use different army caps
    (V2 &amp; in-game cap&nbsp;21, DB cap&nbsp;30), so counts differ by design.</div>
    <div style="margin-top:6px">${DATA.note_weights}</div>`;
}
$('#recorded').onchange = render; $('#disagreeOnly').onchange = render;
render();
</script>
</body>
</html>"""

out = HTML.replace("__DATA__", json.dumps(DATA))
out = (out.replace("__WF__", str(DATA["weights"]["food"]))
          .replace("__WW__", str(DATA["weights"]["wood"]))
          .replace("__WG__", str(DATA["weights"]["gold"]))
          .replace("__SCALE__", DATA["db_scale"])
          .replace("__GEN__", DATA["generated"]))
(HERE / "matchup_dashboard.html").write_text(out, encoding="utf-8")
print("wrote", HERE / "matchup_dashboard.html", f"({len(out)} bytes)")
