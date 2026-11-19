"""Build review-only biome drafts from Golden geometry and the UI-sculpted winter.

The installed editor's 1.59 checkpoint is read-only: its terrain and scenery
were extracted separately. We reconstruct supported 1.58 files from the Golden,
not by relabelling the newer file. The game opens/upgrades these normally.
Combat players and existing triggers are never edited. All additional combat-lane
decorations must have DAT obstruction_type/class == 0 and interaction_mode == 0.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path

from AoE2ScenarioParser.datasets.other import OtherInfo as O
from AoE2ScenarioParser.datasets.terrains import TerrainId as T
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SCENES = OUT / 'scenarios'
SCENES.mkdir(exist_ok=True)
GOLDEN = ROOT / 'apps/video/templates/lab_goldens/melee_vs_ranged.aoe2scenario'
TILES = json.loads((OUT/'winter-native-terrain.json').read_text())
GAIA = json.loads((OUT/'winter-native-gaia.json').read_text())['records']
DAT = {r['id']:r for r in json.loads((OUT/'scenery-dat.json').read_text())}
TREES = {u.ID for u in O if u.name.startswith('TREE_')}
SCENIC_TREES = [r for r in GAIA if r['unit'] in TREES or r['unit'] in (1053,1054)]
WIDER_GLADE = {(4,1),(5,1),(5,2),(5,3),(2,5),(3,5),(1,4)}
ANIMALS = {65,1796,2096,1141,1239,884,816,1028,1243,303}
NAMES = ['Winter', 'Desert', 'Jungle', 'Mangrove', 'Coastal']

def read():
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_file(str(GOLDEN))

def sig(s):
    return [(p,u.reference_id,u.unit_const,u.x,u.y,u.z,u.rotation,u.garrisoned_in_id)
            for p in range(1,9) for u in s.unit_manager.units[p]]

def safe_lane(x,y):
    return 10 <= x+y <= 21

def palette(b,x,y,old):
    """Clusters, not random confetti. Tree coordinates remain the UI checkpoint's."""
    if b=='Winter': return old
    if old in (1053,1054): return 1053
    if b=='Desert': return 1063 if (x<2 or y<2) and int(x+y)%3 else 351
    if b=='Jungle': return 351 if int(x*3+y)%7==0 else (348 if x<5 and y<5 else 414)
    if b=='Mangrove': return 2025 if x+y<5 else 1144
    if b=='Coastal': return 1348 if y<2 or x>14 else 351
    raise ValueError(b)

def terrain(b,x,y,original):
    s=x+y
    if b=='Winter': return original
    # Preserve the UI-sculpted terrain zones, with separate palettes per biome.
    snow={32,36,73,74,72,124,125,126,127,35}
    if b=='Desert':
        return {15:95,100:100,6:102,40:102,72:14,74:14,124:14,125:14}.get(original,14 if original in snow else original)
    if b=='Jungle':
        return {15:95,100:60,6:76,40:40,72:77,74:83,124:60,125:60}.get(original,83 if original in snow else original)
    if b=='Mangrove':
        return {15:130,100:0,6:76,40:76,72:77,74:101,124:12,125:12}.get(original,12 if original in snow else original)
    if b=='Coastal':
        return {15:58,100:100,6:6,40:40,72:100,74:100,124:14,125:14}.get(original,100 if original in snow else original)

def build(b,rich,index):
    s=read(); before=sig(s)
    golden_tree={(u.x,u.y) for u in s.unit_manager.units[0] if u.unit_const in TREES}
    for u in list(s.unit_manager.units[0]): s.unit_manager.remove_unit(unit=u)
    for r in SCENIC_TREES:
        if (int(r['x']),int(r['y'])) in WIDER_GLADE: continue
        uid=palette(b,r['x'],r['y'],r['unit'])
        s.unit_manager.add_unit(player=0,unit_const=uid,x=r['x'],y=r['y'],z=r['z'],
            reference_id=r['ref'],rotation=r['rotation'],animation_frame=r['frame'])
    for i,tile in enumerate(s.map_manager.terrain):
        t=TILES[i];assert (tile.x,tile.y)==(t['x'],t['y'])
        tile.terrain_id=int(terrain(b,tile.x,tile.y,t['terrain']))
        tile.elevation=t['height'] if b!='Mangrove' else 0
    def tile(x,y,typ,height=None):
        t=s.map_manager.terrain[y*16+x];t.terrain_id=int(typ)
        if height is not None:t.elevation=height
    for x,y in WIDER_GLADE:
        tile(x,y,{'Winter':T.GRASS_DRY,'Desert':T.DESERT_SAND,'Jungle':T.GRASS_JUNGLE,
                  'Mangrove':T.GRASS_2,'Coastal':T.GRASS_DRY}[b])
    details=[];animals=[]
    def add(uid,x,y,z=0,rot=0):
        if safe_lane(x,y):
            r=DAT[uid]
            assert r['obstruction_type']==r['obstruction_class']==r['interaction_mode']==0,(b,uid,x,y)
        u=s.unit_manager.add_unit(player=0,unit_const=uid,x=x,y=y,z=z,rotation=rot)
        details.append(dict(id=uid,x=x,y=y,lane=safe_lane(x,y)))
        if uid in ANIMALS:animals.append(u.reference_id)
        return u
    if b=='Winter':
        for uid,x,y,z,rot in [(1323,12.5,12.5,.5,0),(2734,15.5,13.5,2,8),(2734,14.5,13.5,1.5,5),
                              (2598,15,13,2,1),(65,3.5,3.5,0,4.7),(65,3.5,4.5,0,4.7),(809,2,1,0,7),(809,4,2,0,3)]:
            add(uid,x,y,z,rot)
        add(1365,1.7,2.8);add(1365,4.4,3.9)
    elif b=='Desert':
        # Watered oasis on the left, dry sandstone escarpment on the right.
        for xy in [(1,1),(2,1),(1,2)]:tile(*xy,T.WATER_GREEN,0)
        for xy in [(2,2),(3,1),(2,3)]:tile(*xy,T.GRASS_DRY)
        for xy in [(13,12),(13,13),(14,12),(15,12)]:tile(*xy,T.GRAVEL_DESERT)
        for uid,x,y,z,rot in [(2515,15.1,13.3,1.5,2),(1323,13.7,12.5,1,0),(623,15.4,14.3,1,0),
                              (1796,3.8,3.3,0,0),(1796,3.3,4.4,0,1),(1091,12.2,14.8,0,0),(1177,4.2,1.5,0,0)]:add(uid,x,y,z,rot)
        add(1365,4,2);add(1365,12.5,13.9)
    elif b=='Jungle':
        # Keep the enlarged wildlife glade readable; dense jungle ground covers
        # stay at its edges instead of hiding the animals in the middle.
        for x,y in [(2,2),(2,3),(3,2),(3,3),(3,4),(4,2),(4,3),(4,4),(5,2),(2,4)]:
            tile(x,y,T.GRASS_2)
        for uid,x,y,z,rot in [(1149,14.5,13,1,0),(2009,15.4,14.1,1,0),(1323,12.5,12.5,.5,0),
                              (2598,14.4,13.6,.5,1),(2096,2.8,3.5,0,0),(2096,3.7,4.3,0,0),(855,2.5,1.3,0,0)]:add(uid,x,y,z,rot)
        for x,y in [(1.8,2.8),(3,1.9),(12.2,14.6),(13,14.8)]:add(1175,x,y)
        add(1351,13.1,13.8)
    elif b=='Mangrove':
        for x in range(1,4):
            for y in range(1,4):
                if (x,y)!=(3,3):tile(x,y,T.WATER_GREEN,0)
        for x in range(11,16):
            for y in range(12,16):
                if x+y>=25:tile(x,y,T.WATER_WEEDS,0)
        for uid,x,y in [(389,14.8,14.5),(1148,12.4,12.5),(1141,3.5,4.2),(1141,4,3.5),(721,14.2,13.6),
                        (809,2.8,4.1),(809,12.5,13.4),(1351,4,2.5),(1353,3.4,3.3),(1353,12.7,12.7)]:add(uid,x,y)
    else:
        for xy in [(1,1),(1,2),(2,1)]:tile(*xy,T.WATER_AZURE,0)
        for xy in [(2,2),(3,1),(1,3)]:tile(*xy,T.BEACH_WHITE)
        for xy in [(12,13),(12,14),(13,14),(13,15),(14,15)]:tile(*xy,T.WATER_AZURE,0)
        for uid,x,y,z in [(2009,14.4,13.3,1.5),(1148,15.2,14.4,1),(389,12.5,14.2,0),
                           (721,12.7,14.7,0),(1141,3.5,3.4,0),(1141,3,4.1,0),(1330,2.3,3.8,0)]:add(uid,x,y,z)
        add(301,2.8,2.7);add(301,4.2,3.5)

    wildlife={
        'Winter':[(65,4.6,2.4),(1239,5.2,3.1),(1239,3.1,5.1)],
        'Desert':[(1796,4.4,2.8),(884,5.1,2.2),(1239,2.4,5.1)],
        'Jungle':[(2096,4.9,2.4),(816,3.9,1.1),(816,2.5,4.8),(1141,4.1,4.6)],
        'Mangrove':[(1028,2.8,2.4),(1028,4.7,2.1),(1141,2.3,4.4)],
        'Coastal':[(303,3.2,2.5),(303,1.8,3.2),(1141,4.9,2.6)]
    }
    for uid,x,y in wildlife[b]:add(uid,x,y)
    for x,y in [(1.5,4.2),(3.2,4.8),(4.8,1.5),(5.1,3.9)]:
        add(1365 if b in ('Winter','Desert') else 301,x,y)

    if rich:
        # A worn central route, broken into short irregular stretches. These are
        # land terrain textures, not road objects, and retain elevation zero.
        for x in range(2,14):
            y=15-x
            for yy in [y,y+1]:
                typ=T.ROAD_BROKEN if (x+yy)%3 and x not in (5,10) else T.DIRT_1
                if b=='Jungle':typ=T.ROAD_FUNGUS if x not in (5,10) else T.DIRT_MUD
                if b=='Mangrove':typ=T.ROAD_BROKEN if x%3 else T.DIRT_MUD
                if b=='Winter' and x%4==0:typ=T.SNOW_LIGHT
                tile(x,yy,typ,0)
        for x,y in [(4,7),(7,4),(10,9),(9,10),(6,6),(11,7),(3,9)]:
            tile(x,y,T.SNOW_LIGHT if b=='Winter' else T.DIRT_2,0)
        # Sparse readable details along the lane margins, all DAT-verified.
        for uid,x,y in [(710,7.8,4.1),(1091,10.1,8.2),(241,5.8,6.1),(710,4.9,12.5),(809,7.1,11.7)]:add(uid,x,y)
        plant=1365 if b in ('Winter','Desert') else 301
        for x,y in [(5.3,6.2),(9.3,2.4),(11.6,6.9),(2.2,9.1),(6.2,12.3)]:add(plant,x,y)
        # More extensive vignettes remain in the outer clearings.
        extras={
            'Winter':[(858,2.3,2.1),(1320,1.4,2.9),(1330,3.3,1.4),(820,12.4,14.4),(809,4.1,3.6)],
            'Desert':[(1567,4,2.1),(1177,3.5,1.5),(856,12.5,14.4),(1091,3.5,4.2),(1330,3.4,2.4)],
            'Jungle':[(1566,3.6,2.1),(1177,2.8,2.4),(1175,4.2,3.8),(1351,1.7,4.2),(855,12.3,14.2)],
            'Mangrove':[(722,1.6,2.6),(1330,3.8,2.4),(1353,4.2,3.6),(1175,12.4,14.8),(1175,14,15)],
            'Coastal':[(722,1.5,1.8),(1330,3.3,1.7),(1177,2.4,3.2),(856,13.3,12.2),(301,4.3,2.6)]
        }
        for uid,x,y in extras[b]:add(uid,x,y)
    # Freeze only newly added Gaia wildlife so none can wander into the arena.
    if animals:
        tr=s.trigger_manager.add_trigger('Scenery only: wildlife stays in outer clearing')
        tr.new_effect.change_object_speed(quantity=0,source_player=0,selected_object_ids=animals)
    trees={(u.x,u.y) for u in s.unit_manager.units[0] if u.unit_const in TREES}
    assert trees <= golden_tree
    assert sig(s)==before
    assert not [(t.x,t.y) for t in s.map_manager.terrain if 10<=t.x+t.y<=20 and t.elevation]
    name=f'Biome {index:02}{"B" if rich else "A"} - {b} {"Rich" if rich else "Scenic"}'
    path=SCENES/f'{name}.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        s.write_to_file(str(path));v=AoE2DEScenario.from_file(str(path))
    assert sig(v)==before
    return dict(name=name,path=str(path),biome=b,version='B' if rich else 'A',trees=len(trees),
                combatUnchanged=True,flatBattlefield=True,addedTrees=[],details=details,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':
    original=hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    manifest=[build(b,rich,i) for i,b in enumerate(NAMES,1) for rich in (False,True)]
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest()==original
    (OUT/'variants.json').write_text(json.dumps({'goldenSha256':original,'variants':manifest},indent=2))
    print(json.dumps([{'name':r['name'],'trees':r['trees'],'props':len(r['details'])} for r in manifest],indent=2))
