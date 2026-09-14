"""Generate civilization costs from an isolated installed-DAT extraction and audit archives.

Never modifies archived plans, recordings, or published metadata.
Run after aoe2x.extract.run.extract_all into data/local/cost-audit-extracted.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
OUT = ROOT / 'data/local/production-audit'
EXTRACTED = ROOT / 'data/local/cost-audit-extracted'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = EXTRACTED
    analyzer = module.UnitAnalyzer()
    registry = {r['slug']: r for r in read(ROOT/'data/local/cost-audit-registry.json')}
    for filename in ['unique-unit-roster.json', 'recording-subjects.json']:
        for row in read(ROOT/'data'/filename)['units']:
            registry.setdefault(row['slug'], row)
    plans = [(p, read(p)) for p in (LAB/'runs').glob('*/plan.json')]
    identities = {(r['civ'], slug): r for slug, r in registry.items()}
    for _, p in plans:
        for side in ['side2', 'side3']:
            s = p[side]
            if s['slug'] in registry:
                identities[(s['civ'], s['slug'])] = {**registry[s['slug']], 'civ': s['civ']}
    entries, unresolved = {}, []
    for (civ, slug), row in sorted(identities.items()):
        try:
            unit = analyzer.get_unit(row['master'])
            if not unit or civ not in analyzer.civ_name_to_id:
                raise ValueError('Missing installed unit or civilization')
            # Same effect chain as unit stats, but retain cost-changing commands as evidence.
            stats = analyzer.get_base_stats(unit)
            base = {r: getattr(stats, 'cost_'+r) for r in ['food','wood','gold']}
            stages = []
            disabled = analyzer.get_disabled_techs(civ)
            standard = [analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(row['master'], unit['class'], 4)) if t not in disabled and t in analyzer.tech_effect_map]
            stages += standard
            stages += analyzer.get_civ_bonus_techs_for_unit(civ, row['master'], unit['class'], 4)
            stages += analyzer.get_unique_techs_for_unit(civ, row['master'], unit['class'], 4)
            effects = []
            for tech in stages:
                for cmd in tech.get('commands', []):
                    if cmd.get('c') not in (100, 103, 104, 105):
                        continue
                    before = [getattr(stats, 'cost_'+r) for r in base]
                    analyzer.apply_effect_command(cmd, stats, row['master'], unit['class'])
                    after = [getattr(stats, 'cost_'+r) for r in base]
                    if before != after:
                        effects.append({'techId': tech['tech_id'], 'name': tech.get('tech_name'), 'command': cmd, 'before': before, 'after': after})
            purchase = {r: round(getattr(stats, 'cost_'+r)) for r in base}
            # Installed help IDs 26516/26517 explicitly say trained in pairs;
            # DAT creatable_type=3 on 2579/2581, versus Karambit type=2.
            # Population usage is deliberately unrelated to this divisor.
            batch = 2 if row['master'] in (2579,2581) else 1
            final = {r: value/batch for r,value in purchase.items()}
            if min(final.values()) < 0 or sum(final.values()) <= 0:
                raise ValueError('Invalid final purchase cost')
            entries[civ+'|'+slug] = {'civ':civ,'slug':slug,'master':row['master'],'label':row['label'],'baseCost':base,'purchaseCost':purchase,'unitsPerPurchase':batch,'productionEvidence':'Installed help 26516/26517 and DAT creatable_type=3' if batch==2 else 'One physical unit per purchase; population is not a cost divisor','effectiveCost':final,'effects':effects}
        except Exception as error:
            unresolved.append({'civ':civ,'slug':slug,'error':str(error)})
    provenance = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in EXTRACTED.glob('*.json')}
    catalog = {'schemaVersion':1,'costBasis':'fully_upgraded_imperial_v1','source':'Installed DAT extracted in isolation; standard technologies, own civilization bonuses and unique technologies; per-resource rounding after effects','extractionHashes':provenance,'units':entries,'unresolved':unresolved}
    (ROOT/'data/recording-costs.json').write_text(json.dumps(catalog,indent=2)+'\n')
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for path,p in plans:
        recordings=list((path.parent/'live').glob('*/recording.json'))
        if not recordings: continue
        old=[p[s]['count'] for s in ['side2','side3']]
        keys=[p[s]['civ']+'|'+p[s]['slug'] for s in ['side2','side3']]
        row={'jobId':path.parent.name,'subject':p['side2']['label'],'opponent':p['side3']['label'],'plan':str(path),'oldCounts':old,'recordings':[str(r) for r in recordings]}
        if any(k not in entries for k in keys):
            row.update(action='UNRESOLVED',reason='Missing cost identity');results.append(row);continue
        weights=p['balance'].get('weights',{'food':1,'wood':1,'gold':1})
        costs=[sum(e['effectiveCost'][r]*weights[r] for r in weights) for e in [entries[k] for k in keys]]
        cap=p['balance']['cap'];budget=p['balance'].get('maxResources',float('inf'))
        if p['balance']['mode']=='equal_resources':
            a,b=costs
            n=min(cap,int(budget//min(a,b))) if budget!=float('inf') else cap
            new=[n,int(n*a//b)] if a<=b else [int(n*b//a),n]
        else:new=old
        row.update(effectiveCosts=costs,newCounts=new,action='RETAKE' if old!=new else 'REUSE_COUNTS_MATCH',oldCosts=[p[s]['weightedCost'] for s in ['side2','side3']])
        row['costMetadataChanged']=row['oldCosts']!=costs
        row['rawAvailable']=any((r.parent/read(r)['files']['video']['path']).exists() for r in recordings)
        row['framesAvailable']=all((r.parent/read(r)['files']['frames']['path']).exists() for r in recordings)
        results.append(row)
    report={'scope':'All local saved plans with recording.json, including experiments/retakes; episode manifests must choose canonical runs','summary':dict(Counter(r['action'] for r in results)),'unresolvedCostIdentities':unresolved,'jobs':results}
    (OUT/'cost-audit.json').write_text(json.dumps(report,indent=2))
    lines=['# Recorded battle cost audit','','Production remains paused. This report compares recorded counts to installed-data Imperial purchase costs. Count reuse is not final validation of all gameplay conditions.','','| Subject | Retake | Counts match | Unresolved |','|---|---:|---:|---:|']
    for subject in sorted({r['subject'] for r in results}):
        counts=Counter(r['action'] for r in results if r['subject']==subject)
        lines.append(f"| {subject} | {counts['RETAKE']} | {counts['REUSE_COUNTS_MATCH']} | {counts['UNRESOLVED']} |")
    lines+=['','Detailed per-job evidence: `cost-audit.json`. Unaffected chapters may be cut from retained full compilations when individual videos were cleaned up. Recompute all chapter timestamps and Shorts cost rankings. Existing YouTube IDs cannot have their media replaced by this pipeline; replacements must be new uploads, with old uploads left untouched until user decides.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'costIdentities':len(entries),'unresolved':unresolved,'recordedJobs':len(results),'summary':report['summary']}))

if __name__=='__main__':main()
