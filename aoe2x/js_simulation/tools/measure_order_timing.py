import zipfile,json,collections,os,glob,random,bisect
random.seed(3)
Z=zipfile.ZipFile('C:/Users/ddk22/Downloads/aoe2_golden_basics_championvspaladin_2026-08-05_complete (2).zip')
orders={}
for n in Z.namelist():
    if not n.endswith('.commands.jsonl'): continue
    tag=os.path.basename(n).replace('.commands.jsonl','').split('__')[1]
    ts=[json.loads(l)['t'] for l in Z.read(n).decode('utf8','replace').strip().split('\n')
        if l.strip() and json.loads(l).get('kind')=='aiOrder']
    orders[tag]=sorted(ts)
CH,PA=567,569
WIN=[0.05,0.1,0.2,0.3,0.5,1.0]
hit=collections.Counter(); ctl=collections.Counter(); tot=0
switch_times=[]
for path in sorted(glob.glob('cvp92/*.tape_trace.jsonl')):
    tag=os.path.basename(path).split('.')[0]
    ot=orders.get(tag)
    if not ot: continue
    by=collections.defaultdict(list)
    for line in open(path):
        r=json.loads(line)
        if r.get('master') in (CH,PA): by[r['id']].append(r)
    for s in by.values(): s.sort(key=lambda r:r['t_ms'])
    death={}
    for uid,s in by.items():
        for r in s:
            if r.get('hp') is not None and r['hp']<=0: death[uid]=r['t_ms']; break
    END=max(death.values())/1000.0 if death else 30
    for uid,s in by.items():
        cur=None
        for r in s:
            if r.get('hp') is not None and r['hp']<=0: break
            t=r.get('target_id')
            if t in (None,-1,0): t=None
            if t is not None and t!=cur:
                if cur is not None:
                    dd=death.get(cur)
                    if dd is None or r['t_ms']<dd-100:
                        st=r['t_ms']/1000.0
                        tot+=1
                        rt=random.uniform(0,END)
                        for w in WIN:
                            i=bisect.bisect_right(ot,st)
                            if i>0 and st-ot[i-1]<=w: hit[w]+=1
                            j=bisect.bisect_right(ot,rt)
                            if j>0 and rt-ot[j-1]<=w: ctl[w]+=1
                cur=t
print(f'Do voluntary target switches follow an aiOrder?  ({tot} switches, 92 fights)\n')
print(f"{'window after order':>20} {'switches':>10} {'random control':>16} {'lift':>7}")
print('-'*58)
for w in WIN:
    h=hit[w]/tot*100; c=ctl[w]/tot*100
    print(f'{w:17.2f}s {h:9.1f}% {c:15.1f}% {(h/c if c else 0):7.2f}x')
