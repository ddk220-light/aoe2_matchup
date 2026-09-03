import json,collections,glob,math
CH,PA=567,569
def ang(me,o):
    return math.degrees(math.atan2(o['y']-me['y'],o['x']-me['x']))%360
chosen=collections.Counter(); avail=collections.Counter(); n=0
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
                                n+=1
                                chosen[int(ang(me,F[t])//45)]+=1
                                for oid,o in F.items():
                                    if o['master']!=me['master'] and (o.get('hp') or 0)>0:
                                        avail[int(ang(me,o)//45)]+=1
                    cur=t
print(f'Directional bias of the chosen target ({n} switches)\n')
print(f"{'sector':>12} {'chosen':>8} {'available':>10} {'ratio':>7}")
print('-'*40)
names=['E','NE','N','NW','W','SW','S','SE']
tc=sum(chosen.values()); ta=sum(avail.values())
for k in range(8):
    c=chosen[k]/tc*100; a=avail[k]/ta*100
    print(f'{names[k]:>12} {c:7.1f}% {a:9.1f}% {c/a if a else 0:7.2f}')
print('\nratio 1.00 everywhere = no directional preference (pure distance/other rule)')
