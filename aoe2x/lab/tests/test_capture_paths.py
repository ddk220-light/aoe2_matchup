from pathlib import Path

from aoe2x.lab.capture_paths import capture_prefix


def test_short_capture_keeps_legacy_descriptive_name(tmp_path):
    assert capture_prefix(tmp_path, 'paladin_vs_bowman') == tmp_path/'raw recordings'/'paladin_vs_bowman'


def test_sidecars_fit_when_video_alone_would_fit(tmp_path):
    from auto.grpc_capture import archive_stream, copy_sidecar

    directory = tmp_path/'raw recordings'
    directory.mkdir()
    # Make the original video fit exactly while its longer frame suffix fails.
    stem = 'x' * (258 - len(str(directory.absolute())) - 1 - len('.mov'))
    assert len(str(directory/stem)+'.mov') == 258
    assert len(str(directory/stem)+'.frames.bin') > 260
    prefix = capture_prefix(tmp_path, stem)
    assert prefix.name == 'capture'
    source = str(tmp_path/'source')
    payloads = {'.frames.bin': b'frames', '.meta.json': b'{"wall0_epoch":123}',
                '.END': b'{"s1":0}', '.hp.json': b'{"rows":[1]}'}
    for suffix, payload in payloads.items():
        Path(source+suffix).write_bytes(payload)
    video = prefix.with_suffix('.mov')
    assert copy_sidecar(source+'.hp.json', video)
    archive_stream(source, video)
    for suffix, payload in payloads.items():
        assert Path(str(prefix)+suffix).read_bytes() == payload
