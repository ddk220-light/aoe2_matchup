"""Build gathering-comparison.csv for the army-economics review (review only)."""
import csv, json

SCR = '/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/review-gathering'
MT = '/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt'
OUT = '/home/user/aoe2_matchup/docs/army-economics-review/gathering-comparison.csv'

rt = json.load(open(f'{SCR}/runtime_rates.json'))
tt_missing = json.load(open(f'{SCR}/techtree_missing.json'))
README = {}
for r in csv.DictReader(open(f'{MT}/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/civilization-rates.csv')):
    README[r['civilization']] = r
rev = {r['civ_name']: json.loads(r['missing_standard_land_upgrades'])
       for r in csv.DictReader(open(f'{MT}/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/civilization-review.csv'))}

TT = 'SiegeEngineers/aoe2techtree @e56728e (Implement DE Update 188329, 2026-10-27): data.json + en strings'
TT_TEXT = 'aoe2techtree @e56728e en civ help text (DE update 188329)'
rows = []
def add(civ, topic, field, dataset, online, source, verdict, note):
    rows.append(dict(civ=civ, resource_or_mechanic=topic, field=field, dataset_value=dataset,
                     online_or_independent_value=online, source_and_version=source, verdict=verdict, note=note))

# ---------------- Generic DAT parameters and published measurements ----------------
G = 'All (generic)'
add(G, 'food: farm', 'farm generation cap (food/s)', '0.40 food/s, buffer 15', '0.4 food/s regeneration, invisible stockpile cap 15 (=24 food/min ceiling)',
    'AoE2 fandom wiki Farm (AoE2) page via web search 2026-11-12; Feb-2025 reddit "farming cap is still 24"', 'match',
    'Explains why farmer work-rate bonuses barely move food/min: farms, not villagers, are the bottleneck after Hand Cart.')
add(G, 'food: farm', 'Imperial farm food (all 3 mill upgrades)', '550 (175+75+125+175)', '550 (175 base +75/+125/+175)', 'DAT replay; matches long-standing DE values (no conflicting online value found)', 'match', '')
add(G, 'food: farm', 'farm cost / reseed cost', '60 wood, 15 s build', '60 wood', 'DAT; DE standard', 'match', 'Reseed build time 15 s is a model assumption (DAT build work), not measured.')
add(G, 'food: farm', 'farmer work rate (all upgrades)', '0.53 farm-units/s (above 0.40 cap)', 'wiki: villager rates outpace the farm rate after Hand Cart', 'fandom Farm page (search summary)', 'match', '')
add(G, 'food: farm', 'farmer carry', '21 (10 -> WB x1.2695 -> 13, +1 Heavy Plow, x1.5 Hand Cart)', 'not found online at this precision', 'DAT', 'not-verifiable', 'Integer rounding of carry after each upgrade is an assumption.')
add(G, 'all', 'villager speed (Wheelbarrow+Hand Cart)', '0.968 tiles/s (0.8 x1.1 x1.1)', '0.8 base, +10% each', 'DAT; DE standard', 'match', '')
add(G, 'food: farm', 'food/villager-min, full upgrades, 10 farms around 2x2 mill', '23.54', '24.40 (8 farms around TC, 2019/20 DE)', 'Steam guide 1932327114 (old DE patch; TC, forced endpoint deposit)', 'within-tolerance', '-3.5%; different geometry and patch; documented in farms-2026-11-09.')
add(G, 'food: farm', 'food/villager-min, Hand Cart + Heavy Plow, near/outer farm', '23.99 / 23.35 (model in source geometry)', '24.01 / 23.54', 'reddit r/aoe2 18l91t2 (Dec 2023, scenario editor)', 'match', '-0.1% / -0.8%')
add(G, 'food: farm', 'food/villager-min, Hand Cart + Heavy Plow', '23.54 (headline layout)', '23.62', 'AoE forums how-to-nerf-khitans #183 (Jun 2025, after update 147949)', 'match', '-0.3%; layout unspecified.')
add(G, 'food: farm', 'food/villager-min, cap', '23.54', '~24 (cap)', 'reddit r/aoe2 1ipzw3v (Feb 2025, multiplayer)', 'within-tolerance', '-1.9%: drop-off walking keeps the model just under the hard cap.')
add(G, 'food: farm', 'Folwark-ring generic farmers (3x3 drop site, 8 farms, 175 food)', '20.86 adj / 19.91 corner (model)', '20.69 / 19.35', 'vixark.com Folwark Farming Analysis (date/build unknown; 286 obs)', 'within-tolerance', '+0.8% / +2.9%')
add(G, 'wood', 'lumberjack work rate (DBA+BS+TMS)', '0.6178 wood/s (0.39 x1.2 x1.2 x1.1)', '0.39 base; TMS +10%', 'Liquipedia Two-Man Saw; fandom lumberjack 0.39/s (search summaries)', 'match', '')
add(G, 'wood', 'wood/villager-min, full upgrades', '30.43', '31.60', 'reddit r/aoe2 1ilig6h (Feb 2025; 12 lumberjacks, 3 camps, 14 min)', 'within-tolerance', '-3.7% vs this test; model -0.5% in a matched one-tile-gap layout, +4% adjacent-camp layout.')
add(G, 'wood', 'wood/villager-min, full upgrades (analytical)', '30.43', '30.42', 'reddit r/aoe2 fes2fb (older analytical estimate)', 'match', '0.0%')
add(G, 'wood', 'wood/villager-min, no Two-Man Saw (analytical)', '28.24', '28.32', 'reddit r/aoe2 fes2fb', 'match', '-0.3%')
add(G, 'gold', 'gold miner work rate (GM+GSM)', '0.5025 gold/s (0.38 x1.15 x1.15)', '0.38 base, +15% each', 'DE standard values', 'match', '')
add(G, 'gold', 'gold/villager-min, full upgrades', '27.06 (10 workers, 4 tiles, congestion)', '29.27 (one tile from camp, no bumping)', 'forgottenempires.net gold/relics strategy page (patch unstated)', 'version-difference', '-7.5%; model single uncongested worker gives 29.24 (-0.1%). Gap is the modelled crowding of 10 miners, a layout choice not an error.')
add(G, 'stone', 'stone miner work rate (SM+SSM)', '0.4761 stone/s (0.36 x1.15 x1.15)', '0.36 base, +15% each', 'DE standard values', 'match', 'No independent post-Imperial stone gathering test was found; stone uses the gold engine and layout.')
add(G, 'stone', 'stone/villager-min, full upgrades', '25.59', 'none found', '-', 'not-verifiable', 'Stone matters most because of the x3 weight.')
add(G, 'all', 'resource weights', 'food 1, wood 1, gold 1.5, stone 3', 'spec: food 1, wood 1, gold 1.5, stone 3', 'army_context.validation.json / aoe2x/army_economics.py', 'match', '')
add(G, 'all', '+-5% rate sensitivity', 'ratio*1.05/0.95<1 in tools/build_army_context.py (offline close-battle screen only)', 'spec: +-5% sensitivity', 'repo code', 'within-tolerance', 'Applied to the offline reversal screen; the live page headline shows a % difference with no +-5% band.')
add(G, 'all', 'coverage 56 civs x 4 resources', 'runtime: 224/224 activities; README/summary.json: 223/224', '224 expected', 'army_context.db vs army-context-2026-11-10/summary.json', 'mismatch', 'The missing row in README is Khitans food (pasture). Runtime now uses the 25.20 online proxy; README table, summary.json and civilization-rates.csv are stale.')

# ---------------- Tech-tree availability for every civ ----------------
for civ in sorted(rt):
    miss = tt_missing[civ]
    ok = sorted(miss) == sorted(rev[civ])
    add(civ, 'all', 'missing generic eco upgrades', '; '.join(sorted(rev[civ])) or 'none', '; '.join(sorted(miss)) or 'none', TT,
        'match' if ok else 'mismatch', '')

# ---------------- Per-civ rates vs class baseline and online bonus text ----------------
BASE = dict(food=23.54, wood={True: 30.43, False: 28.24}, gold={True: 27.06, False: 23.75}, stone={True: 25.59, False: 22.44})
NEED = dict(wood='Two-Man Saw', gold='Gold Shaft Mining', stone='Stone Shaft Mining')
special = {
 ('Aztecs','food'):('carry +3','+0.8%','within-tolerance','Farm cap limits the carry gain; wiki lists Aztecs among civs hitting the 24/min cap.'),
 ('Aztecs','wood'):('Villagers carry +3','+3.2%','within-tolerance','Online text confirms the bonus; magnitude is model-derived.'),
 ('Aztecs','gold'):('Villagers carry +3','+2.1%','within-tolerance',''),
 ('Aztecs','stone'):('Villagers carry +3','+1.6%','within-tolerance',''),
 ('Armenians','wood'):('Mule Cart technology effects +40% (DBA/BS each +28%)','raw +13.8% vs no-TMS; model +9.4%','within-tolerance','DAT multiplier 1.06667 per wood tech = +40% of +20%; confirmed by online text.'),
 ('Armenians','gold'):('Mule Cart technology effects +40% (+21% per level)','raw +10.7%; model +8.8%','within-tolerance',''),
 ('Armenians','stone'):('+40% on Stone Mining (no Stone Shaft)','raw +5.2%; model +5.9%','within-tolerance','Small excess is drop-site/footprint noise (Mule Cart footprint used as camp).'),
 ('Berbers','food'):('Villagers move +10%','+0.5%','within-tolerance',''),
 ('Berbers','wood'):('Villagers move +10%','+1.4%','within-tolerance',''),
 ('Berbers','gold'):('Villagers move +10%','+1.1%','within-tolerance',''),
 ('Berbers','stone'):('Villagers move +10%','+1.5%','within-tolerance',''),
 ('Bohemians','food'):('Fervor affects villagers (+15% speed)','+0.6%','within-tolerance',''),
 ('Bohemians','wood'):('Fervor affects villagers (+15% speed)','+1.7%','within-tolerance',''),
 ('Bohemians','gold'):('Fervor affects villagers (+15% speed)','+1.3%','within-tolerance',''),
 ('Bohemians','stone'):('Fervor affects villagers (+15% speed)','+2.4%','within-tolerance',''),
 ('Celts','wood'):('Lumberjacks work +15%','+11.2%','within-tolerance','Work bonus diluted by walking/felling; Celts lack Two-Man Saw (confirmed).'),
 ('Danes','food'):('Fishing Ships and Villagers drop off +5% food','expected ~24.71 (+5%)','mismatch','DAT tech 1494 "C-Bonus, Villagers & Fishing Ships +10% food" (resource 299 +5.01, hook 35) is never activated by the extractor: required_techs [0,...] with required_count 0 is treated as "needs tech 0". Bonus is in the official 188329 text and the official Danes deep dive.'),
 ('Georgians','food'):('Fortified Church: +10% work rate, 9 tiles','+0.8%','within-tolerance','Full aura coverage assumed (user decision); farm cap absorbs most of it. README table shows the pre-aura 23.54.'),
 ('Georgians','wood'):('+10% work rate aura','+6.6% vs no-TMS','within-tolerance','README table (28.02) is pre-aura; runtime uses 30.09.'),
 ('Georgians','gold'):('+10% work rate aura','+10.0% vs no-GSM','within-tolerance','README 23.91 is pre-aura; runtime 26.13.'),
 ('Georgians','stone'):('+10% work rate aura','+9.3%','within-tolerance','README 25.90 pre-aura; runtime 27.96.'),
 ('Hindustanis','gold'):('Grand Trunk Road: all gold income +10%','+7.5%','within-tolerance','DAT: gold-miner work x1.10; walking dilutes it. Trade/relic parts excluded.'),
 ('Khitans','food'):('Pastures replace Farms','25.20 (online proxy)','match','Equals the cmfrydos Jun-2025 lifecycle test after update 147949 (HC + 2nd pasture upgrade) by construction; dev notes say herders are ~+7% vs un-upgraded farmers (25.20/23.54 = +7.1%). Not verified for Imperial (Transhumance) or this DAT.'),
 ('Khmer','food'):('Farmers do not need drop sites','+1.0%','within-tolerance','DAT also has farmer work x0.95 (not in help text; forum mentions a -3% nerf). Irrelevant at the farm cap.'),
 ('Koreans','stone'):('Stone miners work +20%','+17.8%','within-tolerance',''),
 ('Malians','gold'):('Villagers drop off +10% gold','+10.0%','match','Runtime 29.76; README table still shows 27.06 (stale).'),
 ('Mayans','food'):('Resources last +15% longer','-0.4%','match','DAT: x1.15 yield with lower work rate; collection speed unchanged, farm wood/food 0.0949 (60/632.5).'),
 ('Mayans','wood'):('Resources last +15% longer','+1.9%','within-tolerance','Fewer tree changes.'),
 ('Mayans','gold'):('Resources last +15% longer (no Gold Shaft)','+0.1%','match',''),
 ('Mayans','stone'):('Resources last +15% longer','+0.8%','match',''),
 ('Muisca','gold'):('Team: natural gold lasts +15% longer','+0.0%','match','Longer-lasting, not faster: correctly no rate gain.'),
 ('Poles','food'):('Folwark: 10% of new farm food collected instantly','26.51 vs model steady state 25.71','mismatch','+3.1% start-up artifact: each covered farm credits 55 instant food at t=0 and again at its single reseed inside the 30-min window. 1800-9000 s of the same model gives 25.71. Online wiki (search summary) says 8% (formerly 10%); DAT says 10% -> version question.'),
 ('Poles','stone'):('Stone miners generate gold','8.53 gold per 25.59 stone (33.3%)','match','Wiki: reduced from 50% to 33% (Dynasties of India).'),
 ('Romans','food'):('Villagers gather +5%','+5.0%','match','DAT raises farm generation x1.05 as well, so the cap moves.'),
 ('Romans','wood'):('Villagers gather +5%','+4.2%','match',''),
 ('Romans','gold'):('Villagers gather +5%','+4.0%','match',''),
 ('Romans','stone'):('Villagers gather +5%','+5.7%','within-tolerance',''),
 ('Sicilians','food'):('Farm upgrades +125% food','+1.1%','match','Rate ~unchanged; benefit is farm wood/food 0.0589 = 60/1018.75.'),
 ('Slavs','food'):('Farmers work +15%','+15.1%','match','DAT farmer x1.23 and farm generation x1.15; community: Slav farm growth rate is raised with villager speed.'),
 ('Turks','gold'):('Gold miners work +25%','+20.5%','within-tolerance',''),
 ('Burgundians','food'):('Burgundian Vineyards: farmers slowly generate gold','+1.58 gold per food villager-min','not-verifiable','DAT 2 gold per active farming minute; old forum arithmetic ~1 gold/min/farmer. Rate depends on engine semantics.'),
 ('Shu','wood'):('Lumberjacks generate food','+2.13 food per 30.43 wood (7%)','not-verifiable','Official page: "a small amount of food"; no number online.'),
 ('Vietnamese','wood'):('Paper Money: lumberjacks slowly generate gold','+1.95 gold per wood villager-min','not-verifiable','Forum estimates 0.75-1.27 g/min in Castle Age (older version).'),
}
for civ in sorted(rt):
    miss = set(tt_missing[civ])
    for res in ('food', 'wood', 'gold', 'stone'):
        act = rt[civ][res]
        val = act[res]
        if res == 'food':
            base = BASE['food']; btxt = '23.54 (generic farm)'
        else:
            full = NEED[res] not in miss
            base = BASE[res][full]; btxt = f'{base:.2f} (generic, {"all upgrades" if full else "no " + NEED[res]})'
        co = '; '.join(f'{k} {v:+.2f}' for k, v in act.items() if k != res and abs(v) > 1e-9)
        ds = f'{val:.2f}' + (f' [coproduct/input: {co}]' if co else '')
        old = README[civ]
        oldv = old.get(f'{res}_per_villager_minute')
        if oldv and abs(float(oldv) - val) > 0.005:
            ds += f' (README table {float(oldv):.2f})'
        key = (civ, res)
        if key in special:
            bonus, mag, verdict, note = special[key]
            add(civ, res, 'gather rate per villager-minute vs class baseline', ds, f'{bonus}; class baseline {btxt}; model effect {mag}', TT_TEXT, verdict, note)
        else:
            d = val / base - 1
            verdict = 'match' if abs(d) <= 0.01 else 'within-tolerance' if abs(d) <= 0.03 else 'mismatch'
            add(civ, res, 'gather rate per villager-minute vs class baseline', ds, f'no {res} gathering bonus in civ text; class baseline {btxt}', TT_TEXT, verdict, f'{d*100:+.1f}% vs baseline')
    # farm wood per food
    if civ == 'Khitans':
        add(civ, 'food: pasture', 'wood per food', f'{-rt[civ]["food"]["wood"]/rt[civ]["food"]["food"]:.4f} (runtime); README 0.3429', '110 wood / 1035 food = 0.1063 (pasture 110 wood after patch; 9 x 115-food animals)', 'Update 147949 notes via search; DAT', 'match', 'README 0.3429 is 60/175 from an unused farm row: stale doc only.')
    else:
        r = rt[civ]['food']
        add(civ, 'food: farm', 'farm wood per credited food', f'{-r["wood"]/r["food"]:.4f}', '', 'DAT farm cost / farm food; civ text', 'match' if civ != 'Danes' else 'mismatch',
            'Danes should be 60/(375x1.05)=0.1524 with the +5% drop-off credit.' if civ == 'Danes' else '')

# ---------------- Mechanics / exclusions ----------------
M = [
 ('Poles','Folwark','instant food: extra or deducted from farm','deducted (farm still holds 550 total; 55 credited at build)','unresolved online (wiki: "gathers 8% of the food of any adjacent newly built farm")','fandom Folwark page (search summary); vixark analysis','not-verifiable','Model choice is the conservative reading; extra-food reading would raise Poles further.'),
 ('Poles','Folwark','instant share','10% (DAT resource 237 = 0.10 x farm food)','8% (formerly 10%) per wiki; 10% per older wiki text and Steam comment of 8%','fandom wiki via search, 2026-11-12','version-difference','Owner should confirm which patch is truth.'),
 ('Poles','Folwark','coverage','8 of 10 farms','-','user assumption','not-verifiable',''),
 ('Khitans','Pasture','herders per pasture / animals / food','2 herders, 9 animals, 1035 food, 110 wood','2 herders (game text); 115 food per animal and 110 wood after balance patch','aoe2techtree strings 26895; forum summary of patch notes','match',''),
 ('Khitans','Pasture','Imperial upgrade effect on rate','none added (proxy measured with 2nd upgrade, not Transhumance)','-','-','not-verifiable','More animals per pasture means fewer rebuilds; likely a small (<2%) under-estimate.'),
 ('Mongols/Cumans/Tatars','Pasture','pastures available?','no (farms)','only Khitans: "Pastures replace Farms"','aoe2techtree e56728e civ texts','match',''),
 ('Malians','gold drop-off','+10% credit','x1.10 credit','+10% more gold','aoe2techtree text','match',''),
 ('Georgians','Fortified Church aura','+10% work rate, 9 tiles','x1.10, full coverage, no building cost','+10%, 9 tiles','aoe2techtree text','match','Coverage is an owner assumption.'),
 ('Danes','food drop-off','+5% food','not modeled','+5% (text); official deep dive confirms extra food','aoe2techtree e56728e; ageofempires.com Danes deep dive','mismatch','Extraction bug, see food row.'),
 ('Portuguese','Feitoria','trickle resources','excluded (inventory only)','Imperial unique building generating all 4 resources','aoe2techtree text','not-verifiable','Not villager labor; exclusion is consistent with spec but not stated in the README limits list.'),
 ('Hindustanis/Persians','Caravanserai','trade','excluded','-','-','not-verifiable','Trade excluded by spec.'),
 ('Wei','Tuntian','soldier food trickle','excluded by user','-','user decision 2026-11-11','not-verifiable',''),
 ('Wei','free villager per eco tech','one-off','excluded','-','-','match','One-off grant.'),
 ('Gurjaras','livestock in Mills','passive food','excluded (needs livestock)','-','-','not-verifiable',''),
 ('Malay/Japanese/Dravidians/Danes','fish traps/fishing','water food','excluded (land model)','Malay fish traps +200% food','aoe2techtree','not-verifiable','Land-map assumption.'),
 ('Aztecs/Burgundians/Huns/Armenians','relic income','relics','excluded','-','-','match','Consistently excluded as conditional.'),
 ('Saxons/Wu/Lithuanians/Ethiopians/Dravidians','one-off grants','building/age grants','excluded','-','-','within-tolerance','Wu +55 food per military building could arguably offset the production-building investment in the headline (open question).'),
 ('Tupi','unit refund 15%','death refund','excluded/conditional','15%','aoe2techtree','not-verifiable','Belongs to replacement accounting, not gathering.'),
 ('Mapuche','gold from kills','combat income','excluded','+3 gold','aoe2techtree','match',''),
 ('Varangians','gold from sheep/hunt/fish','non-farm food gold','excluded (not post-Imperial land)','-','aoe2techtree','match',''),
 ('Spanish','+20 gold per tech','research reward','in research ledger, not gathering','+20 gold','aoe2techtree','match',''),
]
for civ, mech, field, ds, online, src, verdict, note in M:
    add(civ, mech, field, ds, online, src, verdict, note)

with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
from collections import Counter
print(len(rows), Counter(r['verdict'] for r in rows))
for r in rows:
    if r['verdict'] == 'mismatch': print('MISMATCH', r['civ'], r['resource_or_mechanic'], r['field'], r['dataset_value'], r['note'][:80])
