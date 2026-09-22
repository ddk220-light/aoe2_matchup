from pathlib import Path
import json, re
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'asset-manifest.json').read_text())
assert len(manifest['units'])==84
assert len({u['slug'] for u in manifest['units']})==84
assert all(u['complete'] and not u['missing'] for u in manifest['units'])
standard=[]
for u in manifest['units']:
    s=u['slug']; d=ROOT/'graphics/units'/s
    standard += [d/'icon.png',d/'icon_transparent.png']+[d/f'{s}_{suffix}' for suffix in ('idle_dir06.png','idle_dir06_dat4x.png','idle_dir06_ultrasharp4x.png','idle_dir06_dat4x_blue.png','attack_dir06_dat4x.gif')]
assert len(standard)==588 and all(p.is_file() for p in standard)
art=json.loads((HERE/'art-validation.json').read_text())
assert art['complete_sets']==art['expected_sets']==21
assert sum(len(r['checks']) for r in art['results'])==63
for name in ('icon.png','icon_transparent.png'):
    actual=Image.open(ROOT/'graphics/units/flemish_militia'/name).convert('RGBA')
    source=Image.open(ROOT/'.scratch/asset-completion/dat-icons/flemish_militia'/name).convert('RGBA')
    assert actual.size==source.size and actual.tobytes()==source.tobytes()
links=[]
for p in (ROOT/'graphics/ASSET_INVENTORY_2026-09-22.md',HERE/'REVIEW.md'):
    links+=re.findall(r'\]\(<([^>]+)>\)',p.read_text(encoding='utf-8'))
missing=[s for s in links if not Path(s).exists()]
assert not missing,missing
report={
    'scoped_units':84,'standard_asset_files':588,'new_standard_files':100,
    'new_generated_sets':21,'new_generated_files':63,'corrected_existing_icons':2,
    'missing_files':[], 'local_links_checked':len(links),'broken_links':[],
    'flemish_militia_current_DAT_icon_match':True,
    'visual_fidelity_review_required':[u['slug'] for u in manifest['units'] if u['visual_review_status']=='owner-review-required'],
    'owner_approval':'New art is pending; no golden promotion performed.'
}
(HERE/'completion-summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
