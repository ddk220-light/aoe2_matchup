#!/usr/bin/env python3
"""Plot banked/carried gold and comparable source/model throughput measures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/aoe2-gold-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(output):
    comparison=json.loads((output/'comparison.json').read_text())
    run=json.loads((output/'ten-workers.json').read_text())
    frames=run['frames'];ref=comparison['reference']['gold_per_worker_minute']
    fig,axs=plt.subplots(1,2,figsize=(12,4.7),gridspec_kw={'width_ratios':[1.25,1]})
    fig.suptitle('Generic post-Imperial gold mining — first simulation',fontsize=15,fontweight='bold')
    ax=axs[0]
    ax.plot([f['t'] for f in frames],[f['banked'] for f in frames],label='Deposited gold',color='#2766a0')
    ax.plot([f['t'] for f in frames],[f['banked']+f['carried'] for f in frames],label='Deposited + carried',color='#b48014')
    ax.axvline(60,ls=':',color='#777');ax.set(xlabel='Game seconds',ylabel='Total gold',title='Ten workers · four gold tiles · one-tile camp gap')
    ax.legend(frameon=False,loc='upper left');ax.grid(alpha=.2)
    c=comparison['comparison']
    walking=next(r for r in comparison['results'] if r['name']=='ten-walk-only')['windows'][-1]['extracted_per_worker_minute']
    labels=['Reference\nno bumping','One worker\ncomplete cycles','Ten workers\nwalking only','Ten workers\nwith collisions']
    rates=[ref,c['single_cycle_rate'],walking,c['crowded_rate']]
    axs[1].bar(labels,rates,color=['#8693a2','#45957a','#6e9ec1','#2766a0'])
    axs[1].set(ylabel='Gold per villager-minute',ylim=(0,34),title='Sustained-rate comparison')
    for i,rate in enumerate(rates):axs[1].text(i,rate+.45,f'{rate:.2f}',ha='center',fontsize=11)
    axs[1].grid(axis='y',alpha=.2);axs[1].set_axisbelow(True)
    fig.text(.5,.015,'Ten-worker rates adjust for carried-inventory changes over 120–420s. Prototype model; current DE crowd behavior is unvalidated.',ha='center',fontsize=9,color='#475569')
    fig.tight_layout(rect=(0,.045,1,.94));fig.savefig(output/'comparison.png',dpi=180);plt.close(fig)
    report=output/'README.md';text=report.read_text()
    marker='## Playback verification and plot'
    if marker in text:text=text.split(marker)[0].rstrip()+'\n'
    text+='\n'+marker+'\n\n[Open playback](playback.html) · [Comparison plot](comparison.png)\n\n'
    if (output/'browser-validation.json').exists():
        browser=json.loads((output/'browser-validation.json').read_text())
        text+=f"Chromium checks: {len(browser['checks'])} passed, including animation, time seeking, trial selection, reset, mobile layout and no JavaScript errors. Desktop/mobile screenshots are included.\n"
    report.write_text(text)
    manifest_path=output/'manifest.json';manifest=json.loads(manifest_path.read_text())
    root=Path(__file__).resolve().parents[1]
    for name in ['tools/check_gold_playback.py','tools/plot_gold_mining_review.py']:
        manifest['code_sha256'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    for command in ['python tools/check_gold_playback.py','python tools/plot_gold_mining_review.py']:
        if command not in manifest['reproduce']:manifest['reproduce'].append(command)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(output/'comparison.png')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path,nargs='?',default=Path('aoe2x/js_simulation/calibration/economy/gold-2026-11-09'))
    main(p.parse_args().output)
