"""Additional review maps. Production Goldens and combat players stay untouched.

Scenery comes from the installed DAT, not generated artwork. Cultural motifs
are inspired sets, not claims that anonymous editor flags are official emblems.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path

from build_biome_variants import (OUT, SCENES, GOLDEN, TILES, SCENIC_TREES,
    WIDER_GLADE, TREES, read, sig, safe_lane, AoE2DEScenario)

DAT = {r['id']: r for r in json.loads((OUT/'expanded-scenery-dat.json').read_text())}
CONFIG = {
    'Autumn': dict(trees=[1248,1248,1717,350], lane=12, forest=71, glade=12,
        rock=40, water=95, animals=[65,65,65,1239],
        props=[(1323,14.2,13.3,1),(623,15.4,14.2,1),(809,2,1.5,0),(1362,4.7,2,0)],
        rich=[(858,2.1,2,0),(1320,1.4,3.3,0),(1330,3.3,1.5,0),(1837,13,14.3,0)]),
    'Blossom Garden': dict(trees=[2017,2017,1984,2016], lane=12, forest=113, glade=122,
        rock=40, water=95, animals=[65,65,1028,1028],
        props=[(2009,14.3,13.4,1),(623,15.3,14.2,1),(2598,14.4,13.6,.5),(2029,3.3,2.7,0),(2536,14,14.6,0)],
        rich=[(1562,3.3,1.6,0),(1986,2.3,2.3,0),(2022,4.2,1.5,0),(2007,13.3,14.2,0)]),
    'Savannah': dict(trees=[1063,1063,1052,1051], lane=100, forest=41, glade=100,
        rock=102, water=95, animals=[1019,1019,1796,1026,1026],
        props=[(2515,14,13.4,1),(1323,15.3,13.6,1),(1091,12.8,14.6,0),(1365,3,1.4,0)],
        rich=[(1563,3.1,1.8,0),(1177,4.3,2.1,0),(1092,12.5,14.4,0),(1033,1.5,4.3,0)]),
    'Andean Highlands': dict(trees=[2570,2570,2583,350], lane=100, forest=128, glade=12,
        rock=40, water=95, animals=[305,1963,305,1239],
        props=[(2515,14,13.1,1),(2734,15.1,13.6,2),(1323,14.5,14.8,1),(2598,14,13.6,.5),(2611,2.5,1.5,0)],
        rich=[(2611,3.1,1.8,0),(1177,4.2,2,0),(1094,12.7,14.2,0),(1321,1.5,3.2,0)]),
    'Mediterranean': dict(trees=[1349,1349,1347,1348], lane=100, forest=88, glade=12,
        rock=40, water=58, animals=[65,65,1239,303],
        props=[(2009,14.2,13.3,1),(1323,15.1,14.1,1),(2519,2.4,1.5,0),(1366,4.5,2.1,0)],
        rich=[(2234,3.1,1.9,0),(2524,4.1,2.2,0),(2290,1.5,3.2,0),(2528,13.1,14.1,0)]),
}

def load(path):
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_file(str(path))

def put(s, uid, x, y, z=0, details=None):
    row=DAT.get(uid)
    if safe_lane(x,y):
        assert row and all(row[k]==0 for k in ('obstruction_type','obstruction_class','interaction_mode')), (uid,x,y)
    if row and (row['obstruction_type'] or row['obstruction_class']):
        # Entire collision box stays beyond the original fighting corridor.
        radius=(row['collision_size_x'] or 0)+(row['collision_size_y'] or 0)
        assert x+y+radius<10 or x+y-radius>21, (uid,x,y,radius)
    u=s.unit_manager.add_unit(player=0,unit_const=uid,x=x,y=y,z=z,rotation=1 if uid==2598 else 0)
    if details is not None: details.append(dict(id=uid,name=(row or {}).get('name'),x=x,y=y,z=z))
    return u

def save(s,name,details,kind,source=None):
    original=read()
    assert sig(s)==sig(original)
    oldtrees={(u.x,u.y) for u in original.unit_manager.units[0] if u.unit_const in TREES}
    trees={(u.x,u.y) for u in s.unit_manager.units[0] if u.unit_const in TREES}
    assert trees<=oldtrees
    assert all(t.elevation==0 for t in s.map_manager.terrain if 10<=t.x+t.y<=20)
    path=SCENES/f'{name}.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()): s.write_to_file(str(path))
    assert sig(load(path))==sig(original)
    return dict(name=name,path=str(path),kind=kind,source=source,trees=len(trees),
        combatUnchanged=True,flatBattlefield=True,addedTrees=[],details=details,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def biome(name,rich,index):
    c=CONFIG[name];s=read();details=[]
    for u in list(s.unit_manager.units[0]):s.unit_manager.remove_unit(unit=u)
    for r in SCENIC_TREES:
        if (int(r['x']),int(r['y'])) in WIDER_GLADE:continue
        # Small groves of complementary species instead of random single trees.
        palette=c['trees']; k=(int(r['x'])//3+int(r['y'])//4)%len(palette)
        if r['unit'] in (1053,1054): uid=1362
        else:uid=palette[k]
        s.unit_manager.add_unit(player=0,unit_const=uid,x=r['x'],y=r['y'],z=r['z'],reference_id=r['ref'])
    for tile,t in zip(s.map_manager.terrain,TILES):
        x,y=tile.x,tile.y
        if 10<=x+y<=20: typ=c['lane'];height=0
        else:
            typ=c['forest'];height=t['height']
            if x+y<10 and 1<=x<=5 and 1<=y<=5:typ=c['glade'];height=0
            if x+y>=25:typ=c['rock']
            if t['terrain']==15:typ=c['water']
        tile.terrain_id=typ;tile.elevation=height
    def terrain(x,y,typ,h=None):
        tile=s.map_manager.terrain[y*16+x];tile.terrain_id=typ
        if h is not None:tile.elevation=h
    # Separate waterholes, stream edges and alpine caps are outside combat land.
    for x,y in [(1,1),(1,2),(2,1)]:terrain(x,y,c['water'],0)
    if name=='Andean Highlands':
        for x,y in [(15,13),(15,14),(14,13)]:terrain(x,y,73)
    if name=='Blossom Garden':
        for x,y in [(2,2),(3,1),(1,3)]:terrain(x,y,78,0)
    animal_ids=[]
    for uid,(x,y) in zip(c['animals'],[(3.3,3.3),(4.4,2.7),(2.7,4.4),(4.8,3.4),(3.5,4.8)]):
        animal_ids.append(put(s,uid,x,y,details=details).reference_id)
    for args in c['props']:put(s,*args,details=details)
    for x,y in [(1.5,4),(4.7,1.5),(5,3.8)]:
        put(s,1365 if name in ('Savannah','Andean Highlands') else 1366,x,y,details=details)
    if rich:
        for x in range(2,14):
            y=15-x
            terrain(x,y,25 if x not in (4,9) else 6,0)
            if x%3:terrain(x,y+1,78 if name=='Blossom Garden' else 11,0)
        for args in c['rich']:put(s,*args,details=details)
        for uid,x,y in [(710,7.8,4.1),(1091,10.1,8.2),(241,5.8,6.1),(809,7.1,11.7)]:put(s,uid,x,y,details=details)
        if name=='Autumn':
            for x,y in [(4.5,7),(9.5,9),(6.5,5)]:put(s,2031,x,y,details=details)
        if name=='Blossom Garden':
            for x,y in [(4.5,7),(9.5,9),(6.5,5)]:put(s,2029,x,y,details=details)
    tr=s.trigger_manager.add_trigger('Scenery only: wildlife stays in outer clearing')
    tr.new_effect.change_object_speed(quantity=0,source_player=0,selected_object_ids=animal_ids)
    return save(s,f'Biome {index:02}{"B" if rich else "A"} - {name} {"Rich" if rich else "Scenic"}',details,'biome')

# Modest cultural landmarks and two anonymous editor standards. These are
# deliberately outside the lane; flags replace existing trees, never add a new
# obstacle to the open battle footprint. Players/civilizations are not changed.
CIVS=[
 ('Japanese','07A',1562,1986,600),('Chinese','07A',1989,2058,601),
 ('Vikings','01A',858,1320,602),('Celts','06A',1979,820,603),
 ('Byzantines','10A',2234,1838,604),('Saracens','02A',1567,1177,1150),
 ('Ethiopians','08A',1093,1177,1151),('Incas','09A',2611,2611,1282),
 ('Mayans','03A',1279,1279,2601),('Persians','02A',2288,2252,1284),
]

def civilization(index,civ,base,landmark,small,flag):
    source=next(SCENES.glob(f'Biome {base} -*.aoe2scenario'));s=load(source);details=[]
    if civ=='Mayans':
        from AoE2ScenarioParser.datasets.players import PlayerId
        from AoE2ScenarioParser.datasets.object_support import Civilization
        s.player_manager.players[PlayerId.GAIA].civilization=Civilization.MAYANS
    # Replacing one corner accent creates room for the landmark, not clutter.
    for u in list(s.unit_manager.units[0]):
        if u.unit_const not in TREES and u.x+u.y<5.5:s.unit_manager.remove_unit(unit=u)
    if civ=='Celts':
        # Large stone circle: fit its full footprint in the outer corner.
        for u in list(s.unit_manager.units[0]):
            if u.unit_const in TREES and u.x<5.2 and u.y<5.2:s.unit_manager.remove_unit(unit=u)
        put(s,landmark,2.6,2.1,details=details)
    else:put(s,landmark,2.8,1.8,details=details)
    put(s,small,13,14.1,details=details)
    for target in [(7.5,.5),(8.5,15.5)]:
        candidates=[u for u in s.unit_manager.units[0] if u.unit_const in TREES and (u.x+u.y<9 or u.x+u.y>22)]
        u=min(candidates,key=lambda u:(u.x-target[0])**2+(u.y-target[1])**2)
        x,y,z=u.x,u.y,u.z;s.unit_manager.remove_unit(unit=u)
        put(s,flag,x,y,z,details=details)
    return save(s,f'Civ {index:02} - {civ}',details,'civilization',str(source))

if __name__=='__main__':
    before=hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    rows=[biome(name,rich,i) for i,name in enumerate(CONFIG,6) for rich in (False,True)]
    rows += [civilization(i,*c) for i,c in enumerate(CIVS,1)]
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest()==before
    (OUT/'extra-variants.json').write_text(json.dumps(dict(goldenSha256=before,variants=rows),indent=2))
    print(json.dumps([dict(name=r['name'],trees=r['trees']) for r in rows],indent=2))
