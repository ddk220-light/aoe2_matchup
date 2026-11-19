"""Separate rich winter review draft; never changes the clean draft or Golden.

Run with apps/video/.venv/Scripts/python.exe. The old road is only a terrain
texture. Every new object is DAT-verified nonblocking and noninteractive.
Native editor screenshots remain the visual acceptance check.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
from build_campaign_winter import DAT
from build_biome_variants import OUT, SCENES, GOLDEN, TREES, sig
from AoE2ScenarioParser.datasets.terrains import TerrainId as T
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


def load(path):
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_file(str(path))


def build():
    source=SCENES/'Winter Campaign Study - Mountain and Glade.aoe2scenario'
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,GOLDEN)}
    s=load(source)
    army=sig(s)
    old_gaia=[(u.reference_id,u.unit_const,u.x,u.y,u.z,u.rotation) for u in s.unit_manager.units[0]]
    heights=[t.elevation for t in s.map_manager.terrain]
    tiles=[]
    def tile(x,y,terrain):
        t=s.map_manager.terrain[y*16+x]
        assert t.elevation==0 and 10<=x+y<=21
        t.terrain_id=int(terrain)
        tiles.append(dict(x=x,y=y,terrain=int(terrain),name=terrain.name))

    # A partly buried old route gives the central snowfield a reason to exist.
    # Its width varies gently; snow gaps and gravel soften the paved segments.
    path=[(14,1),(13,2),(12,3),(11,4),(10,5),(9,6),(8,7),(7,8),
          (7,9),(6,10),(5,11),(4,12),(3,13),(2,14),(1,15)]
    for i,(x,y) in enumerate(path):
        tile(x,y,T.ROAD_BROKEN)
        if x>0 and y<15:
            tile(x-1,y,T.ROAD_BROKEN)
        if i in (2,3,6,7,10,11):
            tile(x,y+1,T.ROAD_BROKEN)
    for x,y in [(11,2),(9,4),(7,6),(5,8),(4,10),(2,12),(1,13)]:
        tile(x,y,T.SNOW_LIGHT)
    for x,y in [(13,3),(11,5),(8,10),(6,12),(4,14)]:
        tile(x,y,T.SNOW_SOFT_LIGHT)
    # Forest-edge thaw and trodden earth; the spacious centre remains readable.
    for x,y in [(3,8),(4,7),(6,5),(8,3),(10,1),(9,11),(11,9),(13,7)]:
        tile(x,y,T.UNDERBRUSH_SNOW)

    props=[]
    def add(uid,x,y,rotation=0):
        row=DAT[uid]
        assert all(row[k]==0 for k in ('obstruction_type','obstruction_class','interaction_mode')),row
        assert uid not in TREES
        u=s.unit_manager.add_unit(player=0,unit_const=uid,x=x,y=y,z=0,rotation=rotation)
        props.append(dict(id=uid,name=row['name'],x=x,y=y,referenceId=u.reference_id,
                          nonblocking=True,noninteractive=True))
    # Keep small props beside the route, not under the starting formations.
    for uid,x,y,rot in [
        (710,6.1,7.3,1.7),(710,10.8,8.5,4.3),
        # Cracks are technically passable but look like deep trenches at this zoom.
        # Keep the battle lane visually open as well as mechanically open.
        (1359,4.6,7.3,0),(1359,6.0,5.0,0),(1365,8.8,2.6,0),
        (1359,9.5,10.4,0),(1365,12.0,7.9,0),(1359,7.3,12.4,0),
        (1365,3.1,8.6,0),(1365,5.5,13.8,0),(1359,10.2,1.4,0),
        (809,4.1,6.8,3),(809,13.6,6.2,1),
        (2743,5.1,4.5,0),(2743,2.8,6.6,0),(2743,11.1,11.0,0),
        (2738,2.0,7.1,0),(2738,12.0,10.6,2),
        (1365,2.3,7.3,0),(1359,11.8,10.4,0)]:
        add(uid,x,y,rot)

    assert sig(s)==army
    assert [t.elevation for t in s.map_manager.terrain]==heights
    assert [(u.reference_id,u.unit_const,u.x,u.y,u.z,u.rotation)
            for u in s.unit_manager.units[0]][:len(old_gaia)]==old_gaia
    target=SCENES/'Winter Campaign Study - Detailed Battlefield.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        s.write_to_file(str(target))
    check=load(target)
    assert sig(check)==army
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report=dict(path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        sources=hashes,combatUnchanged=True,elevationsUnchanged=True,scenicGaiaPreserved=True,
        extraTrees=0,newBlockingObjects=0,newInteractiveObjects=0,tiles=tiles,props=props)
    (OUT/'campaign-study/winter-detailed.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('tiles','props')},indent=2))


if __name__=='__main__':
    build()
