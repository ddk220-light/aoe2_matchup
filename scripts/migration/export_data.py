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
sys.path[:0]=[str(ROOT),str(ROOT/'apps/backend')]
import aoe2_api.web as website
from aoe2x.sim.unit_lines import UNIT_LINES
from aoe2_api.services.release import release_metadata
from aoe2_api.services.advisor import advisor_catalog
from aoe2_api.services.economy import economy_civilizations

# The simulator data version hashes these configuration inputs keyed by path.
# The two API services kept their pre-move labels (the files moved byte-identical
# from apps/website/services/ to apps/backend/aoe2_api/services/): changing a key
# would change the simulator version, hence the /data/<version>/ URLs and the
# X-AoE2-Simulation-Version header, and open tabs of the previous release would
# get 409 responses although nothing they depend on changed.
SIMULATOR_CONFIGURATION_INPUTS={
    'data/golden/aoe2_reference_simulation.db':'data/golden/aoe2_reference_simulation.db',
    'apps/website/services/battles.py':'apps/backend/aoe2_api/services/battles.py',
    'aoe2x/js_simulation/scenario_config.py':'aoe2x/js_simulation/scenario_config.py',
    'apps/website/services/mechanics.py':'apps/backend/aoe2_api/services/mechanics.py',
    'aoe2x/dbgen/v3_mechanics.py':'aoe2x/dbgen/v3_mechanics.py',
    'aoe2x/js_simulation/fixtures/golden_map.json':'aoe2x/js_simulation/fixtures/golden_map.json',
    'aoe2x/js_simulation/fixtures/golden_formation_27v27.json':'aoe2x/js_simulation/fixtures/golden_formation_27v27.json',
    'aoe2x/js_simulation/fixtures/current_ranged_golden_formations.json':'aoe2x/js_simulation/fixtures/current_ranged_golden_formations.json',
}

def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(data): return hashlib.sha256(data).hexdigest()

def export(destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    # Draft exports are disposable. Published retention comes only from an
    # explicit archive, so reruns cannot collect stray old component versions.
    shutil.rmtree(destination/'data',ignore_errors=True)
    groups={key:{} for key in ['civilizations','rankings','simulator','advisor','economy']}
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
        # Economy files are the API's canonical bytes, so static and API copies are identical.
        if group=='economy':assert encoded==response.data,url
        provenance[group].append({'name':name,'source_endpoint':url,'sha256':sha(encoded)})
    page_names=website._get_page_civs()
    ranking_names=website._get_ref_civs()
    sim_names=sorted(website._sim_civs())
    for name in page_names: api('civilizations',name.lower(),'/api/civilizations/'+name)
    groups['civilizations']['overview']=encode(website.get_civ_overview_data())
    for line in sorted(UNIT_LINES): api('rankings',line,'/api/ref/unit-line/'+line)
    for name in sim_names: api('simulator',name.lower(),'/api/ref/civ/'+name)
    groups['simulator']['search']=encode(website._unit_search_index())
    advisor = advisor_catalog()
    calculation = advisor['civilizations']
    api('advisor', 'catalog', '/api/advisor-catalog')
    for name in calculation:
        api('advisor', name.lower(), '/api/advisor-matchups/' + name)
    # Army economics: one document per civilization + shared metadata, read by
    # apps/web/src/features/economy/ (static file first, API fallback).
    economy=economy_civilizations()
    api('economy','metadata','/api/economy')
    for name in economy:
        api('economy',name.lower(),'/api/economy/'+name)
    rosters={'civilizations':page_names,'rankings':ranking_names,'simulator':sim_names,
             'advisor':calculation,'economy':economy}
    components={}
    for group,files in groups.items():
        inputs={name:sha(data) for name,data in sorted(files.items())}
        configuration_inputs={}
        if group=='simulator':
            for name,path in SIMULATOR_CONFIGURATION_INPUTS.items():
                configuration_inputs[name]=sha((ROOT/path).read_bytes())
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
    # Schema 3: matchup rows carry the Revision 4 eco fields (categories, winner HP, 60-s
    # investment) from data/golden/advisor_cell_metrics.json.gz; units carry full_research_vm.
    components['advisor']['schema_version']=3
    components['advisor']['source']='Saved provisional first-pass matchup evidence plus per-cell army-economics metrics; no live simulations'
    economy_metadata=json.loads(groups['economy']['metadata'])['metadata']
    components['economy']['source']='Compiled army-economics runtime (data/army_economics/army_context.jsonl.gz); pair calculation runs in the browser'
    components['economy']['context_version']=economy_metadata['contextVersion']
    components['economy']['context_schema_version']=economy_metadata['schemaVersion']
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
