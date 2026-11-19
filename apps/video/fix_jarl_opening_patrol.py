"""Correct only the ineffective Camel patrol; reuse the valid Arbalester film.

build_run replaces formation references, so fixed reference IDs in a template
cannot address the new army. Use a P3 whole-map unit-type filter instead; the
builder retargets PATROL filters just as it retargets TASK_OBJECT filters.
"""
import contextlib
import io
from prepare_jarl_kiting_followup import *
from aoe2x.lab.cli import _normalize_batch_row
from aoe2x.lab.live import _load_stack, _validate_scenario

def main():
    directory=WORK/SLUG
    manifest=read(directory/'manifest.json')
    old=manifest['matchups'][0]
    if old['id']=='jkf_jarl_heavy_camel_patrol_all_r7':
        raise FileExistsError('Already corrected; resume pending work only')
    source=ROOT/'data/local/arena-donut-standard/donut-template/Winter Donut.aoe2scenario'
    scn=load_scenario(source)
    t=scn.trigger_manager.add_trigger('P3 opening patrol: whole army by unit type')
    t.looping=False; t.new_condition.timer(timer=1)
    t.new_effect.patrol(source_player=3,object_list_unit_id=scn.unit_manager.units[3][0].unit_const,
        area_x1=0,area_y1=0,area_x2=15,area_y2=15,location_x=11,location_y=5)
    target=WORK/'donut-template/Winter Donut - Army Patrol.aoe2scenario'
    if not target.exists():
        with contextlib.redirect_stdout(io.StringIO()): scn.write_to_file(str(target))
    audit=read(source.with_suffix('.audit.json'))
    audit.update(templateSha256=sha256(target),parentTemplateSha256=sha256(source),
        openingPatrol=dict(owner=3,timerSeconds=1,selection='whole-map army unit type',target=[11,5],looping=False))
    save(target.with_suffix('.audit.json'),audit)
    row=copy.deepcopy(old)
    row.update(id='jkf_jarl_heavy_camel_patrol_all_r7',selectionReason='Fix verified rear-Camel idle: retargeted whole-army opening patrol')
    row['scenario']['donut']=dict(path=target.relative_to(ROOT).as_posix(),sha256=sha256(target),
        auditPath=target.with_suffix('.audit.json').relative_to(ROOT).as_posix(),auditSha256=sha256(target.with_suffix('.audit.json')))
    config=load_config(); stack=_load_stack(config)
    plan=plan_matchup(config,_normalize_batch_row(row,{}));validate_plan_costs(plan)
    save(directory/'plans'/(row['id']+'.json'),plan)
    p=directory/'preflight-scenarios'/(row['id']+'.aoe2scenario')
    sides=[stack['resolve_side'](plan[k]['civ'],plan[k]['slug']) for k in ('side2','side3')]
    with contextlib.redirect_stdout(io.StringIO()):
        stack['build_run'](*sides,p,counts=(26,27),template=capture_template_path(config,plan),remove_player4_buffer=True,subject_owner=2)
        check=_validate_scenario(config,plan,p,stack)
    generated=load_scenario(p)
    effect=generated.trigger_manager.triggers[-1].effects[0]
    assert effect.object_list_unit_id==generated.unit_manager.units[3][0].unit_const
    assert not effect.selected_object_ids
    save(p.with_suffix('.validation.json'),check)
    save(directory/'superseded-patrol-attempt.json',old)
    manifest['matchups'][0]=row;save(directory/'manifest.json',manifest)
    # Only the corrected Camel film is pending. Keep the already verified Arb.
    save(directory/'pilot.json',dict(schemaVersion=1,matchups=[row]))
    save(directory/'pilot-opponent-expectations.json',{row['id']:dict(civ='Turks',hpPerUnit=140)})
    save(WORK/'patrol-selection-correction.json',dict(state='PREPARED',newJob=row['id'],
        reason='Template reference IDs replaced by build_run; whole-army type filter survives generation',
        preservedArbalesterJob=manifest['matchups'][1]['id']))
    print({'pending':1,'reusedArbalester':True,'unitFilter':effect.object_list_unit_id})

if __name__=='__main__':main()
