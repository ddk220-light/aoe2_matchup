"""Freeze the entire identity-aligned legacy/current disagreement inventory.

No old winner is imported as a new measurement. Physical context comes only
from the current table; old claims supply validation priorities and provenance.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
import zlib

ROOT = Path(__file__).resolve().parents[3]
SIM = ROOT / 'aoe2x/js_simulation'
CAMPAIGN = SIM / 'calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05'


def encode(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())


def main(comparison, current):
    assert not CAMPAIGN.exists(), 'inventory already frozen'
    db = sqlite3.connect(f'file:{current}?mode=ro', uri=True)
    units = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,data FROM units')}
    by_name = {(u['civilization'], norm(u['name'])): i for i, u in units.items()}
    assert len(by_name) == len(units) == 555
    cells = {(a, b): dict(outcome=o, evidenceType=e, evidenceId=i, counts=[ca, cb])
             for a, b, o, e, ca, cb, i in db.execute('SELECT a,b,outcome,evidence_type,count_a,count_b,evidence_id FROM cells')}
    assert all(a < b for a, b in cells)
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    evidence = {i: json.loads(zlib.decompressobj(zdict=dictionary).decompress(b))
                for i, b in db.execute('SELECT id,data FROM evidence')}
    claims = collections.defaultdict(list)
    sources = {}
    def collect(a, b, claim):
        assert a != b and units[a]['civilization'] != units[b]['civilization']
        key = tuple(sorted([a, b])); assert key in cells
        claims[key].append(claim)
    def read_csv(name):
        path = comparison / 'results' / name
        sources[name] = dict(sha256=sha(path), kind='comparison_csv')
        with path.open() as f:
            return list(csv.DictReader(f))
    differences = {'opposite_winner', 'old_decisive_new_close', 'old_mixed_new_decisive', 'legacy_direction_dependent'}
    for cohort in ['earlier_multi_civ', 'latest_armenians']:
        name = f'{cohort}_unique_pair_comparison.csv'
        for line, row in enumerate(read_csv(name), 2):
            if row['difference'] not in differences:
                continue
            a = by_name[row['civ_a'], norm(row['unit_a'])]
            b = by_name[row['civ_b'], norm(row['unit_b'])]
            collect(a, b, dict(source=name, line=line, category=row['difference'],
                               legacyOutcome=row['legacy_label'], currentOutcome=row['new_label'],
                               legacyPopulationRows=row['legacy_pop_row_ids'], legacyEconomicRows=row['legacy_eco_row_ids']))
    name = 'composition_coverage_conflicts.csv'
    for line, row in enumerate(read_csv(name), 2):
        b = by_name[row['opponent_civ'], norm(row['enemy_unit'])]
        for member in ('member_1', 'member_2'):
            if not row[member]:
                continue
            a = by_name[row['civ'], norm(row[member])]
            collect(a, b, dict(source=name, line=line, category=row['difference'],
                               legacyEngine=row['legacy_engine'], recipeIds=row['legacy_recipe_ids']))

    # Raw yardstick margins are concrete legacy table entries, unlike aggregate
    # ranking scores. Only complete population/economic pairs are compared.
    source = comparison / 'sources/legacy_derived_data.db'
    old = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    ref = sqlite3.connect(f"file:{comparison / 'sources/legacy_raw_reference.db'}?mode=ro", uri=True)
    names = {(c, s): n for c, s, n in ref.execute("SELECT civ_name,unit_slug,unit_name FROM ref_units WHERE age='Imperial'")}
    targets = dict(champ=('Vikings', 'champion'), paladin=('Franks', 'paladin'),
                   arb=('Britons', 'arbalester'), halb=('Britons', 'halberdier'),
                   elite_skirm=('Britons', 'imp_elite_skirm'), hussar=('Magyars', 'hussar'))
    pattern = re.compile(r'^(?:gc|ac|aa|at)_(30v30|3k)_vs_(champ|paladin|arb|halb|elite_skirm|hussar)_raw$')
    grouped = collections.defaultdict(dict)
    for row_id, c, s, metric, value in old.execute("SELECT id,civ_name,unit_slug,score_type,score_value FROM battle_scores WHERE build_number='177723' AND age='imperial' AND score_type LIKE '%_raw'"):
        m = pattern.fullmatch(metric)
        if not m:
            continue
        scale, target = m.groups(); key = (c, s, target)
        if scale in grouped[key]:
            assert grouped[key][scale]['value'] == value, ('duplicate legacy margins disagree', key, scale)
            grouped[key][scale]['rows'].append(row_id)
        else:
            grouped[key][scale] = dict(value=value, rows=[row_id])
    yardsticks = []
    for (c, s, target), scales in sorted(grouped.items()):
        if set(scales) != {'30v30', '3k'}:
            continue
        tc, ts = targets[target]
        a = by_name.get((c, norm(names.get((c, s), ''))))
        b = by_name.get((tc, norm(names.get((tc, ts), ''))))
        if a is None or b is None or units[a]['civilization'] == units[b]['civilization']:
            continue
        key = tuple(sorted([a, b])); cell = cells[key]
        values = [scales[t]['value'] for t in ['30v30', '3k']]
        legacy = 'a_win' if min(values) >= 10 else 'b_win' if max(values) <= -10 else 'close_or_mixed'
        new = cell['outcome']
        if a != key[0]:
            new = {'a_win': 'b_win', 'b_win': 'a_win'}.get(new, new)
        category = ('opposite_winner' if legacy != new else 'same_winner') if legacy in ('a_win', 'b_win') and new in ('a_win', 'b_win') else 'old_decisive_new_close' if legacy in ('a_win', 'b_win') else 'old_mixed_new_decisive' if new in ('a_win', 'b_win') else 'both_nondecisive'
        row = dict(civ=c, slug=s, targetCiv=tc, targetSlug=ts, unitA=a, unitB=b, legacyOutcome=legacy,
                   currentOutcome=new, category=category, scales=scales)
        yardsticks.append(row)
        if category in differences:
            collect(a, b, dict(source='legacy_derived_data.db', category='yardstick_' + category,
                               legacyBuild='177723', rawMarginRowIds=sum([x['rows'] for x in scales.values()], [])))
    sources['legacy_derived_data.db'] = dict(sha256=sha(source), kind='raw_yardstick_margins')

    frozen_path = SIM / 'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
    frozen = json.loads(frozen_path.read_text())
    representatives = {}
    variants = json.loads((SIM / 'calibration/reports/civ-matchups-first-pass-provisional-2026-11-02/variant-profiles.json').read_text())
    variant_by_key = {v['key']: v for v in variants}
    for v in variants:
        representatives.setdefault(v['profileHash'], v['key'])
    jobs = {}; listed_cells = []
    for (a, b), refs in sorted(claims.items()):
        cell = cells[a, b]; e = evidence[cell['evidenceId']]; context = e['context']
        assert set(context['profiles']) == {units[a]['profileHash'], units[b]['profileHash']}
        for i in (a, b):
            assert variant_by_key[units[i]['key']]['profileHash'] == units[i]['profileHash']
            own = frozen['profiles'][units[i]['key']]['mechanics']
            rep = frozen['profiles'][representatives[units[i]['profileHash']]]['mechanics']
            assert {k: v for k, v in own.items() if k != 'civilization'} == {k: v for k, v in rep.items() if k != 'civilization'}
        digest = hashlib.sha256(encode(context).encode()).hexdigest()
        job_id = 'mv_' + digest[:24]
        job = jobs.setdefault(job_id, dict(id=job_id, contextHash=digest, pairKey=e['pairKey'], context=context,
                    teamKeys=[representatives[h] for h in context['profiles']], profileHashes=context['profiles'],
                    counts=context['counts'], scenarioHash=context['scenarioHash'], family=context['family'],
                    engineFamily=context['engineFamily'], evidenceIds=[], displayedCells=0, categories=[]))
        assert job['context'] == context
        job['displayedCells'] += 1
        job['evidenceIds'] = sorted(set(job['evidenceIds'] + [cell['evidenceId']]))
        job['categories'] = sorted(set(job['categories'] + [r['category'] for r in refs]))
        listed_cells.append(dict(unitA=units[a], unitB=units[b], current=cell, validationJob=job_id, claims=refs))
    # Keep related cells from all civilizations: identical profiles/contexts can
    # share the same measured result, but never swap physical owner orientation.
    for job in jobs.values():
        job['priority'] = (10 if 'opposite_winner' in job['categories'] else 0) + (5 if any(evidence[i]['evidenceType'] != 'observed' for i in job['evidenceIds']) else 0)
    CAMPAIGN.mkdir(parents=True)
    (CAMPAIGN / 'sources').mkdir()
    for name, info in sources.items():
        if info['kind'] != 'comparison_csv':
            continue
        data = (comparison / 'results' / name).read_bytes()
        (CAMPAIGN / 'sources' / (name + '.gz')).write_bytes(gzip.compress(data, mtime=0))
    for name, rows in [('mismatches.jsonl.gz', listed_cells), ('jobs.jsonl.gz', sorted(jobs.values(), key=lambda j: (-j['priority'], j['id']))), ('yardstick-comparison.jsonl.gz', yardsticks)]:
        (CAMPAIGN / name).write_bytes(gzip.compress((''.join(encode(r) + '\n' for r in rows)).encode(), mtime=0))
    (CAMPAIGN / 'sources/source-manifest.json').write_text((comparison / 'results/source-manifest.json').read_text())
    original = [dict(evidenceId=i, evidence=evidence[i]) for i in sorted({cells[k]['evidenceId'] for k in claims})]
    (CAMPAIGN / 'original-evidence.jsonl.gz').write_bytes(gzip.compress((''.join(encode(x) + '\n' for x in original)).encode(), mtime=0))
    report = dict(displayedMismatchCells=len(claims), physicalValidationJobs=len(jobs),
                  minimumFreshSeeds=3 * len(jobs), categories=dict(collections.Counter(r['category'] for v in claims.values() for r in v)),
                  evidenceTypes=dict(collections.Counter(cells[k]['evidenceType'] for k in claims)),
                  yardstickComparisons=len(yardsticks), currentDatabaseSha256=sha(current), sources=sources,
                  frozenProfileManifestSha256=sha(frozen_path),
                  scope='All raw winner/decisiveness disagreements, legacy direction conflicts, conflicting composition claims, and raw yardstick-margin disagreements. Recommendation-only formula differences are excluded.')
    (CAMPAIGN / 'inventory-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'scope')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--current-db', type=Path, required=True)
    args = parser.parse_args()
    main(args.comparison, args.current_db)
