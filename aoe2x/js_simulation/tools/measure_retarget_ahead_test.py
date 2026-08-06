import json,collections,glob,math
CH,PA=567,569
chosen=collections.Counter(); avail=collections.Counter(); n=0
BINS=[(0,45,'ahead 0-45'),(45,90,'45-90'),(90,135,'135'),(135,180,'behind 135-180')]
def binof(a):
    for lo,hi,name in BINS:
        if lo<=a<hi: return name
    return BINS[-1][2]
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
            for j,r in enumerate(s):
                if r.get('hp') is not None and r['hp']<=0: break
                t=r.get('target_id')
                if t in (None,-1,0): t=None
                if t is not None and t!=cur:
                    if cur is not None and j>=6:
                        dd=death.get(cur)
                        if dd is None or r['t_ms']<dd-100:
                            F=frames[times[max(0,tidx.get(r['t_ms'],0)-1)]]
                            me=F.get(uid); p=s[j-6]
                            vx,vy=me['x']-p['x'],me['y']-p['y'] if me else (0,0)
                            sp=math.hypot(vx,vy)
                            if me and t in F and sp>1e-3:
                                def rel(o):
                                    dx,dy=o['x']-me['x'],o['y']-me['y']
                                    dd2=math.hypot(dx,dy)
                                    if dd2<1e-9: return 0.0
                                    c=max(-1,min(1,(vx*dx+vy*dy)/(sp*dd2)))
                                    return math.degrees(math.acos(c))
                                n+=1
                                chosen[binof(rel(F[t]))]+=1
                                for oid,o in F.items():
                                    if o['master']!=me['master'] and (o.get('hp') or 0)>0:
                                        avail[binof(rel(o))]+=1
                    cur=t
print(f'Is the chosen target AHEAD of the unit\'s current motion?  ({n} switches)\n')
print(f"{'angle from heading':>20} {'chosen':>8} {'available':>10} {'ratio':>7}")
print('-'*50)
tc=sum(chosen.values()); ta=sum(avail.values())
for _,_,name in BINS:
    c=chosen[name]/tc*100 if tc else 0; a=avail[name]/ta*100 if ta else 0
    print(f'{name:>20} {c:7.1f}% {a:9.1f}% {(c/a if a else 0):7.2f}')
