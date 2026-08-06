import json,collections,glob,math
CH,PA=567,569
HALF={CH:0.20,PA:0.25}
METRICS={
 'euclid'    : lambda a,b: math.hypot(b['x']-a['x'],b['y']-a['y']),
 'manhattan' : lambda a,b: abs(b['x']-a['x'])+abs(b['y']-a['y']),
 'chebyshev' : lambda a,b: max(abs(b['x']-a['x']),abs(b['y']-a['y'])),
 'dx only'   : lambda a,b: abs(b['x']-a['x']),
 'dy only'   : lambda a,b: abs(b['y']-a['y']),
 'octile'    : lambda a,b: (lambda dx,dy: max(dx,dy)+0.41421356*min(dx,dy))(abs(b['x']-a['x']),abs(b['y']-a['y'])),
}
hit=collections.Counter(); tot=0
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
                            F=frames[times[max(0,tidx.get(r['t_ms'],0)-1)]]
                            me=F.get(uid)
                            if me and t in F:
                                ens=[(oid,o) for oid,o in F.items()
                                     if o['master']!=me['master'] and (o.get('hp') or 0)>0]
                                if not ens: continue
                                tot+=1
                                for name,fn in METRICS.items():
                                    if min(ens,key=lambda p:fn(me,p[1]))[0]==t: hit[name]+=1
                    cur=t
print(f'Which distance metric best predicts the chosen target?  ({tot} switches)\n')
print(f"{'metric':>12} {'picks the chosen target':>25}")
print('-'*40)
for name,_ in sorted(METRICS.items(), key=lambda kv: -hit[kv[0]]):
    print(f'{name:>12} {hit[name]/tot*100:24.1f}%')
