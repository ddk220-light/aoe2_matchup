import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conditional_donut import activate_conditional_donut
from run_champi_comparison_capture import read, save


def setup_case(tmp_path, losses):
    campaign = dict(slug='ranged', workDirectory=str(tmp_path), total=5,
                    conditionalDonut=dict(pending=True, manifest='deferred.json', minimumLosses=3))
    queue = dict(campaigns=[campaign], total=5)
    arena, deferred, results = [], [], []
    for i in range(1, 6):
        arena.append(dict(id=f'arena_{i}', layout='Arena', opponentIndex=15, iteration=i, subjectOwner=2))
        deferred.append(dict(id=f'donut_{i}', layout='Donut', opponentIndex=15, iteration=i, subjectOwner=2))
        run = tmp_path / f'run_{i}'
        save(run / 'manifest.json', dict(capture=dict(winnerOwner=3 if i <= losses else 2)))
        results.append(dict(jobId=f'arena_{i}', status='verified', runDirectory=str(run)))
    save(tmp_path / 'manifest.json', dict(matchups=arena))
    save(tmp_path / 'deferred.json', dict(matchups=deferred))
    save(tmp_path / 'capture/status.json', dict(results=results))
    return queue, campaign


@pytest.mark.parametrize('losses,expected', [(2, False), (3, True)])
def test_majority_activates_only_needed_frozen_trials(tmp_path, losses, expected):
    queue, campaign = setup_case(tmp_path, losses)
    assert activate_conditional_donut(queue, campaign, tmp_path) is expected
    assert campaign['total'] == (10 if expected else 5)
    assert not campaign['conditionalDonut']['pending']
    assert not activate_conditional_donut(queue, campaign, tmp_path)
    assert len(read(tmp_path / 'manifest.json')['matchups']) == campaign['total']


def test_missing_trial_blocks_decision(tmp_path):
    queue, campaign = setup_case(tmp_path, 3)
    status = read(tmp_path / 'capture/status.json')
    status['results'].pop()
    save(tmp_path / 'capture/status.json', status)
    with pytest.raises(ValueError, match='every Arena trial verified'):
        activate_conditional_donut(queue, campaign, tmp_path)
    assert campaign['conditionalDonut']['pending']
    assert len(read(tmp_path / 'manifest.json')['matchups']) == 5


@pytest.mark.parametrize('losses,expected', [(2, False), (3, True)])
def test_ranged_opponent_selects_by_its_losses_not_subject_losses(tmp_path, losses, expected):
    queue, campaign = setup_case(tmp_path, losses)
    campaign['conditionalDonut']['rangedOwner'] = 3
    manifest = read(tmp_path / 'manifest.json')
    for item in manifest['matchups']:
        item.update(subjectOwner=2, rangedOwner=3)
    save(tmp_path / 'manifest.json', manifest)
    deferred = read(tmp_path / 'deferred.json')
    for item in deferred['matchups']:
        item.update(subjectOwner=3, rangedOwner=2)
    save(tmp_path / 'deferred.json', deferred)
    for i in range(1, 6):
        save(tmp_path / f'run_{i}' / 'manifest.json', dict(capture=dict(winnerOwner=2 if i <= losses else 3)))
    assert activate_conditional_donut(queue, campaign, tmp_path) is expected
    decision = read(tmp_path / 'conditional-donut-decision.json')['comparisons'][0]
    assert decision['rangedOwnerOnArena'] == 3
    assert decision['rangedLosses'] == losses
    assert len(read(tmp_path / 'manifest.json')['matchups']) == (10 if expected else 5)
