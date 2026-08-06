import json,collections,glob,math,random
CH,PA=567,569
random.seed(11)
def euclid(a,b): return math.hypot(a['x']-b['x'],a['y']-b['y'])
hit=collections.Counter(); tot=0; ctl=collections.Counter()
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
                                # how many allies (incl. me excluded) currently TARGET each enemy
                                load=collections.Counter()
                                enemies=[oid for oid,o in F.items()
                                         if o['master']!=me['master'] and (o.get('hp') or 0)>0]
                                for oid,o in F.items():
                                    if oid==uid or o['master']!=me['master'] or (o.get('hp') or 0)<=0: continue
                                    tt=o.get('target_id')
                                    if tt in F and tt in enemies: load[tt]+=1
                                if not enemies: continue
                                tot+=1
                                mn=min(load.get(e,0) for e in enemies)
                                least=[e for e in enemies if load.get(e,0)==mn]
                                if t in least: hit['least']+=1
                                if random.choice(enemies) in least: ctl['least']+=1
                                # least-targeted, tie-broken by nearest
                                best=min(least,key=lambda e:euclid(me,F[e]))
                                if t==best: hit['least+near']+=1
                                if random.choice(enemies)==best: ctl['least+near']+=1
                    cur=t
print('Does a unit switch to the LEAST-TARGETED enemy (load balancing by assignment)?\n')
print(f'  switches examined            : {tot}')
for k in ['least','least+near']:
    print(f'  {k:12} chosen: {hit[k]:5d} ({hit[k]/tot*100:5.1f}%)   random control {ctl[k]/tot*100:5.1f}%   lift {hit[k]/max(ctl[k],1):.2f}x')
