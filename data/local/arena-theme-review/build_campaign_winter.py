"""Review-only winter refinement informed by two Viking Sagas campaign maps.

Golden gameplay data is the source of truth. Only Gaia scenery and terrain
textures change; the combat corridor stays flat and free of new collision boxes.
Run with apps/video/.venv/Scripts/python.exe. Native editor review is required.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path

from build_biome_variants import GOLDEN, OUT, SCENES, SCENIC_TREES, TREES, WIDER_GLADE, read, sig
from AoE2ScenarioParser.datasets.terrains import TerrainId as T
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

DAT = {}
for filename in ('scenery-dat.json', 'expanded-scenery-dat.json'):
    DAT.update({r['id']: r for r in json.loads((OUT/filename).read_text())})


def build():
    scene = read()
    source_hash = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    army = sig(scene)
    original_trees = {(u.x,u.y) for u in scene.unit_manager.units[0] if u.unit_const in TREES}
    details = []
    animals = []
    for unit in list(scene.unit_manager.units[0]):
        scene.unit_manager.remove_unit(unit=unit)

    # Reuse the approved clearing footprint. No new tree coordinates, even
    # outside the arena; the surviving boundary trees stay in place.
    for r in SCENIC_TREES:
        x,y = r['x'],r['y']
        if (int(x),int(y)) in WIDER_GLADE:
            continue
        if x+y > 24:  # Bare summit and river: trees belong at the mountain foot.
            continue
        uid = r['unit']
        if uid in TREES:
            # Cohesive small groves, with scattered exposed conifers like the
            # official forest references, instead of alternating every tree.
            uid = 350 if (int(x)//3 + int(y)//4)%4 == 0 else 413
            if (int(x),int(y)) in {(1,5),(5,1),(12,10),(10,13)}:
                uid = 1250
        # Preserve the broad native variant range. Restricting it to 0..3
        # produced mostly bare trunks in native review of these winter assets.
        frame = r['frame']
        scene.unit_manager.add_unit(player=0,unit_const=uid,x=x,y=y,z=0,
            reference_id=r['ref'],rotation=frame,animation_frame=frame)

    # Terrain is grouped by landform, not random texture noise. The diagonal
    # fighting corridor and its boundary row are always elevation zero.
    for t in scene.map_manager.terrain:
        x,y=t.x,t.y
        t.elevation=0
        t.terrain_id=int(T.SNOW_SOFT)
        if x+y<10 or x+y>21:
            t.terrain_id=int(T.UNDERBRUSH_SNOW if (x//3+y//2)%3==0 else T.SNOW_STRONG)

    def tile(x,y,typ,height=0):
        t=scene.map_manager.terrain[y*16+x]
        assert not height or x+y>22
        t.terrain_id=int(typ)
        t.elevation=height

    # Open, irregular left glade: green winter grass edged with thin snow and
    # leaf litter, rather than the former large orange circle.
    for x,y in [(1,1),(2,1),(3,1),(1,2),(2,2),(3,2),(4,2),
                (1,3),(2,3),(3,3),(4,3),(2,4),(3,4),(4,4),(2,5)]:
        tile(x,y,T.GRASS_2)
    for x,y in [(1,1),(3,1),(4,2),(2,5),(4,4)]: tile(x,y,T.SNOW_LIGHT)
    for x,y in [(0,1),(1,0),(4,1),(5,2),(5,3),(3,5),(1,4)]: tile(x,y,T.UNDERBRUSH_SNOW)
    for x,y in [(2,2),(3,3),(4,3)]: tile(x,y,T.SNOW_SOFT_LIGHT)

    # The high shoulder flows down to a lower shelf. The channel runs between
    # two rock groups, ending in a pool that exits the map beyond the trees.
    heights={(14,9):1,(15,9):1,(13,10):1,(14,10):2,(15,10):3,
             (12,11):1,(13,11):2,(14,11):3,(15,11):3,
             (12,12):1,(13,12):2,(14,12):3,(15,12):3,
             (13,13):1,(14,13):2,(15,13):2,(14,14):1,(15,14):2,(15,15):1}
    for (x,y),h in heights.items():
        tile(x,y,T.SNOW_SOFT_STRONG if h==3 else T.ROCK_1,h)
    for x,y in [(11,12),(12,13),(13,14),(14,15)]: tile(x,y,T.GRAVEL_DEFAULT)
    for x,y,h in [(15,12,3),(14,13,2),(13,14,0),(12,14,0),(12,15,0),(11,15,0)]:
        tile(x,y,T.WATER_2D_SHORELESS,h)
    for x,y in [(11,14),(13,15)]: tile(x,y,T.BEACH_WET_GRAVEL)

    # Slightly weathered snow near the edges of the fighting lane. These are
    # land textures, with the same passability and no added objects in the lane.
    for x,y in [(4,7),(5,6),(10,10),(11,9),(6,12),(7,11)]: tile(x,y,T.SNOW_LIGHT)

    def add(uid,x,y,z=0,rot=0):
        row=DAT.get(uid)
        radius=((row or {}).get('collision_size_x') or 0)+((row or {}).get('collision_size_y') or 0)
        if row and row['obstruction_type']:
            assert x+y+radius<10 or x+y-radius>21,(uid,x,y,radius)
        assert x+y<10 or x+y>21,(uid,x,y)
        u=scene.unit_manager.add_unit(player=0,unit_const=uid,x=x,y=y,z=z,rotation=rot)
        details.append(dict(id=uid,name=(row or {}).get('name'),x=x,y=y,z=z))
        if uid in (65,1239): animals.append(u.reference_id)
        return u

    # Snow cliffs and boulders form one connected escarpment, with smaller
    # rubble at its foot. The waterfall is nestled into the gap, not isolated.
    for uid,x,y,z,rot in [
        (1859,14.4,11.7,1.1,0),(2734,15.1,10.6,2.8,3),
        (2734,14.0,11.3,1.8,6),(1323,12.6,11.8,.6,2),
        (623,12.1,12.3,.3,5),(2734,15.2,14.4,1.2,5),
        (2734,14.7,14.7,.5,1),(623,13.9,15.0,0,6),
        (2598,14.2,13.8,1.3,1),(389,12.6,14.7,0,0),
        (623,11.6,14.1,0,2),(1323,13.4,15.3,0,4)]:
        add(uid,x,y,z,rot)
    for uid,x,y in [(1364,11.9,14.8),(1365,11.4,13.4),(1360,12.0,12.7),
                    (1365,13.0,15.6),(809,11.8,15.0),(1362,13.0,11.6)]:
        add(uid,x,y)

    # Wildlife is arranged in a loose grazing group, with ground cover along
    # the perimeter. No extra blocking trees are used to fill visual gaps.
    for uid,x,y,rot in [(65,2.5,3.4,2),(65,3.7,3.9,4.7),(65,4.6,2.6,3.8),
                        (1239,3.4,5.0,1),(1239,5.1,2.8,5)]: add(uid,x,y,rot=rot)
    for uid,x,y,rot in [(809,1.6,2.1,2),(1365,1.3,3.6,0),(1360,2.4,1.1,0),
                       (1358,3.1,2.0,0),(1365,4.8,1.9,0),(1362,1.2,4.5,0),
                       (1358,4.5,4.0,0),(1365,3.2,5.2,0),(1360,5.0,3.5,0),
                       (623,1.0,2.5,2),(1359,2.1,4.5,0)]: add(uid,x,y,rot=rot)
    tr=scene.trigger_manager.add_trigger('Scenery only: wildlife stays in outer clearing')
    tr.new_effect.change_object_speed(quantity=0,source_player=0,selected_object_ids=animals)

    trees={(u.x,u.y) for u in scene.unit_manager.units[0] if u.unit_const in TREES}
    assert trees<=original_trees
    assert sig(scene)==army
    assert all(t.elevation==0 for t in scene.map_manager.terrain if 10<=t.x+t.y<=21)
    name='Winter Campaign Study - Mountain and Glade'
    path=SCENES/f'{name}.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        scene.write_to_file(str(path))
        check=AoE2DEScenario.from_file(str(path))
    assert sig(check)==army
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest()==source_hash
    report=dict(name=name,path=str(path),sourceSha256=source_hash,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),trees=len(trees),
        originalTrees=len(original_trees),addedTreeCoordinates=[],combatUnchanged=True,
        protectedCorridorFlat=True,newBlockingPropsOutsideCorridor=True,details=details,
        references=['Blood Under a Blackened Sky: banks, ford, mountain shrine',
                    'Kings and Cowards: shoreline, forest edge, snow shelf'])
    (OUT/'campaign-study'/'winter-draft.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='details'},indent=2))


if __name__=='__main__':
    build()
