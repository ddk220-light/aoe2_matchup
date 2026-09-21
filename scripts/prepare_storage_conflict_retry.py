"""Keep differing source metadata in separate archive versions; never overwrite."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/local/storage-consolidation-20260916'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
state=read(WORK/'status.json')
if not state['state'].startswith('COMPLETE'):raise SystemExit('Initial transfer must finish first')
plan=read(WORK/'plan.json')
approved={m['source']:m for m in plan['moves']}
rows={}
for issue in state['issues']:
    source=issue.get('source')
    if not issue.get('error','').startswith('Destination conflict:') or source not in approved:continue
    path=Path(source)
    if not path.is_dir() or path.is_junction():continue
    if not path.resolve().is_relative_to(ROOT):raise ValueError('Source outside workspace')
    rows[source]={**approved[source],'destination':str(Path(plan['destinationRoot'])/'retained-source-versions'/path.name)}
retry={**plan,'prunes':[],'moves':list(rows.values())}
(WORK/'conflict-retry-plan.json').write_text(json.dumps(retry,indent=2),encoding='utf-8')
print(json.dumps({'packages':len(rows),'purpose':'Preserve source versions separately from differing render-workspace metadata; no overwrite or additional pruning'}))
