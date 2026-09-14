from continue_capture_queue import capture_decision, campaign_name


def test_capture_advances_while_publication_and_overlays_are_unfinished():
    episode = {'status': 'postprocessing'}
    assert capture_decision(episode, {'state': 'COMPLETE'}, False) == 'advance'
    assert capture_decision(episode, {'state': 'COMPLETE_WITH_FAILURES'}, False) == 'advance'


def test_existing_worker_is_adopted_until_it_releases_the_game():
    assert capture_decision({}, {'state': 'COMPLETE', 'pid': 42}, True) == 'adopt'


def test_final_exports_do_not_hold_the_game_after_explicit_lock_release():
    assert capture_decision({}, {'state': 'FINALIZING', 'captureReleased': True}, True) == 'advance'
    assert capture_decision({}, {'state': 'FINALIZING'}, True) == 'adopt'
    assert capture_decision({}, {'state': 'RUNNING', 'captureReleased': True}, True) == 'adopt'


def test_published_episode_never_recaptures_pruned_files():
    assert capture_decision({'status': 'complete'}, {}, False) == 'skip'


def test_crash_requires_recovery_instead_of_blind_next_game_clicks():
    for state in ('CRASHED', 'STOPPED_AFTER_ERRORS', 'STOPPED', 'RUNNING'):
        assert capture_decision({}, {'state': state}, False) == 'attention'
    assert capture_decision({}, {}, False) == 'start'


def test_manifest_preserves_existing_campaign_directory_name():
    assert campaign_name({'manifest': 'aoe2lab.recorder.mounted-trebuchet-all-unique.toml'}) == 'mounted-trebuchet-all-unique'
