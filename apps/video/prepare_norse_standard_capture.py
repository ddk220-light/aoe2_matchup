"""Freeze 3 x 14 x 5 raw game recordings on audited winter Golden derivatives.

Run once; resume with run_knight_expansion.py --work data/local/norse-standard-capture.
Each iteration is a separate game and job, not a copied recording or simulator seed.
Existing campaigns and the approved unique-unit roster are never rewritten.
"""
import contextlib
import dataclasses
import io
import json
import pickle
import shutil
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import (GOLDENS, _load_stack, _validate_scenario, golden_path,
                            capture_template_path, _player_runtime_configuration,
                            _trigger_structure, _camera_configuration)
from aoe2x.lab.planner import plan_matchup
from prepare_jomsviking_capture import audited_price, NEW_UNITS, EXTRACTED, DAT
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'data/local/norse-standard-capture'
REVIEW = ROOT/'data/local/arena-theme-review'
GAME = DAT.parent/'CivTechTrees'
WINTER = REVIEW/'scenarios/Biome 01A - Winter Scenic.aoe2scenario'
# Selection prioritizes ordinary combat stats over minimizing the number of civs.
# Regional lines have no fully generic provider; exceptions remain visible.
OPPONENTS = [
    ('Spanish','champion',567,'Champion','melee',''),
    ('Saracens','arbalester',492,'Arbalester','mobile_ranged','Building bonus has no target here.'),
    ('Chinese','cavalier',283,'Cavalier','melee','No Paladin upgrade: Post-Imperial scenarios retain Cavaliers.'),
    ('Spanish','paladin',569,'Paladin','melee',''),
    ('Spanish','hussar',441,'Hussar','melee',''),
    ('Turks','heavy_camel',330,'Heavy Camel Rider','melee',''),
    ('Cumans','elite_steppe',1372,'Elite Steppe Lancer','melee',
     'All ordinary combat upgrades; Cuman cavalry speed is 5% above a Husbandry baseline.'),
    ('Bengalis','elite_elephant',1134,'Elite Battle Elephant','melee',
     'No generic provider. Paiks adds 20% attack rate; Bengali elephants resist bonus damage and conversion.'),
    ('Spanish','imp_elite_skirm',6,'Elite Skirmisher','mobile_ranged',''),
    ('Saracens','heavy_cav_archer',474,'Heavy Cavalry Archer','mobile_ranged',''),
    ('Bengalis','elite_elephant_archer',875,'Elite Elephant Archer','mobile_ranged',
     'No generic provider. Paiks and Bengali elephant resistance apply; Thumb Ring unavailable.'),
    ('Saracens','hand_cannoneer',5,'Hand Cannoneer','mobile_ranged','Avoids Spanish firing-rate bonus.'),
    ('Bengalis','heavy_scorpion',542,'Heavy Scorpion','siege_ranged',''),
    ('Incas','elite_champi_warrior',2554,'Elite Champi Warrior','melee',
     'No generic provider. Full standard upgrades plus Fabric Shields (+1/+1 armor) and 30% food discount.'),
]
CATALOGS = ('unique-unit-roster.json','recording-subjects.json','recording-costs.json','recording-balance.json')


def load_scenario(path):
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_file(str(path))


def army_signature(s):
    return [(p,u.reference_id,u.unit_const,u.x,u.y,u.z,u.rotation,u.garrisoned_in_id)
            for p in range(1,9) for u in s.unit_manager.units[p]]


def winter_templates(config, raw_dat, *, visual_source=WINTER, work=WORK, extra_land=frozenset()):
    """Copy only terrain/Gaia art into each family's own gameplay template.

    New Gaia references are assigned above existing combat references. Each
    family's diplomacy, AI, camera, army positions and patrol triggers stay its
    own. Land in the combat corridor remains flat and passable. Wildlife is
    frozen in the outer clearing by a Gaia-only speed effect.
    """
    from AoE2ScenarioParser.datasets.other import OtherInfo
    from build_run import _ai_configuration
    donor = load_scenario(visual_source)
    # Golden perimeter also uses the two wood-bearing bush variants.
    trees = {u.ID for u in OtherInfo if u.name.startswith('TREE_')} | {1053,1054}
    animals = {65,1239}
    # Broken paving is a passable land texture in the approved detailed draft.
    allowed_land = {6,12,25,32,35,36,40,72,73,74,100,124,125,126,127}
    # Non-winter themes opt in to further flat, passable land textures explicitly.
    allowed_land |= set(extra_land)
    out = {}
    for family in GOLDENS:
        if family == 'water':
            continue
        original_path = golden_path(config,family)
        source = load_scenario(original_path)
        themed = load_scenario(original_path)
        old_trees = {(u.x,u.y) for u in source.unit_manager.units[0] if u.unit_const in trees}
        for u in list(themed.unit_manager.units[0]):
            themed.unit_manager.remove_unit(unit=u)
        next_ref = max(u.reference_id for p in range(1,9) for u in themed.unit_manager.units[p])+1
        wildlife = []
        for offset,u in enumerate(donor.unit_manager.units[0]):
            if u.unit_const in trees:
                assert (u.x,u.y) in old_trees, ('new tree location',family,u.x,u.y)
            else:
                dat_unit = raw_dat.civs[0].units[u.unit_const]
                if dat_unit.obstruction_type or dat_unit.obstruction_class:
                    radius = dat_unit.collision_size_x+dat_unit.collision_size_y
                    assert u.x+u.y+radius<10 or u.x+u.y-radius>21, ('prop intrudes',u.unit_const)
            new = themed.unit_manager.add_unit(player=0,unit_const=u.unit_const,
                x=u.x,y=u.y,z=u.z,rotation=u.rotation,reference_id=next_ref+offset,
                animation_frame=u.initial_animation_frame)
            if u.unit_const in animals:
                wildlife.append(new.reference_id)
        for t,d in zip(themed.map_manager.terrain,donor.map_manager.terrain):
            assert (t.x,t.y)==(d.x,d.y)
            t.terrain_id=d.terrain_id
            t.elevation=d.elevation
            if 10<=t.x+t.y<=21:
                # The review draft's mountain starts on row x+y=21. Keep an
                # extra flat boundary tile for live combat beside the trees.
                t.elevation=0
                assert t.elevation==0 and t.terrain_id in allowed_land, ('battle terrain',t.x,t.y)
        tr=themed.trigger_manager.add_trigger('Scenery only: wildlife stays in outer clearing')
        tr.new_effect.change_object_speed(quantity=0,source_player=0,selected_object_ids=wildlife)
        path=work/'winter-templates'/f'{family}.aoe2scenario'
        path.parent.mkdir(parents=True,exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            themed.write_to_file(str(path))
        checked=load_scenario(path)
        assert army_signature(source)==army_signature(checked)
        assert _ai_configuration(source)==_ai_configuration(checked)
        assert _player_runtime_configuration(source)==_player_runtime_configuration(checked)
        assert _camera_configuration(source)==_camera_configuration(checked)
        assert _trigger_structure(checked)[:-1]==_trigger_structure(source)
        effect=checked.trigger_manager.triggers[-1].effects[0]
        assert effect.source_player==0 and effect.quantity==0
        assert set(effect.selected_object_ids)==set(wildlife)
        refs=[u.reference_id for p in range(9) for u in checked.unit_manager.units[p]]
        assert len(refs)==len(set(refs)), 'duplicate object reference'
        audit_path=path.with_suffix('.audit.json')
        save(audit_path,dict(state='PASSED',family=family,goldenSha256=sha256(original_path),
            templateSha256=sha256(path),visualSource=str(visual_source.relative_to(ROOT)),visualSourceSha256=sha256(visual_source),
            combatUnitsUnchanged=True,aiAndDiplomacyUnchanged=True,cameraUnchanged=True,
            originalPatrolTriggersUnchanged=True,battleTerrainFlatPassable=True,
            treesOnlyAtOriginalCoordinates=True,blockingPropsOutsideBattlefield=True,
            wildlifeReferences=wildlife,uniqueObjectReferences=True))
        out[family]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256(path),
            auditPath=audit_path.relative_to(ROOT).as_posix(),auditSha256=sha256(audit_path))
    return out


def available(civ,master):
    tree=read(GAME/f'{civ}.json')
    rows=[r for values in tree.values() if isinstance(values,list) for r in values
          if r.get('Use Type')=='Unit' and r.get('Node ID')==master]
    if not rows or all(r.get('Node Status')=='NotAvailable' for r in rows):
        raise ValueError(f'{civ} does not have unit {master} in the installed tech tree')
    return [dict(name=r['Name'],status=r['Node Status']) for r in rows]


def main():
    import aoe2x.dbgen.unit_analyzer as module
    from build_run import unit_const
    if (WORK/'queue.json').exists():
        raise FileExistsError('Queue frozen. Resume it; never prepare again.')
    # Caller must verify no recording worker is active before changing catalogs.
    module.OUTPUT_DIR=EXTRACTED
    analyzer=module.UnitAnalyzer()
    for name in CATALOGS:
        backup=WORK/'provenance'/name
        if not backup.exists():
            save(backup,read(ROOT/'data'/name))
    roster=read(ROOT/'data/unique-unit-roster.json')
    subjects=read(ROOT/'data/recording-subjects.json')
    costs=read(ROOT/'data/recording-costs.json')
    balance=read(ROOT/'data/recording-balance.json')
    references=[];opponents=[]
    for civ,key,master,label,category,note in OPPONENTS:
        assert unit_const(key)==master, (key,master)
        legality=available(civ,master)
        # Reuse an existing identical recording identity rather than invent duplicates.
        row=next((r for r in roster['units']+subjects['units'] if r['civ']==civ and r['master']==master),None)
        if row is None:
            row=dict(civ=civ,slug=f'{key}_{civ.lower()}',label=label,master=master,
                scenarioKey=key,**{'class':category})
            base=analyzer.get_base_stats(analyzer.get_unit(master))
            row['baseCost']={r:getattr(base,'cost_'+r) for r in ('food','wood','gold')}
            row['costSource']='Installed DAT audit for standard-unit winter captures, 2026-10-01'
            subjects['units'].append(row)
        price=audited_price(analyzer,row)
        identity=civ+'|'+row['slug']
        costs['units'][identity]=price
        balance['units'][identity]=dict(master=master,population=1.0,sharedAcrossCivilizations=True,
            populationEvidence='One comparison population per physical unit',
            classificationEvidence='Standard or regional unit available across civilizations')
        result=analyzer.calculate_unique_unit_stats(civ,dict(base_id=master,display_name=label,
            unit_class=analyzer.get_unit(master)['class']),4)
        references.append(dict(civ=civ,unit=label,slug=row['slug'],master=master,note=note,
            availability=legality,price=price,stats=dataclasses.asdict(result['stats']),
            appliedBonuses=result.get('applied_bonuses',[])))
        opponents.append(row)
    for name,obj in [('recording-subjects.json',subjects),('recording-costs.json',costs),('recording-balance.json',balance)]:
        save(ROOT/'data'/name,obj)
    save(WORK/'opponents.json',references)
    save(WORK/'source.json',dict(datPath=str(DAT),datSha256=sha256(DAT),
        assumptions=['Arbalester interpreted from war blaster','Elite Champi Warrior included separately from Champion'],
        iterations=5,localRawOnly=True))
    config=load_config();stack=_load_stack(config)
    with open(ROOT/'data/local/viking-sagas-research/installed-dat.pkl','rb') as stream:
        raw_dat=pickle.load(stream)
    scenery=winter_templates(config,raw_dat)
    campaigns=[]
    # Requested subjects first, in their established release capture order.
    for selected in NEW_UNITS:
        civ,slug,label,master,category,key=selected
        work=WORK/slug
        rows=[];evidence=[];sample_families=set()
        for index,opponent in enumerate(opponents,1):
            mixed=(category!='melee') != (opponent['class']!='melee')
            family=('ranged_vs_melee' if category!='melee' else 'melee_vs_ranged') if mixed else (
                'melee_vs_melee' if category=='melee' else 'ranged_vs_ranged')
            for iteration in range(1,6):
                rows.append(dict(id=f'norse_std_{slug}_{index:02}_r{iteration}',
                    side2=slug,civ2=civ,side3=opponent['slug'],civ3=opponent['civ'],
                    iteration=iteration,opponentIndex=index,
                    balance=dict(mode='geometric_shared_discount',cap=27,weights=dict(food=1,wood=.9,gold=1.1)),
                    scenario=dict(scenery=scenery[family], subjectOwner=2)))
        save(work/'requested.json',dict(schemaVersion=1,matchups=rows))
        for request in _load_batch(work/'requested.json')[1]:
            plan=plan_matchup(config,request);validate_plan_costs(plan)
            save(work/'plans'/f'{plan["jobId"]}.json',plan)
            family=plan['scenario']['family']
            # Validate one generated scenario per subject/family before any game starts.
            if family not in sample_families:
                output=work/'preflight-scenarios'/f'{family}.aoe2scenario';output.parent.mkdir(parents=True,exist_ok=True)
                sides=[stack['resolve_side'](plan[s]['civ'],plan[s]['slug']) for s in ('side2','side3')]
                with contextlib.redirect_stdout(io.StringIO()):
                    stack['build_run'](*sides,output,counts=(plan['side2']['count'],plan['side3']['count']),
                        template=capture_template_path(config,plan),player4_count=plan['scenario'].get('player4Count'),
                        subject_owner=plan['scenario']['subjectOwner'])
                    validation=_validate_scenario(config,plan,output,stack)
                save(output.with_suffix('.validation.json'),validation);sample_families.add(family)
            evidence.append(dict(jobId=plan['jobId'],opponent=plan['side3']['label'],
                counts=[plan[s]['count'] for s in ('side2','side3')],
                weightedCosts=[plan[s]['weightedCost'] for s in ('side2','side3')],scenario=plan['scenario']))
        for name in CATALOGS:
            # Byte-exact copy is required by the existing supervisor's hash check.
            dst=work/'frozen-catalogs'/name;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/'data'/name,dst)
        stats=analyzer.calculate_unique_unit_stats(civ,dict(base_id=master,display_name=label,
            unit_class=analyzer.get_unit(master)['class']),4)['stats']
        save(work/'subject-stats.json',[dict(civ_name=civ,final_hp=stats.hp,stats=dataclasses.asdict(stats))])
        save(work/'pilot.json',dict(schemaVersion=1,matchups=rows[:1]))
        save(work/'preflight.json',dict(state='PASSED',total=len(rows),jobs=evidence))
        save(work/'manifest.json',dict(schemaVersion=1,matchups=rows))
        campaigns.append(dict(key=slug,slug=slug,civilization=civ,unit=label,total=len(rows),workDirectory=str(work)))
    save(WORK/'queue.json',dict(schemaVersion=1,total=210,campaigns=campaigns,captureOnly=True,
        iterationsPerMatchup=5,opponents=14,scenery=scenery))
    print(json.dumps(dict(total=210,work=str(WORK),opponents=[(r['civ'],r['unit']) for r in references]),indent=2))


if __name__=='__main__':
    main()
