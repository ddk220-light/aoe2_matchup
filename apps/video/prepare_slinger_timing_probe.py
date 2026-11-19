"""One Slinger Donut timing test, preserving all existing trials and counts."""
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
from donut_ai_timing import protect_slinger_volley, slinger_timing
from prepare_jomsviking_capture import DAT
from prepare_norse_standard_capture import CATALOGS, load_scenario
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/slinger-donut-timing'
SLUG = 'elite_varangian_guard_varangians'


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Probe already prepared: resume, never reprepare')
    prior = next(c for c in read(ROOT/'data/local/donut-color-sixth-iteration/queue.json')['campaigns'] if c['slug'] == SLUG)
    old = Path(prior['workDirectory'])
    row = copy.deepcopy(next(r for r in read(old/'manifest.json')['matchups'] if r['opponentSlug'] == 'imp_slinger_incas'))
    old_plan = read(old/'plans'/(row['id']+'.json'))
    index = Path(prior['destination'])/'run.json'
    original = read(index)
    if shutil.disk_usage(ROOT).free < 8*2**30 or shutil.disk_usage(index.parent).free < 4*2**30:
        raise RuntimeError('Storage reserve unavailable')
    descriptor = row['scenario']['donut']
    source = ROOT/descriptor['path']
    assert sha256(source) == descriptor['sha256']
    template = load_scenario(source)
    pd = template.sections['PlayerDataTwo']
    embedded = pd.retriever_map['ai_files'].data[1].retriever_map['ai_per_file_text']
    timing = slinger_timing(DAT)
    ai = protect_slinger_volley(embedded.data, timing)
    old_name = pd.ai_names[1].replace('.ai', '.per')
    name = 'ddkDonutSlingerTiming'
    pd.ai_names[1] = name+'.ai'
    embedded.data = ai
    entries = template.sections['Files'].retriever_map['ai_files'].data
    matched = 0
    for entry in entries:
        if entry.retriever_map['ai_file_name'].data == old_name:
            entry.retriever_map['ai_file_name'].data = name+'.per'
            entry.retriever_map['ai_file'].data = ai
            matched += 1
    assert matched == 1
    folder = WORK/'donut-template'; folder.mkdir(parents=True, exist_ok=True)
    (folder/(name+'.per')).write_text(ai, encoding='utf-8')
    (folder/(name+'.ai')).write_bytes(b'')
    target = folder/'Winter Donut - Slinger Timing.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()): template.write_to_file(str(target))
    audit = read(ROOT/descriptor['auditPath'])
    audit.update(templateSha256=sha256(target), parentTemplateSha256=descriptor['sha256'],
        aiName=name, aiSha256=sha256(folder/(name+'.per')), unitTiming=timing,
        authorization='October 8: fix Slinger windup cancellation; one recorded probe')
    audit_path = target.with_suffix('.audit.json'); save(audit_path, audit)
    row.update(id='slinger_timing_varangian_guard_donut_r7', iteration=7,
               selectionReason='Slinger animation-timed firing window; preserve r01-r06')
    row['scenario']['donut'] = dict(path=target.relative_to(ROOT).as_posix(), sha256=sha256(target),
        auditPath=audit_path.relative_to(ROOT).as_posix(), auditSha256=sha256(audit_path))
    directory = WORK/SLUG
    config = load_config(); stack = _load_stack(config)
    plan = plan_matchup(config, _normalize_batch_row(row, {})); validate_plan_costs(plan)
    assert all(plan[k]['count'] == old_plan[k]['count'] for k in ('side2', 'side3'))
    save(directory/'plans'/(row['id']+'.json'), plan)
    path = directory/'preflight-scenarios'/(row['id']+'.aoe2scenario')
    sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2','side3')]
    with contextlib.redirect_stdout(io.StringIO()):
        stack['build_run'](*sides, path, counts=tuple(plan[k]['count'] for k in ('side2','side3')),
            template=capture_template_path(config,plan), remove_player4_buffer=True, subject_owner=3)
        check = _validate_scenario(config,plan,path,stack)
    save(path.with_suffix('.validation.json'), check)
    save(directory/'previous-run.json', original)
    save(directory/'manifest.json', dict(schemaVersion=1,matchups=[row]))
    save(directory/'pilot.json', dict(schemaVersion=1,matchups=[row]))
    save(directory/'subject-stats.json', [dict(civ_name='Incas',final_hp=35)])
    save(directory/'pilot-opponent-expectations.json', {row['id']:dict(civ='Varangians',hpPerUnit=80)})
    save(directory/'preflight.json', dict(state='PASSED',total=1,countsUnchanged=True,unitTiming=timing))
    for filename in CATALOGS:
        p=directory/'frozen-catalogs'/filename; p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old/'frozen-catalogs'/filename, p)
    save(WORK/'eligibility.json', dict(state='APPROVED', newTrials=1,
        preservedPriorTrials=len(original['matchups']), timing=timing,
        baselineJobId='dcc6_elite_varangian_guard_varangians_imp_slinger_incas_r6'))
    save(WORK/'queue.json', dict(schemaVersion=1,total=1,captureOnly=True,campaigns=[dict(
        key=SLUG,slug=SLUG,civilization='Varangians',unit='Elite Varangian Guard',total=1,
        workDirectory=str(directory),destination=prior['destination'],originalIndexSha256=sha256(index),
        metadataDirectory='_slinger_timing_metadata',extensionKind='slinger-animation-timing',
        documentationPath='docs/video-production/INCA_SLINGER_STANDARD_CAPTURE.md')]))
    print(dict(prepared=1,counts=[plan[k]['count'] for k in ('side2','side3')],timing=timing))


if __name__ == '__main__':
    main()
