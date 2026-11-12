#!/usr/bin/env python3
"""Render a standalone forest playback and scientific comparison figure."""
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/aoe2-wood-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'aoe2x/js_simulation/calibration/economy/wood-2026-11-09'
data=json.loads((OUT/'comparison.json').read_text())
runs={n:json.loads((OUT/(n+'.json')).read_text()) for n in ['none-ten','full-ten','full-four-adjacent']}
by_name={t['name']:t for t in data['trials']}
def window(name,a,b):return next(w for w in by_name[name]['windows'] if w['start']==a and w['end']==b)

fig,axs=plt.subplots(1,2,figsize=(12,4.8),gridspec_kw={'width_ratios':[1,1.2]})
fig.suptitle('Wood gathering: upgrades, hauling and a receding woodline',fontsize=15,fontweight='bold')
for j,(label,key,color) in enumerate([('Active work only','nominal','#a7b2bc'),('Minutes 2–7','middle','#5b91b8'),('Minutes 7–12','late','#2766a0')]):
 vals=[]
 for name in ['none-ten','full-ten']:
  vals.append(runs[name]['fixture']['worker']['work_rate']*60 if key=='nominal' else window(name,120,420)['inventory_adjusted_per_worker_minute'] if key=='middle' else window(name,420,720)['inventory_adjusted_per_worker_minute'])
 bars=axs[0].bar([0+(j-1)*.24,1+(j-1)*.24],vals,.23,color=color,label=label)
 for b,v in zip(bars,vals):axs[0].text(b.get_x()+b.get_width()/2,v+.45,f'{v:.2f}',ha='center',fontsize=9)
axs[0].set(xticks=[0,1],xticklabels=['No upgrades','All standard upgrades'],ylabel='Wood per villager-minute',ylim=(0,42))
axs[0].legend(frameon=False,fontsize=9);axs[0].grid(axis='y',alpha=.2);axs[0].set_axisbelow(True)
for name,color,label in [('none-ten','#ad7b12','No upgrades'),('full-ten','#2766a0','All standard upgrades')]:
 r=runs[name];s={round(v['t']):v for v in r['snapshots']};rates=[]
 for a in range(0,720,60):rates.append((s[a+60]['extracted']-s[a]['extracted'])/10)
 axs[1].plot([a+.5 for a in range(12)],rates,marker='o',markersize=4,color=color,label=label)
axs[1].set(xlabel='Game minutes (one-minute windows)',ylabel='Inventory-adjusted wood per villager-minute',ylim=(0,40),title='Ten workers · fixed camp · finite forest')
axs[1].legend(frameon=False,fontsize=9);axs[1].grid(alpha=.2)
fig.text(.5,.012,'Each tree contains 100 wood. One-tile camp gap; no camp rebuilding. Prototype navigation and felling timing remain unvalidated against current DE.',ha='center',fontsize=9,color='#475569')
fig.tight_layout(rect=(0,.045,1,.94));fig.savefig(OUT/'comparison.png',dpi=180);plt.close(fig)

playback={name:{'fixture':r['fixture'],'options':r['options'],'frames':r['frames']} for name,r in runs.items()}
none=window('none-ten',120,420);full=window('full-ten',120,420);late=window('full-ten',420,720)
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wood gathering review</title>
<style>body{margin:0;background:#f3f5f7;color:#182635;font:16px system-ui,sans-serif}main{max-width:1180px;margin:28px auto;padding:0 18px}h1{font-size:26px}.note{background:#fff5d6;border-left:4px solid #c28a13;padding:12px 16px}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}.panel{min-width:0;background:white;border:1px solid #dce2e8;border-radius:10px;padding:18px}canvas{width:100%;display:block}button,select{font:inherit;padding:7px;max-width:100%}input{width:100%;margin:16px 0}p{line-height:1.5}small{color:#536476}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;border-bottom:1px solid #dce2e8;text-align:left}.stats{line-height:1.7;font-variant-numeric:tabular-nums}a{color:#145ca5}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style>
<main><h1>Wood gathering: harvesting a finite forest</h1><p class="note">Prototype estimates from the supplied game data. Tree felling and current DE crowd behavior still need same-layout validation.</p>
<div class="grid"><section class="panel"><select id="trial"><option value="none-ten">Ten workers · no upgrades</option><option value="full-ten">Ten workers · all standard eco upgrades</option><option value="full-four-adjacent">Four workers · full upgrades · adjacent camp</option></select>
<canvas id="map" width="680" height="660"></canvas><button id="play">Play</button> <button id="reset">Reset</button> <select id="speed"><option value="1">1×</option><option value="5" selected>5×</option><option value="20">20×</option></select><input id="time" type="range" min="0" max="720" step=".5" value="0"><div class="stats" id="stats"></div>
<p><small>Green trees: standing. Brown: felled wood remaining. Gray: depleted and passable. Purple workers: felling. Green: collecting. Orange: carrying to camp. Blue: walking to trees.</small></p></section>
<section class="panel"><h2>Wood per villager-minute</h2><table><tr><th>Ten workers</th><th>Minutes 2–7</th><th>Minutes 7–12</th></tr>
<tr><td>No upgrades</td><td>@@NONE@@</td><td>@@NONELATE@@</td></tr><tr><td>All standard upgrades</td><td>@@FULL@@</td><td>@@LATE@@</td></tr></table>
<p>Rates include deposited wood plus changes in carried inventory. The camp stays fixed, so travel increases as the forest is depleted.</p>
<canvas id="chart" width="600" height="310"></canvas><small>Blue: deposited wood. Gold: deposited + carried. Line: selected time.</small>
<h2>Published comparison</h2><p><a href="https://www.reddit.com/r/aoe2/comments/1ilig6h/">2025 test</a>, four workers per camp over 14 minutes: 23.5 wood/min with Double-Bit Axe, 31.6 fully upgraded. Our related one-tile-gap cases: @@DBA@@ and @@LOWFULL@@. Exact forest geometry and endpoint inventory treatment differ or are unspecified.</p>
<p>Raw source work: 0.39 wood/s, or 0.61776 after all three wood upgrades. Carry: 10 or 20 with Wheelbarrow + Hand Cart. Standard eco runs exclude Sappers.</p>
<p>Default felling uses source 20 HP, summed attack 15, a two-second reload, and an assumed first impact halfway through the current two-second animation. Historical felling timing is tested separately.</p></section></div></main>
<script>const DATA=@@DATA@@;const $=id=>document.getElementById(id),ctx=$('map').getContext('2d'),cg=$('chart').getContext('2d');
let playing=false,last=null,cursor=0;const colors={gathering:'#238454',felling:'#8a4c9f',to_tree:'#2c71b8',to_camp:'#c06d1a',idle:'#777'};
function render(){const r=DATA[$('trial').value],f=r.frames[Math.min(r.frames.length-1,Math.round(+$('time').value/.5))],forest=r.fixture.forest;
ctx.clearRect(0,0,680,660);const S=54,X=x=>32+(x-8)*S,Y=y=>20+(y-9)*S;ctx.strokeStyle='#e5e9ef';ctx.lineWidth=1;
for(let i=8;i<=20;i++){ctx.beginPath();ctx.moveTo(X(i),Y(9));ctx.lineTo(X(i),Y(20));ctx.stroke();ctx.beginPath();ctx.moveTo(X(8),Y(i));ctx.lineTo(X(20),Y(i));ctx.stroke();}
ctx.textAlign='center';ctx.font='12px system-ui';f.remaining.forEach((wood,i)=>{const x=forest.x+i%forest.width,y=forest.y+Math.floor(i/forest.width);ctx.fillStyle=wood<1e-7?'#e7e9e9':f.tree_hp[i]>0?'#8abd83':'#c4a778';ctx.fillRect(X(x),Y(y),S,S);ctx.strokeStyle='white';ctx.strokeRect(X(x),Y(y),S,S);if(wood>1e-7){ctx.fillStyle='#263c2a';ctx.fillText(wood.toFixed(0),X(x+.5),Y(y+.55));}});
const camp=r.fixture.camp,y=forest.y+forest.depth+r.options.gap;ctx.fillStyle='#82715e';ctx.fillRect(X(camp.center[0]-camp.half_width),Y(y),S*2,S*2);ctx.fillStyle='white';ctx.font='14px system-ui';ctx.fillText('Lumber Camp',X(camp.center[0]),Y(y+1));
f.agents.forEach(w=>{ctx.beginPath();ctx.fillStyle=colors[w.state];ctx.arc(X(w.x),Y(w.y),r.fixture.worker.radius*S,0,Math.PI*2);ctx.fill();ctx.strokeStyle='white';ctx.stroke();ctx.fillStyle='#14283b';ctx.font='11px system-ui';ctx.fillText((w.id+1)+':'+w.inventory.toFixed(1),X(w.x),Y(w.y)-14);});
$('stats').textContent='Time '+f.t.toFixed(1)+' s · Banked '+f.banked.toFixed(2)+' · Carried '+f.carried.toFixed(2)+' · Extracted '+(f.banked+f.carried).toFixed(2)+' · Depleted trees '+f.depleted;
cg.clearRect(0,0,600,310);const max=Math.max(...r.frames.map(v=>v.banked+v.carried)),XX=t=>42+t/r.options.duration*535,YY=g=>270-g/(max||1)*240;cg.strokeStyle='#d5dde5';cg.beginPath();cg.moveTo(42,25);cg.lineTo(42,270);cg.lineTo(577,270);cg.stroke();
for(const [color,total] of [['#2766a0',false],['#b48012',true]]){cg.beginPath();cg.strokeStyle=color;r.frames.forEach((v,i)=>{const x=XX(v.t),y=YY(v.banked+(total?v.carried:0));i?cg.lineTo(x,y):cg.moveTo(x,y);});cg.stroke();}
cg.strokeStyle='#9c4660';cg.beginPath();cg.moveTo(XX(f.t),25);cg.lineTo(XX(f.t),270);cg.stroke();cg.fillStyle='#536476';cg.font='12px system-ui';cg.fillText('0 s',35,292);cg.fillText(r.options.duration+' s',535,292);cg.fillText(max.toFixed(0)+' wood',45,17);}
$('play').onclick=()=>{playing=!playing;last=null;$('play').textContent=playing?'Pause':'Play';};$('reset').onclick=()=>{cursor=0;$('time').value=0;render();};$('time').oninput=()=>{cursor=+$('time').value;render();};$('trial').onchange=()=>{const max=DATA[$('trial').value].options.duration;$('time').max=max;cursor=Math.min(cursor,max);$('time').value=cursor;render();};
function animate(t){if(playing&&last!==null){cursor=Math.min(+$('time').max,cursor+(t-last)/1000*+$('speed').value);$('time').value=cursor;render();if(cursor>=+$('time').max){playing=false;$('play').textContent='Play';}}last=t;requestAnimationFrame(animate);}render();requestAnimationFrame(animate);</script></html>'''
for key,value in {'NONE':none['inventory_adjusted_per_worker_minute'],'NONELATE':window('none-ten',420,720)['inventory_adjusted_per_worker_minute'],
 'FULL':full['inventory_adjusted_per_worker_minute'],'LATE':late['inventory_adjusted_per_worker_minute'],
 'DBA':window('double-bit-four-gap-one',0,840)['inventory_adjusted_per_worker_minute'],
 'LOWFULL':window('full-four-gap-one',0,840)['inventory_adjusted_per_worker_minute']}.items():html=html.replace('@@'+key+'@@',f'{value:.2f}')
html=html.replace('@@DATA@@',json.dumps(playback,separators=(',',':')).replace('<','\\u003c'))
(OUT/'playback.html').write_text(html)
report=OUT/'README.md';text=report.read_text();marker='## Plot and playback'
if marker in text:text=text.split(marker)[0].rstrip()+'\n'
report.write_text(text+'\n'+marker+'\n\n[Interactive forest playback](playback.html) · [Comparison plot](comparison.png)\n')
manifest=OUT/'manifest.json';m=json.loads(manifest.read_text());m['code_sha256']['tools/render_wood_review.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();manifest.write_text(json.dumps(m,indent=2)+'\n')
print(OUT/'playback.html')
