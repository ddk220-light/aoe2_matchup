import copy
from types import SimpleNamespace

import capture_storage_guard as storage
import prepare_knight_v2_recapture as preparation
from prepare_knight_required_retakes import different_counts


def test_retake_selection_does_not_treat_policy_label_change_as_count_change():
    before = dict(side2=dict(count=21), side3=dict(count=27), policy="v1")
    after = dict(side2=dict(count=21), side3=dict(count=27), policy="v2")
    assert not different_counts(before, after)
    after["side2"]["count"] = 15
    assert different_counts(before, after)


def test_fresh_requests_preserve_roster_and_apply_relics_without_mutating_baseline():
    roster = [dict(id='camel_turks_unique_39_leitis', side2='heavy_camel_turks', civ2='Turks',
                   side3='elite_leitis_lithuanians', civ3='Lithuanians',
                   balance=dict(mode='geometric_shared_discount', cap=27)),
              dict(id='camel_turks_unique_50_savar', side2='heavy_camel_turks', civ2='Turks',
                   side3='savar_persians', civ3='Persians',
                   balance=dict(mode='geometric_shared_discount', cap=27))]
    before = copy.deepcopy(roster)
    rows = preparation.requests_for_subject('Lithuanians', 'paladin_lithuanians_four_relics', roster)
    assert rows[0]['scenario'] == dict(lithuanianRelics=4, opponentLithuanianRelics=4)
    assert rows[1]['scenario'] == dict(lithuanianRelics=4)
    persians = preparation.requests_for_subject('Persians', 'savar_persians', roster)
    assert len(persians) == 1 and persians[0]['side3'] == 'elite_leitis_lithuanians'
    assert roster == before
    assert not ({row['id'] for row in rows} & {row['id'] for row in roster})


def test_storage_guard_distinguishes_wrong_disk_and_low_space(monkeypatch, tmp_path):
    import win32api
    guard = dict(root=str(tmp_path), label='SAFEHOUSE', volumeSerial=42, reserveGiB=4)
    monkeypatch.setattr(win32api, 'GetVolumeInformation', lambda _: ('SAFEHOUSE', 99))
    assert 'identity changed' in storage.archive_storage_error(guard)
    monkeypatch.setattr(win32api, 'GetVolumeInformation', lambda _: ('SAFEHOUSE', 42))
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda _: SimpleNamespace(free=3 * 2**30))
    assert 'reserve reached' in storage.archive_storage_error(guard)
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda _: SimpleNamespace(free=5 * 2**30))
    assert storage.archive_storage_error(guard) is None


def test_storage_disconnect_returns_pause_reason(monkeypatch, tmp_path):
    import pywintypes
    import win32api
    def disconnected(_):
        raise pywintypes.error(21, 'GetVolumeInformation', 'The device is not ready')
    monkeypatch.setattr(win32api, 'GetVolumeInformation', disconnected)
    guard = dict(root=str(tmp_path), label='SAFEHOUSE', volumeSerial=42)
    assert 'Archive unavailable' in storage.archive_storage_error(guard)
