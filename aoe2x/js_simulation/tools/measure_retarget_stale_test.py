import json,collections,glob,math
CH,PA=567,569
def euclid(a,b): return math.hypot(a['x']-b['x'],a['y']-b['y'])
LAGS=[0,100,200,300,500,700,1000,1400,2000,3000]
hit=collections.Counter(); tot=collections.Counter()
for d in ['cvc','pvp','cvp92']:
    for path in sorted(glob.glob(f'{d}/*.tape_trace.jsonl')):
        by=collections.defaultdict(list); frames=collections.defaultdict(dict)
        for line in open(path):
            r=json.loads(line)
            if r.get('master') in (CH,PA): by[r['id']].append(r); frames[r['t_ms']][r['id']]=r
        for s in by.values(): s.sort(key=lambda r:r['t_ms'])
        death={}
        for uid,s in by.items():
            for r in s:
                if r.get('hp') is not None and r['hp']<=0: death[uid]=r['t_ms']; break
        times=sorted(frames); tidx={t:i for i,t in enumerate(times)}
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
                            i=tidx.get(r['t_ms'],0)
                            for lag in LAGS:
                                j=max(0,i-int(lag/16.75))
                                F=frames[times[j]]
                                me=F.get(uid)
                                if not me or t not in F: continue
                                ens=[(euclid(me,o),oid) for oid,o in F.items()
                                     if o['master']!=me['master'] and (o.get('hp') or 0)>0]
                                if not ens: continue
                                tot[lag]+=1
                                if min(ens)[1]==t: hit[lag]+=1
                    cur=t
print('Is the chosen target the NEAREST enemy as of some EARLIER frame?')
print('(if the engine re-scans on a stale snapshot, hit rate should peak at a lag > 0)\n')
print(f"{'lag':>7} {'cases':>7} {'chose the nearest':>19}")
print('-'*36)
for lag in LAGS:
    if tot[lag]: print(f'{lag:5d}ms {tot[lag]:7d} {hit[lag]/tot[lag]*100:18.1f}%')
