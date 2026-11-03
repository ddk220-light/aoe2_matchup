"""Serving, provenance and orientation contracts for the provisional advisor."""
from collections import Counter
import sqlite3

from apps.website.services.advisor import (
    DATASET, advisor_catalog, advisor_evidence, advisor_matchups,
)
from aoe2x.paths import WEBAPP_DIR


def test_complete_saved_matrix_and_all_civilizations():
    catalog = advisor_catalog()
    assert len(catalog['civilizations']) == 56
    assert len(catalog['units']) == 555
    assert {'Danes', 'Saxons', 'Varangians', 'Mapuche', 'Muisca', 'Tupi'} <= set(catalog['civilizations'])
    with sqlite3.connect(DATASET) as db:
        assert db.execute('SELECT COUNT(*) FROM cells').fetchone()[0] == 151223
        assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 68916
        assert dict(db.execute('SELECT evidence_type, COUNT(*) FROM cells GROUP BY evidence_type')) == {
            'observed': 67645, 'inferred': 22730, 'identity': 820, 'predicted_unvalidated': 60028,
        }
        assert db.execute("SELECT COUNT(*) FROM cells WHERE outcome='unresolved'").fetchone()[0] == 0


def test_every_civilization_pair_has_its_exact_unit_grid():
    catalog = advisor_catalog()
    counts = Counter(u['civilization'] for u in catalog['units'])
    total = 0
    for civilization in catalog['civilizations']:
        data = advisor_matchups(civilization)
        assert len(data['opponents']) == 55
        assert civilization not in data['opponents']
        for opponent, rows in data['opponents'].items():
            assert len(rows) == counts[civilization] * counts[opponent]
            assert len({tuple(r[:2]) for r in rows}) == len(rows)
            total += len(rows)
    assert total == 302446  # both display perspectives of the same saved cells


def test_reversing_display_preserves_the_original_fight_counts_and_evidence():
    a = advisor_matchups('Danes')['opponents']['Saxons']
    b = {(r[1], r[0]): r for r in advisor_matchups('Saxons')['opponents']['Danes']}
    opposite = {'a_win': 'b_win', 'b_win': 'a_win', 'equivalent': 'equivalent', 'close_uncertain': 'close_uncertain'}
    for row in a:
        reverse = b[tuple(row[:2])]
        assert reverse[2] == opposite[row[2]]
        assert reverse[3] == row[3]
        assert reverse[4:6] == row[4:6][::-1]
        assert reverse[6:] == row[6:]


def test_estimate_flags_and_original_provenance_survive_serving():
    with sqlite3.connect(DATASET) as db:
        rows = db.execute("SELECT evidence_id, tier, flags FROM cells WHERE evidence_type='predicted_unvalidated' AND flags>0 LIMIT 30").fetchall()
        recovered = db.execute("SELECT evidence_id FROM cells WHERE tier='repaired_engine_projection' LIMIT 1").fetchone()[0]
    assert rows
    for identifier, tier, flags in rows:
        evidence = advisor_evidence(identifier)
        assert evidence['verified'] is False and evidence['needsValidation'] is True
        assert evidence['originalPrediction']['ruleHash']
        assert evidence['originalPrediction']['sourceSha256']
        assert bool(flags & 1) == bool(evidence.get('predictionContested'))
        assert bool(flags & 2) == (tier == 'weak_model_agreement')
    projection = advisor_evidence(recovered)
    assert projection['evidenceType'] == 'predicted_unvalidated'
    assert projection['recoveryProjection']['targetPhysicsVersion'] == 'frozen-v3'
    assert projection['recoveryProjection']['validationStatus'] == 'not_validated_under_target_engine'
    assert len(projection['recoveryProjection']['seedReferences']) >= 3


def test_canonical_unit_icons_and_existing_siege_reference_are_complete():
    catalog = advisor_catalog()
    units = catalog['units'] + [u for group in catalog['reference_units'].values() for u in group]
    for unit in units:
        assert unit['icon']
        assert (WEBAPP_DIR / unit['icon'].removeprefix('/')).is_file(), unit['name']
    franks = catalog['reference_units']['Franks']
    assert any(u.get('rank') for u in franks)


def test_advisor_never_starts_a_legacy_simulation(client, monkeypatch):
    import app
    def forbidden(*args, **kwargs):
        raise AssertionError('The advisor must only read saved evidence')
    monkeypatch.setattr(app, 'get_matchup_sims', forbidden)
    monkeypatch.setattr(app, 'get_matchup_recommendations', forbidden)
    for path in ['/matchup-advisor', '/api/advisor-catalog', '/api/advisor-matchups/Varangians']:
        response = client.get(path)
        assert response.status_code == 200
    assert client.get('/api/advisor-matchups/Unknown').status_code == 404
    assert client.get('/api/advisor-evidence/999999').status_code == 404
