"""Map audit findings to retained compilations and selected Shorts without edits."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'
OUT=ROOT/'data/local/production-audit'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    cost=read(OUT/'cost-audit.json');jobs={j['jobId']:j for j in cost['jobs']}
    setup=read(OUT/'setup-audit.json');hp=read(OUT/'initial-hp-audit.json')
    hp_jobs={x['jobId'] for x in hp['flags']}
    compilations=[]
    for path in (LAB/'compilations').glob('*/final/manifest.json'):
        c=read(path);rows=c.get('results',[]);offset=0
        if not rows and (path.parent.parent/'manifest.json').exists():
            old=read(path.parent.parent/'manifest.json');rows=old.get('chapters',[]);offset=c.get('introDuration',0)
        mapped=[]
        for row in rows:
            jid=row['jobId'];j=jobs.get(jid)
            mapped.append({'jobId':jid,'costAction':j['action'] if j else 'UNRESOLVED','oldCounts':j.get('oldCounts') if j else None,'correctedCounts':j.get('newCounts') if j else None,'initialHpReview':jid in hp_jobs,'extractStartSeconds':row['startSeconds']+offset,'extractDurationSeconds':row['durationSeconds'],'replacementJobId':jid+'_cost_v2' if j and j['action']=='RETAKE' else None})
        compilations.append({'episode':path.parent.parent.name,'fullVideo':c['output'],'fullVideoExists':Path(c['output']).exists(),'chapters':mapped,'actions':dict(Counter(x['costAction'] for x in mapped))})
    shorts=[]
    for p in (LAB/'shorts').glob('*/selection.json'):
        d=read(p)
        for x in d.get('items',[]):
            jid=x.get('jobId');j=jobs.get(jid)
            shorts.append({'selection':str(p),'jobId':jid,'costAction':j['action'] if j else 'UNRESOLVED','initialHpReview':jid in hp_jobs,'rerankRequired':True})
    repair={'status':'PRODUCTION_PAUSED_AUDIT_REVIEW_REQUIRED','costCatalog':'data/recording-costs.json','compilations':compilations,'shorts':shorts,'policy':['Retakes get new job IDs; never rewrite old plan provenance','Keep originals and frames until all replacements pass QA','Reuse matching-count chapters only after independent setup and stat/HP review','Replace changed chapters, rebuild timestamps/description, and reselect Shorts from corrected outcomes','No resume, cleanup or upload while unresolved audit hold remains']}
    (OUT/'repair-plan.json').write_text(json.dumps(repair,indent=2))
    lines=['# Production correctness audit','','All capture, rendering, uploads and cleanup are paused. No published videos were changed.','',
    '## Verified scope','',f"- {len(jobs)} archived matchup plans, {setup['recordingsChecked']} recorded scenario bundles, {len(compilations)} retained final compilations.",
    '- Costs regenerated from this PC\'s installed DAT in an isolated extraction; 99 unit/civilization identities resolved.',
    '- Army size is a physical unit count, not population. Blackwood purchase produces two units; Karambit purchase produces one.',
    f"- Scenario checks: {setup['flaggedRecordings']} flagged bundles for civilization, master ID, counts, positions, Post-Imperial age, spectator civ, Golden diplomacy/AI/triggers/camera/P4 buffer.",
    f"- Initial recorded HP checked in {hp['checked']} bundles; {len(hp['flags'])} flags, all Elite Mameluke: observed 120 HP per unit versus data-derived 125. This discrepancy is unresolved, not evidence to change the game.",
    '', '## Cost fixes','',
    '- Lab planner now uses per-individual effective Imperial cost, with catalog hash in each plan. Capture rejects legacy or stale cost plans.',
    '- Fixed ignored absolute food/wood/gold SET_ATTRIBUTE effects. Magyar Huszar converts 35 food + 45 gold into 80 food + 0 gold; equal-weight total is unchanged.',
    '- Blackwood pair costs 35 wood + 45 gold; individual cost is 17.5 wood + 22.5 gold. Prior roster had 25 wood + 15 gold, same total but wrong composition.',
    '- Full Inca Slinger rebuild is appropriate: 72 of 74 recorded chapter counts change. The two matching-count chapters may be reused only after the broader checks.',
    '', '## Final compilation repair inventory','', '| Compilation | Chapters | Cost retakes | Counts reusable* | HP review |','|---|---:|---:|---:|---:|']
    for c in compilations:
        lines.append(f"| {c['episode']} | {len(c['chapters'])} | {c['actions'].get('RETAKE',0)} | {c['actions'].get('REUSE_COUNTS_MATCH',0)} | {sum(x['initialHpReview'] for x in c['chapters'])} |")
    lines+=['','*Matching counts only; does not certify every stat, timing, or label. `repair-plan.json` contains each chapter\'s exact source interval and proposed replacement job ID.',
    '', '## Remaining checks before production can resume','',
    '- Resolve Elite Mameluke 120 vs 125 HP and any resulting static overlay/simulation reference mismatch.',
    '- Independently confirm researched technologies and actual attack/armor/range. Scenario Post-Imperial age and correct HP alone do not prove every stat.',
    '- Recheck per-unit overlay alignment evidence and victory/conversion terminal rows against selected videos; no claim that every historical frame/audio track was manually re-reviewed.',
    '- Recompute all Shorts category rankings and chapter winners/HP from corrected battles. Rebuild the descriptions and timestamps after edits.',
    '- Verify corrected planner counts against a small in-game acceptance set before authorizing mass recapture. No such acceptance recordings were made during this pause.',
    '', '## Recovery','',
    'Use retained full compilations for unaffected chapters when individual videos were cleaned up. Every affected battle gets a new capture and overlays, then the full compilation and Shorts are rebuilt. Preserve original full videos and frames. Existing uploads remain untouched; publishing replacements is a later step.',
    '', 'Evidence files: `cost-audit.json`, `setup-audit.json`, `initial-hp-audit.json`, `repair-plan.json`.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'compilations':len(compilations),'chapters':sum(len(c['chapters']) for c in compilations),'costRetakes':sum(c['actions'].get('RETAKE',0) for c in compilations),'shortsInventoried':len(shorts)}))
if __name__=='__main__':main()
