#!/usr/bin/env python3
"""Combine reviewed inputs and saved battles; screen economic reversals without changing combat outcomes."""
import csv,hashlib,json,math,os,re,sqlite3,statistics
from collections import defaultdict,Counter
from pathlib import Path
from army_economics_paths import scratch_path
from eco_scope import mechanic_scope

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('ARMY_CONTEXT_OUT',str(ROOT/'aoe2x/js_simulation/calibration/economy/army-context-2026-11-09')))
SOURCES={'eco':scratch_path('economy-review/labor-inputs/labor-inputs.sqlite'),
         'production':scratch_path('economy-review/corrected-production/production-review.sqlite'),
         'research':Path(os.environ.get('ARMY_RESEARCH_DB',str(scratch_path('research-review/current-results/unit-upgrades.sqlite'))))}
CAMPAIGN=ROOT/'aoe2x/js_simulation/calibration/campaigns/unit-rankings-consolidated-2026-10-29'
RES=('food','wood','stone','gold')
def load(p):return json.loads(Path(p).read_text())
def dump(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def connect(p):
 c=sqlite3.connect(f'file:{p}?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def table(c,name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r));types=[]
 for k in keys:
  vals=[r[k] for r in rows if r.get(k) is not None]
  types.append('INTEGER' if vals and all(isinstance(v,(int,bool)) for v in vals) else 'REAL' if vals and all(isinstance(v,(int,float)) for v in vals) else 'TEXT')
 c.execute(f'CREATE TABLE "{name}" ('+','.join(f'"{k}" {t}' for k,t in zip(keys,types))+')')
 def value(v):return dump(v) if isinstance(v,(dict,list)) else int(v) if isinstance(v,bool) else v
 c.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" for k in keys)})',[[value(r.get(k)) for k in keys] for r in rows])
def csv_write(name,rows):
 if not rows:return
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
  for r in rows:w.writerow({k:dump(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def normalize(s):return re.sub('[^a-z0-9]','',s.lower())

def main():
 specs=load(OUT/'eco-inputs.json');rates=load(OUT/'gather-rates.json')
 assert len(specs)==56 and len(rates)==224,'Economy run incomplete'
 spec={s['civ_name']:s for s in specs};rate={(r['civ_name'],r['resource']):r['rate'] for r in rates}
 for row in rates:
  for r in row['runs']:assert max(abs(v) for v in r['checks'].values())<1e-5
 dbpath=OUT/'army-context.sqlite'
 if dbpath.exists():dbpath.unlink()  # Only this generated output is replaceable.
 db=sqlite3.connect(dbpath);db.row_factory=sqlite3.Row
 src={k:connect(p) for k,p in SOURCES.items()}
 for name,p in SOURCES.items():
  db.execute(f'ATTACH DATABASE ? AS {name}_source',(str(p),))
  for t, in src[name].execute("SELECT name FROM sqlite_master WHERE type='table'"):
   db.execute(f'CREATE TABLE "{name}_{t}" AS SELECT * FROM {name}_source."{t}"')
 for view in ['unit_upgrade_data','unit_upgrade_totals','unit_research_buildings']:
  db.execute(f'CREATE TABLE research_{view} AS SELECT * FROM research_source.{view}')
 table(db,'gather_rates',rates)
 # One row per mechanic, including unmodeled hooks. A complete inventory is not
 # confused with complete quantitative support for every possible game state.
 audit=[]
 for s in specs:
  for m in s['mechanisms']:
   category=m['category']
   status=('modeled_parameters' if category in ['work_rate','carry','movement','resource_yield','recurring_cost','farm_event','drop_off','construction']
           else 'conditional_not_credited' if category in ['coupled_income','area_effect','replacement_refund','conditional_income','pasture']
           else 'outside_baseline_or_inventory_only')
   if category=='resource_yield' and m['effect_id'] in [621,1381]:status='conditional_not_credited'
   scope=mechanic_scope(m)
   if scope.startswith('excluded_') or scope in ['conditional_trade_or_relic','conditional_water_economy']:status='outside_late_game_land_baseline'
   audit.append(dict(civ_name=s['civ_name'],tech_id=m['tech_id'],effect_id=m['effect_id'],mechanic=m['source_label'],category=category,late_game_scope=scope,status=status,description=m['description'],evidence=m['evidence']))
 table(db,'mechanic_coverage',audit)
 def labor(civ,cost):
  total=0.
  for res in RES:
   amount=cost.get(res,0)
   if abs(amount)<1e-10:continue
   rr=rate[civ,res]
   if rr is None or rr<=0:return None
   total+=amount/rr
  if cost.get('food',0):
   s=spec[civ];wood=rate[civ,'wood']
   if not wood:return None
   total+=cost['food']*s['farm_wood']/(s['farm_food']*s['farm_yield']*wood)
  return total
 costs={(r['civ_name'],r['unit_id']):dict(r) for r in src['eco'].execute('select * from replacement_resource_costs')}
 research_units={(r['civ_name'],r['unit_id']):dict(r) for r in src['research'].execute('select * from units')}
 upgrades=defaultdict(dict)
 for row in src['research'].execute("select * from unit_upgrade_data where scope='direct'"):
  r=dict(row);upgrades[r['unit_key']][r['tech_id']]=r
 buildings=defaultdict(list)
 for r in src['research'].execute("select * from unit_research_buildings where scope='direct'"):buildings[r['unit_key']].append(dict(r))
 units=[];lookup={};bykey={}
 for r in src['production'].execute('select * from unit_production'):
  p=dict(r);c=costs[p['civ_name'],p['unit_id']];cost={res:c[res] for res in RES};key=f"{p['civ_name']}:{p['reference_unit_id']}"
  u=research_units.get((p['civ_name'],p['unit_id']))
  flags=list(spec[p['civ_name']]['flags'])
  if 'konnik' in p['unit_name'].lower():flags.append('Dismounted survivors: mounted-unit deaths cannot be inferred from survivor count alone')
  if p['status']!='calculated' or p['review_flags']:flags.append('Production review: '+p['status']+' '+(p['review_flags'] or ''))
  unit=dict(unit_key=key,civ_name=p['civ_name'],unit_id=p['unit_id'],unit_name=p['unit_name'],reference_unit_id=p['reference_unit_id'],
    **cost,labor_seconds=labor(p['civ_name'],cost),train_seconds=p['final_train_seconds'],
    production_building=p['building'],production_building_id=p['building_id'],building_wood_equivalent=p['building_wood_equivalent'],
    production_building_cost={res:p['building_'+res] for res in RES},production_modifiers=p['applied_modifiers'],
    research_unit_key=u['unit_key'] if u else None,flags=flags)
  unit['production_building_resource_labor']=labor(p['civ_name'],unit['production_building_cost'])
  units.append(unit);lookup[p['civ_name'],normalize(p['unit_name'])]=unit;bykey[key]=unit
 table(db,'unit_economy',units)
 civs=sorted(spec,key=len,reverse=True)
 def resolve(label):
  civ=next((n for n in civs if label.startswith(n+' ')),None)
  assert civ,label
  u=lookup.get((civ,normalize(label[len(civ)+1:])))
  assert u,label
  return u
 def tech_comparison(a,b):
  aa=upgrades[a['research_unit_key']];bb=upgrades[b['research_unit_key']]
  common=sorted(aa.keys()&bb.keys());onlya=sorted(aa.keys()-bb.keys());onlyb=sorted(bb.keys()-aa.keys())
  def amounts(rows):return {kind:{res:sum(r[kind+'_'+res] for r in rows) for res in RES} for kind in ['upfront','reward','net']}
  def workload(rows):return None if any(r['final_seconds'] is None for r in rows) else sum(r['final_seconds'] for r in rows)
  ca,cb=[aa[i] for i in common],[bb[i] for i in common]
  ac,bc=amounts(ca),amounts(cb)
  return dict(common_ids=common,loser_common_cost=ac,winner_common_cost=bc,
   loser_common_seconds=workload(ca),winner_common_seconds=workload(cb),
   loser_exclusive_ids=onlya,winner_exclusive_ids=onlyb,
   loser_exclusive_cost=amounts([aa[i] for i in onlya]),winner_exclusive_cost=amounts([bb[i] for i in onlyb]),
   loser_research_buildings=buildings[a['research_unit_key']],winner_research_buildings=buildings[b['research_unit_key']],
   common_net_cost_difference_loser_minus_winner={res:ac['net'][res]-bc['net'][res] for res in RES},
   common_loser_cost_dominates=all(ac['net'][res]<=bc['net'][res]+1e-8 for res in RES) and any(ac['net'][res]<bc['net'][res]-1e-8 for res in RES))
 rawruns=defaultdict(list);battle_rows=[]
 for line_no,line in enumerate((CAMPAIGN/'runs.jsonl').open(),1):
  r=json.loads(line);rawruns[r['matchupId']].append(r)
  battle_rows.append(dict(source_matchup_id=r['matchupId'],seed=r['seed'],winner_owner=r['winnerOwner'],
   side2=r['result']['side2'],side3=r['result']['side3'],starting_hp=r['result']['startingHpByOwner'],remaining=r['result']['remainingByOwner'],
   simulation_seconds=r['simulationSeconds'],provenance=r['selectionProvenance'],source_line=line_no))
 table(db,'battle_runs',battle_rows)
 analysis=[];comparisons={};coverage=[]
 for s in load(CAMPAIGN/'summary.json'):
  a,b=resolve(s['unit']),resolve(s['opponent'])
  source=rawruns[s['simulationSourceMatchupId']]
  assert len(source)==s['requiredRuns']
  coverage.append(dict(matchup_id=s['matchupId'],source_matchup_id=s['simulationSourceMatchupId'],unit_key=a['unit_key'],opponent_key=b['unit_key'],shared_combat_result=s['sharedEquivalentResults'],run_count=len(source)))
  for r in source:
   # The campaign preserves focus side as owner 2, including equivalent aliases.
   assert r['result']['side2']['slug']==s['slug'],(s['unit'],r['result']['side2'])
   assert (r['unitCount'],r['opponentCount'])==(s['unitCount'],s['opponentCount']),s['matchupId']
   winner=r['winnerOwner']
   if winner not in [2,3]:
    assert r['outcome']=='draw',r['outcome']
    continue
   result=r['result'];remaining=result['remainingByOwner'];starting=result['startingHpByOwner']
   frac=remaining[str(winner)]['hp']/starting[str(winner)]
   if not (0<frac<.25):continue
   loser=3 if winner==2 else 2;lu=a if loser==2 else b;wu=b if winner==3 else a
   lc=r['unitCount'] if loser==2 else r['opponentCount'];wc=r['unitCount'] if winner==2 else r['opponentCount']
   ls=remaining[str(loser)]['units'];ws=remaining[str(winner)]['units']
   ld,wd=max(0,lc-ls),max(0,wc-ws)
   ll=None if lu['labor_seconds'] is None else ld*lu['labor_seconds'];wl=None if wu['labor_seconds'] is None else wd*wu['labor_seconds']
   casualty_valid=not any('Dismounted' in f for u in [lu,wu] for f in u['flags']) and ws<=wc and ls<=lc
   ratio=ll/wl if ll is not None and wl is not None and wl>0 and casualty_valid else None
   lt=None if lu['train_seconds'] is None else ld*lu['train_seconds'];wt=None if wu['train_seconds'] is None else wd*wu['train_seconds']
   cid=lu['unit_key']+'|'+wu['unit_key']
   if cid not in comparisons:comparisons[cid]=dict(comparison_id=cid,loser_unit_key=lu['unit_key'],winner_unit_key=wu['unit_key'],**tech_comparison(lu,wu))
   cp=comparisons[cid];timeadv=cp['loser_common_seconds'] is not None and cp['winner_common_seconds'] is not None and cp['loser_common_seconds']<cp['winner_common_seconds']-1e-8
   queue_adv=lt is not None and wt is not None and lt<wt
   econ_adv=ratio is not None and ratio<1
   sensitivity=ratio is not None and ratio*1.05/.95<1
   flags=sorted(set(lu['flags']+wu['flags']))
   capacity=math.floor(wt/lu['train_seconds']+1e-10) if wt is not None and lu['train_seconds'] is not None and lu['train_seconds']>0 else 0
   buildings_needed=math.ceil(ld/capacity) if capacity>0 else None
   extra_buildings=None if buildings_needed is None else max(0,buildings_needed-1)
   extra_labor=None if extra_buildings is None or lu['production_building_resource_labor'] is None else extra_buildings*lu['production_building_resource_labor']
   payback=extra_labor/(wl-ll) if extra_labor is not None and econ_adv else None
   # No arbitrary weighted blend with research, queue speed or army size.
   label='unresolved_labor_or_casualties' if ratio is None else 'attrition_reversal_candidate' if econ_adv else 'no_attrition_reversal'
   if econ_adv and flags:label='conditional_attrition_candidate'
   analysis.append(dict(matchup_id=s['matchupId'],source_matchup_id=s['simulationSourceMatchupId'],seed=r['seed'],
    loser_unit_key=lu['unit_key'],winner_unit_key=wu['unit_key'],loser=f"{lu['civ_name']} {lu['unit_name']}",winner=f"{wu['civ_name']} {wu['unit_name']}",
    winner_hp_fraction=frac,loser_start_count=lc,winner_start_count=wc,loser_deaths=ld,winner_deaths=wd,winner_survivors=ws,
    loser_replacement_labor=ll,winner_replacement_labor=wl,loser_to_winner_loss_labor_ratio=ratio,
    loser_queue_seconds=lt,winner_queue_seconds=wt,queue_favors_loser=queue_adv,
    loser_buildings_to_match_one_winner_building=buildings_needed,extra_loser_buildings=extra_buildings,
    extra_building_resource_labor=extra_labor,extra_building_payback_exchanges=payback,
    attrition_favors_loser=econ_adv,passes_5_percent_rate_sensitivity=sensitivity,
    common_research_faster_for_loser=timeadv,common_research_cheaper_for_loser=cp['common_loser_cost_dominates'],
    loser_gold_free=lu['gold']==0,winner_gold_cost=wu['gold'],gold_exhaustion_candidate=lu['gold']==0 and wu['gold']>0,
    hp_equivalent_winner_replacement_labor=None if wu['labor_seconds'] is None else wc*(1-frac)*wu['labor_seconds'],
    classification=label,flags=flags,upgrade_comparison_id=cid,engine_version=r['selectionProvenance']['engineVersion']))
 table(db,'matchup_coverage',coverage);table(db,'upgrade_comparisons',list(comparisons.values()));table(db,'close_battle_analysis',analysis)
 groups=[];grouped=defaultdict(list)
 for r in analysis:grouped[r['matchup_id'],r['loser_unit_key'],r['winner_unit_key']].append(r)
 for (mid,lk,wk),rows in grouped.items():
  cov=next(x for x in coverage if x['matchup_id']==mid);ratios=[r['loser_to_winner_loss_labor_ratio'] for r in rows if r['loser_to_winner_loss_labor_ratio'] is not None]
  groups.append(dict(matchup_id=mid,loser=rows[0]['loser'],winner=rows[0]['winner'],close_runs=len(rows),total_runs=cov['run_count'],
   mean_winner_hp_percent=100*statistics.mean(r['winner_hp_fraction'] for r in rows),
   attrition_candidate_runs=sum(r['attrition_favors_loser'] for r in rows),queue_advantage_runs=sum(r['queue_favors_loser'] for r in rows),
   sensitivity_pass_runs=sum(r['passes_5_percent_rate_sensitivity'] for r in rows),
   mean_loss_labor_ratio=statistics.mean(ratios) if ratios else None,
   max_loser_buildings_to_match_winner=max((r['loser_buildings_to_match_one_winner_building'] for r in rows if r['loser_buildings_to_match_one_winner_building'] is not None),default=None),
   mean_extra_building_payback_exchanges=statistics.mean([r['extra_building_payback_exchanges'] for r in rows if r['extra_building_payback_exchanges'] is not None]) if any(r['extra_building_payback_exchanges'] is not None for r in rows) else None,
   all_recorded_runs_close_same_winner=len(rows)==cov['run_count'],
   all_close_runs_attrition_reverse=all(r['attrition_favors_loser'] for r in rows),
   clean_candidate=all(r['attrition_favors_loser'] and r['passes_5_percent_rate_sensitivity'] and not r['flags'] for r in rows),
   gold_exhaustion_candidate=rows[0]['gold_exhaustion_candidate'],
   common_research_faster_for_loser=rows[0]['common_research_faster_for_loser'],common_research_cheaper_for_loser=rows[0]['common_research_cheaper_for_loser'],
   flags=rows[0]['flags'],engine_versions=sorted({r['engine_version'] for r in rows})))
 groups.sort(key=lambda g:(not(g['clean_candidate'] and g['all_recorded_runs_close_same_winner']),g['mean_loss_labor_ratio'] if g['mean_loss_labor_ratio'] is not None else 1e9,g['loser']))
 table(db,'matchup_summary',groups)
 for name,columns in [('unit_economy','unit_key'),('gather_rates','civ_name,resource'),('battle_runs','source_matchup_id,seed'),('matchup_coverage','matchup_id'),('upgrade_comparisons','comparison_id')]:
  db.execute(f'CREATE UNIQUE INDEX idx_{name} ON {name}({columns})')
 db.execute('CREATE INDEX idx_close_matchup ON close_battle_analysis(matchup_id)')
 db.execute('CREATE VIEW reversal_candidates AS SELECT * FROM matchup_summary WHERE attrition_candidate_runs>0')
 db.execute('CREATE VIEW strongest_candidates AS SELECT * FROM matchup_summary WHERE clean_candidate=1 AND all_recorded_runs_close_same_winner=1')
 counts=dict(civilizations=len(specs),unit_variants=len(units),resource_rows=len(rates),modeled_resource_rows=sum(r['rate'] is not None for r in rates),
  source_battle_runs=len(battle_rows),matchup_rows=len(coverage),close_battle_contexts=len(analysis),close_matchup_directions=len(groups),
  economic_candidate_directions=sum(g['attrition_candidate_runs']>0 for g in groups),
  strongest_candidate_directions=sum(g['clean_candidate'] and g['all_recorded_runs_close_same_winner'] for g in groups),
  queue_advantage_directions=sum(g['queue_advantage_runs']>0 for g in groups),
  shared_research_faster_directions=sum(g['common_research_faster_for_loser'] for g in groups),
  shared_research_cheaper_directions=sum(g['common_research_cheaper_for_loser'] for g in groups),
  gold_exhaustion_directions=sum(g['gold_exhaustion_candidate'] for g in groups),
  conditional_candidate_directions=sum(g['attrition_candidate_runs']>0 and bool(g['flags']) for g in groups),
  unresolved_close_contexts=sum(r['classification']=='unresolved_labor_or_casualties' for r in analysis))
 game_source=json.loads(src['eco'].execute("select value from metadata where key='source'").fetchone()[0])
 metadata={'counts':counts,'game_source':game_source,'source_hashes':{k:sha(p) for k,p in SOURCES.items()},'campaign_runs_sha256':sha(CAMPAIGN/'runs.jsonl'),
 'assumptions':{'age':'Post-Imperial, all available upgrades; research priced in Imperial','farm_scenario':'10 workers; 1800 game-seconds; 3 seeds; reseeding; generic 2x2 mill or 3x3 Folwark with 8 covered and 2 outer farms',
 'wood_scenario':'10 workers; 8x6 forest, fixed camp; measured seconds 60–600; 3 seeds','mining_scenario':'10 workers; four mineral tiles and camp one tile away; measured seconds 60–240; 3 seeds',
 'labor':'sum(resource cost / effective resource rate) + food cost * farm wood per food / wood rate; construction during reseeding is included in farm simulation',
 'attrition':'Actual dead-unit counts, not remaining HP, determine replacement costs. Loser is an attrition candidate only if its replacement labor is lower.',
 'production':'One selected cheapest production building per side; selected by wood + 2*stone. Alternative routes retained; queue time ignores affordability and transit.',
 'upgrades':'Common tech IDs only for time and common cost; exclusive packages and distinct research buildings separate. Sums are research workload, not elapsed build order.',
 'robustness':'Candidate must survive opposing ±5% rate perturbations; this is a sensitivity assumption, not a statistical confidence bound or game validation.',
 'scope':'Village labor only; no allied team bonuses, relics, trade, market exchanges or aura coverage. Unresolved coupled income/refund mechanics flagged; no fabricated rates.',
 'outcome':'No combat result is changed. Economic candidates require a repeated-battle/position scenario before claiming a military reversal.',
 'source_warning':'Saved battle campaign mixes engine versions; equivalent combat profiles are expanded using each civilization\'s own economic inputs.'}}
 table(db,'analysis_metadata',[dict(key=k,value=v) for k,v in metadata.items()]);db.commit()
 assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
 assert len(coverage)==3591 and len(units)==1030 and len(battle_rows)==7600
 assert all(0<r['winner_hp_fraction']<.25 for r in analysis)
 assert not any(r['attrition_favors_loser'] and (r['loser_to_winner_loss_labor_ratio'] is None or r['loser_to_winner_loss_labor_ratio']>=1) for r in analysis)
 csv_write('close-battles.csv',analysis);csv_write('matchup-summary.csv',groups);csv_write('unit-economy.csv',units);csv_write('mechanic-coverage.csv',audit)
 csv_write('upgrade-comparisons.csv',list(comparisons.values()))
 civrows=[]
 for name,s in spec.items():
  civrows.append(dict(civilization=name,**{r+'_per_villager_minute':None if rate[name,r] is None else rate[name,r]*60 for r in RES},
   farm_food=s['farm_food'],farm_wood=s['farm_wood'],farm_wood_per_credited_food=s['farm_wood']/(s['farm_food']*s['farm_yield']),flags=s['flags']))
 csv_write('civilization-rates.csv',civrows)
 strongest=[g for g in groups if g['clean_candidate'] and g['all_recorded_runs_close_same_winner']]
 def rowfmt(g):return f"| {g['loser']} | {g['winner']} | {g['mean_winner_hp_percent']:.1f}% | {(1-g['mean_loss_labor_ratio'])*100:.1f}% | {g['max_loser_buildings_to_match_winner']} | {g['close_runs']}/{g['total_runs']} |"
 lines=['# Economy and close-matchup review','',
  'This is an economic attrition screen, not a rerun of reinforced combat. A battlefield loser can lose less replacement labor than the winner. That can support a prolonged-war strategy, but does not erase the winner’s surviving army or positional advantage.','',
  'Source: the user-supplied Google Drive DAT archive and its 56 civilization tech trees. The archive dates the DAT to 2026-10-29 (timezone unspecified). Its stored provenance identifies patch 188329 balance changes; the exact executable version is not embedded in the file. No external bonus tables were substituted.','',
  f"DAT SHA-256: `{game_source['sha256']}`.",'',
  '## Coverage','',*[f'- {k}: {v}' for k,v in counts.items()],'',
  'The analysis expands mechanically equivalent battle results using each actual civilization’s economy. Counts of matchup directions and seed contexts are not independent new simulations.','',
  '## Strongest modeled attrition reversals','',
  'Every recorded seed has the same close winner; replacement-labor advantage survives the stated ±5% rate sensitivity; no flagged conditional mechanics. This is a screening definition, not 95% confidence.','',
  '| Battlefield loser | Battlefield winner | Winner HP left | Loser replacement-labor saving | Loser buildings per one winner building | Close seeds |',
  '|---|---|---:|---:|---:|---:|',*[rowfmt(g) for g in strongest[:30]],'',
  'Cheap armies may need more production buildings because they replace more bodies. The building column is the maximum over the observed close seeds: ceil(loser deaths / floor(winner queue seconds / loser unit train seconds)). This respects whole-unit queues; no finite building count helps if even one loser unit takes longer than the winner’s recovery window. `extra_building_payback_exchanges` estimates how many repeated economic savings fund the extra building resource costs; construction labor, build delay and reinforcements walking to the battlefield are excluded, so this is a capital-cost diagnostic, not a combat schedule.','',
  'All close results—including non-reversals, variable winners, unresolved cases and gold-exhaustion candidates—are in `matchup-summary.csv` and SQLite. Shared/exclusive upgrade comparisons are in `upgrade_comparisons`; detailed research and production tables include all routes and costs.','',
  '## Other advantages in close losses','',
  '| Advantage for battlefield loser | Matchup directions |','|---|---:|',
  f"| Faster one-building replacement queue in at least one close seed | {counts['queue_advantage_directions']} |",
  f"| Less time for the common research package | {counts['shared_research_faster_directions']} |",
  f"| Cheaper common research package | {counts['shared_research_cheaper_directions']} |",
  f"| Gold-free unit facing a gold-costing winner | {counts['gold_exhaustion_directions']} |",'',
  'These categories overlap and are not additional proven reversals. Common research is matched by technology ID; cheaper means no resource costs more and at least one costs less, after source-recorded rewards. Exclusive upgrades and research-building costs remain separate. Research speed can indicate an earlier timing opportunity, but cannot change the already fully upgraded battle on its own. Gold exhaustion requires a finite-gold scenario.','',
  '## Gather rates','',
  '| Civilization | Food/min | Wood/min | Gold/min | Stone/min | Farm wood/food |','|---|---:|---:|---:|---:|---:|',
  *['| '+r['civilization']+' | '+' | '.join('unresolved' if r[x+'_per_villager_minute'] is None else f"{r[x+'_per_villager_minute']:.2f}" for x in ['food','wood','gold','stone'])+f" | {r['farm_wood_per_credited_food']:.4f} |" for r in civrows],'',
  '## Limits that matter','',
  '- Khitan pasture food gathering is unresolved: the source has distinct herders, shared/annex objects and animal resources. No generic farm rate was substituted. Food-consuming Khitan units remain unscored for labor.',
  '- Church auras, coupled resource generation and death refunds are retained as explicit conditional flags. Relics, trade, garrison income, combat bounties, starting resources and free-upgrade timing are outside the settled post-Imperial villager baseline.',
  '- Farm motion remains an approximation; prior online comparisons have errors up to about 3%. Extra work stops and special-civilization trajectories are not validated against current DE captures. Three model seeds do not measure real-game uncertainty.',
  '- Rates depend on the stated layout, congestion, resource depletion and sampling window. Faster raw work or movement need not produce a monotonic gain in a small congested simulation.',
  '- Production queues, building capital and upgrades are separate dimensions. Research totals are common-tech workload, not simultaneous completion time. Missing upgrades do not earn a speed bonus.',
  '- Konnik dismounting and other flagged casualty/refund effects cannot be treated as ordinary replaceable deaths. Survivor HP damage is recorded separately; survivors may heal without replacing the unit.',
  '- The database is a complete joined review inventory for the supplied advisor roster; it is not a claim that every compiled-engine economic hook now has a validated numerical model.','',
  '## Reproduce','',
  'Run `python tools/export_army_economy.py`, `node tools/run_army_economy.mjs`, then `python tools/build_army_context.py`. Original source databases and battle results are read-only inputs.','',
  'Run `python tools/validate_army_context.py` to compare every copied source row, preserve saved battle outcomes, verify civilization identities and recompute casualty, labor, whole-unit queue and common/exclusive research relationships. Results are in `independent-validation.json`. Engine tests are `tools/farm-bonuses.test.mjs`, `tools/farm-gathering-sim.test.mjs`, `tools/gold-mining-sim.test.mjs`, and `tools/wood-gathering-sim.test.mjs`.','']
 (OUT/'README.md').write_text('\n'.join(lines));(OUT/'summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
 (OUT/'validation.json').write_text(json.dumps({'sqlite_integrity':'ok','complete_roster':True,'complete_saved_matchup_coverage':True,'all_close_hp_fractions_strictly_below_25_percent':True,'resource_accounting_checks_passed':True,'rates_complete':counts['modeled_resource_rows']==224,'combat_reversals_proven':False,'counts':counts},indent=2)+'\n')
 print(json.dumps(counts,indent=2));print('Top candidates:',json.dumps(strongest[:5],indent=2))

if __name__=='__main__':main()
