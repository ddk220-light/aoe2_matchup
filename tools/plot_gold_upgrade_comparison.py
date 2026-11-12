#!/usr/bin/env python3
"""Render unupgraded results and the nine-cell reference check."""
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/aoe2-gold-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
out=root/'aoe2x/js_simulation/calibration/economy/gold-upgrade-comparison-2026-11-09'
r=json.loads((out/'comparison.json').read_text())
grid=r['grid'];crowds={c['name']:c for c in r['crowds']}
fig,axs=plt.subplots(1,2,figsize=(11.5,4.7))
fig.suptitle('Gold gathering without upgrades — reference comparison',fontsize=15,fontweight='bold')
rates=[grid[0]['reference_rate'],grid[0]['simulated_cycle_rate'],
    crowds['ten-no-upgrades-walk-only']['windows'][1]['extracted_per_worker_minute'],
    crowds['ten-no-upgrades']['windows'][1]['extracted_per_worker_minute']]
axs[0].bar(['Reference\nno bumping','One worker\ncomplete cycles','Ten workers\nwalking only','Ten workers\nwith collisions'],rates,
    color=['#8693a2','#45957a','#6e9ec1','#2766a0'])
for i,n in enumerate(rates):axs[0].text(i,n+.3,f'{n:.2f}',ha='center')
axs[0].set(ylabel='Gold per villager-minute',ylim=(0,25),title='No mining, Wheelbarrow or Hand Cart upgrades')
axs[0].grid(axis='y',alpha=.2);axs[0].set_axisbelow(True)
axs[1].plot([21,30],[21,30],color='#8995a1',ls='--',label='Equal rates')
for m,color in enumerate(['#2766a0','#45957a','#ad7b12']):
    group=[g for g in grid if g['mining_level']==m]
    axs[1].scatter([g['reference_rate'] for g in group],[g['simulated_cycle_rate'] for g in group],
        color=color,s=55,label=['No mining upgrades','Gold Mining','Both mining upgrades'][m])
axs[1].set(xlabel='Published gold per villager-minute',ylabel='Simulated gold per villager-minute',
    xlim=(21,30),ylim=(21,30),title='Nine one-worker upgrade combinations')
axs[1].legend(frameon=False,fontsize=9);axs[1].grid(alpha=.2)
fig.text(.5,.012,'Ten-worker rates adjust for inventory changes over 120–420s. Published reference excludes bumping; DE crowd behavior remains unvalidated.',ha='center',fontsize=9,color='#475569')
fig.tight_layout(rect=(0,.045,1,.94));fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
report=out/'README.md';text=report.read_text();marker='## Plot'
if marker in text:text=text.split(marker)[0].rstrip()+'\n'
report.write_text(text+'\n'+marker+'\n\n[Comparison plot](comparison.png) · [Reference grid CSV](reference-grid.csv)\n')
m=json.loads((out/'manifest.json').read_text())
m['code_sha256']['tools/plot_gold_upgrade_comparison.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(out/'comparison.png')
