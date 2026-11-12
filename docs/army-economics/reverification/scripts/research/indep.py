"""Independent per-civ tech cost/time model: aoe2techtree base (update 188329) + hand-coded civ rules from civ help texts / wiki."""
import json, csv, os
HERE=os.path.dirname(os.path.abspath(__file__)); BASE=os.path.dirname(HERE)
O=json.load(open(os.path.join(BASE,'online_ref.json')))
REF=O['ref']; AVAIL={c:set(v) for c,v in O['avail'].items()}
RES={'f':'Food','w':'Wood','g':'Gold','s':'Stone'}
BS={67,68,75,74,76,77,80,81,82,199,200,201,211,212,219}
STD_BLD={**{t:'Blacksmith' for t in BS},
 **{t:'University' for t in (93,47,377,373,374,375,907,908,909,910)},
 **{t:'Barracks' for t in (222,207,217,264,197,429,875,215,602)},
 **{t:'Archery Range' for t in (100,237,98,218,436,437)},
 **{t:'Stable' for t in (39,435,209,265,254,428,236,715,786)},
 **{t:'Siege Workshop' for t in (96,255,257,320,239,980)},
 **{t:'Dock' for t in (34,35,376,244,905)},
 315:'Castle'}
CONSCRIPT={'Barracks','Archery Range','Stable','Castle','Krepost','Donjon'}
TEAM_WR={('Britons','Archery Range'):1.1,('Goths','Barracks'):1.2,('Huns','Stable'):1.2,('Bulgarians','Blacksmith'):1.8,
         ('Malians','University'):1.8,('Celts','Siege Workshop'):1.2,('Lithuanians','Monastery'):1.2}
FREE={'Bulgarians':{222,207,217,264},'Ethiopians':{197},'Koreans':{211,212,219},'Magyars':{67,68,75},'Malay':{74,76,77},
      'Slavs':{602,875},'Tatars':{436,437},'Turks':{47,254,428},'Vietnamese':{315},'Wu':{374,375}}
SIEGE_FORT_JUR={96,255,239,980,377,257,320}
def expected(civ,tid,bld,unique_castle=False):
    """returns (upfront dict f,w,g,s ; reward gold ; seconds ; notes)"""
    r=REF.get(str(tid))
    if r is None: return None
    base={k:float(r['cost'].get(n,0)) for k,n in RES.items()}; t=float(r['time'])
    bld=STD_BLD.get(tid,bld)
    notes=[]
    up=dict(base)
    if tid in FREE.get(civ,()):
        return {k:0.0 for k in RES},0.0,0.0,['free (civ bonus)']
    def mul(keys,m,why):
        for k in keys: up[k]*=m
        notes.append(why)
    if civ=='Bulgarians' and bld in ('Blacksmith','Siege Workshop'): mul('f',.5,'Bulgarians BS/SW -50% food')
    if civ=='Burgundians' and bld=='Stable': mul('fwgs',.5,'Burgundians stable techs -50%')
    if civ=='Chinese': mul('fwgs',.85,'Chinese -15% (Imperial)')
    if civ=='Danes' and bld in ('Barracks','Siege Workshop'): mul('g',.34,'Danes barracks/SW -66% gold')
    if civ=='Dravidians' and bld=='Barracks': mul('fwgs',.5,'Dravidians barracks -50%')
    if civ=='Italians' and bld in ('Dock','University'): mul('fwgs',.75,'Italians dock/univ -25%')
    if civ=='Jurchens' and tid in SIEGE_FORT_JUR: mul('w',.25,'Jurchens siege/fort -75% wood')
    if civ=='Khitans' and tid==218: mul('fwgs',.5,'Khitans HCA -50%')
    if civ=='Poles' and tid in (435,254,428,786): mul('f',.5,'Poles bloodlines/scout -50% food')
    if civ=='Shu' and tid in (100,237,437,199,200,201,211,212,219,436,218): mul('fwgs',.75,'Shu archery techs -25% (DAT list excl. Elite Skirm)')
    if civ=='Spanish' and bld=='Blacksmith': mul('g',0,'Spanish BS no gold')
    if civ=='Tupi' and bld in ('Archery Range','Barracks'): mul('f',.5,'Tupi AR/barracks -50% food')
    if civ=='Turks' and tid in (376,): mul('fwgs',.5,'Turks gunpowder techs -50%')
    reward=20.0 if civ=='Spanish' else 0.0
    # time
    wr=1.0
    if bld in CONSCRIPT and tid!=315: wr*=1.33
    if civ=='Franks' and bld=='Stable': wr*=1.4
    if civ=='Goths' and bld=='Barracks': wr*=2.0
    if civ=='Berbers' and bld=='Castle' and tid!=578: wr*=1.25
    if civ=='Persians' and bld=='Dock': wr*=1.2
    wr*=TEAM_WR.get((civ,bld),1.0)
    tm=1.0
    if civ=='Portuguese': tm*=1.25
    if civ=='Jurchens' and tid in SIEGE_FORT_JUR: tm*=2.0
    if civ=='Khitans' and tid in (197,429,98,254,428): tm*=1.15
    sec=t/wr/tm
    return up,reward,sec,notes
