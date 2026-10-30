"""Deterministic, per-feature exports of the existing public projections.

Each dataset has its own identity and eligibility roster; presentation does
not become an implicit simulation/ranking/advisor eligibility decision.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import subprocess

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'apps/website'),str(ROOT)]
import app as website
from aoe2x.sim.unit_lines import UNIT_LINES
from aoe2x.advisor.best_units import load_advisor_power_units
from apps.website.services.release import release_metadata

def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(data): return hashlib.sha256(data).hexdigest()

def export(destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    # Draft exports are disposable. Published retention comes only from an
    # explicit archive, so reruns cannot collect stray old component versions.
    shutil.rmtree(destination/'data',ignore_errors=True)
    groups={key:{} for key in ['civilizations','rankings','simulator','advisor']}
    provenance={key:[] for key in groups}
    def api(group,name,url):
        with website.app.test_client() as client:
            response=client.get(url)
        assert response.status_code==200,(url,response.status_code)
        data=response.get_json()
        # Encoding must round-trip exactly, including null/missing fields.
        encoded=encode(data)
        assert json.loads(encoded)==data,url
        groups[group][name]=encoded
        provenance[group].append({'name':name,'source_endpoint':url,'sha256':sha(encoded)})
    page_names=website._get_page_civs()
    ranking_names=website._get_ref_civs()
    sim_names=sorted(website._sim_civs())
    for name in page_names: api('civilizations',name.lower(),'/api/civilizations/'+name)
    groups['civilizations']['overview']=encode(website.get_civ_overview_data())
    for line in sorted(UNIT_LINES): api('rankings',line,'/api/ref/unit-line/'+line)
    for name in sim_names: api('simulator',name.lower(),'/api/ref/civ/'+name)
    groups['simulator']['search']=encode(website._unit_search_index())
    calculation=load_advisor_power_units(build_number=website.current_build())
    groups['advisor']['calculation-roster']=encode(sorted(calculation))
    # Private computation inputs remain packaged read-only in Python; publish
    # only the displayed API projection and eligibility information here.
    for name in ranking_names: api('advisor',name.lower(),'/api/civ-power-units/'+name)
    rosters={'civilizations':page_names,'rankings':ranking_names,'simulator':sim_names,
             'advisor':ranking_names}
    components={}
    for group,files in groups.items():
        inputs={name:sha(data) for name,data in sorted(files.items())}
        configuration_inputs={}
        if group=='simulator':
            for name in ['data/golden/aoe2_reference_simulation.db',
                'apps/website/services/battles.py','aoe2x/js_simulation/scenario_config.py',
                'apps/website/services/mechanics.py','aoe2x/dbgen/v3_mechanics.py',
                'aoe2x/js_simulation/fixtures/golden_map.json',
                'aoe2x/js_simulation/fixtures/golden_formation_27v27.json',
                'aoe2x/js_simulation/fixtures/current_ranged_golden_formations.json']:
                configuration_inputs[name]=sha((ROOT/name).read_bytes())
            inputs['configuration_inputs']=configuration_inputs
        version=sha(encode(inputs))
        folder=destination/'data'/version
        folder.mkdir(parents=True,exist_ok=True)
        records={}
        for name,data in sorted(files.items()):
            target=folder/(name+'.json');target.write_bytes(data)
            records[name]={'url':f'/data/{version}/{name}.json','sha256':sha(data),
                           'bytes':len(data),'gzip_bytes':len(gzip.compress(data,mtime=0))}
        components[group]={'schema_version':1,'version':version,'civilizations':rosters[group],
                           'files':records,'source':'frozen public API and page projections'}
        if configuration_inputs:components[group]['configuration_inputs']=configuration_inputs
    components['advisor']['calculation_civilizations']=sorted(calculation)
    legacy=release_metadata(ROOT,ROOT/'data/golden')
    components['rankings']['published_metadata']=legacy['rankings']
    components['simulator']['reference_sha256']=sha((ROOT/'data/golden/aoe2_reference_simulation.db').read_bytes())
    components['civilizations']['supplement_build']=185872
    components['engine']={'schema_version':1,'version':legacy['engine']['source_sha256'],
                          'name':'simulationv3','mechanics_schema_version':legacy['mechanics_schema_version']}
    result={'schema_version':1,'components':components}
    (destination/'data-manifest.json').write_bytes(encode(result))
    subprocess.run(['node',str(ROOT/'scripts/migration/validate_exports.mjs'),str(destination)],check=True)
    evidence={'schema_version':1,'projections':provenance,'summary':{
      group:{'files':len(component['files']),'civilizations':len(component['civilizations']),
             'bytes':sum(x['bytes'] for x in component['files'].values()),
             'gzip_bytes':sum(x['gzip_bytes'] for x in component['files'].values())}
      for group,component in components.items() if 'files' in component}}
    evidence['roster_differences']={group:sorted(set(page_names)-set(names)) for group,names in rosters.items()}
    evidence['advisor_rosters_kept_separate']=True
    out=ROOT/'docs/migration/milestone-3'
    out.mkdir(parents=True,exist_ok=True)
    (out/'data-export-verification.json').write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n')
    return result

if __name__=='__main__':
    result=export(ROOT/'.migration-cache/exports')
    print(json.dumps({key:val['version'] for key,val in result['components'].items()}))
