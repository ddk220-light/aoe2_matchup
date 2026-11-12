#!/usr/bin/env python3
"""Audit online wood-rate comparisons, keeping banked/carry endpoints explicit.

The source facts below were read from their public pages on 2026-11-09.
This script does not rerun or alter the simulation.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'aoe2x/js_simulation/calibration/economy/wood-2026-11-09'
model=json.loads((OUT/'comparison.json').read_text())
manifest=json.loads((OUT/'manifest.json').read_text())
for name in ['tools/wood-gathering-sim.mjs','tools/gold-mining-sim.mjs']:
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==manifest['code_sha256'][name]

def case(label,name,a,b,reference,url,quality,limits):
    trial=next(t for t in model['trials'] if t['name']==name)
    w=next(w for w in trial['windows'] if w['start']==a and w['end']==b)
    # Independent denominator/accounting checks on the saved result.
    banked=w['banked']*60/(b-a)/w['workers']
    adjusted=(w['banked']+w['carried_end']-w['carried_start'])*60/(b-a)/w['workers']
    assert abs(banked-w['banked_per_worker_minute'])<1e-8
    assert abs(adjusted-w['inventory_adjusted_per_worker_minute'])<1e-8
    return dict(label=label,model_trial=name,model_window=[a,b],reference_rate=reference,
        model_banked_rate=banked,model_inventory_adjusted_rate=adjusted,
        banked_difference_percent=100*(banked/reference-1),
        inventory_adjusted_difference_percent=100*(adjusted/reference-1),
        source_url=url,evidence_type=quality,comparability_limits=limits)

measured='https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/'
crowded='https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/'
older='https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/'
limits_2025='Source says 12 workers, 3 camps, 14 minutes. Model uses one independent four-worker camp. Exact forest/camp spacing, civilization, some upgrade details and ending inventory treatment are unspecified. Sources may mean banked output or harvested output.'
cases=[
    case('Double-Bit Axe, four workers/camp, one-tile gap','double-bit-four-gap-one',0,840,23.5,measured,
        'direct_in_game_measurement',limits_2025),
    case('Fully upgraded, four workers/camp, one-tile gap','full-four-gap-one',0,840,31.6,measured,
        'direct_in_game_measurement',limits_2025),
    case('Double-Bit Axe, adjacent camp alternative','double-bit-four-adjacent',0,840,23.5,measured,
        'placement_sensitivity_of_same_reference',limits_2025),
    case('Fully upgraded, adjacent camp alternative','full-four-adjacent',0,840,31.6,measured,
        'placement_sensitivity_of_same_reference',limits_2025),
    case('12 workers, one camp, three minutes','none-twelve-three-minutes',0,180,754/12/3,crowded,
        'direct_in_game_measurement','Source reports 754 wood, twelve workers, one camp, three-minute trials. Exact civilization, upgrades, forest and carried inventory are unspecified. Our no-upgrade branch is an assumption, so the difference is not a measured same-scenario simulation error.'),
    case('Fully upgraded older analytical estimate','full-ten',0,720,.507*60,older,
        'analytical_reference','Source gives 0.507 wood/s under light congestion; exact geometry and horizon differ. Publication year is not confirmed by the fetched relative-date page; treat it as older analysis, not a current DE capture.'),
    case('Without Two-Man Saw, older analytical estimate','bow-saw-ten',0,720,.472*60,older,
        'analytical_reference','Source gives 0.472 wood/s; analytical/light-congestion assumptions differ from our finite forest. It is not an independent matching DE experiment.'),
]
default=next(c for c in cases if c['model_trial']=='full-ten')['model_inventory_adjusted_rate']
historical=next(t for t in model['trials'] if t['name']=='full-ten-historical-felling')['windows'][-1]['inventory_adjusted_per_worker_minute']
audit=dict(checked_on='2026-11-09',conclusion='Partial corroboration of rates and basic mechanics; exact current-DE navigation/felling behavior remains unvalidated.',
    rate_unit='wood per villager per game-minute',cases=cases,
    measurement_issue='Published collected amounts do not consistently specify carried inventory. Keep banked-only and inventory-adjusted values distinct; do not silently choose the closer number.',
    mechanics=[dict(mechanic='Tree HP and hit count',status='corroborated_for_generic_flat_ground',
        source_url='https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705',
        evidence='Guide reports 20-HP generic trees and 15 damage per hit, requiring two hits. This agrees with the extracted DAT fields and implemented count.'),
      dict(mechanic='Exact felling timing',status='unresolved',
        source_url='https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705',
        evidence='Historical guide reports 1.5-second animations and 2.25-second two-hit felling. The supplied DAT has two-second animation/reload fields; the model assumes three seconds. The online timing does not directly validate the current assumption.',
        current_default_rate=default,historical_timing_rate=historical,
        rate_change_percent=100*(historical/default-1))],
    excluded_as_independent_validation=[dict(source_url='https://aoebuddy.com/villager-calculator',
        reason='Page says its 3,000+ scenarios were run in its own game engine. Its October 25, 2026 measurement date does not establish that the rates were measured in the shipped DE executable. Treat as another model, not independent DE ground truth.'),
      dict(source_url='https://www.youtube.com/watch?v=_UEPVFjNgfs',
        reason='Video fetch failed; no uninspected video numbers used.')],
    engine_unchanged=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'online-validation.json').write_text(json.dumps(audit,indent=2)+'\n')
lines=['# Online evidence audit for wood gathering','',audit['conclusion'],'',
    'Public sources checked on 2026-11-09. Existing simulation outputs were reused; no engine parameter was changed to match a source.','',
    '## Comparable totals and endpoint accounting','',
    'All rates below are wood per worker per game-minute. The source column is the reported rate; its inventory endpoint definition is not always explicit.','',
    '| Case | Online rate | Model banked | Difference | Model with carry change | Difference |',
    '|---|---:|---:|---:|---:|---:|',
    *[f"| [{c['label']}]({c['source_url']}) | {c['reference_rate']:.2f} | {c['model_banked_rate']:.2f} | {c['banked_difference_percent']:+.2f}% | {c['model_inventory_adjusted_rate']:.2f} | {c['inventory_adjusted_difference_percent']:+.2f}% |" for c in cases],'',
    'The strongest low-density comparison is the 14-minute, four-worker-per-camp experiment. One-tile-gap banked rates differ by -1.22% for Double-Bit Axe and -0.54% fully upgraded; the carry-adjusted differences are +0.76% and +3.05%. Adjacent-camp cases are higher and retained above rather than omitted. Matching worker/camp density and duration does not establish matching geometry or upgrades.','',
    'The twelve-worker test is less reassuring: banked output is 680 wood against the published 754, a 9.81% deficit. Adding the 43.21 wood still carried gives 723.21 harvested, reducing the numerical gap to 4.08%, but the source does not establish that this is its measurement definition. This discrepancy cannot be labelled a pass.','',
    'The older analytical estimates agree in broad scale, but are weaker evidence than a controlled current-game experiment. The previous report labelled this source as 2019; the exact publication year is unverified in the fetched page, so this audit avoids that date attribution.','',
    '## Mechanics','',
    '- [The DE Infosheet](https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705) corroborates the 20-HP/15-damage/two-hit generic-tree calculation.',
    f'- Exact impact timing remains unresolved: the historical report gives 2.25 seconds, while the current model assumes 3 seconds from different current DAT animation/reload fields. The already-run historical-timing sensitivity changes full-run collection from {default:.4f} to {historical:.4f} wood/worker-minute ({100*(historical/default-1):+.3f}%). This small rate effect does not prove either timing model correct.','',
    '## Source quality','',
    '- [2025 direct test]('+measured+'): twelve lumberjacks, three camps, fourteen minutes; exact forest/spacing/civ and endpoint inventory unspecified.',
    '- [2021 direct test]('+crowded+'): twelve workers, one camp, three-minute trials; source supplies total wood but not all upgrade/geometry details.',
    '- [Older wood analysis]('+older+'): analytical full-upgrade and no-Two-Man-Saw rates; light congestion and older assumptions.',
    '- [AoE Buddy](https://aoebuddy.com/villager-calculator) explicitly describes measurements in its own engine. It was reviewed but excluded as independent DE validation.',
    '- Spirit of the Law video fetching failed; uninspected video values were not used.','',
    '## Assessment','',
    'The model has partial external support for low-density rates and generic hit counts. A same-layout current-DE observation is still needed to validate busy-camp navigation, exact felling timing and target selection. Published references do not justify treating the numerical/model-invariant test passes as proof of DE fidelity.']
(OUT/'online-validation.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(report=str(OUT/'online-validation.md'),cases=len(cases),engine_changed=False,
    felling_rate_sensitivity_percent=audit['mechanics'][1]['rate_change_percent']),indent=2))
