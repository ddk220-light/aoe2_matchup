"""Two authorized Jarl experiments; append media and preserve prior trials.

The frozen derivative adds exactly one P3 opening patrol. Arbalester uses
the existing quiet P2 kiting AI; Jarl remains a ranged unit in all catalogs.
"""
import contextlib
import copy
import io
import shutil
from pathlib import Path
from aoe2x.lab.cli import _normalize_batch_row
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from prepare_norse_standard_capture import CATALOGS, load_scenario
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/jarl-kiting-followup'
SLUG = 'elite_jarl_varangians'

def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Already prepared; resume the existing two jobs')
    prior = next(c for c in read(ROOT/'data/local/donut-color-sixth-iteration/queue.json')['campaigns'] if c['slug']==SLUG)
    index_path = Path(prior['destination'])/'run.json'
    original = read(index_path)
    old_work = Path(prior['workDirectory'])
    camel = copy.deepcopy(next(r for r in read(old_work/'manifest.json')['matchups'] if r['opponentSlug']=='heavy_camel_turks'))
    descriptor = camel['scenario']['donut']
    source = ROOT/descriptor['path']
    assert sha256(source)==descriptor['sha256']
    template = load_scenario(source)
    before = [[(u.reference_id,u.unit_const,u.x,u.y) for u in template.unit_manager.units[p]] for p in range(9)]
    refs = [u.reference_id for u in template.unit_manager.get_player_units(3)]
    assert len(refs)==27
    # One order includes the rear slots beyond sight-range auto-engagement.
    # Never loop or retask units during combat; counts and positions stay fixed.
    trigger = template.trigger_manager.add_trigger('P3 opening patrol: all army slots')
    trigger.looping = False
    trigger.new_condition.timer(timer=1)
    trigger.new_effect.patrol(source_player=3, object_list_unit_id=template.unit_manager.units[3][0].unit_const,
        area_x1=0, area_y1=0, area_x2=15, area_y2=15, location_x=11, location_y=5)
    folder = WORK/'donut-template'
    folder.mkdir(parents=True,exist_ok=True)
    target = folder/'Winter Donut - Opening Patrol.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()): template.write_to_file(str(target))
    checked = load_scenario(target)
    assert before==[[(u.reference_id,u.unit_const,u.x,u.y) for u in checked.unit_manager.units[p]] for p in range(9)]
    assert all(t.elevation==0 for t in checked.map_manager.terrain)
    audit=read(ROOT/descriptor['auditPath'])
    audit.update(templateSha256=sha256(target),parentTemplateSha256=descriptor['sha256'],
        openingPatrol=dict(owner=3,timerSeconds=1,selection='whole-map army unit type',target=[11,5],looping=False),
        authorization='October 8: idle Heavy Camels and Arbalester kiting Jarl')
    audit_path=target.with_suffix('.audit.json'); save(audit_path,audit)
    for pattern in ('*.per','*.ai'):
        for ai in source.parent.glob(pattern): shutil.copyfile(ai,folder/ai.name)
    donut=dict(path=target.relative_to(ROOT).as_posix(),sha256=sha256(target),
        auditPath=audit_path.relative_to(ROOT).as_posix(),auditSha256=sha256(audit_path))
    camel.update(id='jkf_jarl_heavy_camel_opening_patrol_r7',iteration=7,colorCorrected=True,
        selectionReason='Opening patrol correction: two Camels did not move for 25.52/30 game seconds')
    camel['scenario']['donut']=donut
    arb=copy.deepcopy(camel)
    arb.update(id='jkf_arbalester_kites_jarl_donut_r1',side2='arbalester_saracens',civ2='Saracens',
        side3=SLUG,civ3='Varangians',subjectOwner=3,opponentSlug='arbalester_saracens',opponentIndex=2,iteration=1,
        selectionReason='User experiment: longer-range Arbalesters kite Jarl around the rock')
    arb['scenario'].update(subjectOwner=3,donutExperiment='arbalester_kites_jarl_v1')
    rows=[camel,arb]; config=load_config(); stack=_load_stack(config); directory=WORK/SLUG; validations=[]
    for row in rows:
        plan=plan_matchup(config,_normalize_batch_row(row,{})); validate_plan_costs(plan)
        old=next(r for r in original['matchups'] if r['plan']['side3']['slug']==row['opponentSlug'])['plan']
        counts={old[k]['slug']:old[k]['count'] for k in ('side2','side3')}
        assert all(plan[k]['count']==counts[plan[k]['slug']] for k in ('side2','side3'))
        save(directory/'plans'/(row['id']+'.json'),plan)
        path=directory/'preflight-scenarios'/(row['id']+'.aoe2scenario')
        sides=[stack['resolve_side'](plan[k]['civ'],plan[k]['slug']) for k in ('side2','side3')]
        with contextlib.redirect_stdout(io.StringIO()):
            stack['build_run'](*sides,path,counts=tuple(plan[k]['count'] for k in ('side2','side3')),
                template=capture_template_path(config,plan),remove_player4_buffer=True,subject_owner=row['subjectOwner'])
            check=_validate_scenario(config,plan,path,stack)
        save(path.with_suffix('.validation.json'),check)
        validations.append(dict(jobId=row['id'],countsUnchanged=True,openingPatrol=True,playerColors=plan['scenario']['playerColors']))
    save(directory/'previous-run.json',original)
    save(directory/'manifest.json',dict(schemaVersion=1,matchups=rows))
    save(directory/'pilot.json',dict(schemaVersion=1,matchups=rows))
    save(directory/'subject-stats.json',[dict(civ_name='Varangians',final_hp=105),dict(civ_name='Saracens',final_hp=40)])
    save(directory/'pilot-opponent-expectations.json',{camel['id']:dict(civ='Turks',hpPerUnit=140),arb['id']:dict(civ='Varangians',hpPerUnit=105)})
    save(directory/'preflight.json',dict(state='PASSED',total=2,cases=validations))
    for name in CATALOGS:
        path=directory/'frozen-catalogs'/name; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/'data'/name,path)
    save(WORK/'eligibility.json',dict(state='APPROVED',newTrials=2,preservedPriorTrials=len(original['matchups']),openingIdleEvidence='heavy-camel-r06-samples.json'))
    save(WORK/'queue.json',dict(schemaVersion=1,total=2,captureOnly=True,campaigns=[dict(
        key=SLUG,slug=SLUG,civilization='Varangians',unit='Elite Jarl',total=2,workDirectory=str(directory),
        destination=prior['destination'],originalIndexSha256=sha256(index_path),metadataDirectory='_jarl_kiting_followup_metadata',
        extensionKind='jarl-arbalester-kiting-and-camel-opening-patrol')]))
    print({'prepared':2,'counts':[(r['id'],read(directory/'plans'/(r['id']+'.json'))['side2']['count'],read(directory/'plans'/(r['id']+'.json'))['side3']['count']) for r in rows]})

if __name__=='__main__': main()
