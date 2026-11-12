#!/usr/bin/env python3
"""Render inspectable farm layout, movement playback and uncertainty report."""
import hashlib
import json
import os
import sys
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/farm-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'aoe2x/js_simulation/calibration/economy/farms-2026-11-09'
def read(name):return json.loads((OUT/name).read_text())
def main():
    data=read('comparison.json');fixture=read('fixture-full.json')
    def summary(p):return next(s for s in data['summaries'] if s['profile']==p)
    def trial(n):return next(t for t in data['trials'] if t['name']==n)
    def rate(n):return trial(n)['windows'][-1]['food_per_worker_minute']
    names={'none':'No upgrades','wheelbarrow':'Wheelbarrow','wheelbarrow-plow':'Wheelbarrow + Heavy Plow','full':'All standard eco upgrades'}
    fig,axes=plt.subplots(1,2,figsize=(13,5.3),layout='constrained')
    for ax,p in zip(axes,['none','full']):
        rows=summary(p)['windows'][-1]['per_farm']
        for f,w in zip(fixture['farms'],rows):
            shade=plt.cm.YlGn((w['food_per_minute']-14)/12)
            ax.add_patch(Rectangle((f['x0'],f['y0']),3,3,facecolor=shade,edgecolor='white',linewidth=2))
            ax.text(f['x0']+1.5,f['y0']+1.5,f"Farm {f['id']+1}\n{w['food_per_minute']:.2f}",ha='center',va='center',fontsize=10)
        ax.add_patch(Rectangle((0,0),2,2,facecolor='#845b3b'));ax.text(1,1,'Mill',ha='center',va='center',color='white')
        ax.set(xlim=(-6.3,8.3),ylim=(-3.3,6.3),aspect='equal',title=names[p],xlabel='Tiles',ylabel='Tiles')
        ax.invert_yaxis()
    fig.suptitle('Food per farmer/minute · first 10 minutes · mean of five seeds\nTen farms, one mill; reseeding included; model estimates',fontsize=14)
    fig.savefig(OUT/'layout-rates.png',dpi=150);plt.close(fig)
    lines=['# Generic farming simulation review','',
           '**Experimental model, not a verified reproduction of current DE farmer trajectories.**','',
           'Ten passable 3×3 farms surround one solid 2×2 mill: eight in a compact pinwheel and two outside the east/west farms. Flat terrain, one farmer per farm, no civilization bonuses. Coordinates are in the fixtures. Initial mill/farm construction is excluded; reseeding is enabled in the measured runs. All times are game seconds.','',
           '![Farm layout and rates](layout-rates.png)','',
           '## Source-backed inputs','',
           f"User DAT SHA-256: `{fixture['source']['game_source']['sha256']}`. The reviewed raw extract and selected numeric effect commands are exported alongside each fixture. Source date is not an executable-patch identifier.",'',
           '| Parameter | No upgrades | All standard upgrades |','|---|---:|---:|',
           '| Farmer active harvest rate | 0.53 food/s | 0.53 food/s |',
           '| Farm available-food replenishment | 0.40 food/s | 0.40 food/s |',
           '| Available-food pool capacity | 15 | 15 |',
           '| Farmer carry capacity (rounded model) | 10 | 21 |',
           '| Movement speed | 0.800 tiles/s | 0.968 tiles/s |',
           '| Farm food budget | 175 | 550 |',
           '| Farm wood / single-builder time | 60 wood / 15s | 60 wood / 15s |','',
           'Full profile: Horse Collar, Heavy Plow, Crop Rotation, Wheelbarrow and Hand Cart. Heavy Plow adds one carrying capacity; the mill upgrades otherwise increase farm lifetime. Treadmill Crane is outside this standard economic profile. The source mill costs 100 wood. Ten starting farms plus mill therefore represent 700 wood, excluded from recurring income.','',
           '## Rates','',
           'Means across five seeds. Harvested food includes banked food plus the change in carried inventory; carried food is not yet spendable.','',
           '| Profile | First minute, harvested | Minutes 2–7, harvested | First 10 min, harvested | First 10 min, banked |','|---|---:|---:|---:|---:|']
    for s in data['summaries']:
        a,b,c=s['windows'];lines.append(f"| {names[s['profile']]} | {a['food_per_worker_minute']:.2f} | {b['food_per_worker_minute']:.2f} | {c['food_per_worker_minute']:.2f} | {c['banked_per_worker_minute']:.2f} |")
    lines += ['', 'A window can temporarily exceed 24 food/minute by drawing down food accumulated in the farm pool before that window. The zero-pool simulation from time zero respects the total production bound. Its first minute also contains initial travel and incomplete delivery cycles.','',
              '## Travel and working time','',
              'Mean seconds per farmer in the first 600 seconds (five seeds).','',
              '| Profile | Working | Internal walking | Walk to mill | Walk back | Blocked | Rebuilding |','|---|---:|---:|---:|---:|---:|---:|']
    for p in ['none','full']:
        fs=summary(p)['windows'][-1]['per_farm']
        lines.append('| '+names[p]+' | '+' | '.join(f"{sum(f[k] for f in fs)/len(fs):.1f}" for k in ['working','internal_walking','outbound_walking','return_walking','blocked','building'])+' |')
    lines += ['', 'Initial travel and any idle time account for the remaining seconds. Standing time is computed from the food harvested at each spot and pool availability; it is not a fixed animation timer. Nominal four-stop model: a base quarter-load takes 4.72s at full harvest rate or 6.25s with an empty pool; a 21-capacity quarter-load takes 9.91–13.13s. Walking time follows actual route length and speed. Deposits occur at mill contact; any deposit-animation delay remains unverified.','',
              '| Farm | Placement | No upgrades: food/min | Full: food/min | No upgrades: deposit round trips (s) | Full: deposit round trips (s) |','|---|---|---:|---:|---:|---:|']
    for a,b in zip(summary('none')['windows'][-1]['per_farm'],summary('full')['windows'][-1]['per_farm']):
        lines.append(f"| {int(a['id'])+1} | {a['position']} | {a['food_per_minute']:.2f} | {b['food_per_minute']:.2f} | {a['outbound_walking']+a['return_walking']:.1f} | {b['outbound_walking']+b['return_walking']:.1f} |")
    lines += ['', '## Sustained runs and sensitivity','', '| Profile | First 30 min: harvested food/min | First 30 min: banked food/min | Reseed wood, all ten farms |','|---|---:|---:|---:|']
    for p in ['none','full']:
        w=trial(p+'-sustained')['windows'][-1]
        lines.append(f"| {names[p]} | {w['food_per_worker_minute']:.2f} | {w['banked_per_worker_minute']:.2f} | {w['wood']:.0f} |")
    lines += ['', 'Reseed wood is reported separately, not subtracted from food or converted to labor. Rebuilding assumes a funded external wood budget, final partial-load deposit, return to the previous work spot, and the source single-builder time. This sequence is an approximation pending current-engine observation.','',
              '| Diagnostic, seed 0 unless stated | No upgrades: food/min | Full: food/min |','|---|---:|---:|']
    for label,suffix in [('Four stops, empty initial pool','-seed-0'),('Five stops every load (stress case)','-five-stops'),('No worker collisions','-no-collisions'),('Initially full pool (different starting condition)','-full-initial-pool')]:
        lines.append(f"| {label} | {rate('none'+suffix):.3f} | {rate('full'+suffix):.3f} |")
    numerical=[]
    for p in ['none','full']:
        fine=sum(rate(p+f'-fine-step-{i}') for i in range(5))/5
        coarse=summary(p)['windows'][-1]['food_per_worker_minute']
        change=(fine/coarse-1)*100
        numerical.append(dict(profile=p,coarse=coarse,fine=fine,mean_change_percent=change))
        lines.append(f"| {names[p]} timestep 80→160 Hz, five-seed mean change | {change:+.3f}% | — |")
    lines += ['', 'Five stops on every load is a sensitivity bound, not a claim that this is normal generic behavior. Seeds change stochastic work-spot selection. Neither mean agreement nor timestep stability validates DE pathfinding.','',
              '## External checks and limits','',
              '- The [official 50292 patch](https://www.ageofempires.com/news/aoe2de-update-50292/) confirms centered farm work; the old left-biased grid is not used.',
              '- The [historical DE experiment](https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114) measured about 20.3 / 22.78 / 23.16 / 24.4 food per minute for no upgrades / Wheelbarrow / Wheelbarrow + Heavy Plow / Hand Cart + Heavy Plow. It used eight farms around a TC, an older movement layout, warm-up and forced final deposits. These are broad reference values, not matched tests of this mill layout.',
              '- A [2025 multiplayer follow-up](https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/) supports the 24/min production ceiling and an initially empty pool. The author retracted higher single-player rates. It also reports irregular 20/21-food deliveries and slight excess lifetime yield; those details are not reproduced here.',
              '- [DE Infosheet](https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705) and [work-cycle observations](https://www.reddit.com/r/aoe2/comments/kmj7wo/quantum_farming_equation_pilot_cycles_mayan/) support internal moves but show variable portions and extra stops. The latter predates centered work. Exact selection probabilities, stop thresholds, return targets, collision behavior and drop animations remain unresolved.',
              '- AoEBuddy uses its own simulation engine, so its outputs are excluded as independent DE validation.','',
              '## Extension boundaries','',
              'The engine separates farm replenishment/buffer/lifetime, villager harvesting, carrying, internal movement, deposits and rebuilds. Khmer source effects include technology 654 / effect 690, a ×0.95 farmer work modifier and a separate instant-deposit hook. Their eventual implementation must preserve internal movement and apply both effects. Pastures and completion-triggered food payouts require different resource/event behavior; neither is implemented as a generic percentage bonus here.','',
              'Before comparing small civilization bonuses, capture one near and one outer generic farmer across several complete cycles, recording positions, carried food, banked food and farm state at a known game speed/patch. Check stop intervals, return destinations, contact/deposit timing, integer rounding and one depletion/reseed. This prototype is inspectable and conservative about its evidence; current-DE trajectory accuracy remains open.','',
              '## Files and checks','',
              '`playback.html` shows movement, working spots, food pools and deposits. Click a farm to inspect its farmer. Trace JSON contains timestamped state transitions and deposits; CSV contains every scenario/window. Eleven mechanics tests cover source profiles, exact pool accounting, carry/deposit boundaries, geometry, time accounting, reseeding and deterministic seeds.','']
    (OUT/'README.md').write_text('\n'.join(lines))
    playback={}
    for p in ['none','full']:
        run=read(p+'-seed-0.json')
        playback[p]={k:run[k] for k in ['fixture','options','frames','events']}
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generic farming review</title>
<style>body{font:16px system-ui;margin:24px auto;max-width:1100px;padding:0 14px;background:#f4f6f2;color:#203429}h1{font-size:26px}canvas{width:100%;background:white;border-radius:10px}button,select,input{font:inherit;margin:5px}input[type=range]{width:min(55vw,500px)}#stats,#detail{padding:12px;background:white;border-radius:8px;margin:10px 0}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;padding:5px;border-bottom:1px solid #ddd}.scroll{overflow:auto}small{display:block;margin:10px 0;color:#47584b}</style>
<h1>Ten farms · one mill</h1><p>Generic prototype. Click a farm to inspect its worker. Centered working spots; farm production and villager harvesting are separate.</p>
<select id="profile"><option value="none">No upgrades</option><option value="full">All standard eco upgrades</option></select><button id="play">Play</button><button id="reset">Reset</button><input id="time" aria-label="Game seconds" type="range" min="0" max="600" step="0.01" value="0"><div id="stats"></div>
<canvas id="map" width="1000" height="630"></canvas><div id="detail"></div><small>Green: harvesting · blue: walking · orange: depositing/rebuilding. Brown square: mill. Dots: possible work spots. Farms are passable. Results include carried food separately from the stockpile. This replay is our model, not a DE recording.</small>
<div class="scroll"><table><thead><tr><th>Game time</th><th>Event</th><th>Food carried / deposited</th></tr></thead><tbody id="events"></tbody></table></div>
<script>const DATA=__DATA__;const canvas=document.getElementById('map'),ctx=canvas.getContext('2d'),slider=document.getElementById('time');let selected=0,playing=false,last=0;
const X=x=>40+(x+6)*65,Y=y=>30+(y+3)*65;function run(){return DATA[document.getElementById('profile').value]}
function draw(){const r=run(),t=+slider.value,f=r.frames[Math.min(r.frames.length-1,Math.round(t*2))];ctx.clearRect(0,0,1000,630);
 for(const farm of r.fixture.farms){const state=f.farms[farm.id];ctx.fillStyle=state.rebuilding?'#e9c894':'#dfeacd';ctx.fillRect(X(farm.x0),Y(farm.y0),195,195);ctx.strokeStyle=farm.id===selected?'#ad4f13':'white';ctx.lineWidth=farm.id===selected?4:2;ctx.strokeRect(X(farm.x0),Y(farm.y0),195,195);ctx.fillStyle='#37573b';ctx.font='16px system-ui';ctx.fillText('Farm '+(farm.id+1),X(farm.x0)+8,Y(farm.y0)+22);ctx.font='12px system-ui';ctx.fillText('Pool '+state.pool.toFixed(1)+' · left '+(state.pool+state.reserve).toFixed(0),X(farm.x0)+8,Y(farm.y1)-10);for(const x of [.5,1.5,2.5])for(const y of [.5,1.5,2.5]){ctx.beginPath();ctx.arc(X(farm.x0+x),Y(farm.y0+y),2,0,7);ctx.fill();}}
 ctx.fillStyle='#845b3b';ctx.fillRect(X(0),Y(0),130,130);ctx.fillStyle='white';ctx.font='20px system-ui';ctx.fillText('Mill',X(.7),Y(1.1));
 for(const b of f.agents){ctx.fillStyle=b.state==='gather'?'#1e7b49':(['build','deposit'].includes(b.state)?'#d77d1f':'#2976ac');ctx.beginPath();ctx.arc(X(b.x),Y(b.y),r.fixture.worker.radius*65,0,7);ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=2;ctx.stroke();}
 document.getElementById('stats').textContent=`Time ${f.t.toFixed(1)} s · Banked ${f.banked.toFixed(2)} food · Carried ${f.carried.toFixed(2)} · Reseed wood ${f.wood}`;
 const b=f.agents[selected],farm=f.farms[selected];document.getElementById('detail').textContent=`Farm ${selected+1}: ${b.state} · carrying ${b.inventory.toFixed(2)} / ${r.fixture.worker.carry_capacity} · available pool ${farm.pool.toFixed(2)} / ${r.fixture.farm.pool_capacity} · reseeds ${farm.reseeds}`;
 const ev=r.events.filter(e=>e.worker===selected&&e.t<=f.t).slice(-12).reverse();document.getElementById('events').innerHTML=ev.map(e=>`<tr><td>${e.t.toFixed(2)}</td><td>${e.event==='deposit'?'Deposit':e.event==='depleted'?'Farm depleted':e.from+' → '+e.to}</td><td>${(e.food??e.inventory).toFixed(2)}</td></tr>`).join('');}
 canvas.addEventListener('click',e=>{const b=canvas.getBoundingClientRect(),x=(e.clientX-b.left)*1000/b.width,y=(e.clientY-b.top)*630/b.height;const f=run().fixture.farms.find(f=>x>=X(f.x0)&&x<=X(f.x1)&&y>=Y(f.y0)&&y<=Y(f.y1));if(f){selected=f.id;draw();}});
 slider.addEventListener('input',draw);document.getElementById('profile').addEventListener('change',draw);document.getElementById('reset').onclick=()=>{slider.value=0;draw()};document.getElementById('play').onclick=()=>{playing=!playing;document.getElementById('play').textContent=playing?'Pause':'Play'};
 function animate(now){if(playing&&last){slider.value=Math.min(600,+slider.value+(now-last)*.01);draw();if(+slider.value>=600){playing=false;document.getElementById('play').textContent='Play';}}last=now;requestAnimationFrame(animate)}draw();requestAnimationFrame(animate);
</script></html>'''
    (OUT/'playback.html').write_text(template.replace('__DATA__',json.dumps(playback,separators=(',',':'))))
    (OUT/'numerical-validation.json').write_text(json.dumps(numerical,indent=2)+'\n')
    print('Rendered farm report, layout and playback')

if __name__=='__main__':main()
